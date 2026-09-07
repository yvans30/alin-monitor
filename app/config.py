"""Chargement et validation de la configuration (.env + config/criteria.yaml)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

# Volontairement conservateur : ne pas descendre sans relire les CGU du site.
DEFAULT_CHECK_INTERVAL_SECONDS = 180

# --- Endpoints API AL'in --- (découverts par observation réseau légitime, cf. app/alin/auth.py)
ALIN_AUTH_URL = "https://api.be-ys.com/als-back/v1/accounts/authenticate"
# Échange le token Keycloak (ALIN_AUTH_URL) contre le token "maison" AL'in requis par housing_offers.
ALIN_TOKEN_EXCHANGE_URL = "https://api.al-in.fr/api/token_exchange/als_hermes_salarie"
ALIN_API_BASE_URL = "https://api.al-in.fr/api/dmo"
ALIN_OFFER_URL_TEMPLATE = "https://al-in.fr/#/fiche-logement/{id}"

# Valeur publique exposée sur https://al-in.fr/info, pas un secret ; overridable si le site change.
ALIN_GEXRT_API_KEY_DEFAULT = "7d6bfa55-4632-41ed-bddd-597866ebbfb5"

# Marge de sécurité (secondes) avant expiration réelle pour ré-authentifier proactivement.
ALIN_TOKEN_REFRESH_MARGIN_SECONDS = 100

# "LOGEMENT PUBLIE" = active/candidatable ; "LOGEMENT PLACE" = déjà attribuée (reserved=true).
OFFER_STATUS_ACTIVE = "LOGEMENT PUBLIE"
OFFER_STATUS_PLACED = "LOGEMENT PLACE"

# --- Endpoints API logement-actionlogement.fr --- (mode public sans authentification,
# cf. CGU art. 11.16 ; découverts par observation réseau légitime en navigation publique).
LOGEMENT_ACTIONLOGEMENT_OFFERS_OVERVIEW_URL = (
    "https://api.logement-actionlogement.fr/api/v1/demands/public/offers-overview"
)
LOGEMENT_ACTIONLOGEMENT_OFFER_DETAILS_URL = (
    "https://api.logement-actionlogement.fr/api/v1/demands/public/offer-showcase-details"
)
# Confirmée par observation directe (URL relevée dans la barre d'adresse en cliquant
# une offre) : le segment final est le `guid` de l'offre (même valeur que `offerGuid`
# passé à offer-showcase-details).
LOGEMENT_ACTIONLOGEMENT_OFFER_URL_TEMPLATE = (
    "https://logement-actionlogement.fr/search/detail/{guid}"
)

# --- LOC'annonces (Ville de Paris) --- (mode public sans authentification, page
# HTML classique — pas d'API JSON, cf. app/sources/paris_locannonces/scraper.py).
PARIS_LOCANNONCES_BASE_URL = "https://teleservices.paris.fr/locannonces/"
PARIS_LOCANNONCES_OFFER_URL_TEMPLATE = "https://teleservices.paris.fr/locannonces/logement/{id}"

# --- Espacil --- (mode public sans authentification, page HTML classique — pas
# d'API JSON, cf. app/sources/espacil/scraper.py).
ESPACIL_SEARCH_URL = "https://www.espacil.com/votre-recherche"
ESPACIL_OFFER_URL_TEMPLATE = "https://www.espacil.com{path}"


class Poids(BaseModel):
    ville_correspondante: int = 0
    loyer_sous_seuil: int = 0
    type_correspondant: int = 0
    surface_superieure: int = 0
    disponibilite_interessante: int = 0


class Criteria(BaseModel):
    villes: list[str] = Field(default_factory=list)
    quartiers: list[str] = Field(default_factory=list)
    types_logement: list[str] = Field(default_factory=list)
    loyer_max: float
    surface_min: float
    nb_chambres_min: int | None = None
    charges_max: float | None = None
    disponibilite_avant: str | None = None
    etage_max: int | None = None
    ascenseur_requis: bool = False
    parking_requis: bool = False
    balcon_requis: bool = False
    poids: Poids = Field(default_factory=Poids)
    score_threshold: int = 60


def _load_criteria(path: Path) -> Criteria:
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw.pop("sources", None)  # section à part, lue par _load_sources_config
    raw.pop("_profil", None)  # ancres YAML réutilisées dans `sources`, pas un critère
    scoring = raw.pop("scoring", {}) or {}
    raw["poids"] = scoring.get("poids", {})
    if "score_threshold" in scoring:
        raw["score_threshold"] = scoring["score_threshold"]

    return Criteria.model_validate(raw)


def _load_sources_config(path: Path) -> dict[str, "SourceConfig"]:
    """Charge la section optionnelle `sources:` de config/criteria.yaml."""
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    sources_raw = raw.get("sources") or {}
    return {name: SourceConfig.model_validate(cfg or {}) for name, cfg in sources_raw.items()}


class SourceConfig(BaseModel):
    """Activation et overrides de critères pour une source (cf. config/criteria.yaml `sources:`)."""

    enabled: bool = True
    overrides: dict = Field(default_factory=dict)
    # Paramètres de recherche propres à la source (ex: municipalités pour
    # logement_actionlogement) : ne correspond à aucun champ de Criteria, donc
    # transmis tel quel au scraper plutôt que fusionné via `overrides`.
    search: dict = Field(default_factory=dict)


def get_criteria_for_source(
    base: Criteria, source_name: str, sources_cfg: dict[str, SourceConfig]
) -> Criteria:
    """Applique les overrides partiels de la source (si définis) sur les critères communs."""
    source_cfg = sources_cfg.get(source_name)
    if source_cfg is None or not source_cfg.overrides:
        return base
    return base.model_copy(update=source_cfg.overrides)


class Settings(BaseModel):
    telegram_bot_token: str
    telegram_chat_id: str
    alin_email: str
    # SecretStr pour ne jamais apparaître en clair dans un repr()/log accidentel.
    alin_password: SecretStr
    alin_login_url: str
    alin_gexrt_api_key: str = ALIN_GEXRT_API_KEY_DEFAULT
    check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS
    db_path: Path
    storage_state_path: Path
    log_level: str = "INFO"
    score_threshold: int = 60
    criteria: Criteria
    sources: dict[str, SourceConfig] = Field(default_factory=dict)
    # Fallback Playwright manuel : nécessite un affichage graphique, donc
    # désactivé sur VPS/Docker (ENABLE_MANUAL_FALLBACK=false), où seule une
    # alerte Telegram est envoyée en cas d'échec d'authentification répété.
    enable_manual_fallback: bool = True


@lru_cache(maxsize=1)
def get_settings(
    env_path: str = ".env",
    criteria_path: str = "config/criteria.yaml",
) -> Settings:
    """Charge la configuration (mise en cache)."""
    load_dotenv(env_path)

    criteria = _load_criteria(Path(criteria_path))
    sources_raw = _load_sources_config(Path(criteria_path))

    return Settings(
        telegram_bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
        telegram_chat_id=os.environ["TELEGRAM_CHAT_ID"],
        alin_email=os.environ["ALIN_EMAIL"],
        alin_password=SecretStr(os.environ["ALIN_PASSWORD"]),
        alin_login_url=os.environ["ALIN_LOGIN_URL"],
        alin_gexrt_api_key=os.environ.get(
            "ALIN_GEXRT_API_KEY", ALIN_GEXRT_API_KEY_DEFAULT
        ),
        check_interval_seconds=int(
            os.environ.get("CHECK_INTERVAL_SECONDS", DEFAULT_CHECK_INTERVAL_SECONDS)
        ),
        db_path=Path(os.environ.get("DB_PATH", "data/alin_monitor.db")),
        storage_state_path=Path(
            os.environ.get("STORAGE_STATE_PATH", "data/storage_state.json")
        ),
        log_level=os.environ.get("LOG_LEVEL", "INFO"),
        score_threshold=int(os.environ.get("SCORE_THRESHOLD", criteria.score_threshold)),
        criteria=criteria,
        sources=sources_raw,
        enable_manual_fallback=os.environ.get("ENABLE_MANUAL_FALLBACK", "true").lower()
        not in ("false", "0", "no"),
    )
