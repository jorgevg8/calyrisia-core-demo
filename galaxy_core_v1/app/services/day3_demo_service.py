from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.analytics_service import AnalyticsService
from app.services.inventory_intelligence import InventoryIntelligenceService
from app.services.recommendation_v2_service import RecommendationV2Service
from app.services.system_diagnostics import DiagnosticsService
from app.services.tool_registry import list_tools


class Day3DemoService:
    def __init__(self, conn):
        self.conn = conn

    def overview(self, *, business_id: UUID) -> dict[str, Any]:
        diagnostics = DiagnosticsService(self.conn).diagnostics()
        analytics = AnalyticsService(self.conn).overview(business_id=business_id)
        inventory = InventoryIntelligenceService(self.conn).overview(business_id=business_id)
        recommendations = RecommendationV2Service(self.conn).dashboard(business_id=business_id)
        return {
            "success": True,
            "stage": "day3_mvp_overview",
            "business_id": str(business_id),
            "architecture": {
                "day2_core": ["Galaxy Core", "Memory", "Context", "Tool Manager", "Permission System", "Event Engine"],
                "intelligence": ["Galaxy Brain", "Business Brain", "Recommendation Engine"],
                "day3_modules": ["Webchat", "Customer Agent", "Sales & Orders", "Appointment Manager", "Inventory Intelligence", "Analytics", "Recommendation Engine V2"],
            },
            "diagnostics": diagnostics,
            "tools_registered": len(list_tools()),
            "analytics": analytics,
            "inventory": inventory,
            "recommendations": recommendations,
        }
