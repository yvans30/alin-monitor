"""Tests pour app/sources/logement_actionlogement/parser.py.

Fixture = copie de la réponse réelle de l'endpoint public `offers-overview`
(URLs de photos signées S3 tronquées, non sensibles).
"""

from __future__ import annotations

from app.sources.logement_actionlogement.parser import parse_offer

RAW_OFFER_SUMMARY = {
    "id": 47457,
    "guid": "3364fede-cc6d-43e2-9c5f-7545f10e36dd",
    "reference": "47457",
    "residency": {
        "id": 4730,
        "guid": "14be5650-5d0d-45aa-8871-69827d8fa97e",
        "reference": "4730",
        "name": "ALFORTVILLE ROME",
        "type": {
            "id": 15,
            "ordering": 1,
            "code": "SOC",
            "label": "Logement familial",
        },
    },
    "lodging": {
        "id": 55721,
        "guid": "60024a0d-84e1-43c8-920b-2888d39a1993",
        "reference": "55721",
        "lodgingType": "IDENTIFIED",
        "lodgingTypology": {
            "id": 8,
            "ordering": 7,
            "code": "T3",
            "label": "T3",
            "commercialLabel": "T3",
        },
        "area": 64.40,
        "municipality": {
            "id": 35043,
            "postcode": "94140",
            "code": "94002",
            "name": "Alfortville",
        },
        "description": "EXCLUSIVITE...",
    },
    "availableAt": "2026-09-07",
    "isLodgingFirstTimeAvailable": False,
    "totalRentAmountBaseBound": 1534.58,
    "startDateOfPublication": "2026-08-25",
}


def test_parse_offer_extracts_expected_fields():
    offer = parse_offer(RAW_OFFER_SUMMARY)

    assert offer.id == "3364fede-cc6d-43e2-9c5f-7545f10e36dd"
    assert offer.source == "logement_actionlogement"
    assert offer.city == "Alfortville"
    assert offer.postal_code == "94140"
    assert offer.property_type == "T3"
    assert offer.surface == 64.40
    assert offer.rent == 1534.58
    assert offer.rent_with_charges == 1534.58
    assert offer.availability_date == "2026-09-07"
    assert offer.external_ref == "47457"
    assert offer.is_active is True
    assert offer.url == "https://logement-actionlogement.fr/search/detail/3364fede-cc6d-43e2-9c5f-7545f10e36dd"


def test_parse_offer_requires_guid():
    import pytest

    with pytest.raises(ValueError):
        parse_offer({"lodging": {}, "residency": {}})


def test_parse_offer_handles_missing_nested_fields_gracefully():
    offer = parse_offer({"guid": "minimal-guid"})
    assert offer.id == "minimal-guid"
    assert offer.city == ""
    assert offer.rent == 0.0
    assert offer.surface == 0.0
    assert offer.is_active is True
