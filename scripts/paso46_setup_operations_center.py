from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db import close_pool, get_connection, open_pool

MIGRATION = ROOT / "migration_paso_46_operations_center_v2.sql"


def quote_ident(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


async def main() -> None:
    print("=" * 72)
    print("GALAXY PASO 46 — OPERATIONS CENTER SETUP")
    print("=" * 72)
    sql = MIGRATION.read_text(encoding="utf-8")
    statements = [part.strip() for part in sql.split(";") if part.strip()]
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)

                cur.execute(
                    """
                    SELECT c.conname, pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE t.relname = 'approvals' AND c.contype = 'c'
                      AND pg_get_constraintdef(c.oid) ILIKE '%status%'
                    """
                )
                constraints = cur.fetchall()
                for conname, definition in constraints:
                    literals = set(re.findall(r"'([^']+)'", definition or ""))
                    required = {"pending", "approved", "rejected", "expired"}
                    if not required.issubset(literals):
                        merged = sorted(literals | required)
                        cur.execute(f"ALTER TABLE approvals DROP CONSTRAINT {quote_ident(conname)}")
                        values_sql = ", ".join("'" + value.replace("'", "''") + "'" for value in merged)
                        cur.execute(
                            f"ALTER TABLE approvals ADD CONSTRAINT approvals_status_check_v46 CHECK (status IN ({values_sql}))"
                        )

                # Some installations may restrict audit action_type values. Keep the
                # existing values and widen the check for the Operations Center events.
                cur.execute(
                    """
                    SELECT c.conname, pg_get_constraintdef(c.oid)
                    FROM pg_constraint c
                    JOIN pg_class t ON t.oid = c.conrelid
                    WHERE t.relname = 'audit_logs' AND c.contype = 'c'
                      AND pg_get_constraintdef(c.oid) ILIKE '%action_type%'
                    """
                )
                audit_constraints = cur.fetchall()
                required_audit = {
                    'approval_decision', 'approval_execution_failed', 'approval_retry',
                    'approval_expired', 'human_handoff_acknowledged', 'human_handoff_resolved'
                }
                for conname, definition in audit_constraints:
                    literals = set(re.findall(r"'([^']+)'", definition or ""))
                    if literals and not required_audit.issubset(literals):
                        merged = sorted(literals | required_audit)
                        cur.execute(f"ALTER TABLE audit_logs DROP CONSTRAINT {quote_ident(conname)}")
                        values_sql = ", ".join("'" + value.replace("'", "''") + "'" for value in merged)
                        cur.execute(
                            f"ALTER TABLE audit_logs ADD CONSTRAINT audit_action_type_check_v46 CHECK (action_type IN ({values_sql}))"
                        )
            conn.commit()
            print("[PASS] Columnas del Operations Center listas")
            print("[PASS] Expiración y metadata de decisión listas")
            print("[PASS] Restricción de approvals acepta pending/approved/rejected/expired")
            print("[PASS] Índices de approvals listos")
    finally:
        close_pool()
    print("=" * 72)
    print("PASO 46 — SETUP: PASSED")
    print("=" * 72)


if __name__ == "__main__":
    asyncio.run(main())
