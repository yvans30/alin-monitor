"""Transformation des offres brutes (dicts JSON de l'API AL'in) en objets Offer.

Enveloppe JSON:API confirmée sur l'endpoint détail uniquement ; l'endpoint
liste n'a jamais retourné de données réelles en test, d'où le repli sur un
format "plat" si `attributes` est absent.

LIMITE CONNUE : `district` contient en réalité une COMMUNE, pas un quartier
— d'où le mapping vers `Offer.city` et le filtre "quartier" best-effort dans
app/filters/criteria.py.
"""

from __future__ import annotations

import logging

from app.config import ALIN_OFFER_URL_TEMPLATE, OFFER_STATUS_ACTIVE
from app.database.models import Offer, OfferStatus

logger = logging.getLogger(__name__)

_flat_fallback_warned = False


def _get_attributes(raw: dict) -> dict:
    """Privilégie l'enveloppe JSON:API `attributes` ; sinon repli "plat" (loggé une seule fois)."""
    global _flat_fallback_warned
    attributes = raw.get("attributes")
    if isinstance(attributes, dict):
        return attributes

    if not _flat_fallback_warned:
        logger.warning(
            "Élément housing_offers sans enveloppe JSON:API ('attributes' "
            "absent) : repli sur un format plat, cf. app/sources/alin/parser.py."
        )
        _flat_fallback_warned = True

    return raw


def parse_offer(raw: dict) -> Offer:
    """Convertit un élément brut `data[]` de l'API AL'in en Offer, sans planter sur un champ manquant."""
    offer_id = raw.get("id")
    if not offer_id:
        raise ValueError("Offre AL'in sans identifiant ('id' manquant) : impossible à parser.")

    attrs = _get_attributes(raw)

    offer_status = attrs.get("offer_status")
    reserved = bool(attrs.get("reserved", False))
    is_active = offer_status == OFFER_STATUS_ACTIVE and not reserved

    return Offer(
        id=str(offer_id),
        source="alin",
        url=ALIN_OFFER_URL_TEMPLATE.format(id=offer_id),
        first_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        last_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        title=attrs.get("residence_title") or "",
        city=attrs.get("district") or "",
        address=attrs.get("address") or "",
        property_type=attrs.get("typology") or "",
        rent=_to_float(attrs.get("rent_amount")) or 0.0,
        surface=_to_float(attrs.get("surface")) or 0.0,
        score=0,  # calculé plus tard par app/filters/scoring.py
        status=OfferStatus.NEW,
        charges=_to_float(attrs.get("rental_charges")),
        rent_with_charges=_to_float(attrs.get("rent_with_charges")),
        rooms=_to_int(attrs.get("rooms")),
        bedrooms=_to_int(attrs.get("bedrooms")),
        availability_date=attrs.get("availability_date"),
        floor=_to_int(attrs.get("floor")),
        has_elevator=attrs.get("has_elevator"),
        parking_type=attrs.get("parking_type"),
        balconies=_to_int(attrs.get("terraces_or_balconies")),
        postal_code=attrs.get("postal_code"),
        department=attrs.get("department"),
        offer_status=offer_status,
        reserved=reserved,
        publication_end_date=attrs.get("publication_end_date"),
        date_publication_start=attrs.get("date_publication_start"),
        external_ref=attrs.get("external_ref"),
        is_active=is_active,
    )


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
