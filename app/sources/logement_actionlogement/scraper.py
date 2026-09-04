"""Stub de récupération des offres pour logement-actionlogement.fr — non
implémenté, cf. app/sources/logement_actionlogement/auth.py.
"""

from __future__ import annotations

import httpx

from app.config import Settings


class LogementActionLogementScraperError(RuntimeError):
    """Réservée à la future implémentation réelle, sur le modèle d'AlinScraperError."""


async def fetch_active_offers(
    client: httpx.AsyncClient,
    access_token: str,
    settings: Settings,
) -> list[dict]:
    raise NotImplementedError(
        "Récupération des offres logement-actionlogement.fr non implémentée : "
        "endpoint liste/recherche non identifié, nécessite une session de "
        "découverte réseau légitime avant implémentation, cf. README.md."
    )
