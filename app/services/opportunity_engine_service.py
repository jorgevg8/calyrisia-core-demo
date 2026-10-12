import json
from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class OpportunityEngineError(Exception):
    pass

class OpportunityEngineService:
    def __init__(self, conn):
        self.conn = conn

    def generate_opportunity(self, business_id: UUID, title: str, description: str, opportunity_type: str, potential_value: float = 0.0, metadata: dict = None) -> dict:
        """Registra una nueva oportunidad de negocio detectada por la IA."""
        metadata = metadata or {}
        with self.conn.cursor() as cur:
            opp_id = str(uuid4())
            cur.execute("""
                INSERT INTO business_opportunities (id, business_id, title, description, opportunity_type, potential_value, status, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, 'detected', %s::jsonb)
                RETURNING id, title, description, opportunity_type, potential_value, status
            """, (opp_id, str(business_id), title, description, opportunity_type, potential_value, json.dumps(metadata)))
            
            row = cur.fetchone()
            
            # Rastro en la auditoría de que la IA detectó oro
            AuditService(self.conn).log_action(
                business_id, "SYSTEM", "OPPORTUNITY_DETECTED", opp_id, 
                {"type": opportunity_type, "value": potential_value}
            )
            self.conn.commit()
            
            return {
                "id": str(row[0]), "title": row[1], "description": row[2],
                "opportunity_type": row[3], "potential_value": float(row[4]), "status": row[5]
            }