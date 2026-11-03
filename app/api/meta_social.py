from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import json
import logging
import os
import re
import secrets
import time
import unicodedata
import urllib.parse
import uuid
from datetime import datetime, timezone
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
from app.core.config import get_settings
from app.db import get_connection
from app.meta_schemas import MetaOAuthUrlResponse, NormalizedOmnichannelPayload
from app.services.business_brain_service import BusinessBrainService
from app.services.omnichannel_gateway_service import OmnichannelGatewayService
from app.services.tenant_guard import MultitenantContext, get_multitenant_guard

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_META_PLATFORMS = ("instagram", "facebook", "whatsapp")
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v26.0").strip() or "v26.0"

META_APP_ID = os.getenv("META_APP_ID", "2456430845105397").strip() or "2456430845105397"
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
META_CONFIG_ID = os.getenv("META_CONFIG_ID", "1831235794732615").strip() or "1831235794732615"
META_FACEBOOK_CONFIG_ID = os.getenv("META_FACEBOOK_CONFIG_ID", "").strip()
META_REDIRECT_URI = os.getenv(
    "META_REDIRECT_URI",
    "https://calyrisia.com/api/auth/meta/callback",
).strip()
META_WEBHOOK_VERIFY_TOKEN = os.getenv("META_WEBHOOK_VERIFY_TOKEN", "").strip()

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

_pending_meta_oauth_sessions: dict[str, dict[str, Any]] = {}
_social_polling_task: asyncio.Task | None = None
_processed_social_msg_ids: set[str] = set()

IG_MOBILE_USER_AGENT = (
    "Instagram 275.0.0.27.98 Android (33/13; 420dpi; 1080x2400; "
    "samsung; SM-G991B; o1s; exynos2100; es_ES; 458229258)"
)
IG_APP_ID = "936619743392459"


class MetaChannelConfigUpdate(BaseModel):
    account_name: str = Field(default="", max_length=160)
    page_or_ig_id: str | None = Field(default=None, max_length=120)
    access_token: str | None = Field(default=None, max_length=2000)
    password_or_session: str | None = Field(default=None, max_length=2000)
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


class MetaPopupDirectLoginRequest(BaseModel):
    session_key: str = Field(..., min_length=8, max_length=120)
    platform: str = Field(..., min_length=3, max_length=30)
    username: str = Field(..., min_length=1, max_length=160)
    password: str = Field(..., min_length=1, max_length=500)


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


# ---------------------------------------------------------------------------
# CLIENTE DIRECTO DE INSTAGRAM Y GRAPH API (ENVÍO Y POLLING 100% EN LA NUBE)
# ---------------------------------------------------------------------------

async def _login_instagram_direct_session(username: str, password_or_session: str) -> dict[str, Any]:
    """Autentica directamente en Instagram desde la nube sin requerir Meta for Developers."""
    clean_user = username.strip().lstrip("@")
    cred = password_or_session.strip()
    if not cred:
        return {"ok": False}

    if "sessionid=" in cred or (len(cred) > 24 and "%" in cred and " " not in cred):
        sid = cred.split("sessionid=")[-1].split(";")[0].strip()
        ds_user_id = sid.split("%3A")[0].split(":")[0]
        return {
            "ok": True,
            "mode": "ig_session",
            "sessionid": sid,
            "ds_user_id": ds_user_id,
            "username": f"@{clean_user}" if clean_user else "@instagram",
            "token_payload": f"ig_session:{json.dumps({'sessionid': sid, 'ds_user_id': ds_user_id, 'username': clean_user})}",
        }

    if cred.startswith(("EAA", "IGQ", "IGA")):
        return {
            "ok": True,
            "mode": "graph_token",
            "token_payload": cred,
            "ds_user_id": f"ig_{clean_user}",
            "username": f"@{clean_user}" if clean_user else "@instagram",
        }

    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            await client.get(
                "https://www.instagram.com/accounts/login/",
                headers={"User-Agent": IG_MOBILE_USER_AGENT},
            )
            csrf = client.cookies.get("csrftoken") or "calyrisia_csrf_token"
            ts = int(time.time())
            login_res = await client.post(
                "https://www.instagram.com/api/v1/web/accounts/login/ajax/",
                headers={
                    "User-Agent": IG_MOBILE_USER_AGENT,
                    "X-CSRFToken": csrf,
                    "X-IG-App-ID": IG_APP_ID,
                    "X-Requested-With": "XMLHttpRequest",
                    "Referer": "https://www.instagram.com/accounts/login/",
                },
                data={
                    "username": clean_user,
                    "enc_password": f"#PWD_INSTAGRAM_BROWSER:0:{ts}:{cred}",
                    "queryParams": "{}",
                    "optIntoOneTap": "false",
                },
            )
            data = login_res.json() if login_res.content else {}
            sid = client.cookies.get("sessionid") or ""
            if data.get("authenticated") and sid:
                uid = str(data.get("userId") or sid.split("%3A")[0])
                return {
                    "ok": True,
                    "mode": "ig_session",
                    "sessionid": sid,
                    "ds_user_id": uid,
                    "username": f"@{clean_user}",
                    "token_payload": f"ig_session:{json.dumps({'sessionid': sid, 'ds_user_id': uid, 'csrftoken': csrf, 'username': clean_user})}",
                }
    except Exception as exc:
        logger.info("Instagram direct login notice (%s): %s", clean_user, exc)

    return {"ok": False}


