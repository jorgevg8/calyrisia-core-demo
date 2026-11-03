from __future__ import annotations

import hashlib
import hmac
import html
import base64
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
from cryptography.fernet import Fernet, InvalidToken
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
from app.meta_schemas import MetaOAuthUrlResponse, NormalizedOmnichannelPayload
from app.services.business_brain_service import BusinessBrainService
from app.services.omnichannel_gateway_service import OmnichannelGatewayService
from app.services.tenant_guard import MultitenantContext, get_multitenant_guard

logger = logging.getLogger(__name__)
router = APIRouter()

VALID_META_PLATFORMS = ("instagram", "facebook", "whatsapp")
META_GRAPH_API_VERSION = os.getenv("META_GRAPH_API_VERSION", "v26.0").strip() or "v26.0"

META_APP_ID = os.getenv("META_APP_ID", "").strip()
META_APP_SECRET = os.getenv("META_APP_SECRET", "").strip()
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

_processed_social_msg_ids: set[str] = set()


class MetaChannelConfigUpdate(BaseModel):
    account_name: str = Field(default="", max_length=160)
    page_or_ig_id: str | None = Field(default=None, max_length=120)
    access_token: str | None = Field(default=None, max_length=2000)
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
    """Create channel storage, remove legacy credential-scraping sessions and encrypt official Meta tokens."""
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
                # Older production databases may have a restrictive CHECK constraint
                # on conversations.channel that predates Meta/omnichannel support.
                # Expand it to the channels accepted by app.schemas.Channel. NOT VALID
                # avoids failing deployment because of historical rows, while PostgreSQL
                # still enforces the new rule for every INSERT/UPDATE going forward.
                try:
                    cur.execute("SAVEPOINT sp_meta_conversation_channels")
                    cur.execute(
                        "ALTER TABLE public.conversations "
                        "DROP CONSTRAINT IF EXISTS conversations_channel_check"
                    )
                    cur.execute(
                        "ALTER TABLE public.conversations "
                        "ADD CONSTRAINT conversations_channel_check "
                        "CHECK (channel IN ('whatsapp', 'webchat', 'instagram', 'facebook', "
                        "'messenger', 'telegram', 'email', 'phone', 'other')) NOT VALID"
                    )
                    cur.execute("RELEASE SAVEPOINT sp_meta_conversation_channels")
                except Exception as migration_exc:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_meta_conversation_channels")
                    except Exception:
                        pass
                    logger.warning(
                        "Could not expand conversations.channel constraint for Meta channels: %s",
                        type(migration_exc).__name__,
                    )
                cur.execute(
                    """CREATE TABLE IF NOT EXISTS public.meta_oauth_pending_sessions (
                        session_key varchar(96) PRIMARY KEY,
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        platform varchar(30) NOT NULL CHECK (platform IN ('instagram', 'facebook')),
                        candidates jsonb NOT NULL DEFAULT '[]'::jsonb,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        expires_at timestamptz NOT NULL
                    )"""
                )
                cur.execute("CREATE INDEX IF NOT EXISTS idx_meta_oauth_pending_expiry ON public.meta_oauth_pending_sessions (expires_at)")
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
                           WHERE COALESCE(btrim(access_token), '') = ''
                              OR access_token LIKE 'ig_session:%'
                              OR access_token LIKE 'fb_session:%'"""
                    )
                    cur.execute("DELETE FROM public.meta_oauth_pending_sessions WHERE expires_at < now()")
                    # Migrate legacy official page tokens to encrypted-at-rest storage.
                    cur.execute(
                        "SELECT business_id::text, platform, access_token FROM public.business_meta_channels "
                        "WHERE access_token LIKE 'EAA%'"
                    )
                    for legacy_business_id, legacy_platform, legacy_token in cur.fetchall():
                        try:
                            cur.execute(
                                "UPDATE public.business_meta_channels SET access_token = %s "
                                "WHERE business_id = %s::uuid AND platform = %s",
                                (_encrypt_meta_token(str(legacy_token)), str(legacy_business_id), str(legacy_platform)),
                            )
                        except Exception as migrate_exc:
                            logger.warning("Could not encrypt legacy Meta token for tenant %s: %s", legacy_business_id, type(migrate_exc).__name__)
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


def _meta_token_cipher() -> Fernet:
    # A dedicated key is preferred; otherwise derive a key from an existing server secret.
    secret = (
        os.getenv("META_TOKEN_ENCRYPTION_KEY", "").strip()
        or os.getenv("GALAXY_JWT_SECRET", "").strip()
        or os.getenv("META_APP_SECRET", "").strip()
    )
    if len(secret) < 32:
        raise RuntimeError("Configura META_TOKEN_ENCRYPTION_KEY (o un GALAXY_JWT_SECRET de 32+ caracteres) para cifrar tokens Meta.")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _encrypt_meta_token(token: str) -> str:
    clean = str(token or "").strip()
    if not clean:
        return ""
    if clean.startswith("enc:v1:"):
        return clean
    return "enc:v1:" + _meta_token_cipher().encrypt(clean.encode("utf-8")).decode("ascii")


def _decrypt_meta_token(token: str) -> str:
    clean = str(token or "").strip()
    if not clean.startswith("enc:v1:"):
        return clean
    try:
        return _meta_token_cipher().decrypt(clean[7:].encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, RuntimeError) as exc:
        raise RuntimeError("No se pudo descifrar el token Meta. Comprueba que META_TOKEN_ENCRYPTION_KEY no haya cambiado.") from exc


def _platform_label(platform: str) -> str:
    if platform == "instagram":
        return "Instagram Direct"
    if platform == "whatsapp":
        return "WhatsApp Cloud"
    return "Facebook Messenger"


def _has_real_credentials(page_or_ig_id: str, access_token: str) -> bool:
    pid = str(page_or_ig_id or "").strip()
    try:
        tok = _decrypt_meta_token(str(access_token or "").strip())
    except RuntimeError:
        return False
    if not pid or not tok or len(tok) < 20:
        return False
    # CALYRISIA only accepts official Meta Graph Page/User access tokens here.
    return tok.startswith("EAA") and not pid.startswith(("meta_facebook_", "meta_instagram_", "id_facebook_", "id_instagram_"))


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
    token = (access_token or "").strip()
    asset_id = (page_or_ig_id or send_target_id or "").strip()
    if platform not in ("instagram", "facebook", "whatsapp"):
        return False, "Canal Meta no válido."
    if not token or not asset_id or not recipient_id or not message_text:
        return False, "Falta token oficial, cuenta o destinatario para enviar el mensaje."

    if platform == "whatsapp":
        url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{asset_id}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": recipient_id,
            "type": "text",
            "text": {"preview_url": False, "body": message_text[:4000]},
        }
    else:
        # Messenger uses the Page ID; Instagram Messaging uses the professional IG ID.
        url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{asset_id}/messages"
        payload = {
            "recipient": {"id": recipient_id},
            "messaging_type": "RESPONSE",
            "message": {"text": message_text[:1900]},
        }
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(url, params={"access_token": token}, json=payload)
        if resp.status_code >= 400:
            try:
                body = resp.json()
                err_obj = body.get("error") if isinstance(body, dict) else {}
                err = str((err_obj or {}).get("message") or resp.text[:500])
            except Exception:
                err = resp.text[:500]
            logger.warning("Meta Graph send error (%s, asset=%s, status=%s): %s", platform, asset_id, resp.status_code, err)
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
                access_token=_decrypt_meta_token(str(ch_row[1] or "")),
                recipient_id=sender_id,
                message_text=reply_text,
                send_target_id=str(ch_row[0] or ""),
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
    encrypted_token_str = str(access_token or "").strip()
    decrypt_error = None
    try:
        token_str = _decrypt_meta_token(encrypted_token_str)
    except RuntimeError as exc:
        token_str = ""
        decrypt_error = str(exc)
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
        "last_error": str(last_error or decrypt_error) if (last_error or decrypt_error) else (
            f"La cuenta '{acc_str}' requiere iniciar sesión para autorizar el envío de mensajes. Pulsa Vincular {_platform_label(platform)}."
            if (acc_str and not configured)
            else None
        ),
        "last_event_at": last_ev_str,
        "connected_at": conn_at_str,
    }


# ---------------------------------------------------------------------------
# OFFICIAL META OAUTH (FACEBOOK LOGIN + PAGE ASSET SELECTION)
# ---------------------------------------------------------------------------

def _meta_state_signature(payload: str) -> str:
    secret = (
        os.getenv("META_OAUTH_STATE_SECRET", "").strip()
        or os.getenv("GALAXY_JWT_SECRET", "").strip()
        or META_APP_SECRET
    )
    if len(secret) < 32:
        raise RuntimeError("Configura META_OAUTH_STATE_SECRET o GALAXY_JWT_SECRET con al menos 32 caracteres.")
    return hmac.new(secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256).hexdigest()


def _build_meta_oauth_state(*, business_id: str, platform: str) -> str:
    issued_at = str(int(time.time()))
    nonce = secrets.token_urlsafe(24)
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
    except (ValueError, RuntimeError):
        return None
    if not hmac.compare_digest(signature, expected) or platform not in ("instagram", "facebook"):
        return None
    try:
        uuid.UUID(business_id)
    except (ValueError, TypeError, AttributeError):
        return None
    return business_id, platform


def _oauth_popup_html(*, ok: bool, message: str, account_name: str = "") -> HTMLResponse:
    safe_message = html.escape(message or "")
    safe_name = html.escape(account_name or "")
    status = "ok" if ok else "error"
    title = "Cuenta vinculada" if ok else "No se pudo completar la conexión"
    color = "#34d399" if ok else "#fda4af"
    payload = json.dumps({"type": "META_CONNECTED", "status": status, "message": message, "account_name": account_name}, ensure_ascii=False).replace("<", "\\u003c")
    doc = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title} · CALYRISIA</title><style>body{{margin:0;background:#090d16;color:#f8fafc;font:15px system-ui;padding:36px 18px}}main{{max-width:520px;margin:8vh auto;background:#111827;border:1px solid #334155;border-radius:18px;padding:28px}}h2{{color:{color}}}p{{line-height:1.6;color:#cbd5e1}}button{{padding:10px 16px;border:0;border-radius:10px;background:#2563eb;color:white;font-weight:700;cursor:pointer}}</style></head><body><main><h2>{title}</h2><p>{safe_message}</p>{f'<p><strong>{safe_name}</strong></p>' if safe_name else ''}<button onclick='window.close()'>Cerrar ventana</button></main><script>try{{if(window.opener)window.opener.postMessage({payload},window.location.origin)}}catch(e){{}}</script></body></html>"""
    return HTMLResponse(doc, headers={"Cache-Control": "no-store"})


