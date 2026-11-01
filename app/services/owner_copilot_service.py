from __future__ import annotations

import json
import logging
import re
import unicodedata
import uuid
from typing import Any
from uuid import UUID

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

from app.services.analytics_service import AnalyticsService
from app.services.business_brain_service import BusinessBrainService
from app.services.context_manager import invalidate_business_context_cache
from app.services.inventory_intelligence import InventoryIntelligenceService
from app.services.model_router_service import ModelRouterService
from app.services.recommendation_engine import RecommendationEngine

logger = logging.getLogger(__name__)


def _norm_text(value: str) -> str:
    raw = unicodedata.normalize("NFD", str(value or "").lower())
    no_accents = "".join(ch for ch in raw if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9.$]+", " ", no_accents).strip()


def _stem_es(word: str) -> str:
    w = word.strip().lower()
    if len(w) > 5 and w.endswith("es") and w[-3] not in "aeiou":
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


class OwnerCopilotService:
    """Executive Copilot for the business owner/admin.

    Capable of:
    1. Executing real operational tasks directly from natural language commands:
       - Adding/restocking product units (e.g., "agregame 5 teclados rgb", "suma 10 mouse inalambrico")
       - Creating new catalog items (e.g., "crea el producto Monitor 27 a $190 con 8 en stock")
       - Updating product prices (e.g., "cambia el precio de teclado rgb a $45")
       - Bulk restocking all low-stock items (e.g., "reabastece todos los productos con poco stock")
       - Updating the daily exchange rate (e.g., "actualiza la tasa del dia a 46.50")
    2. Answering executive queries grounded in live PostgreSQL/Supabase business data
       (inventory alerts, sales, pending payments, CRM opportunities, active channels).
    """

    def __init__(self, conn):
        self.conn = conn
        self.analytics = AnalyticsService(conn)
        self.business_brain = BusinessBrainService(conn)
        self.recommendations = RecommendationEngine(conn)
        self.inventory = InventoryIntelligenceService(conn)
        self.router = ModelRouterService()

    def _fetch_live_snapshot(self, business_id: UUID) -> dict[str, Any]:
        bid = str(business_id)
        products: list[dict[str, Any]] = []
        pending_payments: list[dict[str, Any]] = []
        approved_sales_total = 0.0
        approved_sales_count = 0
        biz_name = "Tu Negocio"
        exchange_rate = 0.0
        local_currency = "VES"
        channels_active: list[str] = ["Webchat IA"]

        with self.conn.cursor() as cur:
            try:
                cur.execute("SELECT name, COALESCE(webchat_enabled, true) FROM public.businesses WHERE id = %s", (bid,))
                b_row = cur.fetchone()
                if b_row:
                    biz_name = str(b_row[0] or "Tu Negocio")
            except Exception:
                pass

            try:
                cur.execute(
                    """
                    SELECT p.id::text, p.name, COALESCE(p.price, 0), COALESCE(p.category, 'General'),
                           COALESCE((SELECT SUM(i.quantity) FROM public.inventory i WHERE i.product_id = p.id AND i.business_id = p.business_id), 0)
                    FROM public.products p
                    WHERE p.business_id = %s AND p.status = 'active'
                    ORDER BY p.name ASC
                    """,
                    (bid,),
                )
                for r in cur.fetchall():
                    products.append(
                        {
                            "id": str(r[0]),
                            "name": str(r[1]),
                            "price": float(r[2] or 0),
                            "category": str(r[3] or "General"),
                            "stock": float(r[4] or 0),
                        }
                    )
            except Exception:
                pass

            try:
                cur.execute(
                    """
                    SELECT id::text, COALESCE(customer_name, 'Cliente'), COALESCE(amount, 0), COALESCE(payment_method, 'pago_movil'), status
                    FROM public.webchat_payment_requests
                    WHERE business_id = %s
                    ORDER BY created_at DESC LIMIT 50
                    """,
                    (bid,),
                )
                for r in cur.fetchall():
                    st = str(r[4] or "pending")
                    amt = float(r[2] or 0)
                    if st == "pending":
                        pending_payments.append(
                            {"id": str(r[0]), "customer_name": str(r[1]), "amount": amt, "method": str(r[3])}
                        )
                    elif st == "approved":
                        approved_sales_total += amt
                        approved_sales_count += 1
            except Exception:
                pass

            try:
                cur.execute(
                    "SELECT COALESCE(exchange_rate, 0), COALESCE(local_currency_code, 'VES') FROM public.business_dashboard_settings WHERE business_id = %s",
                    (bid,),
                )
                d_row = cur.fetchone()
                if d_row:
                    exchange_rate = float(d_row[0] or 0)
                    local_currency = str(d_row[1] or "VES")
            except Exception:
                pass

            try:
                cur.execute("SELECT enabled FROM public.business_whatsapp_channels WHERE business_id = %s::uuid", (bid,))
                w_row = cur.fetchone()
                if w_row and bool(w_row[0]):
                    channels_active.append("WhatsApp QR")
            except Exception:
                pass

            try:
                cur.execute("SELECT enabled FROM public.business_telegram_channels WHERE business_id = %s::uuid", (bid,))
                t_row = cur.fetchone()
                if t_row and bool(t_row[0]):
                    channels_active.append("Telegram Bot")
            except Exception:
                pass

            try:
                cur.execute(
                    "SELECT platform, enabled FROM public.business_meta_channels WHERE business_id = %s::uuid",
                    (bid,),
                )
                for mr in cur.fetchall():
                    if mr and bool(mr[1]):
                        channels_active.append("Instagram DM" if str(mr[0]) == "instagram" else "Facebook Messenger")
            except Exception:
                pass

        low_stock = [p for p in products if 0 < p["stock"] <= 5]
        out_of_stock = [p for p in products if p["stock"] <= 0]
        inventory_value = sum(max(0.0, p["stock"]) * p["price"] for p in products)

        return {
            "business_name": biz_name,
            "products": products,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "inventory_value": inventory_value,
            "pending_payments": pending_payments,
            "approved_sales_total": approved_sales_total,
            "approved_sales_count": approved_sales_count,
            "exchange_rate": exchange_rate,
            "local_currency": local_currency,
            "channels_active": channels_active,
        }

    def _find_best_product_match(self, query_fragment: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
        q_norm = _norm_text(query_fragment)
        if not q_norm:
            return None
        stop_words = {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
            "producto", "productos", "articulo", "articulos", "unidad", "unidades", "uds",
            "stock", "inventario", "catalogo", "por", "favor", "en", "con", "mas",
        }
        q_tokens = [_stem_es(t) for t in q_norm.split() if t not in stop_words and len(t) >= 2]
        if not q_tokens:
            return None

        best_prod = None
        best_score = 0.0
        for p in products:
            p_norm = _norm_text(p["name"])
            if q_norm in p_norm or p_norm in q_norm:
                return p
            p_tokens = [_stem_es(t) for t in p_norm.split() if len(t) >= 2]
            overlap = 0
            for qt in q_tokens:
                if any(qt == pt or (len(qt) >= 3 and (qt in pt or pt in qt)) for pt in p_tokens):
                    overlap += 1
            if overlap > 0:
                score = overlap / max(1, len(q_tokens))
                if score > best_score:
                    best_score = score
                    best_prod = p
        return best_prod if best_score >= 0.45 else None

    def _log_copilot_action(
        self,
        *,
        business_id: UUID,
        user_id: UUID,
        tool_name: str,
        reason: str,
        details: dict[str, Any],
    ) -> None:
        bid = str(business_id)
        uid = str(user_id)
        act_id = str(uuid.uuid4())
        try:
            with self.conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_copilot_act")
                cur.execute(
                    """
                    INSERT INTO public.actions (
                        id, business_id, action_type, resource_type, tool_name,
                        autonomy_level, risk_level, status, input_data, output_data,
                        reason, requested_at, started_at, completed_at, created_at
                    ) VALUES (
                        %s, %s, 'execute', 'inventory', %s,
                        'L2', 'low', 'completed', %s, %s,
                        %s, NOW(), NOW(), NOW(), NOW()
                    )
                    """,
                    (act_id, bid, tool_name, Jsonb(details), Jsonb({"ok": True}), reason),
                )
                cur.execute(
                    """
                    INSERT INTO public.audit_logs (
                        id, business_id, actor_user_id, actor_type, action_type,
                        resource_type, resource_id, status, reason, metadata, created_at
                    ) VALUES (
                        %s, %s, %s, 'owner_copilot', %s,
                        'business', %s, 'success', %s, %s, NOW()
                    )
                    """,
                    (str(uuid.uuid4()), bid, uid, tool_name, bid, reason, Jsonb(details)),
                )
                cur.execute("RELEASE SAVEPOINT sp_copilot_act")
            self.conn.commit()
        except Exception:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_copilot_act")
            except Exception:
                pass

    def _try_execute_command(
        self,
        *,
        business_id: UUID,
        user_id: UUID,
        message: str,
        snapshot: dict[str, Any],
    ) -> dict[str, Any] | None:
        raw_msg = message.strip()
        norm = _norm_text(raw_msg)
        products = snapshot["products"]
        bid = str(business_id)

        # 1. BULK RESTOCK ALL LOW-STOCK / OUT-OF-STOCK ITEMS
        # e.g. "reabastece todos los productos con poco stock", "agrega 10 a todo lo de bajo stock"
        if re.search(r"\b(reabastec\w*|repon\w*|rellen\w*|sub\w*|agreg\w*|sum\w*)\b", norm) and re.search(
            r"\b(poco stock|bajo stock|stock bajo|agotad\w*|critico\w*|todos los de bajo)\b", norm
        ):
            m_qty = re.search(r"\b(\d{1,4})\b", norm)
            add_qty = int(m_qty.group(1)) if m_qty else 10
            targets = [p for p in products if p["stock"] <= 5]
            if not targets:
                return {
                    "action_executed": False,
                    "action_type": "bulk_restock_none",
                    "response": (
                        "✅ **Inventario Saludable:** Revisé todo tu catálogo y actualmente **ningún producto tiene stock crítico (≤ 5 uds)**.\n\n"
                        "Si deseas sumar unidades a un artículo específico, escríbeme por ejemplo: `agrégame 5 teclados rgb`."
                    ),
                }
            updated_lines = []
            with self.conn.cursor() as cur:
                for p in targets:
                    new_st = round(p["stock"] + add_qty)
                    cur.execute(
                        "UPDATE public.inventory SET quantity = %s WHERE product_id = %s AND business_id = %s",
                        (new_st, p["id"], bid),
                    )
                    if cur.rowcount == 0:
                        cur.execute(
                            "INSERT INTO public.inventory (id, business_id, product_id, quantity, minimum_quantity, location) VALUES (%s, %s, %s, %s, 0, 'tienda')",
                            (str(uuid.uuid4()), bid, p["id"], new_st),
                        )
                    updated_lines.append(
                        f"• **{p['name']}**: {int(p['stock'])} uds → **{new_st} uds** (+{add_qty});"
                    )
            self.conn.commit()
            invalidate_business_context_cache(business_id)
            self._log_copilot_action(
                business_id=business_id,
                user_id=user_id,
                tool_name="copilot_bulk_restock",
                reason=f"Reabastecimiento automático de {len(targets)} productos con stock bajo (+{add_qty} uds).",
                details={"count": len(targets), "added_each": add_qty},
            )
            return {
                "action_executed": True,
                "action_type": "bulk_restock",
                "response": (
                    f"⚡ **Tarea Ejecutada · Reabastecimiento de Stock Crítico**\n\n"
                    f"He sumado **+{add_qty} unidades** a los **{len(targets)} artículos** que tenían stock bajo o agotado:\n"
                    + "\n".join(updated_lines)
                    + "\n\nEl catálogo y el Cerebro IA ya tienen las nuevas existencias sincronizadas."
                ),
            }

        # 2. UPDATE EXCHANGE RATE (TASA DEL DÍA)
        # e.g. "pon la tasa del dia en 46.50", "actualiza la tasa bcv a 45.8"
        m_rate = re.search(
            r"\b(?:tasa(?:\s+del\s+dia|\s+de\s+cambio|\s+bcv)?|dolar)\b.*?\b(\d+(?:[.,]\d{1,2})?)\b",
            norm,
        )
        if m_rate and any(w in norm for w in ("pon", "actualiza", "cambia", "fija", "configura", "ajusta", "sube", "baja")):
            new_rate = float(m_rate.group(1).replace(",", "."))
            if new_rate >= 0:
                with self.conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO public.business_dashboard_settings (business_id, exchange_rate, updated_at)
                        VALUES (%s, %s, NOW())
                        ON CONFLICT (business_id) DO UPDATE SET exchange_rate = EXCLUDED.exchange_rate, updated_at = NOW()
                        """,
                        (bid, new_rate),
                    )
                self.conn.commit()
                self._log_copilot_action(
                    business_id=business_id,
                    user_id=user_id,
                    tool_name="copilot_update_exchange_rate",
                    reason=f"Tasa de cambio actualizada a {new_rate:.2f} {snapshot['local_currency']}/USD.",
                    details={"exchange_rate": new_rate},
                )
                return {
                    "action_executed": True,
                    "action_type": "update_exchange_rate",
                    "response": (
                        f"✅ **Tarea Ejecutada · Tasa del Día Actualizada**\n\n"
                        f"• **Nueva tasa activa:** **{new_rate:.2f} {snapshot['local_currency']} por 1 USD**;\n"
                        f"• **Ejemplo en vivo:** Un pedido de **USD 100.00** se mostrará automáticamente como **{snapshot['local_currency']} {(100.0 * new_rate):,.2f}** en todos los canales conectados."
                    ),
                }

        # 3. UPDATE PRODUCT PRICE
        # e.g. "cambia el precio de teclado rgb a $42", "pon el precio del mouse en 18.50"
        m_price_cmd = re.search(
            r"\b(?:cambia\w*|actualiza\w*|modifica\w*|pon\w*|fija\w*|ajusta\w*)\s+(?:el\s+)?precio\s+(?:de(?:l)?\s+)?(.+?)\s+(?:a|en)\s+\$?\s*(\d+(?:[.,]\d{1,2})?)\b",
            norm,
        )
        if m_price_cmd:
            prod_query = m_price_cmd.group(1).strip()
            new_price = float(m_price_cmd.group(2).replace(",", "."))
            matched = self._find_best_product_match(prod_query, products)
            if matched:
                old_price = matched["price"]
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.products SET price = %s, updated_at = NOW() WHERE id = %s AND business_id = %s",
                        (new_price, matched["id"], bid),
                    )
                self.conn.commit()
                invalidate_business_context_cache(business_id)
                self._log_copilot_action(
                    business_id=business_id,
                    user_id=user_id,
                    tool_name="copilot_update_price",
                    reason=f"Precio de '{matched['name']}' actualizado de USD {old_price:.2f} a USD {new_price:.2f}.",
                    details={"product_id": matched["id"], "old_price": old_price, "new_price": new_price},
                )
                return {
                    "action_executed": True,
                    "action_type": "update_price",
                    "response": (
                        f"✅ **Tarea Ejecutada · Actualización de Precio**\n\n"
                        f"• **Artículo:** {matched['name']};\n"
                        f"• **Precio anterior:** USD {old_price:.2f} → **Precio nuevo:** **USD {new_price:.2f}**;\n"
                        f"• **Stock disponible:** {int(matched['stock'])} unidades.\n\n"
                        f"El nuevo precio ya está activo en el catálogo y en el bot omnicanal."
                    ),
                }

        # 4. ADD / RESTOCK PRODUCT OR CREATE PRODUCT BY NATURAL COMMAND
        # Patterns supported:
        # - "agregame 5 teclados rgb" / "agrega 5 teclados rgb a $45"
        # - "suma 10 unidades a mouse inalambrico"
        # - "añade 8 auriculares bluetooth"
        # - "crea el producto Monitor Gamer 27 a $210 con 8 en stock"
        m_add = re.search(
            r"\b(?:agreg(?:a|ame|ar|uen)|sum(?:a|ame|ar)|anad(?:e|eme|ir)|repon(?:er|me)?|carg(?:a|ame|ar)|met(?:e|eme)|ingres(?:a|ame|ar)|cre(?:a|ame|ar)|registr(?:a|ame|ar))\s+"
            r"(?:(\d{1,5})\s+(?:unidades?\s+(?:de|a)\s+|uds?\s+(?:de|a)\s+)?)?"
            r"(.+)$",
            norm,
        )
        if m_add:
            qty_str = m_add.group(1)
            rest_raw = m_add.group(2).strip()

            # Check if quantity was placed at the end: e.g. "agrega teclado rgb 5 unidades" or "con 8 en stock"
            qty_val = int(qty_str) if qty_str else None
            price_val: float | None = None

            # Extract optional price: "a $48", "precio 48", "$48"
            m_pr = re.search(r"(?:\ba\s+\$?|\bprecio\s+\$?|\$)(\d+(?:[.,]\d{1,2})?)\b", rest_raw)
            if m_pr:
                price_val = float(m_pr.group(1).replace(",", "."))
                rest_raw = (rest_raw[: m_pr.start()] + " " + rest_raw[m_pr.end() :]).strip()

            # Extract trailing stock/quantity if not at start
            m_tail_qty = re.search(r"\b(?:con\s+|stock\s+)?(\d{1,5})\s*(?:unidades?|uds?|en\s+stock|stock)?\s*$", rest_raw)
            if qty_val is None and m_tail_qty:
                qty_val = int(m_tail_qty.group(1))
                rest_raw = rest_raw[: m_tail_qty.start()].strip()

            if qty_val is None:
                qty_val = 1

            # Clean filler words from product name candidate
            clean_candidate = re.sub(
                r"^(?:el\s+producto|nuevo\s+producto|el\s+articulo|producto|articulo|unidades?\s+de|a|al|de|del)\s+",
                "",
                rest_raw,
            ).strip()
            clean_candidate = re.sub(r"\s+(?:al\s+catalogo|al\s+inventario|en\s+stock|por\s+favor)$", "", clean_candidate).strip()

            if clean_candidate and len(clean_candidate) >= 2:
                matched = self._find_best_product_match(clean_candidate, products)
                if matched:
                    old_stock = int(round(matched["stock"]))
                    new_stock = old_stock + qty_val
                    final_price = price_val if price_val is not None else matched["price"]
                    with self.conn.cursor() as cur:
                        if price_val is not None:
                            cur.execute(
                                "UPDATE public.products SET price = %s, updated_at = NOW() WHERE id = %s AND business_id = %s",
                                (final_price, matched["id"], bid),
                            )
                        cur.execute(
                            "UPDATE public.inventory SET quantity = %s WHERE product_id = %s AND business_id = %s",
                            (new_stock, matched["id"], bid),
                        )
                        if cur.rowcount == 0:
                            cur.execute(
                                "INSERT INTO public.inventory (id, business_id, product_id, quantity, minimum_quantity, location) VALUES (%s, %s, %s, %s, 0, 'tienda')",
                                (str(uuid.uuid4()), bid, matched["id"], new_stock),
                            )
                    self.conn.commit()
                    invalidate_business_context_cache(business_id)
                    self._log_copilot_action(
                        business_id=business_id,
                        user_id=user_id,
                        tool_name="copilot_restock_product",
                        reason=f"Sumadas +{qty_val} unidades a '{matched['name']}' ({old_stock} -> {new_stock}).",
                        details={
                            "product_id": matched["id"],
                            "product_name": matched["name"],
                            "added_quantity": qty_val,
                            "before_stock": old_stock,
                            "after_stock": new_stock,
                        },
                    )
                    return {
                        "action_executed": True,
                        "action_type": "restock_product",
                        "product_id": matched["id"],
                        "product_name": matched["name"],
                        "added_quantity": qty_val,
                        "new_stock": new_stock,
                        "response": (
                            f"✅ **Tarea Ejecutada · Reposición de Inventario**\n\n"
                            f"• **Producto:** {matched['name']};\n"
                            f"• **Unidades agregadas:** +{qty_val} uds;\n"
                            f"• **Stock actualizado:** {old_stock} uds → **{new_stock} unidades disponibles**;\n"
                            f"• **Precio unitario activo:** USD {final_price:.2f}.\n\n"
                            f"El inventario ya quedó actualizado en tiempo real para todos tus canales de venta."
                        ),
                    }
                else:
                    # Product does not exist yet: create it automatically so the owner doesn't lose time!
                    display_name = " ".join(w.capitalize() if len(w) > 2 else w.upper() if w in {"rgb", "usb", "led", "pro", "hd", "4k", "tv"} else w for w in clean_candidate.split())
                    inferred_price = price_val if price_val is not None else 25.00
                    inferred_cat = "Periféricos" if any(k in clean_candidate for k in ("teclado", "mouse", "auricular", "monitor", "webcam")) else "General"
                    new_pid = str(uuid.uuid4())
                    with self.conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO public.products (id, business_id, name, price, category, status)
                            VALUES (%s, %s, %s, %s, %s, 'active')
                            """,
                            (new_pid, bid, display_name, inferred_price, inferred_cat),
                        )
                        cur.execute(
                            """
                            INSERT INTO public.inventory (id, business_id, product_id, quantity, minimum_quantity, location)
                            VALUES (%s, %s, %s, %s, 0, 'tienda')
                            """,
                            (str(uuid.uuid4()), bid, new_pid, qty_val),
                        )
                    self.conn.commit()
                    invalidate_business_context_cache(business_id)
                    self._log_copilot_action(
                        business_id=business_id,
                        user_id=user_id,
                        tool_name="copilot_create_product",
                        reason=f"Producto '{display_name}' creado con {qty_val} unidades y precio USD {inferred_price:.2f}.",
                        details={
                            "product_id": new_pid,
                            "product_name": display_name,
                            "stock": qty_val,
                            "price": inferred_price,
                        },
                    )
                    price_note = (
                        f"USD {inferred_price:.2f}"
                        if price_val is not None
                        else f"USD {inferred_price:.2f} (puedes decirme `cambia el precio de {display_name.lower()} a $X` para ajustarlo)"
                    )
                    return {
                        "action_executed": True,
                        "action_type": "create_product",
                        "product_id": new_pid,
                        "product_name": display_name,
                        "new_stock": qty_val,
                        "response": (
                            f"✅ **Tarea Ejecutada · Nuevo Producto Creado en Catálogo**\n\n"
                            f"Como **{display_name}** no existía aún en tu inventario, lo registré automáticamente:\n"
                            f"• **Artículo:** {display_name};\n"
                            f"• **Categoría asignada:** {inferred_cat};\n"
                            f"• **Stock inicial cargado:** **{qty_val} unidades**;\n"
                            f"• **Precio asignado:** {price_note}.\n\n"
                            f"Ya está disponible para cotizar en Webchat, WhatsApp, Instagram, Facebook y Telegram."
                        ),
                    }

        return None

    def _build_executive_answer(self, message: str, snapshot: dict[str, Any]) -> str:
        norm = _norm_text(message)
        biz_name = snapshot["business_name"]
        products = snapshot["products"]
        low_stock = snapshot["low_stock"]
        out_of_stock = snapshot["out_of_stock"]
        inv_val = snapshot["inventory_value"]
        pending_pays = snapshot["pending_payments"]
        sales_total = snapshot["approved_sales_total"]
        sales_count = snapshot["approved_sales_count"]
        channels = ", ".join(snapshot["channels_active"])

        # Specific question about low stock or inventory
        if any(w in norm for w in ("stock", "inventario", "agotad", "reponer", "catalogo", "productos", "articulos")):
            lines = [
                f"📦 **Reporte de Inventario en Vivo · {biz_name}**\n",
                f"• **Total de artículos activos:** {len(products)} SKUs;",
                f"• **Valor total en almacén:** **USD {inv_val:,.2f}**;",
                f"• **Agotados (0 uds):** {len(out_of_stock)} artículo(s);",
                f"• **En alerta de stock bajo (1 a 5 uds):** {len(low_stock)} artículo(s).",
            ]
            if out_of_stock or low_stock:
                lines.append("\n**Artículos que requieren atención inmediata:**")
                for p in (out_of_stock + low_stock)[:8]:
                    st_lbl = "AGOTADO (0 uds)" if p["stock"] <= 0 else f"{int(p['stock'])} uds disponibles"
                    lines.append(f"• **{p['name']}** ({p['category']}) — **{st_lbl}** · USD {p['price']:.2f};")
                lines.append(
                    "\n💡 *Acción rápida:* Escríbeme `reabastece todos los productos con poco stock` o `agrégame 10 [nombre del producto]` y lo ejecuto por ti al instante."
                )
            else:
                lines.append("\n✅ Todos tus productos cuentan con más de 5 unidades disponibles.")
                if products:
                    lines.append("\n**Muestra de tu catálogo activo:**")
                    for p in products[:6]:
                        lines.append(f"• **{p['name']}** — {int(p['stock'])} uds · USD {p['price']:.2f};")
            return "\n".join(lines)

        # Specific question about sales, revenue, or payments
        if any(w in norm for w in ("venta", "vendido", "ingreso", "pago", "cobro", "caja", "pedido", "orden")):
            pending_sum = sum(p["amount"] for p in pending_pays)
            lines = [
                f"💰 **Balance de Ventas y Pagos · {biz_name}**\n",
                f"• **Ingresos confirmados:** **USD {sales_total:,.2f}** ({sales_count} pago(s) aprobados);",
                f"• **Pagos pendientes por aprobar:** **{len(pending_pays)} solicitud(es)** por **USD {pending_sum:,.2f}**;",
                f"• **Tasa de cambio configurada:** {snapshot['exchange_rate']:.2f} {snapshot['local_currency']}/USD.",
            ]
            if pending_pays:
                lines.append("\n**Solicitudes esperando tu verificación en Aprobaciones:**")
                for pp in pending_pays[:5]:
                    lines.append(f"• **{pp['customer_name']}** — **USD {pp['amount']:.2f}** vía {pp['method']};")
            return "\n".join(lines)

        # Default comprehensive executive briefing
        pending_sum = sum(p["amount"] for p in pending_pays)
        alert_items = out_of_stock + low_stock
        briefing = [
            f"📊 **Resumen Ejecutivo en Tiempo Real · {biz_name}**\n",
            f"**1. Estado Comercial y Caja:**",
            f"• **Ventas aprobadas:** USD {sales_total:,.2f} ({sales_count} órdenes confirmadas);",
            f"• **Pagos en revisión:** {len(pending_pays)} pendiente(s) (USD {pending_sum:,.2f});",
            f"• **Canales activos:** {channels}.\n",
            f"**2. Salud del Catálogo e Inventario:**",
            f"• **Catálogo activo:** {len(products)} productos valorizados en **USD {inv_val:,.2f}**;",
            f"• **Alertas de stock:** {len(out_of_stock)} agotado(s) y {len(low_stock)} con stock bajo (≤ 5 uds).",
        ]
        if alert_items:
            briefing.append("\n**Artículos prioritarios para reponer:**")
            for p in alert_items[:4]:
                briefing.append(f"• **{p['name']}**: {int(p['stock'])} uds (USD {p['price']:.2f});")
        briefing.append(
            "\n⚡ **Comandos que puedo ejecutar por ti ahora mismo:**\n"
            "• `\"Agrégame 5 teclados rgb\"` (suma stock o crea el producto);\n"
            "• `\"Reabastece todos los productos con poco stock\"` (+10 uds a cada crítico);\n"
            "• `\"Cambia el precio de [producto] a $35\"`;\n"
            "• `\"Actualiza la tasa del día a 46.50\"`."
        )
        return "\n".join(briefing)

    def respond(self, *, business_id: UUID, user_id: UUID, message: str) -> dict[str, Any]:
        snapshot = self._fetch_live_snapshot(business_id)

        # 1. Check if the owner is commanding an operational action
        cmd_result = self._try_execute_command(
            business_id=business_id,
            user_id=user_id,
            message=message,
            snapshot=snapshot,
        )
        if cmd_result is not None:
            return {
                "success": True,
                "agent": "owner_copilot",
                "business_id": str(business_id),
                "user_id": str(user_id),
                "action_executed": bool(cmd_result.get("action_executed")),
                "action_type": cmd_result.get("action_type"),
                "response": cmd_result["response"],
                "intent": cmd_result.get("action_type") or "owner_command",
                "confidence": 100.0,
            }

        # 2. Check if it's a direct data question or executive briefing
        norm = _norm_text(message)
        is_direct_metric_query = any(
            k in norm
            for k in (
                "hola", "buenos dias", "buenas", "resumen", "briefing", "reporte", "estado",
                "stock", "inventario", "poco stock", "agotado", "venta", "vendido", "pago",
                "pendiente", "canal", "ayuda", "que puedes hacer", "como vamos",
            )
        )
        executive_fallback = self._build_executive_answer(message, snapshot)

        if is_direct_metric_query:
            final_reply = executive_fallback
        else:
            # Try LLM with strict Owner Executive Prompt, falling back to executive_fallback
            sys_prompt = (
                f"Eres el Copiloto Ejecutivo de {snapshot['business_name']} en CALYRISIA.\n"
                f"Estás hablando con el DUEÑO del negocio (NO con un cliente comprador).\n"
                f"Datos reales en vivo del negocio:\n"
                f"- Productos en catálogo: {len(snapshot['products'])} (Valor total: USD {snapshot['inventory_value']:.2f})\n"
                f"- Productos con stock bajo (<=5): {json.dumps(snapshot['low_stock'], ensure_ascii=False)}\n"
                f"- Productos agotados (0): {json.dumps(snapshot['out_of_stock'], ensure_ascii=False)}\n"
                f"- Ventas aprobadas: USD {snapshot['approved_sales_total']:.2f} ({snapshot['approved_sales_count']} pagos)\n"
                f"- Pagos pendientes de aprobación: {len(snapshot['pending_payments'])}\n"
                f"- Canales activos: {', '.join(snapshot['channels_active'])}\n"
                f"Responde de forma ejecutiva, clara, con viñetas ordenadas y datos reales."
            )
            llm_res = self.router.generate_text(
                task_type="copilot_executive",
                system_instruction=sys_prompt,
                user_prompt=message,
                temperature=0.2,
            )
            final_reply = (llm_res.get("text") or "").strip() if llm_res.get("ok") else ""
            if not final_reply:
                final_reply = executive_fallback

        self._log_copilot_action(
            business_id=business_id,
            user_id=user_id,
            tool_name="owner_copilot_query",
            reason="Consulta ejecutiva respondida por el Copiloto.",
            details={"query": message[:250]},
        )

        return {
            "success": True,
            "agent": "owner_copilot",
            "business_id": str(business_id),
            "user_id": str(user_id),
            "action_executed": False,
            "action_type": "executive_query",
            "response": final_reply,
            "intent": "owner_query",
            "confidence": 98.0,
        }