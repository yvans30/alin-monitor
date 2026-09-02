"""Calcul du score d'intérêt d'une offre (0-100) selon les poids configurés."""

from __future__ import annotations

from datetime import date, timedelta

from app.config import Criteria
from app.database.models import Offer

# Une disponibilité dans les N prochains jours est considérée "intéressante".
DISPONIBILITE_INTERESSANTE_JOURS = 30


def _parse_date_prefix(value: str) -> date | None:
    """Cf. app/filters/criteria.py : tolère un suffixe heure/offset ISO."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def score_offer(offer: Offer, criteria: Criteria) -> int:
    """Additionne les points de chaque critère satisfait, puis borne 0-100."""
    poids = criteria.poids
    score = 0

    if offer.city in criteria.villes:
        score += poids.ville_correspondante

    rent_for_comparison = (
        offer.rent_with_charges if offer.rent_with_charges is not None else offer.rent
    )
    if rent_for_comparison <= criteria.loyer_max:
        score += poids.loyer_sous_seuil

    if offer.property_type in criteria.types_logement:
        score += poids.type_correspondant

    if offer.surface > criteria.surface_min:
        score += poids.surface_superieure

    if offer.availability_date is not None:
        dispo = _parse_date_prefix(offer.availability_date)
        if dispo is not None and dispo <= date.today() + timedelta(
            days=DISPONIBILITE_INTERESSANTE_JOURS
        ):
            score += poids.disponibilite_interessante

    return max(0, min(100, score))
