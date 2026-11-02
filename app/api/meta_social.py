from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import os
import secrets
import time
import html
import re
import unicodedata
import urllib.parse
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel, Field

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

from app.api import auth
from app.db import get_connection
from app.schemas import IncomingMessage, NormalizedOmnichannelPayload
from app.services.autopilot_service import GalaxyAutopilotService
from app.services.business_brain_service import BusinessBrainService
from app.services.omnichannel_gateway_service import OmnichannelGatewayService
from app.services.commercial_limits import AIQuotaExceeded, consume_ai_response

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_META_PLATFORMS = ("instagram", "facebook", "whatsapp")
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v26.0").strip() or "v26.0"

# Credenciales de la App de Meta (configurables por entorno en Render)
META_APP_ID = os.getenv("META_APP_ID", "2456430845105397").strip() or "2456430845105397"
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
# Unified Login configuration shown in the supplied Meta for Developers screenshot.
META_CONFIG_ID = os.getenv("META_CONFIG_ID", "1831235794732615").strip() or "1831235794732615"
# Optional separate Facebook Login for Business configuration for Messenger Pages.
META_FACEBOOK_CONFIG_ID = os.getenv("META_FACEBOOK_CONFIG_ID", "").strip()
META_REDIRECT_URI = os.getenv(
    "META_REDIRECT_URI",
    "https://calyrisia.com/api/auth/meta/callback",
).strip()
META_WEBHOOK_VERIFY_TOKEN = os.getenv(
    "META_WEBHOOK_VERIFY_TOKEN",
    "calyrisia_meta_2026_secret",
).strip()

PAYMENT_METHOD_LABELS = {
    "pago_movil": "Pago Móvil",
    "transferencia": "Transferencia Bancaria",
    "zelle": "Zelle",
    "binance": "Binance Pay",
    "paypal": "PayPal",
}

_PAYMENT_BUTTON_RE = re.compile(
    r"\[BOTON_PAGO:\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:\|\s*ITEMS:\s*(\[[^\]]*\]))?\s*\]",
    re.IGNORECASE | re.DOTALL,
)
_TOTAL_AMOUNT_RE = re.compile(
    r"total(?:\s+a\s+pagar|\s+estimado|\s+del\s+pedido)?[^\d$]{0,20}(?:usd|\$)?\s*([0-9]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

# Temporary in-memory cache of OAuth sessions so the user can pick the exact Page or Instagram account in the popup
_pending_meta_oauth_sessions: dict[str, dict[str, Any]] = {}


class MetaChannelConfigUpdate(BaseModel):
    account_name: str = Field(default="", max_length=160)
    page_or_ig_id: str | None = Field(default=None, max_length=120)
    access_token: str | None = Field(default=None, max_length=600)
    verify_token: str | None = Field(default=None, max_length=160)
    enabled: bool = True


class MetaChannelToggleRequest(BaseModel):
    enabled: bool


class MetaChannelTestRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=1500)
    sender_name: str = Field(default="Cliente Social", max_length=120)
    sender_handle: str = Field(default="@cliente_demo", max_length=120)


class MetaOAuthSelectAccountRequest(BaseModel):
    session_key: str = Field(..., min_length=8, max_length=120)
    platform: str = Field(..., min_length=3, max_length=30)
    page_or_ig_id: str = Field(..., min_length=1, max_length=160)
    account_name: str = Field(..., min_length=1, max_length=160)


async def ensure_meta_social_schema() -> None:
    """Create the multi-tenant table for Instagram Direct, Facebook Messenger and WhatsApp Cloud channels."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.business_meta_channels (
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        platform varchar(30) NOT NULL CHECK (platform IN ('instagram', 'facebook', 'whatsapp')),
                        enabled boolean NOT NULL DEFAULT false,
                        channel_status varchar(30) NOT NULL DEFAULT 'disconnected',
                        account_name varchar(160) NOT NULL DEFAULT '',
                        page_or_ig_id varchar(120) NOT NULL DEFAULT '',
                        parent_page_id varchar(120) NOT NULL DEFAULT '',
                        access_token text NOT NULL DEFAULT '',
                        verify_token varchar(160) NOT NULL DEFAULT '',
                        last_error text,
                        last_event_at timestamptz,
                        connected_at timestamptz,
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (business_id, platform)
                    )
                    """
                )
                cur.execute("ALTER TABLE public.business_meta_channels ADD COLUMN IF NOT EXISTS parent_page_id varchar(120) NOT NULL DEFAULT ''")
                try:
                    cur.execute("SAVEPOINT sp_meta_platform_chk")
                    cur.execute(
                        "ALTER TABLE public.business_meta_channels "
                        "DROP CONSTRAINT IF EXISTS business_meta_channels_platform_check"
                    )
                    cur.execute(
                        "ALTER TABLE public.business_meta_channels "
                        "ADD CONSTRAINT business_meta_channels_platform_check "
                        "CHECK (platform IN ('instagram', 'facebook', 'whatsapp'))"
                    )
                    cur.execute("RELEASE SAVEPOINT sp_meta_platform_chk")
                except Exception:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_meta_platform_chk")
                    except Exception:
                        pass
                cur.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_business_meta_channels_page_id
                    ON public.business_meta_channels (platform, page_or_ig_id)
                    """
                )
            conn.commit()
        except Exception as exc:
            conn.rollback()
            logger.warning("Could not initialize business_meta_channels schema: %s", exc)


def _default_verify_token(business_id: str) -> str:
    clean = str(business_id or "").replace("-", "")[:12]
    return f"calyrisia_meta_{clean}"


def _platform_label(platform: str) -> str:
    if platform == "instagram":
        return "Instagram Direct"
    if platform == "whatsapp":
        return "WhatsApp Cloud"
    return "Facebook Messenger"


def _normalise(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _clean_for_meta(text: str) -> tuple[str, Decimal | None, list[dict[str, Any]]]:
    amount: Decimal | None = None
    items: list[dict[str, Any]] = []
    match = _PAYMENT_BUTTON_RE.search(text or "")
    if match:
        try:
            amount = Decimal(match.group(1)).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            amount = None
        if match.group(2):
            try:
                parsed = json.loads(match.group(2))
                if isinstance(parsed, list):
                    items = [row for row in parsed if isinstance(row, dict)]
            except Exception:
                items = []
    cleaned = _PAYMENT_BUTTON_RE.sub("", text or "")
    cleaned = re.sub(r"\*\*(.+?)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    if len(cleaned) > 1900:
        cleaned = cleaned[:1897].rstrip() + "..."
    return cleaned, amount, items


def _parse_payment_marker(messages: list[str]) -> tuple[Decimal | None, list[dict[str, Any]]]:
    for content in messages:
        match = _PAYMENT_BUTTON_RE.search(content or "")
        if match:
            amount: Decimal | None = None
            items: list[dict[str, Any]] = []
            try:
                amount = Decimal(match.group(1)).quantize(Decimal("0.01"))
            except (InvalidOperation, ValueError):
                amount = None
            if match.group(2):
                try:
                    parsed = json.loads(match.group(2))
                    if isinstance(parsed, list):
                        items = [row for row in parsed if isinstance(row, dict)]
                except Exception:
                    items = []
            if amount is not None and amount > 0:
                return amount, items
        fallback = _TOTAL_AMOUNT_RE.search(content or "")
        if fallback:
            try:
                amount = Decimal(fallback.group(1)).quantize(Decimal("0.01"))
                if amount > 0:
                    return amount, []
            except (InvalidOperation, ValueError):
                continue
    return None, []


def _looks_like_payment_submission(text: str) -> bool:
    normalized = _normalise(text)
    digits = re.findall(r"\d{4,}", normalized)
    keywords = (
        "referencia",
        "ref",
        "comprobante",
        "pago movil",
        "transferencia",
        "zelle",
        "binance",
        "paypal",
        "operacion",
        "capture",
        "pague",
        "ya pague",
        "listo el pago",
    )
    return bool(digits and any(k in normalized for k in keywords)) or len(digits) >= 2


def _get_business_payment_options_sync(conn, business_id: str) -> list[dict[str, str]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT method_code, instructions
            FROM public.business_payment_instructions
            WHERE business_id = %s::uuid
              AND enabled = true
              AND btrim(instructions) <> ''
            ORDER BY CASE method_code
                WHEN 'pago_movil' THEN 1
                WHEN 'transferencia' THEN 2
                WHEN 'zelle' THEN 3
                WHEN 'binance' THEN 4
                WHEN 'paypal' THEN 5
                ELSE 9
            END
            """,
            (business_id,),
        )
        rows = cur.fetchall()
    options: list[dict[str, str]] = []
    for code, instructions in rows:
        code_str = str(code or "")
        clean_instructions = str(instructions or "").strip()
        if code_str in PAYMENT_METHOD_LABELS and clean_instructions:
            options.append(
                {
                    "code": code_str,
                    "label": PAYMENT_METHOD_LABELS[code_str],
                    "instructions": clean_instructions,
                }
            )
    return options


