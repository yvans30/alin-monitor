"""Boucle principale de alin-monitor.

Veille + notification uniquement, jamais de candidature automatique (cf.
README.md). Flow nominal : app/alin/auth.py + app/alin/scraper.py ; le
fallback Playwright (app/alin/browser.py) n'intervient qu'après échec répété
de l'authentification httpx.
"""

from __future__ import annotations

import asyncio
import logging
import signal
from datetime import datetime, timezone

import httpx

from app.alin.auth import AlinAuthClient, AlinAuthenticationError
from app.alin.browser import (
    close_browser,
    create_browser_context,
    ensure_authenticated_manually,
)
from app.alin.parser import parse_offer
from app.alin.scraper import AlinScraperError, fetch_active_offers
from app.config import get_settings
from app.database.db import Database
from app.database.models import OfferStatus
from app.filters.criteria import matches_hard_filters
from app.filters.scoring import score_offer
from app.logging_setup import setup_logging
from app.notifications.alerting import ErrorNotifier
from app.notifications.telegram import TelegramNotifier

logger = logging.getLogger(__name__)


async def run_check_cycle(
    http_client: httpx.AsyncClient,
    auth_client: AlinAuthClient,
    db: Database,
    notifier: TelegramNotifier,
    error_notifier: ErrorNotifier,
    settings,
) -> None:
    try:
        access_token = await auth_client.ensure_valid_token()
    except AlinAuthenticationError:
        raise  # remonté à main() pour déclencher le fallback manuel

    try:
        raw_offers = await fetch_active_offers(http_client, access_token, settings)
    except AlinScraperError as exc:
        logger.exception("Erreur lors de la récupération des offres AL'in.")
        error_notifier.notify_critical_error("scraper_error", str(exc))
        return
    except Exception as exc:  # noqa: BLE001 - on veut survivre à toute erreur du scraper
        logger.exception("Erreur inattendue pendant la récupération des offres.")
        error_notifier.notify_critical_error("scraper_error", str(exc))
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    for raw in raw_offers:
        try:
            offer = parse_offer(raw)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Erreur de parsing d'une offre.")
            error_notifier.notify_critical_error("parser_error", str(exc))
            continue

        existing = db.get_offer_by_id(offer.id)
        offer.first_seen_at = existing.first_seen_at if existing else now_iso
        offer.last_seen_at = now_iso

        if not matches_hard_filters(offer, settings.criteria):
            offer.status = OfferStatus.IGNORED
            db.upsert_offer(offer)
            continue

        offer.score = score_offer(offer, settings.criteria)

        is_new = existing is None

        if is_new and offer.score >= settings.score_threshold:
            offer.status = OfferStatus.NOTIFIED
            db.upsert_offer(offer)
            notifier.notify_new_offer(offer)
            logger.info("Nouvelle offre notifiée: %s (score=%d)", offer.id, offer.score)
        else:
            offer.status = OfferStatus.NEW if is_new else existing.status
            db.upsert_offer(offer)


async def _run_manual_fallback(settings, error_notifier: ErrorNotifier) -> None:
    """Bascule vers le navigateur Playwright pour une intervention manuelle."""
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

    playwright, browser, context = await create_browser_context(settings)
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
    auth_client = AlinAuthClient(settings, client=http_client)

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
            try:
                await run_check_cycle(
                    http_client, auth_client, db, notifier, error_notifier, settings
                )
            except AlinAuthenticationError as exc:
                logger.error("Échec d'authentification AL'in: %s", exc)
                try:
                    await _run_manual_fallback(settings, error_notifier)
                except Exception:  # noqa: BLE001 - le fallback ne doit jamais tuer le process
                    logger.exception(
                        "Le fallback manuel a également échoué. Attente avant "
                        "nouvelle tentative."
                    )
            except Exception as exc:  # noqa: BLE001 - on veut survivre à toute erreur inattendue
                logger.exception("Erreur inattendue pendant le cycle de vérification.")
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
        await auth_client.aclose()
        await http_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())
