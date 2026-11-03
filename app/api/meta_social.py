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
FB_MOBILE_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
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
    account_name: str = Field(default="", max_length=160)
    username: str = Field(..., min_length=1, max_length=200)
    password: str = Field(..., min_length=1, max_length=2000)
    two_factor_code: str | None = Field(default=None, max_length=20)
    two_factor_identifier: str | None = Field(default=None, max_length=200)


async def ensure_meta_social_schema() -> None:
    """Create the multi-tenant table for Instagram Direct, Facebook Messenger and WhatsApp Cloud channels,
    and purge legacy fake connections that had empty access_token from older versions.
    """
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
                # Limpiar registros ficticios antiguos que se guardaron con access_token vacío
                try:
                    cur.execute("SAVEPOINT sp_clean_fake_meta")
                    cur.execute(
                        """DELETE FROM public.business_meta_channels
                           WHERE COALESCE(btrim(access_token), '') = ''"""
                    )
                    cur.execute("RELEASE SAVEPOINT sp_clean_fake_meta")
                except Exception:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_clean_fake_meta")
                    except Exception:
                        pass
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


def _has_real_credentials(page_or_ig_id: str, access_token: str) -> bool:
    pid = str(page_or_ig_id or "").strip()
    tok = str(access_token or "").strip()
    if not pid or not tok or len(tok) < 10:
        return False
    if pid.startswith("meta_facebook_") or pid.startswith("meta_instagram_"):
        if not tok.startswith(("EAA", "IG", "ig_session:", "fb_session:")):
            return False
    return True


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
# CLIENTES DIRECTOS DE INSTAGRAM Y FACEBOOK (100% EN LA NUBE SIN META DEV)
# ---------------------------------------------------------------------------

