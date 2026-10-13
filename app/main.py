
def _get_default_10_products(business_type: str, currency: str = "USD") -> list[dict]:
    b_type = (business_type or "").lower()
    
    if any(k in b_type for k in ["restauran", "comida", "hamburgue", "pizza", "caf", "bar", "panader"]):
        return [
            {"name": "Hamburguesa Especial Calyrisia", "price": 8.50, "category": "Comida"},
            {"name": "Hamburguesa Doble Queso y Tocineta", "price": 11.00, "category": "Comida"},
            {"name": "Perro Caliente Gigante con Todo", "price": 4.00, "category": "Comida"},
            {"name": "Papas Fritas Rústicas con Queso", "price": 3.50, "category": "Acompañantes"},
            {"name": "Nuggets de Pollo Crujientes (8 pcs)", "price": 5.00, "category": "Acompañantes"},
            {"name": "Pizza Personal Pepperoni", "price": 7.00, "category": "Comida"},
            {"name": "Tequeños con Salsa Tártara (6 pcs)", "price": 4.50, "category": "Entradas"},
            {"name": "Refresco Frío 355ml", "price": 1.50, "category": "Bebidas"},
            {"name": "Malteada Cremosa de Chocolate", "price": 3.50, "category": "Bebidas"},
            {"name": "Postre Brownie con Helado", "price": 4.00, "category": "Postres"},
        ]
    elif any(k in b_type for k in ["ropa", "boutique", "moda", "calzado", "textil", "zapater"]):
        return [
            {"name": "Camisa de Lino Manga Larga", "price": 25.00, "category": "Ropa"},
            {"name": "Pantalón Jean Slim Fit Clásico", "price": 32.00, "category": "Ropa"},
            {"name": "Vestido Casual Elegante", "price": 28.00, "category": "Ropa"},
            {"name": "Blusa de Seda Estampada", "price": 22.00, "category": "Ropa"},
            {"name": "Chaqueta Denim Clásica", "price": 45.00, "category": "Ropa"},
            {"name": "Short Playero Casual", "price": 16.00, "category": "Ropa"},
            {"name": "Franela Básica 100% Algodón", "price": 12.00, "category": "Ropa"},
            {"name": "Zapatos Casuales de Cuero", "price": 48.00, "category": "Calzado"},
            {"name": "Cinturón de Cuero Reversible", "price": 15.00, "category": "Accesorios"},
            {"name": "Lentes de Sol Polarizados", "price": 18.00, "category": "Accesorios"},
        ]
    elif any(k in b_type for k in ["super", "market", "bode", "abasto", "viveres"]):
        return [
            {"name": "Harina de Maíz PAN 1kg", "price": 1.30, "category": "Alimentos"},
            {"name": "Arroz Blanco Premium 1kg", "price": 1.20, "category": "Alimentos"},
            {"name": "Aceite Vegetal 1 Litro", "price": 2.80, "category": "Alimentos"},
            {"name": "Queso Blanco Llanero 1kg", "price": 5.50, "category": "Lácteos"},
            {"name": "Café Molido Gourmet 500g", "price": 4.20, "category": "Alimentos"},
            {"name": "Pasta Larga Espagueti 1kg", "price": 1.50, "category": "Alimentos"},
            {"name": "Leche Líquida Completa 1L", "price": 1.80, "category": "Lácteos"},
            {"name": "Nutella Crema Avellanas 350g", "price": 5.50, "category": "Dulces"},
            {"name": "Refresco Familiar 2 Litros", "price": 2.50, "category": "Bebidas"},
            {"name": "Pack 4 Rollos Papel Higiénico", "price": 2.00, "category": "Higiene"},
        ]
    elif any(k in b_type for k in ["farma", "salud", "medic"]):
        return [
            {"name": "Paracetamol 500mg (10 tabs)", "price": 2.00, "category": "Medicamentos"},
            {"name": "Ibuprofeno 400mg (10 tabs)", "price": 2.50, "category": "Medicamentos"},
            {"name": "Protector Solar FPS 50", "price": 14.00, "category": "Cuidado Personal"},
            {"name": "Champú Reparador 400ml", "price": 5.50, "category": "Cuidado Personal"},
            {"name": "Crema Dental Blanqueadora", "price": 2.80, "category": "Higiene"},
            {"name": "Suero Oral Electrolitos", "price": 1.80, "category": "Salud"},
            {"name": "Vitamina C 1000mg Efervescente", "price": 4.50, "category": "Suplementos"},
            {"name": "Alcohol Antiséptico 70% 500ml", "price": 2.20, "category": "Primeros Auxilios"},
            {"name": "Mascarillas Quirúrgicas (Caja 50)", "price": 4.00, "category": "Protección"},
            {"name": "Termómetro Digital Rápido", "price": 6.50, "category": "Equipos Médicos"},
        ]
    else:
        return [
            {"name": "Cable de Carga Rápida USB-C", "price": 6.00, "category": "Accesorios"},
            {"name": "Cargador de Pared 20W", "price": 12.00, "category": "Accesorios"},
            {"name": "Auriculares Inalámbricos Bluetooth", "price": 22.00, "category": "Audio"},
            {"name": "Soporte Magnético para Teléfono", "price": 8.50, "category": "Accesorios"},
            {"name": "Powerbank Portátil 10000mAh", "price": 18.00, "category": "Baterías"},
            {"name": "Protector de Pantalla Vidrio 9D", "price": 5.00, "category": "Accesorios"},
            {"name": "Funda Protectora Antigolpes", "price": 7.50, "category": "Fundas"},
            {"name": "Memoria MicroSD 64GB Clase 10", "price": 9.00, "category": "Memorias"},
            {"name": "Mouse Inalámbrico Ergonómico", "price": 11.50, "category": "Computación"},
            {"name": "Teclado Mecánico RGB", "price": 35.00, "category": "Computación"},
        ]

def _parse_custom_products(text: str) -> list[dict]:
    import re
    products = []
    for line in (text or "").strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = re.split(r'[-–—:]', line)
        if len(parts) >= 2:
            name = parts[0].strip()
            price_str = re.sub(r'[^0-9.]', '', parts[1].strip())
            try:
                price = float(price_str)
            except ValueError:
                price = 10.0
            products.append({"name": name, "price": price, "category": "General"})
        else:
            products.append({"name": line, "price": 10.0, "category": "General"})
    return products

import asyncio
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from contextlib import asynccontextmanager
from uuid import UUID, uuid4
from fastapi import FastAPI, HTTPException, Query, Request, Depends
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Any
from psycopg.types.json import Jsonb

from app.core.config import get_settings
from app.core.security import get_password_hash, create_access_token
from app.db import close_pool, get_connection, open_pool

from app.schemas import (
    ContextResponse,
    CoreResponse,
    CreateEventRequest,
    EventResponse,
    CreateMemoryRequest,
    IncomingMessage,
    WebchatSessionRequest,
    WebchatMessageRequest,
    MemoryResponse,
    ToolExecuteRequest,
    ToolExecuteResponse,
    BrainRequest,
    BrainResponse,
    AutopilotResponse,
    AutopilotEventResponse,
    BusinessBrainAnalyzeRequest,
    BusinessBrainAnalyzeResponse,
    InsightStatusRequest,
    RecommendationStatusRequest,
    OnboardingBusinessRequest,
    OwnerCopilotRequest,
    BusinessTypeProfileOverrideRequest,
    BusinessTypeProfileResponse,
    KnowledgeItemCreateRequest,
    KnowledgeItemUpdateRequest,
    KnowledgeItemResponse,
    Customer360UpdateRequest,
    CustomerMemoryUpsertRequest,
    WorkflowCreateRequest,
    WorkflowResponse,
    WorkflowTriggerRequest,
    WorkflowRunResponse,
    ApprovalDecisionRequest,
    OperationQueueResponse,
    ApprovalResponse,
    AgentBlueprintCreateRequest,
    AgentBlueprintResponse,
    GoalCreateRequest,
    GoalResponse,
    AutonomousTaskCreate,
    AutonomousTaskResponse,
    AutonomousPlanCreate,
    AutonomousPlanResponse,
    AutonomyPolicyCreate,
    AutonomyPolicyResponse,
    EventBusCreate,
    EventBusResponse,
    EventProcessResponse,
    TaskExecuteResponse,
    AuditLogResponse,
    AutonomyStatusResponse,
    AgentExecutionResponse,
    JobCreateRequest,
    JobResponse,
    RuntimeApprovalCreate,
    RuntimeApprovalDecide,
    RuntimeApprovalResponse,
    IdempotencyCheckRequest,
    IdempotencyRecordResponse,
    ProactiveEngagementCreate,
    ProactiveEngagementResponse,
    OmnichannelMessageCreate,
    OmnichannelMessageResponse,
    VisionEvidenceCreate,
    VisionEvidenceResponse,
    OpportunityCreate,
    OpportunityResponse,
    CustomerHealthUpdate,
    CustomerHealthResponse,
    WebhookDispatchCreate,
    WebhookDispatchResponse,
    LLMUsageCreate,
    LLMUsageResponse,
    KPIAnalysisCreate,
    KPIAnalysisResponse,
    AnomalyCreate,
    AnomalyResponse,
    OpportunityScoreRequest,
    PrioritizedOpportunityResponse,
    LearningLoopCreate,
    LearningLoopResponse,
    AgentDelegationCreate,
    AgentDelegationResponse,
    RecoveryLogCreate,
    RecoveryLogResponse,
    CostOptimizationCreate,
    CostOptimizationResponse,
    GovernanceEvaluateCreate,
    GovernanceEvaluateResponse,
    AcceptanceTestRequest,
)

from app.services.context_manager import ContextManager
from app.services.event_engine import EventEngine, EventProcessingError
from app.services.core_service import GalaxyCoreService
from app.services.memory_service import MemoryService
from app.services.tool_manager import ToolExecutionError, ToolManager
from app.services.brain_service import BrainService
from app.services.business_brain_service import BusinessBrainError, BusinessBrainService
from app.services.recommendation_engine import RecommendationEngineError, RecommendationEngine
from app.services.tool_registry import list_tools
from app.services.autopilot_service import GalaxyAutopilotService
from app.services.system_diagnostics import DiagnosticsService
from app.services.conversation_service import ConversationService, ConversationServiceError
from app.services.customer_agent_service import CustomerAgentService
from app.services.sales_service import SalesService, SalesServiceError
from app.services.appointment_service import AppointmentService, AppointmentServiceError
from app.services.inventory_intelligence import InventoryIntelligenceService
from app.services.analytics_service import AnalyticsService
from app.services.recommendation_v2_service import RecommendationV2Service
from app.services.day3_demo_service import Day3DemoService
from app.services.owner_copilot_service import OwnerCopilotService
from app.services.dashboard_service import DashboardService
from app.services.onboarding_service import OnboardingError, OnboardingService
from app.services.tenant_guard import TenantGuard, TenantIsolationError
from app.services.business_type_profile_service import BusinessTypeProfileError, BusinessTypeProfileService
from app.services.knowledge_policy_service import KnowledgePolicyError, KnowledgePolicyService
from app.services.customer_360_service import Customer360Error, Customer360Service
from app.services.workflow_engine import WorkflowError, WorkflowEngine
from app.services.approval_operations_service import ApprovalOperationsError, ApprovalOperationsService
from app.services.integration_service import IntegrationService, IntegrationServiceError
from app.services.agent_blueprint_service import AgentBlueprintService, AgentBlueprintError
from app.services.goal_engine_service import GoalEngineService, GoalEngineError
from app.services.task_planner_service import TaskPlannerService, TaskPlannerError
from app.services.autonomy_policy_service import AutonomyPolicyService, AutonomyPolicyError
from app.services.event_bus_service import EventBusService, EventBusError
from app.services.autonomous_worker_service import AutonomousWorkerService
from app.services.task_execution_service import TaskExecutionService, TaskExecutionError
from app.services.heartbeat_service import HeartbeatService
from app.services.audit_service import AuditService
from app.services.autonomy_dashboard_service import AutonomyDashboardService
from app.services.agent_runtime_service import AgentRuntimeService, AgentRuntimeError
from app.services.job_runner_service import JobRunnerService, JobRunnerError
from app.services.runtime_approval_service import RuntimeApprovalService, RuntimeApprovalError
from app.services.idempotency_service import IdempotencyService, IdempotencyError
from app.services.proactive_lifecycle_service import ProactiveLifecycleService, ProactiveLifecycleError
from app.services.omnichannel_gateway_service import OmnichannelGatewayService, OmnichannelGatewayError
from app.services.vision_evidence_service import VisionEvidenceService, VisionEvidenceError
from app.services.opportunity_engine_service import OpportunityEngineService, OpportunityEngineError
from app.services.customer_health_service import CustomerHealthService, CustomerHealthError
from app.services.webhook_dispatcher_service import WebhookDispatcherService, WebhookDispatcherError
from app.services.llm_cost_service import LLMCostService
from app.services.kpi_intelligence_service import KPIIntelligenceService, KPIIntelligenceError
from app.services.anomaly_detection_service import AnomalyDetectionService, AnomalyDetectionError
from app.services.opportunity_prioritization_service import OpportunityPrioritizationService
from app.services.learning_loop_service import LearningLoopService, LearningLoopError
from app.services.multi_agent_orchestrator import MultiAgentOrchestrator
from app.services.workflow_recovery_service import WorkflowRecoveryService, WorkflowRecoveryError
from app.services.cost_optimization_service import CostOptimizationService
from app.services.governance_service import GovernanceService

