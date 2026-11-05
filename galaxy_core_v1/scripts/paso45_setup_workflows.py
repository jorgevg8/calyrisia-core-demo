from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

MIGRATION = ROOT / "migration_paso_45_workflow_engine_v2.sql"


async def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 45 — WORKFLOW ENGINE V2 SETUP")
    print("=" * 72)
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(MIGRATION.read_text(encoding="utf-8"))
            conn.commit()
        print("[PASS] Tabla workflow_definitions lista")
        print("[PASS] Tabla workflow_runs lista")
        print("[PASS] Tabla workflow_steps lista")
        print("[PASS] Índices de tenant, trigger e idempotencia listos")
    finally:
        close_pool()
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