async def _send_instagram_direct_session_reply(session_data: dict[str, Any], thread_id: str, text: str) -> tuple[bool, str | None]:
    sid = str(session_data.get("sessionid") or "").strip()
    csrf = str(session_data.get("csrftoken") or "calyrisia_csrf").strip()
    if not sid or not thread_id or not text:
        return False, "Falta sessionid o thread_id de Instagram."
    client_ctx = str(uuid.uuid4())
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                "https://i.instagram.com/api/v1/direct_v2/threads/broadcast/text/",
                headers={
                    "User-Agent": IG_MOBILE_USER_AGENT,
                    "X-IG-App-ID": IG_APP_ID,
                    "X-CSRFToken": csrf,
                },
                cookies={"sessionid": sid, "csrftoken": csrf},
                data={
                    "thread_ids": f"[{thread_id}]",
                    "action": "send_item",
                    "text": text[:1900],
                    "client_context": client_ctx,
                    "mutation_token": client_ctx,
                },
            )
            if resp.status_code < 400:
                return True, None
            return False, resp.text[:300]
    except Exception as exc:
        return False, str(exc)[:300]


async def _send_meta_graph_reply(
    *,
    platform: str,
    page_or_ig_id: str,
    access_token: str,
    recipient_id: str,
    message_text: str,
    send_target_id: str | None = None,
) -> tuple[bool, str | None]:
    """Envía la respuesta generada por la IA mediante la Graph API (`/me/messages` o `/{page_id}/messages`) o sesión directa."""
    token = (access_token or "").strip()
    if not token or not recipient_id or not message_text:
        return False, "Falta token, destinatario o contenido para enviar el mensaje."

    if token.startswith("ig_session:"):
        try:
            sess = json.loads(token[len("ig_session:"):])
            return await _send_instagram_direct_session_reply(sess, recipient_id, message_text)
        except Exception as exc:
            return False, str(exc)[:300]

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
    external_message_id: str | None = None,
    instance_or_page_id: str | None = None,
) -> dict[str, Any]:
    """Enruta el mensaje de Instagram Direct, Facebook Messenger o WhatsApp al canal único de IA (`BusinessBrainService`)."""
    text = str(message_text or "").strip()
    if not text:
        return {"replied": False, "reply_text": ""}

    if external_message_id:
        dedup_key = f"{platform}:{business_id}:{external_message_id}"
        if dedup_key in _processed_social_msg_ids:
            return {"replied": False, "reply_text": "", "duplicate": True}
        _processed_social_msg_ids.add(dedup_key)

    norm_payload = NormalizedOmnichannelPayload(
        tenant_id=uuid.UUID(str(business_id)),
        channel=platform if platform in ("instagram", "facebook", "whatsapp") else "facebook",
        sender_id=str(sender_id).strip()[:160],
        sender_name=str(sender_name or f"Cliente {_platform_label(platform)}").strip()[:180],
        message_text=text,
        timestamp=datetime.now(timezone.utc),
        external_message_id=external_message_id,
        instance_or_page_id=instance_or_page_id,
        metadata={"simulation": is_simulation, "platform": platform},
    )

    brain_res = await BusinessBrainService(conn).aprocess_omnichannel_chat(norm_payload)
    reply_text = str(brain_res.get("reply_text") or "").strip()
    customer_id = brain_res.get("customer_id")
    conversation_id = brain_res.get("conversation_id")

    sent_live = False
    if not is_simulation and reply_text:
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
        "replied": bool(reply_text),
        "sent_live": sent_live,
        "reply_text": reply_text,
        "customer_id": customer_id,
        "conversation_id": conversation_id,
        "policies_loaded": brain_res.get("policies_loaded", 0),
    }


# ---------------------------------------------------------------------------
# MOTOR CLOUD POLLING 24/7 (RESPONDE AUTOMÁTICAMENTE AUN SIN WEBHOOKS DE META)
# ---------------------------------------------------------------------------

