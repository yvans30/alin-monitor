"""Récupération brute des offres depuis LOC'annonces (page HTML publique, pas
d'API JSON — cf. app/sources/paris_locannonces/auth.py).

La requête GET initiale déclenche côté serveur une tentative de connexion
OAuth silencieuse (`prompt=none`) qui échoue (`login_required`) puis retombe
sur la page de résultats en clair : confirmé fonctionner sans aucune session
préalable (testé avec un client httpx neuf, `follow_redirects=True`).

Aucune pagination observée, y compris avec une douzaine de résultats sur une
seule page (pas de lien "page suivante" dans le HTML) : tout est donc lu en
une requête. Si la Ville de Paris paginait au-delà d'un certain volume, ce
serait à corriger le jour où ça se produit réellement.
"""

from __future__ import annotations

import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from app.config import PARIS_LOCANNONCES_BASE_URL, Settings

logger = logging.getLogger(__name__)

_TIMEOUT_SECONDS = 20.0
_MAX_RETRIES = 3
_RETRY_BACKOFF_SECONDS = 2.0
_OFFER_HREF_RE = re.compile(r"^logement/(\d+)")


class ParisLocannoncesScraperError(RuntimeError):
    """Levée après épuisement des tentatives de récupération de la page."""


async def fetch_active_offers(
    client: httpx.AsyncClient,
    access_token: str,
    settings: Settings,
) -> list[dict]:
    """Récupère la page de résultats et en extrait les offres."""
    source_cfg = settings.sources.get("paris_locannonces")
    search = (source_cfg.search if source_cfg else {}) or {}

    params = {
        "cp": search.get("cp", ""),
        "nbp": search.get("nbp", ""),
        "smin": search.get("smin", 0),
        "smax": search.get("smax", 200),
        "lmin": search.get("lmin", 0),
        "lmax": search.get("lmax", 2500),
    }

    html = await _get_with_retry(client, params)
    items = _extract_offers(html)

    logger.info("Récupération LOC'annonces : %d offre(s).", len(items))
    return items


async def _get_with_retry(client: httpx.AsyncClient, params: dict) -> str:
    last_error: Exception | None = None
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            response = await client.get(
                PARIS_LOCANNONCES_BASE_URL,
                params=params,
                headers={"Accept": "text/html"},
                follow_redirects=True,
                timeout=_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            last_error = exc
            logger.warning(
                "Erreur réseau lors de la récupération LOC'annonces "
                "(tentative %d/%d): %s",
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
                "Erreur serveur (%d) lors de la récupération LOC'annonces "
                "(tentative %d/%d).",
                response.status_code,
                attempt,
                _MAX_RETRIES,
            )
            if attempt < _MAX_RETRIES:
                await asyncio.sleep(_RETRY_BACKOFF_SECONDS)
            continue

        if response.status_code >= 400:
            logger.error(
                "LOC'annonces a refusé la requête (statut %d).", response.status_code
            )
            raise ParisLocannoncesScraperError(
                f"Requête LOC'annonces refusée (statut {response.status_code})."
            )

        return response.text

    raise ParisLocannoncesScraperError(
        f"Échec de récupération de LOC'annonces après {_MAX_RETRIES} tentatives "
        f"({type(last_error).__name__ if last_error else 'erreur inconnue'})."
    )


def _extract_offers(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    offers: list[dict] = []

    for li in soup.select("ul.row > li"):
        link = li.find("a", href=_OFFER_HREF_RE)
        if not link:
            continue  # tuiles promo ("alertes", "flyer"), pas de vraie offre

        offer_id = _OFFER_HREF_RE.match(link["href"]).group(1)
        date_limite_tag = li.find("p", class_="dateLimite")

        offers.append(
            {
                "id": offer_id,
                "date_limite_title": date_limite_tag.get("title") if date_limite_tag else None,
                "loyer_text": _tag_text(li, "loyer"),
                "loc_text": _tag_text(li, "loc"),
                "surface_text": _tag_text(li, "surface"),
                "pieces_text": _tag_text(li, "pieces"),
            }
        )

    return offers


def _tag_text(li, class_name: str) -> str | None:
    tag = li.find("span", class_=class_name)
    return tag.get_text() if tag else None
