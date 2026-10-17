from __future__ import annotations

import asyncio
import hmac
import json
import re
import urllib.error
import urllib.request
import uuid
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from psycopg.types.json import Jsonb

from app.api import auth
from app.core.config import get_settings
from app.core.logger import get_logger, request_id_var
from app.db import get_connection
from app.schemas import IncomingMessage
from app.services.autopilot_service import GalaxyAutopilotService
from app.services.commercial_limits import AIQuotaExceeded, consume_ai_response, get_business_plan, plan_limits
from app.services.tenant_guard import TenantGuard, TenantIsolationError

logger = get_logger(__name__)
router = APIRouter()

_poll_supervisor_task: asyncio.Task | None = None
_poll_tasks: dict[str, asyncio.Task] = {}
_poll_tokens: dict[str, str] = {}
_telegram_schema_initialized = False


class TelegramChannelUpdate(BaseModel):
    bot_token: str | None = Field(default=None, max_length=300)
    owner_chat_id: str | None = Field(default=None, max_length=80)


class TelegramChannelToggle(BaseModel):
    enabled: bool


def _settings():
    return get_settings()


def _telegram_api_sync(token: str, method: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict:
    """Call Telegram Bot API. All credentials stay server-side."""
    if not token:
        raise RuntimeError("Falta el token del bot de Telegram.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error_data = json.loads(body)
            description = error_data.get("description") or body
        except Exception:
            description = body or str(exc)
        raise RuntimeError(f"Telegram API {method}: {description}") from exc
    except (urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"No se pudo conectar con Telegram ({method}): {exc}") from exc
    if not result.get("ok"):
        raise RuntimeError(str(result.get("description") or f"Telegram API rechazó {method}."))
    return result


async def _telegram_api(token: str, method: str, payload: dict[str, Any] | None = None, timeout: int = 10) -> dict:
    return await asyncio.to_thread(_telegram_api_sync, token, method, payload, timeout)


async def ensure_telegram_schema() -> None:
    """Idempotent, additive schema for per-business Telegram bots."""
    global _telegram_schema_initialized
    if _telegram_schema_initialized:
        return
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.business_telegram_channels (
                        business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
                        bot_token text NOT NULL,
                        bot_username varchar(80),
                        owner_chat_id varchar(80),
                        enabled boolean NOT NULL DEFAULT false,
                        channel_status varchar(20) NOT NULL DEFAULT 'inactive',
                        polling_offset bigint NOT NULL DEFAULT 0,
                        last_error text,
                        last_poll_at timestamptz,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_business_telegram_bot_token
                    ON public.business_telegram_channels (bot_token)
                """)
            conn.commit()
            _telegram_schema_initialized = True
        except Exception:
            conn.rollback()
            raise


def _normalise(text: str) -> str:
    text = (text or "").lower().strip()
    replacements = str.maketrans({"á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u", "ü": "u"})
    return text.translate(replacements)


def _parse_payment_marker(outbound_texts: list[str]) -> tuple[Decimal | None, list[dict[str, Any]]]:
    for text in outbound_texts:
        match = re.search(
            r"\[BOTON_PAGO\s*:\s*(\d+(?:[.,]\d{1,2})?)(?:\s*\|\s*ITEMS\s*:\s*(\[.*?\]))?\s*\]",
            text or "",
            re.IGNORECASE | re.DOTALL,
        )
        if match:
            try:
                amount = Decimal(match.group(1).replace(",", ".")).quantize(Decimal("0.01"))
            except Exception:
                amount = None
            items: list[dict[str, Any]] = []
            if match.group(2):
                try:
                    parsed = json.loads(match.group(2))
                    if isinstance(parsed, list):
                        items = [x for x in parsed if isinstance(x, dict)]
                except Exception:
                    pass
            return amount, items
        total_match = re.search(r"Total a pagar\s*:\s*(?:USD|VES|\$)?\s*(\d+(?:[.,]\d{1,2})?)", text or "", re.I)
        if total_match:
            try:
                return Decimal(total_match.group(1).replace(",", ".")).quantize(Decimal("0.01")), []
            except Exception:
                pass
    return None, []


def _looks_like_payment_submission(text: str) -> bool:
    value = _normalise(text)
    digits = bool(re.search(r"\d{4,}", value))
    proof_words = (
        "referencia", "nro de operacion", "numero de operacion", "operacion bancaria",
        "comprobante", "captura del pago", "datos del pago", "pago realizado",
        "transferencia realizada", "ya pague", "he pagado", "pague por pago movil",
        "te envie el pago", "te mande el comprobante", "aqui esta el pago", "aqui esta el comprobante",
        "pagado", "pago movil realizado",
    )
    has_proof_language = any(word in value for word in proof_words)
    # Require either an explicit proof/reference phrase, or a clear payment confirmation plus a reference-like number.
    clear_confirmation = any(word in value for word in ("ya pague", "he pagado", "pago realizado", "transferencia realizada", "pagado"))
    explicit_receipt = any(word in value for word in ("comprobante", "referencia", "nro de operacion", "numero de operacion"))
    return has_proof_language and (digits or clear_confirmation or explicit_receipt)


def _clean_for_telegram(text: str) -> tuple[str, Decimal | None, list[dict[str, Any]]]:
    amount, items = _parse_payment_marker([text or ""])
    clean = re.sub(r"\[BOTON_PAGO[^\]]*\]", "", text or "", flags=re.IGNORECASE).strip()
    return clean, amount, items


async def _get_business_label(business_id: str) -> str:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name FROM businesses WHERE id = %s::uuid", (business_id,))
            row = cur.fetchone()
    return str(row[0]) if row and row[0] else "este negocio"


def _is_catalog_question(text: str) -> bool:
    """Recognize catalog intent for a safe read-only fallback when the AI cycle errors."""
    value = _normalise(text)
    terms = (
        "producto", "productos", "precio", "precios", "disponible", "disponibles",
        "catalogo", "que venden", "que tienen", "que hay", "inventario", "stock",
        "cuanto cuesta", "cuanto vale", "cuesta", "costos",
    )
    return any(term in value for term in terms)


async def _catalog_fallback_response(business_id: str) -> str:
    """Read the real tenant catalog; never invent demo products in the recovery path."""
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT name, COALESCE(currency, 'USD') FROM businesses WHERE id = %s::uuid",
                (business_id,),
            )
            business = cur.fetchone()
            business_name = str(business[0]) if business and business[0] else "este negocio"
            currency = str(business[1]) if business and business[1] else "USD"

            rows = []
            has_stock = True
            try:
                cur.execute(
                    """SELECT p.name, p.price, COALESCE(SUM(i.quantity), 0) AS stock
                       FROM products p
                       LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                       WHERE p.business_id = %s::uuid AND p.status = 'active'
                       GROUP BY p.id, p.name, p.price
                       ORDER BY p.name LIMIT 20""",
                    (business_id,),
                )
                rows = cur.fetchall()
            except Exception:
                # Some deployments may not have migrated inventory yet. Recover the
                # transaction and still serve the authoritative product names/prices.
                conn.rollback()
                has_stock = False
                with conn.cursor() as cur2:
                    cur2.execute(
                        """SELECT name, price FROM products
                           WHERE business_id = %s::uuid AND status = 'active'
                           ORDER BY name LIMIT 20""",
                        (business_id,),
                    )
                    rows = cur2.fetchall()

    if not rows:
        return (
            f"Revisé el catálogo de {business_name}, pero no hay productos activos cargados todavía. "
            "El dueño debe añadir o activar los productos en CALYRISIA → Productos para mostrar precios reales."
        )

    lines = []
    for row in rows:
        name = str(row[0] or "Producto")
        raw_price = row[1]
        try:
            price = f"{currency} {float(raw_price):,.2f}" if raw_price is not None else "precio por confirmar"
        except (TypeError, ValueError):
            price = "precio por confirmar"
        line = f"• {name}: {price}"
        if has_stock:
            try:
                quantity = float(row[2] or 0)
                if quantity <= 0:
                    line += " — agotado"
                else:
                    qty_text = str(int(quantity)) if quantity.is_integer() else f"{quantity:g}"
                    line += f" — {qty_text} disponibles"
            except (TypeError, ValueError):
                pass
        lines.append(line)

    return (f"Consulté el catálogo actual de {business_name}:\n" + "\n".join(lines) + "\n\n¿Cuál producto te interesa?")[:3800]


async def _save_catalog_fallback_message(
    *, business_id: str, customer_id: uuid.UUID | None,
    conversation_id: uuid.UUID | None, response_text: str,
) -> None:
    """Best-effort persist the recovery reply in the same conversation history."""
    if not conversation_id:
        return
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO conversation_messages
                       (business_id, conversation_id, customer_id, sender_type, direction,
                        message_type, content, metadata)
                       VALUES (%s::uuid, %s, %s, 'galaxy', 'outbound', 'text', %s, %s::jsonb)""",
                    (business_id, conversation_id, customer_id, response_text,
                     json.dumps({"source": "telegram_catalog_recovery", "fallback": True})),
                )
            conn.commit()
    except Exception:
        logger.exception("No se pudo guardar la respuesta de recuperación del catálogo en el historial.")


async def _send_with_token(token: str, chat_id: str | int, text: str) -> bool:
    if not token or not str(chat_id).strip():
        return False
    try:
        await _telegram_api(token, "sendMessage", {"chat_id": str(chat_id), "text": (text or "")[:4000]}, timeout=12)
        return True
    except Exception as exc:
        logger.warning("No se pudo enviar un mensaje Telegram al chat %s: %s", chat_id, exc)
        return False


async def send_business_telegram_message(business_id: str, chat_id: str | int, text: str) -> bool:
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT bot_token, enabled FROM public.business_telegram_channels WHERE business_id = %s::uuid",
                    (str(business_id),),
                )
                row = cur.fetchone()
        if not row or not row[1]:
            return False
        return await _send_with_token(str(row[0]), chat_id, text)
    except Exception as exc:
        logger.warning("No se pudo cargar el canal Telegram del negocio %s: %s", business_id, exc)
        return False


async def _owner_channel(business_id: str) -> tuple[str | None, str | None]:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bot_token, owner_chat_id FROM public.business_telegram_channels WHERE business_id = %s::uuid AND enabled = true",
                (business_id,),
            )
            row = cur.fetchone()
    if not row:
        return None, None
    return str(row[0]), (str(row[1]) if row[1] else None)