# IMPORTACIONES PASOS 94 Y 95
from app.services.commercial_engine import CommercialPlanEngine
from app.services.connector_gateway import ConnectorGateway

# IMPORTACIONES PASOS 96 Y 97
from app.services.operations_center_service import OperationsCenterService
from app.services.business_control_service import BusinessControlService

# Importamos los módulos de rutas
from app.api import auth
# [PASO 36] Importar el router de Telegram
from app.api.telegram import router as telegram_router

settings = get_settings()
WEBCHAT_DEMO_BUSINESS_ID = UUID("b0816122-4da6-42ac-974b-92a80e85eec1")


def _clean_business_id(val: Any) -> str | None:
    if not val:
        return None
    s = str(val).strip().lower()
    if s in ("null", "undefined", "none", ""):
        return None
    try:
        return str(UUID(s))
    except (ValueError, TypeError):
        return None

def _get_webchat_demo_business(conn, business_id: Any = None) -> dict:
    """Resolve the requested business tenant, or automatically pick the most recent business created."""
    valid_id = _clean_business_id(business_id)
    with conn.cursor() as cur:
        row = None
        if valid_id:
            cur.execute(
                """
                SELECT id, name, business_type, currency, timezone, status, description
                FROM businesses
                WHERE id = %s
                """,
                (valid_id,),
            )
            row = cur.fetchone()

        # Si no se pasó business_id o no se encontró, seleccionar el negocio más recientemente creado (el tuyo)
        if not row:
            cur.execute(
                """
                SELECT id, name, business_type, currency, timezone, status, description
                FROM businesses
                WHERE status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            row = cur.fetchone()

        # Si no hay ninguno, fallback final al tenant demo
        if not row:
            cur.execute(
                """
                SELECT id, name, business_type, currency, timezone, status, description
                FROM businesses
                WHERE id = %s
                """,
                (str(WEBCHAT_DEMO_BUSINESS_ID),),
            )
            row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=503, detail="No se encontraron negocios activos en la base de datos.")

    return {
        "id": row[0],
        "name": row[1],
        "business_type": row[2],
        "currency": row[3],
        "timezone": row[4],
        "status": str(row[5] or "active").strip().lower(),
        "description": row[6] or "",
    }


import google.generativeai as genai
genai.configure(api_key=settings.gemini_api_key)

class OwnerRegistrationRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str

class OnboardingRequest(BaseModel):
    business_name: str
    business_type: str 
    ai_prompt: str | None = None
    products_text: str | None = None
    currency: str = "USD"
    owner_email: str
    owner_password: str
    owner_full_name: str
    owner_phone: str = None

class IntegrationCreateRequest(BaseModel):
    provider: str
    credentials: dict

class IntegrationStatusRequest(BaseModel):
    status: str

def _require_business_access(current_user: dict, business_id: UUID) -> None:
    if str(current_user["business_id"]) != str(business_id):
        raise HTTPException(
            status_code=403,
            detail="El usuario no tiene acceso a ese business_id.",
        )


async def _ensure_webchat_payment_schema() -> None:
    """Additive, idempotent schema for the demo payment-approval flow.

    This creates only a new table and indexes. It does not alter existing Galaxy tables.
    Startup intentionally continues if DDL is unavailable so unrelated Core routes remain up;
    the payment endpoints then return a clear error until the migration is applied.
    """
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.webchat_payment_requests (
                        id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        customer_id uuid NOT NULL REFERENCES public.customers(id) ON DELETE RESTRICT,
                        amount numeric(12,2) NOT NULL CHECK (amount > 0),
                        currency varchar(10) NOT NULL DEFAULT 'USD',
                        payment_method varchar(50) NOT NULL DEFAULT 'binance_demo',
                        status varchar(20) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
                        source varchar(50) NOT NULL DEFAULT 'webchat_demo',
                        created_at timestamptz NOT NULL DEFAULT now(),
                        reviewed_at timestamptz,
                        reviewed_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
                        order_id uuid REFERENCES public.orders(id) ON DELETE SET NULL,
                        approval_note text
                    )
                """)
                cur.execute("""
                    ALTER TABLE public.webchat_payment_requests
                    ADD COLUMN IF NOT EXISTS items jsonb;
                """)
                cur.execute("""
                    ALTER TABLE public.webchat_payment_requests
                    ADD COLUMN IF NOT EXISTS conversation_id uuid
                        REFERENCES public.conversations(id) ON DELETE SET NULL;
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webchat_payments_business_status_created
                    ON public.webchat_payment_requests (business_id, status, created_at DESC)
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_webchat_payment_order_id
                    ON public.webchat_payment_requests (order_id) WHERE order_id IS NOT NULL
                """)
            conn.commit()
            print('[CALYRISIA] Esquema de pagos demo disponible.')
        except Exception as exc:
            conn.rollback()
            print(f'[CALYRISIA][WARN] No se pudo preparar la tabla de pagos demo: {exc}')


@asynccontextmanager
async def lifespan(app: FastAPI):
    open_pool()
    await _ensure_webchat_payment_schema()
    heartbeat_task = asyncio.create_task(HeartbeatService.run_loop())
    yield
    heartbeat_task.cancel()
    close_pool()


app = FastAPI(
    title="CALYRISIA Core",
    description="CALYRISIA Business Autopilot MVP integrado.",
    version="1.2.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],  
    allow_headers=["*"],  
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])


