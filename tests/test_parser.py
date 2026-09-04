"""Tests pour app/sources/alin/parser.py.

Fixture = copie anonymisée d'une réponse réelle de l'endpoint détail AL'in
(champ "responsible" redacté).
"""

from __future__ import annotations

from app.sources.alin.parser import parse_offer

RAW_OFFER_DETAIL = {
    "id": "6a7db5d494ec7c5464b03639",
    "type": "housing_offers",
    "attributes": {
        "responsible": {"id": "REDACTED", "first_name": None, "last_name": None},
        "created_at": "2026-08-13T14:17:24.310+02:00",
        "address": "53 Avenue de l'industrie",
        "availability_date": "2026-11-15T01:00:00.000+01:00",
        "date_publication_start": "2026-08-28T00:00:00.000+02:00",
        "publication_end_date": "2026-09-03T00:00:00.000+02:00",
        "designation_date_end": "2026-12-09T23:00:00.000+01:00",
        "department": "94",
        "details": "Dans une résidence neuve, à Ivry-sur-Seine...",
        "district": "Ivry-sur-Seine",
        "elevators": 0,
        "expiry_days": 7,
        "external_ref": "DULIV18530022",
        "floor": 5,
        "floors": None,
        "total_floors": None,
        "has_elevator": True,
        "has_garden": None,
        "gardens": 0,
        "insee_code": "94041",
        "kind": "APT",
        "lessor_status": "PUBLIE",
        "main_picture": {
            "thumb240": "/sassets/example",
            "full_size_absolute": "https://api.al-in.fr/sassets/example",
        },
        "offer_status": "LOGEMENT PUBLIE",
        "parking_charges": 0.0,
        "parking_type": "PCO",
        "pictures": [],
        "pictures_nb": 3,
        "postal_code": "94200",
        "rent_amount": 860.86,
        "rent_with_charges": 985.0,
        "rental_charges": 124.14,
        "total_charges": 124.14,
        "reserved": False,
        "residence_title": "IVRY SUR SEINE AVENUE DE L'INDUSTRIE 94205",
        "rooms": None,
        "bedrooms": None,
        "surface": 32,
        "terraces_or_balconies": 1,
        "typology": "T1",
        "threshold_type": "LLI",
        "threshold_subtype": "ZAB",
        "applicated_nb": 4,
        "heating_type": "COU",
        "construction_type": "COL",
        "construction_year": "2026-01-01",
        "latitude": None,
        "longitude": None,
    },
}


def test_parse_offer_extracts_expected_fields():
    offer = parse_offer(RAW_OFFER_DETAIL)

    assert offer.id == "6a7db5d494ec7c5464b03639"
    assert offer.source == "alin"
    assert offer.city == "Ivry-sur-Seine"
    assert offer.property_type == "T1"
    assert offer.surface == 32
    assert offer.rent_with_charges == 985.0
    assert offer.rent == 860.86
    assert offer.charges == 124.14
    assert offer.is_active is True
    assert offer.reserved is False
    assert offer.external_ref == "DULIV18530022"
    assert "6a7db5d494ec7c5464b03639" in offer.url


def test_parse_offer_marks_placed_offer_as_inactive():
    raw = {
        "id": "some-other-id",
        "attributes": {
            **RAW_OFFER_DETAIL["attributes"],
            "offer_status": "LOGEMENT PLACE",
            "reserved": True,
        },
    }
    offer = parse_offer(raw)
    assert offer.is_active is False


def test_parse_offer_defensive_fallback_on_flat_format():
    flat_raw = {"id": "flat-id", **RAW_OFFER_DETAIL["attributes"]}
    offer = parse_offer(flat_raw)
    assert offer.id == "flat-id"
    assert offer.city == "Ivry-sur-Seine"
    assert offer.is_active is True


def test_parse_offer_handles_missing_fields_gracefully():
    offer = parse_offer({"id": "minimal-id", "attributes": {}})
    assert offer.id == "minimal-id"
    assert offer.city == ""
    assert offer.rent == 0.0
    assert offer.surface == 0.0
    assert offer.is_active is False  # offer_status absent != OFFER_STATUS_ACTIVE
