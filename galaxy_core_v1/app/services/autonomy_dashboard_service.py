from uuid import UUID

class AutonomyDashboardService:
    def __init__(self, conn):
        self.conn = conn

    def get_system_status(self, business_id: UUID) -> dict:
        """Obtiene una radiografía completa del sistema autónomo para el Dashboard."""
        with self.conn.cursor() as cur:
            # Contar eventos pendientes
            cur.execute("SELECT COUNT(*) FROM event_bus_queue WHERE business_id = %s AND status = 'pending'", (str(business_id),))
            pending_events = cur.fetchone()[0]
            
            # Contar tareas pendientes
            cur.execute("SELECT COUNT(*) FROM autonomous_tasks WHERE business_id = %s AND status = 'pending'", (str(business_id),))
            pending_tasks = cur.fetchone()[0]
            
            # Contar políticas configuradas
            cur.execute("SELECT COUNT(*) FROM autonomy_policies WHERE business_id = %s", (str(business_id),))
            active_policies = cur.fetchone()[0]
            
            # Contar metas activas
            cur.execute("SELECT COUNT(*) FROM business_goals WHERE business_id = %s AND status = 'active'", (str(business_id),))
            active_goals = cur.fetchone()[0]
            
            return {
                "success": True,
                "business_id": str(business_id),
                "pending_events": int(pending_events),
                "pending_tasks": int(pending_tasks),
                "active_policies": int(active_policies),
                "active_goals": int(active_goals)
            }