from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID, uuid4

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

from app.meta_schemas import NormalizedOmnichannelPayload
from app.schemas import IncomingMessage
from app.services.commercial_limits import AIQuotaExceeded, consume_ai_response
from app.services.recommendation_engine import RecommendationEngine
from app.services.tenant_guard import TenantGuard


_PAYMENT_BUTTON_RE = re.compile(
    r"\[BOTON_PAGO:\s*([0-9]+(?:\.[0-9]{1,2})?)\s*(?:\|\s*ITEMS:\s*(\[[^\]]*\]))?\s*\]",
    re.IGNORECASE | re.DOTALL,
)
_TOTAL_AMOUNT_RE = re.compile(
    r"total(?:\s+a\s+pagar|\s+estimado|\s+del\s+pedido)?[^\d$]{0,20}(?:usd|\$)?\s*([0-9]+(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

PAYMENT_METHOD_LABELS = {
    "pago_movil": "Pago Móvil",
    "transferencia": "Transferencia Bancaria",
    "zelle": "Zelle",
    "binance": "Binance Pay",
    "paypal": "PayPal",
}


class BusinessBrainError(Exception):
    """Raised when Business Brain cannot analyze a business."""


class BusinessBrainService:
    """Galaxy Business Brain V1 + Motor Centralizado de IA Omnicanal Multitenant."""

    INVENTORY_LOW = "inventory_low"
    INVENTORY_OUT = "inventory_out_of_stock"

    def __init__(self, conn):
        self.conn = conn
        self.recommendation_engine = RecommendationEngine(conn)
        self.tenant_guard = TenantGuard(conn)

    @staticmethod
    def _safe(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (datetime,)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(k): BusinessBrainService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [BusinessBrainService._safe(v) for v in value]
        return value

    # ------------------------------------------------------------------
    # CENTRALIZACIÓN Y MOTOR OMNICANAL DE IA (WHATSAPP, IG, FB, WEBCHAT)
    # ------------------------------------------------------------------

    def load_tenant_policies_and_prompts(self, tenant_id: UUID) -> dict[str, Any]:
        """Carga las políticas, reglas e instrucciones de IA del `tenant_id` desde la base de datos."""
        self.tenant_guard.require_business(tenant_id)
        policies: list[dict[str, Any]] = []
        prompt_text = ""

        with self.conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    SELECT title, content, item_type, priority
                    FROM business_knowledge_items
                    WHERE business_id = %s AND status = 'active'
                    ORDER BY priority DESC, updated_at DESC
                    LIMIT 25
                    """,
                    (str(tenant_id),),
                )
                for r in cur.fetchall():
                    policies.append(
                        {
                            "title": str(r[0] or ""),
                            "content": str(r[1] or ""),
                            "item_type": str(r[2] or "policy"),
                            "priority": int(r[3] or 50),
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
                    SELECT short_description, policies, processes
                    FROM business_profiles
                    WHERE business_id = %s AND status = 'active'
                    LIMIT 1
                    """,
                    (str(tenant_id),),
                )
                prof = cur.fetchone()
                if prof and prof[0]:
                    prompt_text = str(prof[0])
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass

        return {
            "tenant_id": str(tenant_id),
            "policies_loaded": len(policies) + (1 if prompt_text else 0),
            "policies": policies,
            "prompt_summary": prompt_text,
        }

    @staticmethod
    def _clean_omnichannel_reply(text: str) -> tuple[str, Decimal | None, list[dict[str, Any]]]:
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

    @staticmethod
    def _is_payment_info_request(text: str) -> bool:
        normalized = unicodedata.normalize("NFKD", text or "")
        value = "".join(ch for ch in normalized if not unicodedata.combining(ch)).lower()
        value = re.sub(r"\s+", " ", value).strip()
        if any(phrase in value for phrase in ("no quiero pagar", "no voy a pagar", "no puedo pagar", "no deseo pagar", "no me pases los datos")):
            return False
        phrases = (
            "como pago", "como puedo pagar", "como hago el pago", "metodo de pago",
            "metodos de pago", "datos para pagar", "datos de pago", "instrucciones de pago",
            "pasame los datos", "pasame los numeros", "donde pago", "quiero pagar",
            "voy a pagar", "listo para pagar", "para pagar", "cuenta para pagar",
            "cuenta bancaria", "numero de cuenta", "datos bancarios", "numero de pago movil",
            "datos del pago", "pasame la cuenta", "pasame el pago movil",
        )
        return any(phrase in value for phrase in phrases)

    @staticmethod
    def _looks_like_payment_submission(text: str) -> bool:
        decomposed = unicodedata.normalize("NFKD", text or "")
        normalized = "".join(ch for ch in decomposed if not unicodedata.combining(ch)).lower()
        normalized = re.sub(r"\s+", " ", normalized).strip()
        has_number = bool(re.search(r"\d{4,}", normalized))
        proof_phrases = (
            "referencia", "numero de operacion", "nro de operacion", "operacion bancaria",
            "comprobante", "captura del pago", "pago realizado", "transferencia realizada",
            "ya pague", "he pagado", "pague por pago movil", "te envie el pago",
            "te mande el comprobante", "aqui esta el pago", "aqui esta el comprobante", "pagado",
        )
        has_proof_phrase = any(phrase in normalized for phrase in proof_phrases)
        confirmed = any(phrase in normalized for phrase in (
            "ya pague", "he pagado", "pago realizado", "transferencia realizada", "pagado",
        ))
        return has_proof_phrase and (has_number or confirmed or "comprobante" in normalized or "referencia" in normalized)

    @staticmethod
    def _parse_recent_payment_marker(messages: list[str]) -> tuple[Decimal | None, list[dict[str, Any]]]:
        for content in messages:
            match = _PAYMENT_BUTTON_RE.search(content or "")
            if match:
                amount: Decimal | None = None
                items: list[dict[str, Any]] = []
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
                if amount is not None and amount > 0:
                    return amount, items
            fallback = _TOTAL_AMOUNT_RE.search(content or "")
            if fallback:
                try:
                    amount = Decimal(fallback.group(1)).quantize(Decimal("0.01"))
                    if amount > 0:
                        return amount, []
                except (InvalidOperation, ValueError):
                    continue
        return None, []

    def _get_payment_options(self, business_id: str) -> list[dict[str, str]]:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT method_code, instructions
                    FROM public.business_payment_instructions
                    WHERE business_id = %s::uuid
                      AND enabled = true
                      AND btrim(instructions) <> ''
                    ORDER BY CASE method_code
                        WHEN 'pago_movil' THEN 1
                        WHEN 'transferencia' THEN 2
                        WHEN 'zelle' THEN 3
                        WHEN 'binance' THEN 4
                        WHEN 'paypal' THEN 5
                        ELSE 9
                    END
                    """,
                    (business_id,),
                )
                rows = cur.fetchall()
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass
            return []
        options: list[dict[str, str]] = []
        for code, instructions in rows:
            code_str = str(code or "")
            clean_instructions = str(instructions or "").strip()
            if code_str in PAYMENT_METHOD_LABELS and clean_instructions:
                options.append(
                    {
                        "code": code_str,
                        "label": PAYMENT_METHOD_LABELS[code_str],
                        "instructions": clean_instructions,
                    }
                )
        return options

    def _ensure_customer_and_conversation(
        self,
        *,
        business_id: UUID,
        channel: str,
        sender_id: str,
        sender_name: str,
    ) -> tuple[UUID, UUID, str]:
        clean_sender = str(sender_id or "").strip()[:80] or f"{channel}_user"
        display_name = str(sender_name or "").strip()[:150] or f"Cliente {channel.title()} ({clean_sender[-4:]})"
        bid_str = str(business_id)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name FROM public.customers
                WHERE business_id = %s::uuid AND phone = %s
                ORDER BY created_at DESC LIMIT 1
                """,
                (bid_str, clean_sender),
            )
            row = cur.fetchone()
            if row:
                customer_id = UUID(str(row[0]))
                if sender_name and str(row[1] or "").startswith("Cliente "):
                    cur.execute(
                        "UPDATE public.customers SET full_name = %s, last_interaction_at = now() WHERE id = %s AND business_id = %s::uuid",
                        (display_name, str(customer_id), bid_str),
                    )
                else:
                    display_name = str(row[1] or display_name)
            else:
                customer_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO public.customers (id, business_id, full_name, source, channel, phone, status)
                    VALUES (%s, %s::uuid, %s, %s, %s, %s, 'active')
                    """,
                    (str(customer_id), bid_str, display_name, channel, channel, clean_sender),
                )

            cur.execute(
                """
                SELECT id FROM public.conversations
                WHERE business_id = %s::uuid AND customer_id = %s AND channel = %s AND status = 'active'
                ORDER BY created_at DESC LIMIT 1
                """,
                (bid_str, str(customer_id), channel),
            )
            conv_row = cur.fetchone()
            if conv_row:
                conversation_id = UUID(str(conv_row[0]))
            else:
                conversation_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO public.conversations (id, business_id, customer_id, channel, status, metadata)
                    VALUES (%s, %s::uuid, %s, %s, 'active', %s::jsonb)
                    """,
                    (
                        str(conversation_id),
                        bid_str,
                        str(customer_id),
                        channel,
                        Jsonb({"channel": channel, "sender_id": clean_sender}),
                    ),
                )
        self.conn.commit()
        return customer_id, conversation_id, display_name

    def process_omnichannel_chat(self, payload: NormalizedOmnichannelPayload) -> dict[str, Any]:
        """Enruta un mensaje normalizado (`NormalizedOmnichannelPayload`) al Cerebro IA del tenant con aislamiento total."""
        from app.services.autopilot_service import GalaxyAutopilotService

        tenant_id = payload.tenant_id
        channel = "facebook" if payload.channel == "messenger" else str(payload.channel).lower()
        policy_info = self.load_tenant_policies_and_prompts(tenant_id)
        text = str(payload.message_text or "").strip()
        if not text:
            return {
                "success": True,
                "tenant_id": str(tenant_id),
                "channel": channel,
                "sender_id": payload.sender_id,
                "reply_text": "",
                "customer_id": None,
                "conversation_id": None,
                "policies_loaded": policy_info["policies_loaded"],
            }

        customer_id, conversation_id, display_name = self._ensure_customer_and_conversation(
            business_id=tenant_id,
            channel=channel,
            sender_id=payload.sender_id,
            sender_name=payload.sender_name,
        )

        # Verificar si existe un cobro pendiente reciente en la conversación
        recent_outbound: list[str] = []
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT content FROM public.conversation_messages
                    WHERE business_id = %s::uuid AND customer_id = %s AND conversation_id = %s
                      AND direction = 'outbound'
                    ORDER BY created_at DESC LIMIT 10
                    """,
                    (str(tenant_id), str(customer_id), str(conversation_id)),
                )
                recent_outbound = [str(r[0] or "") for r in cur.fetchall()]
        except Exception:
            try:
                self.conn.rollback()
            except Exception:
                pass

        prior_amount, prior_items = self._parse_recent_payment_marker(recent_outbound)
        is_payment_request = self._is_payment_info_request(text)
        reply_text = ""

        if prior_amount is not None and prior_amount > 0 and self._looks_like_payment_submission(text):
            payment_options = self._get_payment_options(str(tenant_id))
            selected_label = payment_options[0]["label"] if payment_options else f"Pago ({channel.title()})"
            payment_id = uuid4()
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO public.webchat_payment_requests
                    (id, business_id, customer_id, amount, currency, payment_method, status, source,
                     approval_note, items, customer_payment_details)
                    VALUES (%s, %s::uuid, %s, %s, 'USD', %s, 'pending', %s, %s, %s, %s)
                    """,
                    (
                        str(payment_id),
                        str(tenant_id),
                        str(customer_id),
                        prior_amount,
                        selected_label,
                        channel,
                        f"Solicitud recibida por {channel.title()}; pendiente de aprobación del dueño.",
                        Jsonb(prior_items) if prior_items else None,
                        text[:4000],
                    ),
                )
            self.conn.commit()
            reply_text = (
                f"✅ Recibimos tus datos de pago por USD {prior_amount:.2f};\n"
                f"• Estado: PENDIENTE de verificación en el panel del negocio;\n"
                f"• Solicitud: #{str(payment_id)[:8].upper()}.\n\n"
                "Apenas el propietario valide la operación en su cuenta, te confirmaremos por esta misma vía."
            )
        else:
            try:
                consume_ai_response(self.conn, str(tenant_id))
                incoming = IncomingMessage(
                    business_id=tenant_id,
                    customer_id=customer_id,
                    conversation_id=conversation_id,
                    channel=channel,
                    message=text,
                    metadata={
                        **(payload.metadata or {}),
                        "channel": channel,
                        "external_sender_id": payload.sender_id,
                        "sender_name": display_name,
                        "timestamp": payload.timestamp.isoformat(),
                    },
                )
                result = GalaxyAutopilotService(self.conn).respond(incoming)
                raw_reply = str(result.get("response") or "¿En qué puedo ayudarte hoy?")
                clean_reply, pay_amount, _pay_items = self._clean_omnichannel_reply(raw_reply)
                # No enviar cuentas ni instrucciones de cobro junto a una cotización.
                # Solo mostrarlas si el cliente pregunta cómo pagar, usando el importe
                # del pedido de esta respuesta o el marcador guardado en el turno anterior.
                payment_amount = (pay_amount or prior_amount) if is_payment_request else None
                if payment_amount is not None and payment_amount > 0:
                    payment_options = self._get_payment_options(str(tenant_id))
                    if payment_options:
                        details = "\n\n".join(
                            f"{opt['label']}:\n{opt['instructions']}" for opt in payment_options
                        )
                        clean_reply = (
                            f"{clean_reply}\n\n"
                            f"Puedes pagar USD {payment_amount:.2f} con:\n\n"
                            f"{details}\n\n"
                            "Cuando pagues, envíame el método utilizado y la referencia."
                        ).strip()
                    else:
                        clean_reply = (
                            f"{clean_reply}\n\nEl total de referencia es USD {payment_amount:.2f}, "
                            "pero este negocio aún no configuró sus datos de cobro. Consulta con la tienda antes de transferir."
                        ).strip()
                reply_text = clean_reply
            except AIQuotaExceeded as exc:
                reply_text = (
                    f"Hemos alcanzado el límite mensual de {exc.limit} respuestas automáticas del plan actual. "
                    "Un asesor te atenderá en breve."
                )
            except Exception:
                try:
                    self.conn.rollback()
                except Exception:
                    pass
                reply_text = "Gracias por escribirnos. En este momento estamos procesando tu consulta; en breve te respondemos."

        return {
            "success": True,
            "tenant_id": str(tenant_id),
            "channel": channel,
            "sender_id": payload.sender_id,
            "reply_text": reply_text,
            "customer_id": str(customer_id),
            "conversation_id": str(conversation_id),
            "policies_loaded": policy_info["policies_loaded"],
        }

    async def aprocess_omnichannel_chat(self, payload: NormalizedOmnichannelPayload) -> dict[str, Any]:
        """Interfaz asíncrona (`async def`) para procesar mensajes omnicanal desde los webhooks de FastAPI."""
        return self.process_omnichannel_chat(payload)

    # ------------------------------------------------------------------
    # FUNCIONES DE ANÁLISIS E INSIGHTS OPERATIVOS (GALAXY BUSINESS BRAIN)
    # ------------------------------------------------------------------

    def analyze(
        self,
        *,
        business_id: UUID,
        focus: str = "all",
        event_id: str | None = None,
    ) -> dict[str, Any]:
        focus = (focus or "all").strip().lower()
        allowed_focus = {"all", "inventory"}
        if focus not in allowed_focus:
            raise BusinessBrainError(
                f"Invalid focus '{focus}'. Allowed: {sorted(allowed_focus)}"
            )

        started_at = datetime.now(timezone.utc)
        detectors_run: list[str] = []
        insights: list[dict[str, Any]] = []
        recommendations: list[dict[str, Any]] = []

        if focus in {"all", "inventory"}:
            detectors_run.append("inventory_detector")
            inventory_insights = self._detect_inventory_issues(business_id=business_id)
            for insight in inventory_insights:
                persisted = self._persist_or_refresh_insight(
                    business_id=business_id,
                    insight=insight,
                    event_id=event_id,
                )
                insights.append(persisted)
                recommendation = self.recommendation_engine.ensure_for_insight(
                    insight=persisted
                )
                recommendations.append(recommendation)

        completed_at = datetime.now(timezone.utc)
        result = {
            "success": True,
            "stage": "business_analysis_completed",
            "business_id": str(business_id),
            "analysis_started_at": started_at.isoformat(),
            "analysis_completed_at": completed_at.isoformat(),
            "focus": focus,
            "detectors_run": detectors_run,
            "insights_detected": len(insights),
            "recommendations_generated": len(recommendations),
            "insights": self._safe(insights),
            "recommendations": self._safe(recommendations),
        }
        self._write_analysis_audit(
            business_id=business_id,
            focus=focus,
            event_id=event_id,
            insights=insights,
            recommendations=recommendations,
        )
        return result

    def _write_analysis_audit(
        self,
        *,
        business_id: UUID,
        focus: str,
        event_id: str | None,
        insights: list[dict[str, Any]],
        recommendations: list[dict[str, Any]],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id,
                    actor_type,
                    action_type,
                    resource_type,
                    resource_id,
                    status,
                    reason,
                    metadata,
                    created_at
                )
                VALUES (
                    %s, 'system', 'business_brain_analysis',
                    'business', %s, 'success', %s, %s, NOW()
                )
                """,
                (
                    business_id,
                    business_id,
                    f"Business Brain analysis: focus={focus}",
                    Jsonb(
                        cls_safe({
                            "focus": focus,
                            "source_event_id": event_id,
                            "insight_count": len(insights),
                            "recommendation_count": len(recommendations),
                            "insight_ids": [item.get("id") for item in insights],
                            "recommendation_ids": [item.get("id") for item in recommendations],
                        })
                    ),
                ),
            )
        self.conn.commit()

    def list_insights(
        self,
        *,
        business_id: UUID,
        status: str = "open",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        allowed_status = {"open", "acknowledged", "resolved", "dismissed"}
        if status not in allowed_status:
            raise BusinessBrainError(
                f"Invalid insight status '{status}'. Allowed: {sorted(allowed_status)}"
            )
        limit = max(1, min(limit, 100))

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, insight_type, category, severity,
                       priority, entity_type, entity_id, title, description,
                       status, confidence, evidence, source_event_id,
                       detected_at, resolved_at, created_at, updated_at
                FROM business_insights
                WHERE business_id = %s
                  AND status = %s
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    detected_at DESC
                LIMIT %s
                """,
                (business_id, status, limit),
            )
            rows = cur.fetchall()
        return [self._insight_row_to_dict(row) for row in rows]

    def acknowledge_insight(
        self,
        *,
        business_id: UUID,
        insight_id: UUID,
        status: str,
    ) -> dict[str, Any]:
        allowed_status = {"acknowledged", "resolved", "dismissed", "open"}
        if status not in allowed_status:
            raise BusinessBrainError(
                f"Invalid insight status '{status}'. Allowed: {sorted(allowed_status)}"
            )

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE business_insights
                SET status = %s,
                    resolved_at = CASE
                        WHEN %s IN ('resolved', 'dismissed') THEN NOW()
                        ELSE resolved_at
                    END,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                RETURNING id, business_id, insight_type, category, severity,
                          priority, entity_type, entity_id, title, description,
                          status, confidence, evidence, source_event_id,
                          detected_at, resolved_at, created_at, updated_at
                """,
                (status, status, insight_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                raise BusinessBrainError("Insight not found for this business")
        self.conn.commit()
        return self._insight_row_to_dict(row)

    def _detect_inventory_issues(self, *, business_id: UUID) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    i.id,
                    i.product_id,
                    i.quantity,
                    i.minimum_quantity,
                    i.location,
                    i.last_counted_at,
                    i.last_count_method,
                    p.name,
                    p.sku,
                    p.status,
                    p.is_service
                FROM inventory i
                JOIN products p
                  ON p.id = i.product_id
                 AND p.business_id = i.business_id
                WHERE i.business_id = %s
                  AND p.status = 'active'
                ORDER BY p.name
                """,
                (business_id,),
            )
            rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for row in rows:
            quantity = row[2]
            minimum = row[3]
            if quantity is None or minimum is None:
                continue

            quantity_number = float(quantity)
            minimum_number = float(minimum)
            if quantity_number <= 0:
                results.append(
                    self._inventory_insight(
                        business_id=business_id,
                        inventory_id=row[0],
                        product_id=row[1],
                        product_name=row[7],
                        sku=row[8],
                        quantity=quantity_number,
                        minimum_quantity=minimum_number,
                        location=row[4],
                        insight_type=self.INVENTORY_OUT,
                        severity="critical",
                        priority="critical",
                        title=f"{row[7]} está agotado",
                        description=(
                            f"El inventario de {row[7]} está en {quantity_number:g} unidades "
                            f"y el mínimo operativo configurado es {minimum_number:g}."
                        ),
                        last_counted_at=row[5],
                        last_count_method=row[6],
                    )
                )
            elif quantity_number < minimum_number:
                results.append(
                    self._inventory_insight(
                        business_id=business_id,
                        inventory_id=row[0],
                        product_id=row[1],
                        product_name=row[7],
                        sku=row[8],
                        quantity=quantity_number,
                        minimum_quantity=minimum_number,
                        location=row[4],
                        insight_type=self.INVENTORY_LOW,
                        severity="high",
                        priority="high",
                        title=f"Stock bajo de {row[7]}",
                        description=(
                            f"El inventario de {row[7]} está en {quantity_number:g} unidades "
                            f"y el mínimo operativo configurado es {minimum_number:g}."
                        ),
                        last_counted_at=row[5],
                        last_count_method=row[6],
                    )
                )

        return results

    @classmethod
    def _inventory_insight(
        cls,
        *,
        business_id: UUID,
        inventory_id: UUID,
        product_id: UUID,
        product_name: str,
        sku: str | None,
        quantity: float,
        minimum_quantity: float,
        location: str | None,
        insight_type: str,
        severity: str,
        priority: str,
        title: str,
        description: str,
        last_counted_at: Any,
        last_count_method: str | None,
    ) -> dict[str, Any]:
        fingerprint = f"{insight_type}:{product_id}"
        evidence = {
            "inventory_id": str(inventory_id),
            "product_id": str(product_id),
            "product_name": product_name,
            "sku": sku,
            "quantity": quantity,
            "minimum_quantity": minimum_quantity,
            "shortage_units": max(minimum_quantity - quantity, 0),
            "location": location,
            "last_counted_at": cls._safe(last_counted_at),
            "last_count_method": last_count_method,
        }
        return {
            "business_id": str(business_id),
            "insight_type": insight_type,
            "category": "problem",
            "severity": severity,
            "priority": priority,
            "entity_type": "product",
            "entity_id": str(product_id),
            "entity_name": product_name,
            "title": title,
            "description": description,
            "status": "open",
            "confidence": 100.0,
            "evidence": evidence,
            "source": "business_brain.inventory",
            "fingerprint": fingerprint,
        }

    def _persist_or_refresh_insight(
        self,
        *,
        business_id: UUID,
        insight: dict[str, Any],
        event_id: str | None,
    ) -> dict[str, Any]:
        source_event_uuid = self._event_uuid_or_none(event_id)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, insight_type, category, severity,
                       priority, entity_type, entity_id, title, description,
                       status, confidence, evidence, source_event_id,
                       detected_at, resolved_at, created_at, updated_at
                FROM business_insights
                WHERE business_id = %s
                  AND fingerprint = %s
                  AND status IN ('open', 'acknowledged')
                LIMIT 1
                """,
                (business_id, insight["fingerprint"]),
            )
            existing = cur.fetchone()

            if existing:
                cur.execute(
                    """
                    UPDATE business_insights
                    SET severity = %s,
                        priority = %s,
                        title = %s,
                        description = %s,
                        confidence = %s,
                        evidence = %s,
                        source_event_id = COALESCE(%s, source_event_id),
                        detected_at = NOW(),
                        updated_at = NOW()
                    WHERE id = %s
                    RETURNING id, business_id, insight_type, category, severity,
                              priority, entity_type, entity_id, title, description,
                              status, confidence, evidence, source_event_id,
                              detected_at, resolved_at, created_at, updated_at
                    """,
                    (
                        insight["severity"],
                        insight["priority"],
                        insight["title"],
                        insight["description"],
                        insight["confidence"],
                        Jsonb(cls_safe(insight["evidence"])),
                        source_event_uuid,
                        existing[0],
                    ),
                )
                row = cur.fetchone()
            else:
                insight_id = uuid4()
                cur.execute(
                    """
                    INSERT INTO business_insights (
                        id, business_id, insight_type, category, severity,
                        priority, entity_type, entity_id, title, description,
                        status, confidence, evidence, source, fingerprint,
                        source_event_id, detected_at, created_at, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, %s, %s, NOW(), NOW(), NOW()
                    )
                    RETURNING id, business_id, insight_type, category, severity,
                              priority, entity_type, entity_id, title, description,
                              status, confidence, evidence, source_event_id,
                              detected_at, resolved_at, created_at, updated_at
                    """,
                    (
                        insight_id,
                        business_id,
                        insight["insight_type"],
                        insight["category"],
                        insight["severity"],
                        insight["priority"],
                        insight["entity_type"],
                        UUID(insight["entity_id"]) if insight.get("entity_id") else None,
                        insight["title"],
                        insight["description"],
                        insight["status"],
                        insight["confidence"],
                        Jsonb(cls_safe(insight["evidence"])),
                        insight["source"],
                        insight["fingerprint"],
                        source_event_uuid,
                    ),
                )
                row = cur.fetchone()
        self.conn.commit()
        result = self._insight_row_to_dict(row)
        result["entity_name"] = insight.get("entity_name")
        return result

    @staticmethod
    def _event_uuid_or_none(event_id: str | None) -> UUID | None:
        if not event_id:
            return None
        try:
            return UUID(str(event_id))
        except ValueError:
            return None

    @staticmethod
    def _insight_row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "business_id": str(row[1]),
            "insight_type": row[2],
            "category": row[3],
            "severity": row[4],
            "priority": row[5],
            "entity_type": row[6],
            "entity_id": str(row[7]) if row[7] else None,
            "title": row[8],
            "description": row[9],
            "status": row[10],
            "confidence": float(row[11]) if row[11] is not None else None,
            "evidence": row[12] or {},
            "source_event_id": str(row[13]) if row[13] else None,
            "detected_at": row[14].isoformat() if row[14] else None,
            "resolved_at": row[15].isoformat() if row[15] else None,
            "created_at": row[16].isoformat() if row[16] else None,
            "updated_at": row[17].isoformat() if row[17] else None,
        }


def cls_safe(value: Any) -> Any:
    """Small JSON-safe helper used only for database evidence payloads."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): cls_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [cls_safe(v) for v in value]
    return value