async def _poll_single_social_channel(
    business_id: str,
    platform: str,
    account_name: str,
    page_or_ig_id: str,
    parent_page_id: str,
    access_token: str,
) -> None:
    """Consulta cada 3 segundos las conversaciones de la Página/Instagram conectada y responde automáticamente."""
    token = (access_token or "").strip()
    if not token:
        return

    # A) Sesión directa de Instagram (cuando el cliente conectó con usuario y contraseña)
    if platform == "instagram" and token.startswith("ig_session:"):
        try:
            sess = json.loads(token[len("ig_session:"):])
            sid = str(sess.get("sessionid") or "").strip()
            csrf = str(sess.get("csrftoken") or "calyrisia_csrf").strip()
            my_uid = str(sess.get("ds_user_id") or sid.split("%3A")[0]).strip()
            if not sid:
                return
            async with httpx.AsyncClient(timeout=12.0) as client:
                try:
                    pend_res = await client.get(
                        "https://i.instagram.com/api/v1/direct_v2/pending_inbox/",
                        headers={"User-Agent": IG_MOBILE_USER_AGENT, "X-IG-App-ID": IG_APP_ID},
                        cookies={"sessionid": sid, "csrftoken": csrf},
                    )
                    if pend_res.status_code < 400 and pend_res.content:
                        pend_threads = ((pend_res.json() or {}).get("inbox") or {}).get("threads") or []
                        for pt in pend_threads[:5]:
                            tid = str(pt.get("thread_id") or "")
                            if tid:
                                await client.post(
                                    f"https://i.instagram.com/api/v1/direct_v2/threads/{tid}/approve/",
                                    headers={"User-Agent": IG_MOBILE_USER_AGENT, "X-IG-App-ID": IG_APP_ID, "X-CSRFToken": csrf},
                                    cookies={"sessionid": sid, "csrftoken": csrf},
                                )
                except Exception:
                    pass

                inbox_res = await client.get(
                    "https://i.instagram.com/api/v1/direct_v2/inbox/?persistentBadging=true&folder=&limit=10&thread_message_limit=3",
                    headers={"User-Agent": IG_MOBILE_USER_AGENT, "X-IG-App-ID": IG_APP_ID},
                    cookies={"sessionid": sid, "csrftoken": csrf},
                )
                if inbox_res.status_code >= 400 or not inbox_res.content:
                    return
                threads = ((inbox_res.json() or {}).get("inbox") or {}).get("threads") or []
                for th in threads:
                    if not isinstance(th, dict):
                        continue
                    thread_id = str(th.get("thread_id") or "").strip()
                    items = th.get("items") or []
                    if not thread_id or not items or not isinstance(items[0], dict):
                        continue
                    last_item = items[0]
                    item_id = str(last_item.get("item_id") or "").strip()
                    sender_uid = str(last_item.get("user_id") or "").strip()
                    if not item_id or sender_uid == my_uid:
                        continue
                    dedup_key = f"instagram:{business_id}:{item_id}"
                    if dedup_key in _processed_social_msg_ids:
                        continue
                    ts_usec = int(last_item.get("timestamp") or 0)
                    if ts_usec > 0 and (time.time() - (ts_usec / 1_000_000.0)) > 600:
                        _processed_social_msg_ids.add(dedup_key)
                        continue
                    msg_text = str(last_item.get("text") or "").strip()
                    if not msg_text:
                        continue
                    users = th.get("users") or []
                    sender_name = str((users[0].get("full_name") or users[0].get("username")) if users else f"Usuario IG #{sender_uid[-4:]}")
                    async with get_connection() as conn:
                        await process_meta_incoming_message(
                            conn,
                            business_id=business_id,
                            platform="instagram",
                            sender_id=thread_id,
                            sender_name=sender_name,
                            message_text=msg_text,
                            is_simulation=False,
                            external_message_id=item_id,
                        )
        except Exception as exc:
            logger.debug("Polling IG session notice (%s): %s", business_id, exc)
        return

    # B) Polling automático con el Token de Página capturado en el botón "Vincular Facebook / Vincular Instagram"
    if token.startswith("EAA"):
        try:
            params: dict[str, str] = {
                "fields": "id,updated_time,participants,messages.limit(2){id,message,from,created_time}",
                "limit": "10",
                "access_token": token,
            }
            if platform == "instagram":
                params["platform"] = "instagram"
            target_node = (parent_page_id or page_or_ig_id or "me").strip() or "me"
            async with httpx.AsyncClient(timeout=12.0) as client:
                res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/conversations",
                    params=params,
                )
                if res.status_code >= 400 and target_node != "me":
                    res = await client.get(
                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{target_node}/conversations",
                        params=params,
                    )
                if res.status_code >= 400 or not res.content:
                    return
                convs = (res.json() or {}).get("data") or []
                clean_acc_name = account_name.strip().lower().lstrip("@")
                own_ids = {x for x in (page_or_ig_id.strip(), parent_page_id.strip()) if x}
                for conv in convs:
                    if not isinstance(conv, dict):
                        continue
                    msgs = ((conv.get("messages") or {}).get("data")) or []
                    if not msgs or not isinstance(msgs[0], dict):
                        continue
                    latest = msgs[0]
                    mid = str(latest.get("id") or "").strip()
                    text = str(latest.get("message") or "").strip()
                    from_obj = latest.get("from") if isinstance(latest.get("from"), dict) else {}
                    sender_id = str(from_obj.get("id") or "").strip()
                    sender_name = str(from_obj.get("name") or from_obj.get("username") or "").strip()
                    if not mid or not text or not sender_id:
                        continue
                    # Ignorar si el último mensaje fue enviado por la propia Página/Negocio
                    if sender_id in own_ids or (clean_acc_name and sender_name.lower().lstrip("@") == clean_acc_name):
                        continue
                    dedup_key = f"{platform}:{business_id}:{mid}"
                    if dedup_key in _processed_social_msg_ids:
                        continue
                    # Ignorar mensajes antiguos (> 15 minutos) para no responder historiales viejos al vincular
                    created_str = str(latest.get("created_time") or "").strip()
                    if created_str:
                        try:
                            iso_str = re.sub(r"([+-]\d{2})(\d{2})$", r"\1:\2", created_str)
                            msg_dt = datetime.fromisoformat(iso_str)
                            if (datetime.now(timezone.utc) - msg_dt.astimezone(timezone.utc)).total_seconds() > 900:
                                _processed_social_msg_ids.add(dedup_key)
                                continue
                        except Exception:
                            pass

                    async with get_connection() as conn:
                        await process_meta_incoming_message(
                            conn,
                            business_id=business_id,
                            platform=platform,
                            sender_id=sender_id,
                            sender_name=sender_name or f"Cliente {_platform_label(platform)}",
                            message_text=text,
                            is_simulation=False,
                            external_message_id=mid,
                            instance_or_page_id=page_or_ig_id,
                        )
        except Exception as exc:
            logger.debug("Polling Facebook/IG conversations notice (%s): %s", business_id, exc)


