from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import uuid
from decimal import Decimal
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
from app.api.telegram import (
    _clean_for_telegram,
    _looks_like_payment_submission,
    _parse_payment_marker,
    notify_owner_payment_pending,
)
from app.core.logger import get_logger
from app.db import get_connection
from app.schemas import IncomingMessage
from app.services.autopilot_service import GalaxyAutopilotService
from app.services.commercial_limits import (
    AIQuotaExceeded,
    consume_ai_response,
)

logger = get_logger(__name__)
router = APIRouter()

_meta_schema_initialized = False
VALID_META_PLATFORMS = {"instagram", "facebook", "whatsapp"}

META_APP_ID = os.getenv("META_APP_ID", "2456430845105397").strip()
META_CONFIG_ID = os.getenv("META_CONFIG_ID", "1831235794732615").strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
META_REDIRECT_URI = os.getenv("META_REDIRECT_URI", "https://calyrisia.com/api/auth/meta/callback").strip()
META_WEBHOOK_VERIFY_TOKEN = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "").strip()
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v26.0").strip() or "v26.0"


class MetaChannelConfigUpdate(BaseModel):
    account_name: str | None = Field(default=None, max_length=160)
    page_or_ig_id: str | None = Field(default=None, max_length=120)
    access_token: str | None = Field(default=None, max_length=600)
    verify_token: str | None = Field(default=None, max_length=160)
    enabled: bool = Field(default=True)


class MetaChannelToggleRequest(BaseModel):
    enabled: bool


class MetaChannelTestRequest(BaseModel):
    message: str = Field(
        default="Hola, vi su perfil y quiero saber qué productos tienen disponibles y precios",
        min_length=1,
        max_length=1500,
    )
    sender_name: str = Field(default="Cliente Demo Social", max_length=120)
    sender_handle: str = Field(default="@cliente_demo", max_length=100)


def _default_verify_token(business_id: str) -> str:
    digest = hashlib.sha256(f"calyrisia-meta-{business_id}".encode("utf-8")).hexdigest()[:12]
    return f"calyrisia_meta_{digest}"


