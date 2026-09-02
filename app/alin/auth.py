"""Authentification à l'API AL'in (endpoint Keycloak "direct grant").

Endpoints découverts par observation légitime du trafic réseau de
l'utilisateur sur son propre compte (pas de rétro-ingénierie anti-bot, pas de
contournement CAPTCHA/MFA ; `x-gexrt-api-key` est une valeur publique exposée
sur https://al-in.fr/info). Flow en deux étapes : POST `ALIN_AUTH_URL`
(login/password → access_token Keycloak), puis échange de ce token contre le
`jwt_token` "maison" AL'in via `ALIN_TOKEN_EXCHANGE_URL`, seul token accepté
par l'API métier.

Règles strictes de ce module : jamais de contournement CAPTCHA/MFA (une
réponse 4xx inattendue lève directement une exception, à charge de
app/main.py de basculer vers le fallback manuel app/alin/browser.py) ; mot de
passe et token jamais loggés.
"""

from __future__ import annotations

import logging
import time

import httpx

from app.config import (
    ALIN_AUTH_URL,
    ALIN_TOKEN_EXCHANGE_URL,
    ALIN_TOKEN_REFRESH_MARGIN_SECONDS,
    Settings,
)

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 15.0
_MAX_AUTH_ATTEMPTS = 3
_RETRY_BACKOFF_SECONDS = 3.0


class AlinAuthenticationError(RuntimeError):
    """Épuisement des tentatives : à app/main.py de basculer vers le fallback manuel."""


class AlinAuthClient:
    """Gère le cycle de vie du token d'accès à l'API AL'in.

    Pas de requête de "refresh" distincte observée : on ré-authentifie
    (rejoue login/password) avant expiration du token, avec une marge.
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)
        self._owns_client = client is None
        self._access_token: str | None = None
        self._expires_at: float = 0.0

    @property
    def access_token(self) -> str | None:
        return self._access_token

    def _is_token_valid(self) -> bool:
        return self._access_token is not None and time.monotonic() < self._expires_at

    async def authenticate(self) -> str:
        """Authentifie et retourne l'access_token ; retente sur erreurs réseau/5xx, échoue net sur 4xx."""
        payload = {
            "login": self._settings.alin_email,
            "password": self._settings.alin_password.get_secret_value(),
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-gexrt-api-key": self._settings.alin_gexrt_api_key,
        }

        last_error: Exception | None = None
        for attempt in range(1, _MAX_AUTH_ATTEMPTS + 1):
            try:
                response = await self._client.post(
                    ALIN_AUTH_URL, json=payload, headers=headers
                )
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Échec réseau lors de l'authentification AL'in (tentative %d/%d): %s",
                    attempt,
                    _MAX_AUTH_ATTEMPTS,
                    type(exc).__name__,
                )
                if attempt < _MAX_AUTH_ATTEMPTS:
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                continue

            if response.status_code >= 500:
                last_error = httpx.HTTPStatusError(
                    "server error", request=response.request, response=response
                )
                logger.warning(
                    "Erreur serveur (%d) lors de l'authentification AL'in "
                    "(tentative %d/%d).",
                    response.status_code,
                    attempt,
                    _MAX_AUTH_ATTEMPTS,
                )
                if attempt < _MAX_AUTH_ATTEMPTS:
                    time.sleep(_RETRY_BACKOFF_SECONDS)
                continue

            if response.status_code >= 400:
                # Peut indiquer une vérification supplémentaire (MFA/CAPTCHA) : on n'insiste jamais.
                logger.error(
                    "Authentification AL'in refusée par l'API (statut %d). "
                    "Aucune tentative de contournement : bascule requise vers "
                    "une vérification manuelle.",
                    response.status_code,
                )
                raise AlinAuthenticationError(
                    f"L'API AL'in a refusé l'authentification (statut {response.status_code}). "
                    "Une vérification supplémentaire inattendue est peut-être requise : "
                    "intervention manuelle nécessaire (cf. app/alin/browser.py)."
                )

            try:
                data = response.json()
                keycloak_access_token = data["access_token"]
                expires_in = data["expires_in"]
            except (ValueError, KeyError) as exc:
                logger.error(
                    "Réponse d'authentification AL'in inattendue (champs manquants)."
                )
                raise AlinAuthenticationError(
                    "Réponse d'authentification AL'in dans un format inattendu."
                ) from exc

            jwt_token = await self._exchange_token(keycloak_access_token)

            self._access_token = jwt_token
            margin = ALIN_TOKEN_REFRESH_MARGIN_SECONDS
            self._expires_at = time.monotonic() + max(expires_in - margin, 0)
            logger.info("Authentification AL'in réussie.")
            return jwt_token

        logger.error(
            "Authentification AL'in échouée après %d tentatives.", _MAX_AUTH_ATTEMPTS
        )
        raise AlinAuthenticationError(
            f"Échec de l'authentification AL'in après {_MAX_AUTH_ATTEMPTS} tentatives "
            f"({type(last_error).__name__ if last_error else 'erreur inconnue'})."
        )

    async def _exchange_token(self, keycloak_access_token: str) -> str:
        """Échange le token Keycloak contre le token "maison" AL'in.

        Pas de header Authorization ici (observé) : le token Keycloak est
        transmis dans le corps JSON, pas en Bearer.
        """
        try:
            response = await self._client.post(
                ALIN_TOKEN_EXCHANGE_URL,
                json={"access_token": keycloak_access_token},
                headers={"accept": "application/json", "content-type": "application/json"},
            )
        except httpx.HTTPError as exc:
            logger.error("Échec réseau lors de l'échange de token AL'in: %s", type(exc).__name__)
            raise AlinAuthenticationError(
                "Échec réseau lors de l'échange de token AL'in."
            ) from exc

        if response.status_code >= 400:
            logger.error(
                "Échange de token AL'in refusé par l'API (statut %d).",
                response.status_code,
            )
            raise AlinAuthenticationError(
                f"L'API AL'in a refusé l'échange de token (statut {response.status_code})."
            )

        try:
            data = response.json()
            if not data.get("success", False):
                raise KeyError("success=false")
            return data["jwt_token"]
        except (ValueError, KeyError) as exc:
            logger.error("Réponse d'échange de token AL'in inattendue (champs manquants).")
            raise AlinAuthenticationError(
                "Réponse d'échange de token AL'in dans un format inattendu."
            ) from exc

    async def ensure_valid_token(self) -> str:
        """Retourne un access_token valide, en ré-authentifiant si nécessaire."""
        if self._is_token_valid():
            return self._access_token  # type: ignore[return-value]
        return await self.authenticate()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()