def _oauth_asset_picker_html(session_key: str, platform: str, candidates: list[dict[str, Any]]) -> HTMLResponse:
    public_candidates = [
        {"id": str(c.get("id") or ""), "name": str(c.get("name") or "Cuenta"), "detail": str(c.get("detail") or "")}
        for c in candidates
    ]
    candidates_json = json.dumps(public_candidates, ensure_ascii=False).replace("<", "\\u003c")
    title = "Selecciona tu cuenta de Instagram profesional" if platform == "instagram" else "Selecciona tu Página de Facebook"
    page = f"""<!doctype html><html lang='es'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title><style>body{{margin:0;padding:28px 16px;background:#090d16;color:#f8fafc;font:14px system-ui}}main{{max-width:560px;margin:5vh auto;background:#111827;border:1px solid #334155;border-radius:18px;padding:24px}}button{{display:block;width:100%;margin:10px 0;padding:14px;text-align:left;background:#1e293b;color:white;border:1px solid #475569;border-radius:12px;cursor:pointer}}button:hover{{border-color:#38bdf8}}small{{display:block;color:#94a3b8;margin-top:4px}}#status{{color:#7dd3fc;min-height:20px}}</style></head><body><main><h2>{title}</h2><p>Elige la cuenta que autorizaste en Meta. CALYRISIA solo guardará el token oficial que Meta concedió.</p><div id='choices'></div><p id='status'></p></main><script>const SESSION={json.dumps(session_key)};const PLATFORM={json.dumps(platform)};const ITEMS={candidates_json};const box=document.getElementById('choices');for(const item of ITEMS){{const b=document.createElement('button');b.textContent=item.name;const sm=document.createElement('small');sm.textContent=item.detail;b.appendChild(sm);b.onclick=()=>selectAccount(item);box.appendChild(b)}}async function selectAccount(item){{const status=document.getElementById('status');status.textContent='Vinculando cuenta y activando el webhook...';for(const b of box.querySelectorAll('button'))b.disabled=true;try{{const r=await fetch('/api/v1/auth/meta/select-account',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{session_key:SESSION,platform:PLATFORM,page_or_ig_id:item.id,account_name:item.name}})}});const data=await r.json();if(!r.ok)throw new Error(data.detail||'No se pudo vincular.');status.textContent=data.message||'Cuenta conectada.';if(window.opener)window.opener.postMessage({{type:'META_CONNECTED',status:data.ready?'ok':'error',platform:PLATFORM,account_name:data.account_name,message:data.message}},window.location.origin);setTimeout(()=>window.close(),900)}}catch(e){{status.textContent=e.message;for(const b of box.querySelectorAll('button'))b.disabled=false}}}}</script></body></html>"""
    return HTMLResponse(page, headers={"Cache-Control": "no-store"})


