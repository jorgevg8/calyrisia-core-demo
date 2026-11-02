from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


OmnichannelType = Literal[
    "whatsapp",
    "instagram",
    "facebook",
    "messenger",
    "telegram",
    "webchat",
]


class NormalizedOmnichannelPayload(BaseModel):
    """Modelo normalizado para mensajes de Meta."""

    tenant_id: UUID = Field(...)
    channel: OmnichannelType = Field(...)
    sender_id: str = Field(..., min_length=1, max_length=160)
    message_text: str = Field(..., min_length=1, max_length=10000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender_name: str = Field(default="Cliente", max_length=180)
    external_message_id: str | None = Field(default=None, max_length=200)
    instance_or_page_id: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)