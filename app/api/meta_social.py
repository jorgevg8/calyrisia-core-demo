from __future__ import annotations

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

# Credenciales de la App de Meta (configurables por entorno en Render)
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

# Caché temporal de sesiones OAuth para que el usuario elija Página/Cuenta IG en la ventana emergente
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


async def _send_meta_graph_reply(
    *,
    platform: str,
    page_or_ig_id: str,
    access_token: str,
    recipient_id: str,
    message_text: str,
    send_target_id: str | None = None,
) -> tuple[bool, str | None]:
    """Envía la respuesta generada por la IA mediante la Graph API de Meta (`/me/messages` o `/{page_id}/messages`)."""
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
    """Enruta el mensaje de Instagram Direct, Facebook Messenger o WhatsApp Cloud al canal único de IA (`BusinessBrainService`)."""
    text = str(message_text or "").strip()
    if not text:
        return {"replied": False, "reply_text": ""}

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
# META OAUTH POPUP FLOW (FACEBOOK MESSENGER + INSTAGRAM UNIFIED LOGIN)
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
            params["config_id"] = config_id
            params["override_default_response_type"] = "true"
        else:
            params["scope"] = ",".join([
                "pages_show_list",
                "pages_messaging",
                "pages_manage_metadata",
                "instagram_basic",
                "instagram_manage_messages",
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


@router.get("/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
@router.get("/channels/meta/connect", response_model=MetaOAuthUrlResponse)
@router.get("/auth/meta/login", response_model=MetaOAuthUrlResponse)
@router.get("/dashboard/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    force_login: bool = Query(default=False),
    tenant_ctx: MultitenantContext = Depends(get_multitenant_guard),
) -> dict[str, Any]:
    """Genera la URL oficial de Meta OAuth en 1 clic para vincular Facebook Messenger o Instagram Direct."""
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
    """Suscribe automáticamente la Página al webhook de mensajes (`messages,messaging_postbacks`)."""
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
        logger.warning("Meta webhook subscription notice (%s, page=%s): %s", platform, page_id, exc)
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
    await ensure_meta_social_schema()
    vtoken = os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip() or _default_verify_token(business_id)
    target_page_id = (subscribe_page_id or (page_or_ig_id if platform == "facebook" else "")).strip()
    subscribed_ok, subscription_notice = await _subscribe_meta_webhook(
        platform=platform,
        page_id=target_page_id,
        access_token=access_token,
    )
    # Dejar el canal activo siempre que contemos con page_or_ig_id y Page Access Token válidos,
    # ya que en Meta los webhooks también pueden estar suscritos a nivel de App en el panel de Meta.
    has_valid_credentials = bool(page_or_ig_id.strip() and access_token.strip())
    enabled = has_valid_credentials
    status = "connected" if has_valid_credentials else "pending_webhook"
    last_err = None if (subscribed_ok or has_valid_credentials) else subscription_notice

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
                    business_id,
                    platform,
                    enabled,
                    status,
                    account_name[:160],
                    page_or_ig_id[:120],
                    target_page_id[:120],
                    access_token,
                    vtoken,
                    last_err,
                ),
            )
        conn.commit()
    return {
        "ready": enabled,
        "subscribed_via_api": subscribed_ok,
        "channel_status": status,
        "last_error": last_err,
    }


@router.post("/auth/meta/select-account")
async def select_meta_oauth_account(payload: MetaOAuthSelectAccountRequest) -> dict[str, Any]:
    """Activa la Página de Facebook o Cuenta Comercial de Instagram seleccionada en el popup OAuth."""
    await ensure_meta_social_schema()
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 900:
        _pending_meta_oauth_sessions.pop(payload.session_key, None)
        raise HTTPException(status_code=400, detail="La sesión de vinculación expiró. Cierra esta ventana y vuelve a pulsar Conectar.")

    platform = payload.platform.lower().strip()
    requested_platform = str(session_info.get("requested_platform") or "")
    if platform != requested_platform or platform not in ("instagram", "facebook"):
        raise HTTPException(status_code=400, detail="La plataforma seleccionada no coincide con la autorización de Meta.")

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
        raise HTTPException(status_code=400, detail="La cuenta no pertenece a la sesión de autorización. Vuelve a conectar desde Meta.")

    account_name = str(candidate.get("name") or payload.account_name or "Cuenta Meta").strip()[:160]
    page_or_ig_id = str(candidate.get("id") or "").strip()[:120]
    page_id = str(candidate.get("page_id") or (page_or_ig_id if platform == "facebook" else "")).strip()[:120]
    access_token = str(candidate.get("access_token") or "").strip()
    if not page_or_ig_id or not page_id or not access_token:
        raise HTTPException(status_code=400, detail="Meta no devolvió una Página y un token válidos para esta cuenta. Verifica los permisos y vuelve a autorizar.")

    business_id = str(session_info["business_id"])
    result = await _activate_meta_account_in_db(
        business_id=business_id,
        platform=platform,
        account_name=account_name,
        page_or_ig_id=page_or_ig_id,
        access_token=access_token,
        subscribe_page_id=page_id,
    )

    # Si al vincular Instagram también tenemos la Página de Facebook padre (o viceversa) y aún no estaba vinculada,
    # dejarla lista automáticamente para ahorrarle pasos al cliente.
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
    message = f"✓ {_platform_label(platform)} ({account_name}) vinculado y activo para responder con IA."
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
                    const targetOrigin = window.location.origin || '*';
                    window.opener.postMessage({{ type: 'META_CONNECTED', status: 'error', message: 'Inicio de sesión cancelado o estado OAuth no válido' }}, targetOrigin);
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
    page_fields = "id,name,access_token,tasks,instagram_business_account{id,username,name},connected_instagram_account{id,username,name}"

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
                error_detail = str(
                    (token_data.get("error") or {}).get("message")
                    or "Falta META_APP_SECRET en el servidor o el código de autorización expiró."
                )
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
                me_name = str(me_json.get("name") or "Cuenta Meta").strip()

                # 1. Consultar páginas directas de la cuenta (/me/accounts)
                pages_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/accounts",
                    params={
                        "fields": page_fields,
                        "limit": "100",
                        "access_token": user_access_token,
                    },
                )
                pages_json = pages_res.json() if pages_res.content else {}
                raw_pages = list(pages_json.get("data") or []) if pages_res.status_code < 400 and isinstance(pages_json, dict) else []
                if pages_res.status_code >= 400:
                    error_detail = str(
                        (pages_json.get("error") or {}).get("message")
                        or "Meta no permitió listar las páginas. Revisa pages_show_list y los activos seleccionados."
                    )

                # 2. Consultar páginas en Business Manager (/me/businesses -> owned_pages / client_pages)
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

                # 3. Fallback con debug_token (granular_scopes target_ids) cuando Unified Login restringe /me/accounts
                if not raw_pages and app_id and app_secret:
                    try:
                        dbg_res = await client.get(
                            f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/debug_token",
                            params={
                                "input_token": user_access_token,
                                "access_token": f"{app_id}|{app_secret}",
                            },
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

                if not raw_pages and not error_detail:
                    error_detail = (
                        "Meta inició sesión, pero no devolvió páginas autorizadas. "
                        "Asegúrate de seleccionar al menos una Página de Facebook (y cuenta profesional de Instagram vinculada) en la ventana de permisos."
                    )

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
            # Auto-vincular también el canal hermano si está en la misma Página
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
                "account_name": str(only.get("name") or "Cuenta Meta"),
                "message": f"✓ {_platform_label(requested_platform)} ({only.get('name')}) vinculado automáticamente en 1 clic.",
            }
        except Exception as _auto_exc:
            logger.warning("Auto-activation of single Meta candidate failed: %s", _auto_exc)

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
  .status-msg {{ margin-top: 12px; font-size: 12.5px; min-height: 18px; }}
