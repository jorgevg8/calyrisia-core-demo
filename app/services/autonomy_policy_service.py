from uuid import UUID, uuid4

class AutonomyPolicyError(Exception):
    pass

class AutonomyPolicyService:
    def __init__(self, conn):
        self.conn = conn

    def upsert_policy(self, business_id: UUID, action_name: str, policy_mode: str, value_limit: float = None) -> dict:
        """Crea o actualiza una política de autonomía para una acción específica."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM autonomy_policies WHERE business_id = %s AND action_name = %s", (str(business_id), action_name))
            existing = cur.fetchone()
            
            if existing:
                cur.execute("""
                    UPDATE autonomy_policies 
                    SET policy_mode = %s, value_limit = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = %s AND action_name = %s
                    RETURNING id, action_name, policy_mode, value_limit
                """, (policy_mode, value_limit, str(business_id), action_name))
            else:
                policy_id = str(uuid4())
                cur.execute("""
                    INSERT INTO autonomy_policies (id, business_id, action_name, policy_mode, value_limit)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, action_name, policy_mode, value_limit
                """, (policy_id, str(business_id), action_name, policy_mode, value_limit))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "business_id": str(business_id),
                "action_name": row[1],
                "policy_mode": row[2],
                "value_limit": float(row[3]) if row[3] is not None else None
            }
            
    def list_policies(self, business_id: UUID) -> list:
        """Lista todas las políticas de autonomía configuradas para el negocio."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, action_name, policy_mode, value_limit 
                FROM autonomy_policies WHERE business_id = %s
            """, (str(business_id),))
            rows = cur.fetchall()
            return [
                {
                    "id": str(r[0]),
                    "business_id": str(business_id),
                    "action_name": r[1],
                    "policy_mode": r[2],
                    "value_limit": float(r[3]) if r[3] is not None else None
                } for r in rows
            ]