import asyncio
from app.db import get_connection
from app.services.autonomous_worker_service import AutonomousWorkerService

class HeartbeatService:
    @staticmethod
    async def run_loop():
        """Bucle infinito que despierta a Galaxy cada 15 segundos con aislamiento transaccional."""
        while True:
            await asyncio.sleep(15)
            
            try:
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT id FROM businesses WHERE status = 'active'")
                        businesses = cur.fetchall()
                        
                    for (b_id,) in businesses:
                        try:
                            worker = AutonomousWorkerService(conn)
                            resultado = worker.process_events(b_id)
                            if resultado.get("processed_count", 0) > 0:
                                print(f"⚡ [HEARTBEAT] Negocio {b_id}: {resultado['processed_count']} eventos procesados.")
                        except Exception as e:
                            conn.rollback()
            except Exception as e:
                pass
