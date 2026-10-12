import json
from uuid import UUID, uuid4

class JobRunnerError(Exception):
    pass

class JobRunnerService:
    def __init__(self, conn):
        self.conn = conn

    def create_job(self, business_id: UUID, task_id: UUID, execution_id: UUID, job_name: str, total_steps: int = 1, max_retries: int = 3) -> dict:
        """Crea un trabajo de larga duración asociado a una ejecución de tarea."""
        with self.conn.cursor() as cur:
            job_id = str(uuid4())
            cur.execute("""
                INSERT INTO long_running_jobs (id, business_id, task_id, execution_id, job_name, status, total_steps, max_retries)
                VALUES (%s, %s, %s, %s, %s, 'running', %s, %s)
                RETURNING id, job_name, status, current_checkpoint, total_steps, retry_count, state_data
            """, (job_id, str(business_id), str(task_id), str(execution_id), job_name, total_steps, max_retries))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]), "job_name": row[1], "status": row[2],
                "current_checkpoint": row[3], "total_steps": row[4],
                "retry_count": row[5], "state_data": row[6] if isinstance(row[6], dict) else json.loads(row[6])
            }

    def update_checkpoint(self, business_id: UUID, job_id: UUID, checkpoint: int, state_data: dict = None) -> dict:
        """Guarda el progreso (checkpoint) de un trabajo en curso."""
        state_data = state_data or {}
        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE long_running_jobs 
                SET current_checkpoint = %s, state_data = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s AND business_id = %s
                RETURNING id, job_name, status, current_checkpoint, total_steps, retry_count, state_data
            """, (checkpoint, json.dumps(state_data), str(job_id), str(business_id)))
            
            row = cur.fetchone()
            if not row:
                raise JobRunnerError("Job no encontrado en este negocio.")
                
            self.conn.commit()
            return {
                "id": str(row[0]), "job_name": row[1], "status": row[2],
                "current_checkpoint": row[3], "total_steps": row[4],
                "retry_count": row[5], "state_data": row[6] if isinstance(row[6], dict) else json.loads(row[6])
            }