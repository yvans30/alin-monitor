"""Authentification pour LOC'annonces (Ville de Paris).

Aucune authentification requise : la liste des offres (onglet "Accueil") est
publique, confirmé par observation directe (la page se rend en 200 même après
l'échec de la tentative de connexion silencieuse OAuth) — cf. `NoAuthClient`
(app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings
from app.sources.base import NoAuthClient


class ParisLocannoncesAuthClient(NoAuthClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, name="paris_locannonces")
