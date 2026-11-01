from __future__ import annotations

import asyncio
import hmac
import json
import os
import re
import shutil
import subprocess
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException
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
from app.services.commercial_limits import AIQuotaExceeded, consume_ai_response, get_business_plan, plan_limits

logger = get_logger(__name__)
router = APIRouter()

WA_BRIDGE_PORT = int(os.getenv("WA_BRIDGE_PORT", "3001"))
WA_BRIDGE_SECRET = os.getenv("WA_BRIDGE_SECRET", "calyrisia-internal-wa-bridge-secret")
_wa_bridge_proc: subprocess.Popen | None = None
_wa_schema_initialized = False


class WhatsAppConnectRequest(BaseModel):
    pairing_phone: str | None = Field(default=None, max_length=40)


class WhatsAppToggleRequest(BaseModel):
    enabled: bool


async def ensure_whatsapp_schema() -> None:
    """Idempotent schema for WhatsApp QR sessions and Supabase auth persistence."""
    global _wa_schema_initialized
    if _wa_schema_initialized:
        return
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.business_whatsapp_channels (
                        business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
                        enabled boolean NOT NULL DEFAULT false,
                        channel_status varchar(30) NOT NULL DEFAULT 'disconnected',
                        phone_number varchar(80),
                        display_name varchar(160),
                        qr_code_data_url text,
                        pairing_code varchar(32),
                        last_error text,
                        connected_at timestamptz,
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.business_whatsapp_auth_keys (
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        file_name varchar(255) NOT NULL,
                        file_content text NOT NULL,
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (business_id, file_name)
                    )
                    """
                )
                cur.execute("ALTER TABLE public.business_whatsapp_channels ENABLE ROW LEVEL SECURITY")
                cur.execute("ALTER TABLE public.business_whatsapp_auth_keys ENABLE ROW LEVEL SECURITY")
                cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_whatsapp_channels TO postgres, service_role")
                cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_whatsapp_auth_keys TO postgres, service_role")
            conn.commit()
            _wa_schema_initialized = True
        except Exception:
            conn.rollback()
            raise


def _bridge_call_sync(path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 12) -> dict:
    url = f"http://127.0.0.1:{WA_BRIDGE_PORT}{path}"
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    req.add_header("X-WA-Bridge-Secret", WA_BRIDGE_SECRET)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            err_json = json.loads(raw)
            raise RuntimeError(err_json.get("error") or raw) from exc
        except json.JSONDecodeError:
            raise RuntimeError(raw or str(exc)) from exc
    except Exception as exc:
        raise RuntimeError(f"Puente WhatsApp QR no disponible: {exc}") from exc


async def _bridge_call(path: str, method: str = "GET", payload: dict[str, Any] | None = None, timeout: int = 12) -> dict:
    return await asyncio.to_thread(_bridge_call_sync, path, method, payload, timeout)


async def is_bridge_online() -> bool:
    try:
        res = await _bridge_call("/health", "GET", None, timeout=3)
        return bool(res.get("ok"))
    except Exception:
        return False


async def start_whatsapp_bridge() -> None:
    """Start the local Baileys Node.js microservice and reconnect previously linked businesses."""
    global _wa_bridge_proc
    try:
        await ensure_whatsapp_schema()
    except Exception as exc:
        logger.warning("No se pudo inicializar el esquema de WhatsApp QR: %s", exc)

    bridge_dir = Path(__file__).resolve().parents[2] / "whatsapp_bridge"
    server_mjs = bridge_dir / "server.mjs"
    node_bin = shutil.which("node")
    if not server_mjs.exists() or not node_bin:
        logger.info("Node.js o whatsapp_bridge/server.mjs no disponible; omitiendo puente QR local.")
        return

    node_modules = bridge_dir / "node_modules"
    npm_bin = shutil.which("npm")
    if not node_modules.exists() and npm_bin:
        try:
            logger.info("Instalando dependencias de whatsapp_bridge (Baileys)...")
            await asyncio.to_thread(
                subprocess.run,
                [npm_bin, "install", "--omit=dev", "--no-audit", "--no-fund"],
                cwd=str(bridge_dir),
                check=False,
                capture_output=True,
                timeout=120,
            )
        except Exception as exc:
            logger.warning("No se pudieron instalar dependencias de whatsapp_bridge: %s", exc)

    if _wa_bridge_proc is None or _wa_bridge_proc.poll() is not None:
        env = os.environ.copy()
        env["WA_BRIDGE_PORT"] = str(WA_BRIDGE_PORT)
        env["WA_BRIDGE_SECRET"] = WA_BRIDGE_SECRET
        env["WA_FASTAPI_BASE"] = f"http://127.0.0.1:{os.getenv('PORT') or os.getenv('APP_PORT') or '8000'}"
        try:
            _wa_bridge_proc = subprocess.Popen(
                [node_bin, str(server_mjs)],
                cwd=str(bridge_dir),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception as exc:
            logger.warning("No se pudo iniciar el subproceso de WhatsApp QR: %s", exc)
            return

    # Wait briefly for bridge health and restore connected sessions from Supabase
    for _ in range(10):
        if await is_bridge_online():
            break
        await asyncio.sleep(0.5)

    if await is_bridge_online():
        try:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT DISTINCT c.business_id::text
                           FROM public.business_whatsapp_channels c
                           JOIN public.business_whatsapp_auth_keys k ON k.business_id = c.business_id
                           WHERE c.channel_status IN ('connected', 'starting')"""
                    )
                    biz_ids = [str(r[0]) for r in cur.fetchall()]
            for bid in biz_ids:
                try:
                    await _bridge_call("/session/start", "POST", {"business_id": bid}, timeout=8)
                except Exception:
                    pass
        except Exception as exc:
            logger.warning("No se pudieron restaurar sesiones previas de WhatsApp QR: %s", exc)


