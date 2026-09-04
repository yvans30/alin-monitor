"""Stub d'authentification pour logement-actionlogement.fr.

**Non implémenté volontairement** : contrairement à AL'in (cf.
app/sources/alin/auth.py), les endpoints réels n'ont jamais été observés en
trafic réseau légitime — les inventer est interdit par ce projet (cf.
app/sources/base.py). Avant d'implémenter : vérifier les CGU, observer le
flow réel via l'onglet Network de l'utilisateur sur son propre compte, puis
documenter les endpoints ici sur le modèle d'app/sources/alin/auth.py.
"""

from __future__ import annotations

from app.config import Settings


class LogementActionLogementAuthenticationError(RuntimeError):
    """Réservé à la future implémentation réelle, sur le modèle d'AlinAuthenticationError."""


class LogementActionLogementAuthClient:
    """Squelette non fonctionnel : tout appel lève NotImplementedError."""

    name = "logement_actionlogement"

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def authenticate(self) -> str:
        raise NotImplementedError(
            "Authentification logement-actionlogement.fr non implémentée : "
            "endpoints non identifiés, nécessite une session de découverte "
            "réseau légitime avant implémentation, cf. README.md."
        )

    async def ensure_valid_token(self) -> str:
        raise NotImplementedError(
            "Authentification logement-actionlogement.fr non implémentée : "
            "endpoints non identifiés, nécessite une session de découverte "
            "réseau légitime avant implémentation, cf. README.md."
        )

    async def aclose(self) -> None:
        return None