async def _authenticate_instagram_direct(
    username: str,
    password: str,
    two_factor_code: str | None = None,
    two_factor_identifier: str | None = None,
) -> dict[str, Any]:
    """Inicia sesión en Instagram Direct desde el servidor (soporta usuario+contraseña, 2FA, sessionid o token)."""
    clean_user = username.strip().lstrip("@")
    cred = password.strip()
    if not cred:
        return {"ok": False, "error": "Ingresa tu contraseña o sesión de Instagram."}

    # 1. Cookie sessionid directa
    if "sessionid=" in cred or (len(cred) > 20 and ("%3A" in cred or ":" in cred) and " " not in cred):
        sid = cred.split("sessionid=")[-1].split(";")[0].strip()
        ds_user_id = sid.split("%3A")[0].split(":")[0]
        return {
            "ok": True,
            "ds_user_id": ds_user_id or f"ig_{clean_user}",
            "username": f"@{clean_user}" if clean_user else "@instagram",
            "token_payload": f"ig_session:{json.dumps({'sessionid': sid, 'ds_user_id': ds_user_id, 'username': clean_user})}",
        }

    # 2. Token EAA / IG
    if cred.startswith(("EAA", "IGQ", "IGA")):
        return {
            "ok": True,
            "ds_user_id": f"ig_{clean_user}",
            "username": f"@{clean_user}" if clean_user else "@instagram",
            "token_payload": cred,
        }

    # 3. Login con Usuario y Contraseña en Instagram Web API
    try:
        async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
            await client.get(
                "https://www.instagram.com/accounts/login/",
                headers={"User-Agent": IG_MOBILE_USER_AGENT},
            )
            csrf = client.cookies.get("csrftoken") or "calyrisia_csrf_token"

            if two_factor_code and two_factor_identifier:
                tf_res = await client.post(
                    "https://www.instagram.com/api/v1/web/accounts/login/ajax/two_factor/",
                    headers={
                        "User-Agent": IG_MOBILE_USER_AGENT,
                        "X-CSRFToken": csrf,
                        "X-IG-App-ID": IG_APP_ID,
                        "X-Requested-With": "XMLHttpRequest",
                        "Referer": "https://www.instagram.com/accounts/login/two_factor",
                    },
                    data={
                        "username": clean_user,
                        "verificationCode": two_factor_code.strip(),
                        "identifier": two_factor_identifier.strip(),
                        "queryParams": "{}",
                    },
                )
                tf_data = tf_res.json() if tf_res.content else {}
                sid = client.cookies.get("sessionid") or ""
                if tf_data.get("authenticated") and sid:
                    uid = str(tf_data.get("userId") or sid.split("%3A")[0])
                    return {
                        "ok": True,
                        "ds_user_id": uid,
                        "username": f"@{clean_user}",
                        "token_payload": f"ig_session:{json.dumps({'sessionid': sid, 'ds_user_id': uid, 'csrftoken': csrf, 'username': clean_user})}",
                    }
                return {"ok": False, "error": str(tf_data.get("message") or "Código de verificación 2FA incorrecto.")}

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
            if data.get("two_factor_required"):
                tf_info = data.get("two_factor_info") or {}
                return {
                    "ok": False,
                    "requires_2fa": True,
                    "two_factor_identifier": str(tf_info.get("two_factor_identifier") or ""),
                    "error": "Ingresa el código de 6 dígitos enviado por Instagram a tu teléfono o app de autenticación.",
                }
            sid = client.cookies.get("sessionid") or ""
            if data.get("authenticated") and sid:
                uid = str(data.get("userId") or sid.split("%3A")[0])
                return {
                    "ok": True,
                    "ds_user_id": uid,
                    "username": f"@{clean_user}",
                    "token_payload": f"ig_session:{json.dumps({'sessionid': sid, 'ds_user_id': uid, 'csrftoken': csrf, 'username': clean_user})}",
                }
            if data.get("user") is False:
                return {"ok": False, "error": "El usuario de Instagram ingresado no existe."}
            if data.get("authenticated") is False:
                return {"ok": False, "error": "Contraseña de Instagram incorrecta."}
            if data.get("checkpoint_url"):
                return {
                    "ok": False,
                    "error": "Instagram solicitó confirmar el inicio de sesión en tu app móvil ('Fui yo'). Confírmalo en tu celular y vuelve a pulsar Conectar.",
                }
            return {"ok": False, "error": str(data.get("message") or "Instagram rechazó la conexión directa. Verifica tu usuario y contraseña.")}
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo conectar con Instagram: {exc}"}


