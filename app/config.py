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

    scoring = raw.pop("scoring", {}) or {}
    raw["poids"] = scoring.get("poids", {})
    if "score_threshold" in scoring:
        raw["score_threshold"] = scoring["score_threshold"]

    return Criteria.model_validate(raw)


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


@lru_cache(maxsize=1)
def get_settings(
    env_path: str = ".env",
    criteria_path: str = "config/criteria.yaml",
) -> Settings:
    """Charge la configuration (mise en cache)."""
    load_dotenv(env_path)

    criteria = _load_criteria(Path(criteria_path))

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
    )
