"""Authentification pour logement-actionlogement.fr.

Aucune authentification requise : la surveillance utilise le mode de
navigation publique du site (CGU art. 11.16), qui expose les offres sans
compte. Cette classe existe uniquement pour respecter le Protocol
`SourceClient` (cf. app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings


class LogementActionLogementAuthenticationError(RuntimeError):
    """Réservée à une future bascule vers un mode authentifié, si jamais nécessaire."""


class LogementActionLogementAuthClient:
    name = "logement_actionlogement"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self) -> str:
        return ""

    async def ensure_valid_token(self) -> str:
        return ""

    async def aclose(self) -> None:
        return None
