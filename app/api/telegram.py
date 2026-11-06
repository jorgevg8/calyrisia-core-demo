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
try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

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
                        auth_mode varchar(20) NOT NULL DEFAULT 'bot',
                        phone_number varchar(40),
                        session_string text,
                        api_id bigint,
                        api_hash text,
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


# Per-conversation memory for two-step payment reporting (e.g., customer sends "referencia 115892330" then "Pago movil", or vice versa)
_pending_tg_payment_context: dict[str, dict[str, Any]] = {}


def _match_payment_option_from_text(text: str, payment_options: list[dict[str, str]]) -> dict[str, str] | None:
    norm = _normalise(text)
    if not norm or not payment_options:
        return None
    for option in payment_options:
        code = str(option.get("code") or "").lower()
        label_norm = _normalise(option.get("label") or "")
        if code and (code in norm or code.replace("_", " ") in norm):
            return option
        if label_norm and label_norm in norm:
            return option
        if code == "pago_movil" and ("pago movil" in norm or "pagomovil" in norm or "movil" in norm):
            return option
        if code == "binance" and ("binance" in norm or "usdt" in norm):
            return option
        if code == "zelle" and "zelle" in norm:
            return option
        if code == "transferencia" and ("transferencia" in norm or "banco" in norm):
            return option
        if code == "paypal" and "paypal" in norm:
            return option
    return None


def _looks_like_payment_submission(text: str) -> bool:
    value = _normalise(text)
    digits = bool(re.search(r"\d{4,}", value))
    # Pure reference number (6 to 20 digits) when replying to a payment prompt
    if re.fullmatch(r"\s*(?:ref(?:erencia)?[:.#\-\s]*)?\d{5,20}\s*", value):
        return True
    proof_words = (
        "referencia", "ref ", "ref:", "ref#", "nro de operacion", "numero de operacion", "operacion bancaria",
        "operacion", "comprobante", "captura", "capture", "datos del pago", "pago realizado",
        "transferencia realizada", "ya pague", "he pagado", "pague", "pago movil", "pagomovil",
        "binance", "zelle", "transferencia", "paypal",
        "te envie el pago", "te mande el comprobante", "aqui esta el pago", "aqui esta el comprobante",
        "pagado", "pago movil realizado",
    )
    has_proof_language = any(word in value for word in proof_words)
    clear_confirmation = any(word in value for word in ("ya pague", "he pagado", "pago realizado", "transferencia realizada", "pagado"))
    explicit_receipt = any(word in value for word in ("comprobante", "referencia", "nro de operacion", "numero de operacion"))
    return has_proof_language and (digits or clear_confirmation or explicit_receipt)


