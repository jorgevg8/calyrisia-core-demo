from __future__ import annotations

from typing import Any
from uuid import UUID


class ConversationServiceError(Exception):
    pass


class ConversationService:
    """Conversation read/management layer for Day 3 continuous chat."""

    def __init__(self, conn):
        self.conn = conn

    def get_conversation(self, *, business_id: UUID, conversation_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, customer_id, channel, status, intent, topic,
                       outcome, handoff_to_human, transfer_reason, started_at,
                       last_message_at, closed_at, metadata, created_at, updated_at
                FROM conversations
                WHERE id = %s AND business_id = %s
                """,
                (conversation_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                raise ConversationServiceError("Conversation not found for this business")

            cur.execute(
                """
                SELECT id, customer_id, sender_type, direction, message_type,
                       content, intent, sentiment, tool_used, action_taken,
                       metadata, created_at
                FROM conversation_messages
                WHERE conversation_id = %s AND business_id = %s
                ORDER BY created_at ASC
                LIMIT 200
                """,
                (conversation_id, business_id),
            )
            messages = cur.fetchall()

        keys = [
            "id", "business_id", "customer_id", "channel", "status", "intent",
            "topic", "outcome", "handoff_to_human", "transfer_reason",
            "started_at", "last_message_at", "closed_at", "metadata",
            "created_at", "updated_at",
        ]
        conversation = dict(zip(keys, row))
        conversation["messages"] = [
            {
                "id": m[0],
                "customer_id": m[1],
                "sender_type": m[2],
                "direction": m[3],
                "message_type": m[4],
                "content": m[5],
                "intent": m[6],
                "sentiment": m[7],
                "tool_used": m[8],
                "action_taken": m[9],
                "metadata": m[10],
                "created_at": m[11],
            }
            for m in messages
        ]
        return self._safe(conversation)

    def handoff(self, *, business_id: UUID, conversation_id: UUID, reason: str, actor: str = "system") -> dict[str, Any]:
        """Mark a conversation for human intervention without changing lifecycle status."""
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE conversations
                SET handoff_to_human = TRUE,
                    transfer_reason = %s,
                    outcome = 'human_handoff_requested',
                    updated_at = NOW(),
                    metadata = COALESCE(metadata, '{}'::jsonb) || jsonb_build_object(
                        'handoff_actor', %s::text,
                        'handoff_status', 'requested',
                        'handoff_timestamp', NOW()
                    )
                WHERE id = %s AND business_id = %s
                RETURNING id, status, handoff_to_human, transfer_reason, outcome, updated_at, metadata
                """,
                (reason, actor, conversation_id, business_id),
            )
            row = cur.fetchone()

        if not row:
            raise ConversationServiceError("Conversation not found for this business")

        self.conn.commit()
        return self._safe(
            {
                "id": row[0],
                "status": row[1],
                "handoff_to_human": row[2],
                "transfer_reason": row[3],
                "outcome": row[4],
                "updated_at": row[5],
                "metadata": row[6],
            }
        )

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
            return {str(k): ConversationService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [ConversationService._safe(v) for v in value]
        return value