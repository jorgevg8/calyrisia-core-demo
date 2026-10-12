from __future__ import annotations

from typing import Any
import time
from uuid import UUID

from psycopg.errors import UndefinedTable

from app.services.memory_service import MemoryService
from app.services.business_type_profile_service import BusinessTypeProfileService
from app.services.knowledge_policy_service import KnowledgePolicyService
from app.services.customer_360_service import Customer360Service


_STATIC_CONTEXT_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_STATIC_CONTEXT_TTL_SECONDS = 30.0


class ContextManager:
    """Builds the minimum useful context for a Galaxy decision."""

    def __init__(self, conn):
        self.conn = conn
        self.memory = MemoryService(conn)
        self.business_type_profiles = BusinessTypeProfileService(conn)
        self.knowledge_policy = KnowledgePolicyService(conn)
        self.customer_360 = Customer360Service(conn)

    def _get_business(self, business_id: UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, name, legal_name, business_type, description,
                       phone, email, website, timezone, currency, status
                FROM businesses
                WHERE id = %s
                """,
                (business_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "legal_name": row[2],
            "business_type": row[3],
            "description": row[4],
            "phone": row[5],
            "email": row[6],
            "website": row[7],
            "timezone": row[8],
            "currency": row[9],
            "status": row[10],
        }

    def _get_profile(self, business_id: UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, industry, short_description, legal_name,
                       address, city, state_province, country, postal_code,
                       operating_hours, policies, processes, objectives,
                       autonomy_config, communication_config, social_links,
                       additional_settings, profile_version, status
                FROM business_profiles
                WHERE business_id = %s AND status = 'active'
                LIMIT 1
                """,
                (business_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        keys = [
            "id", "industry", "short_description", "legal_name", "address",
            "city", "state_province", "country", "postal_code",
            "operating_hours", "policies", "processes", "objectives",
            "autonomy_config", "communication_config", "social_links",
            "additional_settings", "profile_version", "status",
        ]
        return dict(zip(keys, row))

    def _get_business_type_profile(self, business_id: UUID) -> dict[str, Any] | None:
        try:
            return self.business_type_profiles.resolve_for_business(business_id)
        except Exception:
            return None

    def _get_knowledge(self, business_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
        try:
            return self.knowledge_policy.for_context(business_id, limit=limit)
        except Exception:
            # Context building must remain resilient if the Step 43 table is not migrated yet.
            return []

    def _get_customer(self, business_id: UUID, customer_id: UUID | None) -> dict[str, Any] | None:
        if customer_id is None:
            return None
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, full_name, email, phone, status,
                       source, first_contact_at, last_interaction_at, notes
                FROM customers
                WHERE id = %s AND business_id = %s
                """,
                (customer_id, business_id),
            )
            row = cur.fetchone()
        if not row:
            return None
        keys = [
            "id", "full_name", "email", "phone", "status", "source",
            "first_contact_at", "last_interaction_at", "notes",
        ]
        return dict(zip(keys, row))

    def _get_conversation(self, business_id: UUID, conversation_id: UUID | None) -> dict[str, Any] | None:
        if conversation_id is None:
            return None

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, customer_id, channel, status, intent, topic, outcome,
                       handoff_to_human, transfer_reason, started_at, last_message_at,
                       closed_at, metadata
                FROM conversations
                WHERE id = %s AND business_id = %s
                """,
                (conversation_id, business_id),
            )
            row = cur.fetchone()
            if not row:
                return None

            cur.execute(
                """
                SELECT id, sender_type, direction, message_type, content,
                       intent, sentiment, tool_used, action_taken, created_at
                FROM conversation_messages
                WHERE conversation_id = %s AND business_id = %s
                ORDER BY created_at DESC
                LIMIT 8
                """,
                (conversation_id, business_id),
            )
            message_rows = cur.fetchall()

        conversation = {
            "id": row[0],
            "customer_id": row[1],
            "channel": row[2],
            "status": row[3],
            "intent": row[4],
            "topic": row[5],
            "outcome": row[6],
            "handoff_to_human": row[7],
            "transfer_reason": row[8],
            "started_at": row[9],
            "last_message_at": row[10],
            "closed_at": row[11],
            "metadata": row[12],
        }
        conversation["recent_messages"] = [
            {
                "id": m[0],
                "sender_type": m[1],
                "direction": m[2],
                "message_type": m[3],
                "content": m[4],
                "intent": m[5],
                "sentiment": m[6],
                "tool_used": m[7],
                "action_taken": m[8],
                "created_at": m[9],
            }
            for m in reversed(message_rows)
        ]
        return conversation

    def build_context(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None = None,
        conversation_id: UUID | None = None,
        memory_limit: int = 5,
        include_customer_360: bool = False,
    ) -> dict[str, Any]:
        cache_key = str(business_id)
        now = time.monotonic()
        cached = _STATIC_CONTEXT_CACHE.get(cache_key)
        if cached and (now - cached[0]) < _STATIC_CONTEXT_TTL_SECONDS:
            static = cached[1]
        else:
            business = self._get_business(business_id)
            if business is None:
                return {"found": False, "reason": "business_not_found"}
            static = {
                "business": business,
                "business_profile": self._get_profile(business_id),
                "business_type_profile": self._get_business_type_profile(business_id),
                "knowledge_base": self._get_knowledge(business_id),
            }
            _STATIC_CONTEXT_CACHE[cache_key] = (now, static)

        business = static["business"]
        profile = static["business_profile"]
        business_type_profile = static["business_type_profile"]
        knowledge_base = static["knowledge_base"]
        customer = self._get_customer(business_id, customer_id)
        conversation = self._get_conversation(business_id, conversation_id)
        memories = self.memory.get_recent_memories(
            business_id=business_id,
            customer_id=customer_id,
            limit=memory_limit,
        )
        customer_360 = None
        if include_customer_360 and customer_id is not None:
            try:
                customer_360 = self.customer_360.get(business_id=business_id, customer_id=customer_id)
            except Exception:
                customer_360 = None

        return {
            "found": True,
            "business": business,
            "business_profile": profile,
            "business_type_profile": business_type_profile,
            "knowledge_base": knowledge_base,
            "customer": customer,
            "conversation": conversation,
            "memories": memories,
            "customer_360": customer_360,
        }
