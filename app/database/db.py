"""Accès SQLite pour la persistance des offres. Requêtes toujours paramétrées.

Clé composite `(source, id)`, cf. app/database/models.py.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.database.models import Offer, OfferStatus

_SCHEMA = """
CREATE TABLE IF NOT EXISTS offers (
    source TEXT NOT NULL,
    id TEXT NOT NULL,
    url TEXT NOT NULL,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    title TEXT NOT NULL,
    city TEXT NOT NULL,
    address TEXT NOT NULL,
    property_type TEXT NOT NULL,
    rent REAL NOT NULL,
    charges REAL,
    rent_with_charges REAL,
    surface REAL NOT NULL,
    rooms INTEGER,
    bedrooms INTEGER,
    availability_date TEXT,
    floor INTEGER,
    has_elevator INTEGER,
    parking_type TEXT,
    balconies INTEGER,
    postal_code TEXT,
    department TEXT,
    offer_status TEXT,
    reserved INTEGER,
    publication_end_date TEXT,
    date_publication_start TEXT,
    external_ref TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    score INTEGER NOT NULL,
    status TEXT NOT NULL,
    raw_attributes TEXT,
    PRIMARY KEY (source, id)
);
"""

_COLUMNS = [
    "source",
    "id",
    "url",
    "first_seen_at",
    "last_seen_at",
    "title",
    "city",
    "address",
    "property_type",
    "rent",
    "charges",
    "rent_with_charges",
    "surface",
    "rooms",
    "bedrooms",
    "availability_date",
    "floor",
    "has_elevator",
    "parking_type",
    "balconies",
    "postal_code",
    "department",
    "offer_status",
    "reserved",
    "publication_end_date",
    "date_publication_start",
    "external_ref",
    "is_active",
    "score",
    "status",
    "raw_attributes",
]

_UPDATE_COLUMNS = [c for c in _COLUMNS if c not in ("source", "id", "first_seen_at")]


class Database:
    def __init__(self, db_path: str | Path) -> None:
        self._path = Path(db_path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self._path)
        self._conn.row_factory = sqlite3.Row

    def init_schema(self) -> None:
        with self._conn:
            self._conn.execute(_SCHEMA)

    def upsert_offer(self, offer: Offer) -> None:
        placeholders = ", ".join("?" for _ in _COLUMNS)
        set_clause = ", ".join(f"{c} = excluded.{c}" for c in _UPDATE_COLUMNS)
        values = tuple(self._to_row_value(offer, c) for c in _COLUMNS)

        with self._conn:
            self._conn.execute(
                f"""
                INSERT INTO offers ({", ".join(_COLUMNS)})
                VALUES ({placeholders})
                ON CONFLICT(source, id) DO UPDATE SET {set_clause}
                """,
                values,
            )

    def get_offer(self, source: str, offer_id: str) -> Offer | None:
        row = self._conn.execute(
            "SELECT * FROM offers WHERE source = ? AND id = ?", (source, offer_id)
        ).fetchone()
        return self._row_to_offer(row) if row else None

    def mark_status(self, source: str, offer_id: str, status: OfferStatus) -> None:
        with self._conn:
            self._conn.execute(
                "UPDATE offers SET status = ? WHERE source = ? AND id = ?",
                (status.value, source, offer_id),
            )

    def list_by_status(self, status: OfferStatus) -> list[Offer]:
        rows = self._conn.execute(
            "SELECT * FROM offers WHERE status = ?", (status.value,)
        ).fetchall()
        return [self._row_to_offer(row) for row in rows]

    def close(self) -> None:
        self._conn.close()

    @staticmethod
    def _to_row_value(offer: Offer, column: str):
        if column == "status":
            return offer.status.value
        if column == "raw_attributes":
            return json.dumps(offer.raw_attributes) if offer.raw_attributes is not None else None
        value = getattr(offer, column)
        if isinstance(value, bool):
            return int(value)
        return value

    @staticmethod
    def _row_to_offer(row: sqlite3.Row) -> Offer:
        raw_attributes = row["raw_attributes"]
        return Offer(
            id=row["id"],
            source=row["source"],
            url=row["url"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            title=row["title"],
            city=row["city"],
            address=row["address"],
            property_type=row["property_type"],
            rent=row["rent"],
            charges=row["charges"],
            rent_with_charges=row["rent_with_charges"],
            surface=row["surface"],
            rooms=row["rooms"],
            bedrooms=row["bedrooms"],
            availability_date=row["availability_date"],
            floor=row["floor"],
            has_elevator=bool(row["has_elevator"]) if row["has_elevator"] is not None else None,
            parking_type=row["parking_type"],
            balconies=row["balconies"],
            postal_code=row["postal_code"],
            department=row["department"],
            offer_status=row["offer_status"],
            reserved=bool(row["reserved"]) if row["reserved"] is not None else None,
            publication_end_date=row["publication_end_date"],
            date_publication_start=row["date_publication_start"],
            external_ref=row["external_ref"],
            is_active=bool(row["is_active"]),
            score=row["score"],
            status=OfferStatus(row["status"]),
            raw_attributes=json.loads(raw_attributes) if raw_attributes else None,
        )