async def _social_direct_polling_loop() -> None:
    """Worker en segundo plano en Render: revisa cada 3 segundos las bandejas conectadas."""
    await asyncio.sleep(1.5)
    while True:
        try:
            await ensure_meta_social_schema()
            channels: list[tuple[str, str, str, str, str, str]] = []
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT business_id::text, platform, account_name, page_or_ig_id, parent_page_id, access_token
                           FROM public.business_meta_channels
                           WHERE enabled = true AND platform IN ('instagram', 'facebook')"""
                    )
                    channels = [
                        (
                            str(r[0]),
                            str(r[1]),
                            str(r[2] or ""),
                            str(r[3] or ""),
                            str(r[4] or ""),
                            str(r[5] or ""),
                        )
                        for r in cur.fetchall()
                    ]
            for bid, plat, acc, pid, ppid, tok in channels:
                await _poll_single_social_channel(bid, plat, acc, pid, ppid, tok)
            if len(_processed_social_msg_ids) > 5000:
                _processed_social_msg_ids.clear()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Social polling cycle notice: %s", exc)
        await asyncio.sleep(3.0)


async def start_social_direct_polling() -> None:
    global _social_polling_task
    if _social_polling_task is None or _social_polling_task.done():
        _social_polling_task = asyncio.create_task(_social_direct_polling_loop())


async def stop_social_direct_polling() -> None:
    global _social_polling_task
    if _social_polling_task is not None and not _social_polling_task.done():
        _social_polling_task.cancel()
        try:
            await _social_polling_task
        except asyncio.CancelledError:
            pass
    _social_polling_task = None


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
            "channel_status": "disconnected",
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
    last_ev_str = last_event_at.isoformat() if hasattr(last_event_at, "isoformat") else (str(last_event_at) if last_event_at else None)
    conn_at_str = connected_at.isoformat() if hasattr(connected_at, "isoformat") else (str(connected_at) if connected_at else None)
    resolved_status = str(status or ("connected" if enabled else "disconnected"))
    return {
        "platform": platform,
        "label": _platform_label(platform),
        "enabled": bool(enabled),
        "status": resolved_status,
        "channel_status": resolved_status,
        "configured": configured,
        "account_name": acc_str,
        "page_or_ig_id": pid_str,
        "has_access_token": bool(token_str),
        "token_hint": f"••••{token_str[-4:]}" if len(token_str) >= 4 else "",
        "verify_token": vtok_str,
        "webhook_url": webhook_url,
        "last_error": str(last_error) if last_error else None,
        "last_event_at": last_ev_str,
        "connected_at": conn_at_str,
    }


# ---------------------------------------------------------------------------
# FLUJO 1-CLIC DE VINCULACIÓN EN POPUP (OAUTH + SESIÓN CLOUD DIRECTA)
# ---------------------------------------------------------------------------

def _meta_state_signature(payload: str) -> str:
    secret = (
        os.getenv("META_APP_SECRET", META_APP_SECRET).strip()
        or get_settings().galaxy_jwt_secret
        or "calyrisia-meta-oauth-state-signing-key-2026"
    )
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
        if age < -60 or age > 900:
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
        if config_id and not minimal_scopes:
            params["config_id"] = config_id
            params["override_default_response_type"] = "true"
        else:
            params["scope"] = "pages_show_list,pages_messaging,pages_manage_metadata,instagram_basic,instagram_manage_messages"
    elif platform == "facebook":
        facebook_config_id = os.getenv("META_FACEBOOK_CONFIG_ID", "").strip() or META_FACEBOOK_CONFIG_ID
        if facebook_config_id and not minimal_scopes:
            params["config_id"] = facebook_config_id
            params["override_default_response_type"] = "true"
        else:
            params["scope"] = "public_profile,pages_show_list" if minimal_scopes else "pages_show_list,pages_messaging,pages_manage_metadata"
    else:
        raise HTTPException(status_code=422, detail="Canal Meta no válido para OAuth.")

    if force_login:
        params["auth_type"] = "reauthenticate"
    return f"https://www.facebook.com/{META_GRAPH_API_VERSION}/dialog/oauth?{urllib.parse.urlencode(params)}"


@router.get("/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
@router.get("/channels/meta/connect", response_model=MetaOAuthUrlResponse)
@router.get("/auth/meta/login", response_model=MetaOAuthUrlResponse)
@router.get("/dashboard/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    force_login: bool = Query(default=False),
    tenant_ctx: MultitenantContext = Depends(get_multitenant_guard),
) -> dict[str, Any]:
    """Genera la URL de vinculación en 1 clic desde el botón del Dashboard."""
    platform = platform.lower().strip()
    if platform not in ("instagram", "facebook"):
        platform = "instagram"
    business_id = str(tenant_ctx.tenant_id)
    auth_url = _build_facebook_dialog_oauth_url(
        business_id=business_id,
        platform=platform,
        force_login=force_login,
    )
    return {
        "success": True,
        "auth_url": auth_url,
        "platform": platform,
        "tenant_id": business_id,
    }


async def _subscribe_meta_webhook(
    *, platform: str, page_id: str, access_token: str
) -> tuple[bool, str | None]:
    if not page_id or not access_token:
        return False, "No se recibió el ID de la Página ni su token de acceso."
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{page_id}/subscribed_apps"
    last_err = None
    for fields in ("messages,messaging_postbacks", "messages"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    url,
                    params={"subscribed_fields": fields, "access_token": access_token},
                )
            data = response.json() if response.content else {}
            if response.status_code < 400 and isinstance(data, dict) and str(data.get("success", "")).lower() == "true":
                return True, None
            err = ((data.get("error") or {}).get("message") if isinstance(data, dict) else None)
            last_err = str(err or response.text)[:500]
        except Exception as exc:
            last_err = str(exc)[:500]
    return False, last_err


async def _activate_meta_account_in_db(
    *,
    business_id: str,
    platform: str,
    account_name: str,
    page_or_ig_id: str,
    access_token: str,
    subscribe_page_id: str | None = None,
) -> dict[str, Any]:
    await ensure_meta_social_schema()
    vtoken = os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip() or _default_verify_token(business_id)
    target_page_id = (subscribe_page_id or (page_or_ig_id if platform == "facebook" else "")).strip()
    subscribed_ok = False
    if access_token.startswith("EAA") and target_page_id:
        subscribed_ok, _ = await _subscribe_meta_webhook(
            platform=platform,
            page_id=target_page_id,
            access_token=access_token,
        )

    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.business_meta_channels
                   (business_id, platform, enabled, channel_status, account_name, page_or_ig_id,
                    parent_page_id, access_token, verify_token, last_error, connected_at, updated_at)
                   VALUES (%s::uuid, %s, true, 'connected', %s, %s, %s, %s, %s, NULL, now(), now())
                   ON CONFLICT (business_id, platform) DO UPDATE SET
                     enabled = true,
                     channel_status = 'connected',
                     account_name = EXCLUDED.account_name,
                     page_or_ig_id = EXCLUDED.page_or_ig_id,
                     parent_page_id = EXCLUDED.parent_page_id,
                     access_token = EXCLUDED.access_token,
                     verify_token = EXCLUDED.verify_token,
                     last_error = NULL,
                     connected_at = COALESCE(business_meta_channels.connected_at, now()),
                     updated_at = now()""",
                (
                    business_id,
                    platform,
                    account_name[:160],
                    page_or_ig_id[:120],
                    target_page_id[:120],
                    access_token,
                    vtoken,
                ),
            )
        conn.commit()
    await start_social_direct_polling()
    return {"ready": True, "subscribed_via_api": subscribed_ok, "channel_status": "connected", "last_error": None}


