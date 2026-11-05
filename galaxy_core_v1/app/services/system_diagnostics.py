from __future__ import annotations

from typing import Any

from app.core.config import get_settings


REQUIRED_TABLES = (
    "businesses",
    "customers",
    "conversations",
    "conversation_messages",
    "appointments",
    "orders",
    "order_items",
    "products",
    "inventory",
    "events",
    "business_rules",
    "business_profiles",
    "permissions",
    "actions",
    "approvals",
    "memory",
    "audit_logs",
    "business_insights",
    "recommendations",
)


class DiagnosticsService:
    def __init__(self, conn):
        self.conn = conn
        self.settings = get_settings()

    def readiness(self) -> dict[str, Any]:
        checks: dict[str, Any] = {}
        overall_ok = True

        db_ok, db_detail = self._check_database()
        checks["database"] = {"ok": db_ok, **db_detail}
        overall_ok = overall_ok and db_ok

        tables_ok, missing_tables = self._check_required_tables()
        checks["required_tables"] = {
            "ok": tables_ok,
            "missing": missing_tables,
            "count_expected": len(REQUIRED_TABLES),
        }
        overall_ok = overall_ok and tables_ok

        gemini_configured = bool(self.settings.gemini_api_key.strip())
        checks["gemini_configuration"] = {
            "ok": gemini_configured,
            "configured": gemini_configured,
            "model": self.settings.gemini_model,
        }
        overall_ok = overall_ok and gemini_configured
        # We do not make a network call to Gemini during readiness. This avoids
        # turning a health check into an external-provider dependency.

        return {
            "status": "ready" if overall_ok else "not_ready",
            "service": "galaxy-core",
            "version": "1.1.0",
            "checks": checks,
        }

    def diagnostics(self) -> dict[str, Any]:
        db_ok, db_detail = self._check_database()
        tables_ok, missing_tables = self._check_required_tables()

        tool_registry_ok = False
        tool_count = 0
        try:
            from app.services.tool_registry import list_tools

            tools = list_tools()
            tool_count = len(tools)
            tool_registry_ok = tool_count > 0
        except Exception:
            tool_registry_ok = False

        gemini_configured = bool(self.settings.gemini_api_key.strip())

        status = "healthy"
        if not db_ok or not tables_ok or not tool_registry_ok:
            status = "degraded"

        return {
            "status": status,
            "service": "galaxy-core",
            "version": "1.1.0",
            "environment": self.settings.app_env,
            "database": {
                "ok": db_ok,
                **db_detail,
            },
            "schema": {
                "ok": tables_ok,
                "missing_tables": missing_tables,
                "required_table_count": len(REQUIRED_TABLES),
            },
            "gemini": {
                "configured": gemini_configured,
                "model": self.settings.gemini_model,
                "api_key_exposed": False,
            },
            "tool_registry": {
                "ok": tool_registry_ok,
                "tool_count": tool_count,
            },
            "components": {
                "galaxy_core": True,
                "context_manager": True,
                "memory": True,
                "tool_manager": True,
                "permission_system": True,
                "event_engine": True,
                "galaxy_brain": True,
                "business_brain": True,
                "recommendation_engine": True,
                "autopilot": True,
                "audit_log": True,
            },
        }

    def _check_database(self) -> tuple[bool, dict[str, Any]]:
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT current_database(), current_user")
                database, user = cur.fetchone()
            return True, {"database": database, "user": user}
        except Exception as exc:
            self.conn.rollback()
            return False, {"error": str(exc)}

    def _check_required_tables(self) -> tuple[bool, list[str]]:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_name
                    FROM information_schema.tables
                    WHERE table_schema = 'public'
                      AND table_name = ANY(%s)
                    """,
                    (list(REQUIRED_TABLES),),
                )
                existing = {row[0] for row in cur.fetchall()}
            missing = [name for name in REQUIRED_TABLES if name not in existing]
            return len(missing) == 0, missing
        except Exception:
            self.conn.rollback()
            return False, list(REQUIRED_TABLES)