async def stop_whatsapp_bridge() -> None:
    global _wa_bridge_proc
    if _wa_bridge_proc is not None and _wa_bridge_proc.poll() is None:
        try:
            _wa_bridge_proc.terminate()
        except Exception:
            pass
    _wa_bridge_proc = None


def _verify_bridge_secret(secret_header: str | None) -> None:
    if not secret_header or not hmac.compare_digest(secret_header, WA_BRIDGE_SECRET):
        raise HTTPException(status_code=401, detail="No autorizado para el puente interno de WhatsApp.")


# ---------------------------------------------------------------------------
# ENDPOINTS DEL DASHBOARD (AUTENTICADOS PARA OWNER / ADMIN)
# ---------------------------------------------------------------------------

@router.get("/dashboard/channels/whatsapp")
async def get_whatsapp_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    online = await is_bridge_online()
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT enabled, channel_status, phone_number, display_name,
                          qr_code_data_url, pairing_code, last_error, connected_at
                   FROM public.business_whatsapp_channels
                   WHERE business_id = %s::uuid""",
                (business_id,),
            )
            row = cur.fetchone()
    if not row:
        return {
            "success": True,
            "enabled": False,
            "status": "disconnected",
            "phone_number": "",
            "display_name": "",
            "qr_code_data_url": None,
            "pairing_code": None,
            "last_error": None,
            "connected_at": None,
            "bridge_online": online,
        }
    return {
        "success": True,
        "enabled": bool(row[0]),
        "status": str(row[1] or "disconnected"),
        "phone_number": str(row[2] or ""),
        "display_name": str(row[3] or ""),
        "qr_code_data_url": row[4],
        "pairing_code": row[5],
        "last_error": row[6],
        "connected_at": row[7].isoformat() if row[7] else None,
        "bridge_online": online,
    }


@router.post("/dashboard/channels/whatsapp/connect")
async def connect_whatsapp_channel(
    payload: WhatsAppConnectRequest | None = None,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    pairing_phone = (payload.pairing_phone if payload else "") or ""

    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        limits = plan_limits(plan_code)
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM public.businesses WHERE id = %s::uuid", (business_id,))
            webchat_on = bool((cur.fetchone() or [False])[0])
            cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
            tg_on = bool((cur.fetchone() or [False])[0])
            cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_whatsapp_channels WHERE business_id = %s::uuid", (business_id,))
            wa_was_on = bool((cur.fetchone() or [False])[0])

            other_active = int(webchat_on) + int(tg_on)
            if not wa_was_on and other_active >= limits["channels"]:
                raise HTTPException(
                    status_code=409,
                    detail=f"Tu plan {limits['label']} incluye {limits['channels']} canal(es) simultáneo(s). Desactiva primero otro canal activo en esta vista o actualiza al plan Plan PRO ($49).",
                )

            cur.execute(
                """INSERT INTO public.business_whatsapp_channels
                   (business_id, enabled, channel_status, qr_code_data_url, pairing_code, last_error, updated_at)
                   VALUES (%s::uuid, true, 'starting', NULL, NULL, NULL, now())
                   ON CONFLICT (business_id) DO UPDATE SET
                     enabled = true,
                     channel_status = 'starting',
                     qr_code_data_url = NULL,
                     pairing_code = NULL,
                     last_error = NULL,
                     updated_at = now()""",
                (business_id,),
            )
        conn.commit()

    if not await is_bridge_online():
        await start_whatsapp_bridge()

    try:
        await _bridge_call(
            "/session/start",
            "POST",
            {"business_id": business_id, "pairing_phone": pairing_phone.strip()},
            timeout=15,
        )
    except Exception as exc:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE public.business_whatsapp_channels SET channel_status = 'error', last_error = %s, updated_at = now() WHERE business_id = %s::uuid",
                    (str(exc), business_id),
                )
            conn.commit()
        raise HTTPException(status_code=503, detail=f"No se pudo iniciar el generador de QR de WhatsApp: {exc}") from exc

    return {
        "success": True,
        "status": "starting",
        "message": "Generando código QR de WhatsApp en tiempo real. Espera unos segundos y escanéalo desde tu teléfono.",
    }


@router.post("/dashboard/channels/whatsapp/toggle")
async def toggle_whatsapp_channel(
    payload: WhatsAppToggleRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    async with get_connection() as conn:
        if payload.enabled:
            plan_code = get_business_plan(conn, business_id)
            limits = plan_limits(plan_code)
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM public.businesses WHERE id = %s::uuid", (business_id,))
                webchat_on = bool((cur.fetchone() or [False])[0])
                cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                tg_on = bool((cur.fetchone() or [False])[0])
                if (int(webchat_on) + int(tg_on)) >= limits["channels"]:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Tu plan {limits['label']} incluye {limits['channels']} canal(es) activo(s). Desactiva otro canal primero o cambia a Plan PRO.",
                    )
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.business_whatsapp_channels
                   SET enabled = %s, updated_at = now()
                   WHERE business_id = %s::uuid
                   RETURNING enabled, channel_status""",
                (payload.enabled, business_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Primero vincula tu WhatsApp con el código QR.")
    return {
        "success": True,
        "enabled": bool(row[0]),
        "status": str(row[1]),
        "message": "Asistente IA en WhatsApp activado." if row[0] else "Asistente IA en WhatsApp pausado. Puedes responder manualmente desde tu teléfono.",
    }


@router.post("/dashboard/channels/whatsapp/disconnect")
async def disconnect_whatsapp_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    try:
        if await is_bridge_online():
            await _bridge_call("/session/logout", "POST", {"business_id": business_id}, timeout=10)
    except Exception:
        pass
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.business_whatsapp_auth_keys WHERE business_id = %s::uuid", (business_id,))
            cur.execute(
                """UPDATE public.business_whatsapp_channels
                   SET enabled = false, channel_status = 'disconnected', phone_number = NULL,
                       display_name = NULL, qr_code_data_url = NULL, pairing_code = NULL,
                       last_error = NULL, updated_at = now()
                   WHERE business_id = %s::uuid""",
                (business_id,),
            )
        conn.commit()
    return {"success": True, "status": "disconnected", "message": "WhatsApp desvinculado correctamente."}


# ---------------------------------------------------------------------------
# ENDPOINTS INTERNOS DEL PUENTE BAILEYS (127.0.0.1)
# ---------------------------------------------------------------------------

@router.get("/internal/whatsapp/auth-files/{business_id}")
async def internal_get_wa_auth_files(
    business_id: str,
    x_wa_bridge_secret: str | None = Header(default=None),
) -> dict:
    _verify_bridge_secret(x_wa_bridge_secret)
    await ensure_whatsapp_schema()
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT file_name, file_content FROM public.business_whatsapp_auth_keys WHERE business_id = %s::uuid",
                (business_id,),
            )
            files = {str(r[0]): str(r[1]) for r in cur.fetchall()}
    return {"ok": True, "files": files}


