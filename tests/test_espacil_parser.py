"""Tests pour app/sources/espacil/parser.py.

Fixture = champs extraits d'une résidence réelle (page liste + page détail
Espacil).
"""

from __future__ import annotations

from app.sources.espacil.parser import parse_offer

RAW_OFFER = {
    "url": "/louer/residence/residence-etudiante-jeune-actif-beccaria-paris",
    "city": "Paris",
    "title": "Résidence Beccaria",
    "description": "T1, T1 bis",
    "price": "488 €",
    "address": "23 rue Beccaria, Paris",
    "apartment_count": 68,
    "typologies": [
        {"label": "T1 pour étudiants", "surface_text": "de 18 à 25 m²", "price_text": "à partir de502 €/ mois"},
        {"label": "T1 bis pour étudiants", "surface_text": "de 27 à 31 m²", "price_text": "à partir de599 €/ mois"},
        {"label": "T1 pour jeunes salariés", "surface_text": "de 18 à 27 m²", "price_text": "à partir de488 €/ mois"},
        {"label": "T1 bis pour jeunes salariés", "surface_text": "de 36 à 42 m²", "price_text": "à partir de709 €/ mois"},
    ],
}


def test_parse_offer_extracts_expected_fields():
    offer = parse_offer(RAW_OFFER)

    assert offer.id == "residence-etudiante-jeune-actif-beccaria-paris"
    assert offer.source == "espacil"
    assert offer.city == "Paris"
    assert offer.title == "Résidence Beccaria"
    assert offer.property_type == "T1, T1 bis"
    assert offer.rent == 488.0
    assert offer.address == "23 rue Beccaria, Paris"
    assert offer.surface == 18.0  # surface min de la typologie à 488€ (jeunes salariés)
    assert offer.raw_attributes["apartment_count"] == 68
    assert offer.is_active is True
    assert offer.url == (
        "https://www.espacil.com/louer/residence/residence-etudiante-jeune-actif-beccaria-paris"
    )


def test_parse_offer_requires_url():
    import pytest

    with pytest.raises(ValueError):
        parse_offer({})


def test_parse_offer_handles_missing_fields_gracefully():
    offer = parse_offer({"url": "/louer/residence/minimal"})
    assert offer.id == "minimal"
    assert offer.city == ""
    assert offer.rent == 0.0
    assert offer.is_active is True
