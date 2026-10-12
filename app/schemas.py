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


class WebchatSessionRequest(BaseModel):
    business_id: UUID | None = None
    customer_id: UUID | None = None
    visitor_name: str | None = Field(default=None, max_length=150)


class WebchatMessageRequest(BaseModel):
    customer_id: UUID
    conversation_id: UUID | None = None
    message: str = Field(min_length=1, max_length=10000)


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


class OwnerCopilotRequest(BaseModel):
    message: str = Field(min_length=1, max_length=10000)


class BusinessBrainAnalyzeRequest(BaseModel):
    business_id: UUID
    focus: Literal["all", "inventory"] = "all"
    event_id: str | None = Field(default=None, max_length=150)


KnowledgeItemType = Literal["knowledge", "policy", "faq", "process"]
KnowledgeItemVisibility = Literal["customer", "internal", "both"]
KnowledgeItemStatus = Literal["active", "archived"]

class KnowledgeItemCreateRequest(BaseModel):
    item_type: KnowledgeItemType
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=20000)
    visibility: KnowledgeItemVisibility = "both"
    priority: int = Field(default=50, ge=0, le=100)
    source: str | None = Field(default=None, max_length=250)
    metadata: dict[str, Any] = Field(default_factory=dict)

class KnowledgeItemUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1, max_length=20000)
    visibility: KnowledgeItemVisibility | None = None
    priority: int | None = Field(default=None, ge=0, le=100)
    source: str | None = Field(default=None, max_length=250)
    metadata: dict[str, Any] | None = None
    status: KnowledgeItemStatus | None = None

class Customer360UpdateRequest(BaseModel):
    lifecycle_stage: str | None = Field(default=None, min_length=1, max_length=50)
    segment: str | None = Field(default=None, max_length=100)
    tags: list[str] | None = None
    preferences: dict[str, Any] | None = None
    communication_preferences: dict[str, Any] | None = None
    consent: dict[str, Any] | None = None
    summary: str | None = Field(default=None, max_length=10000)
    value_score: float | None = Field(default=None, ge=0, le=100)
    metadata: dict[str, Any] | None = None


class CustomerMemoryUpsertRequest(BaseModel):
    memory_type: MemoryType
    memory_key: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=10000)
    source: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=100)
    importance: int = Field(default=50, ge=0, le=100)
    metadata: dict[str, Any] = Field(default_factory=dict)


class KnowledgeItemResponse(BaseModel):
    id: str
    business_id: str
    item_type: str
    title: str
    content: str
    visibility: str
    priority: int
    source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    status: str
    created_by: str | None = None
    created_at: str | None = None
    updated_at: str | None = None

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


class WorkflowCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    trigger_event_type: str = Field(min_length=1, max_length=100)
    definition: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class WorkflowResponse(BaseModel):
    id: UUID
    business_id: UUID
    name: str
    trigger_event_type: str
    enabled: bool
    definition: dict[str, Any] = Field(default_factory=dict)
    created_by_user_id: UUID | None = None
    created_at: str | None = None
    updated_at: str | None = None


class WorkflowTriggerRequest(BaseModel):
    event_record_id: UUID


class ApprovalDecisionRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=2000)


class OperationQueueResponse(BaseModel):
    success: bool = True
    business_id: UUID
    counts: dict[str, int] = Field(default_factory=dict)
    items: list[dict[str, Any]] = Field(default_factory=list)


class ApprovalResponse(BaseModel):
    success: bool = True
    approval: dict[str, Any]


class WorkflowRunResponse(BaseModel):
    success: bool = True
    duplicate: bool = False
    run_id: UUID
    business_id: UUID | None = None
    workflow_id: UUID | None = None
    event_record_id: UUID | None = None
    idempotency_key: str | None = None
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
    steps: list[dict[str, Any]] = Field(default_factory=list)


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


class OnboardingOwner(BaseModel):
    full_name: str = Field(min_length=1, max_length=150)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=255)
    phone: str | None = Field(default=None, max_length=50)


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
    owner: OnboardingOwner | None = None


class BusinessTypeProfileOverrideRequest(BaseModel):
    overrides: dict[str, Any] = Field(default_factory=dict)


class BusinessTypeProfileResponse(BaseModel):
    success: bool
    profile: dict[str, Any]


# ===============================
# AGENT BLUEPRINT (PASO 61)
# ===============================
class AgentBlueprintCreateRequest(BaseModel):
    agent_name: str
    core_objective: str
    capabilities: list[str]

class AgentBlueprintResponse(BaseModel):
    success: bool
    blueprint_id: str
    business_id: str
    agent_name: str
    core_objective: str
    capabilities: list[str]
    status: str

# ===============================
# GOALS & KPI ENGINE (PASO 62)
# ===============================
class GoalCreateRequest(BaseModel):
    name: str
    metric_name: str
    target_value: float

class GoalResponse(BaseModel):
    id: str
    business_id: str
    name: str
    metric_name: str
    target_value: float
    current_value: float
    status: str