</style>
</head>
<body>
<div class="card">
  <span class="pill">{platform_title}</span>
  <h2>Selecciona la cuenta que quedará activa</h2>
  <p class="sub">
    Sesión autorizada: <strong style="color:#e2e8f0;">{safe_me_name}</strong>.
    Selecciona una cuenta devuelta por Meta para activar el canal:
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

function escapeHtml(value) {{
  return String(value ?? '').replace(/[&<>"']/g, ch => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[ch]));
}}
function notifyParentAndClose(accountName, message) {{
  if (window.opener) {{
    const targetOrigin = window.location.origin || '*';
    window.opener.postMessage({{
      type: 'META_CONNECTED', status: 'ok', platform: PLATFORM,
      account_name: accountName, message: message || 'Cuenta conectada y lista para responder con IA.'
    }}, targetOrigin);
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
    statusEl.style.color = '#34d399';
    statusEl.textContent = data.message || 'Cuenta vinculada con éxito.';
    notifyParentAndClose(data.account_name || name, data.message);
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
    Meta no devolvió cuentas autorizadas para este canal. Comprueba que elegiste tu Página de Facebook y que tu cuenta de Instagram sea Comercial/Profesional y esté vinculada a la Página; después vuelve a iniciar sesión.
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
                if platform in ("instagram", "facebook") and access_token:
                    page_id = parent_page_id or (account_id if platform == "facebook" else "")
                    if page_id:
                        await _subscribe_meta_webhook(platform=platform, page_id=page_id, access_token=access_token)
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
    """Asocia el identificador de la Página de Facebook o Cuenta de Instagram con el `tenant_id` (`business_id`)."""
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
        return str(row[0]) if row else None


async def _process_meta_webhook_payload(body: dict[str, Any], explicit_business_id: str | None = None) -> list[dict[str, Any]]:
    """Valida los eventos (`messages`, `messaging_postbacks`) de Facebook Messenger, Instagram Direct y WhatsApp Cloud,
    los normaliza en modelos Pydantic (`NormalizedOmnichannelPayload`), resuelve el `tenant_id` y responde con la IA.
    """
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