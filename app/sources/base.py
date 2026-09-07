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

from app.config import Criteria, Settings
from app.database.models import Offer


class SourceClient(Protocol):
    """Interface minimale qu'un client d'authentification de source doit respecter.

    Reflète ce que `app/main.py` appelle réellement sur `Source.auth_client` :
    `ensure_valid_token()` (avant chaque cycle) et `aclose()` (à l'arrêt).
    `authenticate()` reste une méthode interne propre à chaque implémentation
    (ex: AlinAuthClient), pas un point d'entrée partagé — volontairement hors
    Protocol. `fetch_active_offers` n'est jamais une méthode d'auth client :
    c'est une fonction libre par source, cf. `Source.fetch_active_offers`.
    """

    name: str

    async def ensure_valid_token(self) -> str: ...

    async def aclose(self) -> None: ...


class NoAuthClient:
    """Client d'authentification no-op, pour une source en mode public
    (confirmé par observation réseau, cf. app/sources/<source>/auth.py) : rien
    à authentifier, pas de token, pas d'état à fermer. Factorise les 3 sources
    sans compte (logement_actionlogement, paris_locannonces, espacil) plutôt
    que de dupliquer les mêmes méthodes vides dans chacune.
    """

    def __init__(self, settings: Settings, *, name: str) -> None:
        self._settings = settings
        self.name = name

    async def authenticate(self) -> str:
        return ""

    async def ensure_valid_token(self) -> str:
        return ""

    async def aclose(self) -> None:
        return None


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
