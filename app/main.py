"""Boucle principale de alin-monitor : veille + notification uniquement,
jamais de candidature automatique (cf. README.md). Harnais multi-source, cf.
app/sources/base.py.
"""

from __future__ import annotations

import asyncio
import functools
import logging
import signal
from datetime import datetime, timezone

import httpx

from app.config import SourceConfig, get_criteria_for_source, get_settings
from app.database.db import Database
from app.database.models import OfferStatus
from app.filters.criteria import matches_hard_filters
from app.filters.scoring import score_offer
from app.logging_setup import setup_logging
from app.notifications.alerting import ErrorNotifier
from app.notifications.telegram import TelegramNotifier
from app.sources.alin.auth import AlinAuthClient, AlinAuthenticationError
from app.sources.alin.parser import parse_offer as parse_alin_offer
from app.sources.alin.scraper import AlinScraperError
from app.sources.alin.scraper import fetch_active_offers as fetch_alin_offers
from app.sources.base import Source
from app.sources.logement_actionlogement.auth import LogementActionLogementAuthClient
from app.sources.logement_actionlogement.parser import (
    parse_offer as parse_logement_actionlogement_offer,
)
from app.sources.logement_actionlogement.scraper import (
    fetch_active_offers as fetch_logement_actionlogement_offers,
)
from app.sources.paris_locannonces.auth import ParisLocannoncesAuthClient
from app.sources.paris_locannonces.parser import parse_offer as parse_paris_locannonces_offer
from app.sources.paris_locannonces.scraper import (
    fetch_active_offers as fetch_paris_locannonces_offers,
)

logger = logging.getLogger(__name__)


def _is_source_enabled(name: str, sources_cfg: dict[str, SourceConfig]) -> bool:
    """Source non listée dans config/criteria.yaml désactivée par défaut,
    sauf `alin` (seule source implémentée) : évite d'activer par erreur un
    stub `NotImplementedError`.
    """
    cfg = sources_cfg.get(name)
    if cfg is not None:
        return cfg.enabled
    return name == "alin"


def build_sources(settings, http_client: httpx.AsyncClient) -> list[Source]:
    """Construit toutes les sources connues, puis filtre celles actives (enabled: true)."""
    alin_source = Source(
        name="alin",
        auth_client=AlinAuthClient(settings, client=http_client),
        fetch_active_offers=functools.partial(fetch_alin_offers, settings=settings),
        parse_offer=parse_alin_offer,
        criteria=get_criteria_for_source(settings.criteria, "alin", settings.sources),
    )
    logement_actionlogement_source = Source(
        name="logement_actionlogement",
        auth_client=LogementActionLogementAuthClient(settings),
        fetch_active_offers=functools.partial(
            fetch_logement_actionlogement_offers, settings=settings
        ),
        parse_offer=parse_logement_actionlogement_offer,
        criteria=get_criteria_for_source(
            settings.criteria, "logement_actionlogement", settings.sources
        ),
    )

    paris_locannonces_source = Source(
        name="paris_locannonces",
        auth_client=ParisLocannoncesAuthClient(settings),
        fetch_active_offers=functools.partial(fetch_paris_locannonces_offers, settings=settings),
        parse_offer=parse_paris_locannonces_offer,
        criteria=get_criteria_for_source(settings.criteria, "paris_locannonces", settings.sources),
    )

    all_sources = [alin_source, logement_actionlogement_source, paris_locannonces_source]
    return [s for s in all_sources if _is_source_enabled(s.name, settings.sources)]


