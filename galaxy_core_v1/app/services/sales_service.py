from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

from app.services.tool_manager import ToolExecutionError, ToolManager


class SalesServiceError(Exception):
    pass


class SalesService:
    """Day 3 Sales & Orders read/prepare layer."""

    def __init__(self, conn):
        self.conn = conn
        self.tools = ToolManager(conn)

    def summary(self, *, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*)::int,
                    COALESCE(SUM(total_amount), 0),
                    COUNT(*) FILTER (WHERE status = 'completed')::int,
                    COUNT(*) FILTER (WHERE status = 'pending')::int,
                    COUNT(*) FILTER (WHERE payment_status = 'paid')::int,
                    COUNT(*) FILTER (WHERE created_at >= CURRENT_DATE)::int,
                    COALESCE(SUM(total_amount) FILTER (WHERE created_at >= CURRENT_DATE), 0)
                FROM orders
                WHERE business_id = %s
                """,
                (business_id,),
            )
            row = cur.fetchone()
        return {
            "orders_total": int(row[0] or 0),
            "gross_sales": float(row[1] or 0),
            "completed_orders": int(row[2] or 0),
            "pending_orders": int(row[3] or 0),
            "paid_orders": int(row[4] or 0),
            "orders_today": int(row[5] or 0),
            "sales_today": float(row[6] or 0),
        }

    def list_orders(self, *, business_id: UUID, status: str | None, limit: int) -> list[dict[str, Any]]:
        query = """
            SELECT id, customer_id, order_number, status, subtotal,
                   discount_amount, tax_amount, total_amount,
                   payment_status, payment_method, source, notes, created_at
            FROM orders
            WHERE business_id = %s
        """
        params: list[Any] = [business_id]
        if status:
            query += " AND status = %s"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT %s"
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()
        return [self._safe(dict(zip([
            "id", "customer_id", "order_number", "status", "subtotal",
            "discount_amount", "tax_amount", "total_amount", "payment_status",
            "payment_method", "source", "notes", "created_at",
        ], row))) for row in rows]

    def prepare_order(
        self,
        *,
        business_id: UUID,
        customer_id: UUID,
        items: list[dict[str, Any]],
        source: str = "webchat",
        requested_by_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        if not items:
            raise SalesServiceError("El pedido debe contener al menos un producto.")

        validated: list[dict[str, Any]] = []
        total = 0.0
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, full_name FROM customers WHERE id = %s AND business_id = %s",
                (customer_id, business_id),
            )
            customer = cur.fetchone()
            if not customer:
                raise SalesServiceError("Customer not found for this business")

            for item in items:
                product_id = UUID(str(item["product_id"]))
                quantity = float(item["quantity"])
                if quantity <= 0:
                    raise SalesServiceError("La cantidad debe ser mayor que cero.")
                cur.execute(
                    """
                    SELECT p.id, p.name, p.price, i.quantity
                    FROM products p
                    LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                    WHERE p.id = %s AND p.business_id = %s
                    """,
                    (product_id, business_id),
                )
                row = cur.fetchone()
                if not row:
                    raise SalesServiceError(f"Producto no encontrado: {product_id}")
                available = float(row[3] or 0)
                unit_price = float(row[2] or 0)
                if quantity > available:
                    raise SalesServiceError(
                        f"Inventario insuficiente para {row[1]}. Disponible: {available}."
                    )
                line_total = unit_price * quantity
                total += line_total
                validated.append({
                    "product_id": str(product_id),
                    "product_name": row[1],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": round(line_total, 2),
                    "available_before": available,
                })

        try:
            result = self.tools.execute(
                business_id=business_id,
                tool_name="create_order",
                inputs={
                    "business_id": str(business_id),
                    "customer_id": str(customer_id),
                    "items": [
                        {"product_id": item["product_id"], "quantity": item["quantity"]}
                        for item in validated
                    ],
                    "source": source,
                },
                requested_by_user_id=requested_by_user_id,
            )
        except ToolExecutionError as exc:
            raise SalesServiceError(str(exc)) from exc

        return {
            "success": True,
            "stage": "order_prepared",
            "customer": {"id": str(customer[0]), "name": customer[1]},
            "items": validated,
            "estimated_total": round(total, 2),
            "tool_execution": self._safe(result),
        }

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
            return {str(k): SalesService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [SalesService._safe(v) for v in value]
        return value
