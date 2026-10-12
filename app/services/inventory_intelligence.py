from __future__ import annotations

from typing import Any
from uuid import UUID


class InventoryIntelligenceError(Exception):
    pass


class InventoryIntelligenceService:
    """Day 3 inventory intelligence built on the existing operational data."""

    def __init__(self, conn):
        self.conn = conn

    def overview(self, *, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*)::int,
                       COUNT(*) FILTER (WHERE quantity <= minimum_quantity)::int,
                       COUNT(*) FILTER (WHERE quantity <= 0)::int,
                       COALESCE(SUM(quantity), 0),
                       COALESCE(SUM(minimum_quantity), 0)
                FROM inventory
                WHERE business_id = %s
                """,
                (business_id,),
            )
            row = cur.fetchone()
            cur.execute(
                """
                SELECT i.id, i.product_id, p.name, p.sku,
                       i.quantity, i.minimum_quantity, i.location
                FROM inventory i
                JOIN products p ON p.id = i.product_id AND p.business_id = i.business_id
                WHERE i.business_id = %s
                  AND i.quantity <= i.minimum_quantity
                ORDER BY (i.quantity - i.minimum_quantity) ASC, p.name ASC
                LIMIT 50
                """,
                (business_id,),
            )
            alerts = cur.fetchall()
        return {
            "products_with_inventory": int(row[0] or 0),
            "low_stock_items": int(row[1] or 0),
            "out_of_stock_items": int(row[2] or 0),
            "units_current": float(row[3] or 0),
            "units_minimum": float(row[4] or 0),
            "alerts": [
                self._safe({
                    "inventory_id": r[0], "product_id": r[1], "product_name": r[2],
                    "sku": r[3], "quantity": r[4], "minimum_quantity": r[5], "location": r[6],
                }) for r in alerts
            ],
        }

    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        if isinstance(value, UUID): return str(value)
        if isinstance(value, (datetime, date, time)): return value.isoformat()
        if isinstance(value, Decimal): return float(value)
        if isinstance(value, dict): return {str(k): InventoryIntelligenceService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [InventoryIntelligenceService._safe(v) for v in value]
        return value
