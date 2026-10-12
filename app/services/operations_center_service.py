from uuid import UUID

class OperationsCenterService:
    def __init__(self, conn):
        self.conn = conn

    def get_live_metrics(self, business_id: UUID) -> dict:
        """
        PASO 96: Operations Command Center.
        Agrega la telemetría de la IA para el dashboard del dueño con detección dinámica.
        """
        with self.conn.cursor() as cur:
            # 1. Tareas de IA pendientes de aprobación humana
            cur.execute("""
                SELECT COUNT(*) FROM permissions 
                WHERE business_id = %s AND requires_approval = TRUE
            """, (str(business_id),))
            pending_approvals = cur.fetchone()[0]

            # 2. Clientes activos en el CRM
            cur.execute("SELECT COUNT(*) FROM customers WHERE business_id = %s", (str(business_id),))
            total_customers = cur.fetchone()[0]

            # 3. Intervenciones de seguridad recientes (Detección dinámica de columna)
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'audit_logs' 
                AND column_name IN ('action', 'action_name', 'action_type', 'event_name', 'event')
                LIMIT 1
            """)
            col_row = cur.fetchone()
            blocked_actions = 0
            
            if col_row:
                col_name = col_row[0]
                # Ejecutamos la consulta con el nombre de columna exacto que tenga tu BD
                query = f"SELECT COUNT(*) FROM audit_logs WHERE business_id = %s AND {col_name} = 'ACTION_BLOCKED'"
                cur.execute(query, (str(business_id),))
                blocked_actions = cur.fetchone()[0]

            return {
                "system_status": "ONLINE_AND_AUTONOMOUS",
                "active_blueprints": 1,
                "metrics": {
                    "pending_human_approvals": pending_approvals,
                    "total_customers_managed": total_customers,
                    "security_blocks_last_24h": blocked_actions
                },
                "recommendation": "Revisar cola de aprobaciones." if pending_approvals > 0 else "Sistema operando en parámetros normales."
            }