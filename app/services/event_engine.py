from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.services.tenant_guard import TenantGuard, TenantIsolationError


class EventProcessingError(Exception):
    """Raised when Galaxy cannot receive/process an event."""


class EventEngine:
    """Receives, validates, deduplicates and routes Galaxy events.

    Step 19 adds Business Brain routing for business-state events while
    preserving Galaxy Brain as the conversational decision engine.
    """

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    @staticmethod
    def _validate_priority(priority: str) -> str:
        allowed = {"critical", "high", "normal", "low"}
        if priority not in allowed:
            raise EventProcessingError(
                f"Invalid priority '{priority}'. Allowed: {sorted(allowed)}"
            )
        return priority

    @staticmethod
    def _next_component(event_type: str, status: str) -> str | None:
        if status not in {"received", "processing", "evaluated", "action_required", "waiting_approval"}:
            return None

        normalized = event_type.strip().upper()
        if normalized in {"STOCK_LOW", "STOCK_OUT", "INVENTORY_DISCREPANCY"}:
            return "business_brain"

        return "galaxy_brain"

    @staticmethod
    def _normalize_event_id(event_id: str | None) -> str:
        if event_id:
            value = event_id.strip()
            if value:
                return value[:150]
        return f"evt_{uuid4().hex}"

    def receive_and_process(
        self,
        *,
        business_id: UUID,
        event_type: str,
        source: str,
        priority: str,
        entity_type: str | None,
        entity_id: UUID | None,
        payload: dict[str, Any],
        event_id: str | None,
        occurred_at: datetime | None,
    ) -> dict[str, Any]:
        if not event_type.strip():
            raise EventProcessingError("event_type cannot be empty")
        try:
            self.tenant.require_business(business_id)
            if entity_type and entity_id:
                self.tenant.require_resource(
                    business_id=business_id,
                    resource_type=entity_type.lower().rstrip("s"),
                    resource_id=entity_id,
                )
        except (TenantIsolationError, ValueError) as exc:
            raise EventProcessingError(f"Tenant isolation violation: {exc}") from exc
        if not source.strip():
            raise EventProcessingError("source cannot be empty")

        priority = self._validate_priority(priority)
        logical_event_id = self._normalize_event_id(event_id)
        occurred_at = occurred_at or datetime.now(timezone.utc)

        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, status, priority, event_type FROM events "
                "WHERE business_id = %s AND event_id = %s",
                (business_id, logical_event_id),
            )
            existing = cur.fetchone()

        if existing:
            return {
                "success": True,
                "duplicate": True,
                "event_record_id": existing[0],
                "event_id": logical_event_id,
                "event_type": existing[3],
                "priority": existing[2],
                "status": existing[1],
                "next_component": self._next_component(existing[3], existing[1]),
            }

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO events (
                    business_id,
                    event_id,
                    event_type,
                    source,
                    priority,
                    status,
                    entity_type,
                    entity_id,
                    payload,
                    occurred_at,
                    received_at,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, 'received', %s, %s, %s,
                    %s, NOW(), NOW(), NOW()
                )
                RETURNING id
                """,
                (
                    business_id,
                    logical_event_id,
                    event_type.strip(),
                    source.strip(),
                    priority,
                    entity_type,
                    entity_id,
                    Jsonb(payload),
                    occurred_at,
                ),
            )
            event_record_id = cur.fetchone()[0]
        self.conn.commit()

        try:
            self._mark_processing(event_record_id)
            self._mark_evaluated(event_record_id)
            self._write_event_audit(
                business_id=business_id,
                event_record_id=event_record_id,
                event_type=event_type.strip(),
                source=source.strip(),
                priority=priority,
                entity_type=entity_type,
                entity_id=entity_id,
                status="success",
            )
        except Exception as exc:
            self._mark_failed(event_record_id, str(exc))
            self._write_event_audit(
                business_id=business_id,
                event_record_id=event_record_id,
                event_type=event_type.strip(),
                source=source.strip(),
                priority=priority,
                entity_type=entity_type,
                entity_id=entity_id,
                status="failed",
                reason=str(exc),
            )
            raise EventProcessingError(f"Event processing failed: {exc}") from exc

        return {
            "success": True,
            "duplicate": False,
            "event_record_id": event_record_id,
            "event_id": logical_event_id,
            "event_type": event_type.strip(),
            "priority": priority,
            "status": "evaluated",
            "next_component": self._next_component(event_type, "evaluated"),
        }

    def _mark_processing(self, event_record_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events
                SET status = 'processing',
                    processing_started_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (event_record_id,),
            )
        self.conn.commit()

    def _mark_evaluated(self, event_record_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events
                SET status = 'evaluated',
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (event_record_id,),
            )
        self.conn.commit()

    def _mark_failed(self, event_record_id: UUID, error_message: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE events
                SET status = 'failed',
                    error_message = %s,
                    processed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (error_message, event_record_id),
            )
        self.conn.commit()

    def _write_event_audit(
        self,
        *,
        business_id: UUID,
        event_record_id: UUID,
        event_type: str,
        source: str,
        priority: str,
        entity_type: str | None,
        entity_id: UUID | None,
        status: str,
        reason: str | None = None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id,
                    event_id,
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
                    %s, %s, 'system', 'event_received', %s, %s, %s, %s, %s, NOW()
                )
                """,
                (
                    business_id,
                    event_record_id,
                    entity_type or "event",
                    entity_id,
                    status,
                    reason,
                    Jsonb(
                        {
                            "event_type": event_type,
                            "source": source,
                            "priority": priority,
                        }
                    ),
                ),
            )
        self.conn.commit()
