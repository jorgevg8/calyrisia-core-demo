from __future__ import annotations

from typing import Any
from uuid import UUID


class AnalyticsService:
    """Day 3 basic business analytics using PostgreSQL as source of truth."""

    def __init__(self, conn):
        self.conn = conn

    def overview(self, *, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int FROM customers WHERE business_id = %s", (business_id,))
            customers = int(cur.fetchone()[0])
            cur.execute("SELECT COUNT(*)::int FROM products WHERE business_id = %s AND status = 'active'", (business_id,))
            products = int(cur.fetchone()[0])
            cur.execute(
                """
                SELECT COUNT(*)::int,
                       COALESCE(SUM(total_amount),0),
                       COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)::int,
                       COALESCE(SUM(total_amount) FILTER (WHERE created_at >= CURRENT_DATE),0)
                FROM orders WHERE business_id = %s
                """,
                (business_id,),
            )
            orders_total, sales_total, orders_today, sales_today = cur.fetchone()
            cur.execute(
                """
                SELECT COUNT(*)::int,
                       COUNT(*) FILTER (WHERE quantity <= minimum_quantity)::int,
                       COUNT(*) FILTER (WHERE quantity <= 0)::int
                FROM inventory WHERE business_id = %s
                """,
                (business_id,),
            )
            inventory_total, low_stock, out_of_stock = cur.fetchone()
        return {
            "customers": customers,
            "active_products": products,
            "orders": {
                "total": int(orders_total or 0),
                "sales_total": float(sales_total or 0),
                "today": int(orders_today or 0),
                "sales_today": float(sales_today or 0),
            },
            "inventory": {
                "records": int(inventory_total or 0),
                "low_stock": int(low_stock or 0),
                "out_of_stock": int(out_of_stock or 0),
            },
        }

    def top_products(self, *, business_id: UUID, limit: int = 10) -> list[dict[str, Any]]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT p.id, p.name, p.sku,
                       COALESCE(SUM(oi.quantity),0) AS units,
                       COALESCE(SUM(oi.line_total),0) AS revenue
                FROM products p
                LEFT JOIN order_items oi ON oi.product_id = p.id AND oi.business_id = p.business_id
                LEFT JOIN orders o ON o.id = oi.order_id AND o.business_id = p.business_id
                WHERE p.business_id = %s
                GROUP BY p.id, p.name, p.sku
                ORDER BY units DESC, revenue DESC, p.name ASC
                LIMIT %s
                """,
                (business_id, limit),
            )
            rows = cur.fetchall()
        return [
            self._safe({"product_id": r[0], "product_name": r[1], "sku": r[2], "units": r[3], "revenue": r[4]})
            for r in rows
        ]

    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID
        if isinstance(value, UUID): return str(value)
        if isinstance(value, (datetime, date, time)): return value.isoformat()
        if isinstance(value, Decimal): return float(value)
        if isinstance(value, dict): return {str(k): AnalyticsService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [AnalyticsService._safe(v) for v in value]
        return value