async def _get_business_payment_options(business_id: str) -> list[dict[str, str]]:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT method_code, instructions FROM public.business_payment_instructions WHERE business_id = %s::uuid AND enabled = true ORDER BY method_code", (business_id,))
            rows = cur.fetchall()
    labels = {"pago_movil": "Pago Móvil", "binance": "Binance Pay"}
    return [{"code": str(r[0]), "label": labels.get(str(r[0]), str(r[0])), "instructions": str(r[1] or "")} for r in rows]


async def notify_owner_payment_pending(
    *, business_id: str, payment_id: str, amount: Decimal | float, customer_name: str,
    customer_chat_id: str, payment_details: str, payment_method: str = "Pago Móvil",
    items: list[dict[str, Any]] | None = None,
) -> bool:
    token, owner_chat_id = await _owner_channel(business_id)
    if not token or not owner_chat_id:
        logger.info("Pago Telegram %s pendiente pero el chat personal del dueño no está configurado.", payment_id)
        return False
    business_name = await _get_business_label(business_id)
    item_lines = []
    for item in (items or [])[:12]:
        name = str(item.get("name") or item.get("product_name") or item.get("product") or "Producto")[:100]
        qty = item.get("qty", item.get("quantity", 1))
        item_lines.append(f"• {qty} x {name}")
    order_summary = "\n".join(item_lines) if item_lines else "No se pudieron recuperar los artículos del pedido."
    message = (
        f"🔔 {payment_method.upper()} PENDIENTE DE REVISIÓN\n\n"
        f"Negocio: {business_name}\n"
        f"Cliente: {customer_name}\n"
        f"Monto del pedido: USD {Decimal(str(amount)).quantize(Decimal('0.01'))}\n"
        f"Canal: Telegram\n"
        f"Chat del cliente: {customer_chat_id}\n\n"
        f"Datos/referencia enviados por el cliente:\n{payment_details[:1200]}\n\n"
        f"Artículos:\n{order_summary}\n\n"
        f"Estado: PENDIENTE. Entra al dashboard CALYRISIA → Aprobaciones para revisar y aprobar o rechazar.\n"
        f"Solicitud: {payment_id}"
    )
    return await _send_with_token(token, owner_chat_id, message)


