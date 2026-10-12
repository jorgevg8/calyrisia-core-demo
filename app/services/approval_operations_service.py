from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.services.tenant_guard import TenantGuard, TenantIsolationError
from app.services.workflow_engine import WorkflowEngine, WorkflowError


class ApprovalOperationsError(Exception):
    pass


class ApprovalOperationsService:
    """Step 46: unified human operations center for approvals and handoffs."""

    DEFAULT_TTL_MINUTES = 1440

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    def list_queue(self, business_id: UUID, *, limit: int = 50) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        limit = max(1, min(int(limit), 200))
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ap.id,
                    ap.business_id,
                    ap.action_id,
                    ap.requested_by_user_id,
                    ap.status,
                    ap.reason,
                    ap.requested_at,
                    ap.expires_at,
                    ap.retry_count,
                    ac.action_type,
                    ac.resource_type,
                    ac.tool_name,
                    ac.status,
                    ac.input_data
                FROM approvals ap
                JOIN actions ac ON ac.id = ap.action_id
                WHERE ap.business_id = %s
                  AND ap.status = 'pending'
                ORDER BY ap.requested_at ASC
                LIMIT %s
                """,
                (business_id, limit),
            )
            approval_rows = cur.fetchall()

            cur.execute(
                """
                SELECT
                    c.id,
                    c.business_id,
                    c.customer_id,
                    c.channel,
                    c.status,
                    c.transfer_reason,
                    c.outcome,
                    c.last_message_at,
                    c.updated_at,
                    c.metadata,
                    cu.full_name
                FROM conversations c
                LEFT JOIN customers cu ON cu.id = c.customer_id
                WHERE c.business_id = %s
                  AND c.handoff_to_human = TRUE
                  AND COALESCE(c.metadata->>'handoff_status', 'requested') <> 'resolved'
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (business_id, limit),
            )
            handoff_rows = cur.fetchall()

        now = datetime.now(timezone.utc)
        items: list[dict[str, Any]] = []
        expired_count = 0

        for row in approval_rows:
            expires_at = self._safe_datetime(row[7])
            expired = bool(expires_at and expires_at <= now)
            if expired:
                expired_count += 1
            items.append(
                {
                    "type": "approval",
                    "id": str(row[0]),
                    "business_id": str(row[1]),
                    "action_id": str(row[2]),
                    "requested_by_user_id": str(row[3]) if row[3] else None,
                    "status": "expired" if expired else row[4],
                    "reason": row[5],
                    "requested_at": self._safe(row[6]),
                    "expires_at": self._safe(row[7]),
                    "retry_count": int(row[8] or 0),
                    "action_type": row[9],
                    "resource_type": row[10],
                    "tool_name": row[11],
                    "action_status": row[12],
                    "input_data": self._safe(row[13] or {}),
                }
            )

        for row in handoff_rows:
            metadata = row[9] or {}
            items.append(
                {
                    "type": "handoff",
                    "id": str(row[0]),
                    "business_id": str(row[1]),
                    "customer_id": str(row[2]) if row[2] else None,
                    "customer_name": row[10],
                    "channel": row[3],
                    "status": metadata.get("handoff_status", "requested"),
                    "conversation_status": row[4],
                    "reason": row[5],
                    "outcome": row[6],
                    "last_message_at": self._safe(row[7]),
                    "updated_at": self._safe(row[8]),
                    "metadata": self._safe(metadata),
                }
            )

        items.sort(key=lambda item: item.get("requested_at") or item.get("updated_at") or "", reverse=True)
        return {
            "success": True,
            "business_id": str(business_id),
            "counts": {
                "approvals_pending": sum(1 for item in items if item["type"] == "approval" and item["status"] == "pending"),
                "approvals_expired": expired_count,
                "handoffs_open": sum(1 for item in items if item["type"] == "handoff"),
                "total": len(items),
            },
            "items": items[:limit],
        }

    def get_approval(self, business_id: UUID, approval_id: UUID) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    ap.id,
                    ap.business_id,
                    ap.action_id,
                    ap.requested_by_user_id,
                    ap.status,
                    ap.reason,
                    ap.requested_at,
                    ap.expires_at,
                    ap.retry_count,
                    ap.decision_by_user_id,
                    ap.decision_at,
                    ap.decision_reason,
                    ac.action_type,
                    ac.resource_type,
                    ac.tool_name,
                    ac.status,
                    ac.input_data,
                    ac.reason
                FROM approvals ap
                JOIN actions ac ON ac.id = ap.action_id
                WHERE ap.id = %s AND ap.business_id = %s
                """,
                (approval_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise ApprovalOperationsError("Approval not found for this business")

        expires_at = self._safe_datetime(row[7])
        expired = row[4] == "pending" and expires_at is not None and expires_at <= datetime.now(timezone.utc)
        return {
            "id": str(row[0]),
            "business_id": str(row[1]),
            "action_id": str(row[2]),
            "requested_by_user_id": str(row[3]) if row[3] else None,
            "status": "expired" if expired else row[4],
            "reason": row[5],
            "requested_at": self._safe(row[6]),
            "expires_at": self._safe(row[7]),
            "retry_count": int(row[8] or 0),
            "decision_by_user_id": str(row[9]) if row[9] else None,
            "decision_at": self._safe(row[10]),
            "decision_reason": row[11],
            "expired": expired,
            "action": {
                "action_type": row[12],
                "resource_type": row[13],
                "tool_name": row[14],
                "status": row[15],
                "input_data": self._safe(row[16] or {}),
                "reason": row[17],
            },
        }

    def decide_approval(
        self,
        business_id: UUID,
        approval_id: UUID,
        *,
        decided_by_user_id: UUID,
        approve: bool,
        reason: str | None,
    ) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        self._require_user(business_id, decided_by_user_id)
        approval = self.get_approval(business_id, approval_id)

        if approval["status"] != "pending":
            raise ApprovalOperationsError(f"Approval is not pending: {approval['status']}")

        decision_reason = (reason or ("Approved by human operator." if approve else "Rejected by human operator.")).strip()
        if not decision_reason:
            raise ApprovalOperationsError("A decision reason is required")

        if approval["expired"]:
            self._expire_one(
                business_id=business_id,
                approval_id=approval_id,
                decided_by_user_id=decided_by_user_id,
                reason="Approval expired before a decision was made.",
            )
            raise ApprovalOperationsError("Approval has expired")

        if not approve:
            return self._reject(business_id, approval, decided_by_user_id, decision_reason)

        self._mark_approved(business_id, approval_id, decided_by_user_id, decision_reason)
        action_id = UUID(approval["action_id"])
        workflow_data = approval["action"]["input_data"] or {}

        if approval["action"]["action_type"] == "workflow_action":
            try:
                run_id = UUID(str(workflow_data["run_id"]))
                resumed = WorkflowEngine(self.conn).resume_after_approval(
                    business_id=business_id,
                    run_id=run_id,
                    approval_id=approval_id,
                    approved_by_user_id=decided_by_user_id,
                )
                self._mark_action_completed(action_id, resumed)
                self._write_audit(
                    business_id=business_id,
                    action_id=action_id,
                    actor_user_id=decided_by_user_id,
                    action_type="approval_decision",
                    resource_type="workflow",
                    resource_id=run_id,
                    reason=decision_reason,
                    metadata={"approval_id": str(approval_id), "decision": "approved", "run_status": resumed.get("status")},
                )
                return {"success": True, "decision": "approved", "approval_id": str(approval_id), "workflow": resumed}
            except Exception as exc:
                self._mark_action_failed(action_id, str(exc))
                self._write_audit(
                    business_id=business_id,
                    action_id=action_id,
                    actor_user_id=decided_by_user_id,
                    action_type="approval_execution_failed",
                    resource_type="workflow",
                    resource_id=UUID(str(workflow_data.get("run_id"))) if workflow_data.get("run_id") else None,
                    reason=str(exc),
                    metadata={"approval_id": str(approval_id), "decision": "approved"},
                )
                raise ApprovalOperationsError(f"Approved workflow could not resume: {exc}") from exc

        # Non-workflow approvals become validated and are ready for their executor layer.
        self._set_action_validated(action_id)
        self._write_audit(
            business_id=business_id,
            action_id=action_id,
            actor_user_id=decided_by_user_id,
            action_type="approval_decision",
            resource_type=approval["action"]["resource_type"],
            resource_id=None,
            reason=decision_reason,
            metadata={"approval_id": str(approval_id), "decision": "approved", "execution_status": "validated"},
        )
        return {"success": True, "decision": "approved", "approval_id": str(approval_id), "action_status": "validated"}

    def retry_approval(self, business_id: UUID, approval_id: UUID, *, requested_by_user_id: UUID, reason: str | None) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        self._require_user(business_id, requested_by_user_id)
        approval = self.get_approval(business_id, approval_id)
        if approval["action"]["action_type"] != "workflow_action":
            raise ApprovalOperationsError("Only workflow approvals support retry in Step 46")
        if approval["status"] not in {"rejected", "expired"}:
            raise ApprovalOperationsError("Only rejected or expired approvals can be retried")

        run_id = approval["action"]["input_data"].get("run_id")
        if not run_id:
            raise ApprovalOperationsError("Approval does not contain a workflow run")

        decision_reason = (reason or "Approval retried by human operator.").strip()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status = 'pending',
                    decision_by_user_id = NULL,
                    decision_at = NULL,
                    decision_reason = NULL,
                    retry_count = COALESCE(retry_count, 0) + 1,
                    expires_at = NOW() + interval '24 hours'
                WHERE id = %s AND business_id = %s
                """,
                (approval_id, business_id),
            )
            cur.execute(
                """
                UPDATE actions
                SET status = 'waiting_approval',
                    error_message = NULL,
                    updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (approval["action_id"], business_id),
            )
            cur.execute(
                """
                UPDATE workflow_runs
                SET status = 'waiting_approval', error_message = NULL, completed_at = NULL, updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (run_id, business_id),
            )
            cur.execute(
                """
                UPDATE workflow_steps
                SET status = 'waiting_approval', error_message = NULL, completed_at = NULL
                WHERE run_id = %s
                  AND output_data->>'approval_id' = %s
                """,
                (run_id, str(approval_id)),
            )
        self.conn.commit()
        self._write_audit(
            business_id=business_id,
            action_id=UUID(approval["action_id"]),
            actor_user_id=requested_by_user_id,
            action_type="approval_retry",
            resource_type="workflow",
            resource_id=UUID(str(run_id)),
            reason=decision_reason,
            metadata={"approval_id": str(approval_id), "retry_count": int(approval["retry_count"]) + 1},
        )
        return {"success": True, "approval_id": str(approval_id), "status": "pending", "retry_count": int(approval["retry_count"]) + 1}

    def expire_stale(self, business_id: UUID, *, decided_by_user_id: UUID, limit: int = 50) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        self._require_user(business_id, decided_by_user_id)
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id
                FROM approvals
                WHERE business_id = %s
                  AND status = 'pending'
                  AND expires_at IS NOT NULL
                  AND expires_at <= NOW()
                ORDER BY requested_at ASC
                LIMIT %s
                """,
                (business_id, max(1, min(limit, 200))),
            )
            ids = [row[0] for row in cur.fetchall()]

        for approval_id in ids:
            self._expire_one(
                business_id=business_id,
                approval_id=approval_id,
                decided_by_user_id=decided_by_user_id,
                reason="Approval expired automatically by the operations center.",
            )
        return {"success": True, "expired_count": len(ids), "approval_ids": [str(x) for x in ids]}

    def acknowledge_handoff(self, business_id: UUID, conversation_id: UUID, *, user_id: UUID, note: str | None) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        self._require_user(business_id, user_id)
        conversation = self._handoff_for_business(business_id, conversation_id)
        metadata = conversation.get("metadata") or {}
        metadata.update(
            {
                "handoff_status": "acknowledged",
                "handoff_actor": str(user_id),
                "handoff_acknowledged_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if note:
            metadata["handoff_note"] = note
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET metadata = %s, updated_at = NOW()
                WHERE id = %s AND business_id = %s AND handoff_to_human = TRUE
                """,
                (Jsonb(metadata), conversation_id, business_id),
            )
        self.conn.commit()
        self._write_handoff_audit(business_id, conversation_id, user_id, "human_handoff_acknowledged", metadata)
        return {"success": True, "conversation_id": str(conversation_id), "handoff_status": "acknowledged", "metadata": metadata}

    def resolve_handoff(self, business_id: UUID, conversation_id: UUID, *, user_id: UUID, note: str | None) -> dict[str, Any]:
        self.tenant.require_business(business_id)
        self._require_user(business_id, user_id)
        conversation = self._handoff_for_business(business_id, conversation_id)
        metadata = conversation.get("metadata") or {}
        metadata.update(
            {
                "handoff_status": "resolved",
                "handoff_actor": str(user_id),
                "handoff_resolved_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        if note:
            metadata["handoff_resolution_note"] = note
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET handoff_to_human = FALSE,
                    metadata = %s,
                    updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (Jsonb(metadata), conversation_id, business_id),
            )
        self.conn.commit()
        self._write_handoff_audit(business_id, conversation_id, user_id, "human_handoff_resolved", metadata)
        return {"success": True, "conversation_id": str(conversation_id), "handoff_status": "resolved", "metadata": metadata}

    def _reject(self, business_id: UUID, approval: dict[str, Any], user_id: UUID, reason: str) -> dict[str, Any]:
        approval_id = UUID(approval["id"])
        action_id = UUID(approval["action_id"])
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status = 'rejected', decision_by_user_id = %s, decision_at = NOW(), decision_reason = %s
                WHERE id = %s AND business_id = %s AND status = 'pending'
                """,
                (user_id, reason, approval_id, business_id),
            )
            cur.execute(
                """
                UPDATE actions
                SET status = 'rejected', error_message = %s, updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (reason, action_id, business_id),
            )
        self.conn.commit()
        input_data = approval["action"]["input_data"] or {}
        if approval["action"]["action_type"] == "workflow_action" and input_data.get("run_id"):
            self._mark_workflow_rejected(business_id, UUID(str(input_data["run_id"])), approval_id, reason)
        self._write_audit(
            business_id=business_id,
            action_id=action_id,
            actor_user_id=user_id,
            action_type="approval_decision",
            resource_type=approval["action"]["resource_type"],
            resource_id=UUID(str(input_data["run_id"])) if input_data.get("run_id") else None,
            reason=reason,
            metadata={"approval_id": str(approval_id), "decision": "rejected"},
        )
        return {"success": True, "decision": "rejected", "approval_id": str(approval_id), "status": "rejected"}

    def _mark_approved(self, business_id: UUID, approval_id: UUID, user_id: UUID, reason: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approvals
                SET status = 'approved', decision_by_user_id = %s, decision_at = NOW(), decision_reason = %s
                WHERE id = %s AND business_id = %s AND status = 'pending'
                """,
                (user_id, reason, approval_id, business_id),
            )
            if cur.rowcount != 1:
                self.conn.rollback()
                raise ApprovalOperationsError("Approval changed before the decision could be recorded")
            cur.execute(
                """
                UPDATE actions
                SET status = 'executing', started_at = COALESCE(started_at, NOW()), updated_at = NOW(), error_message = NULL
                WHERE id = (SELECT action_id FROM approvals WHERE id = %s AND business_id = %s)
                """,
                (approval_id, business_id),
            )
        self.conn.commit()

    def _set_action_validated(self, action_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute("UPDATE actions SET status = 'validated', updated_at = NOW() WHERE id = %s", (action_id,))
        self.conn.commit()

    def _mark_action_completed(self, action_id: UUID, result: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE actions SET status = 'completed', output_data = %s, completed_at = NOW(), updated_at = NOW() WHERE id = %s",
                (Jsonb(self._json_safe(result)), action_id),
            )
        self.conn.commit()

    def _mark_action_failed(self, action_id: UUID, error: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE actions SET status = 'failed', error_message = %s, updated_at = NOW() WHERE id = %s",
                (error, action_id),
            )
        self.conn.commit()

    def _mark_workflow_rejected(self, business_id: UUID, run_id: UUID, approval_id: UUID, reason: str) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE workflow_runs SET status = 'failed', error_message = %s, completed_at = NOW(), updated_at = NOW() WHERE id = %s AND business_id = %s",
                (f"Human approval rejected: {reason}", run_id, business_id),
            )
            cur.execute(
                """
                UPDATE workflow_steps
                SET status = 'failed', error_message = %s, completed_at = NOW()
                WHERE run_id = %s AND output_data->>'approval_id' = %s
                """,
                (f"Human approval rejected: {reason}", run_id, str(approval_id)),
            )
        self.conn.commit()

    def _expire_one(self, *, business_id: UUID, approval_id: UUID, decided_by_user_id: UUID, reason: str) -> None:
        approval = self.get_approval(business_id, approval_id)
        if approval["status"] not in {"pending", "expired"}:
            return
        action_id = UUID(approval["action_id"])
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE approvals SET status = 'rejected', decision_by_user_id = %s, decision_at = NOW(), decision_reason = %s WHERE id = %s AND business_id = %s AND status = 'pending'",
                (decided_by_user_id, reason, approval_id, business_id),
            )
            cur.execute(
                "UPDATE actions SET status = 'rejected', error_message = %s, updated_at = NOW() WHERE id = %s AND business_id = %s",
                (reason, action_id, business_id),
            )
        self.conn.commit()
        input_data = approval["action"]["input_data"] or {}
        if input_data.get("run_id"):
            self._mark_workflow_rejected(business_id, UUID(str(input_data["run_id"])), approval_id, reason)
        self._write_audit(
            business_id=business_id,
            action_id=action_id,
            actor_user_id=decided_by_user_id,
            action_type="approval_expired",
            resource_type=approval["action"]["resource_type"],
            resource_id=UUID(str(input_data["run_id"])) if input_data.get("run_id") else None,
            reason=reason,
            metadata={"approval_id": str(approval_id), "decision": "expired"},
        )

    def _handoff_for_business(self, business_id: UUID, conversation_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id, metadata, handoff_to_human FROM conversations WHERE id = %s AND business_id = %s",
                (conversation_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            raise ApprovalOperationsError("Conversation not found for this business")
        if not row[2]:
            raise ApprovalOperationsError("Conversation does not currently require human handoff")
        return {"id": row[0], "metadata": row[1] or {}}

    def _write_handoff_audit(self, business_id: UUID, conversation_id: UUID, user_id: UUID, action_type: str, metadata: dict[str, Any]) -> None:
        self._write_audit(
            business_id=business_id,
            action_id=None,
            actor_user_id=user_id,
            action_type=action_type,
            resource_type="conversation",
            resource_id=conversation_id,
            reason=action_type,
            metadata=metadata,
        )

    def _write_audit(
        self,
        *,
        business_id: UUID,
        action_id: UUID | None,
        actor_user_id: UUID | None,
        action_type: str,
        resource_type: str | None,
        resource_id: UUID | None,
        reason: str,
        metadata: dict[str, Any],
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id, action_id, actor_type, actor_user_id,
                    action_type, resource_type, resource_id, status,
                    tool_name, reason, before_data, after_data, metadata, created_at
                )
                VALUES (%s, %s, 'user', %s, %s, %s, %s, 'success',
                        'operations_center', %s, '{}'::jsonb, '{}'::jsonb, %s, NOW())
                """,
                (
                    business_id,
                    action_id,
                    actor_user_id,
                    action_type,
                    resource_type,
                    resource_id,
                    reason,
                    Jsonb(self._json_safe(metadata)),
                ),
            )
        self.conn.commit()

    def _require_user(self, business_id: UUID, user_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM users WHERE id = %s AND business_id = %s AND status = 'active'",
                (user_id, business_id),
            )
            if cur.fetchone() is None:
                raise ApprovalOperationsError("User does not belong to this business")

    @staticmethod
    def _safe_datetime(value: Any) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    @staticmethod
    def _safe(value: Any) -> Any:
        from datetime import date, time
        from decimal import Decimal
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, (date, time)):
            return value.isoformat()
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, dict):
            return {str(k): ApprovalOperationsService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [ApprovalOperationsService._safe(v) for v in value]
        return value

    @staticmethod
    def _json_safe(value: Any) -> Any:
        return ApprovalOperationsService._safe(value)
