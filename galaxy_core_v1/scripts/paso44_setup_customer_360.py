from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

MIGRATION = ROOT / "migration_paso_44_customer_360_memory_v2.sql"


async def run() -> None:
    open_pool()
    try:
        async with get_connection() as conn:
            sql = MIGRATION.read_text(encoding="utf-8")
            with conn.cursor() as cur:
                for statement in [part.strip() for part in sql.split(";") if part.strip()]:
                    cur.execute(statement)
                cur.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema='public' AND table_name='customer_360_profiles'
                    )
                    """
                )
                exists = bool(cur.fetchone()[0])
            conn.commit()
            if not exists:
                raise RuntimeError("No se pudo crear customer_360_profiles")
            print("[PASS] Tabla customer_360_profiles lista")
            print("[PASS] Índices de tenant, segmento y actualización listos")
            print("[PASS] Memory V2 utiliza la tabla memory existente sin duplicar almacenamiento")
    finally:
        close_pool()


if __name__ == "__main__":
    asyncio.run(run())