# ===============================
# AUTONOMOUS TASK PLANNER (PASO 63)
# ===============================
class AutonomousTaskCreate(BaseModel):
    title: str
    description: str | None = None
    risk_level: Literal["low", "medium", "high"] = "low"

class AutonomousTaskResponse(BaseModel):
    id: str
    business_id: str
    title: str
    description: str | None
    risk_level: str
    requires_approval: bool
    status: str

class AutonomousPlanCreate(BaseModel):
    steps: list[dict[str, Any]]

class AutonomousPlanResponse(BaseModel):
    id: str
    task_id: str
    steps: list[dict[str, Any]]
    status: str

    # ===============================
# AUTONOMY POLICY MATRIX V2 (PASO 64)
# ===============================
class AutonomyPolicyCreate(BaseModel):
    action_name: str
    policy_mode: Literal["auto", "rule", "approval", "blocked"]
    value_limit: float | None = None

class AutonomyPolicyResponse(BaseModel):
    id: str
    business_id: str
    action_name: str
    policy_mode: str
    value_limit: float | None

    # ===============================
# EVENT BUS + SCHEDULER (PASO 65)
# ===============================
class EventBusCreate(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)

class EventBusResponse(BaseModel):
    id: str
    business_id: str
    event_type: str
    payload: dict[str, Any]
    status: str

    # ===============================
# AUTONOMOUS WORKER (PASO 66)
# ===============================
class EventProcessResponse(BaseModel):
    success: bool
    processed_count: int
    tasks_created: int

    # ===============================
# TASK EXECUTION ENGINE (PASO 67)
# ===============================
class TaskExecuteResponse(BaseModel):
    success: bool
    task_id: str
    status: str
    message: str

    # ===============================
# AUTONOMOUS AUDIT TRAIL (PASO 69)
# ===============================
class AuditLogResponse(BaseModel):
    id: str
    business_id: str
    actor: str
    action: str
    target_resource: str | None
    details: dict[str, Any]
    created_at: Any

    # ===============================
# AUTONOMOUS COMMAND CENTER (PASO 70)
# ===============================
class AutonomyStatusResponse(BaseModel):
    success: bool
    business_id: str
    pending_events: int
    pending_tasks: int
    active_policies: int
    active_goals: int

# ===============================
# AGENT RUNTIME STATE MACHINE (PASO 71)
# ===============================
class AgentExecutionResponse(BaseModel):
    id: str
    status: str
    started_at: Any | None = None
    completed_at: Any | None = None

    # ===============================
# LONG-RUNNING JOBS (PASO 72)
# ===============================
class JobCreateRequest(BaseModel):
    task_id: str
    execution_id: str
    job_name: str
    total_steps: int = 1
    max_retries: int = 3

class JobResponse(BaseModel):
    id: str
    job_name: str
    status: str
    current_checkpoint: int
    total_steps: int
    retry_count: int
    state_data: dict[str, Any]

    # ===============================
# HUMAN-IN-THE-LOOP V2 (PASO 73)
# ===============================
class RuntimeApprovalCreate(BaseModel):
    execution_id: str
    action_name: str
    reason: str
    impact_level: str = "medium"
    evidence: dict[str, Any] = Field(default_factory=dict)

class RuntimeApprovalDecide(BaseModel):
    approved: bool
    notes: str = ""

class RuntimeApprovalResponse(BaseModel):
    id: str
    status: str
    execution_id: str | None = None
    expires_at: Any | None = None
    execution_resumed: bool | None = None

    # ===============================
# ACTION RELIABILITY & IDEMPOTENCY (PASO 74)
# ===============================
class IdempotencyCheckRequest(BaseModel):
    idempotency_key: str
    action_name: str
    payload: dict[str, Any] = Field(default_factory=dict)

class IdempotencyRecordResponse(BaseModel):
    idempotency_key: str
    action_name: str
    status: str
    response_data: dict[str, Any]
    is_duplicate: bool

    # ===============================
# PROACTIVE CUSTOMER LIFECYCLE (PASO 75)
# ===============================
class ProactiveEngagementCreate(BaseModel):
    customer_id: str
    trigger_event: str
    scheduled_for: Any | None = None

class ProactiveEngagementResponse(BaseModel):
    id: str
    customer_id: str
    trigger_event: str
    status: str
    scheduled_for: Any | None = None

# ===============================
# OMNICHANNEL GATEWAY (PASO 76)
# ===============================
class OmnichannelMessageCreate(BaseModel):
    channel: str
    direction: str = "inbound"
    message_content: str
    customer_id: str | None = None
    conversation_id: str | None = None

class OmnichannelMessageResponse(BaseModel):
    id: str
    channel: str
    direction: str
    status: str
    message_content: str

# ===============================
# PATCH PARA QUE UVICORN ARRANQUE
# ===============================
class VisionEvidenceCreate(BaseModel):
    image_url: str
    operation_type: str
    detected_data: dict[str, Any]
    confidence: float

class VisionEvidenceResponse(BaseModel):
    id: str
    image_url: str
    operation_type: str
    confidence: float
    requires_human: bool
    status: str

    # ===============================
