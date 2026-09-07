"""Authentification pour Espacil.

Aucune authentification requise : la recherche de logements est publique
(confirmé par observation directe, `GET /votre-recherche` retourne un 200
sans session préalable). Cette classe existe uniquement pour respecter le
Protocol `SourceClient` (cf. app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings


class EspacilAuthClient:
    name = "espacil"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self) -> str:
        return ""

    async def ensure_valid_token(self) -> str:
        return ""

    async def aclose(self) -> None:
        return None
