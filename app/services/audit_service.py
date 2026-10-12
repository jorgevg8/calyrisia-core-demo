import json
from uuid import UUID, uuid4

class AuditService:
    def __init__(self, conn):
        self.conn = conn

    def log_action(self, business_id: UUID, actor: str, action: str, target_resource: str = None, details: dict = None) -> None:
        """Escribe una entrada inmutable en el registro de auditoría del negocio."""
        details = details or {}
        with self.conn.cursor() as cur:
            cur.execute("""
                INSERT INTO audit_logs (id, business_id, actor, action, target_resource, details)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb)
            """, (str(uuid4()), str(business_id), actor, action, target_resource, json.dumps(details)))
        self.conn.commit()

    def get_logs(self, business_id: UUID, limit: int = 50) -> list:
        """Obtiene el historial de todo lo que ha pasado en el sistema."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, actor, action, target_resource, details, created_at
                FROM audit_logs
                WHERE business_id = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (str(business_id), limit))
            rows = cur.fetchall()
            
            return [
                {
                    "id": str(r[0]),
                    "business_id": str(business_id),
                    "actor": r[1],
                    "action": r[2],
                    "target_resource": r[3],
                    "details": r[4] if isinstance(r[4], dict) else json.loads(r[4] or '{}'),
                    "created_at": r[5]
                } for r in rows
            ]