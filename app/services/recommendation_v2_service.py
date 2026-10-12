from __future__ import annotations

from typing import Any
from uuid import UUID


class RecommendationV2Service:
    """Day 3 Recommendation Engine V2 dashboard/orchestration layer."""

    def __init__(self, conn):
        self.conn = conn

    def dashboard(self, *, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT priority, status, COUNT(*)::int
                FROM recommendations
                WHERE business_id = %s
                GROUP BY priority, status
                ORDER BY priority, status
                """,
                (business_id,),
            )
            counts = [
                {"priority": r[0], "status": r[1], "count": int(r[2])}
                for r in cur.fetchall()
            ]
            cur.execute(
                """
                SELECT id, insight_id, recommendation_type, priority, title,
                       description, rationale, action_type, requires_approval,
                       status, payload, created_at, updated_at
                FROM recommendations
                WHERE business_id = %s AND status = 'pending'
                ORDER BY CASE priority
                    WHEN 'critical' THEN 1
                    WHEN 'high' THEN 2
                    WHEN 'normal' THEN 3
                    WHEN 'low' THEN 4
                    ELSE 5 END,
                    created_at ASC
                LIMIT 20
                """,
                (business_id,),
            )
            rows = cur.fetchall()
        items = [
            self._safe(dict(zip([
                "id", "insight_id", "recommendation_type", "priority", "title",
                "description", "rationale", "action_type", "requires_approval",
                "status", "payload", "created_at", "updated_at",
            ], r))) for r in rows
        ]
        return {"pending_count": len(items), "counts": counts, "pending": items}

    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        if isinstance(value, UUID): return str(value)
        if isinstance(value, (datetime, date, time)): return value.isoformat()
        if isinstance(value, Decimal): return float(value)
        if isinstance(value, dict): return {str(k): RecommendationV2Service._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [RecommendationV2Service._safe(v) for v in value]
        return value
