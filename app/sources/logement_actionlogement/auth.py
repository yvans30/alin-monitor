"""Authentification pour logement-actionlogement.fr.

Aucune authentification requise : la surveillance utilise le mode de
navigation publique du site (CGU art. 11.16), qui expose les offres sans
compte — cf. `NoAuthClient` (app/sources/base.py).
"""

from __future__ import annotations

from app.config import Settings
from app.sources.base import NoAuthClient


class LogementActionLogementAuthenticationError(RuntimeError):
    """Réservée à une future bascule vers un mode authentifié, si jamais nécessaire."""


class LogementActionLogementAuthClient(NoAuthClient):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings, name="logement_actionlogement")
