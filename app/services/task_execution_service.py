from uuid import UUID
from app.services.audit_service import AuditService

class TaskExecutionError(Exception):
    pass

class TaskExecutionService:
    def __init__(self, conn):
        self.conn = conn

    def execute_task(self, business_id: UUID, task_id: UUID) -> dict:
        """Ejecuta una tarea pendiente si no está bloqueada por el candado de aprobación."""
        with self.conn.cursor() as cur:
            # 1. Buscar la tarea para ver su estado y nivel de riesgo
            cur.execute("""
                SELECT id, requires_approval, status 
                FROM autonomous_tasks 
                WHERE id = %s AND business_id = %s
            """, (str(task_id), str(business_id)))
            
            task = cur.fetchone()
            if not task:
                raise TaskExecutionError("Tarea no encontrada en este negocio.")
                
            _, requires_approval, status = task
            
            if status == 'completed':
                return {"success": True, "task_id": str(task_id), "status": "completed", "message": "La tarea ya estaba completada."}
                
            # 2. EL BLINDAJE: Si requiere aprobación y sigue pendiente, bloqueamos la ejecución
            if requires_approval and status == 'pending':
                raise TaskExecutionError("OPERACIÓN BLOQUEADA: Esta tarea es de alto riesgo y requiere aprobación humana en el Dashboard.")

            # 3. Si tiene permiso (o ya fue aprobada), simulamos la ejecución exitosa
            cur.execute("UPDATE autonomous_tasks SET status = 'completed' WHERE id = %s", (str(task_id),))
            
            # También completamos el plan asociado
            cur.execute("UPDATE autonomous_plans SET status = 'completed' WHERE task_id = %s", (str(task_id),))
            
        self.conn.commit()
        
        # 4. Registrar en la auditoría inmutable que el Agente de IA ejecutó la tarea
        AuditService(self.conn).log_action(
            business_id=business_id,
            actor="AI_AGENT",
            action="TAREA_EJECUTADA",
            target_resource=str(task_id),
            details={"status": "success"}
        )
        
        return {
            "success": True,
            "task_id": str(task_id),
            "status": "completed",
            "message": "Tarea ejecutada y completada con éxito de forma autónoma."
        }