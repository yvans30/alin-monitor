"""Transformation des offres brutes (dicts JSON de l'endpoint public
`offers-overview`) en objets Offer.

Champs tirés du résumé liste uniquement (pas d'appel détail par offre, pour
éviter N+1 requêtes) : `floor`/`has_elevator`/`parking_type`/`balconies` ne
sont pas exposés à ce niveau et restent None.
"""

from __future__ import annotations

from app.config import LOGEMENT_ACTIONLOGEMENT_OFFER_URL_TEMPLATE
from app.database.models import Offer, OfferStatus


def parse_offer(raw: dict) -> Offer:
    """Convertit un élément brut `data[]` de offers-overview en Offer."""
    offer_guid = raw.get("guid")
    if not offer_guid:
        raise ValueError(
            "Offre logement-actionlogement.fr sans identifiant ('guid' manquant) : "
            "impossible à parser."
        )

    lodging = raw.get("lodging") or {}
    residency = raw.get("residency") or {}
    municipality = lodging.get("municipality") or {}
    typology = lodging.get("lodgingTypology") or {}

    # L'API publique ne renvoie que les offres actuellement publiées/candidatables ;
    # pas d'équivalent du flag `reserved`/`offer_status` d'AL'in à ce niveau de résumé.
    is_active = True

    return Offer(
        id=str(offer_guid),
        source="logement_actionlogement",
        url=LOGEMENT_ACTIONLOGEMENT_OFFER_URL_TEMPLATE.format(guid=offer_guid),
        first_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        last_seen_at="",  # renseigné par l'appelant (main.py) au moment de l'upsert
        title=residency.get("name") or "",
        city=municipality.get("name") or "",
        address="",  # pas d'adresse précise dans le résumé liste
        property_type=typology.get("code") or "",
        # Pas de ventilation loyer/charges dans le résumé liste (contrairement au détail,
        # qui a housingFeeBaseBound + rentChargeAmount séparés) : on duplique la même
        # valeur sur les deux champs, cohérent avec le repli utilisé par les filtres.
        rent=_to_float(raw.get("totalRentAmountBaseBound")) or 0.0,
        surface=_to_float(lodging.get("area")) or 0.0,
        score=0,  # calculé plus tard par app/filters/scoring.py
        status=OfferStatus.NEW,
        charges=None,
        rent_with_charges=_to_float(raw.get("totalRentAmountBaseBound")),
        rooms=None,
        bedrooms=None,
        availability_date=raw.get("availableAt"),
        floor=None,
        has_elevator=None,
        parking_type=None,
        balconies=None,
        postal_code=municipality.get("postcode"),
        department=None,
        offer_status=None,
        reserved=False,
        publication_end_date=None,
        date_publication_start=raw.get("startDateOfPublication"),
        external_ref=raw.get("reference"),
        is_active=is_active,
        raw_attributes=raw,
    )


def _to_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
