from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb


class RecommendationEngineError(Exception):
    """Raised when Galaxy cannot persist or retrieve a recommendation."""


class RecommendationEngine:
    """Galaxy Recommendation Engine V1.

    Converts a persisted business insight into a concrete, explainable
    recommendation without executing the operational action itself.

    The engine is intentionally separated from Galaxy Brain:
    - Business Brain detects what is happening.
    - Recommendation Engine proposes what should be considered.
    - Galaxy Brain / Tool Manager executes actions when appropriate.
    """

    VALID_PRIORITIES = {"critical", "high", "normal", "low"}
    VALID_STATUSES = {"pending", "accepted", "rejected", "executed", "dismissed", "expired"}

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _safe(value: Any) -> Any:
        if hasattr(value, "isoformat"):
            return value.isoformat()
        return value

    def ensure_for_insight(self, *, insight: dict[str, Any]) -> dict[str, Any]:
        """Create or reuse one recommendation for a given insight."""
        insight_id = UUID(str(insight["id"]))
        business_id = UUID(str(insight["business_id"]))
        insight_type = str(insight.get("insight_type") or "unknown")
        severity = str(insight.get("severity") or "normal")
        entity_name = str(insight.get("entity_name") or insight.get("title") or "el negocio")

        config = self._recommendation_config(
            insight_type=insight_type,
            severity=severity,
            entity_name=entity_name,
            evidence=insight.get("evidence") or {},
        )

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, insight_id, recommendation_type,
                       priority, title, description, rationale, action_type,
                       requires_approval, status, payload, created_at,
                       updated_at, expires_at, acted_at
                FROM recommendations
                WHERE insight_id = %s
                  AND recommendation_type = %s
                LIMIT 1
                """,
                (insight_id, config["recommendation_type"]),
            )
            row = cur.fetchone()

            if row:
                return self._row_to_dict(row)

            recommendation_id = uuid4()
            cur.execute(
                """
                INSERT INTO recommendations (
                    id,
                    business_id,
                    insight_id,
                    recommendation_type,
                    priority,
                    title,
                    description,
                    rationale,
                    action_type,
                    requires_approval,
                    status,
                    payload,
                    created_at,
                    updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    'pending', %s, NOW(), NOW()
                )
                RETURNING id, business_id, insight_id, recommendation_type,
                          priority, title, description, rationale, action_type,
                          requires_approval, status, payload, created_at,
                          updated_at, expires_at, acted_at
                """,
                (
                    recommendation_id,
                    business_id,
                    insight_id,
                    config["recommendation_type"],
                    config["priority"],
                    config["title"],
                    config["description"],
                    config["rationale"],
                    config["action_type"],
                    config["requires_approval"],
                    Jsonb(config["payload"]),
                ),
            )
            created = cur.fetchone()
        self.conn.commit()
        return self._row_to_dict(created)

    @staticmethod
    def _recommendation_config(
        *,
        insight_type: str,
        severity: str,
        entity_name: str,
        evidence: dict[str, Any],
    ) -> dict[str, Any]:
        if insight_type == "inventory_out_of_stock":
            return {
                "recommendation_type": "restock_review",
                "priority": "critical",
                "title": f"Revisar reposición urgente de {entity_name}",
                "description": (
                    f"El inventario de {entity_name} está agotado. "
                    "Revisar proveedor, disponibilidad y cantidad de reposición antes de realizar una compra."
                ),
                "rationale": "El producto no tiene unidades disponibles y existe un riesgo operativo inmediato.",
                "action_type": "review_supplier_restock",
                "requires_approval": True,
                "payload": {
                    "source": "business_brain.inventory",
                    "evidence": evidence,
                    "execution_status": "recommendation_only",
                },
            }

        if insight_type == "inventory_low":
            return {
                "recommendation_type": "restock_review",
                "priority": "high",
                "title": f"Planificar reposición de {entity_name}",
                "description": (
                    f"El stock de {entity_name} está por debajo del mínimo configurado. "
                    "Revisar reposición antes de que se agote."
                ),
                "rationale": "La cantidad actual está por debajo del mínimo operativo del inventario.",
                "action_type": "review_supplier_restock",
                "requires_approval": True,
                "payload": {
                    "source": "business_brain.inventory",
                    "evidence": evidence,
                    "execution_status": "recommendation_only",
                },
            }

        return {
            "recommendation_type": "business_review",
            "priority": severity if severity in RecommendationEngine.VALID_PRIORITIES else "normal",
            "title": f"Revisar situación de {entity_name}",
            "description": "Revisar el hallazgo detectado por Business Brain antes de actuar.",
            "rationale": "La situación requiere revisión humana antes de una acción operativa.",
            "action_type": "manual_review",
            "requires_approval": True,
            "payload": {
                "source": "business_brain",
                "evidence": evidence,
                "execution_status": "recommendation_only",
            },
        }

    def list_recommendations(
        self,
        *,
        business_id: UUID,
        status: str = "pending",
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        if status not in self.VALID_STATUSES:
            raise RecommendationEngineError(
                f"Invalid recommendation status '{status}'. Allowed: {sorted(self.VALID_STATUSES)}"
            )
        limit = max(1, min(limit, 100))

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, insight_id, recommendation_type,
                       priority, title, description, rationale, action_type,
                       requires_approval, status, payload, created_at,
                       updated_at, expires_at, acted_at
                FROM recommendations
                WHERE business_id = %s
                  AND status = %s
                ORDER BY
                    CASE priority
                        WHEN 'critical' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        ELSE 4
                    END,
                    created_at DESC
                LIMIT %s
                """,
                (business_id, status, limit),
            )
            rows = cur.fetchall()
        return [self._row_to_dict(row) for row in rows]

    def update_status(
        self,
        *,
        business_id: UUID,
        recommendation_id: UUID,
        status: str,
    ) -> dict[str, Any]:
        if status not in self.VALID_STATUSES:
            raise RecommendationEngineError(
                f"Invalid recommendation status '{status}'. Allowed: {sorted(self.VALID_STATUSES)}"
            )

        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE recommendations
                SET status = %s,
                    updated_at = NOW(),
                    acted_at = CASE
                        WHEN %s IN ('accepted', 'rejected', 'executed', 'dismissed')
                        THEN NOW()
                        ELSE acted_at
                    END
                WHERE id = %s
                  AND business_id = %s
                RETURNING id, business_id, insight_id, recommendation_type,
                          priority, title, description, rationale, action_type,
                          requires_approval, status, payload, created_at,
                          updated_at, expires_at, acted_at
                """,
                (status, status, recommendation_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                raise RecommendationEngineError("Recommendation not found for this business")
        self.conn.commit()
        return self._row_to_dict(row)

    @staticmethod
    def _row_to_dict(row: tuple[Any, ...]) -> dict[str, Any]:
        return {
            "id": str(row[0]),
            "business_id": str(row[1]),
            "insight_id": str(row[2]),
            "recommendation_type": row[3],
            "priority": row[4],
            "title": row[5],
            "description": row[6],
            "rationale": row[7],
            "action_type": row[8],
            "requires_approval": bool(row[9]),
            "status": row[10],
            "payload": row[11] or {},
            "created_at": RecommendationEngine._safe(row[12]),
            "updated_at": RecommendationEngine._safe(row[13]),
            "expires_at": RecommendationEngine._safe(row[14]),
            "acted_at": RecommendationEngine._safe(row[15]),
        }