async def _authenticate_facebook_direct(
    account_name: str,
    username: str,
    password_or_token: str,
) -> dict[str, Any]:
    """Autentica una Página de Facebook (ej. Tuzonagamerdigital) vía Token de Página/Usuario o Sesión Directa."""
    cred = password_or_token.strip()
    target_page_name = (account_name or username).strip()

    # 1. Si ingresó un Token EAA (de su cuenta o página), extraer automáticamente la Página (ej. Tuzonagamerdigital) y su Page Token
    if cred.startswith("EAA"):
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                ac_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me/accounts",
                    params={
                        "fields": "id,name,access_token,instagram_business_account{id,username},connected_instagram_account{id,username}",
                        "limit": "100",
                        "access_token": cred,
                    },
                )
                if ac_res.status_code < 400 and ac_res.content:
                    pages = (ac_res.json() or {}).get("data") or []
                    chosen = None
                    for p in pages:
                        if isinstance(p, dict) and target_page_name and target_page_name.lower() in str(p.get("name") or "").lower():
                            chosen = p
                            break
                    if not chosen and pages:
                        chosen = pages[0]
                    if isinstance(chosen, dict) and chosen.get("id"):
                        return {
                            "ok": True,
                            "page_id": str(chosen["id"]),
                            "page_name": str(chosen.get("name") or target_page_name),
                            "token_payload": str(chosen.get("access_token") or cred),
                            "ig_obj": chosen.get("instagram_business_account") or chosen.get("connected_instagram_account") or {},
                        }
                me_res = await client.get(
                    f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/me",
                    params={"fields": "id,name", "access_token": cred},
                )
                if me_res.status_code < 400 and me_res.content:
                    me_d = me_res.json() or {}
                    if me_d.get("id"):
                        return {
                            "ok": True,
                            "page_id": str(me_d["id"]),
                            "page_name": str(me_d.get("name") or target_page_name or "Página de Facebook"),
                            "token_payload": cred,
                            "ig_obj": {},
                        }
                err_msg = ((me_res.json() or {}).get("error") or {}).get("message") if me_res.content else "Token expirado o inválido."
                return {"ok": False, "error": f"Facebook rechazó el token: {err_msg}"}
        except Exception as exc:
            return {"ok": False, "error": f"Error verificando token de Facebook: {exc}"}

    # 2. Si ingresó cookies de sesión de Facebook (`c_user=...; xs=...`)
    if "c_user=" in cred and "xs=" in cred:
        c_user = re.search(r"c_user=([^;\s]+)", cred)
        xs = re.search(r"xs=([^;\s]+)", cred)
        if c_user and xs:
            uid = c_user.group(1)
            xs_val = xs.group(1)
            # Intentar extraer el token EAAG interno desde business.facebook.com para automatizar la página
            extracted_token = ""
            try:
                async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
                    r_bm = await client.get(
                        "https://business.facebook.com/business_locations",
                        headers={"User-Agent": FB_MOBILE_USER_AGENT},
                        cookies={"c_user": uid, "xs": xs_val},
                    )
                    m_tok = re.search(r"(EAAG[a-zA-Z0-9]+)", r_bm.text or "")
                    if m_tok:
                        extracted_token = m_tok.group(1)
            except Exception:
                pass
            if extracted_token:
                return await _authenticate_facebook_direct(target_page_name, username, extracted_token)
            return {
                "ok": True,
                "page_id": f"fb_uid_{uid}",
                "page_name": target_page_name or f"Facebook ({uid})",
                "token_payload": f"fb_session:{json.dumps({'c_user': uid, 'xs': xs_val, 'page_name': target_page_name})}",
                "ig_obj": {},
            }

    # 3. Intento de login directo en mbasic.facebook.com con correo y contraseña
    try:
        async with httpx.AsyncClient(timeout=18.0, follow_redirects=True) as client:
            init_r = await client.get(
                "https://mbasic.facebook.com/login.php",
                headers={"User-Agent": FB_MOBILE_USER_AGENT},
            )
            html_body = init_r.text or ""
            lsd_m = re.search(r'name="lsd"\s+value="([^"]+)"', html_body)
            jazoest_m = re.search(r'name="jazoest"\s+value="([^"]+)"', html_body)
            form_data = {
                "email": username.strip(),
                "pass": cred,
                "login": "Iniciar sesión",
            }
            if lsd_m:
                form_data["lsd"] = lsd_m.group(1)
            if jazoest_m:
                form_data["jazoest"] = jazoest_m.group(1)

            await client.post(
                "https://mbasic.facebook.com/login/device-based/regular/login/?refsrc=deprecated&lwv=100",
                headers={
                    "User-Agent": FB_MOBILE_USER_AGENT,
                    "Referer": "https://mbasic.facebook.com/login.php",
                },
                data=form_data,
            )
            c_user = client.cookies.get("c_user") or ""
            xs = client.cookies.get("xs") or ""
            if c_user and xs:
                return await _authenticate_facebook_direct(
                    target_page_name,
                    username,
                    f"c_user={c_user}; xs={xs}",
                )
            return {
                "ok": False,
                "error": (
                    "Facebook solicitó confirmación de seguridad o bloqueó el inicio con contraseña desde la nube. "
                    "Usa la pestaña 'Conectar con Token de Página (1 Clic sin verificar empresa)' justo arriba."
                ),
            }
    except Exception as exc:
        return {"ok": False, "error": f"No se pudo iniciar sesión directa en Facebook: {exc}"}


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