async def _meta_graph_get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{path.lstrip('/')}"
    async with httpx.AsyncClient(timeout=25.0) as client:
        response = await client.get(url, params=params)
    data = response.json() if response.content else {}
    if response.status_code >= 400 or not isinstance(data, dict) or data.get("error"):
        err = (data.get("error") or {}).get("message") if isinstance(data, dict) else None
        raise HTTPException(status_code=400, detail=f"Meta no autorizó la operación: {err or response.text[:400]}")
    return data


async def _exchange_meta_code(code: str) -> str:
    if not META_APP_ID or not META_APP_SECRET or not META_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Falta configurar META_APP_ID, META_APP_SECRET o META_REDIRECT_URI en Render.")
    token_data = await _meta_graph_get(
        "oauth/access_token",
        {"client_id": META_APP_ID, "client_secret": META_APP_SECRET, "redirect_uri": META_REDIRECT_URI, "code": code},
    )
    short_token = str(token_data.get("access_token") or "").strip()
    if not short_token:
        raise HTTPException(status_code=400, detail="Meta no devolvió un token de acceso.")
    long_data = await _meta_graph_get(
        "oauth/access_token",
        {
            "grant_type": "fb_exchange_token",
            "client_id": META_APP_ID,
            "client_secret": META_APP_SECRET,
            "fb_exchange_token": short_token,
        },
    )
    token = str(long_data.get("access_token") or short_token).strip()
    if not token.startswith("EAA"):
        raise HTTPException(status_code=400, detail="Meta devolvió un token inesperado. Revisa la configuración de Facebook Login de la app.")
    return token


