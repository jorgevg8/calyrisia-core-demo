from uuid import UUID, uuid4

class AgentRuntimeError(Exception):
    pass

class AgentRuntimeService:
    def __init__(self, conn):
        self.conn = conn

    def start_execution(self, business_id: UUID, task_id: UUID, actor: str = "SYSTEM") -> dict:
        """Inicia una ejecución de tarea y la marca como 'running'."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT status, requires_approval FROM autonomous_tasks WHERE id = %s AND business_id = %s", (str(task_id), str(business_id)))
            task = cur.fetchone()
            if not task:
                raise AgentRuntimeError("Tarea no encontrada.")
            
            if task[1] and task[0] == 'pending':
                raise AgentRuntimeError("OPERACIÓN BLOQUEADA: La tarea requiere aprobación previa del Owner.")

            exec_id = str(uuid4())
            cur.execute("""
                INSERT INTO agent_executions (id, business_id, task_id, actor, status, started_at)
                VALUES (%s, %s, %s, %s, 'running', CURRENT_TIMESTAMP)
                RETURNING id, status, started_at
            """, (exec_id, str(business_id), str(task_id), actor))
            
            row = cur.fetchone()
            
            cur.execute("UPDATE autonomous_tasks SET status = 'in_progress' WHERE id = %s", (str(task_id),))
            self.conn.commit()
            
            # EL FIX: Convertimos row[0] explícitamente a string
            return {"id": str(row[0]), "status": row[1], "started_at": row[2]}

    def complete_execution(self, business_id: UUID, exec_id: UUID, success: bool, error_message: str = None) -> dict:
        """Finaliza una ejecución y actualiza la tarea padre."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT task_id, status FROM agent_executions WHERE id = %s AND business_id = %s", (str(exec_id), str(business_id)))
            execution = cur.fetchone()
            if not execution:
                raise AgentRuntimeError("Ejecución no encontrada.")
            
            if execution[1] in ['succeeded', 'failed', 'cancelled']:
                raise AgentRuntimeError(f"La ejecución ya finalizó con estado: {execution[1]}")

            final_status = 'succeeded' if success else 'failed'
            task_status = 'completed' if success else 'failed'
            
            cur.execute("""
                UPDATE agent_executions 
                SET status = %s, error_message = %s, completed_at = CURRENT_TIMESTAMP
                WHERE id = %s
                RETURNING id, status, completed_at
            """, (final_status, error_message, str(exec_id)))
            
            row = cur.fetchone()
            
            cur.execute("UPDATE autonomous_tasks SET status = %s WHERE id = %s", (task_status, str(execution[0])))
            self.conn.commit()
            
            # EL FIX: Convertimos row[0] explícitamente a string
            return {"id": str(row[0]), "status": row[1], "completed_at": row[2]}