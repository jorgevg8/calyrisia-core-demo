from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.analytics_service import AnalyticsService
from app.services.business_brain_service import BusinessBrainService
from app.services.commercial_limits import get_business_plan, normalize_plan, plan_limits
from app.services.recommendation_engine import RecommendationEngine


class DashboardService:
    """Single read model for the authenticated owner/admin dashboard."""

    def __init__(self, conn):
        self.conn = conn
        self.analytics = AnalyticsService(conn)
        self.business_brain = BusinessBrainService(conn)
        self.recommendations = RecommendationEngine(conn)

    def overview(self, *, business_id: UUID) -> dict[str, Any]:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT b.id, COALESCE(NULLIF(TRIM(b.name), ''), 'Mi Negocio CALYRISIA') AS name,
                       COALESCE(b.business_type, 'tech_store') AS business_type,
                       COALESCE(b.timezone, 'America/Caracas') AS timezone,
                       COALESCE(b.currency, 'USD') AS currency,
                       COALESCE(b.status, 'active') AS status,
                       bp.industry, bp.short_description,
                       COALESCE(to_jsonb(b)->>'plan_code', 'free') AS plan_code
                FROM businesses b
                LEFT JOIN LATERAL (
                    SELECT industry, short_description
                    FROM business_profiles
                    WHERE business_id = b.id AND status = 'active'
                    ORDER BY created_at DESC NULLS LAST
                    LIMIT 1
                ) bp ON TRUE
                WHERE b.id = %s
                """,
                (business_id,),
            )
            business = cur.fetchone()
            if not business:
                cur.execute(
                    """
                    INSERT INTO businesses (id, name, business_type, timezone, currency, status, plan_code)
                    VALUES (%s, 'Mi Negocio CALYRISIA', 'tech_store', 'America/Caracas', 'USD', 'active', 'free')
                    ON CONFLICT (id) DO NOTHING
                    """,
                    (business_id,),
                )
                self.conn.commit()
                business = (
                    business_id,
                    "Mi Negocio CALYRISIA",
                    "tech_store",
                    "America/Caracas",
                    "USD",
                    "active",
                    "Comercio",
                    "",
                    "free",
                )

            conversations = 0
            handoffs = 0
            audits_today = 0
            try:
                cur.execute("SAVEPOINT sp_dash_conv")
                cur.execute("SELECT COUNT(*)::int FROM conversations WHERE business_id = %s", (business_id,))
                conversations = int(cur.fetchone()[0] or 0)
                cur.execute(
                    "SELECT COUNT(*)::int FROM conversations WHERE business_id = %s AND handoff_to_human = TRUE",
                    (business_id,),
                )
                handoffs = int(cur.fetchone()[0] or 0)
                cur.execute("RELEASE SAVEPOINT sp_dash_conv")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT sp_dash_conv")

            try:
                cur.execute("SAVEPOINT sp_dash_audit")
                cur.execute(
                    "SELECT COUNT(*)::int FROM audit_logs WHERE business_id = %s AND created_at >= CURRENT_DATE",
                    (business_id,),
                )
                audits_today = int(cur.fetchone()[0] or 0)
                cur.execute("RELEASE SAVEPOINT sp_dash_audit")
            except Exception:
                cur.execute("ROLLBACK TO SAVEPOINT sp_dash_audit")

        try:
            analytics = self.analytics.overview(business_id=business_id)
        except Exception:
            self.conn.rollback()
            analytics = {
                "customers": 0,
                "active_products": 0,
                "orders": {"total": 0, "sales_total": 0.0, "today": 0, "sales_today": 0.0},
                "inventory": {"records": 0, "low_stock": 0, "out_of_stock": 0},
            }

        try:
            insights = self.business_brain.list_insights(business_id=business_id, status="open", limit=8)
        except Exception:
            self.conn.rollback()
            insights = []

        try:
            recommendations = self.recommendations.list_recommendations(
                business_id=business_id, status="pending", limit=8
            )
        except Exception:
            self.conn.rollback()
            recommendations = []

        try:
            top_products = self.analytics.top_products(business_id=business_id, limit=5)
        except Exception:
            self.conn.rollback()
            top_products = []

        exchange_rate = 0.0
        local_currency_code = "VES"
        owner_whatsapp = ""
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT COALESCE(exchange_rate, 0), COALESCE(local_currency_code, 'VES'), COALESCE(owner_whatsapp, '')
                    FROM public.business_dashboard_settings
                    WHERE business_id = %s
                    """,
                    (business_id,),
                )
                s_row = cur.fetchone()
                if s_row:
                    exchange_rate = float(s_row[0] or 0)
                    local_currency_code = str(s_row[1] or "VES")
                    owner_whatsapp = str(s_row[2] or "")
        except Exception:
            self.conn.rollback()

        try:
            resolved_plan = get_business_plan(self.conn, business_id)
        except Exception:
            resolved_plan = normalize_plan(business[8] or "free")

        business_dict = {
            "id": str(business[0]),
            "name": str(business[1] or "Mi Negocio CALYRISIA"),
            "business_name": str(business[1] or "Mi Negocio CALYRISIA"),
            "business_type": str(business[2] or "tech_store"),
            "timezone": str(business[3] or "America/Caracas"),
            "currency": str(business[4] or "USD"),
            "status": str(business[5] or "active"),
            "industry": business[6] or "Comercio",
            "short_description": business[7] or "",
            "plan_code": resolved_plan,
            "plan": plan_limits(resolved_plan),
            "exchange_rate": exchange_rate,
            "local_currency_code": local_currency_code,
            "owner_whatsapp": owner_whatsapp,
        }

        return {
            "success": True,
            "name": business_dict["name"],
            "business": business_dict,
            "businesses": [business_dict],
            "analytics": {
                **analytics,
                "conversations_total": conversations,
                "handoffs_total": handoffs,
                "audits_today": audits_today,
            },
            "insights": insights,
            "recommendations": recommendations,
            "top_products": top_products,
        }
