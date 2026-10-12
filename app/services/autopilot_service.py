from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from psycopg.types.json import Jsonb

from app.services.business_brain_service import BusinessBrainService
from app.services.brain_service import BrainService
from app.services.core_service import GalaxyCoreService
from app.services.event_engine import EventEngine
from app.services.analytics_service import AnalyticsService
from app.services.recommendation_engine import RecommendationEngine


class AutopilotServiceError(Exception):
    """Raised when the integrated Galaxy Business Autopilot flow fails."""


class GalaxyAutopilotService:
    """Step 20 orchestration layer."""

    def __init__(self, conn):
        self.conn = conn
        self.core = GalaxyCoreService(conn)
        self.brain = BrainService(conn)
        self.business_brain = BusinessBrainService(conn)
        self.event_engine = EventEngine(conn)

    @staticmethod
    def _safe(value: Any) -> Any:
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, dict):
            return {str(k): GalaxyAutopilotService._safe(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [GalaxyAutopilotService._safe(v) for v in value]
        return value

    def respond(self, payload) -> dict[str, Any]:
        """Run the customer-facing autopilot flow.

        OWNER privileges are intentionally NOT inferred from request metadata.
        The Owner Copilot is exposed only through an authenticated OWNER-only route.
        """

        core_result = self.core.handle_incoming_message(payload)

        conversation_id = core_result["conversation_id"]
        customer_id = core_result.get("customer_id")

        brain_result = self.brain.respond(
            business_id=payload.business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            user_message=payload.message,
        )

        self._audit(
            business_id=payload.business_id,
            action_type="autopilot_message_completed",
            status="success",
            resource_type="conversation",
            resource_id=conversation_id,
            reason="Galaxy Business Autopilot completed a conversational MVP cycle.",
            metadata={
                "channel": payload.channel,
                "input_message_id": core_result["message_id"],
                "output_message_id": brain_result.get("message_id"),
                "brain_route": brain_result.get("brain_route"),
                "brain_rounds": brain_result.get("brain_rounds"),
                "brain_tools": brain_result.get("brain_tools", []),
                "tool_results_count": len(brain_result.get("tool_results", [])),
            },
        )

        return {
            "success": True,
            "stage": "autopilot_completed",
            "business_id": str(payload.business_id),
            "customer_id": str(customer_id) if customer_id else None,
            "conversation_id": str(conversation_id),
            "input_message_id": str(core_result["message_id"]),
            "output_message_id": str(brain_result["message_id"]),
            "response": brain_result.get("response", ""),
            "intent": brain_result.get("intent", "general"),
            "confidence": brain_result.get("confidence", 0.0),
            "brain": self._safe(brain_result),
            "flow": {
                "core": "completed",
                "context": "completed",
                "brain": brain_result.get("brain_route", "unknown"),
                "tools": brain_result.get("brain_tools", []),
                "permissions": "enforced_by_tool_manager",
                "audit": "completed",
            },
            "next_component": "business_brain",
        }

    def process_event(self, payload) -> dict[str, Any]:
        """Run an event through Event Engine and, when appropriate, Business Brain."""
        event_result = self.event_engine.receive_and_process(
            business_id=payload.business_id,
            event_type=payload.event_type,
            source=payload.source,
            priority=payload.priority,
            entity_type=payload.entity_type,
            entity_id=payload.entity_id,
            payload=payload.payload,
            event_id=payload.event_id,
            occurred_at=payload.occurred_at,
        )

        business_analysis = None
        next_component = event_result.get("next_component")

        if not event_result.get("duplicate") and next_component == "business_brain":
            focus = "inventory" if payload.event_type.strip().upper() in {
                "STOCK_LOW",
                "STOCK_OUT",
                "INVENTORY_DISCREPANCY",
            } else "all"
            business_analysis = self.business_brain.analyze(
                business_id=payload.business_id,
                focus=focus,
                event_id=event_result.get("event_record_id"),
            )

        self._audit(
            business_id=payload.business_id,
            action_type="autopilot_event_completed",
            status="success",
            resource_type=payload.entity_type or "event",
            resource_id=payload.entity_id,
            reason="Galaxy Business Autopilot completed an event cycle.",
            event_id=event_result.get("event_record_id"),
            metadata={
                "event_type": payload.event_type,
                "event_duplicate": event_result.get("duplicate"),
                "next_component": next_component,
                "business_analysis_ran": business_analysis is not None,
            },
        )

        return {
            "success": True,
            "stage": "autopilot_event_completed",
            "event": self._safe(event_result),
            "business_analysis": self._safe(business_analysis),
            "next_component": next_component,
        }

    def analyze_business(self, payload) -> dict[str, Any]:
        """Run Business Brain + Recommendation Engine through the MVP facade."""
        result = self.business_brain.analyze(
            business_id=payload.business_id,
            focus=payload.focus,
            event_id=payload.event_id,
        )

        self._audit(
            business_id=payload.business_id,
            action_type="autopilot_business_analysis_completed",
            status="success",
            resource_type="business",
            resource_id=payload.business_id,
            reason="Business Brain analysis completed through the Autopilot facade.",
            metadata={
                "focus": payload.focus,
                "insights_detected": result.get("insights_detected", 0),
                "recommendations_generated": result.get("recommendations_generated", 0),
            },
        )

        return self._safe(result)

    def _audit(
        self,
        *,
        business_id: UUID,
        action_type: str,
        status: str,
        resource_type: str,
        resource_id: UUID | None,
        reason: str,
        metadata: dict[str, Any],
        event_id: UUID | None = None,
    ) -> None:
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (
                        business_id,
                        event_id,
                        actor_type,
                        action_type,
                        resource_type,
                        resource_id,
                        status,
                        reason,
                        metadata,
                        created_at
                    )
                    VALUES (%s, %s, 'system', %s, %s, %s, %s, %s, %s, NOW())
                    """,
                    (
                        business_id,
                        event_id,
                        action_type,
                        resource_type,
                        resource_id,
                        status,
                        reason,
                        Jsonb(self._safe(metadata)),
                    ),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()