from __future__ import annotations

from typing import Any
from uuid import UUID

from app.services.autopilot_service import GalaxyAutopilotService
from app.services.conversation_service import ConversationService


class CustomerAgentService:
    """Day 3 Customer Agent facade with deterministic human-handoff detection."""

    HANDOFF_TERMS = (
        "quiero hablar con una persona",
        "hablar con una persona",
        "quiero hablar con alguien",
        "hablar con alguien",
        "persona real",
        "agente real",
        "asesor",
        "asesora",
        "representante",
        "humano",
    )

    def __init__(self, conn):
        self.conn = conn
        self.autopilot = GalaxyAutopilotService(conn)
        self.conversations = ConversationService(conn)

    def respond(self, payload) -> dict[str, Any]:
        text = payload.message.lower().strip()
        result = self.autopilot.respond(payload)
        conversation_id = UUID(str(result["conversation_id"]))

        if any(term in text for term in self.HANDOFF_TERMS):
            handoff = self.conversations.handoff(
                business_id=payload.business_id,
                conversation_id=conversation_id,
                reason="El cliente solicitó atención humana.",
            )
            result["response"] = (
                "Claro. He marcado esta conversación para atención humana. "
                "Un miembro del equipo podrá continuar contigo."
            )
            result["customer_agent"] = {
                "handoff_to_human": True,
                "handoff": handoff,
            }
        else:
            result["customer_agent"] = {
                "handoff_to_human": False,
                "handoff": None,
            }

        result["agent"] = "customer_agent"
        return result
