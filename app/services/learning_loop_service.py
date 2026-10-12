from uuid import UUID, uuid4
from app.services.memory_service import MemoryService

class LearningLoopError(Exception):
    pass

class LearningLoopService:
    def __init__(self, conn):
        self.conn = conn

    def register_learning(self, business_id: UUID, action_taken: str, reasoning: str, outcome: str, learning_signal: str) -> dict:
        """Registra el resultado de una acción y extrae una señal de aprendizaje para el futuro."""
        
        with self.conn.cursor() as cur:
            loop_id = str(uuid4())
            
            # 1. Guardar en la bitácora de evolución
            cur.execute("""
                INSERT INTO autonomous_learning_loops (id, business_id, action_taken, reasoning, outcome, learning_signal)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, action_taken, outcome, learning_signal
            """, (loop_id, str(business_id), action_taken, reasoning, outcome, learning_signal))
            
            row = cur.fetchone()
            
            # 2. MAGIA: Inyectarlo en la Memoria del Negocio (Contexto a Largo Plazo)
            try:
                MemoryService(self.conn).create_memory(
                    business_id=business_id,
                    customer_id=None,
                    user_id=None,
                    memory_type="business_learning",
                    memory_key=f"learning_{outcome}_{loop_id[:8]}",
                    content=f"ACCION: {action_taken} | RESULTADO: {outcome.upper()} | APRENDIZAJE: {learning_signal}",
                    source="adaptive_loop",
                    importance=0.9 # Alta importancia porque es una regla aprendida por experiencia
                )
            except Exception as e:
                print(f"Nota: No se pudo anclar a memoria: {e}")
            
            self.conn.commit()

            return {
                "id": str(row[0]),
                "action_taken": row[1],
                "outcome": row[2],
                "learning_signal": row[3]
            }