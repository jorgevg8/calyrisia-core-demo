import asyncio

from app.db import pool
from app.services.autonomous_worker_service import AutonomousWorkerService


class HeartbeatService:
    @staticmethod
    def _run_once_sync() -> None:
        """Run one database tick in a worker thread so DB delays do not freeze FastAPI."""
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM businesses WHERE status = 'active'")
                businesses = cur.fetchall()

            for (business_id,) in businesses:
                try:
                    worker = AutonomousWorkerService(conn)
                    result = worker.process_events(business_id)
                    if result.get("processed_count", 0) > 0:
                        print(
                            f"[HEARTBEAT] Negocio {business_id}: "
                            f"{result['processed_count']} eventos procesados."
                        )
                except Exception as exc:
                    conn.rollback()
                    print(f"[HEARTBEAT][WARN] Negocio {business_id}: {exc}")

    @staticmethod
    async def run_loop() -> None:
        """Wake every 15 seconds without blocking API health checks on PostgreSQL."""
        while True:
            await asyncio.sleep(15)
            try:
                await asyncio.to_thread(HeartbeatService._run_once_sync)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                print(f"[HEARTBEAT][WARN] No se pudo ejecutar el ciclo: {exc}")
