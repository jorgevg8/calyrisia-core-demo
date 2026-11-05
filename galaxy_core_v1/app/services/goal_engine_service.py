from uuid import UUID, uuid4

class GoalEngineError(Exception):
    pass

class GoalEngineService:
    def __init__(self, conn):
        self.conn = conn

    def create_goal(self, business_id: UUID, name: str, metric_name: str, target_value: float) -> dict:
        """Crea una nueva meta medible para el negocio."""
        with self.conn.cursor() as cur:
            goal_id = str(uuid4())
            cur.execute("""
                INSERT INTO business_goals (id, business_id, name, metric_name, target_value, current_value, status)
                VALUES (%s, %s, %s, %s, %s, 0, 'active')
                RETURNING id, name, metric_name, target_value, current_value, status
            """, (goal_id, str(business_id), name, metric_name, target_value))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "business_id": str(business_id),
                "name": row[1],
                "metric_name": row[2],
                "target_value": float(row[3]),
                "current_value": float(row[4]),
                "status": row[5]
            }

    def list_goals(self, business_id: UUID) -> list:
        """Lista todas las metas activas del negocio."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, name, metric_name, target_value, current_value, status
                FROM business_goals
                WHERE business_id = %s ORDER BY created_at DESC
            """, (str(business_id),))
            rows = cur.fetchall()
            
            return [
                {
                    "id": str(r[0]),
                    "business_id": str(business_id),
                    "name": r[1],
                    "metric_name": r[2],
                    "target_value": float(r[3]),
                    "current_value": float(r[4]),
                    "status": r[5]
                } for r in rows
            ]