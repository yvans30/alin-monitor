"""Contrat commun à toutes les sources de logements (cf. README.md, section
"Limites et éthique") : jamais de contournement CAPTCHA/MFA, jamais de
candidature automatique, jamais d'endpoint/structure inventé sans observation
réseau légitime — une source non confirmée reste un stub `NotImplementedError`.

`parse_offer(raw) -> Offer` n'est volontairement pas dans ce Protocol : elle
reste une fonction libre par module source (`app/sources/<source>/parser.py`).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol

from app.config import Criteria
from app.database.models import Offer


class SourceClient(Protocol):
    """Interface minimale qu'un client d'authentification de source doit respecter."""

    name: str

    async def authenticate(self) -> str: ...

    async def fetch_active_offers(self, access_token: str) -> list[dict[str, Any]]: ...


@dataclass
class Source:
    """Regroupe ce dont `run_check_cycle` a besoin pour traiter une source.

    `fetch_active_offers`/`parse_offer` sont des fonctions libres (pas des
    méthodes), pour rester cohérent avec `app/sources/alin/`.
    """

    name: str
    auth_client: SourceClient
    fetch_active_offers: Callable[..., Awaitable[list[dict[str, Any]]]]
    parse_offer: Callable[[dict[str, Any]], Offer]
    criteria: Criteria
