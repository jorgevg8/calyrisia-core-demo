from __future__ import annotations

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


LEAD_STAGES = {"new", "contacted", "qualified", "quoted", "awaiting_payment", "won", "lost"}
CONSENT_STATES = {"unknown", "granted", "denied"}
RADAR_REVIEW_STATES = {"reviewed", "snoozed", "dismissed"}


class GrowthRadarError(ValueError):
    pass


class GrowthRadarService:
    """Tenant-scoped CRM pipeline and deterministic business Radar.

    Radar observations are derived from operational records, not fabricated by an LLM.
    Recommendations stay advisory; payment, inventory and booking changes remain in
    their existing controlled workflows.
    """

    def __init__(self, conn: Any = None):
        self.conn = conn
        self.ensure_schema()


    def _enrich_signal(self, sig: dict[str, Any]) -> dict[str, Any]:
        ev = sig.get("evidence") if isinstance(sig.get("evidence"), dict) else {}
        stype = str(sig.get("signal_type") or "")
        is_hypothesis = stype in {"ai_strategic_opportunity", "market_hypothesis"} or bool(ev.get("is_hypothesis"))
        return {
            **sig,
            "finding_kind": "ai_hypothesis" if is_hypothesis else "verified_observation",
            "what_detected": sig.get("what_detected") or sig.get("title") or "Hallazgo operativo detectado",
            "supporting_evidence": sig.get("supporting_evidence") or ev,
            "why_it_matters": sig.get("why_it_matters") or sig.get("summary") or "Impacta conversión y continuidad operativa del negocio.",
            "recommended_action": sig.get("recommended_action") or "Revisar y ejecutar acción sugerida en el panel.",
            "auto_capability": sig.get("auto_capability") or "CALYRISIA prepara automáticamente el seguimiento y organiza la oportunidad en el CRM.",
            "authorization_required": sig.get("authorization_required") if sig.get("authorization_required") is not None else "Confirmación del propietario para cambios de precios, stock físico o pagos.",
        }

    def ensure_schema(self) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_radar_schema")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_sales_leads (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        customer_id UUID REFERENCES public.customers(id) ON DELETE SET NULL,
                        customer_name VARCHAR(200) NOT NULL,
                        customer_phone VARCHAR(80),
                        customer_email VARCHAR(254),
                        source VARCHAR(40) NOT NULL DEFAULT 'manual',
                        interest TEXT,
                        expected_value NUMERIC(14,2),
                        currency VARCHAR(8) NOT NULL DEFAULT 'USD',
                        stage VARCHAR(32) NOT NULL DEFAULT 'new',
                        consent_status VARCHAR(32) NOT NULL DEFAULT 'unknown',
                        last_contact_at TIMESTAMPTZ,
                        next_follow_up_at TIMESTAMPTZ,
                        notes TEXT,
                        created_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_calyrisia_sales_leads_business_customer
                    ON public.calyrisia_sales_leads (business_id, customer_id)
                    WHERE customer_id IS NOT NULL
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_lead_activities (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        lead_id UUID NOT NULL REFERENCES public.calyrisia_sales_leads(id) ON DELETE CASCADE,
                        activity_type VARCHAR(40) NOT NULL,
                        details TEXT,
                        actor_user_id UUID REFERENCES public.users(id) ON DELETE SET NULL,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_radar_reviews (
                        business_id UUID NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        signal_key VARCHAR(220) NOT NULL,
                        state VARCHAR(24) NOT NULL DEFAULT 'reviewed',
                        note TEXT,
                        updated_by UUID REFERENCES public.users(id) ON DELETE SET NULL,
                        expires_at TIMESTAMPTZ,
                        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        PRIMARY KEY (business_id, signal_key)
                    )
                """)
                cur.execute("RELEASE SAVEPOINT sp_radar_schema")
            self.conn.commit()
        except Exception:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_radar_schema")
            except Exception:
                pass


    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, (datetime, date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(k): GrowthRadarService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [GrowthRadarService._safe(v) for v in value]
        return value

    @staticmethod
    def _parse_datetime(value: Any, field_name: str = "fecha") -> datetime | None:
        if value in (None, ""):
            return None
        if isinstance(value, datetime):
            parsed = value
        else:
            try:
                parsed = datetime.fromisoformat(str(value).strip().replace("Z", "+00:00"))
            except (ValueError, TypeError) as exc:
                raise GrowthRadarError(f"El campo {field_name} no contiene una fecha válida.") from exc
        # Browser datetime-local values do not carry an offset; store them as UTC
        # rather than silently depending on the database server's timezone.
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed

    @staticmethod
    def _money(value: Any, field_name: str = "valor estimado") -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            amount = Decimal(str(value))
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise GrowthRadarError(f"El campo {field_name} debe ser numérico.") from exc
        if not amount.is_finite() or amount < 0 or amount > Decimal("999999999999"):
            raise GrowthRadarError(f"El campo {field_name} está fuera del rango permitido.")
        return amount.quantize(Decimal("0.01"))

    def sync_auto_opportunities(self, *, business_id: UUID) -> int:
        """Create CRM opportunities only when a real inbound message shows buying intent.

        This is a deterministic first-pass detector based on stored intent/topic and
        commercial phrases. It never sends a message or grants contact consent.
        """
        created = []
        with self.conn.cursor() as cur:
            cur.execute(
                r"""
                WITH detected AS (
                    SELECT * FROM (
                        SELECT DISTINCT ON (c.id)
                            c.id AS customer_id,
                            COALESCE(NULLIF(c.full_name, ''), 'Cliente sin nombre') AS customer_name,
                            c.phone AS customer_phone,
                            c.email AS customer_email,
                            COALESCE(NULLIF(cv.channel::text, ''), NULLIF(c.source, ''), 'conversación') AS detected_channel,
                            COALESCE(NULLIF(cv.topic, ''), NULLIF(cv.intent, ''), NULLIF(cm.intent, ''),
                                     'Consulta comercial detectada') AS interest,
                            COALESCE(cm.created_at, cv.last_message_at, cv.created_at) AS last_contact_at
                        FROM public.customers c
                        JOIN public.conversations cv
                          ON cv.customer_id = c.id AND cv.business_id = c.business_id
                        JOIN public.conversation_messages cm
                          ON cm.conversation_id = cv.id AND cm.business_id = cv.business_id
                        WHERE c.business_id = %s
                          AND COALESCE(c.source, '') <> 'owner_copilot'
                          AND cm.direction = 'inbound'
                          AND cm.created_at >= NOW() - INTERVAL '14 days'
                          AND LENGTH(TRIM(COALESCE(cm.content, ''))) >= 4
                          AND (
                            CONCAT_WS(' ', cv.intent, cv.topic, cm.intent) ~* '(purchase|purchase_intent|product_inquiry|consulta_producto|consulta_inventario|sales?|reservation|appointment|quote|checkout|pricing)'
                            OR COALESCE(cm.content, '') ~* '(precio|precios|cu[aá]nto|cuanto|cuesta|disponible|tienen|tienes|venden|busco|buscando|comprar|quiero|quisiera|quiero hacer un pedido|hacer un pedido|realizar un pedido|reservar|reserva|cita|agendar|cotiz|presupuesto|informaci[oó]n|informacion|env[ií]o|envio|delivery|me interesa|interesad[oa]|price|how much|available|buy|book|appointment|quote|purchase)'
                          )
                          AND COALESCE(cm.content, '') !~* '(no quiero|no me interesa|ya no necesito|no gracias|dejen de escribir|no me contacten|quiero cancelar|quiero devolver|reclamo|queja|problema con mi pedido|estado de mi pedido|donde esta mi pedido|dónde está mi pedido)'
                          AND NOT EXISTS (
                            SELECT 1 FROM public.orders o
                            WHERE o.business_id = c.business_id AND o.customer_id = c.id
                              AND o.created_at >= NOW() - INTERVAL '14 days'
                              AND COALESCE(o.status, '') NOT IN ('cancelled','canceled','void','failed')
                          )
                          AND NOT EXISTS (
                            SELECT 1 FROM public.calyrisia_sales_leads l
                            WHERE l.business_id = c.business_id AND l.customer_id = c.id
                          )
                        ORDER BY c.id, cm.created_at DESC
                    ) candidates
                    ORDER BY last_contact_at DESC
                    LIMIT 100
                ), inserted AS (
                    INSERT INTO public.calyrisia_sales_leads (
                        business_id, customer_id, customer_name, customer_phone, customer_email,
                        source, interest, stage, consent_status, last_contact_at, notes
                    )
                    SELECT %s, customer_id, customer_name, customer_phone, customer_email,
                           'ia_detectado', interest, 'new', 'unknown', last_contact_at,
                           'Creada automáticamente por CALYRISIA al detectar posible intención comercial en '
                           || COALESCE(detected_channel, 'una conversación')
                           || '. Revisa el contexto antes de contactar; el permiso de contacto sigue sin confirmar.'
                    FROM detected
                    ON CONFLICT (business_id, customer_id) WHERE customer_id IS NOT NULL DO NOTHING
                    RETURNING id, business_id, customer_id, customer_name
                )
                SELECT id, business_id, customer_id, customer_name FROM inserted
                """,
                (business_id, business_id),
            )
            created = cur.fetchall()
            for lead_id, lead_business_id, customer_id, customer_name in created:
                cur.execute(
                    """INSERT INTO public.calyrisia_lead_activities
                       (business_id, lead_id, activity_type, details)
                       VALUES (%s, %s, 'ai_detected', %s)""",
                    (lead_business_id, lead_id,
                     'CALYRISIA detectó una posible intención comercial a partir de una conversación real. Revisa el contexto; no se ha enviado ningún mensaje.'),
                )
        return len(created)

    def list_leads(self, *, business_id: UUID, limit: int = 100) -> dict[str, Any]:
        auto_created_count = self.sync_auto_opportunities(business_id=business_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, customer_id, customer_name, customer_phone, customer_email,
                       source, interest, expected_value, currency, stage, consent_status,
                       last_contact_at, next_follow_up_at, notes, created_at, updated_at
                FROM public.calyrisia_sales_leads
                WHERE business_id = %s
                ORDER BY
                    CASE WHEN next_follow_up_at IS NOT NULL AND next_follow_up_at <= NOW()
                         AND stage NOT IN ('won','lost') THEN 0 ELSE 1 END,
                    next_follow_up_at ASC NULLS LAST,
                    updated_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
            lead_rows = cur.fetchall()
            lead_cols = [col.name for col in cur.description]

            # Surface real recent conversations that have no order in the last 14 days
            # and have not already been placed in an open CRM lead. They are suggestions,
            # not a claim that the customer has definitely abandoned a purchase.
            cur.execute(
                """
                SELECT c.id, COALESCE(NULLIF(c.full_name, ''), 'Cliente sin nombre') AS full_name,
                       c.phone, c.email,
                       COALESCE(NULLIF(c.source, ''), MAX(cv.channel::text), 'conversación') AS source,
                       MAX(COALESCE(cv.last_message_at, cv.created_at)) AS last_contact_at,
                       COUNT(DISTINCT cv.id)::int AS conversation_count
                FROM public.customers c
                JOIN public.conversations cv
                  ON cv.customer_id = c.id AND cv.business_id = c.business_id
                WHERE c.business_id = %s
                  AND COALESCE(c.source, '') <> 'owner_copilot'
                  AND COALESCE(cv.last_message_at, cv.created_at) >= NOW() - INTERVAL '14 days'
                  AND NOT EXISTS (
                      SELECT 1 FROM public.orders o
                      WHERE o.business_id = c.business_id AND o.customer_id = c.id
                        AND o.created_at >= NOW() - INTERVAL '14 days'
                        AND COALESCE(o.status, '') NOT IN ('cancelled','canceled','void','failed')
                  )
                  AND NOT EXISTS (
                      SELECT 1 FROM public.calyrisia_sales_leads l
                      WHERE l.business_id = c.business_id AND l.customer_id = c.id
                        AND l.stage NOT IN ('won','lost')
                  )
                GROUP BY c.id, c.full_name, c.phone, c.email, c.source
                ORDER BY MAX(COALESCE(cv.last_message_at, cv.created_at)) DESC
                LIMIT 25
                """,
                (business_id,),
            )
            suggested_rows = cur.fetchall()
            suggested_cols = [col.name for col in cur.description]
            cur.execute(
                """SELECT
                    COUNT(*) FILTER (WHERE stage NOT IN ('won','lost'))::int AS active_opportunities,
                    COUNT(*) FILTER (WHERE stage NOT IN ('won','lost') AND next_follow_up_at IS NOT NULL AND next_follow_up_at <= NOW())::int AS followups_due,
                    COUNT(*) FILTER (WHERE stage='won')::int AS won,
                    COUNT(*) FILTER (WHERE stage='lost')::int AS lost
                   FROM public.calyrisia_sales_leads WHERE business_id=%s""",
                (business_id,),
            )
            summary_row = cur.fetchone()
            summary = {"active_opportunities": int(summary_row[0] or 0), "followups_due": int(summary_row[1] or 0),
                       "won": int(summary_row[2] or 0), "lost": int(summary_row[3] or 0)}

        leads = [self._safe(dict(zip(lead_cols, row))) for row in lead_rows]
        suggested = [self._safe(dict(zip(suggested_cols, row))) for row in suggested_rows]
        return {"success": True, "leads": leads, "suggested_prospects": suggested,
                "summary": summary, "auto_created_count": auto_created_count}

    def create_lead(self, *, business_id: UUID, user_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        name = str(payload.get("customer_name") or "").strip()[:200]
        if not name:
            raise GrowthRadarError("Indica el nombre del cliente o prospecto.")
        customer_id = None
        if payload.get("customer_id"):
            try:
                customer_id = UUID(str(payload["customer_id"]))
            except (ValueError, TypeError) as exc:
                raise GrowthRadarError("El cliente vinculado no es válido.") from exc
            with self.conn.cursor() as cur:
                cur.execute(
                    "SELECT id FROM public.customers WHERE id = %s AND business_id = %s",
                    (customer_id, business_id),
                )
                if not cur.fetchone():
                    raise GrowthRadarError("El contacto no pertenece a este negocio.")

        stage = str(payload.get("stage") or "new").strip().lower()
        if stage not in LEAD_STAGES:
            raise GrowthRadarError("La etapa comercial no es válida.")
        consent = str(payload.get("consent_status") or "unknown").strip().lower()
        if consent not in CONSENT_STATES:
            raise GrowthRadarError("El estado de consentimiento no es válido.")
        source = str(payload.get("source") or "manual").strip()[:40] or "manual"
        interest = str(payload.get("interest") or "").strip()[:2000] or None
        phone = str(payload.get("customer_phone") or "").strip()[:80] or None
        email = str(payload.get("customer_email") or "").strip()[:254] or None
        notes = str(payload.get("notes") or "").strip()[:5000] or None
        currency = str(payload.get("currency") or "USD").strip().upper()[:8] or "USD"
        expected_value = self._money(payload.get("expected_value"))
        next_follow_up = self._parse_datetime(payload.get("next_follow_up_at"), "próximo seguimiento")

        with self.conn.cursor() as cur:
            if customer_id:
                cur.execute(
                    """
                    INSERT INTO public.calyrisia_sales_leads
                        (id, business_id, customer_id, customer_name, customer_phone,
                         customer_email, source, interest, expected_value, currency,
                         stage, consent_status, next_follow_up_at, notes, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    ON CONFLICT (business_id, customer_id) WHERE customer_id IS NOT NULL
                    DO UPDATE SET
                        customer_name = EXCLUDED.customer_name,
                        customer_phone = COALESCE(EXCLUDED.customer_phone, calyrisia_sales_leads.customer_phone),
                        customer_email = COALESCE(EXCLUDED.customer_email, calyrisia_sales_leads.customer_email),
                        source = EXCLUDED.source,
                        interest = COALESCE(EXCLUDED.interest, calyrisia_sales_leads.interest),
                        updated_at = NOW()
                    RETURNING id, customer_id, customer_name, customer_phone, customer_email,
                              source, interest, expected_value, currency, stage, consent_status,
                              last_contact_at, next_follow_up_at, notes, created_at, updated_at
                    """,
                    (uuid4(), business_id, customer_id, name, phone, email, source, interest,
                     expected_value, currency, stage, consent, next_follow_up, notes, user_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO public.calyrisia_sales_leads
                        (id, business_id, customer_name, customer_phone, customer_email,
                         source, interest, expected_value, currency, stage, consent_status,
                         next_follow_up_at, notes, created_by)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING id, customer_id, customer_name, customer_phone, customer_email,
                              source, interest, expected_value, currency, stage, consent_status,
                              last_contact_at, next_follow_up_at, notes, created_at, updated_at
                    """,
                    (uuid4(), business_id, name, phone, email, source, interest, expected_value,
                     currency, stage, consent, next_follow_up, notes, user_id),
                )
            row = cur.fetchone()
            lead = self._safe(dict(zip([c.name for c in cur.description], row)))
            cur.execute(
                """INSERT INTO public.calyrisia_lead_activities
                   (id,business_id,lead_id,activity_type,details,actor_user_id)
                   VALUES (%s,%s,%s,'lead_created',%s,%s)""",
                (uuid4(), business_id, lead["id"], "Prospecto agregado al seguimiento comercial.", user_id),
            )
        return lead

    def update_lead(self, *, business_id: UUID, user_id: UUID, lead_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
        allowed = {"customer_name", "customer_phone", "customer_email", "source", "interest",
                   "expected_value", "currency", "stage", "consent_status", "last_contact_at",
                   "next_follow_up_at", "notes"}
        incoming = {key: value for key, value in payload.items() if key in allowed}
        if not incoming:
            raise GrowthRadarError("No hay cambios válidos para guardar.")
        clean: dict[str, Any] = {}
        if "customer_name" in incoming:
            value = str(incoming["customer_name"] or "").strip()[:200]
            if not value:
                raise GrowthRadarError("El nombre del cliente no puede quedar vacío.")
            clean["customer_name"] = value
        for key, max_len in (("customer_phone", 80), ("customer_email", 254), ("source", 40), ("interest", 2000), ("notes", 5000), ("currency", 8)):
            if key in incoming:
                raw = incoming[key]
                value = str(raw or "").strip()[:max_len]
                clean[key] = (value.upper() if key == "currency" else value) or None
        if "stage" in incoming:
            stage = str(incoming["stage"] or "").strip().lower()
            if stage not in LEAD_STAGES:
                raise GrowthRadarError("La etapa comercial no es válida.")
            clean["stage"] = stage
        if "consent_status" in incoming:
            consent = str(incoming["consent_status"] or "unknown").strip().lower()
            if consent not in CONSENT_STATES:
                raise GrowthRadarError("El estado de consentimiento no es válido.")
            clean["consent_status"] = consent
        if "expected_value" in incoming:
            clean["expected_value"] = self._money(incoming["expected_value"])
        for key in ("last_contact_at", "next_follow_up_at"):
            if key in incoming:
                clean[key] = self._parse_datetime(incoming[key], key.replace("_", " "))
        assignments = [f"{key} = %s" for key in clean]
        params = list(clean.values())
        assignments.append("updated_at = NOW()")
        params.extend([lead_id, business_id])
        with self.conn.cursor() as cur:
            cur.execute(
                f"UPDATE public.calyrisia_sales_leads SET {', '.join(assignments)} "
                "WHERE id = %s AND business_id = %s "
                "RETURNING id, customer_id, customer_name, customer_phone, customer_email, source, interest, expected_value, currency, stage, consent_status, last_contact_at, next_follow_up_at, notes, created_at, updated_at",
                params,
            )
            row = cur.fetchone()
            if not row:
                raise GrowthRadarError("El prospecto no existe en este negocio.")
            lead = self._safe(dict(zip([c.name for c in cur.description], row)))
            if "stage" in clean:
                cur.execute(
                    """INSERT INTO public.calyrisia_lead_activities
                       (id,business_id,lead_id,activity_type,details,actor_user_id)
                       VALUES (%s,%s,%s,'stage_changed',%s,%s)""",
                    (uuid4(), business_id, lead_id, f"Etapa comercial actualizada a: {clean['stage']}.", user_id),
                )
            if "next_follow_up_at" in clean:
                cur.execute(
                    """INSERT INTO public.calyrisia_lead_activities
                       (id,business_id,lead_id,activity_type,details,actor_user_id)
                       VALUES (%s,%s,%s,'follow_up_scheduled',%s,%s)""",
                    (uuid4(), business_id, lead_id, f"Seguimiento programado para: {lead['next_follow_up_at'] or 'sin fecha'}.", user_id),
                )
        return lead

    def add_lead_activity(self, *, business_id: UUID, user_id: UUID, lead_id: UUID, activity_type: str, details: str = "") -> dict[str, Any]:
        allowed = {"note", "contacted", "follow_up_prepared", "sale_won", "sale_lost"}
        activity_type = (activity_type or "").strip().lower()
        if activity_type not in allowed:
            raise GrowthRadarError("El tipo de actividad no es válido.")
        details = str(details or "").strip()[:3000]
        with self.conn.cursor() as cur:
            if activity_type in {"contacted", "sale_won", "sale_lost"}:
                new_stage = {"contacted": "contacted", "sale_won": "won", "sale_lost": "lost"}[activity_type]
                cur.execute(
                    """UPDATE public.calyrisia_sales_leads
                       SET stage=%s, last_contact_at=CASE WHEN %s='contacted' THEN NOW() ELSE last_contact_at END,
                           updated_at=NOW()
                       WHERE id=%s AND business_id=%s RETURNING id""",
                    (new_stage, activity_type, lead_id, business_id),
                )
            else:
                cur.execute(
                    "SELECT id FROM public.calyrisia_sales_leads WHERE id=%s AND business_id=%s",
                    (lead_id, business_id),
                )
            if not cur.fetchone():
                raise GrowthRadarError("El prospecto no existe en este negocio.")
            cur.execute(
                """INSERT INTO public.calyrisia_lead_activities
                   (id,business_id,lead_id,activity_type,details,actor_user_id)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   RETURNING id, activity_type, details, created_at""",
                (uuid4(), business_id, lead_id, activity_type, details or activity_type.replace("_", " "), user_id),
            )
            row = cur.fetchone()
            return self._safe(dict(zip([c.name for c in cur.description], row)))

    def list_lead_activities(self, *, business_id: UUID, lead_id: UUID, limit: int = 30) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """SELECT id, activity_type, details, created_at
                   FROM public.calyrisia_lead_activities
                   WHERE business_id=%s AND lead_id=%s
                   ORDER BY created_at DESC LIMIT %s""",
                (business_id, lead_id, limit),
            )
            rows = cur.fetchall()
            cols = [c.name for c in cur.description]
        return [self._safe(dict(zip(cols, row))) for row in rows]

    def review_signal(self, *, business_id: UUID, user_id: UUID, signal_key: str, state: str, note: str = "") -> dict[str, Any]:
        state = (state or "").strip().lower()
        if state not in RADAR_REVIEW_STATES:
            raise GrowthRadarError("El estado de revisión no es válido.")
        if not signal_key or len(signal_key) > 220:
            raise GrowthRadarError("La señal indicada no es válida.")
        expires = None
        if state in {"reviewed", "snoozed"}:
            expires_sql = "NOW() + INTERVAL '24 hours'"
        elif state == "dismissed":
            expires_sql = "NOW() + INTERVAL '7 days'"
        else:
            expires_sql = "NULL"
        with self.conn.cursor() as cur:
            cur.execute(
                f"""INSERT INTO public.calyrisia_radar_reviews
                    (business_id, signal_key, state, note, updated_by, expires_at, updated_at)
                    VALUES (%s,%s,%s,%s,%s,{expires_sql},NOW())
                    ON CONFLICT (business_id, signal_key) DO UPDATE SET
                        state=EXCLUDED.state, note=EXCLUDED.note, updated_by=EXCLUDED.updated_by,
                        expires_at=EXCLUDED.expires_at, updated_at=NOW()
                    RETURNING business_id, signal_key, state, note, expires_at, updated_at""",
                (business_id, signal_key, state, str(note or "").strip()[:1000], user_id),
            )
            row = cur.fetchone()
            return self._safe(dict(zip([c.name for c in cur.description], row)))

    def overview(self, *, business_id: UUID) -> dict[str, Any]:
        auto_created_opportunities = self.sync_auto_opportunities(business_id=business_id)
        signals: list[dict[str, Any]] = []
        counters = {"low_stock": 0, "pending_payments": 0, "pending_bookings": 0, "due_follow_ups": 0, "unconverted_conversations": 0, "incomplete_products": 0, "high_demand": 0}

        with self.conn.cursor() as cur:
            # Stock-risk and estimated days of cover: the forecast uses recorded sales only.
            cur.execute(
                """
                SELECT i.id, i.product_id, p.name, i.quantity, i.minimum_quantity,
                       COALESCE(s.units_sold_30d, 0) AS units_sold_30d
                FROM public.inventory i
                JOIN public.products p ON p.id=i.product_id AND p.business_id=i.business_id
                LEFT JOIN LATERAL (
                    SELECT SUM(oi.quantity) AS units_sold_30d
                    FROM public.order_items oi
                    JOIN public.orders o ON o.id=oi.order_id AND o.business_id=oi.business_id
                    WHERE oi.business_id=i.business_id AND oi.product_id=i.product_id
                      AND o.created_at >= NOW() - INTERVAL '30 days'
                      AND COALESCE(o.status, '') NOT IN ('cancelled','canceled','void','failed')
                ) s ON TRUE
                WHERE i.business_id=%s
                ORDER BY (i.quantity - i.minimum_quantity) ASC, p.name ASC
                LIMIT 100
                """,
                (business_id,),
            )
            stock_rows = cur.fetchall()
            for row in stock_rows:
                inventory_id, product_id, name, quantity, minimum, sold_30d = row
                qty = float(quantity or 0)
                min_qty = float(minimum or 0)
                sold = float(sold_30d or 0)
                daily = sold / 30.0
                cover_days = round(qty / daily, 1) if daily > 0 else None
                low_stock = qty <= min_qty
                fast_depletion = cover_days is not None and cover_days <= 7
                if not (low_stock or fast_depletion):
                    continue
                counters["low_stock"] += 1
                priority = "high" if qty <= 0 or (cover_days is not None and cover_days <= 3) else "medium"
                if qty <= 0:
                    description = f"{name}: no quedan unidades registradas en inventario."
                elif cover_days is not None:
                    description = f"{name}: hay {qty:g} unidades y el ritmo registrado de los últimos 30 días estima unas {cover_days:g} jornadas de cobertura."
                else:
                    description = f"{name}: quedan {qty:g} unidades, igual o por debajo del mínimo configurado ({min_qty:g})."
                signals.append({
                    "signal_key": f"stock:{inventory_id}", "type": "inventory", "priority": priority,
                    "title": "Riesgo de agotamiento: " + str(name), "description": description,
                    "evidence": {"product_id": str(product_id), "quantity": qty, "minimum_quantity": min_qty, "units_sold_30d": sold, "estimated_cover_days": cover_days},
                    "suggested_action": "Revisar existencias y preparar una reposición. La previsión es aproximada y usa solo las ventas registradas.",
                    "destination": "specialized",
                })

            cur.execute(
                """SELECT id, amount, currency, payment_method, source, created_at
                   FROM public.webchat_payment_requests
                   WHERE business_id=%s AND status='pending'
                   ORDER BY created_at ASC LIMIT 30""",
                (business_id,),
            )
            payment_rows = cur.fetchall()
            for row in payment_rows:
                payment_id, amount, currency, method, source, created_at = row
                counters["pending_payments"] += 1
                signals.append({
                    "signal_key": f"payment:{payment_id}", "type": "payment", "priority": "high",
                    "title": "Pago pendiente de verificación",
                    "description": f"Solicitud de {float(amount or 0):.2f} {currency or 'USD'} por {method or 'método no indicado'}; aún no está aprobada.",
                    "evidence": {"payment_id": str(payment_id), "amount": float(amount or 0), "currency": str(currency or "USD"), "source": str(source or "webchat"), "created_at": created_at.isoformat() if created_at else None},
                    "suggested_action": "Comprueba el ingreso directamente en el proveedor y usa el Centro de Aprobaciones. No confirmes un pago solo por leer un comprobante.",
                    "destination": "operations",
                })

            cur.execute(
                """SELECT id, booking_type, customer_name, starts_at, service_name, status
                   FROM public.business_bookings
                   WHERE business_id=%s AND status='pending'
                     AND starts_at >= NOW() - INTERVAL '2 hours'
                     AND starts_at <= NOW() + INTERVAL '24 hours'
                   ORDER BY starts_at ASC LIMIT 30""",
                (business_id,),
            )
            booking_rows = cur.fetchall()
            for row in booking_rows:
                booking_id, booking_type, customer_name, starts_at, service_name, status = row
                counters["pending_bookings"] += 1
                kind_label = "reserva" if booking_type == "reservation" else "cita"
                signals.append({
                    "signal_key": f"booking:{booking_id}", "type": "booking", "priority": "medium",
                    "title": f"{kind_label.capitalize()} pendiente de confirmar",
                    "description": f"{customer_name} · {service_name} · {starts_at.isoformat() if starts_at else 'sin fecha'}.",
                    "evidence": {"booking_id": str(booking_id), "booking_type": str(booking_type), "starts_at": starts_at.isoformat() if starts_at else None},
                    "suggested_action": "Revisa la disponibilidad y confirma o contacta al cliente desde la agenda.",
                    "destination": "specialized",
                })

            cur.execute(
                """SELECT id, customer_id, customer_name, customer_phone, interest,
                          stage, consent_status, expected_value, currency, next_follow_up_at
                   FROM public.calyrisia_sales_leads
                   WHERE business_id=%s AND stage NOT IN ('won','lost')
                     AND next_follow_up_at IS NOT NULL AND next_follow_up_at <= NOW()
                   ORDER BY next_follow_up_at ASC LIMIT 30""",
                (business_id,),
            )
            due_rows = cur.fetchall()
            for row in due_rows:
                lead_id, customer_id, customer_name, phone, interest, stage, consent, expected_value, currency, due_at = row
                counters["due_follow_ups"] += 1
                signals.append({
                    "signal_key": f"lead:{lead_id}", "type": "lead", "priority": "high",
                    "title": "Seguimiento comercial vencido: " + str(customer_name),
                    "description": f"Interés: {interest or 'no especificado'}. Seguimiento programado para {due_at.isoformat() if due_at else 'una fecha anterior'}.",
                    "evidence": {"lead_id": str(lead_id), "customer_id": str(customer_id) if customer_id else None, "stage": str(stage), "consent_status": str(consent), "expected_value": float(expected_value) if expected_value is not None else None, "currency": str(currency or "USD"), "phone": str(phone or "")},
                    "suggested_action": "Revisa la conversación y registra el resultado. Solo contacta por canales autorizados y con el consentimiento correspondiente.",
                    "destination": "crm",
                })

            # Recent conversations without a recent order are suggested follow-ups, not automatically labelled lost sales.
            cur.execute(
                """SELECT c.id, COALESCE(NULLIF(c.full_name,''),'Cliente sin nombre') AS full_name, c.phone,
                          COALESCE(NULLIF(c.source,''), MAX(cv.channel::text), 'conversación'),
                          MAX(COALESCE(cv.last_message_at, cv.created_at)) AS last_contact_at,
                          COUNT(DISTINCT cv.id)::int AS conversations
                   FROM public.customers c
                   JOIN public.conversations cv ON cv.customer_id=c.id AND cv.business_id=c.business_id
                   WHERE c.business_id=%s AND COALESCE(c.source,'') <> 'owner_copilot'
                     AND COALESCE(cv.last_message_at,cv.created_at) >= NOW()-INTERVAL '14 days'
                     AND NOT EXISTS (
                       SELECT 1 FROM public.orders o WHERE o.business_id=c.business_id AND o.customer_id=c.id
                         AND o.created_at >= NOW()-INTERVAL '14 days'
                         AND COALESCE(o.status,'') NOT IN ('cancelled','canceled','void','failed')
                     )
                     AND NOT EXISTS (
                       SELECT 1 FROM public.calyrisia_sales_leads l
                       WHERE l.business_id=c.business_id AND l.customer_id=c.id AND l.stage NOT IN ('won','lost')
                     )
                   GROUP BY c.id,c.full_name,c.phone,c.source
                   ORDER BY MAX(COALESCE(cv.last_message_at,cv.created_at)) DESC LIMIT 10""",
                (business_id,),
            )
            conversation_rows = cur.fetchall()
            for row in conversation_rows:
                customer_id, name, phone, source, last_contact, conversation_count = row
                counters["unconverted_conversations"] += 1
                signals.append({
                    "signal_key": f"conversation:{customer_id}", "type": "conversation", "priority": "medium",
                    "title": "Conversación reciente sin pedido registrado: " + str(name),
                    "description": f"Origen: {source}. Se registraron {int(conversation_count or 0)} conversaciones recientes y no aparece un pedido de los últimos 14 días.",
                    "evidence": {"customer_id": str(customer_id), "phone": str(phone or ""), "source": str(source or "conversación"), "last_contact_at": last_contact.isoformat() if last_contact else None, "conversation_count": int(conversation_count or 0)},
                    "suggested_action": "Revisa el historial antes de decidir si corresponde hacer seguimiento. Esto no demuestra por sí solo que se haya perdido una venta.",
                    "destination": "crm",
                })

            cur.execute(
                """SELECT
                     COALESCE(SUM(total_amount) FILTER (WHERE created_at >= NOW()-INTERVAL '7 days'),0),
                     COALESCE(SUM(total_amount) FILTER (WHERE created_at >= NOW()-INTERVAL '14 days' AND created_at < NOW()-INTERVAL '7 days'),0),
                     COUNT(*) FILTER (WHERE created_at >= NOW()-INTERVAL '7 days')::int,
                     COUNT(*) FILTER (WHERE created_at >= NOW()-INTERVAL '14 days' AND created_at < NOW()-INTERVAL '7 days')::int
                   FROM public.orders
                   WHERE business_id=%s AND COALESCE(status,'') NOT IN ('cancelled','canceled','void','failed')""",
                (business_id,),
            )
            trend = cur.fetchone()
            current_sales, previous_sales = float(trend[0] or 0), float(trend[1] or 0)
            current_orders, previous_orders = int(trend[2] or 0), int(trend[3] or 0)

            # Incomplete product information detection (missing price, SKU, or category)
            cur.execute(
                """SELECT id, name, price, sku, category, description
                   FROM public.products
                   WHERE business_id=%s AND status='active'
                     AND (COALESCE(price, 0) <= 0 OR COALESCE(TRIM(category), '') = '' OR COALESCE(TRIM(sku), '') = '')
                   ORDER BY created_at DESC LIMIT 15""",
                (business_id,),
            )
            for prod_row in cur.fetchall():
                p_id, p_name, p_price, p_sku, p_cat, p_desc = prod_row
                missing_parts = []
                if float(p_price or 0) <= 0:
                    missing_parts.append("precio oficial mayor a 0")
                if not str(p_cat or "").strip():
                    missing_parts.append("categoría")
                if not str(p_sku or "").strip():
                    missing_parts.append("código SKU/referencia")
                counters["incomplete_products"] += 1
                signals.append({
                    "signal_key": f"catalog_incomplete:{p_id}",
                    "type": "incomplete_product",
                    "priority": "high" if float(p_price or 0) <= 0 else "low",
                    "title": f"Ficha de producto incompleta: {p_name}",
                    "description": f"Al producto '{p_name}' le falta definir: {', '.join(missing_parts)}.",
                    "evidence": {"product_id": str(p_id), "name": str(p_name), "price": float(p_price or 0), "missing": missing_parts},
                    "suggested_action": "Completa el precio, categoría y SKU en el Catálogo para que el Cerebro IA responda con precisión exacta a los clientes.",
                    "destination": "catalog",
                })

            # High-demand product detection (last 30 days confirmed orders)
            cur.execute(
                """SELECT p.id, p.name, SUM(oi.quantity)::float AS total_qty, COUNT(DISTINCT o.id)::int AS order_count
                   FROM public.order_items oi
                   JOIN public.orders o ON o.id = oi.order_id AND o.business_id = oi.business_id
                   JOIN public.products p ON p.id = oi.product_id AND p.business_id = oi.business_id
                   WHERE oi.business_id = %s
                     AND o.created_at >= NOW() - INTERVAL '30 days'
                     AND COALESCE(o.status, '') NOT IN ('cancelled','canceled','void','failed')
                   GROUP BY p.id, p.name
                   HAVING SUM(oi.quantity) >= 2
                   ORDER BY total_qty DESC LIMIT 5""",
                (business_id,),
            )
            for hd_row in cur.fetchall():
                hp_id, hp_name, hp_qty, hp_orders = hd_row
                counters["high_demand"] += 1
                signals.append({
                    "signal_key": f"high_demand:{hp_id}",
                    "type": "high_demand",
                    "priority": "medium",
                    "title": f"Producto de alta demanda: {hp_name}",
                    "description": f"{hp_name} acumula {hp_qty:g} unidades vendidas en {hp_orders} pedido(s) durante los últimos 30 días.",
                    "evidence": {"product_id": str(hp_id), "units_sold_30d": hp_qty, "orders_30d": hp_orders},
                    "suggested_action": "Asegura disponibilidad continua en inventario y destácalo en tus respuestas o combos promocionales.",
                    "destination": "catalog",
                })

            cur.execute(
                """SELECT signal_key, state, note, expires_at
                   FROM public.calyrisia_radar_reviews
                   WHERE business_id=%s AND (expires_at IS NULL OR expires_at > NOW())""",
                (business_id,),
            )
            reviews = {str(r[0]): {"state": str(r[1]), "note": str(r[2] or ""), "expires_at": r[3].isoformat() if r[3] else None} for r in cur.fetchall()}

        if previous_orders >= 3 and previous_sales > 0 and current_sales <= previous_sales * 0.8:
            change = ((current_sales - previous_sales) / previous_sales) * 100.0
            signals.append({
                "signal_key": "sales:trend_7d", "type": "sales_trend", "priority": "high" if change <= -35 else "medium",
                "title": "Ingresos inferiores a la semana anterior",
                "description": f"Ingresos registrados: {current_sales:.2f} en los últimos 7 días frente a {previous_sales:.2f} en los 7 días anteriores ({change:.1f}%).",
                "evidence": {"current_7d": current_sales, "previous_7d": previous_sales, "change_percent": round(change, 1), "orders_current_7d": current_orders, "orders_previous_7d": previous_orders},
                "suggested_action": "Compara productos, campañas y días equivalentes. Una diferencia puede deberse a estacionalidad o registros incompletos; revisa los datos antes de actuar.",
                "destination": "overview",
            })

        visible = []
        hidden_count = 0
        type_meta = {
            "inventory": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Observación verificada en inventario",
                "why_it_matters": "Evita quiebres de stock y pérdida de ventas cuando los clientes consultan por chat.",
                "auto_capability": "CALYRISIA informa en tiempo real las unidades exactas disponibles y evita ofrecer stock inexistente.",
                "authorization_required": "Autorizar compra a proveedor o ajuste físico de existencias en el catálogo.",
            },
            "payment": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Operación pendiente de autorización (Nivel 3)",
                "why_it_matters": "El cliente ya reportó su pago y espera confirmación para despachar o entregar su pedido.",
                "auto_capability": "CALYRISIA capturó el pedido, verificó duplicidad de referencia y dejó el pago listo en bandeja.",
                "authorization_required": "Verificar el ingreso real en banco/billetera y pulsar Aprobar o Rechazar en Aprobaciones.",
            },
            "booking": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Reserva / cita capturada automáticamente (Nivel 2)",
                "why_it_matters": "Responder rápido a las solicitudes de agenda aumenta la asistencia y fidelidad del cliente.",
                "auto_capability": "CALYRISIA recopiló nombre, teléfono, fecha/hora y servicio, registrando la solicitud en estado pendiente.",
                "authorization_required": "Confirmar o reprogramar el espacio en la agenda del negocio.",
            },
            "lead": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Oportunidad comercial detectada en CRM",
                "why_it_matters": "El seguimiento oportuno a clientes interesados multiplica la tasa de cierre sin invertir más en publicidad.",
                "auto_capability": "CALYRISIA creó la oportunidad automáticamente desde la conversación y calculó el monto estimado.",
                "authorization_required": "Aprobar el contacto de seguimiento o actualizar la etapa comercial en el CRM.",
            },
            "conversation": {
                "finding_kind": "ai_hypothesis",
                "finding_kind_label": "Hipótesis de oportunidad no convertida",
                "why_it_matters": "El cliente interactuó recientemente pero no registra orden confirmada; puede tener una duda pendiente.",
                "auto_capability": "CALYRISIA conserva el historial y contexto del cliente para retomar la atención al instante.",
                "authorization_required": "Revisar la conversación y decidir si enviar un mensaje de seguimiento.",
            },
            "sales_trend": {
                "finding_kind": "ai_hypothesis",
                "finding_kind_label": "Análisis comparativo de tendencia (7 días)",
                "why_it_matters": "Permite detectar desaceleraciones semanales a tiempo y activar promociones sobre clientes recurrentes.",
                "auto_capability": "CALYRISIA compara automáticamente el volumen de órdenes e ingresos frente a la semana previa.",
                "authorization_required": "Definir promociones, ajustes de precios o campañas comerciales.",
            },
            "incomplete_product": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Auditoría de calidad de catálogo",
                "why_it_matters": "Un producto con datos completos (precio, SKU, categoría) permite que la IA cotice sin ambigüedad.",
                "auto_capability": "CALYRISIA audita continuamente el catálogo para detectar fichas incompletas.",
                "authorization_required": "Editar y guardar los campos faltantes del producto en el Catálogo.",
            },
            "high_demand": {
                "finding_kind": "verified_observation",
                "finding_kind_label": "Tendencia verificada de producto líder",
                "why_it_matters": "Los productos de mayor rotación sostienen el flujo de caja y no deben quedarse sin stock.",
                "auto_capability": "CALYRISIA identifica automáticamente los artículos más pedidos y los prioriza al recomendar.",
                "authorization_required": "Asegurar reposición prioritaria con tu distribuidor o proveedor.",
            },
        }
        for signal in signals:
            review = reviews.get(signal["signal_key"], {})
            state = review.get("state", "open")
            if state in {"reviewed", "snoozed", "dismissed"}:
                hidden_count += 1
                continue
            t_info = type_meta.get(signal.get("type", ""), type_meta["conversation"])
            signal["what_detected"] = signal.get("title", "")
            signal["supporting_evidence"] = signal.get("description", "")
            signal["why_it_matters"] = t_info["why_it_matters"]
            signal["recommended_action"] = signal.get("suggested_action", "")
            signal["auto_capability"] = t_info["auto_capability"]
            signal["authorization_required"] = t_info["authorization_required"]
            signal["finding_kind"] = t_info["finding_kind"]
            signal["finding_kind_label"] = t_info["finding_kind_label"]
            signal["review_state"] = state
            signal["review_note"] = review.get("note", "")
            visible.append(signal)
        priority_order = {"high": 0, "medium": 1, "low": 2}
        visible.sort(key=lambda x: (priority_order.get(x["priority"], 3), x["type"], x["title"].lower()))
        return {
            "success": True,
            "auto_created_opportunities": auto_created_opportunities,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "signals": self._safe(visible),
            "counters": {**counters, "open_signals": len(visible), "hidden_signals": hidden_count},
            "sales_trend": {"current_7d": round(current_sales, 2), "previous_7d": round(previous_sales, 2), "change_percent": round(((current_sales - previous_sales) / previous_sales) * 100, 1) if previous_sales > 0 else None, "orders_current_7d": current_orders, "orders_previous_7d": previous_orders},
            "guardrails": [
                "Las señales son recomendaciones derivadas de datos registrados, no garantías de ventas.",
                "Los pagos requieren verificación en el proveedor correspondiente.",
                "Las acciones externas y los mensajes no se consideran enviados hasta que un canal lo confirme.",
            ],
        }
