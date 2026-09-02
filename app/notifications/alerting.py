"""Notification Telegram des erreurs critiques, avec throttle anti-spam."""

from __future__ import annotations

import logging
import time

from app.notifications.telegram import TelegramNotifier

logger = logging.getLogger(__name__)

_THROTTLE_SECONDS = 10 * 60  # une seule alerte du même type toutes les 10 minutes


class ErrorNotifier:
    def __init__(self, notifier: TelegramNotifier) -> None:
        self._notifier = notifier
        self._last_sent_at: dict[str, float] = {}

    def notify_critical_error(self, error_type: str, message: str) -> None:
        now = time.monotonic()
        last_sent = self._last_sent_at.get(error_type)

        if last_sent is not None and (now - last_sent) < _THROTTLE_SECONDS:
            logger.debug("Alerte '%s' throttlée (déjà envoyée récemment).", error_type)
            return

        self._last_sent_at[error_type] = now
        logger.error("Erreur critique [%s]: %s", error_type, message)

        text = f"⚠️ *Erreur alin-monitor*\n\nType : {error_type}\n{message}"
        self._notifier.notify_text(text)
