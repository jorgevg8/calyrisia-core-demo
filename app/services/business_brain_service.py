from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.services.recommendation_engine import RecommendationEngine


class BusinessBrainError(Exception):
    """Raised when Business Brain cannot analyze a business."""


class BusinessBrainService:
    """Galaxy Business Brain V1.

    Business Brain observes the operational state of a business and turns
    factual deviations into persisted insights. It does not execute actions.

    V1 scope:
    - inventory_low
    - inventory_out_of_stock

    RecommendationEngine then turns those insights into actionable,
    human-reviewable recommendations.
    """

    INVENTORY_LOW = "inventory_low"
    INVENTORY_OUT = "inventory_out_of_stock"

    def __init__(self, conn):
        self.conn = conn
        self.recommendation_engine = RecommendationEngine(conn)

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