async def _send_facebook_session_reply(session_data: dict[str, Any], thread_fbid: str, text: str) -> tuple[bool, str | None]:
    c_user = str(session_data.get("c_user") or "").strip()
    xs = str(session_data.get("xs") or "").strip()
    if not c_user or not xs or not thread_fbid or not text:
        return False, "Falta sesión de Facebook o ID de conversación."
    try:
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            conv_page = await client.get(
                f"https://mbasic.facebook.com/messages/read/?fbid={urllib.parse.quote(thread_fbid)}",
                headers={"User-Agent": FB_MOBILE_USER_AGENT},
                cookies={"c_user": c_user, "xs": xs},
            )
            html_body = conv_page.text or ""
            fb_dtsg_m = re.search(r'name="fb_dtsg"\s+value="([^"]+)"', html_body)
            jazoest_m = re.search(r'name="jazoest"\s+value="([^"]+)"', html_body)
            if not fb_dtsg_m:
                return False, "No se pudo obtener token CSRF de mbasic.facebook.com"
            data = {
                "fb_dtsg": fb_dtsg_m.group(1),
                "body": text[:1900],
                "send": "Enviar",
                f"ids[{thread_fbid}]": thread_fbid,
            }
            if jazoest_m:
                data["jazoest"] = jazoest_m.group(1)
            send_res = await client.post(
                "https://mbasic.facebook.com/messages/send/?icm=1",
                headers={"User-Agent": FB_MOBILE_USER_AGENT},
                cookies={"c_user": c_user, "xs": xs},
                data=data,
            )
            return (send_res.status_code < 400), None
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
    token = (access_token or "").strip()
    if not token or not recipient_id or not message_text:
        return False, "Falta token, destinatario o contenido para enviar el mensaje."

    if token.startswith("ig_session:"):
        try:
            sess = json.loads(token[len("ig_session:"):])
            return await _send_instagram_direct_session_reply(sess, recipient_id, message_text)
        except Exception as exc:
            return False, str(exc)[:300]

    if token.startswith("fb_session:"):
        try:
            sess = json.loads(token[len("fb_session:"):])
            return await _send_facebook_session_reply(sess, recipient_id, message_text)
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
# MOTOR CLOUD POLLING 24/7 (RESPONDE AUTOMÁTICAMENTE CADA 3 SEGUNDOS)
# ---------------------------------------------------------------------------

async def _poll_single_social_channel(
    business_id: str,
    platform: str,
    account_name: str,
    page_or_ig_id: str,
    parent_page_id: str,
    access_token: str,
) -> None:
    token = (access_token or "").strip()
    if not token:
        return

    # 1. Polling directo de Instagram por sesión (`ig_session:...`)
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

    # 2. Polling automático con Token de Página (`EAA...`)
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
                    if sender_id in own_ids or (clean_acc_name and sender_name.lower().lstrip("@") == clean_acc_name):
                        continue
                    dedup_key = f"{platform}:{business_id}:{mid}"
                    if dedup_key in _processed_social_msg_ids:
                        continue
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
    configured = bool(acc_str and _has_real_credentials(pid_str, token_str))
    last_ev_str = last_event_at.isoformat() if hasattr(last_event_at, "isoformat") else (str(last_event_at) if last_event_at else None)
    conn_at_str = connected_at.isoformat() if hasattr(connected_at, "isoformat") else (str(connected_at) if connected_at else None)
    resolved_status = str(status or ("connected" if enabled else "disconnected")) if configured else "disconnected"
    return {
        "platform": platform,
        "label": _platform_label(platform),
        "enabled": bool(enabled and configured),
        "status": resolved_status,
        "channel_status": resolved_status,
        "configured": configured,
        "account_name": acc_str if configured else "",
        "page_or_ig_id": pid_str if configured else "",
        "has_access_token": bool(token_str),
        "token_hint": f"••••{token_str[-4:]}" if configured and len(token_str) >= 4 else "",
        "verify_token": vtok_str,
        "webhook_url": webhook_url,
        "last_error": str(last_error) if last_error else (
            f"La cuenta '{acc_str}' requiere iniciar sesión para autorizar el envío de mensajes. Pulsa Vincular {_platform_label(platform)}."
            if (acc_str and not configured)
            else None
        ),
        "last_event_at": last_ev_str,
        "connected_at": conn_at_str,
    }


