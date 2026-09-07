"""Authentification pour Espacil.

Aucune authentification requise : la recherche de logements est publique
(confirmé par observation directe, `GET /votre-recherche` retourne un 200
sans session préalable) — cf. `NoAuthClient` (app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings
from app.sources.base import NoAuthClient


class EspacilAuthClient(NoAuthClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, name="espacil")
