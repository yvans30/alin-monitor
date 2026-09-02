"""Filtres durs (éliminatoires) : une offre qui échoue est exclue, quel que soit son score."""

from __future__ import annotations

import unicodedata
from datetime import date

from app.config import Criteria
from app.database.models import Offer


def _parse_date_prefix(value: str) -> date | None:
    """Parse YYYY-MM-DD en tolérant un suffixe heure/offset ISO (format renvoyé par l'API)."""
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).lower()


def _matches_quartier(offer: Offer, quartiers: list[str]) -> bool:
    # Best-effort uniquement : l'API n'a pas de champ "quartier" fiable (cf. app/alin/parser.py) ;
    # simple recherche de sous-chaîne dans l'adresse, donc faux négatifs/positifs possibles.
    haystack = _normalize(offer.address or "")
    return any(_normalize(q) in haystack for q in quartiers)


def matches_hard_filters(offer: Offer, criteria: Criteria) -> bool:
    """Retourne False si l'offre doit être écartée d'office."""
    if not offer.is_active:
        return False

    if criteria.villes and offer.city not in criteria.villes:
        return False

    if criteria.quartiers and not _matches_quartier(offer, criteria.quartiers):
        return False

    if criteria.types_logement and offer.property_type not in criteria.types_logement:
        return False

    # Loyer charges comprises si disponible, sinon repli sur le loyer hors charges.
    rent_for_comparison = (
        offer.rent_with_charges if offer.rent_with_charges is not None else offer.rent
    )
    if rent_for_comparison > criteria.loyer_max:
        return False

    if offer.surface < criteria.surface_min:
        return False

    if criteria.nb_chambres_min is not None:
        if offer.rooms is None or offer.rooms < criteria.nb_chambres_min:
            return False

    if criteria.charges_max is not None:
        if offer.charges is not None and offer.charges > criteria.charges_max:
            return False

    if criteria.disponibilite_avant is not None and offer.availability_date is not None:
        limite = _parse_date_prefix(criteria.disponibilite_avant)
        dispo = _parse_date_prefix(offer.availability_date)
        if limite is not None and dispo is not None and dispo > limite:
            return False

    if criteria.etage_max is not None and offer.floor is not None:
        if offer.floor > criteria.etage_max:
            return False

    if criteria.ascenseur_requis and not offer.has_elevator:
        return False

    if criteria.parking_requis and not offer.parking_type:
        return False

    if criteria.balcon_requis and not (offer.balconies and offer.balconies > 0):
        return False

    return True
