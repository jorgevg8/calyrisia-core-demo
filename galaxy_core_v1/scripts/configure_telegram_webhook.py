"""Register CALYRISIA's Telegram webhook using environment settings.

Required environment: TELEGRAM_BOT_TOKEN, TELEGRAM_WEBHOOK_SECRET, and either
CALYRISIA_BASE_URL or RENDER_EXTERNAL_URL. Run after the service is deployed.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
import urllib.error
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    token = settings.telegram_bot_token.strip()
    secret = settings.telegram_webhook_secret.strip()
    base_url = (
        settings.calyrisia_base_url
        or os.getenv("CALYRISIA_BASE_URL")
        or os.getenv("RAILWAY_PUBLIC_DOMAIN")
        or os.getenv("RENDER_EXTERNAL_URL")
        or ""
    ).strip().rstrip("/")
    if base_url and not base_url.startswith(("https://", "http://")):
        base_url = f"https://{base_url}"
    if not token or not secret:
        print("ERROR: configura TELEGRAM_BOT_TOKEN y TELEGRAM_WEBHOOK_SECRET en el entorno.")
        return 2
    if not base_url.startswith("https://"):
        print("ERROR: configura CALYRISIA_BASE_URL=https://tu-servicio.onrender.com (o RENDER_EXTERNAL_URL).")
        return 2
    payload = {
        "url": f"{base_url}/api/v1/webhook/telegram",
        "secret_token": secret,
        "allowed_updates": ["message", "callback_query", "edited_message"],
        "drop_pending_updates": False,
    }
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/setWebhook",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"ERROR: no se pudo registrar el webhook ({type(exc).__name__}).")
        return 1
    if not result.get("ok"):
        print("ERROR: Telegram rechazó el registro del webhook.")
        print(str(result.get("description") or "")[:300])
        return 1
    print("OK: webhook de Telegram registrado.")
    print(f"URL: {payload['url']}")
    print("Actualizaciones: message, callback_query, edited_message")
    print("No se imprimió ningún secreto.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
