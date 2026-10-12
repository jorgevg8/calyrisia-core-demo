from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from psycopg.types.json import Jsonb


class KnowledgePolicyError(Exception):
    pass


class KnowledgePolicyService:
    """Step 43 — tenant-isolated Knowledge & Policy Center."""

    ALLOWED_TYPES = {"knowledge", "policy", "faq", "process"}
    ALLOWED_VISIBILITY = {"customer", "internal", "both"}
    ALLOWED_STATUS = {"active", "archived"}

    def __init__(self, conn):
        self.conn = conn

    @staticmethod
    def _row(row: tuple) -> dict[str, Any]:
        keys = [
            "id", "business_id", "item_type", "title", "content", "visibility",
            "priority", "source", "metadata", "status", "created_by", "created_at", "updated_at"
        ]
        data = dict(zip(keys, row))
        data["id"] = str(data["id"])
        data["business_id"] = str(data["business_id"])
        if data.get("created_by") is not None:
            data["created_by"] = str(data["created_by"])
        for key in ("created_at", "updated_at"):
            if data.get(key) is not None and hasattr(data[key], "isoformat"):
                data[key] = data[key].isoformat()
        data["metadata"] = data.get("metadata") or {}
        return data

    def list_items(
        self,
        business_id: UUID,
        *,
        item_type: str | None = None,
        search: str | None = None,
        visibility: str | None = None,
        include_archived: bool = False,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        clauses = ["business_id = %s"]
        params: list[Any] = [business_id]
        if item_type:
            if item_type not in self.ALLOWED_TYPES:
                raise KnowledgePolicyError("Tipo de contenido no válido.")
            clauses.append("item_type = %s")
            params.append(item_type)
        if visibility:
            if visibility not in self.ALLOWED_VISIBILITY:
                raise KnowledgePolicyError("Visibilidad no válida.")
            clauses.append("visibility = %s")
            params.append(visibility)
        if not include_archived:
            clauses.append("status = 'active'")
        if search:
            clauses.append("(title ILIKE %s OR content ILIKE %s)")
            term = f"%{search.strip()}%"
            params.extend([term, term])
        params.append(limit)
        query = f"""
            SELECT id, business_id, item_type, title, content, visibility,
                   priority, source, metadata, status, created_by, created_at, updated_at
            FROM business_knowledge_items
            WHERE {' AND '.join(clauses)}
            ORDER BY priority DESC, updated_at DESC
            LIMIT %s
        """
        with self.conn.cursor() as cur:
            cur.execute(query, tuple(params))
            rows = cur.fetchall()
        return [self._row(r) for r in rows]

    def get(self, business_id: UUID, item_id: UUID) -> dict[str, Any] | None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, business_id, item_type, title, content, visibility,
                       priority, source, metadata, status, created_by, created_at, updated_at
                FROM business_knowledge_items
                WHERE id = %s AND business_id = %s
                """,
                (item_id, business_id),
            )
            row = cur.fetchone()
        return self._row(row) if row else None

    def create(
        self,
        business_id: UUID,
        user_id: UUID,
        *,
        item_type: str,
        title: str,
        content: str,
        visibility: str,
        priority: int,
        source: str | None,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        if item_type not in self.ALLOWED_TYPES:
            raise KnowledgePolicyError("Tipo de contenido no válido.")
        if visibility not in self.ALLOWED_VISIBILITY:
            raise KnowledgePolicyError("Visibilidad no válida.")
        if not title.strip() or not content.strip():
            raise KnowledgePolicyError("Título y contenido son obligatorios.")
        item_id = uuid4()
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO business_knowledge_items (
                    id, business_id, item_type, title, content, visibility,
                    priority, source, metadata, status, created_by, created_at, updated_at
                )
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'active',%s,NOW(),NOW())
                """,
                (
                    item_id, business_id, item_type, title.strip(), content.strip(), visibility,
                    priority, source.strip() if source else None, Jsonb(metadata or {}), user_id,
                ),
            )
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id, actor_type, action_type, resource_type,
                    resource_id, status, reason, metadata, created_at
                )
                VALUES (%s,'user','knowledge_item_created','business_knowledge_item',%s,'success',%s,%s,NOW())
                """,
                (
                    business_id, item_id, f"Creó contenido {item_type}: {title.strip()}",
                    Jsonb({"item_type": item_type, "visibility": visibility, "priority": priority}),
                ),
            )
        return self.get(business_id, item_id)  # type: ignore[return-value]

    def update(self, business_id: UUID, user_id: UUID, item_id: UUID, changes: dict[str, Any]) -> dict[str, Any]:
        current = self.get(business_id, item_id)
        if current is None:
            raise KnowledgePolicyError("Contenido no encontrado.")
        allowed = {"title", "content", "visibility", "priority", "source", "metadata", "status"}
        fields = {k: v for k, v in changes.items() if k in allowed and v is not None}
        if not fields:
            return current
        if "visibility" in fields and fields["visibility"] not in self.ALLOWED_VISIBILITY:
            raise KnowledgePolicyError("Visibilidad no válida.")
        if "status" in fields and fields["status"] not in self.ALLOWED_STATUS:
            raise KnowledgePolicyError("Estado no válido.")
        if "title" in fields and not str(fields["title"]).strip():
            raise KnowledgePolicyError("El título no puede quedar vacío.")
        if "content" in fields and not str(fields["content"]).strip():
            raise KnowledgePolicyError("El contenido no puede quedar vacío.")

        set_parts = []
        params: list[Any] = []
        for key, value in fields.items():
            set_parts.append(f"{key} = %s")
            if key == "metadata":
                params.append(Jsonb(value or {}))
            else:
                params.append(value.strip() if key in {"title", "content", "source"} and isinstance(value, str) else value)
        set_parts.append("updated_at = NOW()")
        params.extend([item_id, business_id])

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                UPDATE business_knowledge_items
                SET {', '.join(set_parts)}
                WHERE id = %s AND business_id = %s
                """,
                tuple(params),
            )
            cur.execute(
                """
                INSERT INTO audit_logs (
                    business_id, actor_type, action_type, resource_type,
                    resource_id, status, reason, metadata, created_at
                )
                VALUES (%s,'user','knowledge_item_updated','business_knowledge_item',%s,'success',%s,%s,NOW())
                """,
                (
                    business_id, item_id, f"Actualizó contenido {current['item_type']}",
                    Jsonb({"fields": sorted(fields.keys())}),
                ),
            )
        return self.get(business_id, item_id)  # type: ignore[return-value]

    def archive(self, business_id: UUID, user_id: UUID, item_id: UUID) -> dict[str, Any]:
        return self.update(business_id, user_id, item_id, {"status": "archived"})

    def for_context(self, business_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
        """Compact set for the Brain. Internal content is safe for Brain context; customer visibility is metadata only."""
        items = self.list_items(business_id, include_archived=False, limit=limit)
        return [
            {
                "id": item["id"],
                "item_type": item["item_type"],
                "title": item["title"],
                "content": item["content"],
                "visibility": item["visibility"],
                "priority": item["priority"],
                "source": item["source"],
            }
            for item in items
        ]