async def _fetch_meta_assets(user_token: str, platform: str) -> list[dict[str, Any]]:
    data = await _meta_graph_get(
        "me/accounts",
        {
            "fields": "id,name,access_token,tasks,instagram_business_account{id,username},connected_instagram_account{id,username}",
            "limit": 100,
            "access_token": user_token,
        },
    )
    pages = data.get("data") if isinstance(data.get("data"), list) else []
    candidates: list[dict[str, Any]] = []
    for page in pages:
        if not isinstance(page, dict) or not page.get("id") or not page.get("access_token"):
            continue
        page_id = str(page.get("id"))
        page_name = str(page.get("name") or "Página de Facebook")
        tasks = {str(x).upper() for x in (page.get("tasks") or [])}
        page_token = str(page.get("access_token") or "").strip()
        if not page_token.startswith("EAA"):
            continue
        if platform == "facebook":
            if tasks and not ({"MESSAGING", "MANAGE"} & tasks):
                continue
            candidates.append({
                "id": page_id, "name": page_name, "detail": "Facebook Messenger · Página comercial",
                "page_id": page_id, "access_token": page_token,
            })
        else:
            ig = page.get("instagram_business_account") or page.get("connected_instagram_account") or {}
            if not isinstance(ig, dict) or not ig.get("id"):
                continue
            if tasks and not ({"MESSAGING", "MANAGE"} & tasks):
                continue
            ig_id = str(ig.get("id"))
            username = str(ig.get("username") or page_name).lstrip("@")
            candidates.append({
                "id": ig_id, "name": f"@{username}", "detail": f"Instagram profesional · Página vinculada: {page_name}",
                "page_id": page_id, "access_token": page_token,
            })
    return candidates