async def notify_payment_decision(business_id: str, payment_id: str, decision: str, amount: float, order_id: str | None = None) -> None:
    """After a dashboard decision, notify Telegram customers only for Telegram-origin requests."""
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT p.source, c.phone, COALESCE(c.full_name, 'Cliente'), p.business_id
                       FROM webchat_payment_requests p
                       JOIN customers c ON c.id = p.customer_id AND c.business_id = p.business_id
                       WHERE p.id = %s::uuid AND p.business_id = %s::uuid""",
                    (payment_id, business_id),
                )
                row = cur.fetchone()
        if not row or str(row[0]).lower() != "telegram" or not row[1]:
            return
        customer_chat = str(row[1])
        if decision == "approve":
            message = f"✅ ¡Pago aprobado por el comercio!\nMonto: USD {amount:.2f}. Pedido confirmado. ¡Gracias por comprar con {await _get_business_label(business_id)}!"
            if order_id:
                message += f"\nPedido: {order_id}"
        else:
            message = f"❌ Tu solicitud de pago por USD {amount:.2f} fue rechazada por el comercio. Por favor, contacta al negocio para coordinar cómo proceder."
        await send_business_telegram_message(business_id, customer_chat, message)
    except Exception as exc:
        logger.warning("No se pudo notificar la decisión del pago %s por Telegram: %s", payment_id, exc)


async def _get_recent_outbound(business_id: str, customer_id: uuid.UUID, conversation_id: uuid.UUID) -> list[str]:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT content FROM conversation_messages
                   WHERE business_id = %s::uuid AND customer_id = %s AND conversation_id = %s
                     AND direction = 'outbound'
                   ORDER BY created_at DESC LIMIT 12""",
                (business_id, customer_id, conversation_id),
            )
            return [str(row[0] or "") for row in cur.fetchall()]