# ---------------------------------------------------------------------------
# VENTANA EMERGENTE DE VINCULACIÓN 1-CLIC (PROPIA DE CALYRISIA · SIN META DEV)
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
        if age < -60 or age > 1800:
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


@router.get("/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
@router.get("/channels/meta/connect", response_model=MetaOAuthUrlResponse)
@router.get("/auth/meta/login", response_model=MetaOAuthUrlResponse)
@router.get("/dashboard/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    force_login: bool = Query(default=False),
    tenant_ctx: MultitenantContext = Depends(get_multitenant_guard),
) -> dict[str, Any]:
    """Devuelve la URL de la ventana emergente de vinculación directa (sin exigir verificación mercantil en Meta)."""
    platform = platform.lower().strip()
    if platform not in ("instagram", "facebook"):
        platform = "instagram"
    business_id = str(tenant_ctx.tenant_id)
    state = _build_meta_oauth_state(business_id=business_id, platform=platform)
    # También construimos la URL OAuth clásica de Facebook por si el administrador desea usarla dentro del popup
    fb_oauth_params = {
        "client_id": os.getenv("META_APP_ID", "").strip() or META_APP_ID,
        "display": "popup",
        "redirect_uri": os.getenv("META_REDIRECT_URI", "").strip() or META_REDIRECT_URI,
        "response_type": "code",
        "scope": "public_profile,pages_show_list,pages_messaging,pages_read_engagement",
        "state": state,
    }
    fb_oauth_url = f"https://www.facebook.com/{META_GRAPH_API_VERSION}/dialog/oauth?{urllib.parse.urlencode(fb_oauth_params)}"
    popup_url = f"/api/v1/auth/meta/connect-window?{urllib.parse.urlencode({'state': state, 'fb_oauth': fb_oauth_url})}"
    return {
        "success": True,
        "auth_url": popup_url,
        "platform": platform,
        "tenant_id": business_id,
    }


@router.get("/auth/meta/connect-window", response_class=HTMLResponse)
async def render_direct_connect_popup(
    state: str = Query(...),
    fb_oauth: str = Query(default=""),
) -> HTMLResponse:
    """Ventana emergente de vinculación en 1 clic de CALYRISIA (no bloqueada por verificación de empresa de Meta)."""
    parsed = _parse_and_validate_meta_oauth_state(state)
    if not parsed:
        return HTMLResponse(
            "<html><body style='background:#090d16;color:#fff;font-family:sans-serif;text-align:center;padding:40px;'>"
            "<h3>La ventana expiró. Ciérrala y vuelve a pulsar Vincular en el Dashboard.</h3></body></html>"
        )
    business_id, platform = parsed
    session_key = uuid.uuid4().hex
    _pending_meta_oauth_sessions[session_key] = {
        "business_id": business_id,
        "requested_platform": platform,
        "created_at": time.time(),
    }

    is_ig = platform == "instagram"
    title = "Instagram Direct" if is_ig else "Facebook Messenger"
    gradient = "linear-gradient(135deg,#f43f5e,#a855f7)" if is_ig else "linear-gradient(135deg,#3b82f6,#1d4ed8)"

    return HTMLResponse(
        f"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Conectar {title} · CALYRISIA</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px;
    background: radial-gradient(circle at 50% 0%, rgba(56,189,248,0.16), transparent 60%), #090d16;
    color: #f8fafc;
    font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
  }}
  .card {{
    max-width: 470px; margin: 0 auto;
    background: rgba(15, 23, 42, 0.95);
    border: 1px solid rgba(148, 163, 184, 0.22);
    border-radius: 20px; padding: 24px;
    box-shadow: 0 24px 60px rgba(0,0,0,0.55);
  }}
  .pill {{
    display: inline-block; padding: 4px 11px; border-radius: 999px;
    font-size: 11px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    background: rgba(56, 189, 248, 0.12); color: #7cecf5; border: 1px solid rgba(56, 189, 248, 0.3);
    margin-bottom: 10px;
  }}
  h2 {{ margin: 0 0 6px; font-size: 1.25rem; }}
  p.sub {{ margin: 0 0 16px; color: #94a3b8; font-size: 13px; line-height: 1.5; }}
  label {{ display: block; font-size: 12px; font-weight: 600; color: #cbd5e1; margin-bottom: 5px; }}
  .input-box {{
    width: 100%; padding: 11px 13px; border-radius: 11px;
    background: #060a12; border: 1px solid rgba(148,163,184,0.28);
    color: #fff; font-size: 13px; margin-bottom: 12px;
  }}
  .btn-primary {{
    width: 100%; border: 0; border-radius: 12px; padding: 12px 16px;
    background: {gradient}; color: #fff;
    font-weight: 700; font-size: 13.5px; cursor: pointer;
  }}
  .btn-primary:disabled {{ opacity: 0.6; cursor: wait; }}
  .status-msg {{ margin-top: 12px; font-size: 12.5px; line-height: 1.45; min-height: 20px; }}
  .helper-box {{
    margin-top: 14px; padding: 11px 13px; border-radius: 11px;
    background: rgba(56,189,248,0.06); border: 1px solid rgba(56,189,248,0.2);
    font-size: 11.5px; color: #94a3b8; line-height: 1.5;
  }}
  .helper-box a {{ color: #38bdf8; text-decoration: none; font-weight: 600; }}
</style>
</head>
<body>
<div class="card">
  <span class="pill">{title} · Conexión Directa IA</span>
  <h2>Conecta tu cuenta con CALYRISIA</h2>
  <p class="sub">
    {"Inicia sesión con tu cuenta de Instagram para que el Cerebro IA responda tus mensajes directos automáticamente 24/7:" if is_ig else "Conecta tu Página comercial (ej. Tuzonagamerdigital) para que el Cerebro IA responda Messenger automáticamente 24/7:"}
  </p>

  <div id="form-wrap">
    {"" if is_ig else '''
    <label for="page-name">Nombre de tu Página de Facebook</label>
    <input id="page-name" class="input-box" type="text" placeholder="Ej. Tuzonagamerdigital" value="Tuzonagamerdigital">
    '''}
    <label for="login-user">{"Usuario o correo de Instagram" if is_ig else "Correo / Teléfono de tu cuenta o nombre de usuario"}</label>
    <input id="login-user" class="input-box" type="text" placeholder="{"Ej. @tuzonagamerdigital" if is_ig else "Tu correo de Facebook o @tuzonagamerdigital"}">

    <label for="login-pass">{"Contraseña de Instagram (o cookie sessionid)" if is_ig else "Token de acceso de tu Página (EAA...) o Contraseña"}</label>
    <input id="login-pass" class="input-box" type="password" placeholder="{"Tu contraseña de Instagram" if is_ig else "Pega tu Token EAA... o tu contraseña"}">

    <div id="twofa-wrap" style="display:none;">
      <label for="twofa-code" style="color:#fbbf24;">Código de verificación de 6 dígitos (2FA)</label>
      <input id="twofa-code" class="input-box" type="text" inputmode="numeric" placeholder="Código de 6 dígitos recibido">
    </div>

    <button type="button" id="submit-btn" class="btn-primary" onclick="submitDirectLogin()">
      Autorizar y Activar Respuestas IA
    </button>
  </div>

  <div id="status-msg" class="status-msg"></div>

  {"" if is_ig else f'''
  <div class="helper-box">
    <strong>¿Cómo obtener el Token de tu propia Página gratis en 10 segundos (sin verificar empresa)?</strong><br>
    1. Abre <a href="https://developers.facebook.com/tools/explorer/" target="_blank" rel="noopener">Graph API Explorer de Facebook</a>.<br>
    2. En <em>User or Page</em> selecciona tu página <strong>Tuzonagamerdigital</strong>, marca <code>pages_messaging</code> y pulsa <strong>Generate Access Token</strong>.<br>
    3. Copia el código que empieza por <code>EAA...</code> y pégalo arriba. Nuestro servidor leerá y responderá tus chats cada 3 segundos sin pedir verificación de empresa.
  </div>
  '''}
</div>

<script>
const SESSION_KEY = {json.dumps(session_key)};
const PLATFORM = {json.dumps(platform)};
let twoFactorId = '';

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

async function submitDirectLogin() {{
  const pageName = (document.getElementById('page-name')?.value || '').trim();
  const u = (document.getElementById('login-user')?.value || pageName || '').trim();
  const p = (document.getElementById('login-pass')?.value || '').trim();
  const code = (document.getElementById('twofa-code')?.value || '').trim();
  const statusEl = document.getElementById('status-msg');
  const btn = document.getElementById('submit-btn');

  if (!u || !p) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = 'Completa los campos para verificar y activar tu cuenta.';
    return;
  }}

  btn.disabled = true;
  btn.textContent = 'Verificando conexión en vivo...';
  statusEl.style.color = '#38bdf8';
  statusEl.textContent = 'Validando credenciales y activando el motor IA en la nube...';

  try {{
    const res = await fetch('/api/v1/auth/meta/popup-direct-login', {{
      method: 'POST',
      headers: {{ 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        session_key: SESSION_KEY,
        platform: PLATFORM,
        account_name: pageName || u,
        username: u,
        password: p,
        two_factor_code: code || null,
        two_factor_identifier: twoFactorId || null
      }})
    }});
    const data = await res.json();
    if (data.requires_2fa) {{
      twoFactorId = data.two_factor_identifier || '';
      document.getElementById('twofa-wrap').style.display = 'block';
      document.getElementById('twofa-code').focus();
      statusEl.style.color = '#fbbf24';
      statusEl.textContent = data.message || 'Ingresa el código de 6 dígitos enviado por Instagram.';
      btn.disabled = false;
      btn.textContent = 'Verificar código y Conectar';
      return;
    }}
    if (!res.ok) throw new Error(data.detail || 'No se pudo autenticar la cuenta.');
    statusEl.style.color = '#34d399';
    statusEl.textContent = data.message || '¡Cuenta conectada y respondiendo con IA!';
    notifyParentAndClose(data.account_name || pageName || u, data.message);
  }} catch (err) {{
    statusEl.style.color = '#fda4af';
    statusEl.textContent = err.message;
    btn.disabled = false;
    btn.textContent = 'Autorizar y Activar Respuestas IA';
  }}
}}
</script>
</body>
</html>"""
    )


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


@router.post("/auth/meta/popup-direct-login")
async def popup_direct_login_account(payload: MetaPopupDirectLoginRequest) -> dict[str, Any]:
    """Autentica y verifica en vivo la cuenta de Instagram o Página de Facebook desde la ventana emergente."""
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 1800:
        raise HTTPException(status_code=400, detail="La ventana expiró. Ciérrala y vuelve a pulsar Vincular en el Dashboard.")

    business_id = str(session_info["business_id"])
    platform = payload.platform.lower().strip()
    username = payload.username.strip()
    password = payload.password.strip()
    account_name = (payload.account_name or username).strip()

    if platform == "instagram":
        auth_res = await _authenticate_instagram_direct(
            username=username,
            password=password,
            two_factor_code=payload.two_factor_code,
            two_factor_identifier=payload.two_factor_identifier,
        )
        if auth_res.get("requires_2fa"):
            return {
                "success": False,
                "requires_2fa": True,
                "two_factor_identifier": auth_res.get("two_factor_identifier"),
                "message": auth_res.get("error"),
            }
        if not auth_res.get("ok"):
            raise HTTPException(status_code=400, detail=str(auth_res.get("error") or "No se pudo autenticar Instagram."))
        token_payload = str(auth_res["token_payload"])
        asset_id = str(auth_res.get("ds_user_id") or f"ig_{business_id[:8]}")
        final_name = str(auth_res.get("username") or account_name)
        await _activate_meta_account_in_db(
            business_id=business_id,
            platform="instagram",
            account_name=final_name,
            page_or_ig_id=asset_id,
            access_token=token_payload,
        )
    else:
        auth_res = await _authenticate_facebook_direct(
            account_name=account_name,
            username=username,
            password_or_token=password,
        )
        if not auth_res.get("ok"):
            raise HTTPException(status_code=400, detail=str(auth_res.get("error") or "No se pudo autenticar Facebook."))
        page_id = str(auth_res["page_id"])
        final_name = str(auth_res["page_name"])
        token_payload = str(auth_res["token_payload"])
        await _activate_meta_account_in_db(
            business_id=business_id,
            platform="facebook",
            account_name=final_name,
            page_or_ig_id=page_id,
            access_token=token_payload,
            subscribe_page_id=page_id,
        )
        # Si la página tiene un Instagram vinculado, dejarlo activo también automáticamente
        ig_obj = auth_res.get("ig_obj")
        if isinstance(ig_obj, dict) and ig_obj.get("id"):
            ig_u = str(ig_obj.get("username") or final_name).strip()
            await _activate_meta_account_in_db(
                business_id=business_id,
                platform="instagram",
                account_name=f"@{ig_u.lstrip('@')}",
                page_or_ig_id=str(ig_obj["id"]),
                access_token=token_payload,
                subscribe_page_id=page_id,
            )

    _pending_meta_oauth_sessions.pop(payload.session_key, None)
    return {
        "success": True,
        "ready": True,
        "platform": platform,
        "account_name": final_name,
        "message": f"✓ {_platform_label(platform)} ({final_name}) verificado y respondiendo automáticamente con IA.",
    }


@router.post("/auth/meta/select-account")
async def select_meta_oauth_account(payload: MetaOAuthSelectAccountRequest) -> dict[str, Any]:
    await ensure_meta_social_schema()
    session_info = _pending_meta_oauth_sessions.get(payload.session_key)
    if not session_info or time.time() - float(session_info.get("created_at", 0)) > 1800:
        _pending_meta_oauth_sessions.pop(payload.session_key, None)
        raise HTTPException(status_code=400, detail="La sesión de vinculación expiró.")

    platform = payload.platform.lower().strip()
    candidates = session_info.get("candidates") or []
    candidate = next(
        (item for item in candidates if isinstance(item, dict) and str(item.get("id") or "") == payload.page_or_ig_id),
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
    _pending_meta_oauth_sessions.pop(payload.session_key, None)
    return {
        "success": True,
        "ready": True,
        "platform": platform,
        "account_name": account_name,
        "channel_status": result["channel_status"],
        "last_error": None,
        "message": f"✓ {_platform_label(platform)} ({account_name}) vinculado y respondiendo con IA.",
    }


async def handle_meta_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    return await render_direct_connect_popup(state=state or "", fb_oauth="")


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
                page_or_ig_id = f"id_{platform}_{business_id[:8]}"

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