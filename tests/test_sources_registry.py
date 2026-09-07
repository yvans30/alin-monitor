"""Tests du harnais multi-source (app/config.py, app/main.py)."""

from __future__ import annotations

import asyncio

import pytest

from app.config import Criteria, Poids, SourceConfig, get_criteria_for_source
from app.main import _is_source_enabled
from app.sources.logement_actionlogement.auth import LogementActionLogementAuthClient
from app.sources.logement_actionlogement.scraper import (
    LogementActionLogementScraperError,
    fetch_active_offers as fetch_logement_offers,
)


def _base_criteria(**overrides) -> Criteria:
    base = dict(
        villes=["Nantes"],
        quartiers=[],
        types_logement=["T2", "T3"],
        loyer_max=750,
        surface_min=40,
        poids=Poids(),
        score_threshold=60,
    )
    base.update(overrides)
    return Criteria(**base)


def test_get_criteria_for_source_without_override_returns_base():
    base = _base_criteria()
    result = get_criteria_for_source(base, "alin", {})
    assert result == base


def test_get_criteria_for_source_applies_partial_override():
    base = _base_criteria()
    sources_cfg = {
        "logement_actionlogement": SourceConfig(
            enabled=False, overrides={"loyer_max": 500, "surface_min": 20}
        )
    }
    result = get_criteria_for_source(base, "logement_actionlogement", sources_cfg)

    assert result.loyer_max == 500
    assert result.surface_min == 20
    # Le reste des critères communs est préservé.
    assert result.villes == base.villes
    assert result.types_logement == base.types_logement


def test_get_criteria_for_source_ignores_unlisted_source():
    base = _base_criteria()
    result = get_criteria_for_source(base, "unknown_source", {"alin": SourceConfig()})
    assert result == base


def test_is_source_enabled_defaults_alin_to_true_when_unlisted():
    assert _is_source_enabled("alin", {}) is True


def test_is_source_enabled_defaults_other_sources_to_false_when_unlisted():
    assert _is_source_enabled("logement_actionlogement", {}) is False


def test_is_source_enabled_respects_explicit_config():
    sources_cfg = {
        "alin": SourceConfig(enabled=False),
        "logement_actionlogement": SourceConfig(enabled=True),
    }
    assert _is_source_enabled("alin", sources_cfg) is False
    assert _is_source_enabled("logement_actionlogement", sources_cfg) is True


# --- logement_actionlogement utilise le mode public (sans authentification,
# cf. CGU art. 11.16) : pas de token à obtenir. ---


def test_logement_actionlogement_auth_client_needs_no_token():
    client = LogementActionLogementAuthClient(settings=None)
    assert asyncio.run(client.authenticate()) == ""
    assert asyncio.run(client.ensure_valid_token()) == ""


# --- Garde-fou : la recherche géographique est obligatoire côté API, pas de
# mode "tout afficher" — un scraper sans municipalité configurée doit échouer
# explicitement plutôt que d'inventer un comportement par défaut. ---


def test_logement_actionlogement_scraper_requires_search_config():
    settings = type("S", (), {"sources": {}})()
    with pytest.raises(LogementActionLogementScraperError):
        asyncio.run(fetch_logement_offers(client=None, access_token="", settings=settings))
