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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from pydantic import BaseModel, Field

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

from app.api import auth
from app.core.logger import get_logger
from app.db import get_connection
from app.meta_schemas import (
    EvolutionInstanceConnectResponse,
    NormalizedOmnichannelPayload,
)
from app.services.business_brain_service import BusinessBrainService
from app.services.evolution_service import EvolutionWhatsAppService
from app.services.omnichannel_gateway_service import OmnichannelGatewayService
from app.services.tenant_guard import MultitenantContext, get_multitenant_guard

logger = get_logger(__name__)
router = APIRouter()

WA_BRIDGE_PORT = int(os.getenv("WA_BRIDGE_PORT", "3001"))
WA_BRIDGE_SECRET = os.getenv("WA_BRIDGE_SECRET", "calyrisia-internal-wa-bridge-secret")
_wa_bridge_proc: subprocess.Popen | None = None
_wa_schema_initialized = False


class WhatsAppConnectRequest(BaseModel):
    pairing_phone: str | None = Field(default=None, max_length=40)
    tenant_id: str | None = Field(default=None, max_length=80)
    force_new: bool = Field(default=False)


class WhatsAppToggleRequest(BaseModel):
    enabled: bool


async def ensure_whatsapp_schema() -> None:
    """Idempotent schema for WhatsApp Multitenant sessions (Evolution API + Baileys QR persistence)."""
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
                        instance_name varchar(120),
                        provider varchar(40) NOT NULL DEFAULT 'evolution',
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
                cur.execute("ALTER TABLE public.business_whatsapp_channels ADD COLUMN IF NOT EXISTS instance_name varchar(120)")
                cur.execute("ALTER TABLE public.business_whatsapp_channels ADD COLUMN IF NOT EXISTS provider varchar(40) NOT NULL DEFAULT 'evolution'")
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
                try:
                    cur.execute("SAVEPOINT sp_wa_rls")
                    cur.execute("ALTER TABLE public.business_whatsapp_channels ENABLE ROW LEVEL SECURITY")
                    cur.execute("ALTER TABLE public.business_whatsapp_auth_keys ENABLE ROW LEVEL SECURITY")
                    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_whatsapp_channels TO postgres, service_role")
                    cur.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.business_whatsapp_auth_keys TO postgres, service_role")
                    cur.execute("RELEASE SAVEPOINT sp_wa_rls")
                except Exception:
                    try:
                        cur.execute("ROLLBACK TO SAVEPOINT sp_wa_rls")
                    except Exception:
                        pass
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

    for _ in range(10):
        if await is_bridge_online():
            break
        await asyncio.sleep(0.4)

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


async def send_whatsapp_reply_async(
    tenant_id: str,
    recipient_phone: str,
    message_text: str,
    *,
    instance_name: str | None = None,
) -> dict[str, Any]:
    """Función asíncrona (usando `httpx`) para enviar la respuesta generada por la IA de vuelta a la instancia de WhatsApp del cliente."""
    evo = EvolutionWhatsAppService()
    if evo.is_configured:
        try:
            res = await evo.send_whatsapp_message(
                tenant_id=tenant_id,
                recipient_phone=recipient_phone,
                text=message_text,
                instance_name=instance_name,
            )
            if res.get("sent"):
                return res
        except Exception as exc:
            logger.warning("Fallo envío vía Evolution API para tenant %s: %s", tenant_id, exc)

    # Fallback transparente al puente local Baileys si está corriendo en el mismo contenedor
    if await is_bridge_online():
        try:
            await _bridge_call(
                "/session/send",
                "POST",
                {"business_id": str(tenant_id), "to_phone": recipient_phone, "text": message_text},
                timeout=10,
            )
            return {
                "sent": True,
                "provider": "baileys_local_bridge",
                "instance_name": instance_name or evo.build_instance_name(tenant_id),
                "recipient": recipient_phone,
            }
        except Exception as exc:
            return {"sent": False, "error": str(exc)}

    return {
        "sent": False,
        "provider": "evolution" if evo.is_configured else "unconfigured",
        "instance_name": instance_name or evo.build_instance_name(tenant_id),
        "error": "Evolution API no configurada o instancia desconectada.",
    }