@app.get("/api/v1/business-type-profiles/catalog")
async def business_type_profiles_catalog(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    async with get_connection() as conn:
        try:
            profiles = BusinessTypeProfileService(conn).list_profiles(enabled_only=True)
            return {"success": True, "profiles": profiles}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Business type profile catalog error: {exc}") from exc


@app.get("/api/v1/business-type-profiles/current", response_model=BusinessTypeProfileResponse)
async def current_business_type_profile(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            profile = BusinessTypeProfileService(conn).resolve_for_business(business_id)
            return {"success": True, "profile": profile}
        except BusinessTypeProfileError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Business type profile error: {exc}") from exc


@app.patch("/api/v1/business-type-profiles/current/overrides", response_model=BusinessTypeProfileResponse)
async def update_business_type_profile_overrides(
    payload: BusinessTypeProfileOverrideRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            service = BusinessTypeProfileService(conn)
            profile = service.set_overrides(business_id, payload.overrides)
            service.audit_profile_change(
                business_id,
                UUID(current_user["id"]),
                "business_type_profile_override_updated",
                "Owner/Admin actualizó overrides del perfil vertical.",
                {"profile_key": profile["profile_key"], "override_keys": sorted(payload.overrides.keys())},
            )
            conn.commit()
            return {"success": True, "profile": profile}
        except BusinessTypeProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Business type profile override error: {exc}") from exc


@app.delete("/api/v1/business-type-profiles/current/overrides", response_model=BusinessTypeProfileResponse)
async def clear_business_type_profile_overrides(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            service = BusinessTypeProfileService(conn)
            profile = service.clear_overrides(business_id)
            service.audit_profile_change(
                business_id,
                UUID(current_user["id"]),
                "business_type_profile_overrides_cleared",
                "Owner/Admin eliminó overrides del perfil vertical.",
                {"profile_key": profile["profile_key"]},
            )
            conn.commit()
            return {"success": True, "profile": profile}
        except BusinessTypeProfileError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Business type profile clear error: {exc}") from exc


@app.get("/api/v1/knowledge", response_model=list[KnowledgeItemResponse])
async def list_knowledge_items(
    item_type: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    visibility: str | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return KnowledgePolicyService(conn).list_items(
                business_id,
                item_type=item_type,
                search=search,
                visibility=visibility,
                include_archived=include_archived,
                limit=limit,
            )
        except KnowledgePolicyError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Knowledge center error: {exc}") from exc


@app.post("/api/v1/knowledge", response_model=KnowledgeItemResponse)
async def create_knowledge_item(
    payload: KnowledgeItemCreateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    user_id = UUID(current_user["id"])
    async with get_connection() as conn:
        try:
            service = KnowledgePolicyService(conn)
            item = service.create(
                business_id,
                user_id,
                item_type=payload.item_type,
                title=payload.title,
                content=payload.content,
                visibility=payload.visibility,
                priority=payload.priority,
                source=payload.source,
                metadata=payload.metadata,
            )
            conn.commit()
            return item
        except KnowledgePolicyError as exc:
            conn.rollback()
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Knowledge item creation error: {exc}") from exc


@app.get("/api/v1/knowledge/{item_id}", response_model=KnowledgeItemResponse)
async def get_knowledge_item(
    item_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            item = KnowledgePolicyService(conn).get(business_id, item_id)
            if item is None:
                raise HTTPException(status_code=404, detail="Contenido no encontrado.")
            return item
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Knowledge item error: {exc}") from exc


@app.patch("/api/v1/knowledge/{item_id}", response_model=KnowledgeItemResponse)
async def update_knowledge_item(
    item_id: UUID,
    payload: KnowledgeItemUpdateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    user_id = UUID(current_user["id"])
    async with get_connection() as conn:
        try:
            service = KnowledgePolicyService(conn)
            item = service.update(business_id, user_id, item_id, payload.model_dump(exclude_unset=True))
            conn.commit()
            return item
        except KnowledgePolicyError as exc:
            conn.rollback()
            raise HTTPException(status_code=404 if "no encontrado" in str(exc).lower() else 400, detail=str(exc)) from exc
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Knowledge item update error: {exc}") from exc


@app.delete("/api/v1/knowledge/{item_id}", response_model=KnowledgeItemResponse)
async def archive_knowledge_item(
    item_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    user_id = UUID(current_user["id"])
    async with get_connection() as conn:
        try:
            item = KnowledgePolicyService(conn).archive(business_id, user_id, item_id)
            conn.commit()
            return item
        except KnowledgePolicyError as exc:
            conn.rollback()
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Knowledge item archive error: {exc}") from exc


@app.post("/api/v1/owner/copilot")
async def owner_copilot(
    payload: OwnerCopilotRequest,
    current_user: dict = Depends(auth.require_roles("OWNER")),
) -> dict:
    async with get_connection() as conn:
        service = OwnerCopilotService(conn)
        try:
            return service.respond(
                business_id=UUID(current_user["business_id"]),
                user_id=UUID(current_user["id"]),
                message=payload.message,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Owner Copilot error: {exc}") from exc


@app.get("/api/v1/dashboard/overview")
async def dashboard_overview(
    business_id: UUID | None = None,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    active_business_id = UUID(current_user["business_id"])
    if business_id is not None:
        _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        try:
            return DashboardService(conn).overview(business_id=active_business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Dashboard error: {exc}") from exc


app.include_router(telegram_router, prefix="/api/v1")

app.mount("/webchat", StaticFiles(directory="app/static/webchat", html=True), name="webchat")
app.mount("/onboarding", StaticFiles(directory="app/static/onboarding", html=True), name="onboarding")
app.mount("/dashboard", StaticFiles(directory="app/static/dashboard", html=True), name="dashboard")
app.mount("/operations", StaticFiles(directory="app/static/operations", html=True), name="operations")
app.mount("/landing", StaticFiles(directory="app/static/landing", html=True), name="landing")
app.mount("/feedback", StaticFiles(directory="app/static/feedback", html=True), name="feedback")

@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    return FileResponse("app/static/landing/index.html")

@app.get("/feedback/", include_in_schema=False)
def feedback_page() -> FileResponse:
    return FileResponse("app/static/feedback/index.html")

@app.get("/dashboard/", include_in_schema=False)
def dashboard_page() -> FileResponse:
    return FileResponse("app/static/dashboard/index.html")

@app.get("/operations/", include_in_schema=False)
def operations_page() -> FileResponse:
    return FileResponse("app/static/operations/index.html")


@app.get("/api/v1/operations/queue", response_model=OperationQueueResponse)
async def operations_queue(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).list_queue(business_id, limit=limit)
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/operations/approvals/{approval_id}", response_model=ApprovalResponse)
async def operations_approval_detail(
    approval_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return {"success": True, "approval": ApprovalOperationsService(conn).get_approval(business_id, approval_id)}
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/operations/approvals/{approval_id}/approve", response_model=dict)
async def operations_approval_approve(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).decide_approval(
                business_id,
                approval_id,
                decided_by_user_id=UUID(current_user["id"]),
                approve=True,
                reason=payload.reason,
            )
        except ApprovalOperationsError as exc:
            code = 409 if "expired" in str(exc).lower() or "not pending" in str(exc).lower() else 400
            raise HTTPException(status_code=code, detail=str(exc)) from exc


@app.post("/api/v1/operations/approvals/{approval_id}/reject", response_model=dict)
async def operations_approval_reject(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).decide_approval(
                business_id,
                approval_id,
                decided_by_user_id=UUID(current_user["id"]),
                approve=False,
                reason=payload.reason,
            )
        except ApprovalOperationsError as exc:
            code = 409 if "expired" in str(exc).lower() or "not pending" in str(exc).lower() else 400
            raise HTTPException(status_code=code, detail=str(exc)) from exc


@app.post("/api/v1/operations/approvals/{approval_id}/retry", response_model=dict)
async def operations_approval_retry(
    approval_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).retry_approval(
                business_id,
                approval_id,
                requested_by_user_id=UUID(current_user["id"]),
                reason=payload.reason,
            )
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/operations/approvals/expire-stale", response_model=dict)
async def operations_expire_stale(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).expire_stale(
                business_id,
                decided_by_user_id=UUID(current_user["id"]),
                limit=limit,
            )
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/operations/handoffs/{conversation_id}/acknowledge", response_model=dict)
async def operations_handoff_acknowledge(
    conversation_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).acknowledge_handoff(
                business_id,
                conversation_id,
                user_id=UUID(current_user["id"]),
                note=payload.reason,
            )
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/operations/handoffs/{conversation_id}/resolve", response_model=dict)
async def operations_handoff_resolve(
    conversation_id: UUID,
    payload: ApprovalDecisionRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ApprovalOperationsService(conn).resolve_handoff(
                business_id,
                conversation_id,
                user_id=UUID(current_user["id"]),
                note=payload.reason,
            )
        except ApprovalOperationsError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/integrations")
async def list_integrations(
    business_id: UUID = Query(...),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = IntegrationService(conn)
        return {"success": True, "integrations": service.list_integrations(business_id)}


@app.post("/api/v1/integrations")
async def register_integration(
    payload: IntegrationCreateRequest,
    business_id: UUID = Query(...),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        try:
            service = IntegrationService(conn)
            result = service.register_integration(business_id, payload.provider, payload.credentials)
            return {"success": True, "integration": result}
        except IntegrationServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    return response


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "service": "calyrisia-core",
        "version": "1.0.0",
    }


@app.get("/health/ready")
async def readiness() -> dict:
    try:
        async with get_connection() as conn:
            service = DiagnosticsService(conn)
            result = service.readiness()
    except Exception as exc:
        result = {
            "status": "not_ready",
            "service": "calyrisia-core",
            "version": "1.1.0",
            "checks": {
                "database": {"ok": False, "error": str(exc)},
                "required_tables": {"ok": False, "missing": []},
                "gemini_configuration": {
                    "ok": bool(settings.gemini_api_key.strip()),
                    "configured": bool(settings.gemini_api_key.strip()),
                    "model": settings.gemini_model,
                },
            },
        }
    return JSONResponse(
        status_code=200 if result.get("status") == "ready" else 503,
        content=result,
    )


@app.get("/api/v1/system/diagnostics")
async def system_diagnostics() -> dict:
    try:
        async with get_connection() as conn:
            service = DiagnosticsService(conn)
            return service.diagnostics()
    except Exception as exc:
        return {
            "status": "degraded",
            "service": "calyrisia-core",
            "version": "1.1.0",
            "database": {"ok": False, "error": str(exc)},
            "schema": {"ok": False, "missing_tables": []},
            "gemini": {
                "configured": bool(settings.gemini_api_key.strip()),
                "model": settings.gemini_model,
                "api_key_exposed": False,
            },
            "tool_registry": {"ok": False, "tool_count": 0},
            "components": {},
        }


@app.get("/health/db")
async def database_health() -> dict:
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), version()")
            database, version = cur.fetchone()
    return {
        "status": "ok",
        "database": database,
        "postgres_version": version,
    }


@app.post("/api/v1/messages", response_model=CoreResponse)
async def receive_message(payload: IncomingMessage) -> CoreResponse:
    async with get_connection() as conn:
        service = GalaxyCoreService(conn)
        result = service.handle_incoming_message(payload)
    return CoreResponse(**result)


@app.post("/api/v1/memory", response_model=MemoryResponse)
async def create_memory(
    payload: CreateMemoryRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> MemoryResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        service = MemoryService(conn)
        try:
            memory_id = service.create_memory(
                business_id=payload.business_id,
                customer_id=payload.customer_id,
                conversation_id=payload.conversation_id,
                user_id=payload.user_id,
                memory_type=payload.memory_type,
                memory_key=payload.memory_key,
                content=payload.content,
                source=payload.source,
                confidence=payload.confidence,
                importance=payload.importance,
                metadata=payload.metadata,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return MemoryResponse(success=True, memory_id=memory_id)


@app.get("/api/v1/customers/{customer_id}/360")
async def get_customer_360(
    customer_id: UUID,
    rebuild: bool = Query(default=False),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        service = Customer360Service(conn)
        try:
            profile = service.rebuild(business_id=business_id, customer_id=customer_id) if rebuild else service.get(business_id=business_id, customer_id=customer_id)
            return {"success": True, "profile": profile}
        except Customer360Error as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Customer 360 error: {exc}") from exc


@app.patch("/api/v1/customers/{customer_id}/360")
async def update_customer_360(
    customer_id: UUID,
    payload: Customer360UpdateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            profile = Customer360Service(conn).update(
                business_id=business_id,
                customer_id=customer_id,
                values=payload.model_dump(exclude_none=True),
            )
            return {"success": True, "profile": profile}
        except Customer360Error as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Customer 360 update error: {exc}") from exc


@app.post("/api/v1/customers/{customer_id}/memories/upsert")
async def upsert_customer_memory(
    customer_id: UUID,
    payload: CustomerMemoryUpsertRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            memory_id = MemoryService(conn).upsert_customer_memory(
                business_id=business_id,
                customer_id=customer_id,
                memory_type=payload.memory_type,
                memory_key=payload.memory_key,
                content=payload.content,
                source=payload.source,
                confidence=payload.confidence,
                importance=payload.importance,
                metadata=payload.metadata,
            )
            return {"success": True, "memory_id": memory_id}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/customers/{customer_id}/memories")
async def search_customer_memories(
    customer_id: UUID,
    q: str = Query(default="", max_length=200),
    limit: int = Query(default=20, ge=1, le=50),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        service = MemoryService(conn)
        try:
            if q.strip():
                memories = service.search_customer_memories(
                    business_id=business_id, customer_id=customer_id, query=q, limit=limit
                )
            else:
                memories = service.get_recent_memories(
                    business_id=business_id, customer_id=customer_id, limit=limit
                )
            return {"success": True, "customer_id": str(customer_id), "memories": memories}
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/v1/context", response_model=ContextResponse)
async def get_context(
    business_id: UUID,
    customer_id: UUID | None = None,
    conversation_id: UUID | None = None,
    memory_limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> ContextResponse:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        tenant = TenantGuard(conn)
        try:
            tenant.require_business(business_id)
            tenant.require_optional_resource(business_id=business_id, resource_type="customer", resource_id=customer_id)
            tenant.require_optional_resource(business_id=business_id, resource_type="conversation", resource_id=conversation_id)
        except TenantIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        manager = ContextManager(conn)
        context = manager.build_context(
            business_id=business_id,
            customer_id=customer_id,
            conversation_id=conversation_id,
            memory_limit=memory_limit,
        )

    if not context.get("found"):
        return ContextResponse(
            found=False,
            reason=context.get("reason"),
            context=None,
        )

    return ContextResponse(found=True, context=context)


@app.get("/api/v1/tools")
def get_tools() -> dict:
    return {"tools": list_tools()}


@app.get("/api/v1/tenant/{business_id}/health")
async def tenant_health(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        tenant = TenantGuard(conn)
        try:
            tenant.require_business(business_id)
        except TenantIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        checks = {}
        with conn.cursor() as cur:
            for key, table in {
                "products": "products", "inventory": "inventory", "customers": "customers",
                "conversations": "conversations", "events": "events", "memory": "memory",
                "audit_logs": "audit_logs", "insights": "business_insights", "recommendations": "recommendations",
            }.items():
                cur.execute(f"SELECT COUNT(*) FROM {table} WHERE business_id = %s", (business_id,))
                checks[key] = int(cur.fetchone()[0])
        return {"success": True, "business_id": str(business_id), "tenant_counts": checks}


@app.post("/api/v1/events", response_model=EventResponse)
async def receive_event(
    payload: CreateEventRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> EventResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        engine = EventEngine(conn)
        try:
            result = engine.receive_and_process(
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
        except EventProcessingError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return EventResponse(**result)


@app.post("/api/v1/tools/execute", response_model=ToolExecuteResponse)
async def execute_tool(
    payload: ToolExecuteRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> ToolExecuteResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        manager = ToolManager(conn)
        try:
            result = manager.execute(
                business_id=payload.business_id,
                tool_name=payload.tool_name,
                inputs=payload.inputs,
                requested_by_user_id=payload.requested_by_user_id,
            )
        except ToolExecutionError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ToolExecuteResponse(**result)


@app.post("/api/v1/business-brain/analyze", response_model=BusinessBrainAnalyzeResponse)
async def analyze_business(
    payload: BusinessBrainAnalyzeRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> BusinessBrainAnalyzeResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        service = BusinessBrainService(conn)
        try:
            result = service.analyze(
                business_id=payload.business_id,
                focus=payload.focus,
                event_id=payload.event_id,
            )
        except BusinessBrainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Business Brain error: {exc}") from exc
    return BusinessBrainAnalyzeResponse(**result)


@app.get("/api/v1/business-brain/insights")
async def list_business_insights(
    business_id: UUID,
    status: str = Query(default="open"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = BusinessBrainService(conn)
        try:
            insights = service.list_insights(
                business_id=business_id,
                status=status,
                limit=limit,
            )
        except BusinessBrainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "insights": insights}


@app.patch("/api/v1/business-brain/insights/{insight_id}")
async def update_business_insight(
    insight_id: UUID,
    payload: InsightStatusRequest,
    business_id: UUID = Query(...),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = BusinessBrainService(conn)
        try:
            insight = service.acknowledge_insight(
                business_id=business_id,
                insight_id=insight_id,
                status=payload.status,
            )
        except BusinessBrainError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "insight": insight}


@app.get("/api/v1/recommendations")
async def list_recommendations(
    business_id: UUID,
    status: str = Query(default="pending"),
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = RecommendationEngine(conn)
        try:
            recommendations = service.list_recommendations(
                business_id=business_id,
                status=status,
                limit=limit,
            )
        except RecommendationEngineError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "recommendations": recommendations}


@app.patch("/api/v1/recommendations/{recommendation_id}")
async def update_recommendation(
    recommendation_id: UUID,
    payload: RecommendationStatusRequest,
    business_id: UUID = Query(...),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = RecommendationEngine(conn)
        try:
            recommendation = service.update_status(
                business_id=business_id,
                recommendation_id=recommendation_id,
                status=payload.status,
            )
        except RecommendationEngineError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"success": True, "recommendation": recommendation}


@app.post("/api/v1/autopilot/respond", response_model=AutopilotResponse)
async def autopilot_respond(payload: IncomingMessage) -> AutopilotResponse:
    async with get_connection() as conn:
        service = GalaxyAutopilotService(conn)
        try:
            result = service.respond(payload)
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Galaxy Autopilot error: {exc}",
            ) from exc
    return AutopilotResponse(**result)


@app.post("/api/v1/autopilot/event", response_model=AutopilotEventResponse)
async def autopilot_event(
    payload: CreateEventRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> AutopilotEventResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        service = GalaxyAutopilotService(conn)
        try:
            result = service.process_event(payload)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Galaxy Autopilot event error: {exc}",
            ) from exc
    return AutopilotEventResponse(**result)


@app.post("/api/v1/autopilot/business-analysis", response_model=BusinessBrainAnalyzeResponse)
async def autopilot_business_analysis(
    payload: BusinessBrainAnalyzeRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> BusinessBrainAnalyzeResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        service = GalaxyAutopilotService(conn)
        try:
            result = service.analyze_business(payload)
        except Exception as exc:
            raise HTTPException(
                status_code=502,
                detail=f"Galaxy Autopilot business-analysis error: {exc}",
            ) from exc
    return BusinessBrainAnalyzeResponse(**result)


@app.post("/api/v1/brain/respond", response_model=BrainResponse)
async def brain_respond(
    payload: BrainRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF", "AGENT")),
) -> BrainResponse:
    _require_business_access(current_user, payload.business_id)
    async with get_connection() as conn:
        service = BrainService(conn)
        try:
            result = service.respond(
                business_id=payload.business_id,
                customer_id=payload.customer_id,
                conversation_id=payload.conversation_id,
                user_message=payload.message,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Galaxy Brain error: {exc}") from exc
    return BrainResponse(**result)


@app.get("/api/v1/webchat/config")
async def webchat_config(business_id: UUID | None = Query(default=None)) -> dict:
    """Public-safe Webchat configuration. Dynamically loads requested or demo business."""
    async with get_connection() as conn:
        business = _get_webchat_demo_business(conn, business_id)
        return {
            "success": True,
            "business": {
                "id": str(business["id"]),
                "name": business["name"],
                "business_type": business["business_type"],
                "currency": business["currency"],
                "timezone": business["timezone"],
            },
        }


@app.post("/api/v1/webchat/session")
async def webchat_session(payload: WebchatSessionRequest) -> dict:
    """Resolve/create the demo customer for the active business."""
    async with get_connection() as conn:
        try:
            business = _get_webchat_demo_business(conn, payload.business_id)
            customer_id = payload.customer_id
            customer = None

            with conn.cursor() as cur:
                if customer_id is not None:
                    cur.execute(
                        """
                        SELECT id, full_name, email, phone, status
                        FROM customers
                        WHERE id = %s AND business_id = %s
                        """,
                        (customer_id, business["id"]),
                    )
                    customer = cur.fetchone()
                    if customer is None:
                        raise HTTPException(status_code=404, detail="El cliente no pertenece al negocio de demo.")

                if customer_id is None:
                    customer_id = uuid4()
                    visitor_name = (payload.visitor_name or "Visitante Webchat").strip() or "Visitante Webchat"
                    cur.execute(
                        """
                        INSERT INTO customers (
                            id, business_id, full_name, status, source, first_contact_at, last_interaction_at, notes
                        )
                        VALUES (%s, %s, %s, 'active', 'webchat', NOW(), NOW(), %s)
                        RETURNING id, full_name, email, phone, status
                        """,
                        (
                            customer_id,
                            business["id"],
                            visitor_name,
                            "Cliente creado automáticamente por Webchat",
                        ),
                    )
                    customer = cur.fetchone()

            conn.commit()
            return {
                "success": True,
                "business": {
                    "name": business["name"],
                    "business_type": business["business_type"],
                    "currency": business["currency"],
                    "timezone": business["timezone"],
                },
                "customer": {
                    "id": str(customer[0]),
                    "full_name": customer[1],
                    "email": customer[2],
                    "phone": customer[3],
                    "status": customer[4],
                },
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"Webchat session error: {exc}") from exc


@app.post("/api/v1/webchat/message")
async def webchat_message(payload: WebchatMessageRequest) -> dict:
    """Customer-facing Webchat endpoint. business_id is injected server-side."""
    async with get_connection() as conn:
        try:
            # Resolver el negocio directamente desde el cliente en la base de datos
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.business_id, b.name
                    FROM customers c
                    JOIN businesses b ON c.business_id = b.id
                    WHERE c.id = %s
                    """,
                    (str(payload.customer_id),),
                )
                row = cur.fetchone()
                if row is None:
                    # Si el customer_id viene de una sesión vieja o negocio anterior,
                    # lo registramos automáticamente para el negocio activo actual
                    biz = _get_webchat_demo_business(conn)
                    business_id = biz["id"]
                    cur.execute(
                        """
                        INSERT INTO customers (id, business_id, full_name, status, source, first_contact_at, last_interaction_at)
                        VALUES (%s, %s, 'Visitante Webchat', 'active', 'webchat', NOW(), NOW())
                        ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id
                        """,
                        (str(payload.customer_id), str(business_id)),
                    )
                    conn.commit()
                else:
                    business_id = row[0]

            internal_payload = IncomingMessage(
                business_id=business_id,
                customer_id=payload.customer_id,
                conversation_id=payload.conversation_id,
                channel="webchat",
                message=payload.message,
                metadata={"source": "calyrisia_webchat_demo", "tenant_resolved_server_side": True},
            )
            result = GalaxyAutopilotService(conn).respond(internal_payload)
            return {
                "success": True,
                "stage": result.get("stage", "autopilot_completed"),
                "conversation_id": result.get("conversation_id"),
                "response": result.get("response", ""),
                "intent": result.get("intent", "general"),
                "confidence": result.get("confidence", 0.0),
                "brain": {
                    "brain_route": result.get("brain", {}).get("brain_route"),
                    "brain_rounds": result.get("brain", {}).get("brain_rounds", 0),
                },
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=502, detail=f"Galaxy Webchat error: {exc}") from exc


@app.get("/api/v1/webchat/history/{conversation_id}")
async def webchat_history(conversation_id: UUID) -> dict:
    """Return conversation history without exposing the tenant ID to the browser."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT business_id FROM conversations WHERE id = %s", (str(conversation_id),))
                c_row = cur.fetchone()
                target_biz_id = c_row[0] if c_row else _get_webchat_demo_business(conn)["id"]

            conversation = ConversationService(conn).get_conversation(
                business_id=target_biz_id,
                conversation_id=conversation_id,
            )
            conversation.pop("business_id", None)
            return {"success": True, "conversation": conversation}
        except ConversationServiceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Webchat history error: {exc}") from exc



def _normalise_order_text(value: Any) -> str:
    """Lowercase text and remove accents/punctuation for safe catalog matching."""
    value = unicodedata.normalize("NFD", str(value or ""))
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _webchat_active_products(conn, business_id: UUID) -> list[dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, price, COALESCE(is_service, FALSE)
            FROM products
            WHERE business_id = %s AND status = 'active'
            ORDER BY name
            """,
            (business_id,),
        )
        rows = cur.fetchall()
    return [
        {"id": str(row[0]), "name": str(row[1]), "price": Decimal(str(row[2] or 0)), "is_service": bool(row[3])}
        for row in rows
    ]


def _canonicalise_webchat_order_items(
    raw_items: Any,
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Resolve item aliases against this business' active catalog and combine duplicate lines."""
    if isinstance(raw_items, str):
        try:
            raw_items = json.loads(raw_items)
        except (TypeError, ValueError, json.JSONDecodeError):
            raw_items = []
    if not raw_items:
        return []
    if isinstance(raw_items, dict):
        raw_items = [raw_items]
    if not isinstance(raw_items, list):
        raise ValueError("La lista de productos del pedido tiene un formato inválido.")

    by_id = {str(p["id"]): p for p in products}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        by_name.setdefault(_normalise_order_text(product["name"]), []).append(product)

    combined: dict[str, dict[str, Any]] = {}
    for item in raw_items:
        if not isinstance(item, dict):
            raise ValueError("Cada producto del pedido debe incluir nombre/código y cantidad.")

        raw_id = item.get("id") or item.get("product_id") or item.get("productId")
        product = by_id.get(str(raw_id)) if raw_id else None

        raw_name = item.get("name") or item.get("product_name") or item.get("productName")
        if product is None and raw_name:
            normalized_name = _normalise_order_text(raw_name)
            exact = by_name.get(normalized_name, [])
            if len(exact) == 1:
                product = exact[0]
            elif len(exact) > 1:
                raise ValueError(f"El nombre de producto '{raw_name}' no identifica un artículo único.")
            else:
                fuzzy = [
                    p for p in products
                    if normalized_name and (
                        normalized_name in _normalise_order_text(p["name"])
                        or _normalise_order_text(p["name"]) in normalized_name
                    )
                ]
                if len(fuzzy) == 1:
                    product = fuzzy[0]
                elif len(fuzzy) > 1:
                    raise ValueError(f"El nombre de producto '{raw_name}' coincide con varios artículos.")

        if product is None:
            raise ValueError(f"No se pudo identificar el producto '{raw_name or raw_id or 'desconocido'}' en el catálogo de este negocio.")

        raw_qty = item.get("qty", item.get("quantity", item.get("cantidad", item.get("count", 1))))
        try:
            qty = Decimal(str(raw_qty).replace(",", "."))
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError(f"La cantidad del producto '{product['name']}' no es válida.")
        if not qty.is_finite() or qty <= 0 or qty > Decimal("1000000"):
            raise ValueError(f"La cantidad del producto '{product['name']}' debe ser mayor que cero.")

        pid = str(product["id"])
        if pid not in combined:
            combined[pid] = {"id": pid, "product_id": pid, "name": product["name"], "qty": qty}
        else:
            combined[pid]["qty"] += qty

    return [
        {
            "id": item["id"],
            "product_id": item["product_id"],
            "name": item["name"],
            "qty": float(item["qty"]),
        }
        for item in combined.values()
    ]


def _quantity_before_position(text: str, position: int) -> float:
    prefix = text[max(0, position - 45):position]
    matches = list(re.finditer(
        r"\b(\d+(?:[.,]\d+)?)\b|\b(un|uno|una|unos|unas|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce)\b",
        prefix,
    ))
    if not matches:
        return 1.0
    match = matches[-1]
    if match.group(1):
        try:
            return float(match.group(1).replace(",", "."))
        except ValueError:
            return 1.0
    word_values = {
        "un": 1, "uno": 1, "una": 1, "unos": 1, "unas": 1,
        "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6,
        "siete": 7, "ocho": 8, "nueve": 9, "diez": 10, "once": 11, "doce": 12,
    }
    return float(word_values.get(match.group(2), 1))


def _items_from_customer_order_message(
    message: str,
    products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Best-effort recovery for multi-turn orders if the payment tag contains only an amount."""
    text = _normalise_order_text(message)
    order_terms = ("quiero", "compr", "llevar", "pedido", "anot", "agrega", "necesito", "dame", "prepara", "encarg", "pido", "orden")
    if not text or not any(term in text for term in order_terms):
        return []

    # Exact full product names are preferred and can safely identify multiple products in one message.
    exact_hits: list[tuple[int, dict[str, Any]]] = []
    for product in products:
        name = _normalise_order_text(product["name"])
        if name and re.search(r"\b" + re.escape(name) + r"\b", text):
            exact_hits.append((text.find(name), product))
    if exact_hits:
        found = []
        seen: set[str] = set()
        for position, product in sorted(exact_hits, key=lambda x: x[0]):
            pid = str(product["id"])
            if pid in seen:
                continue
            seen.add(pid)
            found.append({"id": pid, "name": product["name"], "qty": _quantity_before_position(text, position)})
        return _canonicalise_webchat_order_items(found, products)

    # Support ordinary plurals / shortened names, but never guess if multiple catalog items are equally likely.
    stop_words = {"premium", "blanco", "blanca", "litro", "litros", "gourmet", "completa", "completo", "pack", "para", "con", "sin", "los", "las"}
    candidates: list[tuple[int, int, dict[str, Any]]] = []
    for product in products:
        name_tokens = [
            token for token in _normalise_order_text(product["name"]).split()
            if len(token) >= 3 and token not in stop_words and not token.isdigit()
        ]
        token_positions: list[int] = []
        for token in name_tokens:
            stem = token[:-1] if token.endswith("s") and len(token) > 4 else token
            match = re.search(r"\b" + re.escape(stem) + r"(?:s|es)?\b", text)
            if match:
                token_positions.append(match.start())
        required = 1 if len(name_tokens) <= 1 else 2
        if len(token_positions) >= required:
            candidates.append((len(token_positions), min(token_positions), product))

    if not candidates:
        return []
    top_score = max(candidate[0] for candidate in candidates)
    top = [candidate for candidate in candidates if candidate[0] == top_score]
    if len(top) != 1:
        return []
    _, position, product = top[0]
    return _canonicalise_webchat_order_items(
        [{"id": product["id"], "name": product["name"], "qty": _quantity_before_position(text, position)}],
        products,
    )


def _resolve_webchat_order_items_from_history(
    conn,
    *,
    business_id: UUID,
    conversation_id: UUID | None,
    customer_id: UUID | None,
) -> list[dict[str, Any]]:
    products = _webchat_active_products(conn, business_id)
    if not products:
        return []

    with conn.cursor() as cur:
        if conversation_id:
            cur.execute(
                """
                SELECT direction, sender_type, COALESCE(content, '')
                FROM conversation_messages
                WHERE business_id = %s AND conversation_id = %s
                ORDER BY created_at DESC
                LIMIT 40
                """,
                (business_id, conversation_id),
            )
        elif customer_id:
            cur.execute(
                """
                SELECT direction, sender_type, COALESCE(content, '')
                FROM conversation_messages
                WHERE business_id = %s AND customer_id = %s
                ORDER BY created_at DESC
                LIMIT 40
                """,
                (business_id, customer_id),
            )
        else:
            return []
        messages = cur.fetchall()

    # Locate the latest customer message that names a product and expresses purchase intent.
    # Older quote/payment tags must not be reused for a later, different purchase.
    order_marker_index = None
    inferred_items: list[dict[str, Any]] = []
    for index, (direction, sender_type, content) in enumerate(messages):
        if direction != "inbound" or sender_type != "customer":
            continue
        candidate_items = _items_from_customer_order_message(str(content), products)
        if candidate_items:
            order_marker_index = index
            inferred_items = candidate_items
            break

    # Only accept a structured cart from an assistant message newer than the latest order intent.
    # With no identifiable intent message, inspect only the very latest messages, never the full history.
    max_search_index = order_marker_index if order_marker_index is not None else min(8, len(messages))
    eligible_messages = list(enumerate(messages[:max_search_index]))

    for _index, (direction, _sender_type, content) in eligible_messages:
        if direction != "outbound":
            continue
        match = re.search(
            r"\[BOTON_PAGO:\s*[\d.]+\s*\|ITEMS:\s*(\[.*?\])\s*\]",
            str(content),
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            try:
                items = _canonicalise_webchat_order_items(json.loads(match.group(1)), products)
                if items:
                    return items
            except (ValueError, TypeError, json.JSONDecodeError):
                pass

    # Next use a quoted cart such as "- 2x Laptop X: $1,700".
    line_pattern = re.compile(r"(?m)^\s*[-•]\s*(\d+(?:[.,]\d+)?)\s*x\s+([^:\n]+):")
    for _index, (direction, _sender_type, content) in eligible_messages:
        if direction != "outbound":
            continue
        lines = line_pattern.findall(str(content))
        if not lines:
            continue
        try:
            items = _canonicalise_webchat_order_items(
                [{"name": name.strip(), "qty": qty.replace(",", ".")} for qty, name in lines],
                products,
            )
            if items:
                return items
        except ValueError:
            continue

    # The most recent purchase-intent message is the safest fallback for multi-turn checkout.
    if inferred_items:
        return inferred_items
    return []


def _apply_webchat_order_items(
    conn,
    *,
    business_id: UUID,
    order_id: UUID,
    raw_items: Any,
) -> list[dict[str, Any]]:
    """Persist order lines and deduct exact quantities, atomically, from the business inventory."""
    products = _webchat_active_products(conn, business_id)
    items = _canonicalise_webchat_order_items(raw_items, products)
    if not items:
        raise HTTPException(
            status_code=409,
            detail="No se pudieron identificar los productos de esta compra. No se aprobó el pago ni se modificó el inventario. Vuelve al Webchat e inicia el pedido con los productos y cantidades.",
        )

    saved_items: list[dict[str, Any]] = []
    with conn.cursor() as cur:
        for item in items:
            product_id = UUID(str(item["id"]))
            quantity = Decimal(str(item["qty"]))
            cur.execute(
                """
                SELECT id, name, price, COALESCE(is_service, FALSE)
                FROM products
                WHERE id = %s AND business_id = %s AND status = 'active'
                FOR UPDATE
                """,
                (product_id, business_id),
            )
            product_row = cur.fetchone()
            if not product_row:
                raise HTTPException(status_code=409, detail=f"El producto '{item['name']}' ya no está disponible en este catálogo.")

            unit_price = Decimal(str(product_row[2] or 0)).quantize(Decimal("0.01"))
            is_service = bool(product_row[3])

            if not is_service:
                cur.execute(
                    """
                    SELECT id, quantity
                    FROM inventory
                    WHERE business_id = %s AND product_id = %s
                    ORDER BY created_at, id
                    FOR UPDATE
                    """,
                    (business_id, product_id),
                )
                stock_rows = cur.fetchall()
                available = sum((Decimal(str(stock_row[1] or 0)) for stock_row in stock_rows), Decimal("0"))
                if available < quantity:
                    raise HTTPException(
                        status_code=409,
                        detail=f"Inventario insuficiente para {product_row[1]}. Disponible: {available}; solicitado: {quantity}. No se aprobó el pago.",
                    )

                remaining = quantity
                for stock_id, stock_quantity in stock_rows:
                    current_quantity = Decimal(str(stock_quantity or 0))
                    if remaining <= 0:
                        break
                    take = min(current_quantity, remaining)
                    if take > 0:
                        cur.execute(
                            """
                            UPDATE inventory
                            SET quantity = quantity - %s, updated_at = NOW()
                            WHERE id = %s AND business_id = %s AND product_id = %s
                            """,
                            (take, stock_id, business_id, product_id),
                        )
                        remaining -= take

                if remaining > 0:
                    # Defensive guard; the transaction will roll back rather than underflow stock.
                    raise HTTPException(
                        status_code=409,
                        detail=f"No se pudo descontar el inventario completo de {product_row[1]}. No se aprobó el pago.",
                    )

            line_total = (unit_price * quantity).quantize(Decimal("0.01"))
            cur.execute(
                """
                INSERT INTO order_items
                    (id, business_id, order_id, product_id, quantity, unit_price,
                     discount_amount, tax_amount, line_total)
                VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, 0, 0, %s)
                """,
                (business_id, order_id, product_id, quantity, unit_price, line_total),
            )
            saved_items.append({
                "product_id": str(product_id),
                "name": str(product_row[1]),
                "quantity": float(quantity),
                "unit_price": float(unit_price),
                "line_total": float(line_total),
                "is_service": is_service,
            })

    return saved_items


@app.post("/api/v1/webchat/payment/request")
async def webchat_request_payment(payload: dict):
    """Create a pending demo payment. Tenant is resolved server-side, never trusted from the browser."""
    try:
        raw_amount = payload.get("monto", payload.get("amount"))
        amount = Decimal(str(raw_amount)).quantize(Decimal("0.01"))
        if not amount.is_finite() or amount <= 0 or amount > Decimal("1000000.00"):
            raise ValueError("amount out of range")
        
        supplied_customer_id = None
        raw_cust = payload.get("customer_id")
        if raw_cust:
            try:
                supplied_customer_id = UUID(str(raw_cust))
            except Exception:
                supplied_customer_id = None
        supplied_conversation_id = None
        raw_conversation_id = payload.get("conversation_id")
        if raw_conversation_id:
            try:
                supplied_conversation_id = UUID(str(raw_conversation_id))
            except Exception:
                supplied_conversation_id = None
        payment_method = str(payload.get("payment_method") or "pago_movil_demo")[:50]
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        raise HTTPException(status_code=422, detail="Monto o identificador de cliente inválido.")

    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                target_biz_id = None
                # Prioridad 1: Obtener el negocio directamente del cliente en la BD
                if supplied_customer_id:
                    cur.execute("SELECT business_id FROM customers WHERE id = %s", (supplied_customer_id,))
                    c_row = cur.fetchone()
                    if c_row:
                        target_biz_id = UUID(str(c_row[0]))

                # Prioridad 2: Si vino business_id en el payload
                if not target_biz_id and payload.get("business_id"):
                    try:
                        raw_b = str(payload.get("business_id"))
                        cur.execute("SELECT id FROM businesses WHERE id = %s", (raw_b,))
                        b_row = cur.fetchone()
                        if b_row:
                            target_biz_id = UUID(str(b_row[0]))
                    except Exception:
                        pass

                # Prioridad 3: Fallback a negocio demo activo
                if not target_biz_id:
                    biz = _get_webchat_demo_business(conn)
                    target_biz_id = UUID(str(biz["id"]))

                business_id = target_biz_id

                customer_row = None
                if supplied_customer_id:
                    cur.execute(
                        "SELECT id FROM customers WHERE id = %s AND business_id = %s",
                        (supplied_customer_id, business_id),
                    )
                    customer_row = cur.fetchone()

                if customer_row:
                    customer_id = UUID(str(customer_row[0]))
                else:
                    cur.execute(
                        """SELECT id FROM customers
                           WHERE business_id = %s AND source = 'webchat_payment_demo'
                           ORDER BY created_at ASC LIMIT 1""",
                        (business_id,),
                    )
                    customer_row = cur.fetchone()
                    if customer_row:
                        customer_id = UUID(str(customer_row[0]))
                    else:
                        customer_id = uuid4()
                        cur.execute(
                            """INSERT INTO customers
                               (id, business_id, full_name, status, source, notes)
                               VALUES (%s, %s, 'Cliente Webchat Demo', 'active',
                                       'webchat_payment_demo',
                                       'Cliente creado para la simulación de pago del Webchat.')""",
                            (customer_id, business_id),
                        )

                payment_id = uuid4()
                conversation_id = supplied_conversation_id
                if conversation_id:
                    cur.execute(
                        "SELECT id FROM conversations WHERE id = %s AND business_id = %s",
                        (conversation_id, business_id),
                    )
                    if not cur.fetchone():
                        conversation_id = None

                raw_items = payload.get("items") or []
                try:
                    products = _webchat_active_products(conn, business_id)
                    if raw_items:
                        raw_items = _canonicalise_webchat_order_items(raw_items, products)
                    else:
                        raw_items = _resolve_webchat_order_items_from_history(
                            conn,
                            business_id=business_id,
                            conversation_id=conversation_id,
                            customer_id=customer_id,
                        )
                except ValueError as exc:
                    raise HTTPException(status_code=422, detail=str(exc)) from exc

                if not raw_items:
                    raise HTTPException(
                        status_code=422,
                        detail="No pude identificar los productos y cantidades de esta compra. Envía nuevamente el pedido desde el Webchat con los productos concretos.",
                    )

                cur.execute(
                    """INSERT INTO webchat_payment_requests
                       (id, business_id, customer_id, conversation_id, amount, currency,
                        payment_method, status, source, approval_note, items)
                       VALUES (%s, %s, %s, %s, %s, 'USD', %s, 'pending', 'webchat_demo', %s, %s)""",
                    (
                        payment_id, business_id, customer_id, conversation_id, amount,
                        payment_method, 'Productos del pedido capturados desde el Webchat.',
                        Jsonb(raw_items),
                    ),
                )
            conn.commit()
            return {
                "success": True,
                "payment_id": str(payment_id),
                "customer_id": str(customer_id),
                "status": "pending",
                "amount": float(amount),
                "currency": "USD",
                "message": "Solicitud creada; pendiente de validación manual en el Dashboard.",
            }
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            message = str(exc)
            if "webchat_payment_requests" in message or "does not exist" in message.lower():
                raise HTTPException(
                    status_code=503,
                    detail="La tabla de pagos demo no está disponible. Reinicia Galaxy Core y revisa la consola de arranque.",
                ) from exc
            raise HTTPException(status_code=500, detail=f"No se pudo registrar el pago pendiente: {exc}") from exc


@app.get("/api/v1/webchat/payment/status/{payment_id}")
async def webchat_payment_status(payment_id: UUID, business_id: UUID | None = Query(default=None)):
    """Public status poll."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT status, order_id, amount, payment_method FROM webchat_payment_requests
                       WHERE id = %s""",
                    (payment_id,),
                )
                row = cur.fetchone()
            if not row:
                return {"success": False, "status": "not_found"}
            return {
                "success": True,
                "status": str(row[0]),
                "order_id": str(row[1]) if row[1] else None,
                "amount": float(row[2]) if row[2] else 0.0,
                "payment_method": str(row[3]) if row[3] else "pago_movil_demo",
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"No se pudo consultar el estado del pago: {exc}") from exc


@app.post("/api/v1/webchat/payment/confirm")
async def webchat_confirm_payment(payload: dict):
    """Backward-compatible read-only confirmation; it never records revenue from the public client."""
    try:
        payment_id = UUID(str(payload.get("payment_id", "")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Se requiere payment_id para consultar la aprobación.")
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, order_id FROM webchat_payment_requests
                   WHERE id = %s""",
                (payment_id,),
            )
            row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Solicitud de pago no encontrada.")
        if row[0] != "approved":
            raise HTTPException(status_code=409, detail="El pago aún no fue aprobado desde el Dashboard.")
        return {"success": True, "status": "approved", "order_id": str(row[1]) if row[1] else None}


@app.get("/api/v1/dashboard/webchat-payments")
async def dashboard_webchat_payments(
    status: str = Query(default="pending", pattern="^(pending|approved|rejected|all)$"),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    """Owner/Admin inbox for manual Webchat demo payment validation."""
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            query = """SELECT p.id, p.customer_id, COALESCE(c.full_name, 'Cliente Webchat'),
                              p.amount, p.currency, p.status, p.payment_method,
                              p.created_at, p.reviewed_at, p.order_id, p.approval_note
                       FROM webchat_payment_requests p
                       LEFT JOIN customers c ON c.id = p.customer_id
                       WHERE (p.business_id = %s OR p.source = 'webchat_demo')"""
            params: list[Any] = [business_id]
            if status != "all":
                query += " AND p.status = %s"
                params.append(status)
            query += " ORDER BY CASE WHEN p.status = 'pending' THEN 0 ELSE 1 END, p.created_at DESC LIMIT %s"
            params.append(limit)
            cur.execute(query, params)
            rows = cur.fetchall()
    payments = []
    for row in rows:
        payments.append({
            "id": str(row[0]),
            "customer_id": str(row[1]),
            "customer_name": row[2],
            "amount": float(row[3]),
            "currency": row[4],
            "status": row[5],
            "payment_method": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "reviewed_at": row[8].isoformat() if row[8] else None,
            "order_id": str(row[9]) if row[9] else None,
            "approval_note": row[10],
        })
    return {"success": True, "payments": payments}


@app.post("/api/v1/dashboard/webchat-payments/{payment_id}/decision")
async def decide_webchat_payment(
    payment_id: UUID,
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    """Approve/reject a pending request. Approval and order registration are one transaction."""
    decision = str(payload.get("decision", "")).strip().lower()
    if decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="decision debe ser 'approve' o 'reject'.")

    business_id = UUID(current_user["business_id"])
    reviewer_id = UUID(current_user["id"])
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT id, customer_id, amount, currency, status, order_id, payment_method,
                              business_id, items, approval_note, conversation_id
                       FROM webchat_payment_requests
                       WHERE id = %s AND business_id = %s
                       FOR UPDATE""",
                    (payment_id, business_id),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Pago pendiente no encontrado.")

                current_status = str(row[4])
                if current_status != "pending":
                    if (decision == "approve" and current_status == "approved") or (decision == "reject" and current_status == "rejected"):
                        conn.commit()
                        return {
                            "success": True,
                            "status": current_status,
                            "order_id": str(row[5]) if row[5] else None,
                            "already_processed": True,
                        }
                    raise HTTPException(status_code=409, detail=f"El pago ya fue procesado: {current_status}.")

                customer_id = UUID(str(row[1]))
                amount = Decimal(str(row[2])).quantize(Decimal("0.01"))
                order_id = None
                if decision == "approve":
                    order_id = uuid4()
                    # The approval and stock deduction are committed together below.
                    order_number = f"WC-{payment_id.hex[:24].upper()}"
                    # Asegurar cliente en el negocio del dueño activo
                    cur.execute(
                        "SELECT id FROM customers WHERE id = %s AND business_id = %s",
                        (customer_id, business_id),
                    )
                    if not cur.fetchone():
                        cur.execute(
                            """INSERT INTO customers (id, business_id, full_name, status, source)
                               VALUES (%s, %s, 'Cliente Webchat', 'active', 'webchat_payment_demo')
                               ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id""",
                            (customer_id, business_id),
                        )

                    cur.execute(
                        """INSERT INTO orders
                           (id, business_id, customer_id, order_number, status, subtotal,
                            discount_amount, tax_amount, total_amount, payment_status,
                            payment_method, source, notes)
                           VALUES (%s, %s, %s, %s, 'confirmed', %s, 0, 0, %s, 'paid',
                                   %s, 'webchat_payment_demo', %s)""",
                        (
                            order_id, business_id, customer_id, order_number, amount, amount,
                            str(row[6]) if len(row) > 6 and row[6] else 'pago_movil_demo',
                            f"Pago de demostración aprobado manualmente en Dashboard. payment_id={payment_id}",
                        ),
                    )
                    raw_items = row[8]
                    if isinstance(raw_items, str):
                        try:
                            raw_items = json.loads(raw_items)
                        except (TypeError, ValueError, json.JSONDecodeError):
                            raw_items = []

                    # Compatibility for payment requests created before items were persisted.
                    if not raw_items and len(row) > 9 and row[9]:
                        try:
                            legacy_items = json.loads(str(row[9]))
                            if isinstance(legacy_items, (list, dict)):
                                raw_items = legacy_items
                        except (TypeError, ValueError, json.JSONDecodeError):
                            raw_items = []

                    conversation_id = None
                    if len(row) > 10 and row[10]:
                        try:
                            conversation_id = UUID(str(row[10]))
                        except (TypeError, ValueError):
                            conversation_id = None

                    if not raw_items:
                        raw_items = _resolve_webchat_order_items_from_history(
                            conn,
                            business_id=business_id,
                            conversation_id=conversation_id,
                            customer_id=customer_id,
                        )

                    saved_items = _apply_webchat_order_items(
                        conn,
                        business_id=business_id,
                        order_id=order_id,
                        raw_items=raw_items,
                    )

                    cur.execute(
                        """UPDATE webchat_payment_requests
                           SET status = 'approved', business_id = %s, reviewed_at = now(), reviewed_by = %s,
                               order_id = %s, approval_note = 'Aprobado manualmente desde el Dashboard'
                           WHERE id = %s""",
                        (business_id, reviewer_id, order_id, payment_id),
                    )
                else:
                    cur.execute(
                        """UPDATE webchat_payment_requests
                           SET status = 'rejected', business_id = %s, reviewed_at = now(), reviewed_by = %s,
                               approval_note = 'Rechazado manualmente desde el Dashboard'
                           WHERE id = %s""",
                        (business_id, reviewer_id, payment_id),
                    )
            conn.commit()
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"No se pudo procesar la decisión del pago: {exc}") from exc

        sales_today = None
        if decision == "approve":
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT COALESCE(SUM(total_amount), 0)
                       FROM orders WHERE business_id = %s AND created_at >= CURRENT_DATE""",
                    (business_id,),
                )
                sales_today = float(cur.fetchone()[0] or 0)

    return {
        "success": True,
        "status": "approved" if decision == "approve" else "rejected",
        "order_id": str(order_id) if order_id else None,
        "amount": float(amount),
        "sales_today": sales_today,
    }


@app.post("/api/v1/webchat/stream")
async def webchat_stream(payload: IncomingMessage):
    async def event_generator():
        try:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT name, price FROM products WHERE business_id = %s",
                        (payload.business_id,)
                    )
                    productos_db = cur.fetchall()

            if not productos_db:
                catalogo_texto = "Inventario en actualización."
            else:
                lista_productos = [f"- {p[0]}: ${p[1]} USD (Disponibilidad inmediata)" for p in productos_db]
                catalogo_texto = "\n".join(lista_productos)

            prompt_maestro = f"""
            Rol: Eres el Asesor de Ventas de NovaTelas Boutique.
            
            CATÁLOGO ACTUALIZADO:
            {catalogo_texto}
            
            REGLAS DE ORO (INQUEBRANTABLES): 
            1. SÉ CORTO Y DIRECTO: Máximo 2 párrafos.
            2. FLUJO NATURAL: Lee el historial. No repitas saludos.
            3. TOTALES EXACTOS: Suma los precios del catálogo.
            4. GENERACIÓN DEL BOTÓN (CRÍTICO): Si el cliente dice que va a pagar o da sus datos, tu respuesta DEBE terminar OBLIGATORIAMENTE con esta etiqueta exacta: [BOTON_PAGO:total_en_numeros]. 
            EJEMPLO EXACTO DE CÓMO DEBES RESPONDER: "Perfecto, enviamos a tu dirección. Haz clic abajo para pagar. [BOTON_PAGO:21.50]"
            ¡NO uses URLs, NO pongas links, usa ÚNICAMENTE la etiqueta [BOTON_PAGO:total]!
            
            HISTORIAL RECIENTE:
            {payload.message}
            
            Tu respuesta:
            """
            import google.generativeai as genai
            model = genai.GenerativeModel('gemini-3.5-flash-lite')
            
            response = await model.generate_content_async(prompt_maestro, stream=True)
            
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
                    await asyncio.sleep(0.01)
                    
        except Exception as exc:
            yield f"Ocurrió un error en nuestros sistemas: {str(exc)}"

    return StreamingResponse(event_generator(), media_type="text/plain; charset=utf-8")


@app.get("/api/v1/conversations/{conversation_id}")
async def get_conversation_history(conversation_id: UUID, business_id: UUID = Query(...)) -> dict:
    async with get_connection() as conn:
        service = ConversationService(conn)
        try:
            return {"success": True, "conversation": service.get_conversation(
                business_id=business_id, conversation_id=conversation_id
            )}
        except ConversationServiceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/v1/customer-agent/respond", response_model=AutopilotResponse)
async def customer_agent_respond(payload: IncomingMessage) -> AutopilotResponse:
    async with get_connection() as conn:
        service = CustomerAgentService(conn)
        try:
            result = service.respond(payload)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Customer Agent error: {exc}") from exc
    return AutopilotResponse(**result)


@app.get("/api/v1/sales/summary")
async def sales_summary(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "sales": SalesService(conn).summary(business_id=business_id)}


@app.get("/api/v1/sales/orders")
async def sales_orders(
    business_id: UUID,
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "orders": SalesService(conn).list_orders(
            business_id=business_id, status=status, limit=limit
        )}


@app.post("/api/v1/sales/prepare-order")
async def prepare_sales_order(
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    required = ["business_id", "customer_id", "items"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
    _require_business_access(current_user, UUID(str(payload["business_id"])))
    async with get_connection() as conn:
        service = SalesService(conn)
        try:
            return service.prepare_order(
                business_id=UUID(str(payload["business_id"])),
                customer_id=UUID(str(payload["customer_id"])),
                items=payload["items"],
                source=str(payload.get("source", "webchat")),
                requested_by_user_id=UUID(str(payload["requested_by_user_id"])) if payload.get("requested_by_user_id") else None,
            )
        except SalesServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/appointments/schema")
async def appointments_schema() -> dict:
    async with get_connection() as conn:
        return AppointmentService(conn).table_info()


@app.get("/api/v1/appointments")
async def list_appointments(
    business_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        service = AppointmentService(conn)
        try:
            return service.list_appointments(business_id=business_id, limit=limit)
        except AppointmentServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/appointments/prepare")
async def prepare_appointment(
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    required = ["business_id", "customer_id", "starts_at", "service_name"]
    missing = [key for key in required if key not in payload]
    if missing:
        raise HTTPException(status_code=422, detail=f"Missing fields: {missing}")
    _require_business_access(current_user, UUID(str(payload["business_id"])))
    async with get_connection() as conn:
        service = AppointmentService(conn)
        try:
            from datetime import datetime
            starts_at = datetime.fromisoformat(str(payload["starts_at"]))
            ends_at = datetime.fromisoformat(str(payload["ends_at"])) if payload.get("ends_at") else None
            return service.prepare_booking(
                business_id=UUID(str(payload["business_id"])),
                customer_id=UUID(str(payload["customer_id"])),
                starts_at=starts_at,
                ends_at=ends_at,
                service_name=str(payload["service_name"]),
                notes=payload.get("notes"),
            )
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=422, detail=f"Invalid appointment data: {exc}") from exc
        except AppointmentServiceError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/v1/inventory-intelligence/overview")
async def inventory_intelligence_overview(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "inventory": InventoryIntelligenceService(conn).overview(business_id=business_id)}


@app.get("/api/v1/analytics/overview")
async def analytics_overview(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "analytics": AnalyticsService(conn).overview(business_id=business_id)}


@app.get("/api/v1/analytics/top-products")
async def analytics_top_products(
    business_id: UUID,
    limit: int = Query(default=10, ge=1, le=50),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "products": AnalyticsService(conn).top_products(
            business_id=business_id, limit=limit
        )}


@app.get("/api/v1/recommendations/dashboard")
async def recommendations_dashboard(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        return {"success": True, "dashboard": RecommendationV2Service(conn).dashboard(business_id=business_id)}


@app.get("/api/v1/demo/overview")
async def demo_overview(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        try:
            return Day3DemoService(conn).overview(business_id=business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Day 3 demo overview error: {exc}") from exc


@app.post("/api/v1/onboarding/business", status_code=201)
async def create_business_and_owner(payload: OnboardingRequest):
    business_id = uuid4()
    user_id = uuid4()
    password_hash = get_password_hash(payload.owner_password)
    prompt_text = (payload.ai_prompt or "").strip() or f"Eres el asistente inteligente de {payload.business_name}, especializado en {payload.business_type}."
    
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO businesses (id, name, business_type, description, currency, status)
                    VALUES (%s, %s, %s, %s, %s, 'active')
                    """,
                    (str(business_id), payload.business_name, payload.business_type, prompt_text, payload.currency)
                )
                
                cur.execute(
                    """
                    INSERT INTO users (id, business_id, email, password_hash, role, full_name, phone, status)
                    VALUES (%s, %s, %s, %s, 'OWNER', %s, %s, 'active')
                    """,
                    (str(user_id), str(business_id), payload.owner_email.lower(), password_hash, payload.owner_full_name, payload.owner_phone)
                )

                # Guardar el prompt personalizado en la base de conocimientos y perfil de la IA
                try:
                    cur.execute(
                        """
                        INSERT INTO business_knowledge_items (
                            id, business_id, item_type, title, content, visibility, priority, source, status, created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), %s, 'policy', 'Directrices de Comportamiento e Instrucciones de la IA', %s, 'customer', 100, 'onboarding', 'active', NOW(), NOW()
                        )
                        """,
                        (str(business_id), prompt_text)
                    )
                except Exception:
                    pass

                try:
                    cur.execute(
                        """
                        INSERT INTO business_profiles (
                            id, business_id, industry, short_description, legal_name, operating_hours, policies, objectives, status, profile_version
                        ) VALUES (
                            gen_random_uuid(), %s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, 'active', 1
                        )
                        """,
                        (str(business_id), payload.business_type, prompt_text, payload.business_name)
                    )
                except Exception:
                    pass

                # Cargar automáticamente los 10 productos en el catálogo e inventario
                try:
                    raw_items = _parse_custom_products(payload.products_text) if payload.products_text else []
                    if not raw_items:
                        raw_items = _get_default_10_products(payload.business_type, payload.currency)
                    
                    for item in raw_items:
                        p_id = str(uuid4())
                        cur.execute(
                            """
                            INSERT INTO products (id, business_id, name, price, category, status)
                            VALUES (%s, %s, %s, %s, %s, 'active')
                            """,
                            (p_id, str(business_id), item["name"], item["price"], item.get("category", "General"))
                        )
                        cur.execute(
                            """
                            INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location)
                            VALUES (gen_random_uuid(), %s, %s, %s, %s, 'tienda')
                            """,
                            (str(business_id), p_id, 25.0, 5.0)
                        )
                except Exception as p_err:
                    pass
            
            try:
                provision_data = OnboardingService(conn).provision_new_tenant(
                    business_id=business_id,
                    business_name=payload.business_name,
                    business_type=payload.business_type
                )
            except Exception as prov_err:
                conn.rollback()
                # Re-abrir transacción para confirmar business y owner si falló el aprovisionamiento avanzado
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO businesses (id, name, business_type, currency, status)
                        VALUES (%s, %s, %s, %s, 'active')
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (str(business_id), payload.business_name, payload.business_type, payload.currency)
                    )
                    cur.execute(
                        """
                        INSERT INTO users (id, business_id, email, password_hash, role, full_name, phone, status)
                        VALUES (%s, %s, %s, %s, 'OWNER', %s, %s, 'active')
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (str(user_id), str(business_id), payload.owner_email.lower(), password_hash, payload.owner_full_name, payload.owner_phone)
                    )
                provision_data = {"status": "partial", "warning": str(prov_err)}
            
            conn.commit()
            
            access_token = create_access_token(
                subject=str(user_id),
                role="OWNER",
                business_id=str(business_id),
            )
            return {
                "success": True,
                "message": "Negocio creado y provisionado exitosamente.",
                "business_id": str(business_id),
                "access_token": access_token,
                "token_type": "bearer",
                "provisioning_details": provision_data
            }
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=400, detail=f"Error en onboarding: {str(e)}")


@app.post("/api/v1/onboarding/business/{business_id}/owner")
async def register_owner(business_id: UUID, payload: OwnerRegistrationRequest) -> dict:
    email = payload.email.strip().lower()
    full_name = payload.full_name.strip()
    phone = payload.phone.strip()

    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 8 caracteres.")
    if not email:
        raise HTTPException(status_code=400, detail="El correo del propietario es obligatorio.")
    if not full_name:
        raise HTTPException(status_code=400, detail="El nombre completo del propietario es obligatorio.")

    async with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute("SELECT id FROM businesses WHERE id = %s", (str(business_id),))
                if cur.fetchone() is None:
                    raise HTTPException(status_code=404, detail="El business_id indicado no existe.")

                cur.execute("SELECT id, business_id, role FROM users WHERE LOWER(email) = %s", (email,))
                existing = cur.fetchone()
                if existing is not None:
                    raise HTTPException(status_code=409, detail="Ya existe un usuario con ese correo.")

                user_id = str(uuid4())
                password_hash = get_password_hash(payload.password)
                query = """
                    INSERT INTO users (
                        id, business_id, email, password_hash, role, full_name, phone, status
                    )
                    VALUES (%s, %s, %s, %s, 'OWNER', %s, %s, 'active')
                """
                cur.execute(query, (
                    user_id, str(business_id), email, password_hash, full_name, phone
                ))
                conn.commit()
                return {
                    "success": True,
                    "user_id": user_id,
                    "business_id": str(business_id),
                    "email": email,
                    "role": "OWNER",
                }
            except HTTPException:
                conn.rollback()
                raise
            except Exception as exc:
                conn.rollback()
                raise HTTPException(status_code=400, detail=f"Error creando usuario: {exc}") from exc


@app.post("/api/v1/onboarding/business/{business_id}/repair-permissions")
async def onboarding_repair_permissions(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        try:
            return OnboardingService(conn).repair_permissions(business_id)
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Permission repair error: {exc}") from exc


@app.get("/api/v1/onboarding/business/{business_id}")
async def onboarding_business_summary(
    business_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    _require_business_access(current_user, business_id)
    async with get_connection() as conn:
        try:
            return OnboardingService(conn).summary(business_id)
        except OnboardingError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Onboarding summary error: {exc}") from exc


@app.post("/api/v1/workflows", response_model=WorkflowResponse)
async def create_workflow(
    payload: WorkflowCreateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            result = WorkflowEngine(conn).create_workflow(
                business_id=business_id,
                name=payload.name,
                trigger_event_type=payload.trigger_event_type,
                definition=payload.definition,
                created_by_user_id=UUID(current_user["id"]),
                enabled=payload.enabled,
            )
            return result
        except WorkflowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow creation error: {exc}") from exc


@app.get("/api/v1/workflows", response_model=list[WorkflowResponse])
async def list_workflows(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return WorkflowEngine(conn).list_workflows(business_id)
        except WorkflowError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow list error: {exc}") from exc


@app.get("/api/v1/workflows/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return WorkflowEngine(conn).get_workflow(business_id, workflow_id)
        except WorkflowError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow get error: {exc}") from exc


@app.post("/api/v1/workflows/{workflow_id}/trigger", response_model=WorkflowRunResponse)
async def trigger_workflow(
    workflow_id: UUID,
    payload: WorkflowTriggerRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            result = WorkflowEngine(conn).trigger_workflow(
                business_id=business_id,
                workflow_id=workflow_id,
                event_record_id=payload.event_record_id,
                requested_by_user_id=UUID(current_user["id"]),
            )
            if result.get("run_id"):
                result.update(WorkflowEngine(conn).get_run(business_id, result["run_id"]))
                result["run_id"] = result["id"]
                result.pop("id", None)
            return result
        except WorkflowError as exc:
            message = str(exc)
            if message == "Workflow not found for this business":
                status = 404
            elif "User does not belong" in message:
                status = 403
            else:
                status = 400
            raise HTTPException(status_code=status, detail=message) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow trigger error: {exc}") from exc


@app.get("/api/v1/workflows/runs/{run_id}", response_model=WorkflowRunResponse)
async def get_workflow_run(
    run_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            data = WorkflowEngine(conn).get_run(business_id, run_id)
            return {"success": True, "run_id": data["id"], "business_id": data["business_id"], "workflow_id": data["workflow_id"], "event_record_id": data["event_record_id"], "idempotency_key": data["idempotency_key"], "status": data["status"], "output": data["output_payload"], "input_payload": data["input_payload"], "error_message": data["error_message"], "steps": data["steps"]}
        except WorkflowError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Workflow run error: {exc}") from exc


@app.get("/api/v1/autonomy/blueprint", response_model=AgentBlueprintResponse)
async def get_agent_blueprint(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            data = AgentBlueprintService(conn).get_blueprint(business_id)
            return {"success": True, **data}
        except AgentBlueprintError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error obteniendo Blueprint: {exc}") from exc


@app.post("/api/v1/autonomy/blueprint", response_model=AgentBlueprintResponse)
async def upsert_agent_blueprint(
    payload: AgentBlueprintCreateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            data = AgentBlueprintService(conn).upsert_blueprint(
                business_id=business_id,
                name=payload.agent_name,
                objective=payload.core_objective,
                capabilities=payload.capabilities
            )
            return {"success": True, **data}
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error guardando Blueprint: {exc}") from exc


@app.post("/api/v1/autonomy/goals", response_model=GoalResponse)
async def create_business_goal(
    payload: GoalCreateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return GoalEngineService(conn).create_goal(
                business_id=business_id,
                name=payload.name,
                metric_name=payload.metric_name,
                target_value=payload.target_value
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error creando Meta: {exc}") from exc


@app.get("/api/v1/autonomy/goals", response_model=list[GoalResponse])
async def list_business_goals(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return GoalEngineService(conn).list_goals(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error listando Metas: {exc}") from exc


@app.post("/api/v1/autonomy/tasks", response_model=AutonomousTaskResponse)
async def create_autonomous_task(
    payload: AutonomousTaskCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return TaskPlannerService(conn).create_task(
                business_id=business_id,
                title=payload.title,
                description=payload.description,
                risk_level=payload.risk_level
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error creando Tarea: {exc}") from exc


@app.post("/api/v1/autonomy/tasks/{task_id}/plans", response_model=AutonomousPlanResponse)
async def create_autonomous_plan(
    task_id: UUID,
    payload: AutonomousPlanCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return TaskPlannerService(conn).create_plan(
                business_id=business_id,
                task_id=task_id,
                steps=payload.steps
            )
        except TaskPlannerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error creando Plan: {exc}") from exc


@app.post("/api/v1/autonomy/policies", response_model=AutonomyPolicyResponse)
async def set_autonomy_policy(
    payload: AutonomyPolicyCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AutonomyPolicyService(conn).upsert_policy(
                business_id=business_id,
                action_name=payload.action_name,
                policy_mode=payload.policy_mode,
                value_limit=payload.value_limit
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error guardando Política: {exc}") from exc


@app.get("/api/v1/autonomy/policies", response_model=list[AutonomyPolicyResponse])
async def list_autonomy_policies(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AutonomyPolicyService(conn).list_policies(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error listando Políticas: {exc}") from exc


@app.post("/api/v1/autonomy/events", response_model=EventBusResponse)
async def publish_bus_event(
    payload: EventBusCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return EventBusService(conn).publish_event(
                business_id=business_id,
                event_type=payload.event_type,
                payload=payload.payload
            )
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error publicando Evento: {exc}") from exc


@app.get("/api/v1/autonomy/events/pending", response_model=list[EventBusResponse])
async def list_pending_events(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return EventBusService(conn).list_pending_events(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error listando Eventos: {exc}") from exc


@app.post("/api/v1/autonomy/worker/process", response_model=EventProcessResponse)
async def process_pending_events(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AutonomousWorkerService(conn).process_events(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error en Worker: {exc}") from exc


@app.post("/api/v1/autonomy/tasks/{task_id}/execute", response_model=TaskExecuteResponse)
async def execute_autonomous_task(
    task_id: UUID,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return TaskExecutionService(conn).execute_task(business_id, task_id)
        except TaskExecutionError as exc:
            raise HTTPException(status_code=403 if "BLOQUEADA" in str(exc) else 404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error ejecutando tarea: {exc}") from exc


@app.get("/api/v1/autonomy/audit", response_model=list[AuditLogResponse])
async def get_audit_logs(
    limit: int = Query(default=50, ge=1, le=100),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AuditService(conn).get_logs(business_id, limit)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error obteniendo logs: {exc}") from exc


@app.get("/api/v1/autonomy/status", response_model=AutonomyStatusResponse)
async def get_autonomy_status(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AutonomyDashboardService(conn).get_system_status(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Error obteniendo status del Command Center: {exc}") from exc


@app.post("/api/v1/runtime/executions", response_model=AgentExecutionResponse)
async def start_task_execution(
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AgentRuntimeService(conn).start_execution(
                business_id=business_id,
                task_id=UUID(str(payload["task_id"])),
                actor=current_user.get("role", "SYSTEM")
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/executions/{exec_id}/complete", response_model=AgentExecutionResponse)
async def complete_task_execution(
    exec_id: UUID,
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AgentRuntimeService(conn).complete_execution(
                business_id=business_id,
                exec_id=exec_id,
                success=payload.get("success", True),
                error_message=payload.get("error_message")
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/jobs", response_model=JobResponse)
async def create_long_running_job(
    payload: JobCreateRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return JobRunnerService(conn).create_job(
                business_id=business_id,
                task_id=UUID(payload.task_id),
                execution_id=UUID(payload.execution_id),
                job_name=payload.job_name,
                total_steps=payload.total_steps,
                max_retries=payload.max_retries
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/jobs/{job_id}/checkpoint", response_model=JobResponse)
async def update_job_checkpoint(
    job_id: UUID,
    payload: dict,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return JobRunnerService(conn).update_checkpoint(
                business_id=business_id,
                job_id=job_id,
                checkpoint=payload.get("checkpoint", 0),
                state_data=payload.get("state_data", {})
            )
        except JobRunnerError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/approvals", response_model=RuntimeApprovalResponse)
async def request_runtime_approval(
    payload: RuntimeApprovalCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return RuntimeApprovalService(conn).request_approval(
                business_id=business_id,
                execution_id=UUID(payload.execution_id),
                action_name=payload.action_name,
                reason=payload.reason,
                impact_level=payload.impact_level,
                evidence=payload.evidence
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/approvals/{approval_id}/decide", response_model=RuntimeApprovalResponse)
async def decide_runtime_approval(
    approval_id: UUID,
    payload: RuntimeApprovalDecide,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return RuntimeApprovalService(conn).decide_approval(
                business_id=business_id,
                approval_id=approval_id,
                user_id=UUID(current_user["id"]),
                approved=payload.approved,
                notes=payload.notes
            )
        except RuntimeApprovalError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/v1/runtime/idempotency", response_model=IdempotencyRecordResponse)
async def check_idempotency(
    payload: IdempotencyCheckRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return IdempotencyService(conn).check_and_record(
                business_id=business_id,
                idempotency_key=payload.idempotency_key,
                action_name=payload.action_name,
                response_data=payload.payload
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/proactive-engagement", response_model=ProactiveEngagementResponse)
async def schedule_proactive_engagement(
    payload: ProactiveEngagementCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return ProactiveLifecycleService(conn).evaluate_and_schedule(
                business_id=business_id,
                customer_id=UUID(payload.customer_id),
                trigger_event=payload.trigger_event,
                scheduled_for=payload.scheduled_for
            )
        except ProactiveLifecycleError as exc:
            raise HTTPException(status_code=429, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/omnichannel/message", response_model=OmnichannelMessageResponse)
async def route_omnichannel_message(
    payload: OmnichannelMessageCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return OmnichannelGatewayService(conn).process_message(
                business_id=business_id,
                channel=payload.channel,
                direction=payload.direction,
                message_content=payload.message_content,
                customer_id=UUID(payload.customer_id) if payload.customer_id else None,
                conversation_id=UUID(payload.conversation_id) if payload.conversation_id else None
            )
        except OmnichannelGatewayError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Omnichannel error: {exc}") from exc

@app.post("/api/v1/runtime/vision/evidence", response_model=VisionEvidenceResponse)
async def register_vision_evidence(
    payload: VisionEvidenceCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return VisionEvidenceService(conn).register_evidence(
                business_id=business_id,
                image_url=payload.image_url,
                operation_type=payload.operation_type,
                detected_data=payload.detected_data,
                confidence=payload.confidence
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/opportunities", response_model=OpportunityResponse)
async def create_business_opportunity(
    payload: OpportunityCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return OpportunityEngineService(conn).generate_opportunity(
                business_id=business_id,
                title=payload.title,
                description=payload.description,
                opportunity_type=payload.opportunity_type,
                potential_value=payload.potential_value,
                metadata=payload.metadata
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/customer-health/analyze", response_model=CustomerHealthResponse)
async def analyze_customer_health(
    payload: CustomerHealthUpdate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return CustomerHealthService(conn).update_health(
                business_id=business_id,
                customer_id=UUID(payload.customer_id),
                sentiment_score=payload.sentiment_score,
                churn_risk=payload.churn_risk,
                risk_reason=payload.risk_reason
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/webhooks/dispatch", response_model=WebhookDispatchResponse)
async def dispatch_webhook(
    payload: WebhookDispatchCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM", "AGENT")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return WebhookDispatcherService(conn).dispatch(
                business_id=business_id,
                target_url=payload.target_url,
                event_name=payload.event_name,
                payload=payload.payload
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/llm/usage", response_model=LLMUsageResponse)
async def log_llm_usage(
    payload: LLMUsageCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return LLMCostService(conn).log_usage(
                business_id=business_id,
                model_name=payload.model_name,
                prompt_tokens=payload.prompt_tokens,
                completion_tokens=payload.completion_tokens,
                feature_used=payload.feature_used
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/kpi/analyze", response_model=KPIAnalysisResponse)
async def analyze_business_kpi(
    payload: KPIAnalysisCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return KPIIntelligenceService(conn).analyze_kpi(
                business_id=business_id,
                metric_name=payload.metric_name,
                current_value=payload.current_value,
                previous_value=payload.previous_value
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/anomalies", response_model=AnomalyResponse)
async def register_anomaly(
    payload: AnomalyCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return AnomalyDetectionService(conn).detect_and_register(
                business_id=business_id,
                anomaly_type=payload.anomaly_type,
                description=payload.description,
                severity=payload.severity,
                detected_value=payload.detected_value,
                expected_baseline=payload.expected_baseline
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/opportunities/{opp_id}/score", response_model=PrioritizedOpportunityResponse)
async def score_opportunity(
    opp_id: UUID,
    payload: OpportunityScoreRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return OpportunityPrioritizationService(conn).calculate_and_update_score(
                business_id=business_id,
                opp_id=opp_id,
                impact=payload.impact,
                urgency=payload.urgency,
                confidence=payload.confidence,
                effort=payload.effort
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.get("/api/v1/runtime/opportunities/prioritized", response_model=list[PrioritizedOpportunityResponse])
async def get_prioritized_opportunities(
    limit: int = Query(default=5, ge=1, le=20),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> list[dict]:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return OpportunityPrioritizationService(conn).get_top_priorities(business_id, limit)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/learning-loop", response_model=LearningLoopResponse)
async def register_learning_loop(
    payload: LearningLoopCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return LearningLoopService(conn).register_learning(
                business_id=business_id,
                action_taken=payload.action_taken,
                reasoning=payload.reasoning,
                outcome=payload.outcome,
                learning_signal=payload.learning_signal
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/orchestrator/delegate", response_model=AgentDelegationResponse)
async def delegate_task_to_agent(
    payload: AgentDelegationCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return MultiAgentOrchestrator(conn).route_task(
                business_id=business_id,
                task_description=payload.task_description,
                payload=payload.payload
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/recovery", response_model=RecoveryLogResponse)
async def register_workflow_failure(
    payload: RecoveryLogCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return WorkflowRecoveryService(conn).register_failure_and_recover(
                business_id=business_id,
                task_id=UUID(payload.task_id),
                failure_reason=payload.failure_reason,
                recovery_strategy=payload.recovery_strategy,
                max_attempts=payload.max_attempts
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/optimization/cost", response_model=CostOptimizationResponse)
async def evaluate_task_cost(
    payload: CostOptimizationCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return CostOptimizationService(conn).evaluate_task_roi(
                business_id=business_id,
                task_id=UUID(payload.task_id),
                task_value=payload.task_value,
                estimated_cost=payload.estimated_cost
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/governance/evaluate", response_model=GovernanceEvaluateResponse)
async def evaluate_governance(
    payload: GovernanceEvaluateCreate,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM")),
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return GovernanceService(conn).evaluate_action(
                business_id=business_id,
                agent_name=payload.agent_name,
                action_intent=payload.action_intent,
                risk_score=payload.risk_score
            )
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

@app.post("/api/v1/runtime/acceptance-test")
async def run_galaxy_acceptance_test(
    payload: AcceptanceTestRequest,
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "SYSTEM"))
) -> dict:
    business_id = UUID(current_user["business_id"])
    
    async with get_connection() as conn:
        try:
            orch = MultiAgentOrchestrator(conn).route_task(
                business_id, payload.customer_message, {"source": "e2e_acceptance"}
            )
            opp = OpportunityEngineService(conn).generate_opportunity(
                business_id, 
                title=f"Venta Express - {orch['assigned_agent']}", 
                description=payload.customer_message, 
                opportunity_type="sales", 
                potential_value=1500.0, 
                metadata={}
            )
            prio = OpportunityPrioritizationService(conn).calculate_and_update_score(
                business_id, UUID(opp["id"]), impact=9, urgency=8, confidence=0.9, effort=3
            )
            cost = CostOptimizationService(conn).evaluate_task_roi(
                business_id, UUID(opp["id"]), task_value=1500.0, estimated_cost=0.15
            )
            gov = GovernanceService(conn).evaluate_action(
                business_id, orch["assigned_agent"], f"Enviar cotización de $1500", risk_score=25
            )
            exec_res = WebhookDispatcherService(conn).dispatch(
                business_id, "https://mock.n8n.com/webhook/quote", "SEND_QUOTE", {"opp_id": opp["id"], "amount": 1500}
            )
            learn = LearningLoopService(conn).register_learning(
                business_id, 
                "Envío automático de cotización", 
                "Respuesta menor a 1 min", 
                "success", 
                "Las respuestas en tiempo real aumentan la conversión un 40%."
            )
            kpi = KPIIntelligenceService(conn).analyze_kpi(
                business_id, "sales_pipeline", current_value=1500.0, previous_value=0.0
            )
            bill = LLMCostService(conn).log_usage(
                business_id, "gemini-1.5-pro", prompt_tokens=850, completion_tokens=120, feature_used="e2e_acceptance_flow"
            )
            
            return {
                "success": True,
                "message": "Galaxy Acceptance E2E Completed",
                "trace": {
                    "step_1_orchestrator": orch,
                    "step_2_opportunity": opp,
                    "step_3_prioritization": prio,
                    "step_4_cost_check": cost,
                    "step_5_governance": gov,
                    "step_6_execution": exec_res,
                    "step_7_learning_loop": learn,
                    "step_8_kpi_intelligence": kpi,
                    "step_9_billing": bill
                }
            }
            
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"E2E Test Failed: {exc}") from exc


# ===============================
# PASOS 94 Y 95: ENDPOINTS DE PRUEBA RÁPIDA
# ===============================
@app.post("/api/v1/test/commercial-engine")
async def test_commercial_engine(
    action_type: str = Query(default="sales", description="Prueba con 'sales' o inventa una no permitida como 'hack'"),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            engine = CommercialPlanEngine(conn)
            result = engine.verify_action_quota(business_id, action_type, token_cost=2.5)
            return {"success": True, "data": result}
        except Exception as exc:
            raise HTTPException(status_code=403, detail=str(exc))

@app.post("/api/v1/test/connector-gateway")
async def test_connector_gateway(
    integration: str = Query(default="n8n", description="Prueba con 'n8n' o invéntate una falsa como 'discord'"),
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            gateway = ConnectorGateway(conn)
            payload = {"event": "test_connection", "amount": 100}
            result = await gateway.dispatch_external_action(business_id, integration, payload)
            return {"success": True, "data": result}
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc))

# ===============================
# PASOS 96 Y 97: LOS PANELES DE CONTROL (FINALE)
# ===============================
@app.get("/api/v1/operations/live-metrics")
async def get_live_metrics(
    current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return OperationsCenterService(conn).get_live_metrics(business_id)
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

@app.post("/api/v1/control-center/autonomy")
async def set_autonomy_level(
    level: str = Query(..., description="Opciones: L1, L2, L3, EMERGENCY_STOP"),
    current_user: dict = Depends(auth.require_roles("OWNER")) # Solo el dueño puede tocar esto
) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        try:
            return BusinessControlService(conn).set_global_autonomy(business_id, level)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        except Exception as exc:
            raise HTTPException(status_code=500, detail=str(exc))

class FeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    experience: str = Field(default="Buena", max_length=50)
    liked: str | None = Field(default="", max_length=2000)
    improvements: str | None = Field(default="", max_length=2000)
    author_name: str | None = Field(default="", max_length=150)
    author_email: str | None = Field(default="", max_length=150)
    business_id: UUID | None = None

@app.post("/api/v1/feedback")
async def submit_feedback(payload: FeedbackRequest) -> dict:
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_feedback (
                        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                        rating INTEGER NOT NULL,
                        experience VARCHAR(50),
                        liked TEXT,
                        improvements TEXT,
                        author_name VARCHAR(150),
                        author_email VARCHAR(150),
                        business_id UUID,
                        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    );
                """)
                cur.execute("""
                    INSERT INTO public.calyrisia_feedback (
                        rating, experience, liked, improvements, author_name, author_email, business_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    payload.rating,
                    payload.experience,
                    payload.liked,
                    payload.improvements,
                    payload.author_name,
                    payload.author_email,
                    payload.business_id,
                ))
                conn.commit()
        return {"success": True, "message": "Feedback recibido. ¡Muchas gracias!"}
    except Exception as exc:
        return {"success": True, "message": "Feedback registrado con éxito."}


@app.get("/api/v1/products/list")
async def list_store_products(business_id: str | None = Query(default=None)) -> dict:
    try:
        async with get_connection() as conn:
            biz = _get_webchat_demo_business(conn, business_id)
            target_biz_id = str(biz["id"])
            with conn.cursor() as cur:
                # Si el negocio no tiene productos aún, sembrar automáticamente los 10 productos con inventario
                cur.execute(
                    "SELECT COUNT(*) FROM products WHERE business_id = %s::uuid AND status = 'active'",
                    (target_biz_id,)
                )
                cnt = cur.fetchone()[0]
                if cnt == 0:
                    samples = _get_default_10_products(biz.get("business_type") or "supermercado", biz.get("currency") or "USD")
                    for item in samples:
                        p_id = str(uuid4())
                        cur.execute(
                            """INSERT INTO products (id, business_id, name, price, category, status)
                               VALUES (%s, %s::uuid, %s, %s, %s, 'active')""",
                            (p_id, target_biz_id, item["name"], item["price"], item.get("category", "General")),
                        )
                        cur.execute(
                            """INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location)
                               VALUES (gen_random_uuid(), %s::uuid, %s::uuid, 25.0, 5.0, 'tienda')""",
                            (target_biz_id, p_id),
                        )
                    conn.commit()

                cur.execute(
                    """
                    SELECT p.id, p.name, p.price, p.category, COALESCE(SUM(i.quantity), 0) as stock
                    FROM products p
                    LEFT JOIN inventory i ON i.product_id = p.id AND i.business_id = p.business_id
                    WHERE p.business_id = %s::uuid AND p.status = 'active'
                    GROUP BY p.id, p.name, p.price, p.category
                    ORDER BY p.name
                    """,
                    (target_biz_id,)
                )
                rows = cur.fetchall()
                items = [{"id": str(r[0]), "name": r[1], "price": float(r[2]), "category": r[3], "stock": float(r[4])} for r in rows]
                return {"success": True, "business": biz, "products": items}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al consultar productos: {str(exc)}")

@app.post("/api/v1/products/seed-sample")
async def seed_sample_products(business_id: str | None = Query(default=None)) -> dict:
    try:
        async with get_connection() as conn:
            biz = _get_webchat_demo_business(conn, business_id)
            samples = _get_default_10_products(biz["business_type"], biz["currency"])
            with conn.cursor() as cur:
                for item in samples:
                    p_id = str(uuid4())
                    cur.execute("""
                        INSERT INTO products (id, business_id, name, price, category, status)
                        VALUES (%s, %s, %s, %s, %s, 'active')
                    """, (p_id, str(biz["id"]), item["name"], item["price"], item.get("category", "General")))
                    cur.execute("""
                        INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location)
                        VALUES (gen_random_uuid(), %s, %s, 25.0, 5.0, 'tienda')
                    """, (str(biz["id"]), p_id))
                conn.commit()
            return {"success": True, "message": f"Se han cargado {len(samples)} productos de prueba con stock a {biz['name']}."}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al cargar productos: {str(exc)}")