def _get_recent_outbound_sync(
    conn, business_id: str, customer_id: uuid.UUID, conversation_id: uuid.UUID
) -> list[str]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT content FROM public.conversation_messages
            WHERE business_id = %s::uuid AND customer_id = %s AND conversation_id = %s
              AND direction = 'outbound'
            ORDER BY created_at DESC LIMIT 12
            """,
            (business_id, customer_id, conversation_id),
        )
        return [str(r[0] or "") for r in cur.fetchall()]


def _ensure_social_customer_and_conversation(
    conn,
    *,
    business_id: str,
    platform: str,
    sender_id: str,
    sender_name: str,
) -> tuple[uuid.UUID, uuid.UUID, str]:
    clean_sender = str(sender_id or "").strip()[:80] or f"{platform}_user"
    display_name = (
        str(sender_name or "").strip()[:150]
        or f"Cliente {_platform_label(platform)} ({clean_sender[-6:]})"
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, full_name FROM public.customers
            WHERE business_id = %s::uuid AND source = %s AND phone = %s
            LIMIT 1
            """,
            (business_id, platform, clean_sender),
        )
        row = cur.fetchone()
        if row:
            customer_id = row[0]
            if sender_name and str(row[1] or "").startswith("Cliente "):
                cur.execute(
                    "UPDATE public.customers SET full_name = %s, last_interaction_at = now() WHERE id = %s AND business_id = %s::uuid",
                    (display_name, customer_id, business_id),
                )
            else:
                display_name = str(row[1] or display_name)
        else:
            customer_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO public.customers (id, business_id, full_name, source, channel, phone, status)
                VALUES (%s, %s::uuid, %s, %s, %s, %s, 'active')
                """,
                (customer_id, business_id, display_name, platform, platform, clean_sender),
            )

        cur.execute(
            """
            SELECT id FROM public.conversations
            WHERE business_id = %s::uuid AND customer_id = %s AND channel = %s AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
            """,
            (business_id, customer_id, platform),
        )
        conv_row = cur.fetchone()
        if conv_row:
            conversation_id = conv_row[0]
        else:
            conversation_id = uuid.uuid4()
            cur.execute(
                """
                INSERT INTO public.conversations (id, business_id, customer_id, channel, status, metadata)
                VALUES (%s, %s::uuid, %s, %s, 'active', %s::jsonb)
                """,
                (
                    conversation_id,
                    business_id,
                    customer_id,
                    platform,
                    Jsonb({"channel": platform, "sender_id": clean_sender}),
                ),
            )
    conn.commit()
    return customer_id, conversation_id, display_name


def _create_social_payment_sync(
    conn,
    *,
    business_id: str,
    platform: str,
    customer_id: uuid.UUID,
    amount: Decimal,
    items: list[dict[str, Any]],
    payment_details: str,
    payment_method: str,
) -> tuple[str, bool]:
    payment_id = uuid.uuid4()
    created = True
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id FROM public.webchat_payment_requests
            WHERE business_id = %s::uuid AND customer_id = %s AND source = %s
              AND status = 'pending' AND created_at >= now() - interval '30 minutes'
            ORDER BY created_at DESC LIMIT 1 FOR UPDATE
            """,
            (business_id, customer_id, platform),
        )
        prior = cur.fetchone()
        if prior:
            payment_id = prior[0]
            created = False
            cur.execute(
                """
                UPDATE public.webchat_payment_requests
                SET customer_payment_details = %s, payment_method = %s
                WHERE id = %s AND business_id = %s::uuid
                """,
                (payment_details[:4000], payment_method, payment_id, business_id),
            )
        else:
            cur.execute(
                """
                INSERT INTO public.webchat_payment_requests
                (id, business_id, customer_id, amount, currency, payment_method, status, source,
                 approval_note, items, customer_payment_details)
                VALUES (%s, %s::uuid, %s, %s, 'USD', %s, 'pending', %s,
                        %s, %s, %s)
                """,
                (
                    payment_id,
                    business_id,
                    customer_id,
                    amount,
                    payment_method,
                    platform,
                    f"Solicitud recibida por {_platform_label(platform)}; pendiente de aprobación del dueño.",
                    Jsonb(items) if items else None,
                    payment_details[:4000],
                ),
            )
    conn.commit()
    return str(payment_id), created


async def _send_meta_graph_reply(
    *,
    platform: str,
    page_or_ig_id: str,
    access_token: str,
    recipient_id: str,
    message_text: str,
    send_target_id: str | None = None,
) -> tuple[bool, str | None]:
    """Send a reply through the correct Meta asset (Page token for Messenger/Unified Instagram)."""
    token = (access_token or "").strip()
    if not token or not recipient_id or not message_text:
        return False, "Falta token, destinatario o contenido para enviar el mensaje."
    target_node = (send_target_id or page_or_ig_id or "me").strip() or "me"
    if platform == "whatsapp":
        url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{target_node}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {"preview_url": False, "body": message_text[:4000]},
        }
    else:
        # Enviar mediante Graph API de Meta (/me/messages con Page Access Token) y fallback al nodo de la Página
        url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": message_text[:1950]},
        }
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, params={"access_token": token}, json=payload)
            if resp.status_code >= 400 and platform != "whatsapp" and target_node and target_node != "me":
                fallback_url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{target_node}/messages"
                resp = await client.post(fallback_url, params={"access_token": token}, json=payload)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                err_obj = body.get("error") if isinstance(body, dict) else {}
                err = str((err_obj or {}).get("message") or resp.text[:500])
            except Exception:
                err = resp.text[:500]
            logger.warning("Meta Graph send error (%s, target=%s, status=%s): %s", platform, target_node, resp.status_code, err)
            return False, err[:500]
        return True, None
    except Exception as exc:
        logger.warning("Meta Graph HTTP exception (%s): %s", platform, exc)
        return False, str(exc)[:500]


