from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class GovernanceService:
    def __init__(self, conn):
        self.conn = conn

    def evaluate_action(self, business_id: UUID, agent_name: str, action_intent: str, risk_score: int) -> dict:
        """Evalúa si un agente tiene permitido ejecutar una acción basado en el riesgo y las políticas."""
        
        intent_lower = action_intent.lower()
        
        # Reglas Estrictas de Gobernanza
        if risk_score > 85:
            policy_evaluation = "denied"
            reasoning = "RIESGO CRÍTICO: La acción excede los límites de seguridad de la plataforma. Operación abortada."
        elif risk_score > 50 or "reembolso" in intent_lower or "eliminar" in intent_lower or "descuento" in intent_lower:
            policy_evaluation = "requires_human"
            reasoning = "ACCIÓN SENSIBLE: Riesgo moderado o impacto financiero directo. Requiere autorización explícita del Owner."
        else:
            policy_evaluation = "auto_approved"
            reasoning = "RIESGO BAJO: Acción segura permitida por las políticas de autonomía estándar."

        with self.conn.cursor() as cur:
            eval_id = str(uuid4())
            cur.execute("""
                INSERT INTO autonomous_governance_evaluations (id, business_id, agent_name, action_intent, risk_score, policy_evaluation, reasoning)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, agent_name, action_intent, policy_evaluation, reasoning
            """, (eval_id, str(business_id), agent_name, action_intent, risk_score, policy_evaluation, reasoning))
            
            row = cur.fetchone()
            
            # Auditoría estricta para compliance
            AuditService(self.conn).log_action(
                business_id, "SYSTEM_GOVERNANCE", f"GOVERNANCE_{policy_evaluation.upper()}", agent_name, 
                {"intent": action_intent, "risk": risk_score, "reason": reasoning}
            )
            
            self.conn.commit()

            return {
                "id": str(row[0]),
                "agent_name": row[1],
                "action_intent": row[2],
                "policy_evaluation": row[3],
                "reasoning": row[4]
            }