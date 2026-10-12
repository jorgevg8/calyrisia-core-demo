from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb

from app.services.tenant_guard import TenantGuard, TenantIsolationError


class WorkflowError(Exception):
    pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    return value


class WorkflowEngine:
    """Deterministic workflow execution layer for Galaxy.

    Step 45 keeps workflows declarative and tenant-scoped. A workflow is
    triggered by an existing event record, evaluates conditions, executes
    safe workflow actions, records every step and supports idempotent runs.
    High-impact actions are represented through the existing actions/approvals
    infrastructure and leave the run in waiting_approval until Step 46.
    """

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    @staticmethod
    def validate_definition(definition: dict[str, Any]) -> None:
        steps = definition.get("steps")
        if not isinstance(steps, list) or not steps:
            raise WorkflowError("definition.steps must be a non-empty list")
        seen: set[str] = set()
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict):
                raise WorkflowError(f"step {index} must be an object")
            key = str(step.get("key", "")).strip()
            step_type = str(step.get("type", "")).strip().lower()
            if not key:
                raise WorkflowError(f"step {index} is missing key")
            if key in seen:
                raise WorkflowError(f"duplicate step key: {key}")
            seen.add(key)
            if step_type not in {"condition", "action"}:
                raise WorkflowError(f"step '{key}' has invalid type '{step_type}'")
            if step_type == "condition":
                if not str(step.get("field", "")).strip():
                    raise WorkflowError(f"condition '{key}' needs field")
                if str(step.get("operator", "eq")).strip() not in {
                    "eq", "neq", "gt", "gte", "lt", "lte", "in", "contains", "exists"
                }:
                    raise WorkflowError(f"condition '{key}' has unsupported operator")
            if step_type == "action":
                action = str(step.get("action", "")).strip().lower()
                if action not in {"audit", "request_approval"}:
                    raise WorkflowError(
                        f"action '{key}' unsupported in Step 45: {action}. "
                        "Tool execution remains behind the existing ToolManager/Approval layer."
                    )

    @staticmethod
    def _resolve_path(payload: dict[str, Any], path: str) -> Any:
        current: Any = payload
        for part in path.split("."):
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                return None
        return current

    @classmethod
    def _evaluate_condition(cls, runtime: dict[str, Any], step: dict[str, Any]) -> bool:
        field = str(step.get("field", "")).strip()
        operator = str(step.get("operator", "eq")).strip().lower()
        value = cls._resolve_path(runtime, field)
        expected = step.get("value")
        if operator == "exists":
            return value is not None if expected in (None, True) else value is None
        if operator == "eq":
            return value == expected
        if operator == "neq":
            return value != expected
        if operator == "gt":
            return value is not None and value > expected
        if operator == "gte":
            return value is not None and value >= expected
        if operator == "lt":
            return value is not None and value < expected
        if operator == "lte":
            return value is not None and value <= expected
        if operator == "in":
            return value in expected if isinstance(expected, (list, tuple, set)) else False
        if operator == "contains":
            try:
                return expected in value
            except TypeError:
                return False
        raise WorkflowError(f"Unsupported condition operator: {operator}")

    def create_workflow(
        self,
        *,
        business_id: UUID,
        name: str,
        trigger_event_type: str,
        definition: dict[str, Any],
        created_by_user_id: UUID | None,
        enabled: bool,
    ) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        if created_by_user_id:
            self._require_user(business_id, created_by_user_id)
        name = name.strip()
        trigger_event_type = trigger_event_type.strip()
        if not name or not trigger_event_type:
            raise WorkflowError("name and trigger_event_type are required")
        self.validate_definition(definition)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_definitions (
                    business_id, name, trigger_event_type, enabled, definition,
                    created_by_user_id, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING id, business_id, name, trigger_event_type, enabled,
                          definition, created_by_user_id, created_at, updated_at
                """,
                (business_id, name, trigger_event_type, bool(enabled), Jsonb(definition), created_by_user_id),
            )
            row = cur.fetchone()
        self.conn.commit()
        return self._workflow_row(row)

    def list_workflows(self, business_id: UUID) -> list[dict[str, Any]]:
        self.tenant.require_business(business_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, name, trigger_event_type, enabled,
                       definition, created_by_user_id, created_at, updated_at
                FROM workflow_definitions
                WHERE business_id = %s
                ORDER BY created_at DESC
                """,
                (business_id,),
            )
            return [self._workflow_row(row) for row in cur.fetchall()]

    def get_workflow(self, business_id: UUID, workflow_id: UUID) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, name, trigger_event_type, enabled,
                       definition, created_by_user_id, created_at, updated_at
                FROM workflow_definitions
                WHERE id = %s AND business_id = %s
                """,
                (workflow_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise WorkflowError("Workflow not found for this business")
        return self._workflow_row(row)

    def trigger_workflow(
        self,
        *,
        business_id: UUID,
        workflow_id: UUID,
        event_record_id: UUID,
        requested_by_user_id: UUID | None,
    ) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        if requested_by_user_id:
            self._require_user(business_id, requested_by_user_id)

        workflow = self.get_workflow(business_id, workflow_id)
        if not workflow["enabled"]:
            raise WorkflowError("Workflow is disabled")

        event = self._get_event(business_id, event_record_id)
        if event["event_type"] != workflow["trigger_event_type"]:
            raise WorkflowError(
                f"Event type '{event['event_type']}' does not match workflow trigger "
                f"'{workflow['trigger_event_type']}'"
            )

        idempotency_key = f"{workflow_id}:{event_record_id}"
        existing = self._find_run(business_id, workflow_id, idempotency_key)
        if existing:
            return {"success": True, "duplicate": True, **existing}

        run_id = self._create_run(
            business_id=business_id,
            workflow_id=workflow_id,
            event_record_id=event_record_id,
            idempotency_key=idempotency_key,
            payload=event["payload"],
        )

        runtime = {
            "payload": event["payload"],
            "event": event,
            "workflow": workflow,
            "steps": {},
        }

        try:
            final_status = "completed"
            final_output: dict[str, Any] = {"steps": []}
            for order, step in enumerate(workflow["definition"]["steps"], start=1):
                key = step["key"]
                step_type = step["type"].strip().lower()
                if not self._step_guard_passes(runtime, step):
                    step_result = {"skipped": True, "reason": "run_if condition did not pass"}
                    self._record_step(
                        run_id, order, key, step_type, "skipped", {}, step_result, None
                    )
                    runtime["steps"][key] = step_result
                    final_output["steps"].append({"key": key, **step_result})
                    continue

                self._record_step(run_id, order, key, step_type, "running", {}, {}, None)
                if step_type == "condition":
                    result = self._evaluate_condition(runtime, step)
                    step_output = {
                        "result": bool(result),
                        "field": step["field"],
                        "operator": step.get("operator", "eq"),
                        "expected": step.get("value"),
                    }
                    self._complete_step(run_id, key, "completed", step_output)
                    runtime["steps"][key] = step_output
                    final_output["steps"].append({"key": key, **step_output})
                    continue

                action = str(step.get("action", "")).strip().lower()
                result = self._execute_action(
                    business_id=business_id,
                    run_id=run_id,
                    event=event,
                    workflow=workflow,
                    step=step,
                    requested_by_user_id=requested_by_user_id,
                )
                if result.get("status") == "waiting_approval":
                    self._complete_step(run_id, key, "waiting_approval", result)
                    runtime["steps"][key] = result
                    final_output["steps"].append({"key": key, **result})
                    final_status = "waiting_approval"
                    break

                self._complete_step(run_id, key, "completed", result)
                runtime["steps"][key] = result
                final_output["steps"].append({"key": key, **result})

            self._finish_run(run_id, final_status, final_output, None)
            return {"success": True, "duplicate": False, "run_id": run_id, "status": final_status, "output": final_output}
        except Exception as exc:
            # La excepción puede haber dejado la conexión en estado abortado.
            # Rollback primero para poder persistir el fallo real del run.
            try:
                self.conn.rollback()
            except Exception:
                pass
            try:
                self._finish_run(run_id, "failed", {}, str(exc))
            except Exception:
                pass
            raise WorkflowError(f"Workflow execution failed: {exc}") from exc

    def resume_after_approval(
        self,
        *,
        business_id: UUID,
        run_id: UUID,
        approval_id: UUID,
        approved_by_user_id: UUID,
    ) -> dict[str, Any]:
        """Resume a workflow after a human approval has been granted."""
        self.tenant.require_business(business_id)
        self._require_user(business_id, approved_by_user_id)
        run = self.get_run(business_id, run_id)
        if run["status"] != "waiting_approval":
            raise WorkflowError(f"Workflow run is not waiting for approval: {run['status']}")

        workflow = self.get_workflow(business_id, UUID(str(run["workflow_id"])))
        event = self._get_event(business_id, UUID(str(run["event_record_id"])))
        stored_steps = run["steps"]
        approval_step = None
        for step_row in stored_steps:
            output = step_row.get("output_data") or {}
            if str(output.get("approval_id")) == str(approval_id):
                approval_step = step_row
                break

        if approval_step is None:
            raise WorkflowError("Approval is not linked to a waiting workflow step")

        runtime = {
            "payload": event["payload"],
            "event": event,
            "workflow": workflow,
            "steps": {row["step_key"]: (row.get("output_data") or {}) for row in stored_steps},
        }

        approved_step_result = {
            "status": "completed",
            "action": "request_approval",
            "approval_id": str(approval_id),
            "approved_by_user_id": str(approved_by_user_id),
        }
        self._complete_step(
            run_id,
            approval_step["step_key"],
            "completed",
            approved_step_result,
        )
        runtime["steps"][approval_step["step_key"]] = approved_step_result

        final_output: dict[str, Any] = {"steps": []}
        for row in stored_steps:
            if row["step_key"] == approval_step["step_key"]:
                final_output["steps"].append({"key": row["step_key"], **approved_step_result})
            else:
                final_output["steps"].append({"key": row["step_key"], **(row.get("output_data") or {})})

        current_order = int(approval_step["step_order"])
        final_status = "completed"
        try:
            for order, step in enumerate(workflow["definition"]["steps"], start=1):
                if order <= current_order:
                    continue
                key = step["key"]
                step_type = step["type"].strip().lower()
                if not self._step_guard_passes(runtime, step):
                    step_result = {"skipped": True, "reason": "run_if condition did not pass"}
                    self._record_step(run_id, order, key, step_type, "skipped", {}, step_result, None)
                    runtime["steps"][key] = step_result
                    final_output["steps"].append({"key": key, **step_result})
                    continue

                self._record_step(run_id, order, key, step_type, "running", {}, {}, None)
                if step_type == "condition":
                    result = self._evaluate_condition(runtime, step)
                    step_output = {
                        "result": bool(result),
                        "field": step["field"],
                        "operator": step.get("operator", "eq"),
                        "expected": step.get("value"),
                    }
                    self._complete_step(run_id, key, "completed", step_output)
                    runtime["steps"][key] = step_output
                    final_output["steps"].append({"key": key, **step_output})
                    continue

                result = self._execute_action(
                    business_id=business_id,
                    run_id=run_id,
                    event=event,
                    workflow=workflow,
                    step=step,
                    requested_by_user_id=approved_by_user_id,
                )
                if result.get("status") == "waiting_approval":
                    self._complete_step(run_id, key, "waiting_approval", result)
                    runtime["steps"][key] = result
                    final_output["steps"].append({"key": key, **result})
                    final_status = "waiting_approval"
                    break

                self._complete_step(run_id, key, "completed", result)
                runtime["steps"][key] = result
                final_output["steps"].append({"key": key, **result})

            self._finish_run(run_id, final_status, final_output, None)
            return {
                "success": True,
                "run_id": run_id,
                "status": final_status,
                "output": final_output,
            }
        except Exception as exc:
            self._finish_run(run_id, "failed", final_output, str(exc))
            raise WorkflowError(f"Workflow resume failed: {exc}") from exc

    def get_run(self, business_id: UUID, run_id: UUID) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, workflow_id, event_record_id,
                       idempotency_key, status, input_payload, output_payload,
                       error_message, started_at, completed_at, created_at, updated_at
                FROM workflow_runs
                WHERE id = %s AND business_id = %s
                """,
                (run_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                raise WorkflowError("Workflow run not found for this business")
            cur.execute(
                """
                SELECT step_order, step_key, step_type, status, input_data,
                       output_data, error_message, started_at, completed_at
                FROM workflow_steps
                WHERE run_id = %s
                ORDER BY step_order ASC
                """,
                (run_id,),
            )
            steps = [
                {
                    "step_order": r[0],
                    "step_key": r[1],
                    "step_type": r[2],
                    "status": r[3],
                    "input_data": r[4] or {},
                    "output_data": r[5] or {},
                    "error_message": r[6],
                    "started_at": r[7].isoformat() if r[7] else None,
                    "completed_at": r[8].isoformat() if r[8] else None,
                }
                for r in cur.fetchall()
            ]
        return {
            "id": row[0],
            "business_id": row[1],
            "workflow_id": row[2],
            "event_record_id": row[3],
            "idempotency_key": row[4],
            "status": row[5],
            "input_payload": row[6] or {},
            "output_payload": row[7] or {},
            "error_message": row[8],
            "started_at": row[9].isoformat() if row[9] else None,
            "completed_at": row[10].isoformat() if row[10] else None,
            "created_at": row[11].isoformat() if row[11] else None,
            "updated_at": row[12].isoformat() if row[12] else None,
            "steps": steps,
        }

    def _step_guard_passes(self, runtime: dict[str, Any], step: dict[str, Any]) -> bool:
        if not step.get("run_if"):
            return True
        ref = str(step["run_if"])
        previous = runtime["steps"].get(ref)
        if not isinstance(previous, dict):
            return False
        if previous.get("skipped"):
            return False
        if "result" in previous:
            return bool(previous["result"])
        return previous.get("status") not in {"failed", "skipped"}

    def _execute_action(
        self,
        *,
        business_id: UUID,
        run_id: UUID,
        event: dict[str, Any],
        workflow: dict[str, Any],
        step: dict[str, Any],
        requested_by_user_id: UUID | None,
    ) -> dict[str, Any]:
        action = str(step.get("action", "")).strip().lower()
        reason = str(step.get("reason") or f"Workflow '{workflow['name']}' requested this action.")
        if action == "audit":
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        business_id, event_id, actor_type, actor_user_id,
                        action_type, resource_type, resource_id, status,
                        reason, metadata, created_at
                    )
                    VALUES (%s, %s, 'galaxy', %s, 'workflow_action',
                            'workflow', %s, 'success', %s, %s, NOW())
                    RETURNING id
                    """,
                    (
                        business_id,
                        event["id"],
                        requested_by_user_id,
                        run_id,
                        reason,
                        Jsonb({"workflow_id": str(workflow["id"]), "step_key": step["key"]}),
                    ),
                )
                audit_id = cur.fetchone()[0]
            self.conn.commit()
            return {"status": "completed", "action": "audit", "audit_id": audit_id, "reason": reason}

        if action == "request_approval":
            action_id = self._create_workflow_action(
                business_id=business_id,
                run_id=run_id,
                event=event,
                workflow=workflow,
                step=step,
                requested_by_user_id=requested_by_user_id,
                reason=reason,
            )
            approval_id = self._create_approval(
                business_id=business_id,
                action_id=action_id,
                requested_by_user_id=requested_by_user_id,
                reason=reason,
            )
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        business_id, event_id, action_id, actor_type, actor_user_id,
                        action_type, resource_type, resource_id, status,
                        reason, metadata, created_at
                    )
                    VALUES (%s, %s, %s, 'galaxy', %s, 'workflow_approval_requested',
                            'workflow', %s, 'success', %s, %s, NOW())
                    """,
                    (
                        business_id,
                        event["id"],
                        action_id,
                        requested_by_user_id,
                        run_id,
                        reason,
                        Jsonb({
                            "workflow_id": str(workflow["id"]),
                            "step_key": step["key"],
                            "approval_id": str(approval_id),
                        }),
                    ),
                )
            self.conn.commit()
            return {
                "status": "waiting_approval",
                "action": "request_approval",
                "action_id": action_id,
                "approval_id": approval_id,
                "reason": reason,
            }

        raise WorkflowError(f"Unsupported workflow action: {action}")

    def _create_workflow_action(
        self,
        *,
        business_id: UUID,
        run_id: UUID,
        event: dict[str, Any],
        workflow: dict[str, Any],
        step: dict[str, Any],
        requested_by_user_id: UUID | None,
        reason: str,
    ) -> UUID:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO actions (
                    business_id, requested_by_user_id, permission_id,
                    action_type, resource_type, tool_name,
                    autonomy_level, risk_level, status,
                    input_data, reason, requested_at
                )
                VALUES (%s, %s, NULL, 'update', 'workflow', NULL,
                        'L2', 'high', 'waiting_approval', %s, %s, NOW())
                RETURNING id
                """,
                (
                    business_id,
                    requested_by_user_id,
                    Jsonb({
                        "workflow_id": str(workflow["id"]),
                        "run_id": str(run_id),
                        "event_record_id": str(event["id"]),
                        "step": deepcopy(step),
                    }),
                    reason,
                ),
            )
            action_id = cur.fetchone()[0]
        self.conn.commit()
        return action_id

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
                    business_id, action_id, requested_by_user_id,
                    status, reason, requested_at
                )
                VALUES (%s, %s, %s, 'pending', %s, NOW())
                RETURNING id
                """,
                (business_id, action_id, requested_by_user_id, reason),
            )
            approval_id = cur.fetchone()[0]
        self.conn.commit()
        return approval_id

    def _create_run(self, *, business_id: UUID, workflow_id: UUID, event_record_id: UUID, idempotency_key: str, payload: dict[str, Any]) -> UUID:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_runs (
                    business_id, workflow_id, event_record_id,
                    idempotency_key, status, input_payload, output_payload,
                    started_at, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, 'running', %s, '{}'::jsonb, NOW(), NOW(), NOW())
                RETURNING id
                """,
                (business_id, workflow_id, event_record_id, idempotency_key, Jsonb(_json_safe(payload))),
            )
            run_id = cur.fetchone()[0]
        self.conn.commit()
        return run_id

    def _find_run(self, business_id: UUID, workflow_id: UUID, idempotency_key: str) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, workflow_id, event_record_id, idempotency_key,
                       status, input_payload, output_payload, error_message,
                       started_at, completed_at, created_at, updated_at
                FROM workflow_runs
                WHERE business_id = %s AND workflow_id = %s AND idempotency_key = %s
                """,
                (business_id, workflow_id, idempotency_key),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "run_id": row[0],
            "business_id": row[1],
            "workflow_id": row[2],
            "event_record_id": row[3],
            "idempotency_key": row[4],
            "status": row[5],
            "output": row[7] or {},
        }

    def _get_event(self, business_id: UUID, event_record_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, event_id, event_type, source, priority,
                       status, entity_type, entity_id, payload, occurred_at
                FROM events
                WHERE id = %s AND business_id = %s
                """,
                (event_record_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise WorkflowError("Event not found for this business")
        return {
            "id": row[0],
            "business_id": row[1],
            "event_id": row[2],
            "event_type": row[3],
            "source": row[4],
            "priority": row[5],
            "status": row[6],
            "entity_type": row[7],
            "entity_id": row[8],
            "payload": row[9] or {},
            "occurred_at": row[10].isoformat() if row[10] else None,
        }

    def _record_step(self, run_id: UUID, order: int, key: str, step_type: str, status: str, input_data: dict[str, Any], output_data: dict[str, Any], error_message: str | None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO workflow_steps (
                    run_id, step_order, step_key, step_type, status,
                    input_data, output_data, error_message, started_at, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                ON CONFLICT (run_id, step_key) DO NOTHING
                """,
                (run_id, order, key, step_type, status, Jsonb(_json_safe(input_data)), Jsonb(_json_safe(output_data)), error_message),
            )
        self.conn.commit()

    def _complete_step(self, run_id: UUID, key: str, status: str, output_data: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow_steps
                SET status = %s,
                    output_data = %s,
                    completed_at = NOW()
                WHERE run_id = %s AND step_key = %s
                """,
                (status, Jsonb(_json_safe(output_data)), run_id, key),
            )
        self.conn.commit()

    def _finish_run(self, run_id: UUID, status: str, output: dict[str, Any], error_message: str | None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE workflow_runs
                SET status = %s,
                    output_payload = %s,
                    error_message = %s,
                    completed_at = CASE WHEN %s IN ('completed','failed','skipped') THEN NOW() ELSE NULL END,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (status, Jsonb(_json_safe(output)), error_message, status, run_id),
            )
        self.conn.commit()

    def _require_user(self, business_id: UUID, user_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE id = %s AND business_id = %s AND status = 'active'",
                (user_id, business_id),
            )
            if not cur.fetchone():
                raise WorkflowError("User does not belong to this business")

    @staticmethod
    def _workflow_row(row) -> dict[str, Any]:
        return {
            "id": row[0],
            "business_id": row[1],
            "name": row[2],
            "trigger_event_type": row[3],
            "enabled": bool(row[4]),
            "definition": row[5] or {},
            "created_by_user_id": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "updated_at": row[8].isoformat() if row[8] else None,
        }
