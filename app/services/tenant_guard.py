from __future__ import annotations

from uuid import UUID


class TenantIsolationError(Exception):
    """Raised when a resource does not belong to the active business tenant."""


class TenantGuard:
    """Centralized tenant-isolation checks used by Galaxy services."""

    # Only tables that expose a business_id and are safe to reference through
    # the controlled resource_type map are allowed here.
    RESOURCE_TABLES: dict[str, str] = {
        "customer": "customers",
        "conversation": "conversations",
        "message": "conversation_messages",
        "memory": "memory",
        "business_opportunity": "business_opportunities",
        "opportunity": "business_opportunities",
        "autonomous_task": "autonomous_tasks",
        "task": "autonomous_tasks",
        "autonomous_learning_loop": "autonomous_learning_loops",
        "learning_loop": "autonomous_learning_loops",
        "recommendation": "recommendations",
        "agent_delegation": "agent_delegations",
        "autonomous_governance_evaluation": "autonomous_governance_evaluations",
        "product": "products",
        "order": "orders",
        "event": "events",
        "user": "users",
        "appointment": "appointments",
    }

    def __init__(self, conn):
        self.conn = conn

    def require_business(self, business_id: UUID) -> None:
        """Verify that the tenant exists and is active."""
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT status FROM businesses WHERE id = %s",
                (str(business_id),),
            )
            row = cur.fetchone()

        if not row:
            raise TenantIsolationError(f"Tenant no encontrado: {business_id}")
        if str(row[0] or "").strip().lower() != "active":
            raise TenantIsolationError(f"Tenant inactivo o suspendido: {business_id}")

    @classmethod
    def _table_for_resource_type(cls, resource_type: str) -> str:
        normalized = str(resource_type or "").strip().lower()
        # Accept common plural forms used by event/entity callers.
        normalized = normalized.rstrip("s") if normalized not in {"status"} else normalized
        table_name = cls.RESOURCE_TABLES.get(normalized)
        if not table_name:
            # Try the original value as well (e.g. "business_opportunities").
            table_name = cls.RESOURCE_TABLES.get(str(resource_type or "").strip().lower())
        if not table_name:
            raise ValueError(
                f"Tipo de recurso no autorizado para verificación de tenant: {resource_type}"
            )
        return table_name

    def verify_resource_ownership(
        self,
        business_id: UUID,
        table_name: str,
        resource_id: UUID,
    ) -> None:
        """Verify that a specific resource belongs to the requested tenant."""
        allowed_tables = set(self.RESOURCE_TABLES.values())
        if table_name not in allowed_tables:
            raise ValueError(f"Tabla no autorizada para verificación de tenant: {table_name}")

        query = f"SELECT 1 FROM {table_name} WHERE id = %s AND business_id = %s"
        with self.conn.cursor() as cur:
            cur.execute(query, (str(resource_id), str(business_id)))
            if not cur.fetchone():
                raise TenantIsolationError(
                    "Recurso no encontrado o no pertenece a la instancia actual."
                )

    def require_resource(
        self,
        business_id: UUID,
        resource_type: str,
        resource_id: UUID,
    ) -> None:
        """Backward-compatible strict resource ownership check.

        Several Galaxy services call this method directly. Earlier versions of
        TenantGuard only exposed verify_resource_ownership(), which caused the
        Webchat/Brain flow to fail at runtime with:
        'TenantGuard' object has no attribute 'require_resource'.
        """
        if resource_id is None:
            raise TenantIsolationError("El recurso requerido no puede ser nulo.")
        table_name = self._table_for_resource_type(resource_type)
        self.verify_resource_ownership(business_id, table_name, resource_id)

    def require_optional_resource(
        self,
        business_id: UUID,
        resource_type: str,
        resource_id: UUID | None,
    ) -> None:
        """Validate an optional tenant-scoped resource when an ID is supplied."""
        if not resource_id:
            return
        self.require_resource(
            business_id=business_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )
