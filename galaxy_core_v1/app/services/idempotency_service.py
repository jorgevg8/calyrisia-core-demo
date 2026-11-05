import json
from uuid import UUID

class IdempotencyError(Exception):
    pass

class IdempotencyService:
    def __init__(self, conn):
        self.conn = conn

    def check_and_record(self, business_id: UUID, idempotency_key: str, action_name: str, response_data: dict = None) -> dict:
        """Registra una acción. Si la llave ya existe, devuelve el resultado anterior para evitar duplicados."""
        response_data = response_data or {"msg": "Acción ejecutada exitosamente."}
        
        with self.conn.cursor() as cur:
            # 1. Buscamos si ya existe la llave en la base de datos
            cur.execute("""
                SELECT status, response_data 
                FROM idempotency_records 
                WHERE idempotency_key = %s AND business_id = %s
            """, (idempotency_key, str(business_id)))
            
            existing = cur.fetchone()
            
            if existing:
                # ¡ALERTA DE DUPLICADO! Devolvemos la caché y evitamos ejecutar de nuevo
                return {
                    "idempotency_key": idempotency_key,
                    "action_name": action_name,
                    "status": existing[0],
                    "response_data": existing[1] if isinstance(existing[1], dict) else json.loads(existing[1]),
                    "is_duplicate": True
                }
            
            # 2. ES NUEVA: La dejamos registrada para siempre
            cur.execute("""
                INSERT INTO idempotency_records (idempotency_key, business_id, action_name, status, response_data)
                VALUES (%s, %s, %s, 'executed', %s::jsonb)
            """, (idempotency_key, str(business_id), action_name, json.dumps(response_data)))
            
            self.conn.commit()
            
            return {
                "idempotency_key": idempotency_key,
                "action_name": action_name,
                "status": "executed",
                "response_data": response_data,
                "is_duplicate": False
            }