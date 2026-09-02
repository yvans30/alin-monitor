"""Configuration du logging : fichier rotatif + console, avec redaction des secrets."""

from __future__ import annotations

import logging
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_PATTERNS = [
    re.compile(r"(token[\"'=:\s]+)([A-Za-z0-9_\-:]{10,})", re.IGNORECASE),
    re.compile(r"(password[\"'=:\s]+)(\S+)", re.IGNORECASE),
    re.compile(r"(mot_de_passe[\"'=:\s]+)(\S+)", re.IGNORECASE),
    re.compile(r"(bot\d{6,}:)([A-Za-z0-9_\-]+)"),  # format token Telegram
]


class RedactSecretsFilter(logging.Filter):
    """Filtre de défense en profondeur : masque tout ce qui ressemble à un secret.

    Le code ne devrait jamais logger de mot de passe ou de token, mais ce
    filtre agit comme un filet de sécurité si une erreur d'implémentation
    en logge un par accident.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        redacted = message
        for pattern in _SECRET_PATTERNS:
            redacted = pattern.sub(r"\1***REDACTED***", redacted)
        if redacted != message:
            record.msg = redacted
            record.args = ()
        return True


def setup_logging(log_level: str = "INFO", log_dir: str = "data/logs") -> None:
    Path(log_dir).mkdir(parents=True, exist_ok=True)
    log_file = Path(log_dir) / "alin-monitor.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    redact_filter = RedactSecretsFilter()
    file_handler.addFilter(redact_filter)
    console_handler.addFilter(redact_filter)

    root = logging.getLogger()
    root.setLevel(log_level.upper())
    root.addHandler(file_handler)
    root.addHandler(console_handler)