@router.get("/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
@router.get("/channels/meta/connect", response_model=MetaOAuthUrlResponse)
@router.get("/auth/meta/login", response_model=MetaOAuthUrlResponse)
@router.get("/dashboard/channels/meta/oauth-url", response_model=MetaOAuthUrlResponse)
async def get_meta_oauth_url(
    platform: str = Query(default="instagram"),
    force_login: bool = Query(default=False),
    tenant_ctx: MultitenantContext = Depends(get_multitenant_guard),
) -> dict[str, Any]:
    """Start the official Meta OAuth flow. No Instagram/Facebook password is ever collected by CALYRISIA."""
    platform = platform.lower().strip()
    if platform not in ("instagram", "facebook"):
        raise HTTPException(status_code=422, detail="Canal Meta no válido.")
    if not META_APP_ID or not META_APP_SECRET or not META_REDIRECT_URI:
        raise HTTPException(status_code=503, detail="Conexión Meta aún no configurada: agrega META_APP_ID, META_APP_SECRET y META_REDIRECT_URI en Render.")
    try:
        state = _build_meta_oauth_state(business_id=str(tenant_ctx.tenant_id), platform=platform)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    scopes = ["pages_show_list", "pages_messaging", "pages_read_engagement", "pages_manage_metadata"]
    if platform == "instagram":
        scopes += ["instagram_basic", "instagram_manage_messages"]
    params = {
        "client_id": META_APP_ID,
        "redirect_uri": META_REDIRECT_URI,
        "response_type": "code",
        "scope": ",".join(scopes),
        "state": state,
    }
    if force_login:
        params["auth_type"] = "rerequest"
    auth_url = f"https://www.facebook.com/{META_GRAPH_API_VERSION}/dialog/oauth?{urllib.parse.urlencode(params)}"
    return {"success": True, "auth_url": auth_url, "platform": platform, "tenant_id": str(tenant_ctx.tenant_id)}


async def _subscribe_meta_webhook(
    *, platform: str, page_id: str, access_token: str
) -> tuple[bool, str | None]:
    """Subscribe the selected Page or Instagram professional account to this Meta app."""
    if not page_id or not access_token:
        return False, "Meta no devolvió el ID del activo ni su token oficial."
    url = f"https://graph.facebook.com/{META_GRAPH_API_VERSION}/{page_id}/subscribed_apps"
    last_error = None
    fields_to_try = ("messages,messaging_postbacks", "messages")
    for fields in fields_to_try:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    url,
                    params={"subscribed_fields": fields, "access_token": access_token},
                )
            data = response.json() if response.content else {}
            if response.status_code < 400 and isinstance(data, dict) and str(data.get("success", "")).lower() == "true":
                return True, None
            err_obj = data.get("error") if isinstance(data, dict) else {}
            last_error = str((err_obj or {}).get("message") or response.text or "Meta no confirmó la suscripción.")[:500]
        except Exception as exc:
            last_error = str(exc)[:500]
    return False, last_error or "Meta no confirmó la suscripción al webhook."


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
    if platform not in ("instagram", "facebook"):
        raise HTTPException(status_code=422, detail="Canal Meta no válido.")
    verify_token = (os.getenv("META_WEBHOOK_VERIFY_TOKEN", META_WEBHOOK_VERIFY_TOKEN).strip() or _default_verify_token(business_id))
    # For Instagram the subscribed asset is the IG professional ID; for Messenger it is the Page ID.
    subscribed_asset_id = str(page_or_ig_id if platform == "instagram" else (subscribe_page_id or page_or_ig_id)).strip()
    subscribed_ok, subscribe_error = await _subscribe_meta_webhook(
        platform=platform, page_id=subscribed_asset_id, access_token=access_token
    )
    stored_token = _encrypt_meta_token(access_token)
    channel_status = "connected" if subscribed_ok else "pending_webhook"
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
                    business_id, platform, bool(subscribed_ok), channel_status, account_name[:160],
                    page_or_ig_id[:120], str(subscribe_page_id or "")[:120], stored_token,
                    verify_token, subscribe_error,
                ),
            )
        conn.commit()
    return {
        "ready": bool(subscribed_ok),
        "subscribed_via_api": bool(subscribed_ok),
        "channel_status": channel_status,
        "last_error": subscribe_error,
    }