async def process_meta_incoming_message(
    conn,
    *,
    business_id: str,
    platform: str,
    sender_id: str,
    sender_name: str,
    message_text: str,
    is_simulation: bool = False,
) -> dict[str, Any]:
    """Unified handler for Instagram Direct, Facebook Messenger and WhatsApp Cloud messages."""
    text = str(message_text or "").strip()
    if not text:
        return {"replied": False, "reply_text": ""}

    customer_id, conversation_id, display_name = _ensure_social_customer_and_conversation(
        conn,
        business_id=business_id,
        platform=platform,
        sender_id=sender_id,
        sender_name=sender_name,
    )

    outbound = _get_recent_outbound_sync(conn, business_id, customer_id, conversation_id)
    prior_amount, prior_items = _parse_payment_marker(outbound)

    reply_text = ""
    if prior_amount is not None and prior_amount > 0 and _looks_like_payment_submission(text):
        payment_options = _get_business_payment_options_sync(conn, business_id)
        normalized_proof = _normalise(text)
        selected_option = None
        if len(payment_options) == 1:
            selected_option = payment_options[0]
        else:
            for opt in payment_options:
                if opt["code"].replace("_", " ") in normalized_proof or opt["label"].lower() in normalized_proof:
                    selected_option = opt
                    break
            if selected_option is None and payment_options:
                selected_option = payment_options[0]

        method_label = (
            f"{selected_option['label']} ({_platform_label(platform)})"
            if selected_option
            else f"Pago ({_platform_label(platform)})"
        )
        payment_id, newly_created = _create_social_payment_sync(
            conn,
            business_id=business_id,
            platform=platform,
            customer_id=customer_id,
            amount=prior_amount,
            items=prior_items,
            payment_details=text,
            payment_method=method_label,
        )
        if newly_created:
            reply_text = (
                f"✅ Recibimos tus datos de pago por USD {prior_amount:.2f};\n"
                f"• Estado: PENDIENTE de verificación en el panel del negocio;\n"
                f"• Solicitud: #{payment_id[:8].upper()}.\n\n"
                "Apenas el propietario valide la operación en su cuenta, te confirmaremos por esta misma vía."
            )
        else:
            reply_text = (
                f"📌 Tu reporte de pago #{payment_id[:8].upper()} ha sido actualizado y está pendiente de aprobación por el comercio."
            )
    else:
        try:
            consume_ai_response(conn, business_id)
            payload = IncomingMessage(
                business_id=uuid.UUID(str(business_id)),
                customer_id=customer_id,
                conversation_id=conversation_id,
                channel=platform,
                message=text,
                metadata={
                    "channel": platform,
                    "external_sender_id": sender_id,
                    "sender_name": display_name,
                    "simulation": is_simulation,
                },
            )
            result = GalaxyAutopilotService(conn).respond(payload)
            raw_reply = str(result.get("response") or "¿En qué puedo ayudarte hoy?")
            clean_reply, pay_amount, _pay_items = _clean_for_meta(raw_reply)
            if pay_amount is not None and pay_amount > 0:
                payment_options = _get_business_payment_options_sync(conn, business_id)
                if payment_options:
                    details = "\n\n".join(
                        f"▸ {opt['label']}:\n{opt['instructions']}" for opt in payment_options
                    )
                    clean_reply = (
                        f"{clean_reply}\n\n"
                        f"💳 MÉTODOS DE PAGO DISPONIBLES (USD {pay_amount:.2f}):\n"
                        f"{details}\n\n"
                        "Cuando realices el pago, envíame por este mismo chat el método utilizado y el número de referencia para registrarlo en el sistema."
                    ).strip()
            reply_text = clean_reply
        except AIQuotaExceeded as exc:
            reply_text = (
                f"Hemos alcanzado el límite mensual de {exc.limit} respuestas automáticas del plan actual. "
                "Un asesor te atenderá en breve."
            )
        except Exception as exc:
            logger.exception("Error processing %s message for business %s: %s", platform, business_id, exc)
            reply_text = "Gracias por escribirnos. En este momento estamos procesando tu consulta; en breve te respondemos."

    sent_live = False
    if not is_simulation:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT page_or_ig_id, access_token, enabled, parent_page_id
                FROM public.business_meta_channels
                WHERE business_id = %s::uuid AND platform = %s
                """,
                (business_id, platform),
            )
            ch_row = cur.fetchone()
        if ch_row and bool(ch_row[2]) and str(ch_row[1] or "").strip():
            sent_live, err = await _send_meta_graph_reply(
                platform=platform,
                page_or_ig_id=str(ch_row[0] or ""),
                access_token=str(ch_row[1] or ""),
                recipient_id=sender_id,
                message_text=reply_text,
                send_target_id=(str(ch_row[3] or "").strip() if platform == "instagram" else str(ch_row[0] or "")),
            )
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE public.business_meta_channels
                    SET last_event_at = now(),
                        last_error = %s,
                        updated_at = now()
                    WHERE business_id = %s::uuid AND platform = %s
                    """,
                    (err[:500] if err else None, business_id, platform),
                )
            conn.commit()

    return {
        "replied": True,
        "sent_live": sent_live,
        "reply_text": reply_text,
        "customer_id": str(customer_id),
        "conversation_id": str(conversation_id),
    }


def _channel_row_to_dict(business_id: str, platform: str, row: tuple | None, base_url: str = "") -> dict[str, Any]:
    default_vtoken = META_WEBHOOK_VERIFY_TOKEN or _default_verify_token(business_id)
    webhook_path = "/api/webhooks/meta"
    webhook_url = f"{base_url.rstrip('/')}{webhook_path}" if base_url else webhook_path
    if not row:
        return {
            "platform": platform,
            "label": _platform_label(platform),
            "enabled": False,
            "status": "disconnected",
            "configured": False,
            "account_name": "",
            "page_or_ig_id": "",
            "has_access_token": False,
            "token_hint": "",
            "verify_token": default_vtoken,
            "webhook_url": webhook_url,
            "last_error": None,
            "last_event_at": None,
            "connected_at": None,
        }
    enabled, status, account_name, page_or_ig_id, access_token, verify_token, last_error, last_event_at, connected_at = row
    token_str = str(access_token or "").strip()
    acc_str = str(account_name or "").strip()
    pid_str = str(page_or_ig_id or "").strip()
    vtok_str = str(verify_token or "").strip() or default_vtoken
    configured = bool(acc_str and pid_str and token_str)
    return {
        "platform": platform,
        "label": _platform_label(platform),
        "enabled": bool(enabled),
        "status": str(status or ("connected" if enabled else "disconnected")),
        "configured": configured,
        "account_name": acc_str,
        "page_or_ig_id": pid_str,
        "has_access_token": bool(token_str),
        "token_hint": f"••••{token_str[-4:]}" if len(token_str) >= 4 else "",
        "verify_token": vtok_str,
        "webhook_url": webhook_url,
        "last_error": str(last_error) if last_error else None,
        "last_event_at": last_event_at.isoformat() if last_event_at else None,
        "connected_at": connected_at.isoformat() if connected_at else None,
    }


# ---------------------------------------------------------------------------
# META OAUTH POPUP FLOW (FACEBOOK MESSENGER + INSTAGRAM UNIFIED LOGIN)
# Instagram Unified Login usa Facebook Login for Business con config_id:
# no se debe enviar scope ni cambiarlo por instagram.com/oauth/authorize.
# ---------------------------------------------------------------------------

def _meta_state_signature(payload: str) -> str:
    secret = os.getenv("META_APP_SECRET", META_APP_SECRET).strip()
    if not secret:
        raise HTTPException(status_code=503, detail="Falta configurar META_APP_SECRET en el servidor.")
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_meta_oauth_state(*, business_id: str, platform: str) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(18)
    payload = "|".join((business_id, platform, issued_at, nonce))
    return f"{payload}|{_meta_state_signature(payload)}"


def _parse_and_validate_meta_oauth_state(state: str | None) -> tuple[str, str] | None:
    parts = (state or "").split("|")
    if len(parts) != 5:
        return None
    business_id, platform, issued_at, nonce, signature = parts
    payload = "|".join(parts[:4])
    try:
        age = int(time.time()) - int(issued_at)
        if age < -60 or age > 600:
            return None
        expected = _meta_state_signature(payload)
    except (ValueError, HTTPException):
        return None
    if not hmac.compare_digest(signature, expected) or platform not in ("instagram", "facebook"):
        return None
    try:
        uuid.UUID(business_id)
    except (ValueError, TypeError, AttributeError):
        return None
    return business_id, platform


