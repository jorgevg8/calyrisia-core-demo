from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from app.services.tenant_guard import TenantGuard, TenantIsolationError


class AppointmentServiceError(Exception):
    pass


class AppointmentService:
    """Day 3 appointment adapter.

    Reads the existing appointments table and reports the schema actually present.
    Booking is enabled when the standard fields are available. This avoids silently
    assuming a schema that may differ between demo databases.
    """

    STANDARD_FIELDS = (
        "id", "business_id", "customer_id", "service_name", "service",
        "employee_id", "starts_at", "start_at", "scheduled_at", "ends_at",
        "end_at", "status", "notes", "created_at", "updated_at",
    )

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    def table_info(self) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = 'appointments'
                )
                """
            )
            exists = bool(cur.fetchone()[0])
            if not exists:
                return {"exists": False, "columns": []}
            cur.execute(
                """
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'appointments'
                ORDER BY ordinal_position
                """
            )
            columns = [{"name": r[0], "data_type": r[1]} for r in cur.fetchall()]
        return {"exists": True, "columns": columns}

    def list_appointments(self, *, business_id: UUID, limit: int = 50) -> dict[str, Any]:
        info = self.table_info()
        if not info["exists"]:
            raise AppointmentServiceError("La tabla appointments no existe en esta base de datos.")
        columns = [c["name"] for c in info["columns"]]
        selected = [c for c in self.STANDARD_FIELDS if c in columns]
        if "id" not in selected or "business_id" not in selected:
            raise AppointmentServiceError("La tabla appointments no tiene id/business_id compatibles.")

        query = "SELECT " + ", ".join(selected) + " FROM appointments WHERE business_id = %s"
        if "created_at" in columns:
            query += " ORDER BY created_at DESC"
        query += " LIMIT %s"
        with self.conn.cursor() as cur:
            cur.execute(query, (business_id, limit))
            rows = cur.fetchall()
        data = [self._safe(dict(zip(selected, row))) for row in rows]
        return {"success": True, "schema": info, "appointments": data}

    def prepare_booking(
        self,
        *,
        business_id: UUID,
        customer_id: UUID,
        starts_at: datetime,
        ends_at: datetime | None,
        service_name: str,
        notes: str | None = None,
    ) -> dict[str, Any]:
        info = self.table_info()
        if not info["exists"]:
            raise AppointmentServiceError("La tabla appointments no existe.")
        try:
            self.tenant.require_business(business_id)
            self.tenant.require_resource(business_id=business_id, resource_type="customer", resource_id=customer_id)
        except TenantIsolationError as exc:
            raise AppointmentServiceError(str(exc)) from exc
        columns = {c["name"] for c in info["columns"]}
        start_col = next((c for c in ("starts_at", "start_at", "scheduled_at") if c in columns), None)
        if start_col is None:
            raise AppointmentServiceError(
                "No encontré una columna compatible para fecha/hora de inicio en appointments. "
                "El sistema muestra el esquema real en GET /api/v1/appointments/schema."
            )
        if "customer_id" not in columns or "business_id" not in columns:
            raise AppointmentServiceError("appointments no tiene customer_id/business_id compatibles.")

        service_col = "service_name" if "service_name" in columns else "service" if "service" in columns else None
        end_col = "ends_at" if "ends_at" in columns else "end_at" if "end_at" in columns else None
        notes_col = "notes" if "notes" in columns else None
        status_col = "status" if "status" in columns else None
        insert_cols = ["business_id", "customer_id", start_col]
        values: list[Any] = [business_id, customer_id, starts_at]
        if service_col:
            insert_cols.append(service_col); values.append(service_name)
        if end_col and ends_at:
            insert_cols.append(end_col); values.append(ends_at)
        if notes_col:
            insert_cols.append(notes_col); values.append(notes)
        if status_col:
            insert_cols.append(status_col); values.append("pending")

        placeholders = ", ".join(["%s"] * len(values))
        with self.conn.cursor() as cur:
            cur.execute(
                f"INSERT INTO appointments ({', '.join(insert_cols)}) VALUES ({placeholders}) RETURNING *",
                values,
            )
            row = cur.fetchone()
            returned_cols = [d.name for d in cur.description]
        self.conn.commit()
        return {"success": True, "appointment": self._safe(dict(zip(returned_cols, row))), "schema": info}

    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, datetime, time
        from decimal import Decimal
        from uuid import UUID

        if isinstance(value, UUID): return str(value)
        if isinstance(value, (datetime, date, time)): return value.isoformat()
        if isinstance(value, Decimal): return float(value)
        if isinstance(value, dict): return {str(k): AppointmentService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [AppointmentService._safe(v) for v in value]
        return value
