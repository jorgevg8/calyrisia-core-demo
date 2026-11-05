import logging
import re
from contextvars import ContextVar

from app.core.config import get_settings

request_id_var = ContextVar("request_id", default="SYSTEM-BOOT")


class SecureFormatter(logging.Formatter):
    """Formatter with request IDs and runtime secret redaction."""

    def format(self, record):
        record.request_id = request_id_var.get()
        formatted_message = super().format(record)

        settings = get_settings()
        secrets_to_mask = [
            settings.telegram_bot_token.strip(),
            settings.telegram_webhook_secret.strip(),
            settings.galaxy_jwt_secret.strip(),
            settings.gemini_api_key.strip(),
        ]
        # Never log configured secrets even if a future code path accidentally includes them.
        for secret in secrets_to_mask:
            if secret and len(secret) >= 8:
                formatted_message = formatted_message.replace(secret, "***MASKED_SECRET***")

        sensitive_patterns = [
            r"(bot\d{8,10}:[a-zA-Z0-9_-]{20,})",
            r"(AIza[0-9A-Za-z-_]{20,})",
        ]
        for pattern in sensitive_patterns:
            formatted_message = re.sub(pattern, "***MASKED_SECRET***", formatted_message)

        return formatted_message


def get_logger(name: str):
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = SecureFormatter(
            fmt="[%(asctime)s] [%(levelname)s] [ReqID: %(request_id)s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.propagate = False
    return logger
