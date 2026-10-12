import json
from uuid import UUID, uuid4
from app.services.audit_service import AuditService

class MultiAgentOrchestrator:
    def __init__(self, conn):
        self.conn = conn
        self.available_agents = ["sales_agent", "support_agent", "inventory_agent"]

    def route_task(self, business_id: UUID, task_description: str, payload: dict) -> dict:
        """El orquestador analiza la tarea y se la delega al Agente IA especializado correcto."""
        
        desc_lower = task_description.lower()
        
        # Lógica de ruteo del Jefe (Orquestador)
        if "venta" in desc_lower or "precio" in desc_lower or "cotizaci" in desc_lower or "descuento" in desc_lower:
            assigned_agent = "sales_agent"
        elif "inventario" in desc_lower or "stock" in desc_lower or "producto" in desc_lower or "almacén" in desc_lower:
            assigned_agent = "inventory_agent"
        else:
            assigned_agent = "support_agent"

        with self.conn.cursor() as cur:
            delegation_id = str(uuid4())
            
            # Registrar la delegación en la tabla
            cur.execute("""
                INSERT INTO agent_delegations (id, business_id, task_description, assigned_agent, payload, status)
                VALUES (%s, %s, %s, %s, %s::jsonb, 'assigned')
                RETURNING id, assigned_agent, task_description, status
            """, (delegation_id, str(business_id), task_description, assigned_agent, json.dumps(payload)))
            
            row = cur.fetchone()
            
            # Dejar constancia en la auditoría de que el Orquestador movió los hilos
            AuditService(self.conn).log_action(
                business_id, "SYSTEM_ORCHESTRATOR", "TASK_DELEGATED", delegation_id, 
                {"agent": assigned_agent, "task": task_description}
            )
            
            self.conn.commit()

            return {
                "id": str(row[0]),
                "assigned_agent": row[1],
                "task_description": row[2],
                "status": row[3]
            }