async def ensure_meta_social_schema() -> None:
    """Idempotent schema for Instagram DM and Facebook Messenger business channels."""
    global _meta_schema_initialized
    if _meta_schema_initialized:
        return
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.business_meta_channels (
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        platform varchar(20) NOT NULL CHECK (platform IN ('instagram', 'facebook', 'whatsapp')),
                        enabled boolean NOT NULL DEFAULT false,
                        channel_status varchar(30) NOT NULL DEFAULT 'disconnected',
                        account_name varchar(160),
                        page_or_ig_id varchar(120),
                        access_token text,
                        verify_token varchar(160),
                        last_error text,
                        last_event_at timestamptz,
                        connected_at timestamptz,
                        updated_at timestamptz NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (business_id, platform)
                    )
                    """
                )
                cur.execute("ALTER TABLE public.business_meta_channels DROP CONSTRAINT IF EXISTS business_meta_channels_platform_check")
                cur.execute(
                    """ALTER TABLE public.business_meta_channels
                       ADD CONSTRAINT business_meta_channels_platform_check
                       CHECK (platform IN ('instagram', 'facebook', 'whatsapp'))"""
                )
                try:
                    cur.execute("SAVEPOINT sp_meta_rls")
                    cur.execute("ALTER TABLE public.business_meta_channels ENABLE ROW LEVEL SECURITY")
                    cur.execute(
                        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_meta_channels TO postgres, service_role"
                    )
                    cur.execute("RELEASE SAVEPOINT sp_meta_rls")
                except Exception:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_meta_rls")
                    except Exception:
                        pass
            conn.commit()
            _meta_schema_initialized = True
        except Exception:
            conn.rollback()
            _meta_schema_initialized = True


def _graph_api_call_sync(
    path: str,
    access_token: str,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    timeout: int = 10,
) -> dict[str, Any]:
    sep = "&" if "?" in path else "?"
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{path.lstrip('/')}{sep}access_token={urllib.parse.quote(access_token)}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


async def _send_meta_graph_message(
    *,
    page_or_ig_id: str | None,
    access_token: str | None,
    recipient_id: str,
    text: str,
    platform: str = "facebook",
) -> bool:
    if not access_token or not recipient_id or not text:
        return False
    if access_token.startswith("demo_") or access_token.startswith("test_") or len(access_token.strip()) < 20:
        return True
    target = (page_or_ig_id or "me").strip() or "me"
    try:
        if platform == "whatsapp":
            payload = {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": recipient_id,
                "type": "text",
                "text": {"preview_url": False, "body": text[:4096]},
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{target}/messages",
                    headers={"Authorization": f"Bearer {access_token.strip()}"},
                    json=payload,
                )
                response.raise_for_status()
        else:
            payload = {
                "recipient": {"id": recipient_id},
                "messaging_type": "RESPONSE",
                "message": {"text": text[:2000]},
            }
            await asyncio.to_thread(
                _graph_api_call_sync, f"{target}/messages", access_token.strip(), "POST", payload, 10
            )
        return True
    except Exception as exc:
        logger.warning("Error enviando respuesta por Meta Graph API (%s, %s): %s", platform, target, exc)
        return False


def _platform_label(platform: str) -> str:
    if platform == "instagram":
        return "Instagram Direct"
    if platform == "whatsapp":
        return "WhatsApp Business (Cloud API)"
    return "Facebook Messenger"


def _channel_row_to_dict(business_id: str, platform: str, row: tuple | None, base_url: str = "") -> dict[str, Any]:
    default_vtoken = META_WEBHOOK_VERIFY_TOKEN or _default_verify_token(business_id)
    webhook_path = "/api/webhooks/meta"
    webhook_url = f"{base_url.rstrip('/')}{webhook_path}" if base_url else f"https://calyrisia.com{webhook_path}"
    if not row:
        return {
            "platform": platform,
            "label": _platform_label(platform),
            "configured": False,
            "enabled": False,
            "status": "disconnected",
            "account_name": "",
            "page_or_ig_id": "",
            "token_hint": "",
            "verify_token": default_vtoken,
            "webhook_url": webhook_url,
            "last_error": None,
            "last_event_at": None,
            "connected_at": None,
        }
    enabled, status, acc_name, page_id, acc_token, ver_token, last_err, last_evt, conn_at = row
    tok_str = str(acc_token or "").strip()
    token_hint = f"...{tok_str[-6:]}" if len(tok_str) > 6 else ("Configurado" if tok_str else "")
    return {
        "platform": platform,
        "label": _platform_label(platform),
        "configured": bool(acc_name or page_id or tok_str),
        "enabled": bool(enabled),
        "status": str(status or "disconnected"),
        "account_name": str(acc_name or ""),
        "page_or_ig_id": str(page_id or ""),
        "token_hint": token_hint,
        "verify_token": str(ver_token or default_vtoken),
        "webhook_url": webhook_url,
        "last_error": last_err,
        "last_event_at": str(last_evt) if last_evt else None,
        "connected_at": str(conn_at) if conn_at else None,
    }


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
    """Process an incoming Instagram DM or Facebook Messenger message through CALYRISIA's Brain, CRM & Payments."""
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        platform = "instagram"

    with conn.cursor() as cur:
        cur.execute(
            """SELECT b.status, b.name, COALESCE(d.exchange_rate, 0), COALESCE(d.local_currency_code, 'VES')
               FROM public.businesses b
               LEFT JOIN public.business_dashboard_settings d ON d.business_id = b.id
               WHERE b.id = %s::uuid""",
            (business_id,),
        )
        biz_row = cur.fetchone()
        if not biz_row or str(biz_row[0]) != "active":
            return {"ok": False, "reply_text": "El negocio no está activo."}
        biz_name = str(biz_row[1] or "nuestro negocio")
        ex_rate = float(biz_row[2] or 0)
        loc_curr = str(biz_row[3] or "VES")

        cur.execute(
            """SELECT enabled, page_or_ig_id, access_token, account_name
               FROM public.business_meta_channels
               WHERE business_id = %s::uuid AND platform = %s""",
            (business_id, platform),
        )
        ch_row = cur.fetchone()
        if not is_simulation and (not ch_row or not bool(ch_row[0])):
            return {"ok": True, "reply_text": ""}

        page_or_ig_id = str(ch_row[1] or "") if ch_row else ""
        access_token = str(ch_row[2] or "") if ch_row else ""

        handle_key = f"{platform}:{sender_id}"
        clean_sender_name = (sender_name or f"Cliente {_platform_label(platform)}").strip()[:180]
        cur.execute(
            """SELECT id, full_name FROM public.customers
               WHERE business_id = %s::uuid AND (phone = %s OR full_name = %s)
               ORDER BY created_at DESC LIMIT 1""",
            (business_id, handle_key, clean_sender_name),
        )
        cust_row = cur.fetchone()
        if cust_row:
            customer_id = uuid.UUID(str(cust_row[0]))
            try:
                cur.execute(
                    "UPDATE public.customers SET last_interaction_at = now() WHERE id = %s",
                    (str(customer_id),),
                )
            except Exception:
                pass
        else:
            customer_id = uuid.uuid4()
            try:
                cur.execute("SAVEPOINT sp_meta_cust")
                cur.execute(
                    """INSERT INTO public.customers
                       (id, business_id, full_name, phone, status, source, channel, first_contact_at, last_interaction_at, notes)
                       VALUES (%s, %s::uuid, %s, %s, 'active', %s, %s, now(), now(), %s)""",
                    (
                        str(customer_id),
                        business_id,
                        clean_sender_name,
                        handle_key,
                        platform,
                        platform,
                        f"Cliente capturado automáticamente desde {_platform_label(platform)}.",
                    ),
                )
                cur.execute("RELEASE SAVEPOINT sp_meta_cust")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT sp_meta_cust")
                cur.execute(
                    """INSERT INTO public.customers (id, business_id, full_name, phone, status, source, notes)
                       VALUES (%s, %s, %s, %s, 'active', %s, %s)""",
                    (
                        str(customer_id),
                        business_id,
                        clean_sender_name,
                        handle_key,
                        platform,
                        f"Cliente capturado automáticamente desde {_platform_label(platform)}.",
                    ),
                )

        cur.execute(
            """SELECT id FROM public.conversations
               WHERE business_id = %s::uuid AND customer_id = %s AND channel = %s AND status = 'active'
               ORDER BY updated_at DESC NULLS LAST LIMIT 1""",
            (business_id, str(customer_id), platform),
        )
        conv_row = cur.fetchone()
        if conv_row:
            conversation_id = uuid.UUID(str(conv_row[0]))
        else:
            conversation_id = uuid.uuid4()
            try:
                cur.execute("SAVEPOINT sp_meta_conv")
                cur.execute(
                    """INSERT INTO public.conversations (id, business_id, customer_id, channel, status, started_at, last_message_at)
                       VALUES (%s, %s::uuid, %s, %s, 'active', now(), now())""",
                    (str(conversation_id), business_id, str(customer_id), platform),
                )
                cur.execute("RELEASE SAVEPOINT sp_meta_conv")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT sp_meta_conv")
                cur.execute(
                    """INSERT INTO public.conversations (id, business_id, customer_id, channel, status)
                       VALUES (%s, %s, %s, %s, 'active')""",
                    (str(conversation_id), business_id, str(customer_id), platform),
                )

        if ch_row:
            cur.execute(
                """UPDATE public.business_meta_channels
                   SET last_event_at = now(), updated_at = now()
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
    conn.commit()

    if _looks_like_payment_submission(message_text):
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content FROM public.conversation_messages
                   WHERE business_id = %s::uuid AND customer_id = %s AND conversation_id = %s AND direction = 'outbound'
                   ORDER BY created_at DESC LIMIT 10""",
                (business_id, str(customer_id), str(conversation_id)),
            )
            outbound_msgs = [str(r[0] or "") for r in cur.fetchall()]
        amount, items = _parse_payment_marker(outbound_msgs)
        if amount is None:
            m_amt = re.search(r"(\d+(?:[.,]\d{1,2})?)", message_text)
            amount = Decimal(m_amt.group(1).replace(",", ".")).quantize(Decimal("0.01")) if m_amt else Decimal("1.00")
        raw_norm = message_text.lower()
        pay_method = "binance" if "binance" in raw_norm else "pago_movil"
        pay_id = uuid.uuid4()
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.webchat_payment_requests
                   (id, business_id, customer_id, amount, currency, payment_method, status, source, approval_note, items, customer_payment_details)
                   VALUES (%s, %s::uuid, %s, %s, 'USD', %s, 'pending', %s,
                           %s, %s, %s)""",
                (
                    str(pay_id),
                    business_id,
                    str(customer_id),
                    amount,
                    pay_method,
                    platform,
                    f"Solicitud de pago recibida por {_platform_label(platform)}; pendiente de aprobación.",
                    Jsonb(items) if items else None,
                    message_text[:4000],
                ),
            )
        conn.commit()
        try:
            await notify_owner_payment_pending(
                business_id=business_id,
                payment_id=str(pay_id),
                amount=amount,
                customer_name=f"{clean_sender_name} ({_platform_label(platform)})",
                customer_chat_id=handle_key,
                payment_details=message_text,
                payment_method=f"{'Binance Pay' if pay_method == 'binance' else 'Pago Móvil'} · {_platform_label(platform)}",
                items=items,
            )
        except Exception:
            pass
        reply_text = (
            f"✅ Recibimos los datos de tu pago en {biz_name} por USD {amount:.2f}. "
            f"Tu referencia quedó registrada en nuestro panel para verificación y te confirmaremos por {_platform_label(platform)} apenas sea aprobada."
        )
        if not is_simulation:
            await _send_meta_graph_message(
                page_or_ig_id=page_or_ig_id,
                access_token=access_token,
                recipient_id=sender_id,
                text=reply_text,
                platform=platform,
            )
        return {"ok": True, "reply_text": reply_text, "customer_id": str(customer_id), "conversation_id": str(conversation_id)}

    try:
        consume_ai_response(conn, uuid.UUID(business_id))
        conn.commit()
    except AIQuotaExceeded as exc:
        return {"ok": False, "reply_text": str(exc)}

    incoming = IncomingMessage(
        business_id=uuid.UUID(business_id),
        customer_id=customer_id,
        conversation_id=conversation_id,
        channel=("messenger" if platform == "facebook" else ("whatsapp" if platform == "whatsapp" else "instagram")),
        message=message_text,
        metadata={"source": f"calyrisia_{platform}", "sender_id": sender_id, "sender_name": clean_sender_name},
    )
    result = GalaxyAutopilotService(conn).respond(incoming)
    raw_reply = str(result.get("response") or "").strip()
    clean_reply, pay_amount, _ = _clean_for_telegram(raw_reply)

    if pay_amount is not None and pay_amount > 0:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT method_code, instructions FROM public.business_payment_instructions WHERE business_id = %s::uuid AND enabled = true ORDER BY method_code",
                (business_id,),
            )
            methods = cur.fetchall()
        if methods:
            loc_line = (
                f"\n💱 Equivalente a tasa del día ({ex_rate:.2f} {loc_curr}/USD): {loc_curr} {(float(pay_amount) * ex_rate):,.2f}"
                if ex_rate > 0
                else ""
            )
            inst_lines = [f"\n\n💳 DATOS DE PAGO ({biz_name}):\nTotal: USD {float(pay_amount):.2f}{loc_line}"]
            for m_code, m_inst in methods:
                label = {"pago_movil": "Pago Móvil", "transferencia": "Transferencia Bancaria", "zelle": "Zelle", "binance": "Binance Pay", "paypal": "PayPal"}.get(str(m_code), str(m_code).title())
                inst_lines.append(f"\n• {label}:\n{str(m_inst).strip()}")
            inst_lines.append(
                "\nCuando realices el pago, envíame por este mismo chat el número de referencia (ej. 'Referencia 123456') para registrarlo al instante."
            )
            clean_reply = (clean_reply + "\n" + "\n".join(inst_lines)).strip()

    if not is_simulation:
        await _send_meta_graph_message(
            page_or_ig_id=page_or_ig_id,
            access_token=access_token,
            recipient_id=sender_id,
            text=clean_reply,
            platform=platform,
        )

    return {
        "ok": True,
        "platform": platform,
        "platform_label": _platform_label(platform),
        "reply_text": clean_reply,
        "customer_id": str(customer_id),
        "conversation_id": str(conversation_id),
    }


# ---------------------------------------------------------------------------
# OAUTH 2.0 UNIFIED LOGIN POPUP & AUTOMATIC WEBHOOK SUBSCRIPTION
# ---------------------------------------------------------------------------

@router.get("/dashboard/channels/meta/oauth-url")
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in VALID_META_PLATFORMS:
        platform = "instagram"
    business_id = str(current_user["business_id"])
    app_id = os.getenv("META_APP_ID", META_APP_ID).strip()
    config_id = os.getenv("META_CONFIG_ID", META_CONFIG_ID).strip()
    redirect_uri = os.getenv("META_REDIRECT_URI", META_REDIRECT_URI).strip()
    state = f"{business_id}:{platform}"

    params = {
        "client_id": app_id,
        "display": "popup",
        "override_default_response_type": "true",
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "state": state,
    }
    if config_id:
        params["config_id"] = config_id
    else:
        params["scope"] = (
            "pages_show_list,pages_messaging,pages_manage_metadata,instagram_basic,"
            "instagram_manage_messages,business_management,whatsapp_business_management,whatsapp_business_messaging"
        )

    auth_url = f"https://www.facebook.com/dialog/oauth?{urllib.parse.urlencode(params)}"
    return {"success": True, "auth_url": auth_url, "platform": platform}


async def handle_meta_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    await ensure_meta_social_schema()
    if error or not code or not state:
        return HTMLResponse(
            """<html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;text-align:center;padding-top:60px;">
            <h3>Conexión cancelada o incompleta</h3>
            <script>
                if (window.opener) {
                    window.opener.postMessage({ type: 'META_CONNECTED', status: 'error', message: 'Inicio de sesión cancelado' }, '*');
                }
                setTimeout(() => window.close(), 1200);
            </script></body></html>"""
        )

    parts = state.split(":", 1)
    business_id = parts[0].strip()
    requested_platform = parts[1].strip() if len(parts) > 1 else "instagram"

    app_id = os.getenv("META_APP_ID", META_APP_ID).strip()
    app_secret = os.getenv("META_APP_SECRET", META_APP_SECRET).strip()
    redirect_uri = os.getenv("META_REDIRECT_URI", META_REDIRECT_URI).strip()
    vtoken = os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip() or _default_verify_token(business_id)

    connected_platforms: list[str] = []
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
            user_access_token = token_data.get("access_token")
            if not user_access_token:
                error_detail = str(token_data.get("error", {}).get("message") or "Falta META_APP_SECRET en Render o el código expiró.")
            else:
                pages_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/accounts",
                    params={
                        "fields": "id,name,access_token,instagram_business_account{id,username,name}",
                        "access_token": user_access_token,
                    },
                )
                pages_data = pages_res.json().get("data") or []

                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        for page in pages_data:
                            page_id = str(page.get("id") or "").strip()
                            page_name = str(page.get("name") or "Página de Facebook").strip()[:160]
                            page_token = str(page.get("access_token") or user_access_token).strip()
                            if page_id and page_token:
                                try:
                                    await client.post(
                                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{page_id}/subscribed_apps",
                                        params={
                                            "subscribed_fields": "messages,messaging_postbacks",
                                            "access_token": page_token,
                                        },
                                    )
                                except Exception as sub_exc:
                                    logger.warning("No se pudo suscribir automáticamente la página %s: %s", page_id, sub_exc)

                                cur.execute(
                                    """INSERT INTO public.business_meta_channels
                                       (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, access_token, verify_token, last_error, connected_at, updated_at)
                                       VALUES (%s::uuid, 'facebook', true, 'connected', %s, %s, %s, %s, NULL, now(), now())
                                       ON CONFLICT (business_id, platform) DO UPDATE SET
                                         enabled = true,
                                         channel_status = 'connected',
                                         account_name = EXCLUDED.account_name,
                                         page_or_ig_id = EXCLUDED.page_or_ig_id,
                                         access_token = EXCLUDED.access_token,
                                         verify_token = EXCLUDED.verify_token,
                                         last_error = NULL,
                                         connected_at = COALESCE(business_meta_channels.connected_at, now()),
                                         updated_at = now()""",
                                    (business_id, page_name, page_id, page_token, vtoken),
                                )
                                connected_platforms.append("facebook")

                            ig_obj = page.get("instagram_business_account") or {}
                            ig_id = str(ig_obj.get("id") or "").strip()
                            ig_user = str(ig_obj.get("username") or ig_obj.get("name") or "").strip()
                            if ig_id:
                                ig_handle = f"@{ig_user.lstrip('@')}" if ig_user else f"IG #{ig_id[-6:]}"
                                cur.execute(
                                    """INSERT INTO public.business_meta_channels
                                       (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, access_token, verify_token, last_error, connected_at, updated_at)
                                       VALUES (%s::uuid, 'instagram', true, 'connected', %s, %s, %s, %s, NULL, now(), now())
                                       ON CONFLICT (business_id, platform) DO UPDATE SET
                                         enabled = true,
                                         channel_status = 'connected',
                                         account_name = EXCLUDED.account_name,
                                         page_or_ig_id = EXCLUDED.page_or_ig_id,
                                         access_token = EXCLUDED.access_token,
                                         verify_token = EXCLUDED.verify_token,
                                         last_error = NULL,
                                         connected_at = COALESCE(business_meta_channels.connected_at, now()),
                                         updated_at = now()""",
                                    (business_id, ig_handle[:160], ig_id, page_token, vtoken),
                                )
                                connected_platforms.append("instagram")

                        # WhatsApp Cloud API: discover the connected WABA and its phone-number ID.
                        # Some login configurations do not grant these scopes; that should not block IG/FB.
                        try:
                            businesses_res = await client.get(
                                f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/businesses",
                                params={"fields": "id,name", "access_token": user_access_token},
                            )
                            business_items = businesses_res.json().get("data") or []
                            seen_wabas: set[str] = set()
                            for meta_business in business_items:
                                meta_business_id = str(meta_business.get("id") or "").strip()
                                if not meta_business_id:
                                    continue
                                waba_res = await client.get(
                                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{meta_business_id}/owned_whatsapp_business_accounts",
                                    params={
                                        "fields": "id,name,phone_numbers{id,display_phone_number,verified_name}",
                                        "access_token": user_access_token,
                                    },
                                )
                                for waba in (waba_res.json().get("data") or []):
                                    waba_id = str(waba.get("id") or "").strip()
                                    if not waba_id or waba_id in seen_wabas:
                                        continue
                                    seen_wabas.add(waba_id)
                                    try:
                                        await client.post(
                                            f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{waba_id}/subscribed_apps",
                                            params={"access_token": user_access_token},
                                        )
                                    except Exception as sub_exc:
                                        logger.warning("No se pudo suscribir WABA %s al webhook: %s", waba_id, sub_exc)
                                    phones = (waba.get("phone_numbers") or {}).get("data") or []
                                    for phone_item in phones:
                                        phone_id = str(phone_item.get("id") or "").strip()
                                        if not phone_id:
                                            continue
                                        phone_label = str(
                                            phone_item.get("verified_name")
                                            or phone_item.get("display_phone_number")
                                            or waba.get("name")
                                            or "WhatsApp Business"
                                        ).strip()[:160]
                                        cur.execute(
                                            """INSERT INTO public.business_meta_channels
                                               (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, access_token, verify_token, last_error, connected_at, updated_at)
                                               VALUES (%s::uuid, 'whatsapp', true, 'connected', %s, %s, %s, %s, NULL, now(), now())
                                               ON CONFLICT (business_id, platform) DO UPDATE SET
                                                 enabled = true, channel_status = 'connected',
                                                 account_name = EXCLUDED.account_name,
                                                 page_or_ig_id = EXCLUDED.page_or_ig_id,
                                                 access_token = EXCLUDED.access_token,
                                                 verify_token = EXCLUDED.verify_token,
                                                 last_error = NULL, updated_at = now()""",
                                            (business_id, phone_label, phone_id, user_access_token, vtoken),
                                        )
                                        connected_platforms.append("whatsapp")
                                        break
                                    if "whatsapp" in connected_platforms:
                                        break
                                if "whatsapp" in connected_platforms:
                                    break
                        except Exception as wa_exc:
                            logger.info("WhatsApp Cloud API no se habilitó en este login Meta (opcional): %s", wa_exc)

                        # Fallback if user logged in with Unified Instagram Login without a linked FB Page list
                        if not connected_platforms:
                            me_res = await client.get(
                                f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me",
                                params={"fields": "id,name", "access_token": user_access_token},
                            )
                            me_data = me_res.json()
                            me_id = str(me_data.get("id") or f"meta_{requested_platform}_{business_id[:8]}").strip()
                            me_name = str(me_data.get("name") or f"Cuenta {requested_platform.title()}").strip()[:160]
                            cur.execute(
                                """INSERT INTO public.business_meta_channels
                                   (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, access_token, verify_token, last_error, connected_at, updated_at)
                                   VALUES (%s::uuid, %s, true, 'connected', %s, %s, %s, %s, NULL, now(), now())
                                   ON CONFLICT (business_id, platform) DO UPDATE SET
                                     enabled = true,
                                     channel_status = 'connected',
                                     account_name = EXCLUDED.account_name,
                                     page_or_ig_id = EXCLUDED.page_or_ig_id,
                                     access_token = EXCLUDED.access_token,
                                     verify_token = EXCLUDED.verify_token,
                                     last_error = NULL,
                                     connected_at = COALESCE(business_meta_channels.connected_at, now()),
                                     updated_at = now()""",
                                (business_id, requested_platform, me_name, me_id, user_access_token, vtoken),
                            )
                            connected_platforms.append(requested_platform)
                    conn.commit()
    except Exception as exc:
        logger.exception("Error procesando OAuth callback de Meta: %s", exc)
        error_detail = str(exc)

    status_js = "ok" if connected_platforms else "error"
    msg_js = "Cuenta conectada y lista para responder con IA." if connected_platforms else (error_detail or "No se pudo completar la vinculación.")
    return HTMLResponse(
        f"""<html><body style="background:#0f172a;color:#f8fafc;font-family:sans-serif;text-align:center;padding-top:60px;">
        <h3>{"✓ ¡Cuenta conectada con éxito!" if connected_platforms else "Aviso de conexión Meta"}</h3>
        <p style="color:#94a3b8;font-size:14px;">{msg_js}</p>
        <script>
            if (window.opener) {{
                window.opener.postMessage({{
                    type: 'META_CONNECTED',
                    status: {json.dumps(status_js)},
                    platform: {json.dumps(requested_platform)},
                    message: {json.dumps(msg_js)}
                }}, '*');
            }}
            setTimeout(() => window.close(), 900);
        </script></body></html>"""
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
                    else ("@mi_negocio_ig" if platform == "instagram" else "MiPagina Oficial")
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
    status = "connected" if payload.enabled else "paused"
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.business_meta_channels
                   (business_id, platform, enabled, channel_status, account_name, page_or_ig_id, verify_token, connected_at, updated_at)
                   VALUES (%s::uuid, %s, %s, %s, %s, %s, %s, now(), now())
                   ON CONFLICT (business_id, platform) DO UPDATE SET
                     enabled = EXCLUDED.enabled,
                     channel_status = EXCLUDED.channel_status,
                     updated_at = now()""",
                (
                    business_id,
                    platform,
                    payload.enabled,
                    status,
                    f"@{'cuenta_ig' if platform == 'instagram' else 'PaginaFB'}",
                    f"meta_{platform}_{business_id[:8]}",
                    META_WEBHOOK_VERIFY_TOKEN or _default_verify_token(business_id),
                ),
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
        "enabled": payload.enabled,
        "message": f"{_platform_label(platform)} {'activado' if payload.enabled else 'en pausa'}.",
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
                text_value = msg.get("text")
                message_text = str(text_value or "").strip()
                sender = evt.get("sender") if isinstance(evt.get("sender"), dict) else {}
                sender_id = str(sender.get("id") or "").strip()
                recipient = evt.get("recipient") if isinstance(evt.get("recipient"), dict) else {}
                recipient_id = str(recipient.get("id") or entry_account_id).strip()
                if not message_text or not sender_id:
                    continue

                # Match the exact page/IG account. Never route unmatched messages to an arbitrary tenant.
                target_business_id = explicit_business_id
                with conn.cursor() as cur:
                    if target_business_id:
                        cur.execute(
                            """SELECT business_id::text FROM public.business_meta_channels
                               WHERE business_id = %s::uuid AND platform = %s
                                 AND page_or_ig_id IN (%s, %s) AND enabled = true LIMIT 1""",
                            (target_business_id, platform, recipient_id, entry_account_id),
                        )
                    else:
                        cur.execute(
                            """SELECT business_id::text FROM public.business_meta_channels
                               WHERE platform = %s AND page_or_ig_id IN (%s, %s) AND enabled = true
                               ORDER BY updated_at DESC LIMIT 1""",
                            (platform, recipient_id, entry_account_id),
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
        app_secret = os.getenv("META_APP_SECRET", META_APP_SECRET).strip()
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