def _build_facebook_dialog_oauth_url(
    *,
    business_id: str,
    platform: str,
    force_login: bool = False,
    minimal_scopes: bool = False,
) -> str:
    app_id = os.getenv("META_APP_ID", "").strip() or META_APP_ID
    redirect_uri = os.getenv("META_REDIRECT_URI", "").strip() or META_REDIRECT_URI
    if not app_id or not redirect_uri:
        raise HTTPException(status_code=503, detail="Falta META_APP_ID o META_REDIRECT_URI en el servidor.")
    state = _build_meta_oauth_state(business_id=business_id, platform=platform)

    params: dict[str, str] = {
        "client_id": app_id,
        "display": "popup",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if platform == "instagram":
        config_id = os.getenv("META_CONFIG_ID", "").strip() or META_CONFIG_ID
        if config_id:
            # Unified Login: configuration defines the permissions. Sending scope as well
            # causes Invalid Scopes on Meta apps created with this newer setup.
            params["config_id"] = config_id
            params["override_default_response_type"] = "true"
        else:
            # Compatibility fallback for older Meta apps that still expose the legacy flow.
            params["scope"] = ",".join([
                "pages_show_list", "pages_messaging", "pages_manage_metadata",
                "instagram_basic", "instagram_manage_messages",
            ])
    elif platform == "facebook":
        facebook_config_id = os.getenv("META_FACEBOOK_CONFIG_ID", "").strip() or META_FACEBOOK_CONFIG_ID
        if facebook_config_id:
            params["config_id"] = facebook_config_id
            params["override_default_response_type"] = "true"
        else:
            scopes = ["pages_show_list", "pages_messaging", "pages_manage_metadata"]
            if minimal_scopes:
                scopes = ["public_profile", "pages_show_list"]
            params["scope"] = ",".join(scopes)
    else:
        raise HTTPException(status_code=422, detail="Canal Meta no válido para OAuth.")

    if force_login:
        params["auth_type"] = "reauthenticate"
    return f"https://www.facebook.com/{META_GRAPH_API_VERSION}/dialog/oauth?{urllib.parse.urlencode(params)}"


@router.get("/channels/meta/oauth-url")
@router.get("/auth/meta/login")
@router.get("/dashboard/channels/meta/oauth-url")
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    force_login: bool = Query(default=False),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        platform = "instagram"
    business_id = str(current_user["business_id"])
    auth_url = _build_facebook_dialog_oauth_url(
        business_id=business_id,
        platform=platform,
        force_login=force_login,
    )
    return {"success": True, "auth_url": auth_url, "platform": platform}


async def _subscribe_meta_webhook(
    *, platform: str, page_id: str, access_token: str
) -> tuple[bool, str | None]:
    """Attach the app to the linked Page; Unified Login Instagram messaging uses its Page token."""
    if not page_id or not access_token:
        return False, "No se recibió el ID de la Página ni su token de acceso."
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{page_id}/subscribed_apps"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                url,
                params={
                    "subscribed_fields": "messages,messaging_postbacks",
                    "access_token": access_token,
                },
            )
        try:
            data = response.json()
        except Exception:
            data = {}
        subscribed_ok = (
            isinstance(data, dict)
            and str(data.get("success", "")).strip().lower() == "true"
        )
        if response.status_code < 400 and subscribed_ok:
            return True, None
        err = ((data.get("error") or {}).get("message") if isinstance(data, dict) else None)
        return False, str(err or response.text or f"Meta respondió HTTP {response.status_code}")[:500]
    except Exception as exc:
        logger.warning("Meta webhook subscription failed (%s, page=%s): %s", platform, page_id, exc)
        return False, str(exc)[:500]