async def _create_telegram_payment(
    *, business_id: str, customer_id: uuid.UUID, chat_id: str, customer_name: str,
    amount: Decimal, items: list[dict[str, Any]], payment_details: str, payment_method: str,
) -> tuple[str, bool]:
    """Create one pending payment per submission; returns (payment id, newly created)."""
    payment_id = uuid.uuid4()
    created = True
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Prevent duplicate notifications when the customer resends the same receipt.
                cur.execute(
                    """SELECT id FROM webchat_payment_requests
                       WHERE business_id = %s::uuid AND customer_id = %s AND source = 'telegram'
                         AND status = 'pending' AND created_at >= now() - interval '30 minutes'
                       ORDER BY created_at DESC LIMIT 1 FOR UPDATE""",
                    (business_id, customer_id),
                )
                prior = cur.fetchone()
                if prior:
                    payment_id = prior[0]
                    created = False
                    cur.execute(
                        """UPDATE webchat_payment_requests
                           SET customer_payment_details = %s, payment_method = %s
                           WHERE id = %s AND business_id = %s::uuid""",
                        (payment_details[:4000], payment_method, payment_id, business_id),
                    )
                else:
                    cur.execute(
                        """INSERT INTO webchat_payment_requests
                           (id, business_id, customer_id, amount, currency, payment_method, status, source,
                            approval_note, items, customer_payment_details)
                           VALUES (%s, %s::uuid, %s, %s, 'USD', %s, 'pending', 'telegram',
                                   'Solicitud recibida por Telegram; pendiente de aprobación del dueño.', %s, %s)""",
                        (payment_id, business_id, customer_id, amount, payment_method, Jsonb(items) if items else None, payment_details[:4000]),
                    )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
    if created:
        await notify_owner_payment_pending(
            business_id=business_id,
            payment_id=str(payment_id),
            amount=amount,
            customer_name=customer_name,
            customer_chat_id=chat_id,
            payment_details=payment_details,
            payment_method=payment_method,
            items=items,
        )
    return str(payment_id), created


async def _ensure_customer_and_conversation(business_id: str, chat: dict, sender: dict) -> tuple[uuid.UUID, uuid.UUID, str]:
    chat_id = str(chat.get("id", ""))
    first = str(sender.get("first_name") or "Usuario Telegram").strip()
    last = str(sender.get("last_name") or "").strip()
    display_name = (first + " " + last).strip()[:150] or "Usuario Telegram"
    customer_id: uuid.UUID
    conversation_id: uuid.UUID
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT id FROM customers
                   WHERE business_id = %s::uuid AND source = 'telegram' AND phone = %s LIMIT 1""",
                (business_id, chat_id),
            )
            row = cur.fetchone()
            if row:
                customer_id = row[0]
                # Update only the display name; do not append the Telegram username
                # to notes on every message (schema-dependent and creates duplicate notes).
                cur.execute(
                    "UPDATE customers SET full_name = %s WHERE id = %s AND business_id = %s::uuid",
                    (display_name, customer_id, business_id),
                )
            else:
                customer_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO customers (id, business_id, full_name, source, phone, status)
                       VALUES (%s, %s::uuid, %s, 'telegram', %s, 'active')""",
                    (customer_id, business_id, display_name, chat_id),
                )
            cur.execute(
                """SELECT id FROM conversations
                   WHERE business_id = %s::uuid AND customer_id = %s AND channel = 'telegram' AND status = 'active'
                   ORDER BY created_at DESC LIMIT 1""",
                (business_id, customer_id),
            )
            conv_row = cur.fetchone()
            if conv_row:
                conversation_id = conv_row[0]
            else:
                conversation_id = uuid.uuid4()
                cur.execute(
                    """INSERT INTO conversations (id, business_id, customer_id, channel, status, metadata)
                       VALUES (%s, %s::uuid, %s, 'telegram', 'active', %s::jsonb)""",
                    (conversation_id, business_id, customer_id, Jsonb({"channel": "telegram", "external_chat_id": chat_id})),
                )
        conn.commit()
    return customer_id, conversation_id, display_name


