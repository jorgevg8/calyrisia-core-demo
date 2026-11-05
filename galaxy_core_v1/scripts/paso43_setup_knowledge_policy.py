from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

MIGRATION = ROOT / "migration_paso_43_knowledge_policy.sql"


async def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 43 — KNOWLEDGE & POLICY CENTER SETUP")
    print("=" * 72)
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(MIGRATION.read_text(encoding="utf-8"))
            conn.commit()
        print("[PASS] Tabla business_knowledge_items lista")
        print("[PASS] Índices de tenant y tipo listos")
        print("[INFO] No se modificaron negocios ni contenido existente.")
    finally:
        close_pool()
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
