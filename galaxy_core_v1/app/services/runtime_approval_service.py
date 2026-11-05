import json
from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class RuntimeApprovalError(Exception):
    pass

class RuntimeApprovalService:
    def __init__(self, conn):
        self.conn = conn

    def request_approval(self, business_id: UUID, execution_id: UUID, action_name: str, reason: str, impact_level: str = 'medium', evidence: dict = None) -> dict:
        """La IA pausa la ejecución y solicita permiso al humano."""
        evidence = evidence or {}
        with self.conn.cursor() as cur:
            appr_id = str(uuid4())
            cur.execute("""
                INSERT INTO runtime_approvals (id, business_id, execution_id, action_name, reason, impact_level, status, evidence, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending', %s::jsonb, CURRENT_TIMESTAMP + INTERVAL '24 hours')
                RETURNING id, status, expires_at
            """, (appr_id, str(business_id), str(execution_id), action_name, reason, impact_level, json.dumps(evidence)))
            row = cur.fetchone()
            
            # 1. Congelamos a la IA (Pausamos la ejecución)
            cur.execute("UPDATE agent_executions SET status = 'waiting_approval' WHERE id = %s AND business_id = %s", (str(execution_id), str(business_id)))
            
            # 2. Registramos la solicitud en la auditoría inmutable
            AuditService(self.conn).log_action(business_id, "AI_AGENT", "APPROVAL_REQUESTED", str(execution_id), {"action": action_name})
            self.conn.commit()
            
            # EL FIX: Convertimos row[0] explícitamente a string
            return {"id": str(row[0]), "status": row[1], "expires_at": row[2]}

    def decide_approval(self, business_id: UUID, approval_id: UUID, user_id: UUID, approved: bool, notes: str = "") -> dict:
        """El humano (Owner) decide y la IA se descongela."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT execution_id, status FROM runtime_approvals WHERE id = %s AND business_id = %s", (str(approval_id), str(business_id)))
            appr = cur.fetchone()
            if not appr:
                raise RuntimeApprovalError("Aprobación no encontrada.")
            if appr[1] != 'pending':
                raise RuntimeApprovalError(f"La aprobación ya fue decidida o expiró: {appr[1]}")
            
            exec_id = appr[0]
            new_status = 'approved' if approved else 'rejected'
            
            cur.execute("""
                UPDATE runtime_approvals 
                SET status = %s, decided_by = %s, updated_at = CURRENT_TIMESTAMP 
                WHERE id = %s
            """, (new_status, str(user_id), str(approval_id)))

            # 3. Descongelamos a la IA o la cancelamos definitivamente
            exec_status = 'running' if approved else 'cancelled'
            cur.execute("UPDATE agent_executions SET status = %s WHERE id = %s", (exec_status, str(exec_id)))

            # 4. Dejamos huella en la auditoría
            audit_action = "APPROVAL_GRANTED" if approved else "APPROVAL_DENIED"
            AuditService(self.conn).log_action(business_id, "OWNER", audit_action, str(exec_id), {"notes": notes})

            self.conn.commit()
            
            # EL FIX: Convertimos exec_id explícitamente a string
            return {"id": str(approval_id), "execution_id": str(exec_id), "status": new_status, "execution_resumed": approved}