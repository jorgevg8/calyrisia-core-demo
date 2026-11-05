import json
from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class WebhookDispatcherError(Exception):
    pass

class WebhookDispatcherService:
    def __init__(self, conn):
        self.conn = conn

    def dispatch(self, business_id: UUID, target_url: str, event_name: str, payload: dict) -> dict:
        """Registra y encola un webhook para disparar acciones en sistemas externos (ej. n8n, Make, Zapier)."""
        with self.conn.cursor() as cur:
            webhook_id = str(uuid4())
            
            # Guardamos el registro del disparo
            cur.execute("""
                INSERT INTO external_webhooks (id, business_id, target_url, event_name, payload, status)
                VALUES (%s, %s, %s, %s, %s::jsonb, 'dispatched')
                RETURNING id, target_url, event_name, status
            """, (webhook_id, str(business_id), target_url, event_name, json.dumps(payload)))
            
            row = cur.fetchone()
            
            # Auditoría: Dejamos constancia de que la IA se comunicó con el exterior
            AuditService(self.conn).log_action(
                business_id, "SYSTEM", "WEBHOOK_DISPATCHED", webhook_id, 
                {"event": event_name, "url": target_url}
            )
            
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "target_url": row[1],
                "event_name": row[2],
                "status": row[3]
            }