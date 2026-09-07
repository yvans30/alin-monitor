"""Client Telegram minimal (httpx) pour envoyer les notifications de nouvelles offres.

Ne jamais logger le token du bot, même en cas d'erreur.
"""

from __future__ import annotations

import logging

import httpx

from app.database.models import Offer

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
_MAX_RETRIES = 2
_TIMEOUT_SECONDS = 10.0

SOURCE_LABELS = {
    "alin": "AL'in",
    "logement_actionlogement": "Action Logement",
    "paris_locannonces": "LOC'annonces (Ville de Paris)",
}


class TelegramNotifier:
    def __init__(self, bot_token: str, chat_id: str) -> None:
        self._bot_token = bot_token
        self._chat_id = chat_id

    def _send_message(self, text: str, url_button: str | None = None) -> None:
        # Pas de parse_mode : le texte contient des champs scrapés/des messages
        # d'erreur arbitraires, jamais garantis valides en Markdown (ex: un
        # underscore isolé fait échouer l'entité et renvoie un 400).
        payload: dict = {
            "chat_id": self._chat_id,
            "text": text,
        }
        if url_button:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": "🔗 Ouvrir l'annonce", "url": url_button}]]
            }

        endpoint = f"{TELEGRAM_API_BASE}/bot{self._bot_token}/sendMessage"

        last_error: Exception | None = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = httpx.post(endpoint, json=payload, timeout=_TIMEOUT_SECONDS)
                response.raise_for_status()
                return
            except httpx.HTTPError as exc:
                last_error = exc
                logger.warning(
                    "Échec envoi Telegram (tentative %d/%d): %s",
                    attempt,
                    _MAX_RETRIES,
                    type(exc).__name__,
                )

        logger.error(
            "Impossible d'envoyer la notification Telegram après %d tentatives: %s",
            _MAX_RETRIES,
            type(last_error).__name__ if last_error else "erreur inconnue",
        )

    def notify_new_offer(self, offer: Offer) -> None:
        address = offer.address or "adresse non précisée"
        availability = offer.availability_date or "non précisée"
        rent_with_charges = (
            offer.rent_with_charges if offer.rent_with_charges is not None else offer.rent
        )
        city = f"{offer.city} ({offer.postal_code})" if offer.postal_code else offer.city
        source_label = SOURCE_LABELS.get(offer.source, offer.source)

        text = (
            "🚨 NOUVELLE OFFRE\n\n"
            f"🌐 Source : {source_label}\n"
            f"📍 {city} — {address}\n"
            f"🏠 {offer.property_type}\n"
            f"📐 {offer.surface} m²\n"
            f"💰 {rent_with_charges} € CC\n"
            f"📅 Disponible : {availability}\n\n"
            f"⭐ Score : {offer.score}/100"
        )
        self._send_message(text, url_button=offer.url)

    def notify_text(self, text: str) -> None:
        """Envoi d'un message texte simple (utilisé par ErrorNotifier)."""
        self._send_message(text)
