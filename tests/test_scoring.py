"""Tests unitaires basiques pour le scoring et les filtres durs."""

from __future__ import annotations

from app.config import Criteria, Poids
from app.database.models import Offer, OfferStatus
from app.filters.criteria import matches_hard_filters
from app.filters.scoring import score_offer


def make_criteria(**overrides) -> Criteria:
    base = dict(
        villes=["Nantes"],
        quartiers=[],
        types_logement=["T2", "T3"],
        loyer_max=750,
        surface_min=40,
        nb_chambres_min=1,
        charges_max=100,
        poids=Poids(
            ville_correspondante=30,
            loyer_sous_seuil=25,
            type_correspondant=20,
            surface_superieure=15,
            disponibilite_interessante=10,
        ),
        score_threshold=60,
    )
    base.update(overrides)
    return Criteria(**base)


def make_offer(**overrides) -> Offer:
    base = dict(
        id="offer-1",
        url="https://al-in.fr/#/fiche-logement/offer-1",
        first_seen_at="2026-08-31T10:00:00Z",
        last_seen_at="2026-08-31T10:00:00Z",
        title="Bel appartement",
        city="Nantes",
        address="1 rue de la Paix",
        property_type="T2",
        rent=700,
        surface=45,
        score=0,
        status=OfferStatus.NEW,
        rooms=2,
        is_active=True,
    )
    base.update(overrides)
    return Offer(**base)


def test_score_offer_full_match_gives_high_score():
    offer = make_offer()
    criteria = make_criteria()
    score = score_offer(offer, criteria)
    assert score == 90  # 30 + 25 + 20 + 15, pas de date de disponibilité


def test_score_offer_no_match_gives_zero():
    offer = make_offer(city="Paris", property_type="T5", rent=2000, surface=10)
    criteria = make_criteria()
    score = score_offer(offer, criteria)
    assert score == 0


def test_score_offer_is_clamped_between_0_and_100():
    offer = make_offer()
    criteria = make_criteria(
        poids=Poids(
            ville_correspondante=100,
            loyer_sous_seuil=100,
            type_correspondant=100,
            surface_superieure=100,
            disponibilite_interessante=100,
        )
    )
    score = score_offer(offer, criteria)
    assert score == 100


def test_matches_hard_filters_rejects_wrong_city():
    offer = make_offer(city="Rennes")
    criteria = make_criteria()
    assert matches_hard_filters(offer, criteria) is False


def test_matches_hard_filters_rejects_rent_above_max():
    offer = make_offer(rent=900)
    criteria = make_criteria()
    assert matches_hard_filters(offer, criteria) is False


def test_matches_hard_filters_rejects_surface_below_min():
    offer = make_offer(surface=20)
    criteria = make_criteria()
    assert matches_hard_filters(offer, criteria) is False


def test_matches_hard_filters_accepts_valid_offer():
    offer = make_offer()
    criteria = make_criteria()
    assert matches_hard_filters(offer, criteria) is True


def test_matches_hard_filters_rejects_inactive_offer():
    offer = make_offer(is_active=False)
    criteria = make_criteria()
    assert matches_hard_filters(offer, criteria) is False


def test_matches_hard_filters_quartier_best_effort_substring_match():
    offer = make_offer(address="12 rue du Centre-Ville")
    criteria = make_criteria(quartiers=["centre-ville"])
    assert matches_hard_filters(offer, criteria) is True

    offer_no_match = make_offer(address="12 rue des Fleurs")
    assert matches_hard_filters(offer_no_match, criteria) is False
