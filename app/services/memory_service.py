from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.services.tenant_guard import TenantGuard, TenantIsolationError


class MemoryService:
    """Persistence layer for Galaxy's structured memory."""

    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    def create_memory(
        self,
        *,
        business_id: UUID,
        memory_type: str,
        memory_key: str,
        content: str,
        customer_id: UUID | None = None,
        conversation_id: UUID | None = None,
        user_id: UUID | None = None,
        source: str | None = None,
        confidence: float | None = None,
        importance: int = 50,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> UUID:
        if not 0 <= importance <= 100:
            raise ValueError("importance must be between 0 and 100")
        if confidence is not None and not 0 <= confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")

        try:
            self.tenant.require_business(business_id)
            self.tenant.require_optional_resource(business_id=business_id, resource_type="customer", resource_id=customer_id)
            self.tenant.require_optional_resource(business_id=business_id, resource_type="conversation", resource_id=conversation_id)
            self.tenant.require_optional_resource(business_id=business_id, resource_type="user", resource_id=user_id)
        except TenantIsolationError as exc:
            raise ValueError(str(exc)) from exc

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO memory (
                    business_id,
                    customer_id,
                    conversation_id,
                    user_id,
                    memory_type,
                    memory_key,
                    content,
                    source,
                    confidence,
                    importance,
                    metadata,
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    business_id,
                    customer_id,
                    conversation_id,
                    user_id,
                    memory_type,
                    memory_key,
                    content,
                    source,
                    confidence,
                    importance,
                    Jsonb(metadata or {}),
                    expires_at,
                ),
            )
            memory_id = cur.fetchone()[0]
        self.conn.commit()
        return memory_id

    def get_recent_memories(
        self,
        *,
        business_id: UUID,
        customer_id: UUID | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 50))
        query = """
            SELECT id, memory_type, memory_key, content, source,
                   confidence, importance, metadata, created_at, expires_at
            FROM memory
            WHERE business_id = %s
              AND (expires_at IS NULL OR expires_at > NOW())
        """
        params: list[Any] = [business_id]

        if customer_id is not None:
            query += " AND (customer_id = %s OR customer_id IS NULL)"
            params.append(customer_id)

        query += " ORDER BY importance DESC, created_at DESC LIMIT %s"
        params.append(limit)

        with self.conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

        return [
            {
                "id": row[0],
                "memory_type": row[1],
                "memory_key": row[2],
                "content": row[3],
                "source": row[4],
                "confidence": float(row[5]) if row[5] is not None else None,
                "importance": row[6],
                "metadata": row[7],
                "created_at": row[8],
                "expires_at": row[9],
            }
            for row in rows
        ]
    def upsert_customer_memory(
        self,
        *,
        business_id: UUID,
        customer_id: UUID,
        memory_type: str,
        memory_key: str,
        content: str,
        source: str | None = None,
        confidence: float | None = None,
        importance: int = 50,
        metadata: dict[str, Any] | None = None,
        expires_at: datetime | None = None,
    ) -> UUID:
        """Create or update a customer-scoped memory using business+customer+key identity."""
        if not memory_key.strip():
            raise ValueError("memory_key is required")
        if not 0 <= importance <= 100:
            raise ValueError("importance must be between 0 and 100")
        if confidence is not None and not 0 <= confidence <= 100:
            raise ValueError("confidence must be between 0 and 100")
        try:
            self.tenant.require_business(business_id)
            self.tenant.require_resource(business_id=business_id, resource_type="customer", resource_id=customer_id)
        except TenantIsolationError as exc:
            raise ValueError(str(exc)) from exc

        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id FROM memory
                WHERE business_id = %s AND customer_id = %s AND memory_key = %s
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (business_id, customer_id, memory_key),
            )
            row = cur.fetchone()
            if row:
                memory_id = row[0]
                cur.execute(
                    """
                    UPDATE memory
                    SET memory_type = %s, content = %s, source = %s,
                        confidence = %s, importance = %s, metadata = %s, expires_at = %s
                    WHERE id = %s AND business_id = %s AND customer_id = %s
                    """,
                    (memory_type, content, source, confidence, importance, Jsonb(metadata or {}), expires_at, memory_id, business_id, customer_id),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO memory (business_id, customer_id, memory_type, memory_key, content, source, confidence, importance, metadata, expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (business_id, customer_id, memory_type, memory_key, content, source, confidence, importance, Jsonb(metadata or {}), expires_at),
                )
                memory_id = cur.fetchone()[0]
        self.conn.commit()
        return memory_id

    def search_customer_memories(
        self, *, business_id: UUID, customer_id: UUID, query: str, limit: int = 20
    ) -> list[dict[str, Any]]:
        try:
            self.tenant.require_resource(business_id=business_id, resource_type="customer", resource_id=customer_id)
        except TenantIsolationError as exc:
            raise ValueError(str(exc)) from exc
        limit = max(1, min(limit, 50))
        term = f"%{query.strip()}%"
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, memory_type, memory_key, content, source, confidence, importance, metadata, created_at, expires_at
                FROM memory
                WHERE business_id = %s AND customer_id = %s
                  AND (expires_at IS NULL OR expires_at > NOW())
                  AND (memory_key ILIKE %s OR content ILIKE %s)
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
                """,
                (business_id, customer_id, term, term, limit),
            )
            rows = cur.fetchall()
        return [
            {
                "id": row[0], "memory_type": row[1], "memory_key": row[2], "content": row[3],
                "source": row[4], "confidence": float(row[5]) if row[5] is not None else None,
                "importance": row[6], "metadata": row[7], "created_at": row[8], "expires_at": row[9],
            }
            for row in rows
        ]