@router.post("/auth/meta/select-account")
async def select_meta_oauth_account(payload: MetaOAuthSelectAccountRequest) -> dict[str, Any]:
    await ensure_meta_social_schema()
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 900:
        _pending_meta_oauth_sessions.pop(payload.session_key, None)
        raise HTTPException(status_code=400, detail="La sesión de vinculación expiró. Cierra esta ventana y vuelve a pulsar Vincular.")

    platform = payload.platform.lower().strip()
    candidates = session_info.get("candidates") or []
    candidate = next(
        (
            item
            for item in candidates
            if isinstance(item, dict) and str(item.get("id") or "") == payload.page_or_ig_id
        ),
        None,
    )
    if not candidate:
        raise HTTPException(status_code=400, detail="La cuenta no pertenece a la sesión de autorización.")

    account_name = str(candidate.get("name") or payload.account_name or "Cuenta Conectada").strip()[:160]
    page_or_ig_id = str(candidate.get("id") or "").strip()[:120]
    page_id = str(candidate.get("page_id") or (page_or_ig_id if platform == "facebook" else "")).strip()[:120]
    access_token = str(candidate.get("access_token") or "").strip()
    business_id = str(session_info["business_id"])

    result = await _activate_meta_account_in_db(
        business_id=business_id,
        platform=platform,
        account_name=account_name,
        page_or_ig_id=page_or_ig_id,
        access_token=access_token,
        subscribe_page_id=page_id,
    )

    try:
        if platform == "instagram" and page_id and candidate.get("page_name"):
            await _activate_meta_account_in_db(
                business_id=business_id,
                platform="facebook",
                account_name=str(candidate.get("page_name"))[:160],
                page_or_ig_id=page_id,
                access_token=access_token,
                subscribe_page_id=page_id,
            )
        elif platform == "facebook" and candidate.get("ig_id"):
            await _activate_meta_account_in_db(
                business_id=business_id,
                platform="instagram",
                account_name=str(candidate.get("ig_name") or f"@{account_name.replace(' ', '_').lower()}")[:160],
                page_or_ig_id=str(candidate["ig_id"])[:120],
                access_token=access_token,
                subscribe_page_id=page_id,
            )
    except Exception:
        pass

    _pending_meta_oauth_sessions.pop(payload.session_key, None)
    return {
        "success": True,
        "ready": True,
        "platform": platform,
        "account_name": account_name,
        "channel_status": result["channel_status"],
        "last_error": None,
        "message": f"✓ {_platform_label(platform)} ({account_name}) vinculado y respondiendo automáticamente con IA.",
    }


