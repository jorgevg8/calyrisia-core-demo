from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class WorkflowRecoveryError(Exception):
    pass

class WorkflowRecoveryService:
    def __init__(self, conn):
        self.conn = conn

    def register_failure_and_recover(self, business_id: UUID, task_id: UUID, failure_reason: str, recovery_strategy: str, max_attempts: int = 3) -> dict:
        """Registra un fallo en un workflow y determina si se puede intentar recuperar."""
        with self.conn.cursor() as cur:
            # Verificar si ya existe un registro de recuperación activo para esta tarea
            cur.execute("""
                SELECT id, attempt_count, max_attempts FROM autonomous_recovery_logs
                WHERE task_id = %s AND business_id = %s
            """, (str(task_id), str(business_id)))
            
            existing = cur.fetchone()
            
            if existing:
                log_id, attempt_count, current_max = existing
                if attempt_count < current_max:
                    new_status = 'pending'
                    new_attempts = attempt_count + 1
                else:
                    new_status = 'failed' # Agotó sus intentos, muere definitivamente
                    new_attempts = attempt_count
                    
                cur.execute("""
                    UPDATE autonomous_recovery_logs
                    SET attempt_count = %s, status = %s, failure_reason = %s
                    WHERE id = %s
                    RETURNING id, task_id, status, attempt_count, recovery_strategy
                """, (new_attempts, new_status, failure_reason, log_id))
                row = cur.fetchone()
            else:
                log_id = str(uuid4())
                cur.execute("""
                    INSERT INTO autonomous_recovery_logs (id, business_id, task_id, failure_reason, recovery_strategy, attempt_count, max_attempts, status)
                    VALUES (%s, %s, %s, %s, %s, 1, %s, 'pending')
                    RETURNING id, task_id, status, attempt_count, recovery_strategy
                """, (log_id, str(business_id), str(task_id), failure_reason, recovery_strategy, max_attempts))
                row = cur.fetchone()
            
            # Dejamos constancia en la Auditoría si estamos reintentando o si ya murió
            action_log = "RECOVERY_ATTEMPT" if row[2] == 'pending' else "RECOVERY_FAILED"
            AuditService(self.conn).log_action(
                business_id, "SYSTEM_RECOVERY", action_log, str(task_id), 
                {"reason": failure_reason, "attempts": row[3]}
            )
            
            self.conn.commit()

            return {
                "id": str(row[0]),
                "task_id": str(row[1]),
                "status": row[2],
                "attempt_count": row[3],
                "recovery_strategy": row[4]
            }