async def process_telegram_update(update: dict, business_id: str, token: str, req_id: str | None = None) -> None:
    """Tenant-safe handler shared by local polling and the optional legacy webhook."""
    if req_id:
        request_id_var.set(req_id)
    message = update.get("message") or update.get("edited_message") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    text = str(message.get("text") or message.get("caption") or "").strip()
    if not chat.get("id"):
        return
    chat_id = str(chat["id"])

    if not text:
        await _send_with_token(token, chat_id, "Puedo leer los datos de Pago Móvil cuando me los envíes como texto. Escribe la referencia/operación del pago para dejarlo pendiente de revisión.")
        return

    command = text.split()[0].split("@")[0].lower() if text.startswith("/") else ""
    if command in {"/id", "/chatid"}:
        await _send_with_token(token, chat_id, f"Tu Telegram chat ID es: {chat_id}\nColoca ese número en CALYRISIA → Canales → Chat ID del dueño para recibir alertas de pagos.")
        return
    if command in {"/start", "/help"}:
        label = await _get_business_label(business_id)
        await _send_with_token(
            token,
            chat_id,
            f"¡Hola! Soy el asistente de {label}. Puedes consultarme productos, precios, pedidos y formas de pago.\n\nPara conocer tu chat ID usa /id.",
        )
        return

    customer_id: uuid.UUID | None = None
    conversation_id: uuid.UUID | None = None
    customer_name = str(sender.get("first_name") or "Cliente Telegram")
    try:
        # Resolve the tenant from the token currently being polled, not from user-supplied message data.
        async with get_connection() as conn:
            TenantGuard(conn).require_business(business_id)
        customer_id, conversation_id, customer_name = await _ensure_customer_and_conversation(business_id, chat, sender)

        outbound = await _get_recent_outbound(business_id, customer_id, conversation_id)
        prior_amount, prior_items = _parse_payment_marker(outbound)
        if prior_amount is not None and prior_amount > 0 and _looks_like_payment_submission(text):
            payment_options = await _get_business_payment_options(business_id)
            if not payment_options:
                await _send_with_token(token, chat_id, "Este negocio aún no ha configurado métodos de cobro en CALYRISIA. Por seguridad, no envíes dinero ni datos de pago; contacta directamente con el comercio.")
                return
            normalized_proof = _normalise(text)
            selected_option = None
            if len(payment_options) == 1:
                selected_option = payment_options[0]
            elif "binance" in normalized_proof:
                selected_option = next((option for option in payment_options if option["code"] == "binance"), None)
            elif "pago movil" in normalized_proof or "pago móvil" in text.lower():
                selected_option = next((option for option in payment_options if option["code"] == "pago_movil"), None)
            if selected_option is None:
                choices = " o ".join(option["label"] for option in payment_options)
                await _send_with_token(token, chat_id, f"Antes de registrar la referencia, indica qué método utilizaste ({choices}) y vuelve a enviar el detalle de la operación en el mismo mensaje.")
                return
            payment_method_label = selected_option["label"] + " (Telegram)"
            payment_id, newly_created = await _create_telegram_payment(
                business_id=business_id,
                customer_id=customer_id,
                chat_id=chat_id,
                customer_name=customer_name,
                amount=prior_amount,
                items=prior_items,
                payment_details=text,
                payment_method=payment_method_label,
            )
            if newly_created:
                reply = (
                    f"✅ Recibí tus datos de {selected_option['label']} para USD {prior_amount:.2f}.\n"
                    f"Tu pago quedó PENDIENTE de revisión del comercio. Te aviso por aquí cuando el dueño lo apruebe o rechace.\n"
                    f"Referencia de solicitud: {payment_id[:8].upper()}"
                )
            else:
                reply = (
                    f"📌 Tu solicitud de pago {payment_id[:8].upper()} ya está pendiente de revisión. "
                    "Actualicé los datos enviados; el dueño la revisará desde CALYRISIA."
                )
            await _send_with_token(token, chat_id, reply)
            return

        payload = IncomingMessage(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            channel="telegram",
            message=text,
            metadata={"channel": "telegram", "external_chat_id": chat_id, "telegram_username": sender.get("username")},
        )
        async with get_connection() as conn:
            consume_ai_response(conn, business_id)
            result = GalaxyAutopilotService(conn).respond(payload)
        response_text = str(result.get("response") or "No pude generar una respuesta. Inténtalo de nuevo.")
        clean_response, pay_amount, _pay_items = _clean_for_telegram(response_text)
        if pay_amount is not None and pay_amount > 0:
            label = await _get_business_label(business_id)
            payment_options = await _get_business_payment_options(business_id)
            if payment_options:
                details = "\n\n".join(f"{option['label']}:\n{option['instructions']}" for option in payment_options)
                payment_info = (
                    f"\n\n💳 INSTRUCCIONES DE PAGO · USD {pay_amount:.2f}\n"
                    f"{details}\n\n"
                    "Cuando completes el pago, envíame la referencia o los datos de la operación por este chat. "
                    "Si hay varios métodos, incluye también en el mismo mensaje el nombre del que utilizaste (por ejemplo, Pago Móvil o Binance Pay). "
                    "La solicitud quedará pendiente de revisión por el comercio."
                )
            else:
                payment_info = (
                    f"\n\nEl monto de referencia de tu pedido es USD {pay_amount:.2f}. "
                    "Este comercio todavía no ha configurado sus instrucciones de pago en CALYRISIA. "
                    "Por seguridad, no transfieras dinero hasta recibir instrucciones oficiales directamente del negocio."
                )
            clean_response = (clean_response + payment_info).strip()
        if not clean_response:
            clean_response = "¿En qué puedo ayudarte?"
        await _send_with_token(token, chat_id, clean_response)
        logger.info("Telegram message completed for business_id=%s customer_id=%s", business_id, customer_id)
    except AIQuotaExceeded as exc:
        logger.info("Monthly AI quota reached for business_id=%s limit=%s", business_id, exc.limit)
        await _send_with_token(token, chat_id, f"Has alcanzado las {exc.limit} respuestas de IA incluidas en el plan este mes. Contacta con CALYRISIA para ampliar tu capacidad o cambiar de plan.")
    except TenantIsolationError as exc:
        logger.error("Telegram tenant binding is invalid: %s", exc)
        await _send_with_token(token, chat_id, "Este canal no está correctamente vinculado a un negocio. Contacta al administrador.")
    except Exception as exc:
        logger.exception("Telegram processing failure for business_id=%s: %s", business_id, exc)
        # The shared AI brain remains the primary path. If it fails during a catalog
        # request, degrade gracefully to the same tenant's real DB catalog instead of
        # making the customer see a generic technical error.
        if _is_catalog_question(text):
            try:
                fallback_text = await _catalog_fallback_response(business_id)
                await _save_catalog_fallback_message(
                    business_id=business_id,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    response_text=fallback_text,
                )
                await _send_with_token(token, chat_id, fallback_text)
                logger.warning(
                    "Telegram served read-only catalog fallback after AI error (business_id=%s, error_type=%s)",
                    business_id, type(exc).__name__,
                )
                return
            except Exception:
                logger.exception("Telegram catalog recovery also failed for business_id=%s", business_id)
        await _send_with_token(token, chat_id, "Lo siento, estamos experimentando problemas técnicos. Inténtalo nuevamente en unos minutos.")