def _clean_for_telegram(text: str) -> tuple[str, Decimal | None, list[dict[str, Any]]]:
    amount, items = _parse_payment_marker([text or ""])
    clean = re.sub(r"\[BOTON_PAGO:\s*[\d.,]+(?:\s*\|\s*ITEMS:\s*\[[\s\S]*?\])?\s*\]", "", text or "", flags=re.IGNORECASE)
    clean = re.sub(r"\[BOTON_PAGO[^\]]*\]", "", clean, flags=re.IGNORECASE)
    clean = re.sub(r"(?:^|\n)\s*\]\s*$", "", clean).strip()
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
    labels = {"pago_movil": "Pago Móvil", "transferencia": "Transferencia Bancaria", "zelle": "Zelle", "binance": "Binance Pay", "paypal": "PayPal"}
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
                     AND created_at >= now() - interval '2 hours'
                   ORDER BY created_at DESC LIMIT 4""",
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
        welcome_text = f"¡Hola! Bienvenido a {label}, ¿en qué te puedo ayudar?"
        if command == "/help":
            welcome_text += "\n\nPuedes consultarme por nuestros productos disponibles, precios, horarios, ubicación o métodos de pago. Para conocer tu chat ID usa /id."
        try:
            cust_id, conv_id, _ = await _ensure_customer_and_conversation(business_id, chat, sender)
            await _save_catalog_fallback_message(
                business_id=business_id,
                customer_id=cust_id,
                conversation_id=conv_id,
                response_text=welcome_text,
            )
        except Exception:
            pass
        await _send_with_token(token, chat_id, welcome_text)
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
        conv_key = f"{business_id}:{conversation_id}"
        pending_ctx = _pending_tg_payment_context.get(conv_key) or {}

        if prior_amount is not None and prior_amount > 0:
            payment_options = await _get_business_payment_options(business_id)
            matched_opt = _match_payment_option_from_text(text, payment_options)
            is_sub = _looks_like_payment_submission(text)

            # Recover reference from outbound history if server restarted after asking for payment method
            recovered_ref = pending_ctx.get("reference_text")
            if not recovered_ref and outbound:
                m_ref = re.search(r"Recibí tu referencia \(([^)]+)\)", outbound[0])
                if m_ref:
                    recovered_ref = m_ref.group(1).strip()

            # Case A: User previously sent the reference (e.g. "referencia 115892330") and now replies with the method (e.g. "Pago movil")
            if recovered_ref and matched_opt and not is_sub:
                pending_ctx["reference_text"] = recovered_ref
                combined_details = f"{matched_opt['label']} — {pending_ctx['reference_text']}"
                _pending_tg_payment_context.pop(conv_key, None)
                payment_method_label = matched_opt["label"] + " (Telegram)"
                payment_id, newly_created = await _create_telegram_payment(
                    business_id=business_id,
                    customer_id=customer_id,
                    chat_id=chat_id,
                    customer_name=customer_name,
                    amount=prior_amount,
                    items=prior_items,
                    payment_details=combined_details,
                    payment_method=payment_method_label,
                )
                reply = (
                    f"✅ Recibí tus datos de {matched_opt['label']} ({pending_ctx['reference_text']}) para USD {prior_amount:.2f}.\n"
                    f"Tu pago quedó PENDIENTE de revisión del comercio. Te aviso por aquí cuando el dueño lo apruebe o rechace.\n"
                    f"Referencia de solicitud: {payment_id[:8].upper()}"
                    if newly_created
                    else f"📌 Tu solicitud de pago {payment_id[:8].upper()} ya está pendiente de revisión. Actualicé los datos enviados."
                )
                await _save_catalog_fallback_message(
                    business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
                )
                await _send_with_token(token, chat_id, reply)
                return

            # Case B: User selects the payment method first (e.g. "Pago movil") before sending the reference digits
            if matched_opt and not is_sub and len(_normalise(text).split()) <= 5:
                _pending_tg_payment_context[conv_key] = {"selected_option": matched_opt}
                reply = (
                    f"¡Perfecto! Anoté {matched_opt['label']} para tu pedido de USD {prior_amount:.2f}.\n\n"
                    f"▸ Datos de {matched_opt['label']}:\n{matched_opt['instructions']}\n\n"
                    f"Envíame por aquí el número de referencia o comprobante de tu operación para registrarlo."
                )
                await _save_catalog_fallback_message(
                    business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
                )
                await _send_with_token(token, chat_id, reply)
                return

            # Case C: User sends the payment reference / receipt
            if is_sub:
                if not payment_options:
                    await _send_with_token(token, chat_id, "Este negocio aún no ha configurado métodos de cobro en CALYRISIA. Por seguridad, no envíes dinero ni datos de pago; contacta directamente con el comercio.")
                    return
                selected_option = matched_opt
                if selected_option is None and len(payment_options) == 1:
                    selected_option = payment_options[0]
                if selected_option is None and pending_ctx.get("selected_option"):
                    selected_option = pending_ctx["selected_option"]
                if selected_option is None:
                    # Save the reference in context so when the user replies "Pago movil" or "Binance", we complete it immediately!
                    _pending_tg_payment_context[conv_key] = {"reference_text": text}
                    choices = " o ".join(option["label"] for option in payment_options)
                    ask_method_msg = (
                        f"Recibí tu referencia ({text}). Para terminar de registrarla, "
                        f"respóndeme qué método de pago utilizaste ({choices})."
                    )
                    await _save_catalog_fallback_message(
                        business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=ask_method_msg
                    )
                    await _send_with_token(token, chat_id, ask_method_msg)
                    return
                _pending_tg_payment_context.pop(conv_key, None)
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
                await _save_catalog_fallback_message(
                    business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
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
                   FROM public.business_telegram_channels
                   WHERE enabled = true AND COALESCE(auth_mode, 'bot') = 'bot'"""
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
    for business_id in list(globals().get("_active_userbot_clients", {}).keys()):
        await stop_telegram_user_listener(business_id)




