from uuid import UUID, uuid4
from app.services.task_planner_service import TaskPlannerService
from app.services.audit_service import AuditService

class ProactiveLifecycleError(Exception):
    pass

class ProactiveLifecycleService:
    def __init__(self, conn):
        self.conn = conn

    def evaluate_and_schedule(self, business_id: UUID, customer_id: UUID, trigger_event: str, scheduled_for=None) -> dict:
        """Evalúa si es pertinente contactar al cliente proactivamente y programa una tarea si pasa el filtro anti-spam."""
        with self.conn.cursor() as cur:
            # 1. REGLA ANTI-SPAM: Revisar si ya se le contactó por este mismo motivo en los últimos 7 días
            cur.execute("""
                SELECT id FROM proactive_engagements 
                WHERE business_id = %s AND customer_id = %s AND trigger_event = %s
                AND created_at > CURRENT_TIMESTAMP - INTERVAL '7 days'
            """, (str(business_id), str(customer_id), trigger_event))
            
            if cur.fetchone():
                raise ProactiveLifecycleError(f"BLOQUEO ANTI-SPAM: El cliente ya tiene un evento '{trigger_event}' reciente.")

            # 2. ES SEGURO: Crear el registro del engagement
            eng_id = str(uuid4())
            # FIX APLICADO AQUÍ: 5 huecos (%s) para 5 variables
            cur.execute("""
                INSERT INTO proactive_engagements (id, business_id, customer_id, trigger_event, status)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id, status, scheduled_for
            """, (eng_id, str(business_id), str(customer_id), trigger_event, 'planned'))
            row = cur.fetchone()
            self.conn.commit()

        # 3. CONECTAMOS CON EL PASO 63: Le decimos a la IA que cree una tarea para ejecutar este plan
        try:
            planner = TaskPlannerService(self.conn)
            planner.create_task(
                business_id=business_id,
                title=f"Seguimiento Proactivo: {trigger_event}",
                description=f"Evaluar y contactar al cliente {str(customer_id)} por motivo: {trigger_event}.",
                risk_level="low"
            )
        except Exception as e:
            pass # Si falla la creación de tarea, igual mantenemos el registro del engagement

        # 4. Huella en auditoría
        AuditService(self.conn).log_action(business_id, "SYSTEM", "PROACTIVE_ENGAGEMENT_PLANNED", str(customer_id), {"trigger": trigger_event})

        # Retornamos convirtiendo los UUIDs a strings por si acaso (para evitar el error de Pydantic)
        return {
            "id": str(row[0]), 
            "customer_id": str(customer_id), 
            "trigger_event": trigger_event, 
            "status": row[1], 
            "scheduled_for": row[2]
        }