async def _activate_meta_account_in_db(
    *,
    business_id: str,
    platform: str,
    account_name: str,
    page_or_ig_id: str,
    access_token: str,
    subscribe_page_id: str | None = None,
) -> dict[str, Any]:
    vtoken = os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip() or _default_verify_token(business_id)
    ready, subscription_error = await _subscribe_meta_webhook(
        platform=platform,
        page_id=(subscribe_page_id or (page_or_ig_id if platform == "facebook" else "")),
        access_token=access_token,
    )
    status = "connected" if ready else "pending_webhook"
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.business_meta_channels
                   (business_id, platform, enabled, channel_status, account_name, page_or_ig_id,
                    parent_page_id, access_token, verify_token, last_error, connected_at, updated_at)
                   VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now())
                   ON CONFLICT (business_id, platform) DO UPDATE SET
                     enabled = EXCLUDED.enabled,
                     channel_status = EXCLUDED.channel_status,
                     account_name = EXCLUDED.account_name,
                     page_or_ig_id = EXCLUDED.page_or_ig_id,
                     parent_page_id = EXCLUDED.parent_page_id,
                     access_token = EXCLUDED.access_token,
                     verify_token = EXCLUDED.verify_token,
                     last_error = EXCLUDED.last_error,
                     connected_at = COALESCE(business_meta_channels.connected_at, now()),
                     updated_at = now()""",
                (
                    business_id, platform, ready, status, account_name[:160], page_or_ig_id[:120],
                    (subscribe_page_id or "")[:120], access_token, vtoken,
                    subscription_error,
                ),
            )
        conn.commit()
    return {"ready": ready, "channel_status": status, "last_error": subscription_error}


@router.post("/auth/meta/select-account")
async def select_meta_oauth_account(payload: MetaOAuthSelectAccountRequest) -> dict[str, Any]:
    """Activate only an account returned by this server-side OAuth session."""
    await ensure_meta_social_schema()
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 600:
        _pending_meta_oauth_sessions.pop(payload.session_key, None)
        raise HTTPException(status_code=400, detail="La sesión de vinculación expiró. Cierra esta ventana y vuelve a pulsar Conectar.")

    platform = payload.platform.lower().strip()
    requested_platform = str(session_info.get("requested_platform") or "")
    if platform != requested_platform or platform not in ("instagram", "facebook"):
        raise HTTPException(status_code=400, detail="La plataforma seleccionada no coincide con la autorización de Meta.")

    candidates = session_info.get("candidates") or []
    candidate = next((
        item for item in candidates
        if isinstance(item, dict) and str(item.get("id") or "") == payload.page_or_ig_id
    ), None)
    if not candidate:
        raise HTTPException(status_code=400, detail="La cuenta no pertenece a la sesión de autorización. Vuelve a conectar desde Meta.")

    account_name = str(candidate.get("name") or payload.account_name or "Cuenta Meta").strip()[:160]
    page_or_ig_id = str(candidate.get("id") or "").strip()[:120]
    page_id = str(candidate.get("page_id") or (page_or_ig_id if platform == "facebook" else "")).strip()[:120]
    access_token = str(candidate.get("access_token") or "").strip()
    if not page_or_ig_id or not page_id or not access_token:
        raise HTTPException(status_code=400, detail="Meta no devolvió una Página y un token válidos para esta cuenta. Verifica los permisos y vuelve a autorizar.")

    result = await _activate_meta_account_in_db(
        business_id=str(session_info["business_id"]),
        platform=platform,
        account_name=account_name,
        page_or_ig_id=page_or_ig_id,
        access_token=access_token,
        subscribe_page_id=page_id,
    )
    _pending_meta_oauth_sessions.pop(payload.session_key, None)
    if result["ready"]:
        message = f"✓ {_platform_label(platform)} ({account_name}) vinculado; webhook confirmado y listo para responder con IA."
    else:
        message = f"Cuenta guardada, pero Meta no confirmó la suscripción del webhook: {result['last_error'] or 'verifica la configuración de webhooks y permisos.'}"
    return {
        "success": True,
        "ready": result["ready"],
        "platform": platform,
        "account_name": account_name,
        "channel_status": result["channel_status"],
        "last_error": result["last_error"],
        "message": message,
    }


async def handle_meta_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    parsed_state = _parse_and_validate_meta_oauth_state(state)
    business_id, requested_platform = parsed_state if parsed_state else ("", "instagram")

    switch_account_url = (
        _build_facebook_dialog_oauth_url(business_id=business_id, platform=requested_platform, force_login=True)
        if business_id
        else "#"
    )
    rerequest_url = (
        _build_facebook_dialog_oauth_url(business_id=business_id, platform=requested_platform, force_login=False)
        if business_id
        else "#"
    )


    if error or not code or not business_id or not parsed_state:
        return HTMLResponse(
            f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Vincular {_platform_label(requested_platform)}</title></head>
            <body style="background:#090d16;color:#f8fafc;font-family:'Plus Jakarta Sans',system-ui,sans-serif;text-align:center;padding:48px 24px;">
            <div style="max-width:440px;margin:0 auto;padding:28px;border-radius:18px;background:#111827;border:1px solid rgba(255,255,255,0.1);">
                <h3 style="margin:0 0 10px;font-size:18px;">Conexión cancelada o incompleta</h3>
                <p style="color:#94a3b8;font-size:13.5px;line-height:1.5;margin-bottom:20px;">No se completó el inicio de sesión en Meta. Puedes intentar de nuevo o iniciar sesión con otra cuenta.</p>
                <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;">
                    <a href="{rerequest_url}" style="padding:10px 16px;border-radius:10px;background:#3b82f6;color:#fff;text-decoration:none;font-weight:700;font-size:13px;">Intentar de nuevo</a>
                    <button onclick="window.close()" style="padding:10px 16px;border-radius:10px;background:rgba(255,255,255,0.08);color:#cbd5e1;border:1px solid rgba(255,255,255,0.12);cursor:pointer;font-size:13px;">Cerrar ventana</button>
                </div>
            </div>
            <script>
                if (window.opener) {{
                    window.opener.postMessage({{ type: 'META_CONNECTED', status: 'error', message: 'Inicio de sesión cancelado o estado OAuth no válido' }}, {json.dumps(urllib.parse.urlsplit(os.getenv('META_REDIRECT_URI', META_REDIRECT_URI).strip()).scheme + '://' + urllib.parse.urlsplit(os.getenv('META_REDIRECT_URI', META_REDIRECT_URI).strip()).netloc)});
                }}
            </script></body></html>"""
        )

    app_id = os.getenv("META_APP_ID", "").strip() or META_APP_ID
    app_secret = os.getenv("META_APP_SECRET", "").strip() or META_APP_SECRET
    redirect_uri = os.getenv("META_REDIRECT_URI", "").strip() or META_REDIRECT_URI

    user_access_token = ""
    me_name = "Usuario de Meta"
    me_id = ""
    discovered_pages: list[dict[str, str]] = []
    discovered_ig_accounts: list[dict[str, str]] = []
    error_detail = ""

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_res = await client.get(
                f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/oauth/access_token",
                params={
                    "client_id": app_id,
                    "redirect_uri": redirect_uri,
                    "client_secret": app_secret,
                    "code": code,
                },
            )
            token_data = token_res.json()
            user_access_token = str(token_data.get("access_token") or "").strip()
            if not user_access_token:
                error_detail = str(
                    (token_data.get("error") or {}).get("message")
                    or "Falta META_APP_SECRET en el servidor o el código de autorización expiró."
                )
            else:
                # Exchange the short-lived user token for a long-lived token before
                # requesting Page tokens; this reduces unexpected disconnects.
                long_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/oauth/access_token",
                    params={
                        "grant_type": "fb_exchange_token",
                        "client_id": app_id,
                        "client_secret": app_secret,
                        "fb_exchange_token": user_access_token,
                    },
                )
                if long_res.status_code < 400:
                    long_data = long_res.json()
                    user_access_token = str(long_data.get("access_token") or user_access_token).strip()
                else:
                    logger.warning("Meta long-lived token exchange failed: %s", long_res.text[:300])

                me_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me",
                    params={"fields": "id,name", "access_token": user_access_token},
                )
                me_json = me_res.json() if me_res.status_code < 400 else {}
                me_id = str(me_json.get("id") or "").strip()
                me_name = str(me_json.get("name") or "Cuenta Meta").strip()

                # 1. Consultar páginas directas de la cuenta (/me/accounts)
                pages_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/accounts",
                    params={
                        "fields": "id,name,access_token,tasks,instagram_business_account{id,username}",
                        "limit": "100",
                        "access_token": user_access_token,
                    },
                )
                pages_json = pages_res.json() if pages_res.content else {}
                raw_pages = list(pages_json.get("data") or []) if pages_res.status_code < 400 and isinstance(pages_json, dict) else []
                if pages_res.status_code >= 400:
                    error_detail = str((pages_json.get("error") or {}).get("message") or "Meta no permitió listar las páginas. Revisa pages_show_list y los activos incluidos en la configuración.")

                # 2. Consultar páginas dentro de Business Manager (/me/businesses -> owned_pages / client_pages)
                try:
                    biz_res = await client.get(
                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/businesses",
                        params={
                            "fields": "id,name,owned_pages{id,name,access_token,tasks,instagram_business_account{id,username}}",
                            "access_token": user_access_token,
                        },
                    )
                    if biz_res.status_code < 400:
                        for b_item in (biz_res.json().get("data") or []):
                            for p_item in ((b_item.get("owned_pages") or {}).get("data") or []):
                                raw_pages.append(p_item)
                except Exception:
                    pass

                if not raw_pages and not error_detail:
                    error_detail = "Meta inició sesión, pero no devolvió páginas. En la cuenta autorizada debes tener una Página con tarea de mensajería y, para Instagram, una cuenta profesional vinculada. Revisa los activos/permisos de la configuración Unified Login."

                seen_page_ids: set[str] = set()
                seen_ig_ids: set[str] = set()
                for page in raw_pages:
                    if not isinstance(page, dict):
                        continue
                    page_id = str(page.get("id") or "").strip()
                    page_name = str(page.get("name") or "Página de Facebook").strip()[:160]
                    page_token = str(page.get("access_token") or "").strip()
                    if page_id and page_id not in seen_page_ids and page_token:
                        seen_page_ids.add(page_id)
                        discovered_pages.append(
                            {
                                "id": page_id,
                                "name": page_name,
                                "page_id": page_id,
                                "access_token": page_token,
                            }
                        )
                    ig_obj = page.get("instagram_business_account") or {}
                    if isinstance(ig_obj, dict):
                        ig_id = str(ig_obj.get("id") or "").strip()
                        ig_user = str(ig_obj.get("username") or ig_obj.get("name") or "").strip()
                        if ig_id and page_id and page_token and ig_id not in seen_ig_ids:
                            seen_ig_ids.add(ig_id)
                            ig_handle = f"@{ig_user.lstrip('@')}" if ig_user else f"@{page_name.replace(' ', '_').lower()}"
                            discovered_ig_accounts.append(
                                {
                                    "id": ig_id,
                                    "name": ig_handle[:160],
                                    "page_name": page_name,
                                    "page_id": page_id,
                                    "access_token": page_token,
                                }
                            )
    except Exception as exc:
        logger.exception("Error procesando OAuth callback de Meta: %s", exc)
        error_detail = str(exc)

    session_key = uuid.uuid4().hex
    candidates = discovered_ig_accounts if requested_platform == "instagram" else discovered_pages
    auto_activated_info = None
    if len(candidates) == 1 and not error_detail:
        only = candidates[0]
        try:
            auto_res = await _activate_meta_account_in_db(
                business_id=business_id,
                platform=requested_platform,
                account_name=str(only.get("name") or "Cuenta Meta")[:160],
                page_or_ig_id=str(only.get("id") or "")[:120],
                access_token=str(only.get("access_token") or ""),
                subscribe_page_id=str(only.get("page_id") or only.get("id") or "")[:120],
            )
            auto_activated_info = {
                "ready": auto_res["ready"],
                "account_name": str(only.get("name") or "Cuenta Meta"),
                "message": f"✓ {_platform_label(requested_platform)} ({only.get('name')}) vinculado automáticamente en 1 clic.",
            }
        except Exception as _auto_exc:
            logger.warning("Auto-activation of single Meta candidate failed: %s", _auto_exc)
    # Keep Page tokens server-side; never embed access tokens in popup HTML/JavaScript.
    _pending_meta_oauth_sessions[session_key] = {
        "business_id": business_id,
        "requested_platform": requested_platform,
        "user_access_token": user_access_token,
        "me_id": me_id,
        "me_name": me_name,
        "candidates": candidates,
        "created_at": time.time(),
    }
    for old_key, old_session in list(_pending_meta_oauth_sessions.items()):
        if time.time() - float(old_session.get("created_at", 0)) > 600:
            _pending_meta_oauth_sessions.pop(old_key, None)

    platform_title = "Instagram Direct" if requested_platform == "instagram" else "Facebook Messenger"
    accent_gradient = (
        "linear-gradient(135deg,#f43f5e,#a855f7)"
        if requested_platform == "instagram"
        else "linear-gradient(135deg,#3b82f6,#1d4ed8)"
    )
    safe_me_name = html.escape(me_name)
    public_candidates = [
        {"id": item.get("id", ""), "name": item.get("name", ""),
         "page_name": item.get("page_name", ""), "page_id": item.get("page_id", "")}
        for item in candidates
    ]
    candidates_json = json.dumps(public_candidates)

    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar {platform_title} · CALYRISIA</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 28px 18px;
    background: radial-gradient(circle at 50% 0%, rgba(56,189,248,0.14), transparent 55%), #090d16;
    color: #f8fafc;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  }}
  .card {{
    max-width: 500px; margin: 0 auto;
    background: rgba(15, 23, 42, 0.92);
    border: 1px solid rgba(148, 163, 184, 0.2);
    border-radius: 20px; padding: 24px;
    box-shadow: 0 24px 60px rgba(0,0,0,0.5);
  }}
  .pill {{
    display: inline-block; padding: 4px 10px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    background: rgba(56, 189, 248, 0.12); color: #7cecf5; border: 1px solid rgba(56, 189, 248, 0.3);
    margin-bottom: 10px;
  }}
  h2 {{ margin: 0 0 6px; font-size: 1.25rem; }}
  p.sub {{ margin: 0 0 18px; color: #94a3b8; font-size: 13px; line-height: 1.55; }}
  .account-option {{
    display: flex; align-items: center; justify-content: space-between; gap: 12px;
    padding: 13px 15px; border-radius: 14px;
    background: rgba(255,255,255,0.03); border: 1px solid rgba(148,163,184,0.18);
    margin-bottom: 10px;
  }}
  .account-option strong {{ display: block; font-size: 14px; color: #fff; }}
  .account-option small {{ color: #94a3b8; font-size: 12px; }}
  .btn-primary {{
    border: 0; border-radius: 11px; padding: 10px 16px;
    background: {accent_gradient}; color: #fff;
    font-weight: 700; font-size: 12.5px; cursor: pointer; white-space: nowrap;
  }}
  .btn-secondary {{
    display: inline-flex; align-items: center; justify-content: center;
    border: 1px solid rgba(148,163,184,0.25); border-radius: 11px; padding: 9px 14px;
    background: rgba(255,255,255,0.04); color: #cbd5e1;
    font-weight: 600; font-size: 12px; text-decoration: none; cursor: pointer;
  }}
  .input-box {{
    width: 100%; padding: 11px 13px; border-radius: 11px;
    background: #060a12; border: 1px solid rgba(148,163,184,0.28);
    color: #fff; font-size: 13px; margin-bottom: 10px;
  }}
  .status-msg {{ margin-top: 12px; font-size: 12.5px; min-height: 18px; }}
</style>
</head>
<body>
<div class="card">
  <span class="pill">{platform_title}</span>
  <h2>Selecciona la cuenta que quedará activa</h2>
  <p class="sub">
    Sesión autorizada: <strong style="color:#e2e8f0;">{safe_me_name}</strong>.
    Selecciona una cuenta realmente devuelta por Meta para activar el canal:
  </p>

  <div id="accounts-list"></div>


  <div id="status-msg" class="status-msg"></div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-top:18px;padding-top:14px;border-top:1px solid rgba(148,163,184,0.14);">
    <a href="{switch_account_url}" class="btn-secondary">Cambiar de cuenta de Meta</a>
    <a href="{rerequest_url}" class="btn-secondary">Elegir otras páginas en Meta</a>
  </div>
</div>

<script>
const SESSION_KEY = {json.dumps(session_key)};
const PLATFORM = {json.dumps(requested_platform)};
const CANDIDATES = {candidates_json};
const ERROR_DETAIL = {json.dumps(error_detail)};

const listEl = document.getElementById('accounts-list');
const statusEl = document.getElementById('status-msg');

const PARENT_ORIGIN = {json.dumps(urllib.parse.urlsplit(os.getenv("META_REDIRECT_URI", META_REDIRECT_URI).strip()).scheme + "://" + urllib.parse.urlsplit(os.getenv("META_REDIRECT_URI", META_REDIRECT_URI).strip()).netloc)};
function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function notifyParentAndClose(accountName, message) {{
  if (window.opener && PARENT_ORIGIN) {{
    window.opener.postMessage({{
      type: 'META_CONNECTED', status: 'ok', platform: PLATFORM,
      account_name: accountName, message: message || 'Cuenta conectada y lista para responder con IA.'
    }}, PARENT_ORIGIN);
  }}
  setTimeout(() => window.close(), 700);
}}
async function selectAccount(id, name) {{
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Activando ' + name + ' en CALYRISIA...';
  try {{
    const res = await fetch('/api/v1/auth/meta/select-account', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ session_key: SESSION_KEY, platform: PLATFORM, page_or_ig_id: id, account_name: name }})
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'No se pudo activar la cuenta.');
    statusEl.style.color = data.ready ? '#34d399' : '#fbbf24';
    statusEl.textContent = data.message || 'Resultado de la vinculación recibido.';
    if (data.ready) notifyParentAndClose(data.account_name || name, data.message);
  }} catch (err) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = err.message;
  }}
}}
if (ERROR_DETAIL) {{
  statusEl.style.color = '#fda4af';
  statusEl.textContent = ERROR_DETAIL;
}}

if (CANDIDATES.length > 0) {{
  listEl.innerHTML = CANDIDATES.map((item, idx) => {{
    const sub = item.page_name ? ('Página vinculada: ' + escapeHtml(item.page_name)) : ('ID: ' + escapeHtml(item.id));
    return `<div class="account-option">
      <div><strong>${{escapeHtml(item.name)}}</strong><small>${{sub}}</small></div>
      <button type="button" class="btn-primary" id="cand-btn-${{idx}}">Conectar y activar</button>
    </div>`;
  }}).join('');
  CANDIDATES.forEach((item, idx) => {{
    document.getElementById('cand-btn-' + idx)?.addEventListener('click', () => selectAccount(item.id, item.name));
  }});
  const AUTO_ACTIVATED = {json.dumps(auto_activated_info)};
  if (AUTO_ACTIVATED && AUTO_ACTIVATED.ready) {{
    statusEl.style.color = '#34d399';
    statusEl.textContent = AUTO_ACTIVATED.message;
    notifyParentAndClose(AUTO_ACTIVATED.account_name, AUTO_ACTIVATED.message);
  }}
}} else {{
  listEl.innerHTML = `<div style="padding:12px 14px;border-radius:12px;background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.28);color:#fde68a;font-size:12.5px;margin-bottom:10px;">
    Meta no devolvió cuentas autorizadas para este canal. No se creará una conexión ficticia. Comprueba que elegiste los activos correctos en Unified Login, que la cuenta de Instagram es Profesional y que está vinculada a una Página; después vuelve a iniciar sesión.
  </div>`;
}}
</script>
</body>
</html>"""
    )


@router.get("/auth/meta/callback")
async def meta_oauth_callback_route(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    return await handle_meta_oauth_callback(code=code, state=state, error=error)


# ---------------------------------------------------------------------------
# DASHBOARD ENDPOINTS FOR INSTAGRAM & FACEBOOK MESSENGER
# ---------------------------------------------------------------------------

@router.get("/dashboard/channels/meta")
async def get_meta_channels(
    request: Request,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    base_url = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""
    rows_by_platform: dict[str, tuple] = {}
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT platform, enabled, channel_status, account_name, page_or_ig_id,
                          access_token, verify_token, last_error, last_event_at, connected_at
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid""",
                (business_id,),
            )
            for r in cur.fetchall():
                rows_by_platform[str(r[0])] = r[1:]
    return {
        "success": True,
        "instagram": _channel_row_to_dict(business_id, "instagram", rows_by_platform.get("instagram"), base_url),
        "facebook": _channel_row_to_dict(business_id, "facebook", rows_by_platform.get("facebook"), base_url),
        "whatsapp": _channel_row_to_dict(business_id, "whatsapp", rows_by_platform.get("whatsapp"), base_url),
    }


