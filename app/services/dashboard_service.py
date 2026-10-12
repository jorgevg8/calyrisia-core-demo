from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.analytics_service import AnalyticsService
from app.services.business_brain_service import BusinessBrainService
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
                SELECT b.id, b.name, b.business_type, b.timezone, b.currency, b.status,
                       bp.industry, bp.short_description
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
                raise ValueError("Business no encontrado")

            cur.execute(
                "SELECT COUNT(*)::int FROM conversations WHERE business_id = %s",
                (business_id,),
            )
            conversations = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM conversations
                WHERE business_id = %s AND handoff_to_human = TRUE
                """,
                (business_id,),
            )
            handoffs = int(cur.fetchone()[0])

            cur.execute(
                """
                SELECT COUNT(*)::int
                FROM audit_logs
                WHERE business_id = %s
                  AND created_at >= CURRENT_DATE
                """,
                (business_id,),
            )
            audits_today = int(cur.fetchone()[0])

        analytics = self.analytics.overview(business_id=business_id)
        insights = self.business_brain.list_insights(
            business_id=business_id, status="open", limit=8
        )
        recommendations = self.recommendations.list_recommendations(
            business_id=business_id, status="pending", limit=8
        )
        top_products = self.analytics.top_products(business_id=business_id, limit=5)

        return {
            "success": True,
            "business": {
                "id": str(business[0]),
                "name": business[1],
                "business_type": business[2],
                "timezone": business[3],
                "currency": business[4],
                "status": business[5],
                "industry": business[6],
                "short_description": business[7],
            },
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
