"""Stub de parsing des offres pour logement-actionlogement.fr — non
implémenté, cf. app/sources/logement_actionlogement/auth.py.
"""

from __future__ import annotations

from app.database.models import Offer


def parse_offer(raw: dict) -> Offer:
    raise NotImplementedError(
        "Parsing des offres logement-actionlogement.fr non implémenté : "
        "structure d'offre non identifiée, nécessite une session de "
        "découverte réseau légitime avant implémentation, cf. README.md."
    )