@router.get("/dashboard/channels/telegram")
async def get_telegram_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    try:
        await _ensure_telegram_mtproto_columns()
        business_id = str(current_user["business_id"])
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT bot_token, bot_username, owner_chat_id, enabled, channel_status,
                              last_error, last_poll_at, COALESCE(auth_mode, 'bot'), phone_number
                       FROM public.business_telegram_channels WHERE business_id = %s::uuid""",
                    (business_id,),
                )
                row = cur.fetchone()
        if not row:
            return {
                "success": True,
                "configured": False,
                "enabled": False,
                "status": "inactive",
                "auth_mode": "phone",
                "phone_number": "",
                "bot_username": None,
                "owner_chat_id": "",
                "token_hint": "",
            }
        token = str(row[0] or "")
        auth_mode = str(row[7] or "bot")
        phone_number = str(row[8] or "")
        is_configured = bool(token or phone_number)
        status_val = str(row[4] or ("active" if row[3] else "inactive"))
        if auth_mode == "phone" and row[3] and business_id in _active_userbot_clients:
            status_val = "active"
        return {
            "success": True,
            "configured": is_configured,
            "enabled": bool(row[3]),
            "status": status_val,
            "auth_mode": auth_mode,
            "phone_number": phone_number,
            "bot_username": str(row[1]) if row[1] else None,
            "owner_chat_id": str(row[2]) if row[2] else "",
            "token_hint": f"••••{token[-4:]}" if token and not token.startswith("mtproto_") else "",
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
        await _ensure_telegram_mtproto_columns()
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT bot_token FROM public.business_telegram_channels WHERE business_id = %s::uuid", (business_id,))
                existing = cur.fetchone()
        submitted_token = (payload.bot_token or "").strip()
        token = submitted_token or (str(existing[0]) if existing else "")
        if not token or token.startswith("mtproto_"):
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
                             auth_mode = 'bot',
                             phone_number = NULL,
                             session_string = NULL,
                             api_id = NULL,
                             api_hash = NULL,
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
        await stop_telegram_user_listener(business_id)
        return {"success": True, "message": f"Bot @{bot_username} validado y activo.", "bot_username": bot_username, "enabled": True}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Could not save Telegram channel config")
        raise HTTPException(status_code=500, detail=f"No se pudo guardar Telegram: {exc}") from exc


@router.post("/dashboard/channels/telegram/toggle")
async def toggle_telegram_channel(payload: TelegramChannelToggle, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await _ensure_telegram_mtproto_columns()
    business_id = str(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COALESCE(auth_mode, 'bot') FROM public.business_telegram_channels
                   WHERE business_id = %s::uuid""",
                (business_id,),
            )
            mode_row = cur.fetchone()
            if not mode_row:
                raise HTTPException(status_code=404, detail="Primero conecta tu cuenta o bot de Telegram.")
            auth_mode = str(mode_row[0] or "bot")
            new_status = ("active" if auth_mode == "phone" else "starting") if payload.enabled else "inactive"
            cur.execute(
                """UPDATE public.business_telegram_channels
                   SET enabled = %s, channel_status = %s, last_error = NULL, updated_at = now()
                   WHERE business_id = %s::uuid RETURNING enabled""",
                (payload.enabled, new_status, business_id),
            )
            row = cur.fetchone()
        conn.commit()

    if not payload.enabled:
        await stop_telegram_user_listener(business_id)
    else:
        try:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """SELECT auth_mode, session_string, api_id, api_hash
                           FROM public.business_telegram_channels WHERE business_id = %s::uuid""",
                        (business_id,),
                    )
                    auth_row = cur.fetchone()
            if auth_row and str(auth_row[0] or "bot") == "phone" and auth_row[1]:
                api_id, api_hash = _get_telegram_api_credentials(
                    int(auth_row[2]) if auth_row[2] else None,
                    str(auth_row[3]) if auth_row[3] else None,
                )
                await _start_telethon_user_listener(business_id, str(auth_row[1]), api_id, api_hash)
        except Exception as exc:
            logger.warning("No se pudo reactivar el listener MTProto (%s): %s", business_id, exc)
    return {"success": True, "enabled": bool(row[0]), "status": new_status}


