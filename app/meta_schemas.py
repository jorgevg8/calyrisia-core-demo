from __future__ import annotations

from datetime import datetime, timezone
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
    """Modelo Pydantic estándar para centralizar y normalizar payloads de WhatsApp, Instagram y Facebook."""

    tenant_id: UUID = Field(..., description="Identificador único del negocio (tenant_id)")
    channel: OmnichannelType = Field(..., description="Canal de origen normalizado")
    sender_id: str = Field(..., min_length=1, max_length=160, description="Identificador o teléfono del remitente")
    message_text: str = Field(..., min_length=1, max_length=10000, description="Texto limpio del mensaje")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Marca de tiempo UTC del mensaje",
    )
    sender_name: str = Field(default="Cliente", max_length=180)
    external_message_id: str | None = Field(default=None, max_length=200)
    instance_or_page_id: str | None = Field(default=None, max_length=160)
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvolutionInstanceConnectResponse(BaseModel):
    """Respuesta tipada al solicitar la creación o conexión de una instancia de WhatsApp por tenant_id."""

    success: bool = True
    tenant_id: str
    instance_name: str
    provider: str = "evolution"
    status: str = "qr_ready"
    qr_code_data_url: str | None = None
    qr_code_base64: str | None = None
    pairing_code: str | None = None
    webhook_url: str | None = None
    message: str


class MetaOAuthUrlResponse(BaseModel):
    """Respuesta tipada para iniciar el flujo OAuth en 1 clic con Facebook e Instagram."""

    success: bool = True
    auth_url: str
    platform: str
    tenant_id: str | None = None
