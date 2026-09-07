"""Transformation des offres brutes (dicts extraits du HTML par
app/sources/espacil/scraper.py) en objets Offer.

Granularité résidence (cf. scraper.py) : `rent` est un prix "à partir de"
(le moins cher des typologies disponibles), pas le loyer exact d'un logement
précis ; `property_type` reste la liste brute des typologies ("T1, T1 bis")
plutôt qu'un code unique inventé. `surface` est reprise de la typologie dont
le prix correspond à ce "à partir de" (surface minimale de cette typologie,
pas une surface exacte de logement) ; `address`/`apartment_count`/le détail
complet des typologies viennent de la page détail (absents si son
enrichissement a échoué, cf. scraper.py).
"""

from __future__ import annotations

import re

from app.config import ESPACIL_OFFER_URL_TEMPLATE
from app.database.models import Offer, OfferStatus

_LEADING_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_SURFACE_RANGE_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:à\s*(\d+(?:[.,]\d+)?))?\s*m", re.I)


def parse_offer(raw: dict) -> Offer:
    """Convertit une résidence brute (extrait HTML) d'Espacil en Offer."""
    path = raw.get("url")
    if not path:
        raise ValueError("Résidence Espacil sans URL ('url' manquant) : impossible à parser.")

    offer_id = path.rstrip("/").rsplit("/", 1)[-1]
    rent = _leading_number(raw.get("price"))

    return Offer(
        id=offer_id,
        source="espacil",
        url=ESPACIL_OFFER_URL_TEMPLATE.format(path=path),
        first_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        last_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        title=raw.get("title") or "",
        city=raw.get("city") or "",
        address=raw.get("address") or "",
        property_type=raw.get("description") or "",
        rent=rent or 0.0,
        surface=_surface_min_for_rent(raw.get("typologies"), rent) or 0.0,
        score=0,  # calculé plus tard par app/filters/scoring.py
        status=OfferStatus.NEW,
        charges=None,
        rent_with_charges=None,
        rooms=None,
        bedrooms=None,
        availability_date=None,
        floor=None,
        has_elevator=None,
        parking_type=None,
        balconies=None,
        postal_code=None,
        department=None,
        offer_status=None,
        reserved=False,
        publication_end_date=None,
        date_publication_start=None,
        external_ref=offer_id,
        is_active=True,  # seules les résidences ayant une disponibilité actuelle apparaissent
        raw_attributes=raw,
    )


def _leading_number(text: str | None) -> float | None:
    if not text:
        return None
    match = _LEADING_NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _surface_min_for_rent(typologies: list[dict] | None, rent: float | None) -> float | None:
    """Surface minimale de la typologie dont le prix correspond au "à partir de" du résumé."""
    if not typologies or rent is None:
        return None
    for typology in typologies:
        if _leading_number(typology.get("price_text")) == rent:
            match = _SURFACE_RANGE_RE.search(typology.get("surface_text") or "")
            if match:
                return float(match.group(1).replace(",", "."))
    return None
