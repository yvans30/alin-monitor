"""Modèles de données pour la persistance des offres."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class OfferStatus(str, Enum):
    NEW = "NEW"
    NOTIFIED = "NOTIFIED"
    IGNORED = "IGNORED"
    OPENED = "OPENED"
    APPLIED = "APPLIED"  # candidature effectuée manuellement par l'utilisateur, hors outil


@dataclass
class Offer:
    """Offre de logement, toutes sources confondues.

    `source` + `id` forment la clé composite en base (cf. app/database/db.py) :
    deux sources différentes peuvent réutiliser le même `id` sans collision.
    """

    id: str
    source: str  # ex: "alin", "logement_actionlogement" — cf. app/sources/*/
    url: str
    first_seen_at: str
    last_seen_at: str
    title: str
    city: str  # limitation connue: mappé depuis district, cf. app/sources/alin/parser.py
    address: str
    property_type: str
    rent: float  # hors charges
    surface: float
    score: int
    status: OfferStatus
    charges: float | None = None
    rent_with_charges: float | None = None
    rooms: int | None = None
    bedrooms: int | None = None
    availability_date: str | None = None
    floor: int | None = None
    has_elevator: bool | None = None
    parking_type: str | None = None
    balconies: int | None = None
    postal_code: str | None = None
    department: str | None = None
    offer_status: str | None = None
    reserved: bool | None = None
    publication_end_date: str | None = None
    date_publication_start: str | None = None
    external_ref: str | None = None
    is_active: bool = True  # offer_status actif ET non reserved
    # Absorbe tout champ propre à une source future sans forcer le schéma commun.
    raw_attributes: dict | None = None