@router.post("/internal/whatsapp/auth-files/{business_id}")
async def internal_save_wa_auth_files(
    business_id: str,
    payload: dict,
    x_wa_bridge_secret: str | None = Header(default=None),
) -> dict:
    _verify_bridge_secret(x_wa_bridge_secret)
    await ensure_whatsapp_schema()
    files = payload.get("files") or {}
    if not isinstance(files, dict):
        return {"ok": False}
    async with get_connection() as conn:
        with conn.cursor() as cur:
            for fname, content in files.items():
                cur.execute(
                    """INSERT INTO public.business_whatsapp_auth_keys (business_id, file_name, file_content, updated_at)
                       VALUES (%s::uuid, %s, %s, now())
                       ON CONFLICT (business_id, file_name) DO UPDATE
                       SET file_content = EXCLUDED.file_content, updated_at = now()""",
                    (business_id, str(fname)[:255], str(content)),
                )
        conn.commit()
    return {"ok": True}


@router.post("/internal/whatsapp/status")
async def internal_update_wa_status(
    payload: dict,
    x_wa_bridge_secret: str | None = Header(default=None),
) -> dict:
    _verify_bridge_secret(x_wa_bridge_secret)
    await ensure_whatsapp_schema()
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        raise HTTPException(status_code=400, detail="business_id required")
    status = str(payload.get("status") or "disconnected")
    qr_url = payload.get("qr_code_data_url")
    pairing = payload.get("pairing_code")
    phone = payload.get("phone_number")
    dname = payload.get("display_name")
    err = payload.get("last_error")
    clear_auth = bool(payload.get("clear_auth"))

    async with get_connection() as conn:
        with conn.cursor() as cur:
            if clear_auth:
                cur.execute("DELETE FROM public.business_whatsapp_auth_keys WHERE business_id = %s::uuid", (business_id,))
            cur.execute(
                """INSERT INTO public.business_whatsapp_channels
                   (business_id, enabled, channel_status, phone_number, display_name, qr_code_data_url, pairing_code, last_error, connected_at, updated_at)
                   VALUES (%s::uuid, true, %s, %s, %s, %s, %s, %s, CASE WHEN %s = 'connected' THEN now() ELSE NULL END, now())
                   ON CONFLICT (business_id) DO UPDATE SET
                     channel_status = EXCLUDED.channel_status,
                     phone_number = COALESCE(EXCLUDED.phone_number, business_whatsapp_channels.phone_number),
                     display_name = COALESCE(EXCLUDED.display_name, business_whatsapp_channels.display_name),
                     qr_code_data_url = CASE WHEN %s = 'connected' THEN NULL ELSE COALESCE(EXCLUDED.qr_code_data_url, business_whatsapp_channels.qr_code_data_url) END,
                     pairing_code = CASE WHEN %s = 'connected' THEN NULL ELSE COALESCE(EXCLUDED.pairing_code, business_whatsapp_channels.pairing_code) END,
                     last_error = EXCLUDED.last_error,
                     connected_at = CASE WHEN %s = 'connected' THEN now() ELSE business_whatsapp_channels.connected_at END,
                     updated_at = now()""",
                (business_id, status, phone, dname, qr_url, pairing, err, status, status, status, status),
            )
        conn.commit()
    return {"ok": True}


