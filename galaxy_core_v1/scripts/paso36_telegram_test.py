import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.core.config import get_settings
from app.db import get_connection, open_pool, close_pool

BASE_URL = "http://127.0.0.1:8000/api/v1/webhook/telegram"


def simulate_telegram_message(text: str):
    settings = get_settings()
    secret = settings.telegram_webhook_secret.strip()
    if not secret:
        print("❌ TELEGRAM_WEBHOOK_SECRET no está configurado.")
        sys.exit(1)
    payload = {
        "update_id": int(time.time()),
        "message": {
            "message_id": 1,
            "chat": {"id": 987654321, "type": "private"},
            "text": text,
        },
    }
    req = urllib.request.Request(BASE_URL, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("x-telegram-bot-api-secret-token", secret)
    try:
        with urllib.request.urlopen(req, data=json.dumps(payload).encode()) as response:
            return response.status
    except urllib.error.HTTPError as exc:
        print(f"Error HTTP {exc.code}: {exc.read().decode()}")
        return exc.code


def verify_customer():
    settings = get_settings()
    if not settings.telegram_business_id:
        return None
    open_pool()
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, conversation_id
                    FROM customers c
                    LEFT JOIN conversations co
                      ON co.customer_id = c.id
                     AND co.business_id = c.business_id
                     AND co.channel = 'telegram'
                    WHERE c.business_id = %s
                      AND c.source = 'telegram'
                      AND c.phone = %s
                    ORDER BY c.created_at DESC NULLS LAST
                    LIMIT 1
                    """,
                    (settings.telegram_business_id, "987654321"),
                )
                return cur.fetchone()
    finally:
        close_pool()


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 36 — TELEGRAM CONFIGURABLE TEST")
    print("=" * 72)
    settings = get_settings()
    print(f"[INFO] Business Telegram configurado: {settings.telegram_business_id or 'NO CONFIGURADO'}")
    status = simulate_telegram_message("Hola, ¿cómo hago un pedido?")
    if status != 200:
        sys.exit(1)
    print("✅ Webhook autenticado y aceptado (HTTP 200).")
    print("[INFO] Esperando procesamiento en background...")
    time.sleep(4)
    row = verify_customer()
    if not row:
        print("❌ No se encontró el cliente Telegram persistido en el tenant configurado.")
        sys.exit(1)
    print(f"✅ Cliente Telegram persistido: customer_id={row[0]}")
    print(f"✅ Conversación Telegram persistida: conversation_id={row[1]}")
    print("[INFO] Si TELEGRAM_BOT_TOKEN está configurado, revisa que también haya respuesta saliente.")
    print("=" * 72)
    print("PASO 36 — TELEGRAM TEST: PASSED")
    print("=" * 72)
