"""Tests pour app/sources/paris_locannonces/parser.py.

Fixture = champs extraits d'une offre réelle de la page LOC'annonces.
"""

from __future__ import annotations

from app.sources.paris_locannonces.parser import parse_offer

RAW_OFFER = {
    "id": "18598",
    "date_limite_title": "Date limite de candidature jusqu'au 14/09/2026",
    "loyer_text": "991 € CCC",
    "loc_text": "PARIS 14e",
    "surface_text": "59\xa0m²",
    "pieces_text": "2 pièces",
}


def test_parse_offer_extracts_expected_fields():
    offer = parse_offer(RAW_OFFER)

    assert offer.id == "18598"
    assert offer.source == "paris_locannonces"
    assert offer.city == "PARIS 14e"
    assert offer.property_type == "2 pièces"
    assert offer.surface == 59.0
    assert offer.rent == 991.0
    assert offer.rent_with_charges == 991.0
    assert offer.rooms == 2
    assert offer.publication_end_date == "2026-09-14"
    assert offer.is_active is True
    assert offer.url == "https://teleservices.paris.fr/locannonces/logement/18598"


def test_parse_offer_requires_id():
    import pytest

    with pytest.raises(ValueError):
        parse_offer({})


def test_parse_offer_handles_missing_fields_gracefully():
    offer = parse_offer({"id": "minimal-id"})
    assert offer.id == "minimal-id"
    assert offer.city == ""
    assert offer.rent == 0.0
    assert offer.surface == 0.0
    assert offer.publication_end_date is None
    assert offer.is_active is True