# OPPORTUNITY ENGINE V2 (PASO 78)
# ===============================
class OpportunityCreate(BaseModel):
    title: str
    description: str
    opportunity_type: str
    potential_value: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)

class OpportunityResponse(BaseModel):
    id: str
    title: str
    description: str
    opportunity_type: str
    potential_value: float
    status: str

    # ===============================
# CUSTOMER HEALTH & CHURN (PASO 79)
# ===============================
class CustomerHealthUpdate(BaseModel):
    customer_id: str
    sentiment_score: float = Field(ge=0.0, le=1.0)
    churn_risk: str
    risk_reason: str | None = None

class CustomerHealthResponse(BaseModel):
    customer_id: str
    sentiment_score: float
    churn_risk: str
    risk_reason: str | None

    # ===============================
# EXTERNAL WEBHOOK DISPATCHER (PASO 80)
# ===============================
class WebhookDispatchCreate(BaseModel):
    target_url: str
    event_name: str
    payload: dict[str, Any] = Field(default_factory=dict)

class WebhookDispatchResponse(BaseModel):
    id: str
    target_url: str
    event_name: str
    status: str

    # ===============================
# LLM USAGE & COST TRACKER (PASO 81)
# ===============================
class LLMUsageCreate(BaseModel):
    model_name: str
    prompt_tokens: int
    completion_tokens: int
    feature_used: str

class LLMUsageResponse(BaseModel):
    id: str
    model_name: str
    total_tokens: int
    total_cost: float
    feature_used: str

    # ===============================
# BUSINESS KPI INTELLIGENCE V2 (PASO 82)
# ===============================
class KPIAnalysisCreate(BaseModel):
    metric_name: str
    current_value: float
    previous_value: float

class KPIAnalysisResponse(BaseModel):
    id: str
    metric_name: str
    current_value: float
    trend_percentage: float
    trend_direction: str
    insight: str | None
    recommendation: str | None

    # ===============================
# ANOMALY DETECTION ENGINE (PASO 83)
# ===============================
class AnomalyCreate(BaseModel):
    anomaly_type: str
    description: str
    severity: str
    detected_value: float
    expected_baseline: float

class AnomalyResponse(BaseModel):
    id: str
    anomaly_type: str
    description: str
    severity: str
    status: str

    # ===============================
# OPPORTUNITY PRIORITIZATION (PASO 84)
# ===============================
class OpportunityScoreRequest(BaseModel):
    impact: int = Field(ge=1, le=10, description="Impacto en el negocio (1-10)")
    urgency: int = Field(ge=1, le=10, description="Urgencia temporal (1-10)")
    confidence: float = Field(ge=0.0, le=1.0, description="Nivel de certeza de la IA (0.0-1.0)")
    effort: int = Field(ge=1, le=10, description="Esfuerzo o costo de ejecución (1-10)")

class PrioritizedOpportunityResponse(BaseModel):
    id: str
    title: str
    opportunity_type: str
    potential_value: float
    priority_score: int

    # ===============================
# ADAPTIVE LEARNING LOOP V2 (PASO 85)
# ===============================
class LearningLoopCreate(BaseModel):
    action_taken: str
    reasoning: str
    outcome: str
    learning_signal: str

class LearningLoopResponse(BaseModel):
    id: str
    action_taken: str
    outcome: str
    learning_signal: str

    # ===============================
# MULTI-AGENT ORCHESTRATOR (PASO 86)
# ===============================
class AgentDelegationCreate(BaseModel):
    task_description: str
    payload: dict[str, Any] = Field(default_factory=dict)

class AgentDelegationResponse(BaseModel):
    id: str
    assigned_agent: str
    task_description: str
    status: str

    # ===============================
# AUTONOMOUS WORKFLOW RECOVERY (PASO 87)
# ===============================
class RecoveryLogCreate(BaseModel):
    task_id: str
    failure_reason: str
    recovery_strategy: str = "retry"
    max_attempts: int = 3

class RecoveryLogResponse(BaseModel):
    id: str
    task_id: str
    status: str
    attempt_count: int
    recovery_strategy: str

    # ===============================
# COST & RESOURCE OPTIMIZATION (PASO 88)
# ===============================
class CostOptimizationCreate(BaseModel):
    task_id: str
    task_value: float
    estimated_cost: float

class CostOptimizationResponse(BaseModel):
    id: str
    task_id: str
    roi_status: str
    decision: str
    net_profit: float

    # ===============================
# AUTONOMOUS GOVERNANCE (PASO 89)
# ===============================
class GovernanceEvaluateCreate(BaseModel):
    agent_name: str
    action_intent: str
    risk_score: int = Field(ge=0, le=100)

class GovernanceEvaluateResponse(BaseModel):
    id: str
    agent_name: str
    action_intent: str
    policy_evaluation: str
    reasoning: str

    # ===============================
# GALAXY ACCEPTANCE E2E (PASO 90)
# ===============================
class AcceptanceTestRequest(BaseModel):
    customer_message: str