async def _load_enabled_channels() -> list[dict[str, Any]]:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT business_id::text, bot_token, COALESCE(polling_offset, 0)
                   FROM public.business_telegram_channels WHERE enabled = true"""
            )
            return [{"business_id": r[0], "bot_token": r[1], "polling_offset": int(r[2] or 0)} for r in cur.fetchall()]


async def _set_channel_poll_state(business_id: str, *, offset: int | None = None, status: str | None = None, error: str | None = None) -> None:
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                fields = ["updated_at = now()"]
                params: list[Any] = []
                if offset is not None:
                    fields.append("polling_offset = %s")
                    params.append(offset)
                if status is not None:
                    fields.append("channel_status = %s")
                    params.append(status)
                fields.append("last_error = %s")
                params.append(error[:1000] if error else None)
                if status == "active":
                    fields.append("last_poll_at = now()")
                params.append(business_id)
                cur.execute(
                    f"UPDATE public.business_telegram_channels SET {', '.join(fields)} WHERE business_id = %s::uuid",
                    params,
                )
            conn.commit()
    except Exception as exc:
        logger.debug("Could not update Telegram polling state: %s", exc)


async def _poll_bot_channel(business_id: str, token: str) -> None:
    next_offset = 0
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT polling_offset FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                row = cur.fetchone()
                if row:
                    next_offset = int(row[0] or 0)
        while True:
            try:
                payload: dict[str, Any] = {"timeout": 1, "allowed_updates": ["message"]}
                if next_offset:
                    payload["offset"] = next_offset
                response = await _telegram_api(token, "getUpdates", payload, timeout=5)
                await _set_channel_poll_state(business_id, offset=next_offset, status="active", error=None)
                updates = response.get("result") or []
                for update in updates:
                    update_id = int(update.get("update_id", 0))
                    try:
                        await process_telegram_update(update, business_id, token, f"tg-{business_id}-{update_id}")
                    finally:
                        next_offset = max(next_offset, update_id + 1)
                        await _set_channel_poll_state(business_id, offset=next_offset, status="active", error=None)
                if not updates:
                    await asyncio.sleep(0.3)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                error = str(exc)
                await _set_channel_poll_state(business_id, status="error", error=error)
                logger.warning("Telegram polling error for business_id=%s: %s", business_id, error)
                await asyncio.sleep(5)
    except asyncio.CancelledError:
        raise


async def _polling_supervisor() -> None:
    global _poll_tasks, _poll_tokens
    while True:
        try:
            configs = await _load_enabled_channels()
            desired = {str(row["business_id"]): str(row["bot_token"]) for row in configs}
            for business_id, task in list(_poll_tasks.items()):
                if business_id not in desired or _poll_tokens.get(business_id) != desired[business_id]:
                    task.cancel()
                    try:
                        await task
                    except (asyncio.CancelledError, Exception):
                        pass
                    _poll_tasks.pop(business_id, None)
                    _poll_tokens.pop(business_id, None)
            for business_id, token in desired.items():
                if business_id not in _poll_tasks or _poll_tasks[business_id].done():
                    _poll_tokens[business_id] = token
                    _poll_tasks[business_id] = asyncio.create_task(_poll_bot_channel(business_id, token))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.debug("Telegram supervisor waiting for database/schema: %s", exc)
        await asyncio.sleep(3)


async def start_telegram_polling() -> None:
    global _poll_supervisor_task
    if _poll_supervisor_task is None or _poll_supervisor_task.done():
        _poll_supervisor_task = asyncio.create_task(_polling_supervisor(), name="calyrisia-telegram-polling-supervisor")


async def stop_telegram_polling() -> None:
    global _poll_supervisor_task, _poll_tasks, _poll_tokens
    if _poll_supervisor_task:
        _poll_supervisor_task.cancel()
        try:
            await _poll_supervisor_task
        except asyncio.CancelledError:
            pass
        _poll_supervisor_task = None
    for task in list(_poll_tasks.values()):
        task.cancel()
    for task in list(_poll_tasks.values()):
        try:
            await task
        except (asyncio.CancelledError, Exception):
            pass
    _poll_tasks = {}
    _poll_tokens = {}


@router.get("/dashboard/channels/telegram")
async def get_telegram_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    try:
        await ensure_telegram_schema()
        business_id = str(current_user["business_id"])
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT bot_token, bot_username, owner_chat_id, enabled, channel_status, last_error, last_poll_at
                       FROM public.business_telegram_channels WHERE business_id = %s::uuid""",
                    (business_id,),
                )
                row = cur.fetchone()
        if not row:
            return {"success": True, "configured": False, "enabled": False, "status": "inactive", "bot_username": None, "owner_chat_id": "", "token_hint": ""}
        token = str(row[0] or "")
        return {
            "success": True,
            "configured": bool(token),
            "enabled": bool(row[3]),
            "status": str(row[4] or "inactive"),
            "bot_username": str(row[1]) if row[1] else None,
            "owner_chat_id": str(row[2]) if row[2] else "",
            "token_hint": f"••••{token[-4:]}" if token else "",
            "last_error": str(row[5]) if row[5] else None,
            "last_poll_at": row[6].isoformat() if row[6] else None,
        }
    except Exception as exc:
        logger.exception("Could not read Telegram channel config")
        raise HTTPException(status_code=503, detail=f"No se pudo leer la configuración de Telegram: {exc}") from exc


