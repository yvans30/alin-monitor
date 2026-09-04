"""Récupération brute des offres depuis l'API AL'in (httpx).

La forme exacte des éléments `data[]` de l'endpoint liste `housing_offers`
n'a jamais été confirmée avec de vraies données — voir le parsing défensif
dans app/sources/alin/parser.py.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date

import httpx

from app.config import ALIN_API_BASE_URL, Settings

logger = logging.getLogger(__name__)

_HOUSING_OFFERS_PATH = "/housing_offers"
_TIMEOUT_SECONDS = 20.0
_PER_PAGE = 100
_MAX_RETRIES_PER_PAGE = 3
_RETRY_BACKOFF_SECONDS = 2.0


class AlinScraperError(RuntimeError):
    """Levée après épuisement des tentatives de récupération d'une page."""


async def fetch_active_offers(
    client: httpx.AsyncClient,
    access_token: str,
    settings: Settings,
) -> list[dict]:
    """Récupère toutes les offres actives sur AL'in (pagination complète), sans transformation."""
    today = date.today().isoformat()
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
    }
    base_params = {
        "per_page": _PER_PAGE,
        "publication_end_date[$gte]": today,
        "date_publication_start[$lte]": today,
    }

    all_items: list[dict] = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params = dict(base_params, page=page)
        data = await _get_page_with_retry(client, headers, params)

        items = data.get("data") or []
        if not isinstance(items, list):
            logger.warning(
                "Réponse housing_offers inattendue (champ 'data' non-liste) sur la page %d.",
                page,
            )
            items = []
        all_items.extend(items)

        pagination = (data.get("meta") or {}).get("pagination") or {}
        total_pages = pagination.get("total_pages", page) or page

        page += 1

    logger.info("Récupération AL'in : %d offre(s) sur %d page(s).", len(all_items), total_pages)
    return all_items


async def _get_page_with_retry(
    client: httpx.AsyncClient, headers: dict, params: dict
) -> dict:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES_PER_PAGE + 1):
        try:
            response = await client.get(
                f"{ALIN_API_BASE_URL}{_HOUSING_OFFERS_PATH}",
                headers=headers,
                params=params,
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Erreur réseau lors de la récupération des offres AL'in "
                "(tentative %d/%d, page=%s): %s",
                attempt,
                _MAX_RETRIES_PER_PAGE,
                params.get("page"),
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
                "Erreur serveur (%d) lors de la récupération des offres AL'in "
                "(tentative %d/%d, page=%s).",
                response.status_code,
                attempt,
                _MAX_RETRIES_PER_PAGE,
                params.get("page"),
            )
            if attempt < _MAX_RETRIES_PER_PAGE:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 400:
            # 4xx = non transitoire (token expiré, paramètres refusés) : ne pas retenter.
            logger.error(
                "L'API AL'in a refusé la requête housing_offers (statut %d, page=%s).",
                response.status_code,
                params.get("page"),
            )
            raise AlinScraperError(
                f"Requête housing_offers refusée (statut {response.status_code})."
            )

        return response.json()

    raise AlinScraperError(
        f"Échec de récupération de la page {params.get('page')} des offres AL'in "
        f"après {_MAX_RETRIES_PER_PAGE} tentatives "
        f"({type(last_error).__name__ if last_error else 'erreur inconnue'})."
    )
