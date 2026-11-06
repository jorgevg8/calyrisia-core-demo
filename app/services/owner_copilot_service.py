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
    return re.sub(r"[^a-z0-9.$%]+", " ", no_accents).strip()


def _stem_es(word: str) -> str:
    w = word.strip().lower()
    if len(w) > 5 and w.endswith("es") and w[-3] not in "aeiou":
        return w[:-2]
    if len(w) > 3 and w.endswith("s"):
        return w[:-1]
    return w


class OwnerCopilotService:
    """Executive Copilot for the business owner/admin (Human Partner + Advisor + Executor).

    Capable of:
    1. Executing real operational tasks directly from natural language commands:
       - Adding/restocking product units (e.g., "agregame 5 teclados rgb", "suma 10 mouse inalambrico")
       - Subtracting stock / registering counter sales (e.g., "resta 2 a teclado rgb", "vendi 3 mouse en tienda")
       - Creating new catalog items (e.g., "crea el producto Monitor 27 a $190 con 8 en stock")
       - Updating product prices (e.g., "cambia el precio de teclado rgb a $45" or "baja el precio de X un 10%")
       - Deleting/archiving catalog items (e.g., "elimina el producto X")
       - Bulk restocking all low-stock items (e.g., "reabastece todos los productos con poco stock")
       - Updating the daily exchange rate (e.g., "actualiza la tasa del dia a 46.50")
       - Adding rules to the AI instructions (e.g., "agrega la regla: delivery gratis en compras mayores a $50")
    2. Providing human, empathetic, strategic advisory on catalog items (how to sell an item,
       bundle/combo creation, pricing analysis, capital rotation, handling customer objections)
       and answering any unexpected question about the business grounded in live PostgreSQL data.
    """

    def __init__(self, conn):
        self.conn = conn
        self.analytics = AnalyticsService(conn)
        self.business_brain = BusinessBrainService(conn)
        self.recommendations = RecommendationEngine(conn)
        self.inventory = InventoryIntelligenceService(conn)
        self.router = ModelRouterService(conn)

    def _fetch_live_snapshot(self, business_id: UUID) -> dict[str, Any]:
        bid = str(business_id)
        products: list[dict[str, Any]] = []
        pending_payments: list[dict[str, Any]] = []
        approved_sales_total = 0.0
        approved_sales_count = 0
        biz_name = "Tu Negocio"
        biz_type = "sales_small"
        ai_instructions = ""
        exchange_rate = 0.0
        local_currency = "VES"
        owner_whatsapp = ""
        channels_active: list[str] = ["Webchat IA"]
        payment_methods_active: list[str] = []
        crm_leads_count = 0
        pending_bookings_count = 0

        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    "SELECT name, COALESCE(business_type, 'sales_small'), COALESCE(description, ''), COALESCE(webchat_enabled, true) FROM public.businesses WHERE id = %s",
                    (bid,),
                )
                b_row = cur.fetchone()
                if b_row:
                    biz_name = str(b_row[0] or "Tu Negocio")
                    biz_type = str(b_row[1] or "sales_small")
                    ai_instructions = str(b_row[2] or "")
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute(
                    """
                    SELECT p.id::text, p.name, COALESCE(p.price, 0), COALESCE(p.category, 'General'),
                           COALESCE((SELECT SUM(i.quantity) FROM public.inventory i WHERE i.product_id = p.id AND i.business_id = p.business_id), 0),
                           COALESCE(p.description, ''), COALESCE(p.brand, ''), COALESCE(p.sku, '')
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
                            "description": str(r[5] or ""),
                            "brand": str(r[6] or ""),
                            "sku": str(r[7] or ""),
                        }
                    )
            except Exception:
                try:
                    self.conn.rollback()
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
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute(
                    "SELECT COALESCE(exchange_rate, 0), COALESCE(local_currency_code, 'VES'), COALESCE(owner_whatsapp, '') FROM public.business_dashboard_settings WHERE business_id = %s",
                    (bid,),
                )
                d_row = cur.fetchone()
                if d_row:
                    exchange_rate = float(d_row[0] or 0)
                    local_currency = str(d_row[1] or "VES")
                    owner_whatsapp = str(d_row[2] or "")
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute(
                    "SELECT method_code FROM public.business_payment_instructions WHERE business_id = %s AND enabled = true AND btrim(instructions) <> ''",
                    (bid,),
                )
                labels = {
                    "pago_movil": "Pago Móvil",
                    "transferencia": "Transferencia Bancaria",
                    "zelle": "Zelle",
                    "binance": "Binance Pay",
                    "paypal": "PayPal",
                }
                for pr in cur.fetchall():
                    if pr and pr[0]:
                        payment_methods_active.append(labels.get(str(pr[0]), str(pr[0])))
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute("SELECT COUNT(*) FROM public.calyrisia_sales_leads WHERE business_id = %s AND stage NOT IN ('won', 'lost')", (bid,))
                l_row = cur.fetchone()
                if l_row:
                    crm_leads_count = int(l_row[0] or 0)
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute("SELECT COUNT(*) FROM public.business_bookings WHERE business_id = %s AND status = 'pending'", (bid,))
                bk_row = cur.fetchone()
                if bk_row:
                    pending_bookings_count = int(bk_row[0] or 0)
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute("SELECT enabled FROM public.business_whatsapp_channels WHERE business_id = %s::uuid", (bid,))
                w_row = cur.fetchone()
                if w_row and bool(w_row[0]):
                    channels_active.append("WhatsApp QR")
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

            try:
                cur.execute("SELECT enabled FROM public.business_telegram_channels WHERE business_id = %s::uuid", (bid,))
                t_row = cur.fetchone()
                if t_row and bool(t_row[0]):
                    channels_active.append("Telegram Bot")
            except Exception:
                try:
                    self.conn.rollback()
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
                try:
                    self.conn.rollback()
                except Exception:
                    pass

        low_stock = [p for p in products if 0 < p["stock"] <= 5]
        out_of_stock = [p for p in products if p["stock"] <= 0]
        inventory_value = sum(max(0.0, p["stock"]) * p["price"] for p in products)

        return {
            "business_name": biz_name,
            "business_type": biz_type,
            "ai_instructions": ai_instructions,
            "products": products,
            "low_stock": low_stock,
            "out_of_stock": out_of_stock,
            "inventory_value": inventory_value,
            "pending_payments": pending_payments,
            "approved_sales_total": approved_sales_total,
            "approved_sales_count": approved_sales_count,
            "exchange_rate": exchange_rate,
            "local_currency": local_currency,
            "owner_whatsapp": owner_whatsapp,
            "channels_active": channels_active,
            "payment_methods_active": payment_methods_active,
            "crm_leads_count": crm_leads_count,
            "pending_bookings_count": pending_bookings_count,
        }

    def _find_best_product_match(self, query_fragment: str, products: list[dict[str, Any]]) -> dict[str, Any] | None:
        q_norm = _norm_text(query_fragment)
        if not q_norm:
            return None
        stop_words = {
            "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del", "al", "a",
            "producto", "productos", "articulo", "articulos", "unidad", "unidades", "uds",
            "stock", "inventario", "catalogo", "por", "favor", "en", "con", "mas", "sobre",
            "vender", "mejor", "como", "que", "tal", "precio", "cuesta", "vale", "tienda",
            "mostrador", "para", "este", "ese", "mi", "mis",
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
                score = overlap / max(1, min(len(q_tokens), len(p_tokens) + 1))
                if score > best_score:
                    best_score = score
                    best_prod = p
        return best_prod if best_score >= 0.4 else None

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
                        "✅ **¡Buenas noticias, Jefe!** Revisé todo tu catálogo y actualmente **ningún artículo tiene stock crítico (≤ 5 uds)**.\n\n"
                        "Si quieres sumar unidades a un producto puntual, dime por ejemplo: `agrégame 5 teclados rgb` y lo hago al instante."
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
                    f"⚡ **¡Listo Jefe! · Reabastecimiento de Stock Crítico Ejecutado**\n\n"
                    f"Le sumé **+{add_qty} unidades** a los **{len(targets)} artículos** que tenías en alerta o agotados:\n"
                    + "\n".join(updated_lines)
                    + "\n\nEl catálogo y tu Asesor IA en vivo ya están ofreciendo estas nuevas existencias."
                ),
            }

        # 2. UPDATE EXCHANGE RATE (TASA DEL DÍA)
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
                invalidate_business_context_cache(business_id)
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
                        f"✅ **¡Hecho! · Tasa del Día Actualizada**\n\n"
                        f"• **Nueva tasa activa:** **{new_rate:.2f} {snapshot['local_currency']} por 1 USD**;\n"
                        f"• **Conversión automática:** Un artículo o pedido de **USD 50.00** se cotizará automáticamente en **{snapshot['local_currency']} {(50.0 * new_rate):,.2f}** en todos tus canales activos."
                    ),
                }

        # 3. PERCENTAGE PRICE ADJUSTMENT ("baja el precio de X un 10%", "sube el precio de X un 15%")
        m_pct_cmd = re.search(
            r"\b(baja\w*|descuent\w*|reduc\w*|sub\w*|aument\w*|increment\w*)\s+(?:el\s+)?(?:precio\s+(?:de(?:l)?\s+)?)?(.+?)\s+(?:en\s+|un\s+)?(\d{1,2}(?:[.,]\d{1,2})?)\s*%",
            norm,
        )
        if m_pct_cmd:
            verb = m_pct_cmd.group(1)
            prod_query = m_pct_cmd.group(2).strip()
            pct = float(m_pct_cmd.group(3).replace(",", "."))
            matched = self._find_best_product_match(prod_query, products)
            if matched and 0 < pct < 100:
                old_price = matched["price"]
                is_down = any(v in verb for v in ("baja", "descuent", "reduc"))
                factor = (1.0 - pct / 100.0) if is_down else (1.0 + pct / 100.0)
                new_price = round(max(0.01, old_price * factor), 2)
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
                    tool_name="copilot_update_price_pct",
                    reason=f"Ajuste porcentual ({'-' if is_down else '+'}{pct}%) en '{matched['name']}': USD {old_price:.2f} -> USD {new_price:.2f}.",
                    details={"product_id": matched["id"], "old_price": old_price, "new_price": new_price, "pct": pct},
                )
                return {
                    "action_executed": True,
                    "action_type": "update_price",
                    "response": (
                        f"✅ **¡Ajuste Aplicado! · {'Descuento' if is_down else 'Incremento'} del {pct:g}%**\n\n"
                        f"• **Artículo:** {matched['name']};\n"
                        f"• **Precio anterior:** USD {old_price:.2f} → **Precio nuevo:** **USD {new_price:.2f}**;\n"
                        f"• **Existencia actual:** {int(matched['stock'])} unidades.\n\n"
                        f"La IA ya está cotizando con este nuevo precio en tus canales."
                    ),
                }

        # 4. UPDATE PRODUCT PRICE TO EXACT AMOUNT ("cambia el precio de teclado rgb a $42")
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
                        f"✅ **¡Listo Jefe! · Precio Actualizado**\n\n"
                        f"• **Artículo:** {matched['name']};\n"
                        f"• **Precio anterior:** USD {old_price:.2f} → **Precio nuevo:** **USD {new_price:.2f}**;\n"
                        f"• **Stock disponible:** {int(matched['stock'])} unidades.\n\n"
                        f"Ya quedó sincronizado en el catálogo y en el Cerebro IA."
                    ),
                }

        # 5. SUBTRACT STOCK / COUNTER SALE ("resta 2 a teclado rgb", "descuenta 3 mouse", "vendi 2 auriculares en tienda")
        m_sub = re.search(
            r"\b(?:rest(?:a|ame|ar)|descuent(?:a|ame|ar)|quit(?:a|ame|ar)|vend(?:i|imos))\s+"
            r"(?:(\d{1,5})\s+(?:unidades?\s+(?:de|a)\s+|uds?\s+(?:de|a)\s+)?)?"
            r"(.+)$",
            norm,
        )
        if m_sub:
            qty_str = m_sub.group(1)
            rest_raw = m_sub.group(2).strip()
            qty_val = int(qty_str) if qty_str else 1
            m_tail = re.search(r"\b(\d{1,5})\s*(?:unidades?|uds?)?\s*$", rest_raw)
            if qty_str is None and m_tail:
                qty_val = int(m_tail.group(1))
                rest_raw = rest_raw[: m_tail.start()].strip()
            matched = self._find_best_product_match(rest_raw, products)
            if matched:
                old_stock = int(round(matched["stock"]))
                new_stock = max(0, old_stock - qty_val)
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.inventory SET quantity = %s WHERE product_id = %s AND business_id = %s",
                        (new_stock, matched["id"], bid),
                    )
                self.conn.commit()
                invalidate_business_context_cache(business_id)
                self._log_copilot_action(
                    business_id=business_id,
                    user_id=user_id,
                    tool_name="copilot_subtract_stock",
                    reason=f"Descontadas -{qty_val} unidades de '{matched['name']}' ({old_stock} -> {new_stock}).",
                    details={"product_id": matched["id"], "removed_quantity": qty_val, "after_stock": new_stock},
                )
                alert_note = (
                    "\n⚠️ *Ojo Jefe:* Este artículo quedó en stock crítico. Avísame si quieres que lo reabastezcamos."
                    if new_stock <= 5 else ""
                )
                return {
                    "action_executed": True,
                    "action_type": "subtract_stock",
                    "product_id": matched["id"],
                    "new_stock": new_stock,
                    "response": (
                        f"✅ **¡Anotado! · Descuento de Inventario Ejecutado**\n\n"
                        f"• **Artículo:** {matched['name']};\n"
                        f"• **Unidades descontadas:** −{qty_val} uds;\n"
                        f"• **Stock actualizado:** {old_stock} uds → **{new_stock} unidades disponibles**."
                        f"{alert_note}"
                    ),
                }

        # 6. DELETE / ARCHIVE PRODUCT ("elimina el producto X", "borra X del catalogo")
        m_del = re.search(
            r"\b(?:elimin(?:a|ar|ame)|borr(?:a|ar|ame)|desactiv(?:a|ar|ame)|retir(?:a|ar|ame))\s+(?:el\s+producto\s+|el\s+articulo\s+)?(.+?)(?:\s+del\s+catalogo|\s+del\s+inventario)?$",
            norm,
        )
        if m_del:
            prod_query = m_del.group(1).strip()
            matched = self._find_best_product_match(prod_query, products)
            if matched:
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.products SET status = 'archived', updated_at = NOW() WHERE id = %s AND business_id = %s",
                        (matched["id"], bid),
                    )
                self.conn.commit()
                invalidate_business_context_cache(business_id)
                self._log_copilot_action(
                    business_id=business_id,
                    user_id=user_id,
                    tool_name="copilot_archive_product",
                    reason=f"Producto '{matched['name']}' retirado del catálogo activo.",
                    details={"product_id": matched["id"], "product_name": matched["name"]},
                )
                return {
                    "action_executed": True,
                    "action_type": "archive_product",
                    "response": (
                        f"✅ **¡Hecho! · Artículo Retirado del Catálogo**\n\n"
                        f"He desactivado **{matched['name']}** de tu catálogo activo para que la IA ya no lo ofrezca a los clientes."
                    ),
                }

        # 7. APPEND AI INSTRUCTION / BUSINESS RULE ("agrega la regla: ...", "dile a la ia que ...")
        m_rule = re.search(
            r"\b(?:agrega\s+la\s+regla|nueva\s+regla|dile\s+a\s+la\s+ia\s+que|instruye\s+a\s+la\s+ia\s+que)\s*:?\s*(.+)$",
            raw_msg,
            re.IGNORECASE,
        )
        if m_rule:
            new_rule = m_rule.group(1).strip()
            if len(new_rule) >= 5:
                current_desc = snapshot.get("ai_instructions") or ""
                updated_desc = (current_desc.strip() + f"\n- REGLA EJECUTIVA: {new_rule}").strip()[:3000]
                with self.conn.cursor() as cur:
                    cur.execute(
                        "UPDATE public.businesses SET description = %s, updated_at = NOW() WHERE id = %s",
                        (updated_desc, bid),
                    )
                self.conn.commit()
                invalidate_business_context_cache(business_id)
                self._log_copilot_action(
                    business_id=business_id,
                    user_id=user_id,
                    tool_name="copilot_update_ai_rule",
                    reason=f"Nueva directriz añadida al Cerebro IA: {new_rule[:120]}",
                    details={"rule": new_rule},
                )
                return {
                    "action_executed": True,
                    "action_type": "update_ai_rule",
                    "response": (
                        f"✅ **¡Regla Incorporada al Cerebro IA!**\n\n"
                        f"Acabo de entrenar a tu asistente de ventas con esta directriz:\n"
                        f"• `\"{new_rule}\"`\n\n"
                        f"A partir de este instante, la IA aplicará esta regla cuando atienda clientes en Webchat, WhatsApp, Instagram, Facebook y Telegram."
                    ),
                }

        # 8. ADD / RESTOCK PRODUCT OR CREATE PRODUCT BY NATURAL COMMAND
        m_add = re.search(
            r"\b(?:agreg(?:a|ame|ar|uen)|sum(?:a|ame|ar)|anad(?:e|eme|ir)|repon(?:er|me)?|carg(?:a|ame|ar)|met(?:e|eme)|ingres(?:a|ame|ar)|cre(?:a|ame|ar)|registr(?:a|ame|ar))\s+"
            r"(?:(\d{1,5})\s+(?:unidades?\s+(?:de|a)\s+|uds?\s+(?:de|a)\s+)?)?"
            r"(.+)$",
            norm,
        )
        if m_add:
            qty_str = m_add.group(1)
            rest_raw = m_add.group(2).strip()

            qty_val = int(qty_str) if qty_str else None
            price_val: float | None = None

            m_pr = re.search(r"(?:\ba\s+\$?|\bprecio\s+\$?|\$)(\d+(?:[.,]\d{1,2})?)\b", rest_raw)
            if m_pr:
                price_val = float(m_pr.group(1).replace(",", "."))
                rest_raw = (rest_raw[: m_pr.start()] + " " + rest_raw[m_pr.end() :]).strip()

            m_tail_qty = re.search(r"\b(?:con\s+|stock\s+)?(\d{1,5})\s*(?:unidades?|uds?|en\s+stock|stock)?\s*$", rest_raw)
            if qty_val is None and m_tail_qty:
                qty_val = int(m_tail_qty.group(1))
                rest_raw = rest_raw[: m_tail_qty.start()].strip()

            if qty_val is None:
                qty_val = 1

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
                            f"✅ **¡Listo Jefe! · Reposición de Inventario Ejecutada**\n\n"
                            f"• **Producto:** {matched['name']};\n"
                            f"• **Unidades agregadas:** +{qty_val} uds;\n"
                            f"• **Stock actualizado:** {old_stock} uds → **{new_stock} unidades disponibles**;\n"
                            f"• **Precio unitario activo:** USD {final_price:.2f}.\n\n"
                            f"El inventario ya quedó actualizado en tiempo real para todos tus canales de venta."
                        ),
                    }
                else:
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
                        else f"USD {inferred_price:.2f} (dime `cambia el precio de {display_name.lower()} a $X` si quieres ajustarlo)"
                    )
                    return {
                        "action_executed": True,
                        "action_type": "create_product",
                        "product_id": new_pid,
                        "product_name": display_name,
                        "new_stock": qty_val,
                        "response": (
                            f"✅ **¡Listo Jefe! · Nuevo Producto Creado en Catálogo**\n\n"
                            f"Como **{display_name}** no existía aún en tu inventario, lo creé automáticamente por ti:\n"
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
        ex_rate = snapshot["exchange_rate"]
        loc_curr = snapshot["local_currency"]
        in_stock = [p for p in products if p["stock"] > 0]

        def _fmt_usd(val: float) -> str:
            base = f"USD {val:,.2f}"
            if ex_rate > 0:
                base += f" (≈ {loc_curr} {val * ex_rate:,.2f})"
            return base

        # 1. PRODUCT-SPECIFIC ADVISORY FOR THE OWNER ("cómo vendo X", "háblame de X", "asesoría sobre X")
        matched_prod = self._find_best_product_match(message, products)
        is_asking_about_item = any(
            w in norm
            for w in (
                "asesor", "vender", "vendo", "promocion", "impulsar", "rotar", "opinas",
                "opinion", "hablame", "dime", "detalle", "margen", "capital", "articulo",
                "producto", "como", "que tal", "precio",
            )
        )
        if matched_prod and (is_asking_about_item or len(norm.split()) <= 6):
            p = matched_prod
            cap_tied = max(0.0, p["stock"]) * p["price"]
            companions = [x for x in in_stock if x["id"] != p["id"]]
            comp = companions[0] if companions else None
            combo_line = (
                f"• **Idea de Combo Ganador:** Ármalo en paquete con **{comp['name']}** (Precio normal: USD {(p['price'] + comp['price']):.2f} → **Precio Combo sugerido: USD {((p['price'] + comp['price']) * 0.92):.2f}** con 8% de descuento para subir el ticket promedio)."
                if comp else "• **Estrategia de Cierre:** Destaca su disponibilidad inmediata y ofrece entrega prioritaria hoy mismo."
            )
            stock_status_advice = (
                "⚠️ **Alerta de Stock:** Está agotado (0 uds). Dime `agrégame 10 " + p["name"].lower() + "` para reponerlo ya mismo y no perder ventas."
                if p["stock"] <= 0
                else (
                    f"⚠️ **Atención de Stock:** Solo quedan **{int(p['stock'])} unidades**. Usa el gatillo de escasez (\"¡Últimas {int(p['stock'])} unidades disponibles!\") en tus estados de WhatsApp e Instagram."
                    if p["stock"] <= 5
                    else f"✅ **Buen respaldo de inventario ({int(p['stock'])} uds):** Tienes **{_fmt_usd(cap_tied)}** en capital aquí. Es un excelente candidato para empujar en campañas rápidas o combos."
                )
            )
            return (
                f"🎯 **Asesoría Ejecutiva de Artículo · {p['name']}**\n\n"
                f"Aquí tienes la radiografía comercial y cómo sacarle el máximo provecho en **{biz_name}**:\n"
                f"• **Categoría:** {p['category']} | **Precio activo:** **{_fmt_usd(p['price'])}**;\n"
                f"• **Existencia actual:** {int(p['stock'])} unidades (Capital valorizado: **USD {cap_tied:,.2f}**);\n"
                f"• **Diagnóstico de rotación:** {stock_status_advice}\n\n"
                f"💡 **Cómo asesorar y cerrar más ventas de este artículo:**\n"
                f"• **Ángulo comercial:** Cuando el cliente pregunte, resalta su relación calidad-precio y que tienes entrega inmediata verificada;\n"
                f"{combo_line}\n\n"
                f"¿Quieres que ajuste su precio (`cambia el precio de {p['name'].lower()} a $X`) o le sume unidades?"
            )

        # 2. COMBOS, BUNDLES & WHAT TO PROMOTE TODAY ("combo", "promocionar", "impulsar", "recomiendas", "vender más")
        if any(w in norm for w in ("combo", "combos", "paquete", "promocionar", "promociono", "impulsar", "recomiendas", "sugieres", "vender mas", "rotar")):
            if not products:
                return (
                    f"💡 **Estrategia Comercial · {biz_name}**\n\n"
                    f"Aún no tienes artículos activos cargados en el catálogo. Dime por ejemplo: `crea el producto Audífonos Pro a $25 con 15 en stock` "
                    f"y apenas tengamos tus productos listos te diseño combos y campañas para mover inventario."
                )
            by_stock = sorted(in_stock or products, key=lambda x: x["stock"], reverse=True)
            by_val = sorted(in_stock or products, key=lambda x: x["stock"] * x["price"], reverse=True)
            star = by_val[0]
            lines = [
                f"🚀 **Plan de Asesoría Comercial para Impulsar Ventas Hoy · {biz_name}**\n",
                f"Analicé tu inventario en vivo (**{len(products)} SKUs** por **USD {inv_val:,.2f}**) y esto es lo que te recomiendo mover hoy mismo:\n",
                f"**1. Artículo Prioritario para Liberar Capital:**",
                f"• **{star['name']}** ({int(star['stock'])} uds en stock a {_fmt_usd(star['price'])}). Tienes **USD {(star['stock'] * star['price']):,.2f}** concentrados aquí; promoverlo hoy en tus historias de WhatsApp e Instagram te dará liquidez inmediata.\n",
            ]
            if len(by_stock) >= 2:
                p1, p2 = by_stock[0], by_stock[1]
                reg_sum = p1["price"] + p2["price"]
                combo_p = round(reg_sum * 0.90, 2)
                lines.append(
                    f"**2. Combo Relámpago Sugerido (-10%):**\n"
                    f"• **{p1['name']} + {p2['name']}**\n"
                    f"• Precio por separado: USD {reg_sum:.2f} → **Precio Combo Hoy: USD {combo_p:.2f}**.\n"
                    f"• *Mensaje listo para copiar a tu estado de WhatsApp:*\n"
                    f"  `\"🔥 Promo Especial en {biz_name}: Llévate {p1['name']} + {p2['name']} por solo ${combo_p:.2f} (Stock limitado). Escríbenos para apartar el tuyo.\"`"
                )
            if low_stock:
                low_item = low_stock[0]
                lines.append(
                    f"\n**3. Gatillo de Escasez (Últimas Unidades):**\n"
                    f"• De **{low_item['name']}** solo te quedan **{int(low_item['stock'])} unidades**. Anúncialo como \"últimas piezas disponibles\" para cerrar a los clientes indecisos."
                )
            return "\n".join(lines)

        # 3. SALES COACHING & HANDLING CUSTOMER OBJECTIONS ("cliente indeciso", "está caro", "objeción", "cómo cierro")
        if any(w in norm for w in ("indeciso", "caro", "objecion", "rebaja", "descuento", "cerrar", "cliente dice", "convencer", "atender")):
            pay_list = ", ".join(snapshot["payment_methods_active"]) if snapshot["payment_methods_active"] else "Pago Móvil, Binance Pay y Zelle"
            sample_p = in_stock[0] if in_stock else (products[0] if products else None)
            sample_example = (
                f"Por ejemplo, con **{sample_p['name']}** ({_fmt_usd(sample_p['price'])}), destaca que tienes **{int(sample_p['stock'])} unidades verificadas** listas para despacho inmediato."
                if sample_p else "Destaca siempre que tu inventario es real y de entrega inmediata."
            )
            return (
                f"🤝 **Guía Ejecutiva de Cierre y Manejo de Objeciones · {biz_name}**\n\n"
                f"Cuando un cliente está indeciso o siente que un artículo está costoso, nunca compitas solo bajando precio. Usa esta estructura de 3 pasos:\n\n"
                f"**1. Valida con empatía y cambia el foco al valor y garantía:**\n"
                f"• *Qué decirle:* `\"Te entiendo totalmente. Justamente por eso en {biz_name} seleccionamos artículos revisados y con respaldo directo, para que tu inversión te dure y vayas a lo seguro.\"`\n\n"
                f"**2. Ofrece dos caminos claros (Anclaje de Opciones):**\n"
                f"• Muéstrale tu opción principal y al lado una alternativa más accesible de tu catálogo para que elija *cuál* llevar en vez de *si* comprar o no. {sample_example}\n\n"
                f"**3. Facilita el pago y cierra con pregunta doble:**\n"
                f"• Recuérdale que aceptas **{pay_list}**"
                + (f" a tasa oficial del día (**{ex_rate:.2f} {loc_curr}/USD**)" if ex_rate > 0 else "")
                + " y cierra preguntando: `\"¿Prefieres que te lo enviemos hoy con delivery o pasas a retirarlo por tienda?\"`\n\n"
                f"💡 *Tip pro:* Tu Asesor IA de Calyrisia ya aplica esta psicología consultiva automáticamente en tus chats."
            )

        # 4. UNEXPECTED BUSINESS QUESTIONS (ENVÍOS, GARANTÍA, HORARIOS, POLÍTICAS, TASA, EQUIPO)
        if any(w in norm for w in ("envio", "delivery", "garantia", "horario", "politica", "regla", "configur", "como funciona")):
            rules_preview = (snapshot.get("ai_instructions") or "Sin reglas personalizadas aún.")[:320]
            return (
                f"🧭 **Políticas Operativas y Cerebro IA · {biz_name}**\n\n"
                f"Así está operando tu negocio frente a los clientes en este momento:\n"
                f"• **Canales conectados:** {channels};\n"
                f"• **Tasa de cambio activa:** {f'{ex_rate:.2f} {loc_curr} por 1 USD' if ex_rate > 0 else 'Solo USD (tasa en 0)'};\n"
                f"• **Métodos de cobro activos:** {', '.join(snapshot['payment_methods_active']) if snapshot['payment_methods_active'] else 'Pendientes por activar en Configuración → Métodos de Pago'};\n"
                f"• **Instrucciones actuales de tu IA:**\n  `{rules_preview}`\n\n"
                f"💡 *¿Quieres añadir una política nueva sin ir a Configuración?* Escríbeme aquí mismo: `agrega la regla: [tu nueva política de envíos, horarios o garantía]` y yo entreno a la IA al instante."
            )

        # 5. SPECIFIC INVENTORY / STOCK REPORT
        if any(w in norm for w in ("stock", "inventario", "agotad", "reponer", "catalogo", "almacen")):
            lines = [
                f"📦 **Estado de Inventario en Vivo · {biz_name}**\n",
                f"• **Artículos activos en catálogo:** {len(products)} SKUs;",
                f"• **Capital total valorizado:** **{_fmt_usd(inv_val)}**;",
                f"• **Agotados (0 uds):** {len(out_of_stock)} artículo(s);",
                f"• **En alerta de stock bajo (1 a 5 uds):** {len(low_stock)} artículo(s).",
            ]
            if out_of_stock or low_stock:
                lines.append("\n**Artículos que requieren tu atención prioritaria:**")
                for p in (out_of_stock + low_stock)[:8]:
                    st_lbl = "AGOTADO (0 uds)" if p["stock"] <= 0 else f"{int(p['stock'])} uds disponibles"
                    lines.append(f"• **{p['name']}** ({p['category']}) — **{st_lbl}** · {_fmt_usd(p['price'])};")
                lines.append(
                    "\n⚡ *Acción en 1 toque:* Dime `reabastece todos los productos con poco stock` o `agrégame 10 [nombre del producto]` y lo ejecuto ahora mismo."
                )
            else:
                lines.append("\n✅ ¡Excelente! Todos tus productos tienen más de 5 unidades disponibles.")
                if products:
                    lines.append("\n**Tus artículos con mayor capital en almacén:**")
                    top_cap = sorted(products, key=lambda x: x["stock"] * x["price"], reverse=True)[:5]
                    for p in top_cap:
                        lines.append(f"• **{p['name']}** — {int(p['stock'])} uds · {_fmt_usd(p['price'])} (Total: USD {(p['stock'] * p['price']):,.2f});")
            return "\n".join(lines)

        # 6. SPECIFIC SALES, REVENUE & PAYMENTS REPORT
        if any(w in norm for w in ("venta", "vendido", "ingreso", "pago", "cobro", "caja", "pedido", "orden", "aprobacion")):
            pending_sum = sum(p["amount"] for p in pending_pays)
            lines = [
                f"💰 **Balance Comercial, Caja y Cobros · {biz_name}**\n",
                f"• **Ingresos confirmados:** **{_fmt_usd(sales_total)}** ({sales_count} pago(s) verificados);",
                f"• **Pagos esperando tu aprobación:** **{len(pending_pays)} solicitud(es)** por **{_fmt_usd(pending_sum)}**;",
                f"• **Oportunidades activas en CRM:** {snapshot['crm_leads_count']} prospecto(s) en seguimiento;",
                f"• **Tasa de cambio activa:** {f'{ex_rate:.2f} {loc_curr}/USD' if ex_rate > 0 else 'Solo USD'}.",
            ]
            if pending_pays:
                lines.append("\n**Solicitudes listas para revisar en la pestaña Pagos / Aprobaciones:**")
                for pp in pending_pays[:5]:
                    lines.append(f"• **{pp['customer_name']}** — **{_fmt_usd(pp['amount'])}** vía {pp['method']};")
            else:
                lines.append("\n✅ Tienes la bandeja de pagos al día (0 pendientes por revisar).")
            return "\n".join(lines)

        # 7. CONVERSATIONAL GREETING / EMPATHY / EXECUTIVE BRIEFING
        pending_sum = sum(p["amount"] for p in pending_pays)
        alert_items = out_of_stock + low_stock
        top_item_advice = ""
        if in_stock:
            top_p = sorted(in_stock, key=lambda x: x["stock"] * x["price"], reverse=True)[0]
            top_item_advice = (
                f"\n💡 **Mi recomendación comercial para hoy:** Tienes **{int(top_p['stock'])} unidades** de **{top_p['name']}** "
                f"({_fmt_usd(top_p['price'])}). Es tu artículo con mayor capital disponible (**USD {(top_p['stock'] * top_p['price']):,.2f}**): "
                f"pregúntame `¿cómo vendo mejor {top_p['name'].lower()}?` o `sugerir combos rentables` y armamos una promoción rápida."
            )

        briefing = [
            f"👋 **¡Aquí estoy contigo, Jefe! Diagnóstico en Vivo de {biz_name}**\n",
            f"**1. Caja, Ventas y Clientes:**",
            f"• **Ventas aprobadas:** {_fmt_usd(sales_total)} ({sales_count} órdenes confirmadas);",
            f"• **Pagos por revisar:** {len(pending_pays)} pendiente(s) ({_fmt_usd(pending_sum)});",
            f"• **Oportunidades en CRM:** {snapshot['crm_leads_count']} activa(s) | **Canales:** {channels}.\n",
            f"**2. Salud de tu Catálogo e Inventario:**",
            f"• **Catálogo activo:** {len(products)} artículos valorizados en **{_fmt_usd(inv_val)}**;",
            f"• **Alertas de stock:** {len(out_of_stock)} agotado(s) y {len(low_stock)} con stock bajo (≤ 5 uds).",
        ]
        if alert_items:
            briefing.append("\n**Artículos que te sugiero reponer primero:**")
            for p in alert_items[:4]:
                briefing.append(f"• **{p['name']}**: {int(p['stock'])} uds ({_fmt_usd(p['price'])});")
        if top_item_advice:
            briefing.append(top_item_advice)
        briefing.append(
            "\n⚡ **¿Qué hacemos ahora? Pídeme asesoría o dame una orden directa:**\n"
            "• `\"¿Qué combos puedo armar hoy?\"` o `\"¿Cómo cierro un cliente indeciso?\"`;\n"
            "• `\"Agrégame 5 teclados rgb\"` o `\"Vendí 2 mouse en mostrador\"`;\n"
            "• `\"Reabastece todos los productos con poco stock\"`;\n"
            "• `\"Cambia el precio de [producto] a $35\"` o `\"Baja el precio de [producto] un 10%\"`."
        )
        return "\n".join(briefing)

    def respond(
        self,
        *,
        business_id: UUID,
        user_id: UUID,
        message: str,
        history: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        snapshot = self._fetch_live_snapshot(business_id)

        # 1. Check if the owner is commanding an operational database action
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

        # 2. Build our rich deterministic human advisor response (always ready and 100% grounded)
        executive_advisor_reply = self._build_executive_answer(message, snapshot)

        # 3. Try Gemini LLM with full business context + conversation history for open-ended / unexpected questions
        norm = _norm_text(message)
        is_pure_snapshot_shortcut = norm in {
            "resumen", "resumen ejecutivo", "dame un resumen ejecutivo de ventas e inventario",
            "dame un resumen ejecutivo y diagnostico honesto de mi negocio",
            "que productos tienen poco stock",
        }

        final_reply = executive_advisor_reply
        if not is_pure_snapshot_shortcut:
            history_lines = []
            for h in (history or [])[-6:]:
                if isinstance(h, dict) and h.get("content"):
                    role_lbl = "Dueño" if h.get("role") == "user" else "Copiloto"
                    history_lines.append(f"{role_lbl}: {str(h['content'])[:350]}")
            history_block = "\n".join(history_lines)

            sys_prompt = (
                f"Eres el Copiloto Ejecutivo y Socio Comercial de confianza del dueño de {snapshot['business_name']} en CALYRISIA.\n"
                f"Hablas con el DUEÑO del negocio con un tono cálido, humano, cercano ('Jefe', de tú a tú), empático y sumamente inteligente.\n"
                f"Tu misión es triple:\n"
                f"1) Responder cualquier pregunta inesperada sobre el negocio, estrategia comercial, envíos, garantías, precios, clientes o finanzas.\n"
                f"2) Dar asesoría experta sobre los artículos de su catálogo (cómo venderlos mejor, qué combos armar, qué rotar, argumentos de venta y manejo de objeciones).\n"
                f"3) Guiarlo con datos reales en tiempo real de su negocio.\n\n"
                f"DATOS EN VIVO DE {snapshot['business_name'].upper()}:\n"
                f"- Giro: {snapshot['business_type']}\n"
                f"- Catálogo completo ({len(snapshot['products'])} SKUs, Valor total USD {snapshot['inventory_value']:.2f}): {json.dumps(snapshot['products'][:35], ensure_ascii=False)}\n"
                f"- Artículos con stock bajo (<=5): {json.dumps(snapshot['low_stock'], ensure_ascii=False)}\n"
                f"- Artículos agotados (0): {json.dumps(snapshot['out_of_stock'], ensure_ascii=False)}\n"
                f"- Ventas confirmadas: USD {snapshot['approved_sales_total']:.2f} ({snapshot['approved_sales_count']} órdenes)\n"
                f"- Pagos pendientes de aprobación: {len(snapshot['pending_payments'])}\n"
                f"- Oportunidades CRM activas: {snapshot['crm_leads_count']} | Citas/Reservas pendientes: {snapshot['pending_bookings_count']}\n"
                f"- Tasa de cambio: {snapshot['exchange_rate']:.2f} {snapshot['local_currency']}/USD\n"
                f"- Métodos de pago activos: {', '.join(snapshot['payment_methods_active']) or 'Por configurar'}\n"
                f"- Canales activos: {', '.join(snapshot['channels_active'])}\n\n"
                f"Usa negritas (**texto**) para destacar cifras o nombres clave y viñetas (•) claras. Nunca inventes productos que no estén en la lista."
            )
            user_prompt_full = (
                f"HISTORIAL RECIENTE:\n{history_block}\n\nCONSULTA ACTUAL DEL DUEÑO:\n{message}"
                if history_block else message
            )
            llm_res = self.router.generate_text(
                task_type="copilot_executive",
                system_instruction=sys_prompt,
                user_prompt=user_prompt_full,
                temperature=0.35,
                max_output_tokens=850,
                business_id=business_id,
            )
            if llm_res.get("ok") and (llm_res.get("text") or "").strip():
                final_reply = llm_res["text"].strip()

        self._log_copilot_action(
            business_id=business_id,
            user_id=user_id,
            tool_name="owner_copilot_query",
            reason="Consulta ejecutiva y asesoría respondida por el Copiloto.",
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
            "confidence": 99.0,
        }