@router.put("/dashboard/channels/telegram")
async def save_telegram_channel(payload: TelegramChannelUpdate, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = str(current_user["business_id"])
    try:
        await ensure_telegram_schema()
        async with get_connection() as conn:
            plan_code = get_business_plan(conn, business_id)
            limits = plan_limits(plan_code)
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM public.businesses WHERE id = %s::uuid", (business_id,))
                webchat_row = cur.fetchone()
                webchat_enabled = bool(webchat_row[0]) if webchat_row else False
                cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                old_enabled_row = cur.fetchone()
                telegram_was_enabled = bool(old_enabled_row[0]) if old_enabled_row else False
                if not telegram_was_enabled and webchat_enabled and limits["channels"] < 2:
                    raise HTTPException(status_code=409, detail=f"El plan {limits['label']} incluye un solo canal activo. Desactiva Webchat en Dashboard → Canales antes de activar Telegram, o cambia a Smart Business.")
                cur.execute("SELECT bot_token FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                existing = cur.fetchone()
        submitted_token = (payload.bot_token or "").strip()
        token = submitted_token or (str(existing[0]) if existing else "")
        if not token:
            raise HTTPException(status_code=422, detail="Pega el token del bot obtenido desde @BotFather.")
        owner_chat_id = (payload.owner_chat_id or "").strip()
        if owner_chat_id and not re.fullmatch(r"-?\d{1,30}", owner_chat_id):
            raise HTTPException(status_code=422, detail="El Chat ID del dueño debe ser numérico. En Telegram abre tu bot y envía /id.")
        try:
            me = await _telegram_api(token, "getMe", {}, timeout=10)
            bot_user = me.get("result") or {}
            if not bot_user.get("is_bot"):
                raise RuntimeError("El token no pertenece a un bot.")
            bot_username = str(bot_user.get("username") or "")
            # Local Uvicorn uses polling; Telegram refuses getUpdates while a webhook remains configured.
            await _telegram_api(token, "deleteWebhook", {"drop_pending_updates": False}, timeout=10)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=f"No se pudo validar el token de Telegram: {exc}") from exc

        async with get_connection() as conn:
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT business_id::text FROM public.business_telegram_channels
                           WHERE bot_token = %s AND business_id <> %s::uuid LIMIT 1""",
                        (token, business_id),
                    )
                    duplicate = cur.fetchone()
                    if duplicate:
                        raise HTTPException(status_code=409, detail="Este bot de Telegram ya está vinculado a otro negocio. Usa un bot distinto para cada negocio.")
                    cur.execute(
                        """INSERT INTO public.business_telegram_channels
                           (business_id, bot_token, bot_username, owner_chat_id, enabled, channel_status, polling_offset, last_error, updated_at)
                           VALUES (%s::uuid, %s, %s, %s, true, 'starting', 0, NULL, now())
                           ON CONFLICT (business_id) DO UPDATE SET
                             bot_token = EXCLUDED.bot_token,
                             bot_username = EXCLUDED.bot_username,
                             owner_chat_id = EXCLUDED.owner_chat_id,
                             enabled = true,
                             channel_status = 'starting',
                             polling_offset = CASE WHEN business_telegram_channels.bot_token = EXCLUDED.bot_token
                                                   THEN business_telegram_channels.polling_offset ELSE 0 END,
                             last_error = NULL,
                             updated_at = now()""",
                        (business_id, token, bot_username, owner_chat_id or None),
                    )
                conn.commit()
            except HTTPException:
                conn.rollback()
                raise
            except Exception:
                conn.rollback()
                raise
        return {"success": True, "message": f"Bot @{bot_username} validado. Telegram está activándose en modo local.", "bot_username": bot_username, "enabled": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not save Telegram channel config")
        raise HTTPException(status_code=500, detail=f"No se pudo guardar Telegram: {exc}") from exc


@router.post("/dashboard/channels/telegram/toggle")
async def toggle_telegram_channel(payload: TelegramChannelToggle, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await ensure_telegram_schema()
    business_id = str(current_user["business_id"])
    async with get_connection() as conn:
        if payload.enabled:
            plan_code = get_business_plan(conn, business_id)
            limits = plan_limits(plan_code)
            with conn.cursor() as cur:
                cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM public.businesses WHERE id = %s::uuid", (business_id,))
                webchat_row = cur.fetchone()
                webchat_enabled = bool(webchat_row[0]) if webchat_row else False
                cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                existing_row = cur.fetchone()
                already_enabled = bool(existing_row[0]) if existing_row else False
                if not already_enabled and webchat_enabled and limits["channels"] < 2:
                    raise HTTPException(status_code=409, detail=f"El plan {limits['label']} incluye un solo canal activo. Desactiva Webchat primero o cambia a Smart Business.")
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE public.business_telegram_channels
                   SET enabled = %s, channel_status = %s, last_error = NULL, updated_at = now()
                   WHERE business_id = %s::uuid AND bot_token IS NOT NULL RETURNING enabled""",
                (payload.enabled, "starting" if payload.enabled else "inactive", business_id),
            )
            row = cur.fetchone()
        conn.commit()
    if not row:
        raise HTTPException(status_code=404, detail="Primero configura y valida el token del bot.")
    return {"success": True, "enabled": bool(row[0]), "status": "starting" if row[0] else "inactive"}


