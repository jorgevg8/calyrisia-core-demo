from __future__ import annotations

import json
import re
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

try:
    import psycopg
except Exception:  # pragma: no cover
    psycopg = None  # type: ignore

try:
    from psycopg_pool import ConnectionPool
    _HAS_POOL = True
except Exception:  # pragma: no cover
    _HAS_POOL = False

    class ConnectionPool:  # type: ignore
        def __init__(self, *args, **kwargs):
            self.closed = True

        def open(self, *args, **kwargs):
            self.closed = False

        def close(self, *args, **kwargs):
            self.closed = True

from app.core.config import get_settings

settings = get_settings()

_pool_kwargs: dict[str, Any] = {
    **settings.database_kwargs,
    "connect_timeout": 8,
    "prepare_threshold": None,
}

pool = ConnectionPool(
    conninfo="",
    min_size=0,
    max_size=10,
    timeout=10,
    kwargs=_pool_kwargs,
    open=False,
)


def open_pool() -> None:
    """Start the connection pool without blocking API startup on PostgreSQL."""
    if _HAS_POOL and getattr(pool, "closed", True):
        try:
            pool.open(wait=False)
        except Exception:
            pass


def close_pool() -> None:
    """Close the pool only if it is currently open."""
    if _HAS_POOL and not getattr(pool, "closed", True):
        try:
            pool.close()
        except Exception:
            pass


_LOCAL_DB_PATH = Path(tempfile.gettempdir()) / "calyrisia_local_fallback.db"

_SQLITE_UUID_DEFAULT = (
    "(lower(hex(randomblob(4))) || '-' || lower(hex(randomblob(2))) || '-4' || "
    "substr(lower(hex(randomblob(2))),2) || '-' || "
    "substr('89ab',abs(random()) % 4 + 1, 1) || substr(lower(hex(randomblob(2))),2) || '-' || "
    "lower(hex(randomblob(6))))"
)


