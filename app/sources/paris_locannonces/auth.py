"""Authentification pour LOC'annonces (Ville de Paris).

Aucune authentification requise : la liste des offres (onglet "Accueil") est
publique, confirmé par observation directe (la page se rend en 200 même après
l'échec de la tentative de connexion silencieuse OAuth). Cette classe existe
uniquement pour respecter le Protocol `SourceClient` (cf. app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings


class ParisLocannoncesAuthClient:
    name = "paris_locannonces"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self) -> str:
        return ""

    async def ensure_valid_token(self) -> str:
        return ""

    async def aclose(self) -> None:
        return None