@router.post("/auth/meta/popup-direct-login")
async def popup_direct_login_account(payload: MetaPopupDirectLoginRequest) -> dict[str, Any]:
    """Permite al usuario iniciar sesión directamente en el popup cuando su cuenta no usa páginas de Meta."""
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 900:
        raise HTTPException(status_code=400, detail="La ventana expiró. Ciérrala y vuelve a pulsar Vincular.")

    business_id = str(session_info["business_id"])
    platform = payload.platform.lower().strip()
    username = payload.username.strip()
    password = payload.password.strip()

    if platform == "instagram" and not username.startswith("@"):
        username = f"@{username}"

    login_res = await _login_instagram_direct_session(username, password)
    if login_res.get("ok"):
        token_payload = str(login_res["token_payload"])
        asset_id = str(login_res.get("ds_user_id") or f"{platform}_{business_id[:8]}")
        account_name = str(login_res.get("username") or username)
    else:
        token_payload = password if password.startswith("EAA") else f"ig_session:{json.dumps({'username': username, 'sessionid': password})}"
        asset_id = f"{platform}_{business_id[:8]}"
        account_name = username

    await _activate_meta_account_in_db(
        business_id=business_id,
        platform=platform,
        account_name=account_name,
        page_or_ig_id=asset_id,
        access_token=token_payload,
    )
    _pending_meta_oauth_sessions.pop(payload.session_key, None)
    return {
        "success": True,
        "ready": True,
        "platform": platform,
        "account_name": account_name,
        "message": f"✓ {_platform_label(platform)} ({account_name}) conectado y respondiendo con IA.",
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
        _build_facebook_dialog_oauth_url(business_id=business_id, platform=requested_platform, force_login=False, minimal_scopes=True)
        if business_id
        else "#"
    )

    app_id = os.getenv("META_APP_ID", "").strip() or META_APP_ID
    app_secret = os.getenv("META_APP_SECRET", "").strip() or META_APP_SECRET
    redirect_uri = os.getenv("META_REDIRECT_URI", "").strip() or META_REDIRECT_URI

    user_access_token = ""
    me_name = "Usuario Conectado"
    me_id = ""
    discovered_pages: list[dict[str, str]] = []
    discovered_ig_accounts: list[dict[str, str]] = []
    error_detail = ""
    page_fields = "id,name,access_token,tasks,instagram_business_account{id,username,name},connected_instagram_account{id,username,name}"

    if code and business_id and parsed_state and not error:
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
                token_data = token_res.json() if token_res.content else {}
                user_access_token = str(token_data.get("access_token") or "").strip()
                if not user_access_token:
                    error_detail = str((token_data.get("error") or {}).get("message") or "")
                else:
                    long_res = await client.get(
                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/oauth/access_token",
                        params={
                            "grant_type": "fb_exchange_token",
                            "client_id": app_id,
                            "client_secret": app_secret,
                            "fb_exchange_token": user_access_token,
                        },
                    )
                    if long_res.status_code < 400 and long_res.content:
                        long_data = long_res.json()
                        user_access_token = str(long_data.get("access_token") or user_access_token).strip()

                    me_res = await client.get(
                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me",
                        params={"fields": "id,name", "access_token": user_access_token},
                    )
                    me_json = me_res.json() if me_res.status_code < 400 and me_res.content else {}
                    me_id = str(me_json.get("id") or "").strip()
                    me_name = str(me_json.get("name") or "Cuenta Autorizada").strip()

                    pages_res = await client.get(
                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/accounts",
                        params={"fields": page_fields, "limit": "100", "access_token": user_access_token},
                    )
                    pages_json = pages_res.json() if pages_res.content else {}
                    raw_pages = list(pages_json.get("data") or []) if pages_res.status_code < 400 and isinstance(pages_json, dict) else []

                    try:
                        biz_res = await client.get(
                            f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/businesses",
                            params={
                                "fields": f"id,name,owned_pages{{{page_fields}}},client_pages{{{page_fields}}}",
                                "access_token": user_access_token,
                            },
                        )
                        if biz_res.status_code < 400 and biz_res.content:
                            for b_item in (biz_res.json().get("data") or []):
                                for p_item in ((b_item.get("owned_pages") or {}).get("data") or []):
                                    raw_pages.append(p_item)
                                for p_item in ((b_item.get("client_pages") or {}).get("data") or []):
                                    raw_pages.append(p_item)
                    except Exception:
                        pass

                    if not raw_pages and app_id and app_secret:
                        try:
                            dbg_res = await client.get(
                                f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/debug_token",
                                params={"input_token": user_access_token, "access_token": f"{app_id}|{app_secret}"},
                            )
                            if dbg_res.status_code < 400 and dbg_res.content:
                                dbg_data = (dbg_res.json() or {}).get("data") or {}
                                target_ids: list[str] = []
                                for gs in (dbg_data.get("granular_scopes") or []):
                                    if isinstance(gs, dict):
                                        for tid in (gs.get("target_ids") or []):
                                            tid_str = str(tid).strip()
                                            if tid_str and tid_str not in target_ids:
                                                target_ids.append(tid_str)
                                for tid_str in target_ids[:20]:
                                    p_res = await client.get(
                                        f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{tid_str}",
                                        params={"fields": page_fields, "access_token": user_access_token},
                                    )
                                    if p_res.status_code < 400 and p_res.content:
                                        p_obj = p_res.json()
                                        if isinstance(p_obj, dict) and p_obj.get("id") and p_obj.get("access_token"):
                                            raw_pages.append(p_obj)
                        except Exception:
                            pass

                    seen_page_ids: set[str] = set()
                    seen_ig_ids: set[str] = set()
                    for page in raw_pages:
                        if not isinstance(page, dict):
                            continue
                        page_id = str(page.get("id") or "").strip()
                        page_name = str(page.get("name") or "Página de Facebook").strip()[:160]
                        page_token = str(page.get("access_token") or "").strip()

                        ig_obj = page.get("instagram_business_account") or page.get("connected_instagram_account") or {}
                        ig_id = ""
                        ig_handle = ""
                        if isinstance(ig_obj, dict):
                            ig_id = str(ig_obj.get("id") or "").strip()
                            ig_user = str(ig_obj.get("username") or ig_obj.get("name") or "").strip()
                            if ig_id:
                                ig_handle = f"@{ig_user.lstrip('@')}" if ig_user else f"@{page_name.replace(' ', '_').lower()}"

                        if page_id and page_id not in seen_page_ids and page_token:
                            seen_page_ids.add(page_id)
                            discovered_pages.append(
                                {
                                    "id": page_id,
                                    "name": page_name,
                                    "page_id": page_id,
                                    "access_token": page_token,
                                    "ig_id": ig_id,
                                    "ig_name": ig_handle,
                                }
                            )
                        if ig_id and page_id and page_token and ig_id not in seen_ig_ids:
                            seen_ig_ids.add(ig_id)
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
            logger.exception("Error procesando OAuth callback: %s", exc)
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
                account_name=str(only.get("name") or "Cuenta Conectada")[:160],
                page_or_ig_id=str(only.get("id") or "")[:120],
                access_token=str(only.get("access_token") or ""),
                subscribe_page_id=str(only.get("page_id") or only.get("id") or "")[:120],
            )
            if requested_platform == "instagram" and only.get("page_id") and only.get("page_name"):
                await _activate_meta_account_in_db(
                    business_id=business_id,
                    platform="facebook",
                    account_name=str(only.get("page_name"))[:160],
                    page_or_ig_id=str(only.get("page_id"))[:120],
                    access_token=str(only.get("access_token") or ""),
                    subscribe_page_id=str(only.get("page_id"))[:120],
                )
            elif requested_platform == "facebook" and only.get("ig_id"):
                await _activate_meta_account_in_db(
                    business_id=business_id,
                    platform="instagram",
                    account_name=str(only.get("ig_name") or "@instagram")[:160],
                    page_or_ig_id=str(only.get("ig_id"))[:120],
                    access_token=str(only.get("access_token") or ""),
                    subscribe_page_id=str(only.get("page_id") or only.get("id"))[:120],
                )
            auto_activated_info = {
                "ready": auto_res["ready"],
                "account_name": str(only.get("name") or "Cuenta Conectada"),
                "message": f"✓ {_platform_label(requested_platform)} ({only.get('name')}) vinculado automáticamente en 1 clic.",
            }
        except Exception as _auto_exc:
            logger.warning("Auto-activation failed: %s", _auto_exc)

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
        if time.time() - float(old_session.get("created_at", 0)) > 900:
            _pending_meta_oauth_sessions.pop(old_key, None)

    platform_title = "Instagram Direct" if requested_platform == "instagram" else "Facebook Messenger"
    accent_gradient = (
        "linear-gradient(135deg,#f43f5e,#a855f7)"
        if requested_platform == "instagram"
        else "linear-gradient(135deg,#3b82f6,#1d4ed8)"
    )
    safe_me_name = html.escape(me_name)
    public_candidates = [
        {
            "id": item.get("id", ""),
            "name": item.get("name", ""),
            "page_name": item.get("page_name", ""),
            "page_id": item.get("page_id", ""),
        }
        for item in candidates
    ]
    candidates_json = json.dumps(public_candidates)

    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Vincular {platform_title} · CALYRISIA</title>
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
  <h2>Conectar cuenta con el Cerebro IA</h2>
  <p class="sub">
    Sesión: <strong style="color:#e2e8f0;">{safe_me_name}</strong>.
    Selecciona tu cuenta o inicia sesión directamente para que la IA responda sola 24/7:
  </p>

  <div id="accounts-list"></div>
  <div id="status-msg" class="status-msg"></div>

  <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin-top:18px;padding-top:14px;border-top:1px solid rgba(148,163,184,0.14);">
    <a href="{switch_account_url}" class="btn-secondary">Cambiar de cuenta</a>
    <a href="{rerequest_url}" class="btn-secondary">Elegir páginas</a>
  </div>
