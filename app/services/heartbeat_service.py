import asyncio
from app.db import get_connection
from app.services.autonomous_worker_service import AutonomousWorkerService

class HeartbeatService:
    @staticmethod
    async def run_loop():
        """Bucle infinito que despierta a Galaxy cada 15 segundos."""
        while True:
            await asyncio.sleep(15)  # Espera 15 segundos
            
            try:
                # Abrimos conexión a la base de datos de forma silenciosa
                async with get_connection() as conn:
                    with conn.cursor() as cur:
                        # Buscamos todos los negocios activos en tu plataforma
                        cur.execute("SELECT id FROM businesses WHERE status = 'active'")
                        businesses = cur.fetchall()
                        
                    # Ponemos a trabajar a la IA por cada negocio de forma aislada
                    for (b_id,) in businesses:
                        try:
                            worker = AutonomousWorkerService(conn)
                            resultado = worker.process_events(b_id)
                            
                            if resultado["processed_count"] > 0:
                                print(f"⚡ [GALAXY HEARTBEAT] Negocio {b_id}: Procesó {resultado['processed_count']} eventos y creó {resultado['tasks_created']} tareas nuevas.")
                        except Exception as e:
                            print(f"⚠️ Error en Heartbeat para negocio {b_id}: {e}")
            except Exception as e:
                print(f"⚠️ Error global del Heartbeat: {e}")