@router.put("/dashboard/channels/meta/{platform}")
async def save_meta_channel(
    platform: str,
    payload: MetaChannelConfigUpdate,
    request: Request,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        raise HTTPException(status_code=422, detail="Plataforma inválida. Usa 'instagram', 'facebook' o 'whatsapp'.")
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    base_url = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""

    account_name = (payload.account_name or "").strip()[:160]
    page_or_ig_id = (payload.page_or_ig_id or "").strip()[:120]
    access_token = (payload.access_token or "").strip()[:600]
    verify_token = (payload.verify_token or "").strip()[:160] or META_WEBHOOK_VERIFY_TOKEN or _default_verify_token(business_id)

    if platform in ("instagram", "facebook"):
        # These channels must come from a real OAuth selection so the linked Page ID,
        # Page token and Instagram business ID remain paired correctly.
        raise HTTPException(
            status_code=409,
            detail=f"{_platform_label(platform)} se vincula con el botón OAuth del dashboard. No uses la configuración manual.",
        )

    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT account_name, page_or_ig_id, access_token, verify_token
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
            existing = cur.fetchone()
            if existing:
                if not account_name:
                    account_name = str(existing[0] or "")
                if not page_or_ig_id:
                    page_or_ig_id = str(existing[1] or "")
                if not access_token:
                    access_token = str(existing[2] or "")
                if not payload.verify_token and existing[3]:
                    verify_token = str(existing[3])

            if not account_name:
                account_name = (
                    "WhatsApp Business" if platform == "whatsapp"
                    else ("@cuenta_instagram" if platform == "instagram" else "Página de Facebook")
                )
            if not page_or_ig_id:
                page_or_ig_id = f"meta_{platform}_{business_id[:8]}"

            status = "connected" if payload.enabled else "paused"
            cur.execute(
                """INSERT INTO public.business_meta_channels
                   (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, access_token, verify_token, last_error, connected_at, updated_at)
                   VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, %s, NULL, now(), now())
                   ON CONFLICT (business_id, platform) DO UPDATE SET
                     enabled = EXCLUDED.enabled,
                     channel_status = EXCLUDED.channel_status,
                     account_name = EXCLUDED.account_name,
                     page_or_ig_id = EXCLUDED.page_or_ig_id,
                     access_token = EXCLUDED.access_token,
                     verify_token = EXCLUDED.verify_token,
                     last_error = NULL,
                     connected_at = COALESCE(business_meta_channels.connected_at, now()),
                     updated_at = now()""",
                (business_id, platform, payload.enabled, status, account_name, page_or_ig_id, access_token, verify_token),
            )
            cur.execute(
                """SELECT enabled, channel_status, account_name, page_or_ig_id,
                          access_token, verify_token, last_error, last_event_at, connected_at
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
            row = cur.fetchone()
        conn.commit()

    return {
        "success": True,
        "message": f"{_platform_label(platform)} vinculado y activo para responder con el Cerebro IA.",
        "channel": _channel_row_to_dict(business_id, platform, row, base_url),
    }


@router.post("/dashboard/channels/meta/{platform}/toggle")
async def toggle_meta_channel(
    platform: str,
    payload: MetaChannelToggleRequest,
    request: Request,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        raise HTTPException(status_code=422, detail="Plataforma inválida.")
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    base_url = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""
    result_error = None
    enabled = bool(payload.enabled)
    status = "connected" if enabled else "paused"
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT account_name, page_or_ig_id, parent_page_id, access_token
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
            existing = cur.fetchone()
            if not existing:
                raise HTTPException(status_code=404, detail=f"Primero vincula tu cuenta de {_platform_label(platform)}.")
            if enabled:
                account_id, parent_page_id, access_token = str(existing[1] or ""), str(existing[2] or ""), str(existing[3] or "")
                if platform in ("instagram", "facebook"):
                    page_id = parent_page_id or (account_id if platform == "facebook" else "")
                    ready, result_error = await _subscribe_meta_webhook(platform=platform, page_id=page_id, access_token=access_token)
                    if not ready:
                        enabled = False
                        status = "pending_webhook"
                    elif not access_token or not account_id:
                        enabled = False
                        status = "pending_webhook"
                        result_error = "Falta el ID de la cuenta o el token de Meta. Desvincula y vuelve a autorizar el canal."
                else:
                    # WhatsApp Cloud has its own WABA subscription flow; leave its existing toggle semantics unchanged.
                    result_error = None
            else:
                status = "paused"
            cur.execute(
                """UPDATE public.business_meta_channels
                   SET enabled = %s, channel_status = %s, last_error = %s, updated_at = now()
                   WHERE business_id = %s::uuid AND platform = %s""",
                (enabled, status, result_error, business_id, platform),
            )
            cur.execute(
                """SELECT enabled, channel_status, account_name, page_or_ig_id,
                          access_token, verify_token, last_error, last_event_at, connected_at
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
            row = cur.fetchone()
        conn.commit()
    if enabled:
        message = f"{_platform_label(platform)} activado; Meta confirmó la suscripción del webhook."
    elif payload.enabled:
        message = f"La cuenta sigue guardada, pero no se activó porque Meta no confirmó el webhook: {result_error or 'verifica permisos y configuración.'}"
    else:
        message = f"{_platform_label(platform)} está en pausa."
    return {
        "success": True,
        "enabled": enabled,
        "message": message,
        "channel": _channel_row_to_dict(business_id, platform, row, base_url),
    }


@router.post("/dashboard/channels/meta/{platform}/disconnect")
async def disconnect_meta_channel(
    platform: str,
    request: Request,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        raise HTTPException(status_code=422, detail="Plataforma inválida.")
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    base_url = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.business_meta_channels WHERE business_id = %s::uuid AND platform = %s",
                (business_id, platform),
            )
        conn.commit()
    return {
        "success": True,
        "message": f"{_platform_label(platform)} desvinculado correctamente.",
        "channel": _channel_row_to_dict(business_id, platform, None, base_url),
    }


@router.post("/dashboard/channels/meta/{platform}/test")
async def test_meta_channel_message(
    platform: str,
    payload: MetaChannelTestRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        raise HTTPException(status_code=422, detail="Plataforma inválida.")
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    sender_handle = (payload.sender_handle or "@cliente_social").strip()
    sender_name = (payload.sender_name or f"Cliente {_platform_label(platform)}").strip()
    async with get_connection() as conn:
        result = await process_meta_incoming_message(
            conn,
            business_id=business_id,
            platform=platform,
            sender_id=sender_handle,
            sender_name=sender_name,
            message_text=payload.message,
            is_simulation=True,
        )
    return {
        "success": True,
        "platform": platform,
        "platform_label": _platform_label(platform),
        "customer_message": payload.message,
        "bot_reply": result.get("reply_text") or "Sin respuesta generada.",
        "customer_id": result.get("customer_id"),
        "conversation_id": result.get("conversation_id"),
    }


# ---------------------------------------------------------------------------
# PUBLIC META GRAPH API WEBHOOKS (GLOBAL MULTI-TENANT + PER-BUSINESS)
# ---------------------------------------------------------------------------

async def verify_global_meta_webhook_handler(
    hub_mode: str | None = None,
    hub_verify_token: str | None = None,
    hub_challenge: str | None = None,
    business_id: str | None = None,
) -> PlainTextResponse:
    if hub_mode != "subscribe" or hub_challenge is None:
        raise HTTPException(status_code=400, detail="Solicitud de verificación Meta incompleta.")

    token_clean = (hub_verify_token or "").strip()
    if not token_clean:
        raise HTTPException(status_code=403, detail="Token de verificación Meta inválido.")

    env_token = os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip()
    valid = bool(env_token and hmac.compare_digest(token_clean, env_token))

    if not valid:
        try:
            await ensure_meta_social_schema()
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    if business_id:
                        cur.execute(
                            """SELECT 1 FROM public.business_meta_channels
                               WHERE business_id = %s::uuid AND verify_token = %s LIMIT 1""",
                            (business_id, token_clean),
                        )
                    else:
                        cur.execute(
                            """SELECT 1 FROM public.business_meta_channels
                               WHERE verify_token = %s LIMIT 1""",
                            (token_clean,),
                        )
                    valid = cur.fetchone() is not None
        except Exception as exc:
            logger.warning("Could not validate Meta webhook token from the database: %s", exc)
            valid = False

    if not valid:
        raise HTTPException(status_code=403, detail="Token de verificación Meta inválido.")
    return PlainTextResponse(content=str(hub_challenge), status_code=200)


async def _process_meta_webhook_payload(body: dict[str, Any], explicit_business_id: str | None = None) -> None:
    """Process Meta webhook events after the HTTP endpoint has acknowledged delivery."""
    await ensure_meta_social_schema()
    obj_type = str(body.get("object") or "").lower().strip()
    entries = body.get("entry") if isinstance(body.get("entry"), list) else []
    if not entries:
        return

    async with get_connection() as conn:
        if obj_type == "whatsapp_business_account":
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                changes = entry.get("changes") if isinstance(entry.get("changes"), list) else []
                for change in changes:
                    if not isinstance(change, dict) or change.get("field") not in (None, "messages"):
                        continue
                    value = change.get("value") if isinstance(change.get("value"), dict) else {}
                    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
                    phone_id = str(metadata.get("phone_number_id") or "").strip()
                    messages = value.get("messages") if isinstance(value.get("messages"), list) else []
                    contacts = value.get("contacts") if isinstance(value.get("contacts"), list) else []
                    if not phone_id:
                        continue
                    target_business_id = explicit_business_id
                    with conn.cursor() as cur:
                        if target_business_id:
                            cur.execute(
                                """SELECT business_id::text FROM public.business_meta_channels
                                   WHERE business_id = %s::uuid AND platform = 'whatsapp'
                                     AND page_or_ig_id = %s AND enabled = true LIMIT 1""",
                                (target_business_id, phone_id),
                            )
                        else:
                            cur.execute(
                                """SELECT business_id::text FROM public.business_meta_channels
                                   WHERE platform = 'whatsapp' AND page_or_ig_id = %s AND enabled = true
                                   LIMIT 1""",
                                (phone_id,),
                            )
                        matched = cur.fetchone()
                    if not matched:
                        continue
                    target_business_id = str(matched[0])
                    for message in messages:
                        if not isinstance(message, dict):
                            continue
                        sender_id = str(message.get("from") or "").strip()
                        message_type = str(message.get("type") or "").lower()
                        message_text = ""
                        if message_type == "text":
                            text_obj = message.get("text") if isinstance(message.get("text"), dict) else {}
                            message_text = str(text_obj.get("body") or "").strip()
                        elif message_type == "interactive":
                            interactive = message.get("interactive") if isinstance(message.get("interactive"), dict) else {}
                            reply = interactive.get("button_reply") or interactive.get("list_reply") or {}
                            if isinstance(reply, dict):
                                message_text = str(reply.get("title") or reply.get("id") or "").strip()
                        if not sender_id or not message_text:
                            continue
                        sender_name = sender_id
                        for contact in contacts:
                            if isinstance(contact, dict) and str(contact.get("wa_id") or "") == sender_id:
                                profile = contact.get("profile") if isinstance(contact.get("profile"), dict) else {}
                                sender_name = str(profile.get("name") or sender_id)
                                break
                        try:
                            await process_meta_incoming_message(
                                conn, business_id=target_business_id, platform="whatsapp",
                                sender_id=sender_id, sender_name=sender_name,
                                message_text=message_text, is_simulation=False,
                            )
                        except Exception as exc:
                            conn.rollback()
                            logger.exception("WhatsApp Cloud webhook processing failed for business %s: %s", target_business_id, exc)
            return

        if obj_type not in {"instagram", "page"}:
            logger.debug("Ignored unsupported Meta webhook object: %s", obj_type)
            return
        platform = "instagram" if obj_type == "instagram" else "facebook"
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_account_id = str(entry.get("id") or "").strip()
            events = entry.get("messaging") if isinstance(entry.get("messaging"), list) else []
            for evt in events:
                if not isinstance(evt, dict):
                    continue
                msg = evt.get("message") if isinstance(evt.get("message"), dict) else {}
                if msg.get("is_echo"):
                    continue
                postback = evt.get("postback") if isinstance(evt.get("postback"), dict) else {}
                quick_reply = msg.get("quick_reply") if isinstance(msg.get("quick_reply"), dict) else {}
                text_value = (
                    msg.get("text")
                    or quick_reply.get("payload")
                    or postback.get("title")
                    or postback.get("payload")
                )
                message_text = str(text_value or "").strip()
                sender = evt.get("sender") if isinstance(evt.get("sender"), dict) else {}
                sender_id = str(sender.get("id") or "").strip()
                recipient = evt.get("recipient") if isinstance(evt.get("recipient"), dict) else {}
                recipient_id = str(recipient.get("id") or entry_account_id).strip()
                if not message_text or not sender_id or sender_id in (recipient_id, entry_account_id):
                    continue

                # Match the exact page/IG account or parent_page_id. Never route unmatched messages to an arbitrary tenant.
                target_business_id = explicit_business_id
                with conn.cursor() as cur:
                    if target_business_id:
                        cur.execute(
                            """SELECT business_id::text FROM public.business_meta_channels
                               WHERE business_id = %s::uuid AND platform = %s
                                 AND (page_or_ig_id IN (%s, %s) OR parent_page_id IN (%s, %s))
                                 AND enabled = true LIMIT 1""",
                            (target_business_id, platform, recipient_id, entry_account_id, recipient_id, entry_account_id),
                        )
                    else:
                        cur.execute(
                            """SELECT business_id::text FROM public.business_meta_channels
                               WHERE platform = %s
                                 AND (page_or_ig_id IN (%s, %s) OR parent_page_id IN (%s, %s))
                                 AND enabled = true
                               ORDER BY updated_at DESC LIMIT 1""",
                            (platform, recipient_id, entry_account_id, recipient_id, entry_account_id),
                        )
                    matched = cur.fetchone()
                if not matched:
                    continue
                target_business_id = str(matched[0])
                sender_name = f"Usuario {'IG' if platform == 'instagram' else 'FB'} #{sender_id[-4:]}"
                try:
                    await process_meta_incoming_message(
                        conn, business_id=target_business_id, platform=platform,
                        sender_id=sender_id, sender_name=sender_name,
                        message_text=message_text, is_simulation=False,
                    )
                except Exception as exc:
                    conn.rollback()
                    logger.exception("Meta webhook processing failed for business %s (%s): %s", target_business_id, platform, exc)


async def receive_global_meta_webhook_handler(
    request: Request,
    explicit_business_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> PlainTextResponse:
    try:
        raw_body = await request.body()
        app_secret = os.getenv("META_APP_SECRET", "").strip() or META_APP_SECRET
        signature = request.headers.get("X-Hub-Signature-256", "").strip()
        if app_secret:
            expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not signature or not hmac.compare_digest(signature, expected):
                raise HTTPException(status_code=401, detail="Firma de webhook Meta inválida.")
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        if not isinstance(body, dict):
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
    except HTTPException:
        raise
    except Exception:
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)

    if background_tasks is not None:
        background_tasks.add_task(_process_meta_webhook_payload, body, explicit_business_id)
    else:
        await _process_meta_webhook_payload(body, explicit_business_id)
    return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)


@router.get("/webhooks/meta")
async def verify_meta_webhook_global(
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    return await verify_global_meta_webhook_handler(hub_mode, hub_verify_token, hub_challenge)


@router.post("/webhooks/meta")
async def receive_meta_webhook_global(request: Request, background_tasks: BackgroundTasks):
    return await receive_global_meta_webhook_handler(request, background_tasks=background_tasks)


@router.get("/webhooks/meta/{business_id}")
async def verify_meta_webhook(
    business_id: str,
    hub_mode: str | None = Query(default=None, alias="hub.mode"),
    hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
    hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
):
    return await verify_global_meta_webhook_handler(hub_mode, hub_verify_token, hub_challenge, business_id=business_id)


@router.post("/webhooks/meta/{business_id}")
async def receive_meta_webhook(business_id: str, request: Request, background_tasks: BackgroundTasks):
    return await receive_global_meta_webhook_handler(request, explicit_business_id=business_id, background_tasks=background_tasks)