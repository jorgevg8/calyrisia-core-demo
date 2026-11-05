import json
from uuid import UUID, uuid4

class AutonomousWorkerService:
    def __init__(self, conn):
        self.conn = conn

    def process_events(self, business_id: UUID) -> dict:
        """Lee los eventos pendientes del bus y los convierte en tareas de la IA."""
        processed = 0
        tasks = 0
        
        with self.conn.cursor() as cur:
            # 1. Buscar todos los eventos en estado 'pending'
            cur.execute("""
                SELECT id, event_type, payload 
                FROM event_bus_queue 
                WHERE business_id = %s AND status = 'pending'
            """, (str(business_id),))
            
            events = cur.fetchall()
            
            for ev in events:
                event_id, event_type, payload = ev
                
                # 2. Generar una Tarea Autónoma para resolver ese evento
                task_id = str(uuid4())
                title = f"Resolver alerta automática: {event_type}"
                description = f"Datos detectados por el sistema: {json.dumps(payload)}"
                
                # Insertamos la tarea (Le ponemos riesgo medium por defecto)
                cur.execute("""
                    INSERT INTO autonomous_tasks (id, business_id, title, description, risk_level, requires_approval, status)
                    VALUES (%s, %s, %s, %s, 'medium', false, 'pending')
                """, (task_id, str(business_id), title, description))
                tasks += 1
                
                # 3. Marcar el evento como 'processed' para no volver a leerlo
                cur.execute("""
                    UPDATE event_bus_queue 
                    SET status = 'processed'
                    WHERE id = %s
                """, (event_id,))
                processed += 1
                
            self.conn.commit()
            
            return {
                "success": True,
                "processed_count": processed,
                "tasks_created": tasks
            }