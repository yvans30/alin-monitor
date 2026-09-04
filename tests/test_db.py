"""Tests pour app/database/db.py, en particulier la clé composite (source, id)."""

from __future__ import annotations

from app.database.db import Database
from app.database.models import Offer, OfferStatus


def make_offer(**overrides) -> Offer:
    base = dict(
        id="shared-external-id",
        source="alin",
        url="https://al-in.fr/#/fiche-logement/shared-external-id",
        first_seen_at="2026-09-01T10:00:00Z",
        last_seen_at="2026-09-01T10:00:00Z",
        title="Offre",
        city="Nantes",
        address="1 rue de la Paix",
        property_type="T2",
        rent=700,
        surface=45,
        score=0,
        status=OfferStatus.NEW,
    )
    base.update(overrides)
    return Offer(**base)


def _make_db(tmp_path) -> Database:
    db = Database(tmp_path / "test.db")
    db.init_schema()
    return db


def test_upsert_and_get_offer_roundtrip(tmp_path):
    db = _make_db(tmp_path)
    offer = make_offer(title="Bel appartement")
    db.upsert_offer(offer)

    fetched = db.get_offer("alin", "shared-external-id")
    assert fetched is not None
    assert fetched.title == "Bel appartement"
    assert fetched.source == "alin"
    db.close()


def test_composite_key_does_not_collide_across_sources(tmp_path):
    """Deux offres de sources différentes avec le même id externe ne s'écrasent pas."""
    db = _make_db(tmp_path)

    alin_offer = make_offer(id="123", source="alin", title="Offre AL'in")
    other_offer = make_offer(id="123", source="logement_actionlogement", title="Offre Action Logement")

    db.upsert_offer(alin_offer)
    db.upsert_offer(other_offer)

    fetched_alin = db.get_offer("alin", "123")
    fetched_other = db.get_offer("logement_actionlogement", "123")

    assert fetched_alin is not None
    assert fetched_other is not None
    assert fetched_alin.title == "Offre AL'in"
    assert fetched_other.title == "Offre Action Logement"
    db.close()


def test_get_offer_returns_none_when_not_found(tmp_path):
    db = _make_db(tmp_path)
    assert db.get_offer("alin", "does-not-exist") is None
    db.close()


def test_upsert_offer_updates_existing_row_without_duplicating(tmp_path):
    db = _make_db(tmp_path)
    offer = make_offer(score=10)
    db.upsert_offer(offer)

    updated = make_offer(score=90, status=OfferStatus.NOTIFIED)
    db.upsert_offer(updated)

    fetched = db.get_offer("alin", "shared-external-id")
    assert fetched.score == 90
    assert fetched.status == OfferStatus.NOTIFIED
    db.close()


def test_raw_attributes_roundtrip_as_json(tmp_path):
    db = _make_db(tmp_path)
    offer = make_offer(raw_attributes={"custom_field": "value", "nested": {"a": 1}})
    db.upsert_offer(offer)

    fetched = db.get_offer("alin", "shared-external-id")
    assert fetched.raw_attributes == {"custom_field": "value", "nested": {"a": 1}}
    db.close()