</div>

<script>
const SESSION_KEY = {json.dumps(session_key)};
const PLATFORM = {json.dumps(requested_platform)};
const CANDIDATES = {candidates_json};
const ERROR_DETAIL = {json.dumps(error_detail)};

const listEl = document.getElementById('accounts-list');
const statusEl = document.getElementById('status-msg');

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function notifyParentAndClose(accountName, message) {{
  if (window.opener) {{
    const targetOrigin = window.location.origin || '*';
    window.opener.postMessage({{
      type: 'META_CONNECTED', status: 'ok', platform: PLATFORM,
      account_name: accountName, message: message || 'Cuenta conectada y respondiendo con IA.'
    }}, targetOrigin);
  }}
  setTimeout(() => window.close(), 650);
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
    statusEl.style.color = '#34d399';
    statusEl.textContent = data.message || 'Cuenta vinculada con éxito.';
    notifyParentAndClose(data.account_name || name, data.message);
  }} catch (err) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = err.message;
  }}
}}
async function directPopupLogin() {{
  const u = (document.getElementById('direct-user')?.value || '').trim();
  const p = (document.getElementById('direct-pass')?.value || '').trim();
  if (!u || !p) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = 'Ingresa tu usuario y contraseña para vincular la cuenta.';
    return;
  }}
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Conectando cuenta directamente con el Cerebro IA...';
  try {{
    const res = await fetch('/api/v1/auth/meta/popup-direct-login', {{
      method: 'POST', headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ session_key: SESSION_KEY, platform: PLATFORM, username: u, password: p }})
    }});
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || 'No se pudo conectar la cuenta.');
    statusEl.style.color = '#34d399';
    statusEl.textContent = data.message;
    notifyParentAndClose(data.account_name || u, data.message);
  }} catch (err) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = err.message;
  }}
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
  listEl.innerHTML = `<div style="padding:14px;border-radius:14px;background:rgba(255,255,255,0.03);border:1px solid rgba(148,163,184,0.2);">
    <p style="margin:0 0 10px;font-size:12.5px;color:#cbd5e1;">Inicia sesión directamente con tu cuenta de {platform_title} para activar las respuestas automáticas 24/7:</p>
    <input id="direct-user" class="input-box" type="text" placeholder="Usuario o nombre de página (ej. @tuzonagamerdigital)">
    <input id="direct-pass" class="input-box" type="password" placeholder="Contraseña o Token de acceso">
    <button type="button" class="btn-primary" style="width:100%;padding:11px;" onclick="directPopupLogin()">Conectar y activar IA</button>
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
    access_token = (payload.access_token or payload.password_or_session or "").strip()[:2000]
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
                    "WhatsApp Business"
                    if platform == "whatsapp"
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

    await start_social_direct_polling()
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
                if platform in ("instagram", "facebook") and access_token.startswith("EAA"):
                    page_id = parent_page_id or (account_id if platform == "facebook" else "")
                    if page_id:
                        await _subscribe_meta_webhook(platform=platform, page_id=page_id, access_token=access_token)
            cur.execute(
                """UPDATE public.business_meta_channels
                   SET enabled = %s, channel_status = %s, last_error = NULL, updated_at = now()
                   WHERE business_id = %s::uuid AND platform = %s""",
                (enabled, status, business_id, platform),
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
    message = (
        f"{_platform_label(platform)} activado y respondiendo con IA."
        if enabled
        else f"{_platform_label(platform)} está en pausa."
    )
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

    if not valid and business_id and hmac.compare_digest(token_clean, _default_verify_token(business_id)):
        valid = True

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
                    if not valid and token_clean.startswith("calyrisia_meta_"):
                        cur.execute("SELECT id FROM public.businesses WHERE status = 'active' LIMIT 200")
                        for r in cur.fetchall():
                            if hmac.compare_digest(token_clean, _default_verify_token(str(r[0]))):
                                valid = True
                                break
        except Exception as exc:
            logger.warning("Could not validate Meta webhook token from the database: %s", exc)
            valid = False

    if not valid:
        raise HTTPException(status_code=403, detail="Token de verificación Meta inválido.")
    return PlainTextResponse(content=str(hub_challenge), status_code=200)


def _resolve_tenant_for_meta_event(
    conn,
    *,
    platform: str,
    page_or_ig_id: str,
    entry_id: str,
    explicit_business_id: str | None = None,
) -> str | None:
    with conn.cursor() as cur:
        if explicit_business_id:
            cur.execute(
                """SELECT business_id::text FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s
                     AND (page_or_ig_id IN (%s, %s) OR parent_page_id IN (%s, %s))
                     AND enabled = true LIMIT 1""",
                (explicit_business_id, platform, page_or_ig_id, entry_id, page_or_ig_id, entry_id),
            )
            row = cur.fetchone()
            if row:
                return str(row[0])
            cur.execute(
                """SELECT business_id::text FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s AND enabled = true LIMIT 1""",
                (explicit_business_id, platform),
            )
            row = cur.fetchone()
            return str(row[0]) if row else None

        cur.execute(
            """SELECT business_id::text FROM public.business_meta_channels
               WHERE platform = %s
                 AND (page_or_ig_id IN (%s, %s) OR parent_page_id IN (%s, %s))
                 AND enabled = true
               ORDER BY updated_at DESC LIMIT 1""",
            (platform, page_or_ig_id, entry_id, page_or_ig_id, entry_id),
        )
        row = cur.fetchone()
        if row:
            return str(row[0])

        cur.execute(
            """SELECT business_id::text, page_or_ig_id FROM public.business_meta_channels
               WHERE platform = %s AND enabled = true
               ORDER BY updated_at DESC LIMIT 2""",
            (platform,),
        )
        active_rows = cur.fetchall()
        if len(active_rows) == 1:
            return str(active_rows[0][0])

        return None


async def _process_meta_webhook_payload(body: dict[str, Any], explicit_business_id: str | None = None) -> list[dict[str, Any]]:
    await ensure_meta_social_schema()
    normalized_events = OmnichannelGatewayService.normalize_meta_webhook(body, tenant_id=explicit_business_id)
    if not normalized_events:
        return []

    processed_results: list[dict[str, Any]] = []
    async with get_connection() as conn:
        for norm_evt in normalized_events:
            platform = "facebook" if norm_evt.channel == "messenger" else norm_evt.channel
            page_or_ig_id = str(norm_evt.instance_or_page_id or "").strip()
            entry_id = str((norm_evt.metadata or {}).get("entry_id") or page_or_ig_id).strip()
            target_business_id = _resolve_tenant_for_meta_event(
                conn,
                platform=platform,
                page_or_ig_id=page_or_ig_id,
                entry_id=entry_id,
                explicit_business_id=explicit_business_id,
            )
            if not target_business_id:
                continue
            try:
                res = await process_meta_incoming_message(
                    conn,
                    business_id=target_business_id,
                    platform=platform,
                    sender_id=norm_evt.sender_id,
                    sender_name=norm_evt.sender_name,
                    message_text=norm_evt.message_text,
                    is_simulation=False,
                    external_message_id=norm_evt.external_message_id,
                    instance_or_page_id=page_or_ig_id,
                )
                processed_results.append(
                    {
                        "tenant_id": target_business_id,
                        "channel": platform,
                        "sender_id": norm_evt.sender_id,
                        "reply_text": res.get("reply_text", ""),
                        "sent_live": res.get("sent_live", False),
                    }
                )
            except Exception as exc:
                conn.rollback()
                logger.exception("Meta webhook processing failed for business %s (%s): %s", target_business_id, platform, exc)
    return processed_results


async def receive_global_meta_webhook_handler(
    request: Request,
    explicit_business_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> PlainTextResponse:
    try:
        raw_body = await request.body()
        app_secret = os.getenv("META_APP_SECRET", "").strip() or META_APP_SECRET
        signature = request.headers.get("X-Hub-Signature-256", "").strip()
        if app_secret and signature:
            expected = "sha256=" + hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                if os.getenv("META_STRICT_SIGNATURE", "false").lower() == "true":
                    raise HTTPException(status_code=401, detail="Firma de webhook Meta inválida.")
        body = json.loads(raw_body.decode("utf-8")) if raw_body else {}
        if not isinstance(body, dict):
            return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)
    except HTTPException:
        raise
    except Exception:
        return PlainTextResponse(content="EVENT_RECEIVED", status_code=200)

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