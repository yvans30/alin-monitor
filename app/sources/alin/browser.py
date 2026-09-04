"""Fallback Playwright pour une intervention manuelle sur AL'in.

Déclenché par app/main.py après échec répété de l'authentification httpx
nominale (cf. app/sources/alin/auth.py) : ouvre un navigateur visible pour
que l'utilisateur termine la connexion lui-même. Mot de passe jamais loggé.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    async_playwright,
)

from app.config import Settings
from app.notifications.alerting import ErrorNotifier

logger = logging.getLogger(__name__)

# Timeout volontairement généreux : laisser le temps de saisir un code MFA.
_MFA_POLL_INTERVAL_SECONDS = 5
_MFA_POLL_TIMEOUT_SECONDS = 15 * 60


class ChromiumNotAvailableError(RuntimeError):
    """Cause la plus fréquente : `playwright install --with-deps chromium`
    jamais exécuté (VPS nu), ou image Docker de base changée sans
    réinstaller le navigateur (cf. Dockerfile).
    """


def load_storage_state(path: str | Path) -> dict | None:
    p = Path(path)
    if not p.exists():
        return None
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


async def save_storage_state(context: BrowserContext, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    await context.storage_state(path=str(p))
    logger.info("Session sauvegardée dans %s", p)


async def create_browser_context(
    settings: Settings,
    error_notifier: ErrorNotifier | None = None,
) -> tuple[Playwright, Browser, BrowserContext]:
    """Lance Chromium en mode visible pour permettre une intervention manuelle.

    Lève `ChromiumNotAvailableError` (notifie Telegram si `error_notifier`
    est fourni) si Chromium n'est pas installé.
    """
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.launch(headless=False)
    except PlaywrightError as exc:
        await playwright.stop()
        message = (
            "Le navigateur Chromium requis par le fallback Playwright est "
            "indisponible. Corrigez avec `playwright install --with-deps "
            "chromium` (VPS nu), ou reconstruisez l'image Docker (le "
            "Dockerfile installe Chromium en filet de sécurité). Détail : "
            f"{exc}"
        )
        logger.error(message)
        if error_notifier:
            error_notifier.notify_critical_error("chromium_not_available", message)
        raise ChromiumNotAvailableError(message) from exc

    storage_state = load_storage_state(settings.storage_state_path)
    if storage_state:
        logger.info("Session existante chargée depuis %s", settings.storage_state_path)
        context = await browser.new_context(storage_state=storage_state)
    else:
        logger.info("Aucune session existante, nouveau contexte vierge.")
        context = await browser.new_context()

    return playwright, browser, context


async def close_browser(playwright: Playwright, browser: Browser) -> None:
    await browser.close()
    await playwright.stop()
    logger.info("Navigateur fermé proprement.")


async def _is_logged_in(page: Page) -> bool:
    # TODO: sélecteur de session active non encore défini.
    raise NotImplementedError(
        "Sélecteur de détection de connexion non défini : à faire lors d'une "
        "future intervention manuelle avec l'utilisateur."
    )


async def _is_mfa_prompted(page: Page) -> bool:
    # Pas de sélecteur fiable défini : prudemment False plutôt que d'en inventer un au hasard.
    return False


async def _wait_for_manual_authentication(
    page: Page,
    error_notifier: ErrorNotifier | None,
    poll_interval: int = _MFA_POLL_INTERVAL_SECONDS,
    timeout: int = _MFA_POLL_TIMEOUT_SECONDS,
) -> bool:
    """Attend par polling que l'utilisateur termine une MFA manuellement (jamais de code deviné)."""
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(poll_interval)
        elapsed += poll_interval
        try:
            if await _is_logged_in(page):
                logger.info("Authentification manuelle détectée comme réussie.")
                return True
        except NotImplementedError:
            logger.debug(
                "Vérification de session non implémentée pendant l'attente MFA."
            )
    logger.warning(
        "Timeout atteint en attendant la fin de l'authentification manuelle (MFA)."
    )
    if error_notifier:
        error_notifier.notify_critical_error(
            "mfa_timeout",
            "Aucune session active détectée après le délai d'attente suite à "
            "la détection MFA. Une nouvelle intervention manuelle sera "
            "nécessaire.",
        )
    return False


async def ensure_authenticated_manually(
    page: Page, settings: Settings, error_notifier: ErrorNotifier | None = None
) -> None:
    """Fallback manuel : ouvre la page de connexion et attend une intervention humaine."""
    await page.goto(settings.alin_login_url)

    try:
        logged_in = await _is_logged_in(page)
    except NotImplementedError:
        logger.warning(
            "Détection de session non implémentée : intervention manuelle requise."
        )
        if error_notifier:
            error_notifier.notify_critical_error(
                "auth_fallback_not_implemented",
                "Le fallback Playwright d'authentification AL'in nécessite une "
                "intervention manuelle : la détection de session n'est pas "
                "encore implémentée.",
            )
        raise

    if logged_in:
        logger.info("Session AL'in déjà active.")
        return

    logger.info(
        "Session non active. Merci de vous connecter manuellement dans la "
        "fenêtre du navigateur ouverte."
    )

    if await _is_mfa_prompted(page):
        logger.warning(
            "MFA détectée, intervention manuelle requise. Le programme "
            "attend que la connexion soit terminée manuellement dans la "
            "fenêtre du navigateur ouverte."
        )
        if error_notifier:
            error_notifier.notify_critical_error(
                "mfa_detected",
                "Une vérification MFA a été détectée lors de la connexion à "
                "AL'in. Merci de terminer l'authentification manuellement "
                "dans la fenêtre du navigateur ouverte sur le serveur.",
            )

    if await _wait_for_manual_authentication(page, error_notifier):
        return
    raise RuntimeError("Authentification manuelle non terminée avant le timeout.")
