from uuid import UUID, uuid4

class LLMCostService:
    def __init__(self, conn):
        self.conn = conn
        # Precios oficiales de Gemini por 1 Millón de tokens (Flash y Pro)
        self.pricing = {
            "gemini-1.5-flash": {"prompt": 0.075 / 1000000, "completion": 0.30 / 1000000},
            "gemini-1.5-pro": {"prompt": 3.50 / 1000000, "completion": 10.50 / 1000000}
        }

    def log_usage(self, business_id: UUID, model_name: str, prompt_tokens: int, completion_tokens: int, feature_used: str) -> dict:
        """Calcula el costo en dólares y guarda el registro de consumo de IA."""
        # Obtener precios del modelo o cobrar a $0 si es un modelo no registrado
        prices = self.pricing.get(model_name, {"prompt": 0.0, "completion": 0.0})
        
        # Fórmula: (Tokens Entrada * Costo Entrada) + (Tokens Salida * Costo Salida)
        cost = (prompt_tokens * prices["prompt"]) + (completion_tokens * prices["completion"])

        with self.conn.cursor() as cur:
            log_id = str(uuid4())
            cur.execute("""
                INSERT INTO llm_usage_logs (id, business_id, model_name, prompt_tokens, completion_tokens, total_cost, feature_used)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, model_name, (prompt_tokens + completion_tokens), total_cost, feature_used
            """, (log_id, str(business_id), model_name, prompt_tokens, completion_tokens, cost, feature_used))
            
            row = cur.fetchone()
            self.conn.commit()

            return {
                "id": str(row[0]),
                "model_name": row[1],
                "total_tokens": int(row[2]),
                "total_cost": float(row[3]),
                "feature_used": row[4]
            }