@router.post("/dashboard/channels/telegram/disconnect")
async def disconnect_telegram_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    await _ensure_telegram_mtproto_columns()
    business_id = str(current_user["business_id"])
    await stop_telegram_user_listener(business_id)
    old_pending = _pending_tg_otp.pop(business_id, None)
    if old_pending and old_pending.get("client"):
        try:
            await old_pending["client"].disconnect()
        except Exception:
            pass
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM public.business_telegram_channels WHERE business_id = %s::uuid",
                (business_id,),
            )
        conn.commit()
    return {"success": True, "message": "Telegram desvinculado correctamente."}


@router.post("/dashboard/channels/telegram/test")
async def test_telegram_channel(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = str(current_user["business_id"])
    token, owner_chat_id = await _owner_channel(business_id)
    if not token or token.startswith("mtproto_"):
        raise HTTPException(status_code=409, detail="Configura primero un bot o cuenta de Telegram.")
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


# ===========================================================================
# CONEXIÓN DE TELEGRAM POR NÚMERO DE TELÉFONO + CÓDIGO OTP (TELETHON MTPROTO)
# ===========================================================================
import os

try:
    from telethon import TelegramClient, events
    from telethon.sessions import StringSession
    from telethon.errors import (
        SessionPasswordNeededError,
        PhoneNumberInvalidError,
        PhoneCodeInvalidError,
        PhoneCodeExpiredError,
        FloodWaitError,
    )
    _HAS_TELETHON = True
except Exception:
    _HAS_TELETHON = False

# Credenciales oficiales de cliente Telegram Desktop por defecto para que funcione en Render
# incluso si el usuario aún no definió TELEGRAM_API_ID / TELEGRAM_API_HASH en variables de entorno
DEFAULT_TELEGRAM_API_ID = 2040
DEFAULT_TELEGRAM_API_HASH = "b18441a1ff607e10a989891a5462e627"

_pending_tg_otp: dict[str, dict[str, Any]] = {}
_active_userbot_clients: dict[str, Any] = {}


class TelegramSendCodeRequest(BaseModel):
    phone_number: str = Field(..., min_length=6, max_length=40)
    owner_chat_id: str | None = Field(default=None, max_length=80)
    force_sms: bool = False
    api_id: int | None = None
    api_hash: str | None = None


class TelegramVerifyCodeRequest(BaseModel):
    phone_number: str = Field(..., min_length=6, max_length=40)
    code: str = Field(..., min_length=3, max_length=12)
    password: str | None = Field(default=None, max_length=200)
    owner_chat_id: str | None = Field(default=None, max_length=80)


def _normalize_telegram_phone(raw_phone: str) -> str:
    """Normalize phone number to strict E.164 format (+CountryCodeNumber).
    Automatically converts Venezuelan local numbers (0412/0414/0424/0416/0426) or +58 0412... to +58412..."""
    digits = re.sub(r"\D", "", raw_phone or "")
    if not digits:
        return ""
    if len(digits) == 11 and digits.startswith(("0412", "0414", "0424", "0416", "0426")):
        digits = "58" + digits[1:]
    elif digits.startswith("580") and len(digits) == 13:
        digits = "58" + digits[3:]
    elif len(digits) == 10 and digits.startswith(("412", "414", "424", "416", "426")):
        digits = "58" + digits
    return "+" + digits


async def _ensure_telegram_mtproto_columns() -> None:
    """Additive migration for persisted Telethon sessions and their API credentials."""
    await ensure_telegram_schema()
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("ALTER TABLE public.business_telegram_channels ADD COLUMN IF NOT EXISTS auth_mode varchar(20) NOT NULL DEFAULT 'bot'")
                cur.execute("ALTER TABLE public.business_telegram_channels ADD COLUMN IF NOT EXISTS phone_number varchar(40)")
                cur.execute("ALTER TABLE public.business_telegram_channels ADD COLUMN IF NOT EXISTS session_string text")
                cur.execute("ALTER TABLE public.business_telegram_channels ADD COLUMN IF NOT EXISTS api_id bigint")
                cur.execute("ALTER TABLE public.business_telegram_channels ADD COLUMN IF NOT EXISTS api_hash text")
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _get_telegram_api_credentials(custom_id: int | None = None, custom_hash: str | None = None) -> tuple[int, str]:
    raw_id = custom_id or os.getenv("TELEGRAM_API_ID", "").strip()
    raw_hash = (custom_hash or os.getenv("TELEGRAM_API_HASH", "")).strip()
    try:
        parsed_id = int(raw_id) if raw_id else DEFAULT_TELEGRAM_API_ID
    except (ValueError, TypeError):
        parsed_id = DEFAULT_TELEGRAM_API_ID
    parsed_hash = raw_hash if (raw_hash and len(raw_hash) >= 16) else DEFAULT_TELEGRAM_API_HASH
    return parsed_id, parsed_hash


def _create_telethon_client(session: StringSession, api_id: int, api_hash: str) -> "TelegramClient":
    return TelegramClient(
        session,
        api_id,
        api_hash,
        device_model="CALYRISIA Business Desktop",
        system_version="Windows 11 x64",
        app_version="4.16.8 x64",
        lang_code="es",
        system_lang_code="es",
    )


async def _start_telethon_user_listener(business_id: str, session_str: str, api_id: int, api_hash: str) -> None:
    if not _HAS_TELETHON or not session_str:
        return
    old_client = _active_userbot_clients.pop(business_id, None)
    if old_client:
        try:
            await old_client.disconnect()
        except Exception:
            pass

    client = _create_telethon_client(StringSession(session_str), api_id, api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        await client.disconnect()
        return

    @client.on(events.NewMessage(incoming=True))
    async def _on_private_message(event):
        if not event.is_private or event.out:
            return
        sender = await event.get_sender()
        if getattr(sender, "bot", False):
            return
        sender_id = str(event.sender_id)
        if sender_id == "777000":
            return
        text = str(event.raw_text or "").strip()
        if not text:
            return
        first_name = str(getattr(sender, "first_name", "") or "Cliente Telegram")
        last_name = str(getattr(sender, "last_name", "") or "")
        username = str(getattr(sender, "username", "") or "")

        try:
            chat_dict = {"id": sender_id}
            sender_dict = {"first_name": first_name, "last_name": last_name, "username": username}
            customer_id, conversation_id, customer_name = await _ensure_customer_and_conversation(business_id, chat_dict, sender_dict)

            outbound = await _get_recent_outbound(business_id, customer_id, conversation_id)
            prior_amount, prior_items = _parse_payment_marker(outbound)
            conv_key = f"{business_id}:{conversation_id}"
            pending_ctx = _pending_tg_payment_context.get(conv_key) or {}
            if prior_amount is not None and prior_amount > 0:
                payment_options = await _get_business_payment_options(business_id)
                matched_opt = _match_payment_option_from_text(text, payment_options)
                is_sub = _looks_like_payment_submission(text)

                if pending_ctx.get("reference_text") and matched_opt and not is_sub:
                    combined_details = f"{matched_opt['label']} — {pending_ctx['reference_text']}"
                    _pending_tg_payment_context.pop(conv_key, None)
                    method_label = matched_opt["label"] + " (Telegram)"
                    payment_id, newly_created = await _create_telegram_payment(
                        business_id=business_id,
                        customer_id=customer_id,
                        chat_id=sender_id,
                        customer_name=customer_name,
                        amount=prior_amount,
                        items=prior_items,
                        payment_details=combined_details,
                        payment_method=method_label,
                    )
                    reply = (
                        f"✅ Recibí tus datos de {matched_opt['label']} ({pending_ctx['reference_text']}) por USD {prior_amount:.2f}.\n"
                        f"Tu pago quedó PENDIENTE de revisión en el panel del comercio (Solicitud #{payment_id[:8].upper()})."
                        if newly_created
                        else f"📌 Tu solicitud de pago #{payment_id[:8].upper()} fue actualizada y sigue pendiente de revisión."
                    )
                    await _save_catalog_fallback_message(
                        business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
                    )
                    await event.reply(reply)
                    return

                if matched_opt and not is_sub and len(_normalise(text).split()) <= 5:
                    _pending_tg_payment_context[conv_key] = {"selected_option": matched_opt}
                    reply = (
                        f"¡Perfecto! Anoté {matched_opt['label']} para tu pedido de USD {prior_amount:.2f}.\n\n"
                        f"▸ Datos de {matched_opt['label']}:\n{matched_opt['instructions']}\n\n"
                        f"Envíame por aquí el número de referencia de tu operación para registrarlo."
                    )
                    await _save_catalog_fallback_message(
                        business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
                    )
                    await event.reply(reply)
                    return

                if is_sub:
                    selected_option = matched_opt or (payment_options[0] if len(payment_options) == 1 else pending_ctx.get("selected_option"))
                    if not selected_option and len(payment_options) > 1:
                        _pending_tg_payment_context[conv_key] = {"reference_text": text}
                        choices = " o ".join(option["label"] for option in payment_options)
                        ask_msg = f"Recibí tu referencia ({text}). Respóndeme qué método utilizaste ({choices}) para terminar de registrarla."
                        await _save_catalog_fallback_message(
                            business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=ask_msg
                        )
                        await event.reply(ask_msg)
                        return
                    _pending_tg_payment_context.pop(conv_key, None)
                    method_label = (selected_option["label"] if selected_option else "Pago") + " (Telegram)"
                    payment_id, newly_created = await _create_telegram_payment(
                        business_id=business_id,
                        customer_id=customer_id,
                        chat_id=sender_id,
                        customer_name=customer_name,
                        amount=prior_amount,
                        items=prior_items,
                        payment_details=text,
                        payment_method=method_label,
                    )
                    reply = (
                        f"✅ Recibí tus datos de {selected_option['label'] if selected_option else 'pago'} por USD {prior_amount:.2f}.\n"
                        f"Tu pago quedó PENDIENTE de revisión en el panel del comercio (Solicitud #{payment_id[:8].upper()})."
                        if newly_created
                        else f"📌 Tu solicitud de pago #{payment_id[:8].upper()} fue actualizada y sigue pendiente de revisión."
                    )
                    await _save_catalog_fallback_message(
                        business_id=business_id, customer_id=customer_id, conversation_id=conversation_id, response_text=reply
                    )
                    await event.reply(reply)
                    return

            payload = IncomingMessage(
                business_id=uuid.UUID(business_id),
                customer_id=customer_id,
                conversation_id=conversation_id,
                channel="telegram",
                message=text,
                metadata={"channel": "telegram", "external_chat_id": sender_id, "telegram_username": username},
            )
            async with get_connection() as conn:
                consume_ai_response(conn, uuid.UUID(business_id))
                result = GalaxyAutopilotService(conn).respond(payload)
            raw_reply = str(result.get("response") or "").strip()
            clean_reply, pay_amount, _ = _clean_for_telegram(raw_reply)
            if pay_amount is not None and pay_amount > 0:
                payment_options = await _get_business_payment_options(business_id)
                if payment_options:
                    details = "\n\n".join(f"▸ {opt['label']}:\n{opt['instructions']}" for opt in payment_options)
                    clean_reply = (
                        f"{clean_reply}\n\n💳 INSTRUCCIONES DE PAGO · USD {pay_amount:.2f}\n{details}\n\n"
                        "Envíame por este mismo chat el número de referencia cuando completes el pago."
                    ).strip()
            if clean_reply:
                await event.reply(clean_reply)
        except Exception as exc:
            logger.warning("Error respondiendo con Telethon en business_id=%s: %s", business_id, exc)

    _active_userbot_clients[business_id] = client


async def stop_telegram_user_listener(business_id: str) -> None:
    client = _active_userbot_clients.pop(str(business_id), None)
    if client is not None:
        try:
            await client.disconnect()
        except Exception as exc:
            logger.debug("Could not disconnect Telegram user session for %s: %s", business_id, exc)


async def restore_telegram_user_sessions() -> dict[str, int]:
    """Restore each active tenant's persisted MTProto session after every server restart."""
    if not _HAS_TELETHON:
        logger.warning("Telethon is unavailable; MTProto sessions were not restored.")
        return {"restored": 0, "failed": 0}

    await _ensure_telegram_mtproto_columns()
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT business_id::text, session_string, api_id, api_hash
                   FROM public.business_telegram_channels
                   WHERE enabled = true AND auth_mode = 'phone'
                     AND session_string IS NOT NULL AND btrim(session_string) <> ''"""
            )
            sessions = cur.fetchall()

    restored = 0
    failed = 0
    for business_id, session_string, stored_api_id, stored_api_hash in sessions:
        business_id = str(business_id)
        try:
            api_id, api_hash = _get_telegram_api_credentials(
                int(stored_api_id) if stored_api_id else None,
                str(stored_api_hash) if stored_api_hash else None,
            )
            await _start_telethon_user_listener(business_id, str(session_string), api_id, api_hash)
            if business_id in _active_userbot_clients:
                restored += 1
            else:
                failed += 1
                logger.warning("Telegram MTProto session for business %s is no longer authorized.", business_id)
        except Exception as exc:
            failed += 1
            logger.exception("Could not restore Telegram MTProto session for business %s: %s", business_id, exc)
            try:
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """UPDATE public.business_telegram_channels
                               SET channel_status = 'error', last_error = %s, updated_at = now()
                               WHERE business_id = %s::uuid AND auth_mode = 'phone'""",
                            (str(exc)[:1000], business_id),
                        )
                    conn.commit()
            except Exception:
                pass
    logger.info("Telegram MTProto session restore completed: %s restored, %s failed.", restored, failed)
    return {"restored": restored, "failed": failed}


@router.post("/dashboard/channels/telegram/send-code")
async def send_telegram_login_code(
    payload: TelegramSendCodeRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    if not _HAS_TELETHON:
        raise HTTPException(status_code=503, detail="La librería Telethon no está instalada en el servidor.")
    await _ensure_telegram_mtproto_columns()
    business_id = str(current_user["business_id"])
    api_id, api_hash = _get_telegram_api_credentials(payload.api_id, payload.api_hash)
    phone = _normalize_telegram_phone(payload.phone_number)
    if len(phone) < 8:
        raise HTTPException(
            status_code=422,
            detail="Ingresa un número válido con código de país (por ejemplo +584121234567).",
        )

    prev_pending = _pending_tg_otp.pop(business_id, None)
    if prev_pending and prev_pending.get("client"):
        try:
            await prev_pending["client"].disconnect()
        except Exception:
            pass

    client = _create_telethon_client(StringSession(), api_id, api_hash)
    await client.connect()
    try:
        sent = await client.send_code_request(phone, force_sms=bool(payload.force_sms))
        temp_session = client.session.save()
        delivery_type_name = type(getattr(sent, "type", None)).__name__.lower()
        _pending_tg_otp[business_id] = {
            "phone": phone,
            "client": client,
            "session_str": temp_session,
            "phone_code_hash": sent.phone_code_hash,
            "api_id": api_id,
            "api_hash": api_hash,
        }
    except PhoneNumberInvalidError as exc:
        await client.disconnect()
        raise HTTPException(
            status_code=422,
            detail=f"El número {phone} no es válido en Telegram. Verifica el código de país (ej. +58412...).",
        ) from exc
    except FloodWaitError as exc:
        await client.disconnect()
        raise HTTPException(
            status_code=429,
            detail=f"Telegram solicitó esperar {exc.seconds} segundos antes de pedir otro código.",
        ) from exc
    except Exception as exc:
        await client.disconnect()
        raise HTTPException(status_code=422, detail=f"No se pudo enviar el código a {phone}: {exc}") from exc

    if "sms" in delivery_type_name:
        delivery_msg = f"✓ Código de 5 dígitos enviado por SMS a {phone}. Ingrésalo abajo para conectar."
    else:
        delivery_msg = (
            f"✓ Código de 5 dígitos enviado a tu app de Telegram ({phone}). "
            "Abre Telegram en tu celular o PC y revisa el chat oficial 'Telegram' (notificaciones de servicio)."
        )

    return {
        "success": True,
        "status": "code_sent",
        "phone_number": phone,
        "delivery_type": delivery_type_name,
        "message": delivery_msg,
    }


@router.post("/dashboard/channels/telegram/verify-code")
async def verify_telegram_login_code(
    payload: TelegramVerifyCodeRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict[str, Any]:
    if not _HAS_TELETHON:
        raise HTTPException(status_code=503, detail="La librería Telethon no está instalada.")
    await _ensure_telegram_mtproto_columns()
    business_id = str(current_user["business_id"])
    pending = _pending_tg_otp.get(business_id)
    if not pending:
        raise HTTPException(status_code=400, detail="Primero solicita el código con tu número de teléfono.")

    api_id = int(pending["api_id"])
    api_hash = str(pending["api_hash"])
    phone = str(pending["phone"])
    code = re.sub(r"\D", "", payload.code or "") or payload.code.strip()

    client = pending.get("client")
    if client is None or not client.is_connected():
        client = _create_telethon_client(StringSession(pending["session_str"]), api_id, api_hash)
        await client.connect()

    try:
        try:
            await client.sign_in(phone=phone, code=code, phone_code_hash=pending["phone_code_hash"])
        except SessionPasswordNeededError:
            if not payload.password:
                pending["client"] = client
                pending["session_str"] = client.session.save()
                return {
                    "success": False,
                    "requires_2fa": True,
                    "message": "Tu cuenta tiene verificación en dos pasos (2FA). Escribe tu contraseña de Telegram y pulsa Verificar.",
                }
            await client.sign_in(password=payload.password.strip())

        me = await client.get_me()
        username = str(getattr(me, "username", "") or getattr(me, "first_name", "") or phone)
        final_session = client.session.save()
    except PhoneCodeInvalidError as exc:
        raise HTTPException(status_code=422, detail="El código ingresado es incorrecto. Verifica los 5 dígitos en tu app de Telegram.") from exc
    except PhoneCodeExpiredError as exc:
        _pending_tg_otp.pop(business_id, None)
        try:
            await client.disconnect()
        except Exception:
            pass
        raise HTTPException(status_code=422, detail="El código expiró. Pulsa 'Enviar código' nuevamente e ingrésalo de inmediato.") from exc
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Error verificando el código de Telegram: {exc}") from exc

    try:
        await client.disconnect()
    except Exception:
        pass

    placeholder_token = f"mtproto_{business_id}"
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO public.business_telegram_channels
                   (business_id, bot_token, bot_username, owner_chat_id, enabled, channel_status, auth_mode, phone_number, session_string, api_id, api_hash, last_error, updated_at)
                   VALUES (%s::uuid, %s, %s, %s, true, 'active', 'phone', %s, %s, %s, %s, NULL, now())
                   ON CONFLICT (business_id) DO UPDATE SET
                     bot_token = EXCLUDED.bot_token,
                     bot_username = EXCLUDED.bot_username,
                     owner_chat_id = COALESCE(EXCLUDED.owner_chat_id, business_telegram_channels.owner_chat_id),
                     enabled = true,
                     channel_status = 'active',
                     auth_mode = 'phone',
                     phone_number = EXCLUDED.phone_number,
                     session_string = EXCLUDED.session_string,
                     api_id = EXCLUDED.api_id,
                     api_hash = EXCLUDED.api_hash,
                     last_error = NULL,
                     updated_at = now()""",
                (business_id, placeholder_token, username, (payload.owner_chat_id or "").strip() or None, phone, final_session, api_id, api_hash),
            )
        conn.commit()

    _pending_tg_otp.pop(business_id, None)
    await _start_telethon_user_listener(business_id, final_session, api_id, api_hash)

    return {
        "success": True,
        "status": "connected",
        "bot_username": username,
        "phone_number": phone,
        "message": f"✓ Cuenta de Telegram ({username} · {phone}) conectada y respondiendo con el Cerebro IA.",
    }


async def process_message(update: dict, req_id: str | None = None) -> None:
    """Backwards-compatible entrypoint used by scripts/telegram_local_runner.py."""
    settings = _settings()
    business_id = (settings.telegram_business_id or "").strip()
    token = (settings.telegram_bot_token or "").strip()
    if not business_id or not token:
        return
    await process_telegram_update(update, business_id, token, req_id)


def send_to_telegram(chat_id: str | int, text: str) -> bool:
    """Backwards-compatible synchronous sender used by scripts/telegram_local_runner.py."""
    settings = _settings()
    token = (settings.telegram_bot_token or "").strip()
    if not token or not str(chat_id).strip():
        return False
    try:
        _telegram_api_sync(token, "sendMessage", {"chat_id": str(chat_id), "text": (text or "")[:4000]}, timeout=12)
        return True
    except Exception:
        return False
