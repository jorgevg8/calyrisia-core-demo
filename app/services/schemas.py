from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


Channel = Literal[
    "whatsapp",
    "webchat",
    "instagram",
    "messenger",
    "telegram",
    "email",
    "phone",
    "other",
]


MemoryType = Literal[
    "conversation",
    "customer",
    "operational",
    "business",
    "decision",
    "preference",
    "knowledge",
    "error",
    "system",
]


class IncomingMessage(BaseModel):
    business_id: UUID
    customer_id: UUID | None = None
    conversation_id: UUID | None = None
    channel: Channel = "webchat"
    message: str = Field(min_length=1, max_length=10000)
    metadata: dict[str, Any] = Field(default_factory=dict)


class CoreResponse(BaseModel):
    success: bool
    stage: str
    business_id: UUID
    customer_id: UUID | None = None
    conversation_id: UUID
    message_id: UUID
    next_component: str


class CreateMemoryRequest(BaseModel):
    business_id: UUID
    customer_id: UUID | None = None
    conversation_id: UUID | None = None
    user_id: UUID | None = None
    memory_type: MemoryType
    memory_key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    importance: int = Field(default=50, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemoryResponse(BaseModel):
    success: bool
    memory_id: UUID


class ContextResponse(BaseModel):
    found: bool
    reason: str | None = None
    context: dict[str, Any] | None = None


class CreateEventRequest(BaseModel):
    business_id: UUID
    event_id: str | None = Field(default=None, min_length=1, max_length=150)
    event_type: str = Field(min_length=1, max_length=100)
    source: str = Field(min_length=1, max_length=100)
    priority: Literal["critical", "high", "normal", "low"] = "normal"
    entity_type: str | None = Field(default=None, max_length=100)
    entity_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    occurred_at: datetime | None = None


class EventResponse(BaseModel):
    success: bool
    duplicate: bool
    event_record_id: UUID
    event_id: str
    event_type: str
    priority: str
    status: str
    next_component: str | None = None


class ToolExecuteRequest(BaseModel):
    business_id: UUID
    tool_name: str = Field(min_length=1, max_length=150)
    inputs: dict[str, Any] = Field(default_factory=dict)
    requested_by_user_id: UUID | None = None


class ToolExecuteResponse(BaseModel):
    success: bool
    action_id: UUID
    status: str = "completed"
    approval_id: UUID | None = None
    permission: dict[str, Any] = Field(default_factory=dict)
    tool: dict[str, Any]
    result: dict[str, Any] | None = None
    resource_type: str | None = None
    resource_id: UUID | None = None


class BrainRequest(BaseModel):
    business_id: UUID
    customer_id: UUID | None = None
    conversation_id: UUID
    message: str = Field(min_length=1, max_length=10000)


class BusinessBrainAnalyzeRequest(BaseModel):
    business_id: UUID
    focus: Literal["all", "inventory"] = "all"
    event_id: str | None = Field(default=None, max_length=150)


class BusinessInsightResponse(BaseModel):
    id: str
    business_id: str
    insight_type: str
    category: str
    severity: str
    priority: str
    entity_type: str | None = None
    entity_id: str | None = None
    title: str
    description: str
    status: str
    confidence: float | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    source_event_id: str | None = None
    detected_at: str | None = None
    resolved_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class RecommendationResponse(BaseModel):
    id: str
    business_id: str
    insight_id: str
    recommendation_type: str
    priority: str
    title: str
    description: str
    rationale: str
    action_type: str
    requires_approval: bool
    status: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str | None = None
    updated_at: str | None = None
    expires_at: str | None = None
    acted_at: str | None = None


class BusinessBrainAnalyzeResponse(BaseModel):
    success: bool
    stage: str
    business_id: str
    analysis_started_at: str
    analysis_completed_at: str
    focus: str
    detectors_run: list[str] = Field(default_factory=list)
    insights_detected: int
    recommendations_generated: int
    insights: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[dict[str, Any]] = Field(default_factory=list)


class InsightStatusRequest(BaseModel):
    status: Literal["open", "acknowledged", "resolved", "dismissed"]


class RecommendationStatusRequest(BaseModel):
    status: Literal["pending", "accepted", "rejected", "executed", "dismissed", "expired"]




class AutopilotResponse(BaseModel):
    success: bool
    stage: str
    business_id: str
    customer_id: str | None = None
    conversation_id: str
    input_message_id: str
    output_message_id: str
    response: str
    intent: str
    confidence: float
    brain: dict[str, Any] = Field(default_factory=dict)
    flow: dict[str, Any] = Field(default_factory=dict)
    next_component: str
    # Paso 35 / Customer Agent: these fields must survive the FastAPI response_model.
    customer_agent: dict[str, Any] = Field(default_factory=dict)
    agent: str | None = None


class AutopilotEventResponse(BaseModel):
    success: bool
    stage: str
    event: dict[str, Any] = Field(default_factory=dict)
    business_analysis: dict[str, Any] | None = None
    next_component: str | None = None


class BrainResponse(BaseModel):
    success: bool
    stage: str
    intent: str
    confidence: float
    response: str
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    message_id: UUID
    next_component: str
    brain_route: str = "unknown"
    brain_rounds: int = 0
    brain_tools: list[str] = Field(default_factory=list)
    brain_error: str | None = None
    brain_models_tried: list[str] = Field(default_factory=list)


class OnboardingProduct(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    sku: str | None = Field(default=None, max_length=100)
    category: str = Field(default="General", max_length=150)
    price: float = Field(default=0, ge=0)
    quantity: float = Field(default=0, ge=0)
    minimum_quantity: float = Field(default=0, ge=0)
    location: str = Field(default="main", max_length=150)


class OnboardingCustomer(BaseModel):
    full_name: str = Field(min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    phone: str | None = Field(default=None, max_length=80)


class OnboardingBusinessRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=250)
    business_type: str = Field(default="Retail", max_length=150)
    industry: str = Field(default="Technology / Retail", max_length=150)
    description: str = Field(default="", max_length=5000)
    phone: str | None = Field(default=None, max_length=80)
    email: str | None = Field(default=None, max_length=320)
    website: str | None = Field(default=None, max_length=500)
    timezone: str = Field(default="America/New_York", max_length=100)
    currency: str = Field(default="USD", min_length=3, max_length=10)
    address: str | None = Field(default=None, max_length=300)
    city: str | None = Field(default=None, max_length=120)
    state_province: str | None = Field(default=None, max_length=120)
    country: str = Field(default="United States", max_length=120)
    postal_code: str | None = Field(default=None, max_length=40)
    operating_hours: dict[str, Any] = Field(default_factory=dict)
    policies: dict[str, Any] = Field(default_factory=dict)
    objectives: list[str] = Field(default_factory=list)
    processes: dict[str, Any] = Field(default_factory=dict)
    autonomy_config: dict[str, Any] = Field(default_factory=dict)
    communication_config: dict[str, Any] = Field(default_factory=dict)
    social_links: dict[str, Any] = Field(default_factory=dict)
    additional_settings: dict[str, Any] = Field(default_factory=dict)
    product: OnboardingProduct | None = None
    customer: OnboardingCustomer | None = None
