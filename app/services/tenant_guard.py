from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Header, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.core.security import decode_access_token
from app.db import get_connection


class TenantIsolationError(Exception):
    """Raised when a resource does not belong to the active business tenant."""


class MultitenantContext(BaseModel):
    """Contexto inyectado por el Multitenant Guard de FastAPI para garantizar aislamiento total."""

    tenant_id: UUID = Field(..., description="UUID verificado del tenant (business_id)")
    business_id: UUID = Field(..., description="Alias de compatibilidad para tenant_id")
    user_id: UUID | None = None
    role: str = "OWNER"
    business_name: str = ""
    plan_code: str = "free"


class TenantGuard:
    """Centralized tenant-isolation checks used by Galaxy / CALYRISIA services."""

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
        "knowledge_item": "business_knowledge_items",
        "business_knowledge_item": "business_knowledge_items",
        "omnichannel_message": "omnichannel_messages",
    }

    def __init__(self, conn: Any):
        self.conn = conn

    def require_business(self, business_id: UUID | str) -> dict[str, Any]:
        """Verify that the tenant exists and is active, returning basic tenant metadata."""
        bid_str = str(business_id).strip()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, COALESCE(name, 'Negocio CALYRISIA'), COALESCE(status, 'active'),
                       COALESCE(to_jsonb(businesses)->>'plan_code', 'free')
                FROM businesses
                WHERE id = %s
                """,
                (bid_str,),
            )
            row = cur.fetchone()

        if not row:
            raise TenantIsolationError(f"Tenant no encontrado: {business_id}")
        if str(row[2] or "").strip().lower() != "active":
            raise TenantIsolationError(f"Tenant inactivo o suspendido: {business_id}")
        return {
            "id": str(row[0]),
            "name": str(row[1] or "Negocio CALYRISIA"),
            "status": str(row[2] or "active"),
            "plan_code": str(row[3] or "free"),
        }

    @classmethod
    def _table_for_resource_type(cls, resource_type: str) -> str:
        normalized = str(resource_type or "").strip().lower()
        normalized = normalized.rstrip("s") if normalized not in {"status"} else normalized
        table_name = cls.RESOURCE_TABLES.get(normalized)
        if not table_name:
            table_name = cls.RESOURCE_TABLES.get(str(resource_type or "").strip().lower())
        if not table_name:
            raise ValueError(
                f"Tipo de recurso no autorizado para verificación de tenant: {resource_type}"
            )
        return table_name

    def verify_resource_ownership(
        self,
        business_id: UUID | str,
        table_name: str,
        resource_id: UUID | str,
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
        business_id: UUID | str,
        resource_type: str,
        resource_id: UUID | str,
    ) -> None:
        """Backward-compatible strict resource ownership check."""
        if resource_id is None:
            raise TenantIsolationError("El recurso requerido no puede ser nulo.")
        table_name = self._table_for_resource_type(resource_type)
        self.verify_resource_ownership(business_id, table_name, resource_id)

    def require_optional_resource(
        self,
        business_id: UUID | str,
        resource_type: str,
        resource_id: UUID | str | None,
    ) -> None:
        """Validate an optional tenant-scoped resource when an ID is supplied."""
        if not resource_id:
            return
        self.require_resource(
            business_id=business_id,
            resource_type=resource_type,
            resource_id=resource_id,
        )


def _parse_uuid_or_none(raw: Any) -> UUID | None:
    if not raw:
        return None
    try:
        return UUID(str(raw).strip())
    except (ValueError, TypeError, AttributeError):
        return None


async def get_multitenant_guard(
    request: Request,
    x_tenant_id: str | None = Header(default=None, alias="X-Tenant-Id"),
    x_business_id: str | None = Header(default=None, alias="X-Business-Id"),
) -> MultitenantContext:
    """Dependencia asíncrona de FastAPI (Multitenant Guard).

    Garantiza el aislamiento estricto de datos por `tenant_id`:
    1. Si existe cabecera `Authorization: Bearer <token>`, valida el JWT, verifica el usuario y negocio
       en base de datos y comprueba que cualquier `X-Tenant-Id` / `tenant_id` coincida exactamente.
    2. Si se invoca mediante `X-Tenant-Id` / `X-Business-Id` o query/body `tenant_id`, verifica que sea un
       UUID válido perteneciente a un negocio activo en `businesses`.
    """
    auth_header = (request.headers.get("Authorization") or "").strip()
    explicit_header_raw = (x_tenant_id or x_business_id or request.query_params.get("tenant_id") or "").strip()
    explicit_uuid = _parse_uuid_or_none(explicit_header_raw) if explicit_header_raw else None
    if explicit_header_raw and explicit_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El identificador tenant_id proporcionado no tiene un formato UUID válido.",
        )

    # 1. Validación vía JWT Bearer
    if auth_header.lower().startswith("bearer "):
        token = auth_header[7:].strip()
        try:
            payload = decode_access_token(token)
            user_id_raw = payload.get("sub")
            token_bid_raw = payload.get("business_id")
            token_role = str(payload.get("role") or "OWNER").upper()
            if not user_id_raw:
                raise ValueError("Missing sub")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token de autenticación inválido o expirado.",
                headers={"WWW-Authenticate": "Bearer"},
            ) from exc

        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, business_id, role, status
                    FROM users
                    WHERE id = %s AND status = 'active'
                    """,
                    (str(user_id_raw),),
                )
                u_row = cur.fetchone()
                if not u_row:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Usuario no encontrado o inactivo.",
                    )
                resolved_bid = _parse_uuid_or_none(u_row[1] or token_bid_raw)
                if not resolved_bid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="El usuario no tiene un tenant_id (business_id) asignado.",
                    )
                if explicit_uuid and explicit_uuid != resolved_bid:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Aislamiento Multitenant: No tienes permiso para acceder a otro tenant_id.",
                    )
                try:
                    biz_meta = TenantGuard(conn).require_business(resolved_bid)
                except TenantIsolationError as exc:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc

                return MultitenantContext(
                    tenant_id=resolved_bid,
                    business_id=resolved_bid,
                    user_id=_parse_uuid_or_none(u_row[0]),
                    role=str(u_row[2] or token_role).upper(),
                    business_name=biz_meta["name"],
                    plan_code=biz_meta["plan_code"],
                )

    # 2. Validación por cabecera X-Tenant-Id / query param / body JSON
    candidate_uuid = explicit_uuid
    if candidate_uuid is None and request.method in {"POST", "PUT", "PATCH"}:
        try:
            body_json = await request.json()
            if isinstance(body_json, dict):
                raw_body_tid = body_json.get("tenant_id") or body_json.get("business_id")
                if raw_body_tid:
                    candidate_uuid = _parse_uuid_or_none(raw_body_tid)
                    if candidate_uuid is None:
                        raise HTTPException(
                            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            detail="El campo tenant_id del cuerpo JSON no es un UUID válido.",
                        )
        except HTTPException:
            raise
        except Exception:
            pass

    if candidate_uuid is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación requerida: envía Authorization Bearer o un tenant_id válido.",
        )

    async with get_connection() as conn:
        try:
            biz_meta = TenantGuard(conn).require_business(candidate_uuid)
        except TenantIsolationError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

        return MultitenantContext(
            tenant_id=candidate_uuid,
            business_id=candidate_uuid,
            user_id=None,
            role="OWNER",
            business_name=biz_meta["name"],
            plan_code=biz_meta["plan_code"],
        )