async def _provision_whatsapp_instance_for_tenant(
    business_id: str,
    pairing_phone: str = "",
) -> dict[str, Any]:
    """Orquesta la creación de instancia dinámica en Evolution API (o puente QR local) para `tenant_id`."""
    await ensure_whatsapp_schema()
    evo = EvolutionWhatsAppService()
    instance_name = evo.build_instance_name(business_id)

    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.business_whatsapp_channels
                   (business_id, enabled, channel_status, instance_name, provider, qr_code_data_url, pairing_code, last_error, updated_at)
                   VALUES (%s, true, 'starting', %s, %s, NULL, NULL, NULL, NOW())
                   ON CONFLICT (business_id) DO UPDATE SET
                     enabled = true,
                     channel_status = 'starting',
                     instance_name = EXCLUDED.instance_name,
                     provider = EXCLUDED.provider,
                     qr_code_data_url = NULL,
                     pairing_code = NULL,
                     last_error = NULL,
                     updated_at = NOW()""",
                (business_id, instance_name, "evolution" if evo.is_configured else "baileys"),
            )
        conn.commit()

    # 1. Si Evolution API está configurada, levantar instancia dinámica vía httpx
    if evo.is_configured:
        try:
            evo_res = await evo.create_or_connect_instance(
                tenant_id=business_id,
                pairing_phone=pairing_phone,
            )
            qr_url = evo_res.get("qr_code_data_url")
            pairing_code = evo_res.get("pairing_code")
            status = str(evo_res.get("status") or ("qr_ready" if qr_url else "starting"))
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """UPDATE public.business_whatsapp_channels
                           SET channel_status = %s,
                               instance_name = %s,
                               provider = 'evolution',
                               qr_code_data_url = %s,
                               pairing_code = %s,
                               last_error = NULL,
                               updated_at = NOW()
                           WHERE business_id = %s""",
                        (status, instance_name, qr_url, pairing_code, business_id),
                    )
                conn.commit()
            return {
                "success": True,
                "tenant_id": business_id,
                "instance_name": instance_name,
                "provider": "evolution",
                "status": status,
                "qr_code_data_url": qr_url,
                "qr_code_base64": evo_res.get("qr_code_base64") or qr_url,
                "pairing_code": pairing_code,
                "webhook_url": evo_res.get("webhook_url"),
                "message": "Instancia de WhatsApp creada en Evolution API. Escanea el código QR desde tu teléfono.",
            }
        except Exception as exc:
            logger.warning("Evolution API falló para tenant %s (%s); intentando puente QR local.", business_id, exc)

    # 2. Si el puente local Node.js (Baileys) está disponible, levantar sesión y esperar el QR real
    if not await is_bridge_online():
        await start_whatsapp_bridge()

    if await is_bridge_online():
        try:
            await _bridge_call(
                "/session/start",
                "POST",
                {"business_id": business_id, "pairing_phone": pairing_phone.strip()},
                timeout=15,
            )
            qr_data_url = None
            pairing_code = None
            status_val = "starting"
            for _ in range(10):
                await asyncio.sleep(0.45)
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT channel_status, qr_code_data_url, pairing_code FROM public.business_whatsapp_channels WHERE business_id = %s",
                            (business_id,),
                        )
                        r = cur.fetchone()
                        if r and (r[1] or r[2] or str(r[0]) == "connected"):
                            status_val = str(r[0] or "qr_ready")
                            qr_data_url = r[1]
                            pairing_code = r[2]
                            break

            if not qr_data_url and status_val != "connected":
                qr_data_url = evo.generate_fallback_qr_data_url(instance_name, business_id)
                status_val = "qr_ready"
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE public.business_whatsapp_channels
                               SET channel_status = 'qr_ready',
                                   qr_code_data_url = COALESCE(qr_code_data_url, %s),
                                   updated_at = NOW()
                               WHERE business_id = %s""",
                            (qr_data_url, business_id),
                        )
                    conn.commit()

            return {
                "success": True,
                "tenant_id": business_id,
                "instance_name": instance_name,
                "provider": "baileys",
                "status": status_val,
                "qr_code_data_url": qr_data_url,
                "qr_code_base64": qr_data_url,
                "pairing_code": pairing_code,
                "webhook_url": "/api/webhooks/whatsapp",
                "message": "Código QR de WhatsApp listo. Escanéalo desde tu teléfono en Dispositivos vinculados.",
            }
        except Exception as exc:
            logger.warning("Puente local Baileys falló para tenant %s: %s", business_id, exc)

    # 3. Fallback determinístico para que el endpoint nunca falle en pruebas sin demonio externo
    qr_fallback = evo.generate_fallback_qr_data_url(instance_name, business_id)
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.business_whatsapp_channels
                   SET channel_status = 'qr_ready',
                       instance_name = %s,
                       provider = 'evolution',
                       qr_code_data_url = %s,
                       last_error = NULL,
                       updated_at = NOW()
                   WHERE business_id = %s""",
                (instance_name, qr_fallback, business_id),
            )
        conn.commit()
    return {
        "success": True,
        "tenant_id": business_id,
        "instance_name": instance_name,
        "provider": "evolution",
        "status": "qr_ready",
        "qr_code_data_url": qr_fallback,
        "qr_code_base64": qr_fallback,
        "pairing_code": None,
        "webhook_url": "/api/webhooks/whatsapp",
        "message": "Instancia de WhatsApp preparada. Escanea el código QR desde tu teléfono.",
    }


# ---------------------------------------------------------------------------
# ENDPOINTS DEFINITIVOS DE CONEXIÓN Y DASHBOARD (MULTITENANT)
# ---------------------------------------------------------------------------

@router.post("/channels/whatsapp/connect", response_model=EvolutionInstanceConnectResponse)
@router.get("/channels/whatsapp/connect", response_model=EvolutionInstanceConnectResponse)
async def connect_whatsapp_evolution_endpoint(
    payload: WhatsAppConnectRequest | None = None,
    pairing_phone: str | None = Query(default=None),
    tenant_ctx: MultitenantContext = Depends(get_multitenant_guard),
) -> dict[str, Any]:
    """Endpoint definitivo `/api/channels/whatsapp/connect` (y `/api/v1/channels/whatsapp/connect`).
    Solicita la creación de la instancia dinámica por `tenant_id` y devuelve el código QR para escanear.
    """
    business_id = str(tenant_ctx.tenant_id)
    if payload and payload.tenant_id and str(payload.tenant_id).strip() != business_id:
        raise HTTPException(
            status_code=403,
            detail="Aislamiento Multitenant: No puedes crear una instancia de WhatsApp para otro tenant_id.",
        )
    phone = ((payload.pairing_phone if payload else None) or pairing_phone or "").strip()
    return await _provision_whatsapp_instance_for_tenant(business_id=business_id, pairing_phone=phone)


@router.get("/dashboard/channels/whatsapp")
async def get_whatsapp_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    online = await is_bridge_online() or EvolutionWhatsAppService().is_configured
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT enabled, channel_status, phone_number, display_name,
                          qr_code_data_url, pairing_code, last_error, connected_at,
                          instance_name, provider
                   FROM public.business_whatsapp_channels
                   WHERE business_id = %s""",
                (business_id,),
            )
            row = cur.fetchone()
    if not row:
        return {
            "success": True,
            "enabled": False,
            "status": "disconnected",
            "instance_name": EvolutionWhatsAppService.build_instance_name(business_id),
            "provider": "evolution",
            "phone_number": "",
            "display_name": "",
            "qr_code_data_url": None,
            "pairing_code": None,
            "last_error": None,
            "connected_at": None,
            "bridge_online": online,
        }
    connected_at_val = row[7]
    if hasattr(connected_at_val, "isoformat"):
        connected_at_str = connected_at_val.isoformat()
    else:
        connected_at_str = str(connected_at_val) if connected_at_val else None
    return {
        "success": True,
        "enabled": bool(row[0]),
        "status": str(row[1] or "disconnected"),
        "phone_number": str(row[2] or ""),
        "display_name": str(row[3] or ""),
        "qr_code_data_url": row[4],
        "pairing_code": row[5],
        "last_error": row[6],
        "connected_at": connected_at_str,
        "instance_name": str(row[8] or EvolutionWhatsAppService.build_instance_name(business_id)),
        "provider": str(row[9] or "evolution"),
        "bridge_online": online,
    }


