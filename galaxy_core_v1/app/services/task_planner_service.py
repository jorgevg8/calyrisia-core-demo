import json
from uuid import UUID, uuid4

class TaskPlannerError(Exception):
    pass

class TaskPlannerService:
    def __init__(self, conn):
        self.conn = conn

    def create_task(self, business_id: UUID, title: str, description: str, risk_level: str) -> dict:
        """Crea una tarea autónoma. Si es de alto riesgo, fuerza la aprobación humana."""
        requires_approval = True if risk_level == "high" else False
        
        with self.conn.cursor() as cur:
            task_id = str(uuid4())
            cur.execute("""
                INSERT INTO autonomous_tasks (id, business_id, title, description, risk_level, requires_approval, status)
                VALUES (%s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id, title, description, risk_level, requires_approval, status
            """, (task_id, str(business_id), title, description, risk_level, requires_approval))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "business_id": str(business_id),
                "title": row[1],
                "description": row[2],
                "risk_level": row[3],
                "requires_approval": row[4],
                "status": row[5]
            }

    def create_plan(self, business_id: UUID, task_id: UUID, steps: list) -> dict:
        """Asigna un plan de ejecución a una tarea existente."""
        with self.conn.cursor() as cur:
            # Blindaje: Verificar que la tarea exista y pertenezca al negocio del usuario
            cur.execute("SELECT id FROM autonomous_tasks WHERE id = %s AND business_id = %s", (str(task_id), str(business_id)))
            if not cur.fetchone():
                raise TaskPlannerError("Tarea no encontrada o no pertenece a este negocio.")
                
            plan_id = str(uuid4())
            cur.execute("""
                INSERT INTO autonomous_plans (id, task_id, steps, status)
                VALUES (%s, %s, %s::jsonb, 'draft')
                RETURNING id, task_id, steps, status
            """, (plan_id, str(task_id), json.dumps(steps)))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "task_id": str(row[1]),
                "steps": row[2] if isinstance(row[2], list) else json.loads(row[2]),
                "status": row[3]
            }