async def handle_meta_oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
) -> HTMLResponse:
    if error:
        return _oauth_popup_html(ok=False, message=f"Meta canceló la autorización: {error}")
    parsed = _parse_and_validate_meta_oauth_state(state)
    if not parsed:
        return _oauth_popup_html(ok=False, message="La autorización caducó o la firma de seguridad no es válida. Regresa al panel e inténtalo otra vez.")
    if not code:
        return _oauth_popup_html(ok=False, message="Meta no devolvió el código de autorización.")
    business_id, platform = parsed
    try:
        user_token = await _exchange_meta_code(code)
        candidates = await _fetch_meta_assets(user_token, platform)
        if not candidates:
            hint = (
                "No encontramos una cuenta profesional de Instagram conectada a una Página que puedas administrar. Convierte Instagram a cuenta Profesional, vincúlala a una Página y concede los permisos solicitados."
                if platform == "instagram"
                else "No encontramos Páginas administrables con permisos de mensajería para esta cuenta de Facebook."
            )
            return _oauth_popup_html(ok=False, message=hint)
        session_key = secrets.token_urlsafe(36)
        encrypted_candidates = []
        for item in candidates:
            stored = dict(item)
            stored["access_token"] = _encrypt_meta_token(str(item["access_token"]))
            encrypted_candidates.append(stored)
        await ensure_meta_social_schema()
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO public.meta_oauth_pending_sessions
                       (session_key, business_id, platform, candidates, expires_at)
                       VALUES (%s, %s::uuid, %s, %s, now() + interval '10 minutes')""",
                    (session_key, business_id, platform, Jsonb(encrypted_candidates)),
                )
            conn.commit()
        return _oauth_asset_picker_html(session_key, platform, candidates)
    except HTTPException as exc:
        return _oauth_popup_html(ok=False, message=str(exc.detail))
    except Exception as exc:
        logger.exception("Meta OAuth callback failed: %s", exc)
        return _oauth_popup_html(ok=False, message="No se pudo terminar la autorización. Revisa META_APP_ID, META_APP_SECRET, permisos y la URL de retorno configurada en Meta.")


@router.get("/auth/meta/callback")
async def meta_oauth_callback_route(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
):
    return await handle_meta_oauth_callback(code=code, state=state, error=error)


@router.post("/auth/meta/select-account")
async def select_meta_oauth_account(payload: MetaOAuthSelectAccountRequest) -> dict[str, Any]:
    await ensure_meta_social_schema()
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT business_id::text, platform, candidates
                   FROM public.meta_oauth_pending_sessions
                   WHERE session_key = %s AND expires_at > now()""",
                (payload.session_key,),
            )
            session = cur.fetchone()
    if not session:
        raise HTTPException(status_code=400, detail="La selección caducó. Vuelve a iniciar la conexión desde CALYRISIA.")
    business_id, platform, raw_candidates = str(session[0]), str(session[1]), session[2]
    if platform != payload.platform.lower().strip():
        raise HTTPException(status_code=400, detail="La selección no corresponde al canal solicitado.")
    if isinstance(raw_candidates, str):
        try:
            raw_candidates = json.loads(raw_candidates)
        except Exception:
            raw_candidates = []
    candidates = raw_candidates if isinstance(raw_candidates, list) else []
    selected = next((x for x in candidates if isinstance(x, dict) and str(x.get("id") or "") == payload.page_or_ig_id), None)
    if not selected:
        raise HTTPException(status_code=400, detail="La cuenta elegida no pertenece a la autorización de Meta.")
    token = _decrypt_meta_token(str(selected.get("access_token") or ""))
    page_id = str(selected.get("page_id") or "").strip()
    account_name = str(selected.get("name") or payload.account_name or "Cuenta Meta").strip()[:160]
    result = await _activate_meta_account_in_db(
        business_id=business_id,
        platform=platform,
        account_name=account_name,
        page_or_ig_id=str(selected.get("id") or ""),
        access_token=token,
        subscribe_page_id=page_id,
    )
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.meta_oauth_pending_sessions WHERE session_key = %s", (payload.session_key,))
        conn.commit()
    if not result.get("subscribed_via_api"):
        message = f"Cuenta autorizada ({account_name}), pero Meta no confirmó el webhook: {result.get('last_error') or 'revisa la configuración de Webhooks y pages_manage_metadata.'}"
    else:
        message = f"{_platform_label(platform)} ({account_name}) conectado. La IA ya puede responder los mensajes recibidos por el webhook."
    return {
        "success": True, "ready": bool(result.get("subscribed_via_api")), "platform": platform,
        "account_name": account_name, "channel_status": result.get("channel_status"),
        "last_error": result.get("last_error"), "message": message,
    }


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
    raise HTTPException(
        status_code=409,
        detail="No se puede vincular escribiendo un nombre, contraseña o cookie. Usa el botón de autorización oficial de Meta.",
    )


