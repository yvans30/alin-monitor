"""Récupération brute des offres depuis Espacil (page HTML publique, pas
d'API JSON — cf. app/sources/espacil/auth.py).

La page de résultats embarque un bloc JS `window.locationsList` (GeoJSON pour
la carte) qui reprend les mêmes champs que les cartes affichées, en plus
structuré. Ce n'est toutefois pas du JSON strict (tableau `tags` en quotes
simples JS), d'où une extraction champ par champ plutôt qu'un `json.loads`
direct.

Granularité résidence, pas logement individuel : chaque résultat est un
bâtiment ("Résidence Beccaria") avec un prix "à partir de" et la liste des
typologies disponibles, pas une offre précise avec loyer/surface exacts.

Une page détail par résidence est ensuite récupérée (adresse, nombre
d'appartements, détail des typologies avec fourchette de surface) : nombre de
résidences par recherche généralement faible (une poignée), donc le coût
N+1 reste négligeable. Un échec sur une page détail dégrade juste cette
résidence (champs enrichis absents) plutôt que de faire échouer tout le cycle.

Pas de pagination observée sur la liste (un seul résultat en test).
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import ESPACIL_OFFER_URL_TEMPLATE, ESPACIL_SEARCH_URL, Settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 20.0
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0
_LOCATIONS_LIST_RE = re.compile(r"window\.locationsList\s*=\s*(\{.*?)\s*</script>", re.S)
_FEATURE_SPLIT_RE = re.compile(r'"type":\s*"Feature"')
_APARTMENT_COUNT_RE = re.compile(r"(\d+)\s*(?:appartements?|logements?)", re.I)


class EspacilScraperError(RuntimeError):
    """Levée après épuisement des tentatives de récupération de la page liste."""


async def fetch_active_offers(
    client: httpx.AsyncClient,
    access_token: str,
    settings: Settings,
) -> list[dict]:
    """Récupère la page de résultats, puis enrichit chaque résidence avec sa page détail."""
    source_cfg = settings.sources.get("espacil")
    search = (source_cfg.search if source_cfg else {}) or {}

    params = {
        "txsc[profile]": search.get("profile", ""),
        "txsc[department][]": search.get("department", []),
        "txsc[city][]": search.get("city", []),
        "txsc[budget]": search.get("budget", ""),
        "txsc[context]": "location",  # jamais "accession" (achat) : hors périmètre de ce projet
    }

    html = await _get_with_retry(client, ESPACIL_SEARCH_URL, params)
    items = _extract_offers(html)

    for item in items:
        if not item.get("url"):
            continue
        try:
            detail_html = await _get_with_retry(
                client, ESPACIL_OFFER_URL_TEMPLATE.format(path=item["url"]), None
            )
        except EspacilScraperError as exc:
            logger.warning(
                "Page détail Espacil indisponible pour '%s', résidence gardée sans "
                "enrichissement (adresse/typologies): %s",
                item.get("url"),
                exc,
            )
            continue
        item.update(_extract_detail(detail_html))

    logger.info("Récupération Espacil : %d résidence(s).", len(items))
    return items


async def _get_with_retry(client: httpx.AsyncClient, url: str, params: dict | None) -> str:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.get(
                url,
                params=params,
                headers={"Accept": "text/html"},
                follow_redirects=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Erreur réseau lors de la récupération Espacil (tentative %d/%d): %s",
                attempt,
                _MAX_RETRIES,
                type(exc).__name__,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 500:
            last_error = httpx.HTTPStatusError(
                "server error", request=response.request, response=response
            )
            logger.warning(
                "Erreur serveur (%d) lors de la récupération Espacil (tentative %d/%d).",
                response.status_code,
                attempt,
                _MAX_RETRIES,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 400:
            logger.error("Espacil a refusé la requête (statut %d).", response.status_code)
            raise EspacilScraperError(f"Requête Espacil refusée (statut {response.status_code}).")

        return response.text

    raise EspacilScraperError(
        f"Échec de récupération d'Espacil après {_MAX_RETRIES} tentatives "
        f"({type(last_error).__name__ if last_error else 'erreur inconnue'})."
    )


def _extract_offers(html: str) -> list[dict]:
    match = _LOCATIONS_LIST_RE.search(html)
    if not match:
        logger.warning("Bloc window.locationsList introuvable dans la page Espacil.")
        return []

    blob = match.group(1)
    offers = []
    for block in _FEATURE_SPLIT_RE.split(blob)[1:]:
        offers.append(
            {
                "url": _string_field(block, "url"),
                "city": _string_field(block, "city"),
                "title": _string_field(block, "title"),
                "description": _string_field(block, "description"),
                "price": _string_field(block, "price"),
            }
        )
    return offers


def _string_field(block: str, name: str) -> str | None:
    match = re.search(rf'"{name}":\s*"([^"]*)"', block)
    return match.group(1) if match else None


def _extract_detail(html: str) -> dict:
    """Extrait adresse, nombre d'appartements et détail des typologies (page résidence)."""
    soup = BeautifulSoup(html, "html.parser")
    detail: dict = {"address": None, "apartment_count": None, "typologies": []}

    info_ul = soup.select_one("ul.flex.flex-col.gap-2")
    if info_ul:
        for li in info_ul.find_all("li"):
            text = li.get_text(strip=True)
            count_match = _APARTMENT_COUNT_RE.search(text)
            if count_match:
                detail["apartment_count"] = int(count_match.group(1))
            elif detail["address"] is None:
                detail["address"] = text

    mensualites_title = soup.find("h2", string="Mensualités")
    section = mensualites_title.find_parent("section") if mensualites_title else None
    if section:
        for row in section.select("div.bg-white.w-full.shadow"):
            label = row.select_one("div.h4")
            surface = row.select_one("div.flex.items-baseline.gap-1")
            price = row.select_one("div.mt-1")
            if not (label and surface and price):
                continue
            detail["typologies"].append(
                {
                    "label": label.get_text(strip=True),
                    "surface_text": surface.get_text(strip=True),
                    "price_text": price.get_text(strip=True),
                }
            )

    return detail