async def run_check_cycle(
    source: Source,
    http_client: httpx.AsyncClient,
    db: Database,
    notifier: TelegramNotifier,
    error_notifier: ErrorNotifier,
) -> None:
    access_token = await source.auth_client.ensure_valid_token()

    try:
        raw_offers = await source.fetch_active_offers(http_client, access_token)
    except (AlinScraperError, NotImplementedError) as exc:
        logger.exception("Erreur lors de la récupération des offres (%s).", source.name)
        error_notifier.notify_critical_error(f"{source.name}_scraper_error", str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - on veut survivre à toute erreur du scraper
        logger.exception("Erreur inattendue pendant la récupération des offres (%s).", source.name)
        error_notifier.notify_critical_error(f"{source.name}_scraper_error", str(exc))
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    for raw in raw_offers:
        try:
            offer = source.parse_offer(raw)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erreur de parsing d'une offre (%s).", source.name)
            error_notifier.notify_critical_error(f"{source.name}_parser_error", str(exc))
            continue

        existing = db.get_offer(source.name, offer.id)
        offer.first_seen_at = existing.first_seen_at if existing else now_iso
        offer.last_seen_at = now_iso

        if not matches_hard_filters(offer, source.criteria):
            offer.status = OfferStatus.IGNORED
            db.upsert_offer(offer)
            continue

        offer.score = score_offer(offer, source.criteria)

        is_new = existing is None

        if is_new and offer.score >= source.criteria.score_threshold:
            offer.status = OfferStatus.NOTIFIED
            db.upsert_offer(offer)
            notifier.notify_new_offer(offer)
            logger.info(
                "Nouvelle offre notifiée (%s): %s (score=%d)", source.name, offer.id, offer.score
            )
        else:
            offer.status = OfferStatus.NEW if is_new else existing.status
            db.upsert_offer(offer)


async def _run_manual_fallback(settings, error_notifier: ErrorNotifier) -> None:
    """Bascule vers le navigateur Playwright pour une intervention manuelle (AL'in uniquement).

    Nécessite un affichage graphique : désactivé par défaut sur VPS/Docker
    (`ENABLE_MANUAL_FALLBACK=false`), où seule une alerte Telegram est
    envoyée. Import Playwright fait ici, pas en tête de module, pour que ce
    package ne soit pas requis quand le fallback est désactivé.
    """
    if not settings.enable_manual_fallback:
        error_notifier.notify_critical_error(
            "auth_fallback_disabled",
            "L'authentification automatique à l'API AL'in a échoué de façon "
            "répétée. Le fallback navigateur est désactivé sur cette machine "
            "(pas d'affichage). Lancez alin-monitor en local sur votre poste "
            "pour investiguer/résoudre une éventuelle vérification "
            "supplémentaire (MFA/CAPTCHA) manuellement.",
        )
        logger.warning(
            "Fallback Playwright désactivé (ENABLE_MANUAL_FALLBACK=false). "
            "Intervention à faire en local."
        )
        return

    from app.sources.alin.browser import (
        ChromiumNotAvailableError,
        close_browser,
        create_browser_context,
        ensure_authenticated_manually,
    )

    logger.warning(
        "Basculement vers le fallback Playwright (authentification httpx "
        "en échec répété). Une intervention manuelle est requise."
    )
    error_notifier.notify_critical_error(
        "auth_fallback_triggered",
        "L'authentification automatique à l'API AL'in a échoué de façon "
        "répétée. Un navigateur va s'ouvrir pour une intervention manuelle. "
        "alin-monitor ne tentera jamais de deviner ou contourner une "
        "éventuelle vérification supplémentaire (MFA/CAPTCHA).",
    )

    try:
        playwright, browser, context = await create_browser_context(settings, error_notifier)
    except ChromiumNotAvailableError:
        logger.error(
            "Fallback Playwright impossible : Chromium indisponible sur cette "
            "machine. Corrigez l'installation (cf. README.md) puis relancez "
            "alin-monitor."
        )
        raise

    page = await context.new_page()
    try:
        await ensure_authenticated_manually(page, settings, error_notifier)
    finally:
        await close_browser(playwright, browser)


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Démarrage de alin-monitor (intervalle=%ds)", settings.check_interval_seconds)

    db = Database(settings.db_path)
    db.init_schema()

    notifier = TelegramNotifier(settings.telegram_bot_token, settings.telegram_chat_id)
    error_notifier = ErrorNotifier(notifier)

    http_client = httpx.AsyncClient()

    active_sources = build_sources(settings, http_client)
    logger.info(
        "Sources actives: %s", ", ".join(s.name for s in active_sources) or "aucune"
    )

    stop_event = asyncio.Event()

    def _request_stop() -> None:
        logger.info("Signal d'arrêt reçu, fermeture en cours...")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except NotImplementedError:
            pass  # non disponible sur toutes les plateformes (ex: Windows)

    try:
        while not stop_event.is_set():
            for source in active_sources:
                try:
                    await run_check_cycle(source, http_client, db, notifier, error_notifier)
                except AlinAuthenticationError as exc:
                    logger.error("Échec d'authentification (%s): %s", source.name, exc)
                    if source.name == "alin":
                        try:
                            await _run_manual_fallback(settings, error_notifier)
                        except Exception:  # noqa: BLE001 - le fallback ne doit jamais tuer le process
                            logger.exception(
                                "Le fallback manuel a également échoué. Attente "
                                "avant nouvelle tentative."
                            )
                    else:
                        error_notifier.notify_critical_error(
                            f"{source.name}_auth_error", str(exc)
                        )
                except NotImplementedError as exc:
                    # Ne devrait pas arriver (stubs enabled=false par défaut) ; filet de sécurité.
                    logger.error(
                        "Source '%s' non implémentée, ignorée pour ce cycle: %s",
                        source.name,
                        exc,
                    )
                    error_notifier.notify_critical_error(
                        f"{source.name}_not_implemented", str(exc)
                    )
                except Exception as exc:  # noqa: BLE001 - on veut survivre à toute erreur inattendue
                    logger.exception(
                        "Erreur inattendue pendant le cycle de vérification (%s).", source.name
                    )
                    error_notifier.notify_critical_error("cycle_error", str(exc))

            try:
                await asyncio.wait_for(
                    stop_event.wait(), timeout=settings.check_interval_seconds
                )
            except asyncio.TimeoutError:
                pass  # cycle suivant
    except KeyboardInterrupt:
        logger.info("Interruption clavier reçue.")
    finally:
        logger.info("Arrêt de alin-monitor à %s", datetime.now(timezone.utc).isoformat())
        db.close()
        for source in active_sources:
            aclose = getattr(source.auth_client, "aclose", None)
            if aclose is not None:
                await aclose()
        await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
