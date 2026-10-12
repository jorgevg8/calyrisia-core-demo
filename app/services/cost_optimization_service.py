from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class CostOptimizationService:
    def __init__(self, conn):
        self.conn = conn

    def evaluate_task_roi(self, business_id: UUID, task_id: UUID, task_value: float, estimated_cost: float) -> dict:
        """Evalúa si vale la pena ejecutar una tarea basándose en su costo vs el valor potencial."""
        
        net_profit = task_value - estimated_cost
        
        # Reglas del Director Financiero IA
        if task_value == 0 and estimated_cost > 0.05:
            roi_status = "NEGATIVE"
            decision = "skip"  # Muy caro para no tener retorno financiero claro
        elif net_profit < 0:
            roi_status = "NEGATIVE"
            decision = "skip"  # Pérdida directa de dinero
        elif net_profit > 10.0:
            roi_status = "HIGH"
            decision = "execute" # Excelente ganancia, ejecutar con el mejor modelo (Pro)
        else:
            roi_status = "LOW"
            decision = "downgrade" # Ganancia marginal: Ejecutar pero con un modelo de IA más barato (Flash)

        with self.conn.cursor() as cur:
            opt_id = str(uuid4())
            cur.execute("""
                INSERT INTO autonomous_cost_optimizations (id, business_id, task_id, task_value, estimated_cost, roi_status, decision)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, task_id, roi_status, decision
            """, (opt_id, str(business_id), str(task_id), task_value, estimated_cost, roi_status, decision))
            
            row = cur.fetchone()
            
            # Dejamos constancia en la auditoría si la IA decidió cancelar una tarea por ser cara
            if decision == "skip":
                AuditService(self.conn).log_action(
                    business_id, "SYSTEM_CFO", "TASK_SKIPPED_DUE_TO_COST", str(task_id), 
                    {"cost": estimated_cost, "value": task_value}
                )
                
            self.conn.commit()

            return {
                "id": str(row[0]),
                "task_id": str(row[1]),
                "roi_status": row[2],
                "decision": row[3],
                "net_profit": float(net_profit)
            }