import json
from uuid import UUID, uuid4

class EventBusError(Exception):
    pass

class EventBusService:
    def __init__(self, conn):
        self.conn = conn

    def publish_event(self, business_id: UUID, event_type: str, payload: dict) -> dict:
        """Publica un evento en el bus (buzón) para ser procesado."""
        with self.conn.cursor() as cur:
            event_id = str(uuid4())
            cur.execute("""
                INSERT INTO event_bus_queue (id, business_id, event_type, payload, status)
                VALUES (%s, %s, %s, %s::jsonb, 'pending')
                RETURNING id, event_type, payload, status
            """, (event_id, str(business_id), event_type, json.dumps(payload)))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "business_id": str(business_id),
                "event_type": row[1],
                "payload": row[2] if isinstance(row[2], dict) else json.loads(row[2]),
                "status": row[3]
            }

    def list_pending_events(self, business_id: UUID) -> list:
        """Lista los eventos que Galaxy todavía no ha procesado."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, event_type, payload, status 
                FROM event_bus_queue 
                WHERE business_id = %s AND status = 'pending'
                ORDER BY created_at ASC
            """, (str(business_id),))
            rows = cur.fetchall()
            
            return [
                {
                    "id": str(r[0]),
                    "business_id": str(business_id),
                    "event_type": r[1],
                    "payload": r[2] if isinstance(r[2], dict) else json.loads(r[2]),
                    "status": r[3]
                } for r in rows
            ]