@router.post("/internal/whatsapp/incoming")
async def internal_whatsapp_incoming(
    payload: dict,
    x_wa_bridge_secret: str | None = Header(default=None),
) -> dict:
    """Process an incoming WhatsApp message through CALYRISIA's AI Brain, Catalog, Bookings & Payment Approvals."""
    _verify_bridge_secret(x_wa_bridge_secret)
    await ensure_whatsapp_schema()
    business_id = str(payload.get("business_id") or "").strip()
    sender_phone = re.sub(r"\D", "", str(payload.get("sender_phone") or ""))
    sender_name = str(payload.get("sender_name") or "Cliente WhatsApp").strip()[:180]
    message_text = str(payload.get("message_text") or "").strip()

    if not business_id or not sender_phone or not message_text:
        return {"ok": True, "reply_text": ""}

    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT c.enabled, b.status, b.name, COALESCE(d.exchange_rate, 0), COALESCE(d.local_currency_code, 'VES')
                   FROM public.business_whatsapp_channels c
                   JOIN public.businesses b ON b.id = c.business_id
                   LEFT JOIN public.business_dashboard_settings d ON d.business_id = c.business_id
                   WHERE c.business_id = %s::uuid""",
                (business_id,),
            )
            cfg = cur.fetchone()
            if not cfg or not bool(cfg[0]) or str(cfg[1]) != "active":
                return {"ok": True, "reply_text": ""}
            biz_name = str(cfg[2] or "nuestro negocio")
            ex_rate = float(cfg[3] or 0)
            loc_curr = str(cfg[4] or "VES")

            # 1. Resolve or create customer & active conversation for this WhatsApp number
            phone_display = f"+{sender_phone}"
            cur.execute(
                """SELECT id, full_name FROM public.customers
                   WHERE business_id = %s::uuid AND REPLACE( COALESCE(phone, ''), '+', '' ) = %s
                   ORDER BY created_at DESC LIMIT 1""",
                (business_id, sender_phone),
            )
            cust_row = cur.fetchone()
            if cust_row:
                customer_id = uuid.UUID(str(cust_row[0]))
                if sender_name and sender_name != "Cliente WhatsApp" and (not cust_row[1] or cust_row[1] == "Cliente WhatsApp"):
                    cur.execute("UPDATE public.customers SET full_name = %s, last_interaction_at = now() WHERE id = %s", (sender_name, customer_id))
                else:
                    cur.execute("UPDATE public.customers SET last_interaction_at = now() WHERE id = %s", (customer_id,))
            else:
                customer_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO public.customers (id, business_id, full_name, phone, status, source, channel, first_contact_at, last_interaction_at, notes)
                       VALUES (%s, %s::uuid, %s, %s, 'active', 'whatsapp', 'whatsapp', now(), now(), 'Cliente atendido automáticamente por WhatsApp QR.')""",
                    (customer_id, business_id, sender_name, phone_display),
                )

            cur.execute(
                """SELECT id FROM public.conversations
                   WHERE business_id = %s::uuid AND customer_id = %s AND channel = 'whatsapp' AND status = 'active'
                   ORDER BY updated_at DESC NULLS LAST LIMIT 1""",
                (business_id, customer_id),
            )
            conv_row = cur.fetchone()
            if conv_row:
                conversation_id = uuid.UUID(str(conv_row[0]))
            else:
                conversation_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO public.conversations (id, business_id, customer_id, channel, status, started_at, last_message_at)
                       VALUES (%s, %s::uuid, %s, 'whatsapp', 'active', now(), now())""",
                    (conversation_id, business_id, customer_id),
                )
        conn.commit()

        # 2. Check if customer is submitting a payment reference on WhatsApp
        if _looks_like_payment_submission(message_text):
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT content FROM public.conversation_messages
                       WHERE business_id = %s::uuid AND customer_id = %s AND conversation_id = %s AND direction = 'outbound'
                       ORDER BY created_at DESC LIMIT 10""",
                    (business_id, customer_id, conversation_id),
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
                       VALUES (%s, %s::uuid, %s, %s, 'USD', %s, 'pending', 'whatsapp',
                               'Solicitud de pago recibida por WhatsApp; pendiente de aprobación del dueño.', %s, %s)""",
                    (pay_id, business_id, customer_id, amount, pay_method, Jsonb(items) if items else None, message_text[:4000]),
                )
            conn.commit()
            try:
                await notify_owner_payment_pending(
                    business_id=business_id,
                    payment_id=str(pay_id),
                    amount=amount,
                    customer_name=f"{sender_name} ({phone_display})",
                    customer_chat_id=phone_display,
                    payment_details=message_text,
                    payment_method=f"{'Binance Pay' if pay_method == 'binance' else 'Pago Móvil'} · WhatsApp",
                    items=items,
                )
            except Exception:
                pass
            return {
                "ok": True,
                "reply_text": (
                    f"✅ Recibimos los datos de tu pago en {biz_name} por USD {amount:.2f}. "
                    f"Tu referencia quedó registrada para revisión del comercio y te confirmaremos por esta misma vía en cuanto sea aprobada."
                ),
            }

        # 3. Consume AI quota and run CALYRISIA Autopilot Brain
        try:
            consume_ai_response(conn, uuid.UUID(business_id))
            conn.commit()
        except AIQuotaExceeded:
            return {"ok": True, "reply_text": ""}

        try:
            incoming = IncomingMessage(
                business_id=uuid.UUID(business_id),
                customer_id=customer_id,
                conversation_id=conversation_id,
                channel="whatsapp",
                message=message_text,
                metadata={"source": "calyrisia_whatsapp_qr", "sender_phone": phone_display},
            )
            result = GalaxyAutopilotService(conn).respond(incoming)
            raw_reply = str(result.get("response") or "").strip()
            clean_reply, pay_amount, _ = _clean_for_telegram(raw_reply)

            # If the AI triggered a payment button, append the official payment instructions & local currency conversion
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
                        if ex_rate > 0 else ""
                    )
                    inst_lines = [f"\n\n💳 DATOS DE PAGO ({biz_name}):\nTotal: USD {float(pay_amount):.2f}{loc_line}"]
                    for m_code, m_inst in methods:
                        label = {"pago_movil": "Pago Móvil", "transferencia": "Transferencia Bancaria", "zelle": "Zelle", "binance": "Binance Pay", "paypal": "PayPal"}.get(str(m_code), str(m_code).title())
                        inst_lines.append(f"\n• {label}:\n{str(m_inst).strip()}")
                    inst_lines.append("\nCuando realices el pago, envíame por aquí el número de referencia (ej. 'Referencia 123456') para registrarlo de inmediato.")
                    clean_reply = (clean_reply + "\n" + "\n".join(inst_lines)).strip()

            return {"ok": True, "reply_text": clean_reply}
        except Exception as exc:
            conn.rollback()
            logger.warning("Error procesando mensaje entrante de WhatsApp QR: %s", exc)
            return {"ok": True, "reply_text": ""}


async def notify_whatsapp_payment_decision(
    business_id: str,
    payment_id: str,
    decision: str,
    amount: float,
    order_id: str | None = None,
) -> None:
    """When the owner approves or rejects a payment in Dashboard, notify the customer on WhatsApp if connected."""
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT p.source, c.phone, COALESCE(c.full_name, 'Cliente'), b.name
                       FROM public.webchat_payment_requests p
                       JOIN public.customers c ON c.id = p.customer_id AND c.business_id = p.business_id
                       JOIN public.businesses b ON b.id = p.business_id
                       WHERE p.id = %s::uuid AND p.business_id = %s::uuid""",
                    (payment_id, business_id),
                )
                row = cur.fetchone()
        if not row or not row[1]:
            return
        phone = str(row[1]).strip()
        biz_name = str(row[3] or "nuestro comercio")
        if decision == "approve":
            msg = f"🎉 ¡Pago Aprobado! Hola {row[2]}, en {biz_name} hemos verificado tu pago por USD {amount:.2f}. Tu pedido ya está confirmado y en preparación."
            if order_id:
                msg += f" (Orden #{str(order_id)[:8]})"
        else:
            msg = f"Hola {row[2]}, tu reporte de pago por USD {amount:.2f} en {biz_name} no pudo ser verificado. Por favor escríbenos por esta vía para revisar la referencia."
        if await is_bridge_online():
            await _bridge_call("/session/send", "POST", {"business_id": business_id, "to_phone": phone, "text": msg}, timeout=10)
    except Exception:
        pass
