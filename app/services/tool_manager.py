from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID

try:
    from psycopg.types.json import Jsonb
except Exception:  # pragma: no cover
    class Jsonb:  # type: ignore
        def __init__(self, val):
            self.val = val

from app.services.permission_service import PermissionService
from app.services.tenant_guard import TenantGuard, TenantIsolationError
from app.services.tool_registry import get_tool


class ToolExecutionError(Exception):
    pass


def _json_safe(value: Any) -> Any:
    """Convert database/Python values into JSON-serializable values."""
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


class ToolManager:
    """Registry + permission validation + idempotency + execution layer for CALYRISIA tools."""

    def __init__(self, conn: Any = None):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    @staticmethod
    def _require_uuid(inputs: dict[str, Any], key: str) -> UUID:
        value = inputs.get(key)
        if not value:
            raise ToolExecutionError(f"Missing required input: {key}")
        try:
            return UUID(str(value))
        except ValueError as exc:
            raise ToolExecutionError(f"Invalid UUID for {key}") from exc

    def _check_idempotency(
        self,
        *,
        business_id: UUID,
        tool_name: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any] | None:
        """Prevent duplicate execution of the same non-read tool operation when an idempotency_key is provided."""
        idem_key = str(inputs.get("idempotency_key") or "").strip()
        if not idem_key:
            return None
        scoped_key = hashlib.sha256(f"{business_id}:{tool_name}:{idem_key}".encode("utf-8")).hexdigest()[:64]
        try:
            with self.conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_tool_idem")
                cur.execute(
                    """
                    SELECT response_data FROM public.idempotency_keys
                    WHERE business_id = %s AND idempotency_key = %s
                    LIMIT 1
                    """,
                    (business_id, scoped_key),
                )
                row = cur.fetchone()
                cur.execute("RELEASE SAVEPOINT sp_tool_idem")
                if row and row[0]:
                    data = row[0] if isinstance(row[0], dict) else json.loads(str(row[0]))
                    return {**data, "idempotent_replay": True}
        except Exception:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_tool_idem")
            except Exception:
                pass
        return None

    def _store_idempotency(
        self,
        *,
        business_id: UUID,
        tool_name: str,
        inputs: dict[str, Any],
        response_payload: dict[str, Any],
    ) -> None:
        idem_key = str(inputs.get("idempotency_key") or "").strip()
        if not idem_key:
            return
        scoped_key = hashlib.sha256(f"{business_id}:{tool_name}:{idem_key}".encode("utf-8")).hexdigest()[:64]
        try:
            with self.conn.cursor() as cur:
                cur.execute("SAVEPOINT sp_tool_idem_save")
                cur.execute(
                    """
                    INSERT INTO public.idempotency_keys (business_id, idempotency_key, action_name, response_data)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (idempotency_key) DO NOTHING
                    """,
                    (business_id, scoped_key, tool_name, Jsonb(_json_safe(response_payload))),
                )
                cur.execute("RELEASE SAVEPOINT sp_tool_idem_save")
            self.conn.commit()
        except Exception:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_tool_idem_save")
            except Exception:
                pass

    def execute(
        self,
        *,
        business_id: UUID,
        tool_name: str,
        inputs: dict[str, Any],
        requested_by_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        tool = get_tool(tool_name)
        if tool is None:
            raise ToolExecutionError(f"Unknown tool: {tool_name}")

        try:
            self.tenant.require_business(business_id)
            input_business_id = inputs.get("business_id")
            if input_business_id is not None and UUID(str(input_business_id)) != business_id:
                raise TenantIsolationError("Tool input business_id does not match the active tenant")

            resource_map = {
                "get_customer": ("customer", inputs.get("customer_id")),
                "get_product": ("product", inputs.get("product_id")),
                "get_inventory": ("product", inputs.get("product_id")),
                "get_order": ("order", inputs.get("order_id")),
                "create_order": ("customer", inputs.get("customer_id")),
                "prepare_order": ("customer", inputs.get("customer_id")),
                "capture_customer_lead": ("customer", inputs.get("customer_id")),
                "issue_refund": ("order", inputs.get("order_id")),
                "request_human_handoff": ("conversation", inputs.get("conversation_id")),
            }
            for name, (rtype, rid) in resource_map.items():
                if tool_name == name and rid is not None:
                    self.tenant.require_resource(
                        business_id=business_id, resource_type=rtype, resource_id=UUID(str(rid))
                    )
            if tool_name in {"get_product", "get_inventory", "create_order", "prepare_order", "update_inventory"} and inputs.get("product_id") is not None:
                self.tenant.require_resource(
                    business_id=business_id, resource_type="product", resource_id=UUID(str(inputs["product_id"]))
                )
        except (TenantIsolationError, ValueError) as exc:
            raise ToolExecutionError(f"Tenant isolation violation: {exc}") from exc

        # Check idempotency before executing or creating duplicate approvals
        if tool["action_type"] != "read":
            cached_idem = self._check_idempotency(business_id=business_id, tool_name=tool_name, inputs=inputs)
            if cached_idem is not None:
                return cached_idem

        permission_service = PermissionService(self.conn)
        decision = permission_service.evaluate(
            business_id=business_id,
            resource_type=tool["resource_type"],
            action_type=tool["action_type"] if tool["action_type"] != "prepare" else "read",
            requested_by_user_id=requested_by_user_id,
            tool_requires_approval=bool(tool.get("requires_approval")),
        )

        # Level 3 tools ALWAYS require human authorization even if a generic permission row exists
        requires_human_approval = bool(decision.requires_approval or tool.get("autonomy_level") == "L3" or tool.get("requires_approval"))

        action_id = self._record_action_requested(
            business_id=business_id,
            tool=tool,
            inputs=inputs,
            requested_by_user_id=requested_by_user_id,
            permission_id=decision.permission_id,
            initial_status=(
                "rejected"
                if not decision.allowed
                else "waiting_approval"
                if requires_human_approval
                else "validated"
            ),
            reason=decision.reason,
        )

        if not decision.allowed:
            self._write_audit_log(
                business_id=business_id,
                action_id=action_id,
                actor_type="user" if requested_by_user_id else "galaxy",
                actor_user_id=requested_by_user_id,
                action_type=tool["action_type"],
                resource_type=tool["resource_type"],
                resource_id=None,
                status="rejected",
                tool_name=tool_name,
                reason=decision.reason,
                before_data={},
                after_data={},
                metadata={
                    "permission_id": str(decision.permission_id) if decision.permission_id else None,
                    "autonomy_level": tool.get("autonomy_level", "L1"),
                },
            )
            raise ToolExecutionError(decision.reason)

        if requires_human_approval:
            approval_id = self._create_approval(
                business_id=business_id,
                action_id=action_id,
                requested_by_user_id=requested_by_user_id,
                reason=decision.reason or f"Acción Nivel 3 ({tool_name}) requiere autorización humana.",
            )
            self._write_audit_log(
                business_id=business_id,
                action_id=action_id,
                actor_type="user" if requested_by_user_id else "galaxy",
                actor_user_id=requested_by_user_id,
                action_type=tool["action_type"],
                resource_type=tool["resource_type"],
                resource_id=None,
                status="info",
                tool_name=tool_name,
                reason=decision.reason,
                before_data={},
                after_data={},
                metadata={
                    "permission_id": str(decision.permission_id) if decision.permission_id else None,
                    "approval_id": str(approval_id),
                    "autonomy_level": tool.get("autonomy_level", "L3"),
                },
            )
            waiting_payload = {
                "success": True,
                "action_id": action_id,
                "status": "waiting_approval",
                "autonomy_level": tool.get("autonomy_level", "L3"),
                "approval_id": approval_id,
                "permission": {
                    "allowed": True,
                    "requires_approval": True,
                    "permission_id": decision.permission_id,
                    "reason": decision.reason,
                    "limits": decision.limits,
                },
                "tool": tool,
                "result": None,
                "resource_type": tool["resource_type"],
                "resource_id": None,
            }
            self._store_idempotency(business_id=business_id, tool_name=tool_name, inputs=inputs, response_payload=waiting_payload)
            return waiting_payload

        allowed_auto_tools = {
            "get_business_profile",
            "get_customer",
            "get_product",
            "search_catalog",
            "get_inventory",
            "get_order",
            "request_human_handoff",
            "prepare_order",
            "capture_customer_lead",
        }
        if tool_name not in allowed_auto_tools:
            raise ToolExecutionError(
                f"Tool '{tool_name}' is authorized but its execution requires explicit approval workflow."
            )

        self._set_action_validated_to_executing(action_id)

        try:
            if tool_name == "request_human_handoff":
                conversation_id = self._require_uuid(inputs, "conversation_id")
                reason = inputs.get("reason", "El cliente ha solicitado hablar con un humano")
                from app.services.conversation_service import ConversationService

                conv_service = ConversationService(self.conn)
                result = conv_service.handoff(
                    business_id=business_id,
                    conversation_id=conversation_id,
                    reason=reason,
                    actor="galaxy_brain",
                )
                resource_type = "conversation"
                resource_id = conversation_id
            elif tool_name == "prepare_order":
                result, resource_type, resource_id = self._execute_prepare_order(
                    business_id=business_id,
                    inputs=inputs,
                    requested_by_user_id=requested_by_user_id,
                )
            elif tool_name == "capture_customer_lead":
                result, resource_type, resource_id = self._execute_capture_lead(
                    business_id=business_id,
                    inputs=inputs,
                )
            else:
                result, resource_type, resource_id = self._execute_read_tool(
                    business_id=business_id,
                    tool_name=tool_name,
                    inputs=inputs,
                )

            safe_result = _json_safe(result)
            self._complete_action(
                action_id=action_id,
                status="completed",
                output_data=safe_result,
            )
            self._write_audit_log(
                business_id=business_id,
                action_id=action_id,
                actor_type="user" if requested_by_user_id else "galaxy",
                actor_user_id=requested_by_user_id,
                action_type=tool["action_type"],
                resource_type=resource_type,
                resource_id=resource_id,
                status="success",
                tool_name=tool_name,
                reason=decision.reason,
                before_data={},
                after_data=safe_result,
                metadata={
                    "permission_id": str(decision.permission_id) if decision.permission_id else None,
                    "autonomy_level": tool.get("autonomy_level", "L1"),
                },
            )
            completed_payload = {
                "success": True,
                "action_id": action_id,
                "status": "completed",
                "autonomy_level": tool.get("autonomy_level", "L1"),
                "permission": {
                    "allowed": True,
                    "requires_approval": False,
                    "permission_id": decision.permission_id,
                    "reason": decision.reason,
                    "limits": decision.limits,
                },
                "tool": tool,
                "result": safe_result,
                "resource_type": resource_type,
                "resource_id": resource_id,
            }
            if tool["action_type"] != "read":
                self._store_idempotency(business_id=business_id, tool_name=tool_name, inputs=inputs, response_payload=completed_payload)
            return completed_payload
        except Exception as exc:
            self._complete_action(
                action_id=action_id,
                status="failed",
                output_data={},
                error_message=str(exc),
            )
            self._write_audit_log(
                business_id=business_id,
                action_id=action_id,
                actor_type="user" if requested_by_user_id else "galaxy",
                actor_user_id=requested_by_user_id,
                action_type=tool["action_type"],
                resource_type=tool["resource_type"],
                resource_id=None,
                status="failed",
                tool_name=tool_name,
                reason=str(exc),
                before_data={},
                after_data={},
                metadata={
                    "permission_id": str(decision.permission_id) if decision.permission_id else None,
                    "autonomy_level": tool.get("autonomy_level", "L1"),
                },
            )
            if isinstance(exc, ToolExecutionError):
                raise
            raise ToolExecutionError(f"Tool execution failed: {exc}") from exc

    def _record_action_requested(
        self,
        *,
        business_id: UUID,
        tool: dict[str, Any],
        inputs: dict[str, Any],
        requested_by_user_id: UUID | None,
        permission_id: UUID | None,
        initial_status: str,
        reason: str,
    ) -> UUID:
        # Map L1/L2/L3 to DB check constraint values if actions table restricts autonomy_level
        db_autonomy = tool.get("autonomy_level", "L1")
        if db_autonomy not in {"L0", "L1", "L2", "L3", "L4"}:
            db_autonomy = "L1"
        db_action_type = tool["action_type"]
        if db_action_type == "prepare":
            db_action_type = "create"
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO actions (
                    business_id,
                    requested_by_user_id,
                    permission_id,
                    action_type,
                    resource_type,
                    tool_name,
                    autonomy_level,
                    risk_level,
                    status,
                    input_data,
                    reason,
                    requested_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                RETURNING id
                """,
                (
                    business_id,
                    requested_by_user_id,
                    permission_id,
                    db_action_type,
                    tool["resource_type"],
                    tool["name"],
                    db_autonomy,
                    tool["risk_level"],
                    initial_status,
                    Jsonb(inputs),
                    reason,
                ),
            )
            action_id = cur.fetchone()[0]
        self.conn.commit()
        return action_id

    def _set_action_validated_to_executing(self, action_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE actions
                SET status = 'executing',
                    started_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (action_id,),
            )
        self.conn.commit()

    def _create_approval(
        self,
        *,
        business_id: UUID,
        action_id: UUID,
        requested_by_user_id: UUID | None,
        reason: str,
    ) -> UUID:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO approvals (
                    business_id,
                    action_id,
                    requested_by_user_id,
                    status,
                    reason,
                    requested_at
                )
                VALUES (%s, %s, %s, 'pending', %s, NOW())
                RETURNING id
                """,
                (business_id, action_id, requested_by_user_id, reason),
            )
            approval_id = cur.fetchone()[0]
        self.conn.commit()
        return approval_id

    def _write_audit_log(
        self,
        *,
        business_id: UUID,
        action_id: UUID,
        actor_type: str,
        actor_user_id: UUID | None,
        action_type: str,
        resource_type: str | None,
        resource_id: UUID | None,
        status: str,
        tool_name: str,
        reason: str,
        before_data: dict[str, Any],
        after_data: dict[str, Any],
        metadata: dict[str, Any],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id,
                    action_id,
                    actor_type,
                    actor_user_id,
                    action_type,
                    resource_type,
                    resource_id,
                    status,
                    tool_name,
                    reason,
                    before_data,
                    after_data,
                    metadata,
                    created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    business_id,
                    action_id,
                    actor_type,
                    actor_user_id,
                    action_type,
                    resource_type,
                    resource_id,
                    status,
                    tool_name,
                    reason,
                    Jsonb(before_data),
                    Jsonb(after_data),
                    Jsonb(metadata),
                ),
            )
        self.conn.commit()

    def _complete_action(
        self,
        *,
        action_id: UUID,
        status: str,
        output_data: dict[str, Any],
        error_message: str | None = None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE actions
                SET status = %s,
                    output_data = %s,
                    error_message = %s,
                    completed_at = NOW(),
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, Jsonb(output_data), error_message, action_id),
            )
        self.conn.commit()

    def _execute_prepare_order(
        self,
        *,
        business_id: UUID,
        inputs: dict[str, Any],
        requested_by_user_id: UUID | None,
    ) -> tuple[dict[str, Any], str, UUID | None]:
        customer_id = self._require_uuid(inputs, "customer_id")
        items = inputs.get("items") or []
        if not isinstance(items, list) or not items:
            raise ToolExecutionError("prepare_order requires a non-empty items list")
        from app.services.sales_service import SalesService

        prep = SalesService(self.conn).prepare_order(
            business_id=business_id,
            customer_id=customer_id,
            items=items,
            source=str(inputs.get("source") or "webchat"),
            requested_by_user_id=requested_by_user_id,
        )
        return prep, "order", customer_id

    def _execute_capture_lead(
        self,
        *,
        business_id: UUID,
        inputs: dict[str, Any],
    ) -> tuple[dict[str, Any], str, UUID | None]:
        from app.services.growth_radar_service import GrowthRadarService

        synced = GrowthRadarService(self.conn).sync_auto_opportunities(business_id=business_id)
        return synced, "customer", None

    def _execute_read_tool(
        self,
        *,
        business_id: UUID,
        tool_name: str,
        inputs: dict[str, Any],
    ) -> tuple[dict[str, Any], str, UUID | None]:
        if tool_name == "get_business_profile":
            return self._get_business_profile(business_id), "business_profile", None
        if tool_name == "get_customer":
            customer_id = self._require_uuid(inputs, "customer_id")
            return self._get_customer(business_id, customer_id), "customer", customer_id
        if tool_name == "get_product":
            product_id = self._require_uuid(inputs, "product_id")
            return self._get_product(business_id, product_id), "product", product_id
        if tool_name == "search_catalog":
            query = str(inputs.get("query") or "").strip()
            return self._search_catalog(business_id, query), "product", None
        if tool_name == "get_inventory":
            product_id = self._require_uuid(inputs, "product_id")
            return self._get_inventory(business_id, product_id), "inventory", product_id
        if tool_name == "get_order":
            order_id = self._require_uuid(inputs, "order_id")
            return self._get_order(business_id, order_id), "order", order_id
        raise ToolExecutionError(f"Read tool not implemented: {tool_name}")

    def _search_catalog(self, business_id: UUID, query: str = "") -> dict[str, Any]:
        with self.conn.cursor() as cur:
            if query:
                like_q = f"%{query}%"
                cur.execute(
                    """
                    SELECT p.id, p.name, p.sku, p.description, p.category, p.brand,
                           p.price, p.status, p.is_service,
                           COALESCE(SUM(i.quantity), 0) AS stock,
                           COALESCE(to_jsonb(p)->'variants', '[]'::jsonb) AS variants,
                           COALESCE(to_jsonb(p)->'attributes', '{}'::jsonb) AS attributes
                    FROM products p
                    LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                    WHERE p.business_id = %s AND p.status = 'active'
                      AND (p.name ILIKE %s OR COALESCE(p.sku, '') ILIKE %s OR COALESCE(p.category, '') ILIKE %s OR COALESCE(p.brand, '') ILIKE %s)
                    GROUP BY p.id
                    ORDER BY p.name
                    LIMIT 25
                    """,
                    (business_id, like_q, like_q, like_q, like_q),
                )
            else:
                cur.execute(
                    """
                    SELECT p.id, p.name, p.sku, p.description, p.category, p.brand,
                           p.price, p.status, p.is_service,
                           COALESCE(SUM(i.quantity), 0) AS stock,
                           COALESCE(to_jsonb(p)->'variants', '[]'::jsonb) AS variants,
                           COALESCE(to_jsonb(p)->'attributes', '{}'::jsonb) AS attributes
                    FROM products p
                    LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                    WHERE p.business_id = %s AND p.status = 'active'
                    GROUP BY p.id
                    ORDER BY p.name
                    LIMIT 25
                    """,
                    (business_id,),
                )
            rows = cur.fetchall()
        return {
            "query": query,
            "count": len(rows),
            "products": [
                {
                    "id": str(r[0]),
                    "name": r[1],
                    "sku": r[2],
                    "description": r[3],
                    "category": r[4],
                    "brand": r[5],
                    "price": float(r[6]) if r[6] is not None else 0.0,
                    "status": r[7],
                    "is_service": bool(r[8]),
                    "stock": float(r[9] or 0),
                    "variants": r[10] if isinstance(r[10], list) else [],
                    "attributes": r[11] if isinstance(r[11], dict) else {},
                }
                for r in rows
            ],
        }

    def _get_business_profile(self, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, b.name, b.business_type, b.timezone, b.currency,
                       bp.id, bp.industry, bp.short_description, bp.city,
                       bp.state_province, bp.country, bp.operating_hours,
                       bp.policies, bp.processes, bp.objectives,
                       bp.autonomy_config, bp.communication_config,
                       bp.social_links, bp.additional_settings,
                       bp.profile_version, bp.status
                FROM businesses b
                LEFT JOIN business_profiles bp ON bp.business_id = b.id
                    AND bp.status = 'active'
                WHERE b.id = %s
                """,
                (business_id,),
            )
            row = cur.fetchone()
        if not row:
            raise ToolExecutionError("Business not found")
        return {
            "business": {
                "id": row[0],
                "name": row[1],
                "business_type": row[2],
                "timezone": row[3],
                "currency": row[4],
            },
            "business_profile": {
                "id": row[5],
                "industry": row[6],
                "short_description": row[7],
                "city": row[8],
                "state_province": row[9],
                "country": row[10],
                "operating_hours": row[11],
                "policies": row[12],
                "processes": row[13],
                "objectives": row[14],
                "autonomy_config": row[15],
                "communication_config": row[16],
                "social_links": row[17],
                "additional_settings": row[18],
                "profile_version": row[19],
                "status": row[20],
            },
        }

    def _get_customer(self, business_id: UUID, customer_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, phone, status, source,
                       first_contact_at, last_interaction_at, notes
                FROM customers
                WHERE id = %s AND business_id = %s
                """,
                (customer_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise ToolExecutionError("Customer not found for this business")
        return {
            "id": row[0],
            "full_name": row[1],
            "email": row[2],
            "phone": row[3],
            "status": row[4],
            "source": row[5],
            "first_contact_at": row[6],
            "last_interaction_at": row[7],
            "notes": row[8],
        }

    def _get_product(self, business_id: UUID, product_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, sku, description, category, brand,
                       price, cost_price, status, is_service,
                       COALESCE(to_jsonb(products)->'variants', '[]'::jsonb) AS variants,
                       COALESCE(to_jsonb(products)->'attributes', '{}'::jsonb) AS attributes
                FROM products
                WHERE id = %s AND business_id = %s
                """,
                (product_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise ToolExecutionError("Product not found for this business")
        return {
            "id": row[0],
            "name": row[1],
            "sku": row[2],
            "description": row[3],
            "category": row[4],
            "brand": row[5],
            "price": float(row[6]) if row[6] is not None else None,
            "cost_price": float(row[7]) if row[7] is not None else None,
            "status": row[8],
            "is_service": row[9],
            "variants": row[10] if isinstance(row[10], list) else [],
            "attributes": row[11] if isinstance(row[11], dict) else {},
        }

    def _get_inventory(self, business_id: UUID, product_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, product_id, quantity, minimum_quantity,
                       location, last_counted_at, last_count_method
                FROM inventory
                WHERE product_id = %s AND business_id = %s
                """,
                (product_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise ToolExecutionError("Inventory record not found for this business")
        quantity = Decimal(row[2])
        minimum = Decimal(row[3])
        return {
            "id": row[0],
            "product_id": row[1],
            "quantity": float(quantity),
            "minimum_quantity": float(minimum),
            "low_stock": quantity <= minimum,
            "location": row[4],
            "last_counted_at": row[5],
            "last_count_method": row[6],
        }

    def _get_order(self, business_id: UUID, order_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, customer_id, order_number, status,
                       subtotal, discount_amount, tax_amount, total_amount,
                       payment_status, payment_method, source, notes, created_at
                FROM orders
                WHERE id = %s AND business_id = %s
                """,
                (order_id, business_id),
            )
            order = cur.fetchone()
            if not order:
                raise ToolExecutionError("Order not found for this business")
            cur.execute(
                """
                SELECT oi.id, oi.product_id, p.name, oi.quantity,
                       oi.unit_price, oi.discount_amount, oi.tax_amount,
                       oi.line_total
                FROM order_items oi
                JOIN products p ON p.id = oi.product_id
                WHERE oi.order_id = %s AND oi.business_id = %s
                ORDER BY oi.created_at
                """,
                (order_id, business_id),
            )
            items = cur.fetchall()
        return {
            "id": order[0],
            "customer_id": order[1],
            "order_number": order[2],
            "status": order[3],
            "subtotal": float(order[4]),
            "discount_amount": float(order[5]),
            "tax_amount": float(order[6]),
            "total_amount": float(order[7]),
            "payment_status": order[8],
            "payment_method": order[9],
            "source": order[10],
            "notes": order[11],
            "created_at": order[12],
            "items": [
                {
                    "id": row[0],
                    "product_id": row[1],
                    "product_name": row[2],
                    "quantity": float(row[3]),
                    "unit_price": float(row[4]),
                    "discount_amount": float(row[5]),
                    "tax_amount": float(row[6]),
                    "line_total": float(row[7]),
                }
                for row in items
            ],
        }