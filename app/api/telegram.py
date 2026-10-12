from __future__ import annotations

import json
import hmac
import os
import urllib.error
import urllib.request
import uuid

from fastapi import APIRouter, Request, BackgroundTasks, Header, HTTPException
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.core.logger import get_logger, request_id_var
from app.db import get_connection
from app.schemas import IncomingMessage
from app.services.autopilot_service import GalaxyAutopilotService
from app.services.tenant_guard import TenantGuard, TenantIsolationError

logger = get_logger(__name__)
router = APIRouter()


def _settings():
    return get_settings()


def send_to_telegram(chat_id: int, text: str):
    token = _settings().telegram_bot_token.strip()
    if not token:
        logger.info("Telegram reply suppressed because TELEGRAM_BOT_TOKEN is not configured.")
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            logger.info("Telegram response dispatched successfully (chat_id=%s, status=%s).", chat_id, response.status)
    except urllib.error.URLError as exc:
        logger.error("Telegram delivery failed: %s", exc)


async def process_message(update: dict, req_id: str):
    request_id_var.set(req_id)
    settings = _settings()
    business_id = settings.telegram_business_id.strip()

    if not business_id:
        logger.error("TELEGRAM_BUSINESS_ID is not configured.")
        return

    if "message" not in update or "text" not in update["message"]:
        logger.warning("Telegram update discarded because it has no text message.")
        return

    chat_id = update["message"]["chat"]["id"]
    text = update["message"]["text"]
    logger.info("Processing Telegram message for configured business. chat_id=%s", chat_id)

    try:
        async with get_connection() as conn:
            tenant = TenantGuard(conn)
            tenant.require_business(business_id)

            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM customers
                    WHERE business_id = %s
                      AND source = 'telegram'
                      AND phone = %s
                    LIMIT 1
                    """,
                    (business_id, str(chat_id)),
                )
                row = cur.fetchone()
                if row:
                    cust_id = row[0]
                else:
                    cust_id = uuid.uuid4()
                    cur.execute(
                        """
                        INSERT INTO customers (id, business_id, full_name, source, phone, channel)
                        VALUES (%s, %s, 'Usuario Telegram', 'telegram', %s, 'telegram')
                        """,
                        (cust_id, business_id, str(chat_id)),
                    )

                cur.execute(
                    """
                    SELECT id
                    FROM conversations
                    WHERE business_id = %s
                      AND customer_id = %s
                      AND channel = 'telegram'
                      AND status = 'active'
                    LIMIT 1
                    """,
                    (business_id, cust_id),
                )
                conv_row = cur.fetchone()
                if conv_row:
                    conv_id = conv_row[0]
                else:
                    conv_id = uuid.uuid4()
                    cur.execute(
                        """
                        INSERT INTO conversations (id, business_id, customer_id, channel, status, metadata)
                        VALUES (%s, %s, %s, 'telegram', 'active', %s::jsonb)
                        """,
                        (conv_id, business_id, cust_id, Jsonb({"channel": "telegram"})),
                    )
            conn.commit()

        payload = IncomingMessage(
            business_id=business_id,
            customer_id=cust_id,
            conversation_id=conv_id,
            channel="telegram",
            message=text,
            metadata={"channel": "telegram", "external_chat_id": str(chat_id)},
        )

        async with get_connection() as conn:
            result = GalaxyAutopilotService(conn).respond(payload)

        send_to_telegram(chat_id, result.get("response", "Sin respuesta."))
        logger.info("Telegram message completed successfully for business_id=%s", business_id)

    except TenantIsolationError as exc:
        logger.error("Configured Telegram business is invalid: %s", exc)
        send_to_telegram(chat_id, "El canal Telegram no está correctamente configurado.")
    except Exception as exc:
        logger.exception("Critical Telegram processing failure: %s", exc)
        send_to_telegram(chat_id, "Lo siento, estamos experimentando problemas técnicos.")


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    request_id_var.set(req_id)

    expected_secret = _settings().telegram_webhook_secret.strip()
    if not expected_secret:
        raise HTTPException(status_code=503, detail="Telegram webhook is not configured.")

    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, expected_secret
    ):
        logger.warning("Rejected Telegram webhook with invalid provider secret.")
        raise HTTPException(status_code=401, detail="Unauthorized webhook")

    update = await request.json()
    background_tasks.add_task(process_message, update, req_id)
    return {"status": "ok", "request_id": req_id}
