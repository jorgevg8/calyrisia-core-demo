import json
from uuid import UUID, uuid4

class AgentBlueprintError(Exception):
    pass

class AgentBlueprintService:
    def __init__(self, conn):
        self.conn = conn

    def upsert_blueprint(self, business_id: UUID, name: str, objective: str, capabilities: list) -> dict:
        """Crea o actualiza el Blueprint del Agente para un negocio específico."""
        with self.conn.cursor() as cur:
            cur.execute("SELECT id FROM agent_blueprints WHERE business_id = %s", (str(business_id),))
            existing = cur.fetchone()
            
            # Convertimos la lista a un string JSON
            caps_json = json.dumps(capabilities)
            
            if existing:
                # Agregamos ::jsonb para que Postgres lo entienda correctamente
                cur.execute("""
                    UPDATE agent_blueprints 
                    SET agent_name = %s, core_objective = %s, capabilities = %s::jsonb, updated_at = CURRENT_TIMESTAMP
                    WHERE business_id = %s
                    RETURNING id, agent_name, core_objective, capabilities, status
                """, (name, objective, caps_json, str(business_id)))
            else:
                blueprint_id = str(uuid4())
                # Agregamos ::jsonb aquí también
                cur.execute("""
                    INSERT INTO agent_blueprints (id, business_id, agent_name, core_objective, capabilities, status)
                    VALUES (%s, %s, %s, %s, %s::jsonb, 'active')
                    RETURNING id, agent_name, core_objective, capabilities, status
                """, (blueprint_id, str(business_id), name, objective, caps_json))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "blueprint_id": str(row[0]),
                "business_id": str(business_id),
                "agent_name": row[1],
                "core_objective": row[2],
                "capabilities": row[3],
                "status": row[4]
            }

    def get_blueprint(self, business_id: UUID) -> dict:
        """Obtiene el Blueprint activo de un negocio."""
        with self.conn.cursor() as cur:
            cur.execute("""
                SELECT id, agent_name, core_objective, capabilities, status 
                FROM agent_blueprints WHERE business_id = %s
            """, (str(business_id),))
            row = cur.fetchone()
            
            if not row:
                raise AgentBlueprintError("No se encontró un Blueprint para este negocio.")
                
            return {
                "blueprint_id": str(row[0]),
                "business_id": str(business_id),
                "agent_name": row[1],
                "core_objective": row[2],
                "capabilities": row[3] if isinstance(row[3], list) else json.loads(row[3]),
                "status": row[4]
            }