def _init_local_sqlite(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.executescript(
        f"""
        CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            name TEXT NOT NULL,
            legal_name TEXT,
            business_type TEXT NOT NULL DEFAULT 'tech_store',
            description TEXT,
            phone TEXT,
            email TEXT,
            website TEXT,
            timezone TEXT NOT NULL DEFAULT 'America/Caracas',
            currency TEXT NOT NULL DEFAULT 'USD',
            status TEXT NOT NULL DEFAULT 'active',
            plan_code TEXT NOT NULL DEFAULT 'free',
            webchat_enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            full_name TEXT NOT NULL DEFAULT 'Propietario',
            email TEXT NOT NULL,
            phone TEXT,
            role TEXT NOT NULL DEFAULT 'OWNER',
            status TEXT NOT NULL DEFAULT 'active',
            password_hash TEXT,
            last_login_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_profiles (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            industry TEXT,
            short_description TEXT,
            legal_name TEXT,
            address TEXT,
            city TEXT,
            state_province TEXT,
            country TEXT,
            postal_code TEXT,
            operating_hours TEXT DEFAULT '{{}}',
            policies TEXT DEFAULT '{{}}',
            processes TEXT DEFAULT '{{}}',
            objectives TEXT DEFAULT '[]',
            autonomy_config TEXT DEFAULT '{{}}',
            communication_config TEXT DEFAULT '{{}}',
            social_links TEXT DEFAULT '{{}}',
            additional_settings TEXT DEFAULT '{{}}',
            profile_version INTEGER DEFAULT 1,
            status TEXT DEFAULT 'active',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_knowledge_items (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            item_type TEXT NOT NULL DEFAULT 'policy',
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            visibility TEXT NOT NULL DEFAULT 'both',
            priority INTEGER NOT NULL DEFAULT 50,
            source TEXT,
            metadata TEXT DEFAULT '{{}}',
            status TEXT NOT NULL DEFAULT 'active',
            created_by TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS products (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            sku TEXT,
            brand TEXT,
            category TEXT DEFAULT 'General',
            price REAL NOT NULL DEFAULT 0,
            cost_price REAL,
            currency TEXT DEFAULT 'USD',
            variants TEXT DEFAULT '[]',
            attributes TEXT DEFAULT '{{}}',
            status TEXT NOT NULL DEFAULT 'active',
            is_active INTEGER NOT NULL DEFAULT 1,
            is_service INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS inventory (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            quantity REAL NOT NULL DEFAULT 0,
            minimum_quantity REAL NOT NULL DEFAULT 0,
            location TEXT DEFAULT 'tienda',
            last_counted_at TEXT,
            last_count_method TEXT,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS customers (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            email TEXT,
            phone TEXT,
            status TEXT DEFAULT 'active',
            source TEXT DEFAULT 'webchat',
            channel TEXT DEFAULT 'webchat',
            metadata TEXT DEFAULT '{{}}',
            first_contact_at TEXT DEFAULT (datetime('now')),
            last_interaction_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            customer_id TEXT,
            channel TEXT DEFAULT 'webchat',
            status TEXT DEFAULT 'active',
            intent TEXT,
            topic TEXT,
            outcome TEXT,
            handoff_to_human INTEGER DEFAULT 0,
            transfer_reason TEXT,
            started_at TEXT DEFAULT (datetime('now')),
            last_message_at TEXT DEFAULT (datetime('now')),
            closed_at TEXT,
            metadata TEXT DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS conversation_messages (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            conversation_id TEXT NOT NULL,
            customer_id TEXT,
            sender_type TEXT DEFAULT 'customer',
            direction TEXT DEFAULT 'inbound',
            message_type TEXT DEFAULT 'text',
            content TEXT,
            intent TEXT,
            sentiment TEXT,
            tool_used TEXT,
            action_taken TEXT,
            metadata TEXT DEFAULT '{{}}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS omnichannel_messages (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            customer_id TEXT,
            conversation_id TEXT,
            channel TEXT NOT NULL,
            direction TEXT NOT NULL,
            message_content TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'delivered',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS orders (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            customer_id TEXT,
            order_number TEXT,
            status TEXT DEFAULT 'pending',
            payment_status TEXT DEFAULT 'pending',
            subtotal REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            source TEXT DEFAULT 'webchat',
            notes TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS order_items (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            order_id TEXT NOT NULL,
            product_id TEXT,
            product_name TEXT,
            quantity REAL DEFAULT 1,
            unit_price REAL DEFAULT 0,
            discount_amount REAL DEFAULT 0,
            tax_amount REAL DEFAULT 0,
            line_total REAL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS agent_blueprints (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            core_objective TEXT,
            capabilities TEXT DEFAULT '[]',
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS autonomy_policies (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            action_name TEXT NOT NULL,
            policy_mode TEXT NOT NULL,
            value_limit REAL DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_goals (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            target_value REAL NOT NULL DEFAULT 0,
            current_value REAL DEFAULT 0,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            event_id TEXT,
            action_id TEXT,
            actor_type TEXT DEFAULT 'system',
            actor_user_id TEXT,
            action_type TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            status TEXT DEFAULT 'success',
            tool_name TEXT,
            reason TEXT,
            before_data TEXT DEFAULT '{{}}',
            after_data TEXT DEFAULT '{{}}',
            metadata TEXT DEFAULT '{{}}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS permissions (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            name TEXT,
            description TEXT,
            subject_type TEXT DEFAULT 'system',
            role TEXT,
            user_id TEXT,
            resource_type TEXT,
            action_type TEXT,
            effect TEXT DEFAULT 'allow',
            requires_approval INTEGER DEFAULT 0,
            priority INTEGER DEFAULT 100,
            enabled INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS actions (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            action_type TEXT,
            resource_type TEXT,
            tool_name TEXT,
            autonomy_level TEXT DEFAULT 'L1',
            risk_level TEXT DEFAULT 'low',
            status TEXT DEFAULT 'completed',
            input_data TEXT DEFAULT '{{}}',
            output_data TEXT DEFAULT '{{}}',
            reason TEXT,
            requested_at TEXT DEFAULT (datetime('now')),
            started_at TEXT,
            completed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS approvals (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            action_id TEXT,
            status TEXT DEFAULT 'pending',
            reason TEXT,
            requested_at TEXT DEFAULT (datetime('now')),
            reviewed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS business_ai_usage_monthly (
            business_id TEXT NOT NULL,
            month_start TEXT NOT NULL,
            response_count INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (business_id, month_start)
        );
        CREATE TABLE IF NOT EXISTS llm_usage_logs (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            model_name TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            estimated_cost_usd REAL DEFAULT 0,
            feature_used TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS calyrisia_sales_leads (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            customer_id TEXT,
            conversation_id TEXT,
            contact_name TEXT NOT NULL,
            phone TEXT,
            email TEXT,
            source_channel TEXT DEFAULT 'webchat',
            interest_summary TEXT,
            expected_value REAL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            stage TEXT DEFAULT 'new',
            consent_status TEXT DEFAULT 'unknown',
            follow_up_due_at TEXT,
            last_interaction_at TEXT DEFAULT (datetime('now')),
            notes TEXT,
            metadata TEXT DEFAULT '{{}}',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS calyrisia_lead_activities (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            lead_id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            activity_type TEXT NOT NULL,
            summary TEXT NOT NULL,
            actor_user_id TEXT,
            metadata TEXT DEFAULT '{{}}',
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS calyrisia_radar_reviews (
            business_id TEXT NOT NULL,
            signal_key TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'open',
            snoozed_until TEXT,
            note TEXT,
            updated_by TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (business_id, signal_key)
        );
        CREATE TABLE IF NOT EXISTS business_dashboard_settings (
            business_id TEXT PRIMARY KEY,
            exchange_rate REAL DEFAULT 0,
            exchange_rate_ves REAL DEFAULT 0,
            local_currency_code TEXT DEFAULT 'VES',
            owner_whatsapp TEXT DEFAULT '',
            restaurant_table_count INTEGER DEFAULT 12,
            custom_settings TEXT DEFAULT '{{}}',
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_payment_instructions (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            method_code TEXT NOT NULL,
            label TEXT,
            instructions TEXT,
            enabled INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(business_id, method_code)
        );
        CREATE TABLE IF NOT EXISTS webchat_payment_requests (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            customer_id TEXT,
            order_id TEXT,
            amount REAL NOT NULL DEFAULT 0,
            currency TEXT DEFAULT 'USD',
            payment_method TEXT DEFAULT 'pago_movil',
            customer_payment_details TEXT,
            items TEXT DEFAULT '[]',
            status TEXT DEFAULT 'pending',
            source TEXT DEFAULT 'webchat',
            approval_note TEXT,
            reviewed_by TEXT,
            reviewed_at TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_bookings (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            booking_type TEXT DEFAULT 'appointment',
            customer_name TEXT,
            customer_phone TEXT,
            party_size INTEGER DEFAULT 1,
            starts_at TEXT,
            service_name TEXT,
            status TEXT DEFAULT 'pending',
            table_number INTEGER,
            notes TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_whatsapp_channels (
            business_id TEXT PRIMARY KEY,
            enabled INTEGER DEFAULT 0,
            channel_status TEXT DEFAULT 'disconnected',
            connection_status TEXT DEFAULT 'disconnected',
            instance_name TEXT,
            provider TEXT DEFAULT 'evolution',
            phone_number TEXT,
            display_name TEXT,
            qr_code_data_url TEXT,
            pairing_code TEXT,
            last_error TEXT,
            connected_at TEXT,
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_whatsapp_auth_keys (
            business_id TEXT NOT NULL,
            file_name TEXT NOT NULL,
            file_content TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (business_id, file_name)
        );
        CREATE TABLE IF NOT EXISTS business_telegram_channels (
            business_id TEXT PRIMARY KEY,
            bot_token TEXT,
            bot_username TEXT,
            owner_chat_id TEXT,
            enabled INTEGER DEFAULT 0,
            channel_status TEXT DEFAULT 'inactive',
            polling_offset INTEGER DEFAULT 0,
            last_error TEXT,
            last_poll_at TEXT,
            tg_phone_number TEXT,
            tg_session_string TEXT,
            tg_user_id TEXT,
            tg_username TEXT,
            tg_display_name TEXT,
            tg_auth_mode TEXT DEFAULT 'none',
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS business_meta_channels (
            business_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            channel_status TEXT DEFAULT 'disconnected',
            account_name TEXT DEFAULT '',
            page_or_ig_id TEXT DEFAULT '',
            parent_page_id TEXT DEFAULT '',
            access_token TEXT DEFAULT '',
            verify_token TEXT DEFAULT '',
            last_error TEXT,
            last_event_at TEXT,
            connected_at TEXT,
            updated_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (business_id, platform)
        );
        CREATE TABLE IF NOT EXISTS calyrisia_checkout_orders (
            checkout_ref TEXT PRIMARY KEY,
            plan_code TEXT NOT NULL DEFAULT 'pro',
            amount REAL NOT NULL DEFAULT 39,
            currency TEXT NOT NULL DEFAULT 'USD',
            payment_method TEXT NOT NULL DEFAULT 'pago_movil',
            status TEXT NOT NULL DEFAULT 'pending',
            paypal_plan_id TEXT,
            paypal_subscription_id TEXT,
            paypal_status TEXT,
            customer_name TEXT,
            customer_email TEXT,
            customer_phone TEXT,
            business_name TEXT,
            customer_note TEXT,
            transaction_reference TEXT,
            proof_note TEXT,
            proof_submitted_at TEXT,
            contact_saved_at TEXT,
            paid_at TEXT,
            reviewed_at TEXT,
            reviewed_by TEXT,
            review_note TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS product_images (
            id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT},
            business_id TEXT NOT NULL,
            product_id TEXT NOT NULL,
            image_url TEXT NOT NULL,
            position INTEGER DEFAULT 0,
            sort_order INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """
    )
    for _alt in (
        "ALTER TABLE customers ADD COLUMN channel TEXT DEFAULT 'webchat'",
        "ALTER TABLE customers ADD COLUMN first_contact_at TEXT",
        "ALTER TABLE customers ADD COLUMN last_interaction_at TEXT",
        "ALTER TABLE conversations ADD COLUMN started_at TEXT",
        "ALTER TABLE conversations ADD COLUMN metadata TEXT DEFAULT '{}'",
        "ALTER TABLE conversations ADD COLUMN intent TEXT",
        "ALTER TABLE conversations ADD COLUMN topic TEXT",
        "ALTER TABLE conversations ADD COLUMN outcome TEXT",
        "ALTER TABLE conversations ADD COLUMN handoff_to_human INTEGER DEFAULT 0",
        "ALTER TABLE conversations ADD COLUMN transfer_reason TEXT",
        "ALTER TABLE conversations ADD COLUMN closed_at TEXT",
        "ALTER TABLE business_dashboard_settings ADD COLUMN exchange_rate REAL DEFAULT 0",
        "ALTER TABLE business_dashboard_settings ADD COLUMN local_currency_code TEXT DEFAULT 'VES'",
        "ALTER TABLE business_dashboard_settings ADD COLUMN owner_whatsapp TEXT DEFAULT ''",
        "ALTER TABLE product_images ADD COLUMN position INTEGER DEFAULT 0",
        "ALTER TABLE products ADD COLUMN is_service INTEGER DEFAULT 0",
        "ALTER TABLE conversation_messages ADD COLUMN intent TEXT",
        "ALTER TABLE conversation_messages ADD COLUMN sentiment TEXT",
        "ALTER TABLE business_whatsapp_channels ADD COLUMN channel_status TEXT DEFAULT 'disconnected'",
        "ALTER TABLE business_whatsapp_channels ADD COLUMN instance_name TEXT",
        "ALTER TABLE business_whatsapp_channels ADD COLUMN provider TEXT DEFAULT 'evolution'",
        "ALTER TABLE business_meta_channels ADD COLUMN parent_page_id TEXT DEFAULT ''",
        f"CREATE TABLE IF NOT EXISTS memory (id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT}, business_id TEXT NOT NULL, customer_id TEXT, conversation_id TEXT, user_id TEXT, memory_type TEXT DEFAULT 'fact', memory_key TEXT, content TEXT, source TEXT DEFAULT 'brain', confidence REAL DEFAULT 90, importance INTEGER DEFAULT 50, metadata TEXT DEFAULT '{{}}', expires_at TEXT, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))",
        f"CREATE TABLE IF NOT EXISTS business_rules (id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT}, business_id TEXT NOT NULL, rule_key TEXT, rule_value TEXT DEFAULT '{{}}', enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))",
        f"CREATE TABLE IF NOT EXISTS business_type_profiles (id TEXT PRIMARY KEY DEFAULT {_SQLITE_UUID_DEFAULT}, type_key TEXT UNIQUE, display_name TEXT, description TEXT, default_operating_mode TEXT DEFAULT 'hybrid', default_capabilities TEXT DEFAULT '[]', default_rules TEXT DEFAULT '{{}}', default_prompt_guidance TEXT, enabled INTEGER DEFAULT 1, created_at TEXT DEFAULT (datetime('now')), updated_at TEXT DEFAULT (datetime('now')))",
    ):
        try:
            conn.execute(_alt)
        except Exception:
            pass
    conn.commit()


class _SqlitePgCursor:
    def __init__(self, raw_cur: sqlite3.Cursor):
        self._cur = raw_cur

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            self._cur.close()
        except Exception:
            pass

    @staticmethod
    def _adapt_param(val: Any) -> Any:
        if hasattr(val, "val"):
            val = val.val
        if isinstance(val, (dict, list)):
            return json.dumps(val)
        if isinstance(val, bool):
            return 1 if val else 0
        if val is None or isinstance(val, (int, float, str, bytes)):
            return val
        return str(val)

    @staticmethod
    def _translate_sql(query: str) -> str:
        q = str(query).strip()
        q = re.sub(r"\bpublic\.", "", q, flags=re.IGNORECASE)
        q = re.sub(
            r"COALESCE\s*\(\s*to_jsonb\(\w+\)->>'plan_code'\s*,\s*'([^']+)'\s*\)",
            r"COALESCE(plan_code, '\1')",
            q,
            flags=re.IGNORECASE,
        )
        q = re.sub(r"to_jsonb\((\w+)\)->>?'(\w+)'", r"\1.\2", q, flags=re.IGNORECASE)
        q = re.sub(r"to_jsonb\((\w+)\)->'(\w+)'", r"\1.\2", q, flags=re.IGNORECASE)
        q = re.sub(r"json_agg\([^)]*\)", "'[]'", q, flags=re.IGNORECASE)
        q = re.sub(r"date_trunc\('month',\s*CURRENT_DATE\)", "strftime('%Y-%m-01', 'now')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bbtrim\(([^)]+)\)", r"trim(\1)", q, flags=re.IGNORECASE)
        q = re.sub(r"now\(\)\s*-\s*interval\s*'30 minutes'", "datetime('now', '-30 minutes')", q, flags=re.IGNORECASE)
        q = re.sub(r"::[a-zA-Z0-9_\[\]]+", "", q)
        q = re.sub(r"\bILIKE\b", "LIKE", q, flags=re.IGNORECASE)
        q = re.sub(r"\bgen_random_uuid\(\)", f"'{uuid4()}'", q, flags=re.IGNORECASE)
        q = re.sub(r"\bDEFAULT\s+NOW\(\)", "DEFAULT (datetime('now'))", q, flags=re.IGNORECASE)
        q = re.sub(r"\bNOW\(\)", "datetime('now')", q, flags=re.IGNORECASE)
        q = re.sub(r"\bTRUE\b", "1", q, flags=re.IGNORECASE)
        q = re.sub(r"\bFALSE\b", "0", q, flags=re.IGNORECASE)
        q = re.sub(r"\bFOR UPDATE\b", "", q, flags=re.IGNORECASE)
        q = re.sub(r"\bNULLS LAST\b", "", q, flags=re.IGNORECASE)
        q = q.replace("%s", "?")
        return q

    def execute(self, query: Any, params: Any = None):
        q_str = str(query)
        upper = q_str.strip().upper()
        if any(
            upper.startswith(prefix)
            for prefix in (
                "CREATE TABLE",
                "ALTER TABLE",
                "CREATE INDEX",
                "SET ",
                "GRANT ",
                "REVOKE ",
                "SAVEPOINT ",
                "RELEASE SAVEPOINT",
                "ROLLBACK TO SAVEPOINT",
            )
        ):
            return self
        sql_translated = self._translate_sql(q_str)
        adapted_params = tuple(self._adapt_param(p) for p in (params or ()))
        self._cur.execute(sql_translated, adapted_params)
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self) -> int:
        return self._cur.rowcount


