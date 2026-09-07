"""Transformation des offres brutes (dicts extraits du HTML par
app/sources/paris_locannonces/scraper.py) en objets Offer.

Pas de typologie (T1/T2...) exposée sur la page liste, seulement un nombre de
pièces : `property_type` reste donc le libellé brut ("2 pièces") plutôt
qu'un code inventé.
"""

from __future__ import annotations

import re

from app.config import PARIS_LOCANNONCES_OFFER_URL_TEMPLATE
from app.database.models import Offer, OfferStatus

_LEADING_NUMBER_RE = re.compile(r"(\d+(?:[.,]\d+)?)")
_DATE_RE = re.compile(r"(\d{2})/(\d{2})/(\d{4})")


def parse_offer(raw: dict) -> Offer:
    """Convertit un élément brut (extrait HTML) de LOC'annonces en Offer."""
    offer_id = raw.get("id")
    if not offer_id:
        raise ValueError("Offre LOC'annonces sans identifiant ('id' manquant) : impossible à parser.")

    return Offer(
        id=str(offer_id),
        source="paris_locannonces",
        url=PARIS_LOCANNONCES_OFFER_URL_TEMPLATE.format(id=offer_id),
        first_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        last_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        title="",
        city=(raw.get("loc_text") or "").strip(),
        address="",  # pas d'adresse précise sur la page liste
        property_type=(raw.get("pieces_text") or "").strip(),
        rent=_leading_number(raw.get("loyer_text")) or 0.0,
        surface=_leading_number(raw.get("surface_text")) or 0.0,
        score=0,  # calculé plus tard par app/filters/scoring.py
        status=OfferStatus.NEW,
        charges=None,
        rent_with_charges=_leading_number(raw.get("loyer_text")),  # "CCC" = charges comprises
        rooms=_leading_int(raw.get("pieces_text")),
        bedrooms=None,
        availability_date=None,  # non exposé sur la page liste
        floor=None,
        has_elevator=None,
        parking_type=None,
        balconies=None,
        postal_code=None,
        department=None,
        offer_status=None,
        reserved=False,
        # "Date limite" = fin de la période de candidature, sémantique la plus proche
        # de publication_end_date parmi les champs communs (pas d'équivalent exact).
        publication_end_date=_parse_date_limite(raw.get("date_limite_title")),
        date_publication_start=None,
        external_ref=str(offer_id),
        is_active=True,  # seules les offres actuellement publiées apparaissent sur la page
        raw_attributes=raw,
    )


def _leading_number(text: str | None) -> float | None:
    if not text:
        return None
    match = _LEADING_NUMBER_RE.search(text)
    if not match:
        return None
    return float(match.group(1).replace(",", "."))


def _leading_int(text: str | None) -> int | None:
    value = _leading_number(text)
    return int(value) if value is not None else None


def _parse_date_limite(title: str | None) -> str | None:
    """Extrait la date limite de candidature (`dd/mm/YYYY` -> `YYYY-mm-dd`)."""
    if not title:
        return None
    match = _DATE_RE.search(title)
    if not match:
        return None
    day, month, year = match.groups()
    return f"{year}-{month}-{day}"
