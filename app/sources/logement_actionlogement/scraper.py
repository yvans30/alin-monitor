"""Récupération brute des offres depuis l'API publique de logement-actionlogement.fr
(mode sans authentification, cf. app/sources/logement_actionlogement/auth.py).

L'endpoint liste (`offers-overview`) est un POST avec un corps de recherche
géographique obligatoire (municipalités + rayon) : il n'existe pas de mode
"tout afficher" nationwide. Ces paramètres viennent de
`config/criteria.yaml` (`sources.logement_actionlogement.search`), pas de
`Criteria` (aucun champ de ce modèle commun ne correspond à une municipalité
INSEE ou un rayon en km).
"""

from __future__ import annotations

import asyncio
import logging

import httpx

from app.config import LOGEMENT_ACTIONLOGEMENT_OFFERS_OVERVIEW_URL, Settings

logger = logging.getLogger(__name__)

_PAGE_SIZE = 20
_TIMEOUT_SECONDS = 20.0
_MAX_RETRIES_PER_PAGE = 3
_RETRY_BACKOFF_SECONDS = 2.0


class LogementActionLogementScraperError(RuntimeError):
    """Levée après épuisement des tentatives, ou si la recherche n'est pas configurée."""


async def fetch_active_offers(
    client: httpx.AsyncClient,
    access_token: str,
    settings: Settings,
) -> list[dict]:
    """Récupère toutes les offres de la recherche configurée (pagination complète)."""
    source_cfg = settings.sources.get("logement_actionlogement")
    search = (source_cfg.search if source_cfg else {}) or {}

    municipalities = search.get("municipalities")
    if not municipalities:
        raise LogementActionLogementScraperError(
            "Recherche non configurée : renseignez au moins une municipalité "
            "dans config/criteria.yaml (sources.logement_actionlogement.search."
            "municipalities), l'API l'exige."
        )

    body = {
        "municipalities": municipalities,
        "searchRadiusInKm": search.get("searchRadiusInKm", 5),
        "maxRent": search.get("maxRent"),
        "typologyCodes": search.get("typologyCodes", []),
        "productGuids": search.get("productGuids", []),
    }

    all_items: list[dict] = []
    page = 0
    total_pages = 1

    while page < total_pages:
        data = await _post_page_with_retry(client, page, body)

        items = data.get("data") or []
        if not isinstance(items, list):
            logger.warning(
                "Réponse offers-overview inattendue (champ 'data' non-liste) sur la page %d.",
                page,
            )
            items = []
        all_items.extend(items)

        total_pages = data.get("totalPages", page + 1) or (page + 1)
        page += 1

    logger.info(
        "Récupération logement-actionlogement.fr : %d offre(s) sur %d page(s).",
        len(all_items),
        total_pages,
    )
    return all_items


async def _post_page_with_retry(client: httpx.AsyncClient, page: int, body: dict) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES_PER_PAGE + 1):
        try:
            response = await client.post(
                LOGEMENT_ACTIONLOGEMENT_OFFERS_OVERVIEW_URL,
                params={"size": _PAGE_SIZE, "page": page},
                json=body,
                headers={"Accept": "application/json"},
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Erreur réseau lors de la récupération des offres "
                "logement-actionlogement.fr (tentative %d/%d, page=%d): %s",
                attempt,
                _MAX_RETRIES_PER_PAGE,
                page,
                type(exc).__name__,
            )
            if attempt < _MAX_RETRIES_PER_PAGE:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                "server error", request=response.request, response=response
            )
            logger.warning(
                "Erreur serveur (%d) lors de la récupération des offres "
                "logement-actionlogement.fr (tentative %d/%d, page=%d).",
                response.status_code,
                attempt,
                _MAX_RETRIES_PER_PAGE,
                page,
            )
            if attempt < _MAX_RETRIES_PER_PAGE:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 400:
            logger.error(
                "L'API logement-actionlogement.fr a refusé la requête "
                "offers-overview (statut %d, page=%d).",
                response.status_code,
                page,
            )
            raise LogementActionLogementScraperError(
                f"Requête offers-overview refusée (statut {response.status_code})."
            )

        return response.json()

    raise LogementActionLogementScraperError(
        f"Échec de récupération de la page {page} des offres "
        f"logement-actionlogement.fr après {_MAX_RETRIES_PER_PAGE} tentatives "
        f"({type(last_error).__name__ if last_error else 'erreur inconnue'})."
    )