class _SqlitePgConnection:
    def __init__(self, path: Path):
        self._conn = sqlite3.connect(str(path), check_same_thread=False)
        self.autocommit = False
        _init_local_sqlite(self._conn)

    def cursor(self, *args, **kwargs) -> _SqlitePgCursor:
        return _SqlitePgCursor(self._conn.cursor())

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass


@asynccontextmanager
async def get_connection():
    pool_ctx = None
    conn = None

    # 1. Attempt to acquire connection from psycopg_pool
    if _HAS_POOL:
        try:
            if getattr(pool, "closed", True):
                pool.open(wait=False)
            pool_ctx = pool.connection()
            conn = pool_ctx.__enter__()
        except Exception:
            pool_ctx = None
            conn = None

    if conn is not None and pool_ctx is not None:
        try:
            yield conn
        finally:
            try:
                pool_ctx.__exit__(None, None, None)
            except Exception:
                pass
        return

    # 2. Attempt direct psycopg connection if pool failed to acquire
    if psycopg is not None:
        direct_conn = None
        try:
            direct_conn = psycopg.connect(**_pool_kwargs)
        except Exception:
            direct_conn = None
        if direct_conn is not None:
            try:
                yield direct_conn
            finally:
                try:
                    direct_conn.close()
                except Exception:
                    pass
            return

    # 3. Automatic local SQLite fallback when running offline or without PostgreSQL
    sqlite_conn = _SqlitePgConnection(_LOCAL_DB_PATH)
    try:
        yield sqlite_conn
    finally:
        sqlite_conn.close()