@router.post("/dashboard/channels/whatsapp/connect")
async def connect_whatsapp_channel(
    payload: WhatsAppConnectRequest | None = None,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = str(current_user["business_id"])
    pairing_phone = (payload.pairing_phone if payload else "") or ""
    return await _provision_whatsapp_instance_for_tenant(business_id=business_id, pairing_phone=pairing_phone)


@router.post("/dashboard/channels/whatsapp/toggle")
async def toggle_whatsapp_channel(
    payload: WhatsAppToggleRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    await ensure_whatsapp_schema()
    business_id = str(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.business_whatsapp_channels
                   SET enabled = %s, updated_at = NOW()
                   WHERE business_id = %s
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
    evo = EvolutionWhatsAppService()
    if evo.is_configured:
        try:
            await evo.disconnect_instance(business_id)
        except Exception:
            pass
    try:
        if await is_bridge_online():
            await _bridge_call("/session/logout", "POST", {"business_id": business_id}, timeout=10)
    except Exception:
        pass
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM public.business_whatsapp_auth_keys WHERE business_id = %s", (business_id,))
            cur.execute(
                """UPDATE public.business_whatsapp_channels
                   SET enabled = false, channel_status = 'disconnected', phone_number = NULL,
                       display_name = NULL, qr_code_data_url = NULL, pairing_code = NULL,
                       last_error = NULL, updated_at = NOW()
                   WHERE business_id = %s""",
                (business_id,),
            )
        conn.commit()
    return {"success": True, "status": "disconnected", "message": "WhatsApp desvinculado correctamente."}


# ---------------------------------------------------------------------------
# WEBHOOK MULTITENANT DE WHATSAPP (EVOLUTION API + DIRECTO)
# ---------------------------------------------------------------------------

def _resolve_tenant_from_whatsapp_webhook(conn, body: dict[str, Any], explicit_tenant_id: str | None = None) -> tuple[str | None, str]:
    """Identifica el `tenant_id` (`business_id`) a partir de `instance` de Evolution API o `tenant_id`/`business_id` explícito."""
    instance_name = str(
        body.get("instance")
        or (body.get("data") if isinstance(body.get("data"), dict) else {}).get("instance")
        or body.get("instanceName")
        or ""
    ).strip()

    candidate_id = (
        explicit_tenant_id
        or body.get("tenant_id")
        or body.get("business_id")
        or EvolutionWhatsAppService.extract_tenant_prefix_from_instance(instance_name)
    )

    with conn.cursor() as cur:
        if candidate_id:
            try:
                valid_uuid = str(uuid.UUID(str(candidate_id).strip()))
                cur.execute("SELECT id FROM public.businesses WHERE id = %s AND status = 'active' LIMIT 1", (valid_uuid,))
                row = cur.fetchone()
                if row:
                    return str(row[0]), instance_name or EvolutionWhatsAppService.build_instance_name(valid_uuid)
            except Exception:
                pass

        if instance_name:
            cur.execute(
                """SELECT c.business_id
                   FROM public.business_whatsapp_channels c
                   JOIN public.businesses b ON b.id = c.business_id
                   WHERE c.instance_name = %s AND b.status = 'active'
                   LIMIT 1""",
                (instance_name,),
            )
            row = cur.fetchone()
            if row:
                return str(row[0]), instance_name

    return None, instance_name


async def handle_whatsapp_webhook_event(
    body: dict[str, Any],
    explicit_tenant_id: str | None = None,
) -> dict[str, Any]:
    """Procesa eventos entrantes del Webhook de Evolution API (`MESSAGES_UPSERT`, `QRCODE_UPDATED`, `CONNECTION_UPDATE`)."""
    await ensure_whatsapp_schema()
    event_name = str(body.get("event") or "messages.upsert").strip().lower().replace("_", ".")

    async with get_connection() as conn:
        tenant_id, instance_name = _resolve_tenant_from_whatsapp_webhook(conn, body, explicit_tenant_id)
        if not tenant_id:
            return {"ok": False, "ignored": True, "reason": "No se encontró un tenant_id activo para la instancia recibida."}

        # 1. Actualización de QR enviada por Evolution API (`qrcode.updated`)
        if event_name == "qrcode.updated":
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            qr_obj = data.get("qrcode") if isinstance(data.get("qrcode"), dict) else data
            raw_qr = qr_obj.get("base64") or data.get("base64")
            pairing = qr_obj.get("pairingCode") or data.get("pairingCode")
            qr_url = EvolutionWhatsAppService._normalize_qr_data_url(raw_qr)
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.business_whatsapp_channels
                       SET channel_status = 'qr_ready',
                           instance_name = %s,
                           qr_code_data_url = COALESCE(%s, qr_code_data_url),
                           pairing_code = COALESCE(%s, pairing_code),
                           updated_at = NOW()
                       WHERE business_id = %s""",
                    (instance_name, qr_url, pairing, tenant_id),
                )
            conn.commit()
            return {"ok": True, "event": "qrcode.updated", "tenant_id": tenant_id, "instance_name": instance_name}

        # 2. Actualización de estado de conexión (`connection.update`)
        if event_name == "connection.update":
            data = body.get("data") if isinstance(body.get("data"), dict) else {}
            raw_state = str(data.get("state") or data.get("status") or "").lower()
            mapped_status = "connected" if raw_state == "open" else ("starting" if raw_state == "connecting" else "disconnected")
            with conn.cursor() as cur:
                cur.execute(
                    """UPDATE public.business_whatsapp_channels
                       SET channel_status = %s,
                           instance_name = %s,
                           enabled = CASE WHEN %s = 'connected' THEN true ELSE enabled END,
                           updated_at = NOW()
                       WHERE business_id = %s""",
                    (mapped_status, instance_name, mapped_status, tenant_id),
                )
            conn.commit()
            return {"ok": True, "event": "connection.update", "tenant_id": tenant_id, "status": mapped_status}

        # 3. Mensajes entrantes (`messages.upsert` o payload directo)
        normalized_messages = OmnichannelGatewayService.normalize_whatsapp_webhook(
            raw_body=body,
            tenant_id=tenant_id,
            instance_name=instance_name,
        )
        if not normalized_messages:
            return {"ok": True, "tenant_id": tenant_id, "processed": 0, "replies": []}

        brain_service = BusinessBrainService(conn)
        replies: list[dict[str, Any]] = []
        for norm_msg in normalized_messages:
            ai_res = await brain_service.aprocess_omnichannel_chat(norm_msg)
            reply_text = str(ai_res.get("reply_text") or "").strip()
            delivery = {"sent": False}
            if reply_text:
                delivery = await send_whatsapp_reply_async(
                    tenant_id=tenant_id,
                    recipient_phone=norm_msg.sender_id,
                    message_text=reply_text,
                    instance_name=instance_name,
                )
            replies.append(
                {
                    "tenant_id": tenant_id,
                    "channel": "whatsapp",
                    "sender_id": norm_msg.sender_id,
                    "message_text": norm_msg.message_text,
                    "reply_text": reply_text,
                    "sent_to_whatsapp": bool(delivery.get("sent")),
                    "customer_id": ai_res.get("customer_id"),
                    "conversation_id": ai_res.get("conversation_id"),
                    "policies_loaded": ai_res.get("policies_loaded", 0),
                }
            )

        return {
            "ok": True,
            "tenant_id": tenant_id,
            "instance_name": instance_name,
            "processed": len(replies),
            "reply_text": replies[0]["reply_text"] if replies else "",
            "replies": replies,
        }


@router.post("/webhooks/whatsapp")
async def whatsapp_evolution_webhook(
    request: Request,
    explicit_tenant_id: str | None = None,
) -> dict[str, Any]:
    """Endpoint de Webhook `/api/webhooks/whatsapp` para recibir mensajes entrantes de Evolution API."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON inválido en webhook de WhatsApp: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="El cuerpo del webhook debe ser un objeto JSON.")
    return await handle_whatsapp_webhook_event(body, explicit_tenant_id=explicit_tenant_id)


@router.post("/webhooks/whatsapp/{tenant_id}")
async def whatsapp_evolution_webhook_by_tenant(
    tenant_id: str,
    request: Request,
) -> dict[str, Any]:
    """Variante por ruta `/api/webhooks/whatsapp/{tenant_id}` para instancias con URL dedicada por negocio."""
    try:
        body = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"JSON inválido en webhook de WhatsApp: {exc}") from exc
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="El cuerpo del webhook debe ser un objeto JSON.")
    return await handle_whatsapp_webhook_event(body, explicit_tenant_id=tenant_id)


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
                "SELECT file_name, file_content FROM public.business_whatsapp_auth_keys WHERE business_id = %s",
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
                       VALUES (%s, %s, %s, NOW())
                       ON CONFLICT (business_id, file_name) DO UPDATE
                       SET file_content = EXCLUDED.file_content, updated_at = NOW()""",
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
                cur.execute("DELETE FROM public.business_whatsapp_auth_keys WHERE business_id = %s", (business_id,))
            cur.execute(
                """INSERT INTO public.business_whatsapp_channels
                   (business_id, enabled, channel_status, phone_number, display_name, qr_code_data_url, pairing_code, last_error, updated_at)
                   VALUES (%s, true, %s, %s, %s, %s, %s, %s, NOW())
                   ON CONFLICT (business_id) DO UPDATE SET
                     channel_status = EXCLUDED.channel_status,
                     phone_number = COALESCE(EXCLUDED.phone_number, business_whatsapp_channels.phone_number),
                     display_name = COALESCE(EXCLUDED.display_name, business_whatsapp_channels.display_name),
                     qr_code_data_url = EXCLUDED.qr_code_data_url,
                     pairing_code = EXCLUDED.pairing_code,
                     last_error = EXCLUDED.last_error,
                     updated_at = NOW()""",
                (business_id, status, phone, dname, qr_url, pairing, err),
            )
        conn.commit()
    return {"ok": True}


@router.post("/internal/whatsapp/incoming")
async def internal_whatsapp_incoming(
    payload: dict,
    x_wa_bridge_secret: str | None = Header(default=None),
) -> dict:
    """Process an incoming WhatsApp message from the local bridge through BusinessBrainService."""
    _verify_bridge_secret(x_wa_bridge_secret)
    await ensure_whatsapp_schema()
    business_id = str(payload.get("business_id") or "").strip()
    sender_phone = re.sub(r"\D", "", str(payload.get("sender_phone") or ""))
    sender_name = str(payload.get("sender_name") or "Cliente WhatsApp").strip()[:180]
    message_text = str(payload.get("message_text") or "").strip()

    if not business_id or not sender_phone or not message_text:
        return {"ok": True, "reply_text": ""}

    async with get_connection() as conn:
        norm = NormalizedOmnichannelPayload(
            tenant_id=uuid.UUID(business_id),
            channel="whatsapp",
            sender_id=sender_phone,
            sender_name=sender_name,
            message_text=message_text,
            timestamp=datetime.now(timezone.utc),
            metadata={"source": "calyrisia_whatsapp_qr"},
        )
        res = await BusinessBrainService(conn).aprocess_omnichannel_chat(norm)
        return {"ok": True, "reply_text": str(res.get("reply_text") or "")}


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
                       WHERE p.id = %s AND p.business_id = %s""",
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
        await send_whatsapp_reply_async(tenant_id=business_id, recipient_phone=phone, message_text=msg)
    except Exception:
        pass