@router.post("/dashboard/channels/telegram/test")
async def test_telegram_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = str(current_user["business_id"])
    token, owner_chat_id = await _owner_channel(business_id)
    if not token:
        raise HTTPException(status_code=409, detail="Configura y activa primero tu bot de Telegram.")
    if not owner_chat_id:
        raise HTTPException(status_code=422, detail="Añade el Chat ID del dueño. Abre tu bot en Telegram, envía /id y pega el número aquí.")
    label = await _get_business_label(business_id)
    sent = await _send_with_token(token, owner_chat_id, f"✅ Prueba de CALYRISIA\nNegocio: {label}\nLas alertas de pagos pendientes llegarán a este chat.")
    if not sent:
        raise HTTPException(status_code=502, detail="No se pudo entregar el mensaje. Abre el bot en Telegram y pulsa Iniciar; revisa el Chat ID.")
    return {"success": True, "message": "Mensaje de prueba enviado al Telegram del dueño."}


@router.post("/webhook/telegram")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    """Legacy webhook compatibility. Local testing should use the dashboard-configured polling worker."""
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    request_id_var.set(req_id)
    settings = _settings()
    expected_secret = settings.telegram_webhook_secret.strip()
    business_id = settings.telegram_business_id.strip()
    token = settings.telegram_bot_token.strip()
    if not expected_secret or not business_id or not token:
        raise HTTPException(status_code=503, detail="Webhook heredado no configurado; configura Telegram en el dashboard.")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(x_telegram_bot_api_secret_token, expected_secret):
        logger.warning("Rejected Telegram webhook with invalid provider secret.")
        raise HTTPException(status_code=401, detail="Unauthorized webhook")
    update = await request.json()
    background_tasks.add_task(process_telegram_update, update, business_id, token, req_id)
    return {"status": "ok", "request_id": req_id}