@router.post("/dashboard/channels/meta/{platform}/toggle")
async def toggle_meta_channel(
    platform: str,
    payload: MetaChannelToggleRequest,
    request: Request,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    platform = platform.lower().strip()
    if platform not in ("instagram", "facebook"):
        raise HTTPException(status_code=422, detail="Plataforma inválida.")
    await ensure_meta_social_schema()
    business_id = str(current_user["business_id"])
    base_url = f"{request.url.scheme}://{request.url.netloc}" if request.url.netloc else ""
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT account_name, page_or_ig_id, parent_page_id, access_token, channel_status
                   FROM public.business_meta_channels
                   WHERE business_id = %s::uuid AND platform = %s""",
                (business_id, platform),
            )
            existing = cur.fetchone()
    if not existing:
        raise HTTPException(status_code=404, detail=f"Primero vincula tu cuenta de {_platform_label(platform)}.")

    enabled = bool(payload.enabled)
    status = "paused" if not enabled else "connected"
    last_error = None
    if enabled:
        try:
            token = _decrypt_meta_token(str(existing[3] or ""))
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        subscribe_asset_id = str(existing[1] if platform == "instagram" else (existing[2] or existing[1]))
        subscribed_ok, last_error = await _subscribe_meta_webhook(
            platform=platform, page_id=subscribe_asset_id, access_token=token
        )
        enabled = bool(subscribed_ok)
        status = "connected" if subscribed_ok else "pending_webhook"
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.business_meta_channels
                   SET enabled = %s, channel_status = %s, last_error = %s, updated_at = now()
                   WHERE business_id = %s::uuid AND platform = %s""",
                (enabled, status, last_error, business_id, platform),
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
    if not payload.enabled:
        message = f"{_platform_label(platform)} está en pausa."
    elif enabled:
        message = f"{_platform_label(platform)} activado y webhook confirmado por Meta."
    else:
        message = f"La cuenta está autorizada, pero el webhook sigue pendiente: {last_error or 'revisa permisos y suscripciones de Webhooks en Meta.'}"
    return {
        "success": True, "enabled": enabled, "message": message,
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


async def _process_meta_webhook_payload_background(
    body: dict[str, Any], explicit_business_id: str | None = None
) -> None:
    try:
        await _process_meta_webhook_payload(body, explicit_business_id)
    except Exception:
        logger.exception("Meta webhook background processing failed")


async def receive_global_meta_webhook_handler(
    request: Request,
    explicit_business_id: str | None = None,
    background_tasks: BackgroundTasks | None = None,
) -> PlainTextResponse:
    try:
        raw_body = await request.body()
        app_secret = os.getenv("META_APP_SECRET", "").strip() or META_APP_SECRET
        signature = request.headers.get("X-Hub-Signature-256", "").strip()
        if not app_secret:
            raise HTTPException(status_code=503, detail="META_APP_SECRET no está configurado; no se procesan webhooks sin verificar.")
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

    # Meta expects a quick 2xx acknowledgement. Run the LLM and Graph API reply
    # after the HTTP response so a slow model call does not trigger webhook retries.
    if background_tasks is not None:
        background_tasks.add_task(_process_meta_webhook_payload_background, body, explicit_business_id)
    else:  # Useful for direct invocations and tests outside FastAPI.
        await _process_meta_webhook_payload_background(body, explicit_business_id)
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