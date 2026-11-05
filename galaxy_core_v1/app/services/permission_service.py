from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class PermissionDecision:
    allowed: bool
    requires_approval: bool
    permission_id: UUID | None
    effect: str
    subject_type: str
    reason: str
    limits: dict[str, Any]


class PermissionService:
    """Evaluates Galaxy permissions before a tool is executed.

    Resolution order:
      1. explicit permission for a user
      2. permission for the user's role
      3. system permission (Galaxy)

    Within a level, lower priority numbers win.
    A missing permission is denied by default (least privilege).
    """

    def __init__(self, conn):
        self.conn = conn

    def evaluate(
        self,
        *,
        business_id: UUID,
        resource_type: str,
        action_type: str,
        requested_by_user_id: UUID | None,
        tool_requires_approval: bool,
    ) -> PermissionDecision:
        subject_candidates: list[tuple[str, UUID | None, str | None, int]] = []

        if requested_by_user_id is not None:
            subject_candidates.append(("user", requested_by_user_id, None, 1))
            role = self._get_user_role(business_id, requested_by_user_id)
            if role:
                subject_candidates.append(("user_role", None, role, 2))

        subject_candidates.append(("system", None, None, 3))

        for subject_type, user_id, role, specificity in subject_candidates:
            permission = self._find_permission(
                business_id=business_id,
                resource_type=resource_type,
                action_type=action_type,
                subject_type=subject_type,
                user_id=user_id,
                role=role,
            )
            if permission:
                permission_id, effect, requires_approval, limits, name = permission
                if effect == "deny":
                    return PermissionDecision(
                        allowed=False,
                        requires_approval=False,
                        permission_id=permission_id,
                        effect="deny",
                        subject_type=subject_type,
                        reason=f"Permission denied by '{name}'.",
                        limits=limits,
                    )

                approval_required = bool(requires_approval or tool_requires_approval)
                reason = (
                    f"Permission '{name}' allows the action. Human approval is required."
                    if approval_required
                    else f"Permission '{name}' allows the action."
                )
                return PermissionDecision(
                    allowed=True,
                    requires_approval=approval_required,
                    permission_id=permission_id,
                    effect="allow",
                    subject_type=subject_type,
                    reason=reason,
                    limits=limits,
                )

        return PermissionDecision(
            allowed=False,
            requires_approval=False,
            permission_id=None,
            effect="deny",
            subject_type="none",
            reason="No matching permission was found. Access is denied by default.",
            limits={},
        )

    def _get_user_role(self, business_id: UUID, user_id: UUID) -> str | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT role
                FROM users
                WHERE id = %s
                  AND business_id = %s
                  AND status = 'active'
                """,
                (user_id, business_id),
            )
            row = cur.fetchone()
        return row[0] if row else None

    def _find_permission(
        self,
        *,
        business_id: UUID,
        resource_type: str,
        action_type: str,
        subject_type: str,
        user_id: UUID | None,
        role: str | None,
    ) -> tuple[UUID, str, bool, dict[str, Any], str] | None:
        if subject_type == "user":
            subject_sql = "subject_type = 'user' AND user_id = %s"
            params: list[Any] = [
                business_id,
                resource_type,
                action_type,
                user_id,
            ]
        elif subject_type == "user_role":
            subject_sql = "subject_type = 'user_role' AND role = %s"
            params = [
                business_id,
                resource_type,
                action_type,
                role,
            ]
        else:
            subject_sql = "subject_type = 'system'"
            params = [business_id, resource_type, action_type]

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT id, effect, requires_approval, limits, name
                FROM permissions
                WHERE business_id = %s
                  AND resource_type = %s
                  AND action_type = %s
                  AND enabled = TRUE
                  AND {subject_sql}
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
                """,
                params,
            )
            row = cur.fetchone()

        if not row:
            return None

        return (
            row[0],
            row[1],
            bool(row[2]),
            row[3] or {},
            row[4],
        )
