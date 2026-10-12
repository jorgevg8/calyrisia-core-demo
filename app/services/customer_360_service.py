from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.services.tenant_guard import TenantGuard, TenantIsolationError


class Customer360Error(Exception):
    pass


class Customer360Service:
    """Step 44: Customer 360 profile + derived operational metrics."""

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    def _require_customer(self, business_id: UUID, customer_id: UUID) -> None:
        try:
            self.tenant.require_business(business_id)
            self.tenant.require_resource(
                business_id=business_id,
                resource_type="customer",
                resource_id=customer_id,
            )
        except TenantIsolationError as exc:
            raise Customer360Error(str(exc)) from exc

    def _ensure_profile_row(self, business_id: UUID, customer_id: UUID) -> UUID:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM customer_360_profiles WHERE business_id = %s AND customer_id = %s",
                (business_id, customer_id),
            )
            row = cur.fetchone()
            if row:
                return row[0]
            profile_id = uuid4()
            cur.execute(
                """
                INSERT INTO customer_360_profiles (id, business_id, customer_id)
                VALUES (%s, %s, %s)
                """,
                (profile_id, business_id, customer_id),
            )
        self.conn.commit()
        return profile_id

    def _fetch_profile(self, business_id: UUID, customer_id: UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, customer_id, lifecycle_stage, segment,
                       tags, preferences, communication_preferences, consent,
                       summary, value_score, total_orders, total_spend,
                       conversation_count, last_order_at, last_conversation_at,
                       last_appointment_at, last_channel, metadata,
                       created_at, updated_at
                FROM customer_360_profiles
                WHERE business_id = %s AND customer_id = %s
                """,
                (business_id, customer_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        keys = [
            "id", "business_id", "customer_id", "lifecycle_stage", "segment",
            "tags", "preferences", "communication_preferences", "consent",
            "summary", "value_score", "total_orders", "total_spend",
            "conversation_count", "last_order_at", "last_conversation_at",
            "last_appointment_at", "last_channel", "metadata",
            "created_at", "updated_at",
        ]
        data = dict(zip(keys, row))
        data["business_id"] = str(data["business_id"])
        data["customer_id"] = str(data["customer_id"])
        data["id"] = str(data["id"])
        data["value_score"] = float(data["value_score"] or 0)
        data["total_spend"] = float(data["total_spend"] or 0)
        return self._safe(data)

    def rebuild(self, *, business_id: UUID, customer_id: UUID) -> dict[str, Any]:
        self._require_customer(business_id, customer_id)
        profile_id = self._ensure_profile_row(business_id, customer_id)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT full_name, email, phone, status, source,
                       first_contact_at, last_interaction_at, notes
                FROM customers
                WHERE id = %s AND business_id = %s
                """,
                (customer_id, business_id),
            )
            customer = cur.fetchone()
            if not customer:
                raise Customer360Error("Customer not found for this business")

            cur.execute(
                """
                SELECT COUNT(*)::int,
                       COALESCE(SUM(total_amount), 0),
                       MAX(created_at)
                FROM orders
                WHERE business_id = %s AND customer_id = %s
                """,
                (business_id, customer_id),
            )
            order_row = cur.fetchone()

            cur.execute(
                """
                SELECT COUNT(*)::int, MAX(last_message_at)
                FROM conversations
                WHERE business_id = %s AND customer_id = %s
                """,
                (business_id, customer_id),
            )
            conversation_row = cur.fetchone()

            cur.execute(
                """
                SELECT channel
                FROM conversations
                WHERE business_id = %s AND customer_id = %s
                ORDER BY last_message_at DESC NULLS LAST, created_at DESC
                LIMIT 1
                """,
                (business_id, customer_id),
            )
            channel_row = cur.fetchone()

            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema='public' AND table_name='appointments'
                )
                """
            )
            appointments_exists = bool(cur.fetchone()[0])
            last_appointment = None
            if appointments_exists:
                cur.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema='public' AND table_name='appointments'
                    """
                )
                columns = {r[0] for r in cur.fetchall()}
                date_col = next((c for c in ("starts_at", "start_at", "scheduled_at", "created_at") if c in columns), None)
                if date_col:
                    cur.execute(
                        f"SELECT MAX({date_col}) FROM appointments WHERE business_id = %s AND customer_id = %s",
                        (business_id, customer_id),
                    )
                    last_appointment = cur.fetchone()[0]

            cur.execute(
                "SELECT COUNT(*)::int FROM memory WHERE business_id = %s AND customer_id = %s",
                (business_id, customer_id),
            )
            memory_count = int(cur.fetchone()[0] or 0)

            cur.execute(
                "SELECT lifecycle_stage, segment, tags, preferences, communication_preferences, consent, summary, value_score, metadata FROM customer_360_profiles WHERE id = %s",
                (profile_id,),
            )
            existing = cur.fetchone()

        total_orders = int(order_row[0] or 0)
        total_spend = float(order_row[1] or 0)
        last_order_at = order_row[2]
        conversation_count = int(conversation_row[0] or 0)
        last_conversation_at = conversation_row[1]
        last_channel = channel_row[0] if channel_row else None

        existing_stage = existing[0] if existing else None
        lifecycle_stage = existing_stage or ("customer" if total_orders > 0 else "lead")
        summary = (existing[6] if existing else None) or (
            f"Cliente {customer[0]}. Historial: {total_orders} pedidos, "
            f"{conversation_count} conversaciones y {memory_count} memorias."
        )
        value_score = float(existing[7] if existing and existing[7] is not None else 0)

        # Derived score is conservative: activity exists, but we do not invent monetary value.
        if value_score == 0 and total_spend > 0:
            value_score = round(min(100.0, total_spend / 100.0), 2)

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE customer_360_profiles
                SET lifecycle_stage = %s,
                    summary = %s,
                    value_score = %s,
                    total_orders = %s,
                    total_spend = %s,
                    conversation_count = %s,
                    last_order_at = %s,
                    last_conversation_at = %s,
                    last_appointment_at = %s,
                    last_channel = %s,
                    updated_at = NOW()
                WHERE id = %s AND business_id = %s AND customer_id = %s
                """,
                (
                    lifecycle_stage,
                    summary,
                    value_score,
                    total_orders,
                    total_spend,
                    conversation_count,
                    last_order_at,
                    last_conversation_at,
                    last_appointment,
                    last_channel,
                    profile_id,
                    business_id,
                    customer_id,
                ),
            )
        self.conn.commit()
        return self.get(business_id=business_id, customer_id=customer_id) or {}

    def get(self, *, business_id: UUID, customer_id: UUID) -> dict[str, Any]:
        self._require_customer(business_id, customer_id)
        self._ensure_profile_row(business_id, customer_id)
        profile = self._fetch_profile(business_id, customer_id)
        if profile is None:
            raise Customer360Error("Customer 360 profile could not be loaded")
        return profile

    def update(self, *, business_id: UUID, customer_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        self._require_customer(business_id, customer_id)
        self._ensure_profile_row(business_id, customer_id)
        allowed = {
            "lifecycle_stage", "segment", "tags", "preferences",
            "communication_preferences", "consent", "summary", "value_score", "metadata",
        }
        clean = {k: v for k, v in values.items() if k in allowed and v is not None}
        if "value_score" in clean and not 0 <= float(clean["value_score"]) <= 100:
            raise Customer360Error("value_score must be between 0 and 100")
        if "tags" in clean and not isinstance(clean["tags"], list):
            raise Customer360Error("tags must be a list")

        assignments = []
        params: list[Any] = []
        for field, value in clean.items():
            assignments.append(f"{field} = %s")
            params.append(Jsonb(value) if field in {"tags", "preferences", "communication_preferences", "consent", "metadata"} else value)
        if assignments:
            params.extend([business_id, customer_id])
            with self.conn.cursor() as cur:
                cur.execute(
                    f"UPDATE customer_360_profiles SET {', '.join(assignments)}, updated_at = NOW() WHERE business_id = %s AND customer_id = %s",
                    params,
                )
            self.conn.commit()
        return self.get(business_id=business_id, customer_id=customer_id)

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
            return {str(k): Customer360Service._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [Customer360Service._safe(v) for v in value]
        return value
