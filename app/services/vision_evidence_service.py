import json
from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class VisionEvidenceError(Exception):
    pass

class VisionEvidenceService:
    def __init__(self, conn):
        self.conn = conn

    def register_evidence(self, business_id: UUID, image_url: str, operation_type: str, detected_data: dict, confidence: float) -> dict:
        """Registra lo que vio la IA. Si la confianza es baja, exige revisión humana."""
        requires_human = confidence < 0.85 

        with self.conn.cursor() as cur:
            ev_id = str(uuid4())
            cur.execute("""
                INSERT INTO vision_evidences (id, business_id, image_url, operation_type, detected_data, confidence, requires_human, status)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, 'pending')
                RETURNING id, image_url, operation_type, confidence, requires_human, status
            """, (ev_id, str(business_id), image_url, operation_type, json.dumps(detected_data), confidence, requires_human))
            
            row = cur.fetchone()
            
            # Dejamos rastro de que la IA analizó una imagen
            AuditService(self.conn).log_action(
                business_id, "AI_VISION", "EVIDENCE_REGISTERED", ev_id, 
                {"operation": operation_type, "confidence": confidence, "needs_human": requires_human}
            )
            self.conn.commit()
            
            return {
                "id": str(row[0]), "image_url": row[1], "operation_type": row[2],
                "confidence": float(row[3]), "requires_human": row[4], "status": row[5]
            }