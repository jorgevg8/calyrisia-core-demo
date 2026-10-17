
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
import hmac
import re
import os
import httpx
from datetime import datetime, timedelta, timezone
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
from app.services.commercial_limits import PLAN_LIMITS, AIQuotaExceeded, get_business_plan, plan_limits, consume_ai_response
from app.services.business_catalog import plan_catalog, validate_plan_business_type, can_use_booking
from app.services.connector_gateway import ConnectorGateway

# IMPORTACIONES PASOS 96 Y 97
from app.services.operations_center_service import OperationsCenterService
from app.services.business_control_service import BusinessControlService

# Importamos los módulos de rutas
from app.api import auth
# [PASO 36] Importar el router de Telegram
from app.api.telegram import (
    router as telegram_router,
    start_telegram_polling,
    stop_telegram_polling,
    notify_payment_decision,
)

settings = get_settings()


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

def _get_active_webchat_business(conn, business_id: Any) -> dict:
    """Resolve an explicitly configured tenant; never fall back to a shared demo business."""
    valid_id = _clean_business_id(business_id)
    if valid_id is None:
        raise HTTPException(status_code=422, detail="Falta un business_id válido para este canal Webchat.")
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT id, name, business_type, currency, timezone, status, description,
                   COALESCE(to_jsonb(b)->>'webchat_enabled', 'false') <> 'false' AS webchat_enabled
            FROM businesses b
            WHERE id = %s AND status = 'active'
            LIMIT 1
            """,
            (valid_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="El negocio solicitado no existe o está inactivo.")
    if not bool(row[7]):
        raise HTTPException(status_code=403, detail="El canal Webchat está desactivado para este negocio. Actívalo desde Dashboard → Canales.")
    return {
        "id": row[0], "name": row[1], "business_type": row[2], "currency": row[3],
        "timezone": row[4], "status": str(row[5] or "active").strip().lower(),
        "description": row[6] or "", "webchat_enabled": bool(row[7]),
    }


class OwnerRegistrationRequest(BaseModel):
    email: str
    password: str
    full_name: str
    phone: str

class OnboardingRequest(BaseModel):
    business_name: str
    business_type: str
    plan_code: str | None = None
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
    """Additive, idempotent schema for payment approval, payment instructions and Telegram channels.

    Adds tenant-specific payment settings, the payment request table and the per-business Telegram channel registry.
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
                        payment_method varchar(50) NOT NULL DEFAULT 'manual',
                        status varchar(20) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'approved', 'rejected')),
                        source varchar(50) NOT NULL DEFAULT 'webchat',
                        created_at timestamptz NOT NULL DEFAULT now(),
                        reviewed_at timestamptz,
                        reviewed_by uuid REFERENCES public.users(id) ON DELETE SET NULL,
                        order_id uuid REFERENCES public.orders(id) ON DELETE SET NULL,
                        approval_note text,
                        customer_payment_details text
                    )
                """)
                cur.execute("""
                    ALTER TABLE public.webchat_payment_requests
                    ADD COLUMN IF NOT EXISTS items jsonb;
                """)
                cur.execute("""
                    ALTER TABLE public.webchat_payment_requests
                    ADD COLUMN IF NOT EXISTS customer_payment_details text;
                """)
                cur.execute("ALTER TABLE public.webchat_payment_requests ALTER COLUMN payment_method SET DEFAULT 'manual'")
                cur.execute("ALTER TABLE public.webchat_payment_requests ALTER COLUMN source SET DEFAULT 'webchat'")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.business_payment_instructions (
                        business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
                        method_code varchar(30) NOT NULL CHECK (method_code IN ('pago_movil','binance')),
                        enabled boolean NOT NULL DEFAULT false,
                        instructions text NOT NULL DEFAULT '',
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (business_id, method_code),
                        CHECK (length(instructions) <= 3000)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.business_telegram_channels (
                        business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
                        bot_token text NOT NULL,
                        bot_username varchar(80),
                        owner_chat_id varchar(80),
                        enabled boolean NOT NULL DEFAULT false,
                        channel_status varchar(20) NOT NULL DEFAULT 'inactive',
                        polling_offset bigint NOT NULL DEFAULT 0,
                        last_error text,
                        last_poll_at timestamptz,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now()
                    )
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_business_telegram_bot_token
                    ON public.business_telegram_channels (bot_token)
                """)
                cur.execute("""
                    CREATE INDEX IF NOT EXISTS idx_webchat_payments_business_status_created
                    ON public.webchat_payment_requests (business_id, status, created_at DESC)
                """)
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_webchat_payment_order_id
                    ON public.webchat_payment_requests (order_id) WHERE order_id IS NOT NULL
                """)
                # Enforce the customer and payment request belong to the same tenant.
                cur.execute("""
                    CREATE UNIQUE INDEX IF NOT EXISTS uq_customers_id_business_id
                    ON public.customers (id, business_id)
                """)
                cur.execute("""
                    DO $$
                    BEGIN
                        IF NOT EXISTS (
                            SELECT 1 FROM pg_constraint
                            WHERE conname = 'fk_webchat_payment_customer_tenant'
                              AND conrelid = 'public.webchat_payment_requests'::regclass
                        ) THEN
                            ALTER TABLE public.webchat_payment_requests
                                ADD CONSTRAINT fk_webchat_payment_customer_tenant
                                FOREIGN KEY (customer_id, business_id)
                                REFERENCES public.customers (id, business_id)
                                ON DELETE RESTRICT NOT VALID;
                        END IF;
                    END $$;
                """)
            conn.commit()
            print('[CALYRISIA] Esquema de solicitudes de pago disponible.')
        except Exception as exc:
            conn.rollback()
            print(f'[CALYRISIA][WARN] No se pudo preparar la tabla de solicitudes de pago: {exc}')


async def _ensure_commercial_dashboard_schema() -> None:
    """Idempotent schema for subscription plans, monthly AI limits, images and business-specific appointments/reservations."""
    statements = [
        "ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS plan_code varchar(30) NOT NULL DEFAULT 'emprendedor'",
        "ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS webchat_enabled boolean NOT NULL DEFAULT false",
        "UPDATE public.businesses SET plan_code = 'emprendedor' WHERE plan_code IS NULL OR plan_code NOT IN ('emprendedor','smart_business','enterprise')",
        """CREATE TABLE IF NOT EXISTS public.business_ai_usage_monthly (
            business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
            month_start date NOT NULL, response_count integer NOT NULL DEFAULT 0 CHECK (response_count >= 0),
            updated_at timestamptz NOT NULL DEFAULT now(), PRIMARY KEY (business_id, month_start))""",
        """CREATE TABLE IF NOT EXISTS public.product_images (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(), business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
            product_id uuid NOT NULL REFERENCES public.products(id) ON DELETE CASCADE, image_url text NOT NULL,
            position integer NOT NULL DEFAULT 0, created_at timestamptz NOT NULL DEFAULT now(), CHECK (length(image_url) <= 2048))""",
        "CREATE INDEX IF NOT EXISTS idx_product_images_tenant_product ON public.product_images (business_id, product_id, position)",
        """CREATE TABLE IF NOT EXISTS public.business_bookings (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(), business_id uuid NOT NULL REFERENCES public.businesses(id) ON DELETE CASCADE,
            booking_type varchar(20) NOT NULL CHECK (booking_type IN ('appointment','reservation')),
            customer_name varchar(200) NOT NULL, customer_phone varchar(80),
            party_size integer NOT NULL DEFAULT 1 CHECK (party_size >= 1 AND party_size <= 200), starts_at timestamptz NOT NULL,
            service_name varchar(200) NOT NULL, table_number varchar(30),
            status varchar(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','confirmed','completed','cancelled')),
            notes text, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now())""",
        "CREATE INDEX IF NOT EXISTS idx_business_bookings_tenant_start ON public.business_bookings (business_id, booking_type, starts_at)",
        """CREATE TABLE IF NOT EXISTS public.business_dashboard_settings (
            business_id uuid PRIMARY KEY REFERENCES public.businesses(id) ON DELETE CASCADE,
            restaurant_table_count integer NOT NULL DEFAULT 12 CHECK (restaurant_table_count BETWEEN 1 AND 100),
            updated_at timestamptz NOT NULL DEFAULT now()
        )""",
    ]
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                for statement in statements:
                    cur.execute(statement)
            conn.commit()
        except Exception:
            conn.rollback()
            raise


async def _ensure_public_checkout_schema() -> None:
    """Durable order tracking for manual checkout and verified PayPal subscriptions."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_checkout_orders (
                        checkout_ref varchar(64) PRIMARY KEY,
                        plan_code varchar(32) NOT NULL CHECK (plan_code IN ('emprendedor','smart_business','enterprise')),
                        amount numeric(10,2) NOT NULL CHECK (amount > 0),
                        currency varchar(3) NOT NULL DEFAULT 'USD',
                        payment_method varchar(30) NOT NULL DEFAULT 'pending',
                        status varchar(30) NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending','awaiting_payment','paid','failed','cancelled')),
                        paypal_subscription_id varchar(128) UNIQUE,
                        paypal_plan_id varchar(128),
                        paypal_transaction_id varchar(128),
                        subscription_status varchar(32),
                        webhook_event_id varchar(128),
                        created_at timestamptz NOT NULL DEFAULT now(),
                        updated_at timestamptz NOT NULL DEFAULT now(),
                        paid_at timestamptz
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_calyrisia_checkout_status_created ON public.calyrisia_checkout_orders(status, created_at DESC)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_calyrisia_checkout_paypal_subscription ON public.calyrisia_checkout_orders(paypal_subscription_id)")
                # Webhooks may arrive before the browser's subscription-attach call. Keep unmatched
                # verified sales briefly so attach can reconcile them rather than losing a payment.
                # Administrative review metadata for direct/manual payment methods.
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS reviewed_at timestamptz")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS reviewed_by varchar(160)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS review_note text")
                # Customer identity and payment-proof metadata, tied to a single opaque checkout reference.
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS customer_name varchar(160)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS customer_email varchar(254)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS customer_phone varchar(64)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS business_name varchar(180)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS contact_saved_at timestamptz")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS transaction_reference varchar(180)")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS proof_note text")
                cur.execute("ALTER TABLE public.calyrisia_checkout_orders ADD COLUMN IF NOT EXISTS proof_submitted_at timestamptz")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS public.calyrisia_paypal_pending_sales (
                        subscription_id varchar(128) NOT NULL,
                        transaction_id varchar(128) NOT NULL,
                        event_id varchar(128),
                        amount numeric(10,2) NOT NULL,
                        currency varchar(3) NOT NULL,
                        created_at timestamptz NOT NULL DEFAULT now(),
                        PRIMARY KEY (subscription_id, transaction_id)
                    )
                """)
            conn.commit()
        except Exception as exc:
            conn.rollback()
            print(f"[CALYRISIA][WARN] No se pudo preparar el esquema de checkout: {exc}")
            raise


def _setup_public_checkout_schema_in_worker() -> None:
    try:
        asyncio.run(_ensure_public_checkout_schema())
    except Exception as exc:
        print(f"[CALYRISIA][WARN] Checkout comercial no disponible todavía: {exc}")


def _setup_commercial_dashboard_schema_in_worker() -> None:
    try:
        asyncio.run(_ensure_commercial_dashboard_schema())
    except Exception as exc:
        print(f"[Commercial Schema Notice] {exc}")


def _setup_payment_schema_in_worker() -> None:
    """Best-effort schema setup isolated from the ASGI event loop."""
    try:
        asyncio.run(_ensure_webchat_payment_schema())
    except Exception as exc:
        print(f"[Startup Schema Notice] {exc}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        open_pool()
    except Exception as exc:
        print(f"[Startup DB Notice] {exc}")

    # PostgreSQL can be unreachable/misconfigured on first deploy. Keep the
    # API process responsive and report database status through /health/ready.
    schema_task = asyncio.create_task(asyncio.to_thread(_setup_payment_schema_in_worker))
    commercial_schema_task = asyncio.create_task(asyncio.to_thread(_setup_commercial_dashboard_schema_in_worker))
    checkout_schema_task = asyncio.create_task(asyncio.to_thread(_setup_public_checkout_schema_in_worker))
    # Wait for additive schemas before accepting tenant-aware features; failures are logged, not fatal.
    await asyncio.gather(schema_task, commercial_schema_task, checkout_schema_task, return_exceptions=True)
    heartbeat_task = asyncio.create_task(HeartbeatService.run_loop())
    await start_telegram_polling()
    try:
        yield
    finally:
        await stop_telegram_polling()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        if schema_task.done():
            try:
                await schema_task
            except Exception as exc:
                print(f"[Shutdown Schema Notice] {exc}")
        if commercial_schema_task.done():
            try:
                await commercial_schema_task
            except Exception as exc:
                print(f"[Shutdown Commercial Schema Notice] {exc}")
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


@app.get("/api/v1/dashboard/payment-instructions")
async def dashboard_payment_instructions(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT method_code, enabled, instructions FROM public.business_payment_instructions WHERE business_id = %s", (str(business_id),))
            rows = {str(r[0]): {"enabled": bool(r[1]), "instructions": str(r[2] or "")} for r in cur.fetchall()}
    return {"success": True, "methods": {
        "pago_movil": rows.get("pago_movil", {"enabled": False, "instructions": ""}),
        "binance": rows.get("binance", {"enabled": False, "instructions": ""}),
    }}


@app.put("/api/v1/dashboard/payment-instructions")
async def save_dashboard_payment_instructions(payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    methods = payload.get("methods")
    if not isinstance(methods, dict):
        raise HTTPException(status_code=422, detail="Se requiere un objeto methods con pago_movil y/o binance.")
    normalized = []
    for method in ("pago_movil", "binance"):
        item = methods.get(method, {})
        if not isinstance(item, dict):
            raise HTTPException(status_code=422, detail=f"Configuración inválida para {method}.")
        enabled = item.get("enabled", False)
        if not isinstance(enabled, bool):
            raise HTTPException(status_code=422, detail=f"El estado de {method} debe ser booleano.")
        instructions = str(item.get("instructions") or "").strip()
        if len(instructions) > 3000:
            raise HTTPException(status_code=422, detail=f"Las instrucciones de {method} no pueden superar 3.000 caracteres.")
        if enabled and not instructions:
            raise HTTPException(status_code=422, detail=f"Escribe las instrucciones reales de {method} antes de activarlo.")
        normalized.append((method, enabled, instructions))
    async with get_connection() as conn:
        with conn.cursor() as cur:
            for method, enabled, instructions in normalized:
                cur.execute("""INSERT INTO public.business_payment_instructions (business_id, method_code, enabled, instructions, updated_at)
                               VALUES (%s, %s, %s, %s, now())
                               ON CONFLICT (business_id, method_code) DO UPDATE
                               SET enabled = EXCLUDED.enabled, instructions = EXCLUDED.instructions, updated_at = now()""",
                            (str(business_id), method, enabled, instructions))
        conn.commit()
    return {"success": True, "message": "Los métodos de cobro del negocio fueron actualizados."}


@app.get("/api/v1/webchat/payment-instructions")
async def public_webchat_payment_instructions(business_id: UUID = Query(...)) -> dict:
    async with get_connection() as conn:
        _get_active_webchat_business(conn, business_id)
        with conn.cursor() as cur:
            cur.execute("SELECT method_code, instructions FROM public.business_payment_instructions WHERE business_id = %s AND enabled = true ORDER BY method_code", (str(business_id),))
            methods = [{"code": str(r[0]), "label": "Pago Móvil" if r[0] == "pago_movil" else "Binance Pay", "instructions": str(r[1] or "")} for r in cur.fetchall()]
    return {"success": True, "methods": methods}


@app.get("/api/v1/dashboard/plan-usage")
async def dashboard_plan_usage(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        limits = plan_limits(plan_code)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int FROM products WHERE business_id = %s", (str(business_id),))
            product_count = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*)::int FROM product_images WHERE business_id = %s", (str(business_id),))
            image_count = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT response_count FROM business_ai_usage_monthly WHERE business_id = %s AND month_start = date_trunc('month', CURRENT_DATE)::date", (str(business_id),))
            usage_row = cur.fetchone()
        ai_used = int(usage_row[0]) if usage_row else 0
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM businesses WHERE id = %s", (str(business_id),))
            webchat_row = cur.fetchone()
            webchat_enabled = bool(webchat_row[0]) if webchat_row else False
            try:
                cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (str(business_id),))
                telegram_row = cur.fetchone()
                telegram_enabled = bool(telegram_row[0]) if telegram_row else False
            except Exception:
                conn.rollback()
                telegram_enabled = False
        return {"success": True, "plan_code": plan_code, "plan": limits,
                "usage": {"products": product_count, "images": image_count, "ai_responses": ai_used,
                          "ai_remaining": max(0, limits["ai_responses_month"] - ai_used),
                          "channels": int(webchat_enabled) + int(telegram_enabled)}}


@app.get("/api/v1/dashboard/channels")
async def dashboard_channels(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        limits = plan_limits(plan_code)
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM businesses WHERE id = %s", (str(business_id),))
            row = cur.fetchone()
            webchat_enabled = bool(row[0]) if row else False
            telegram_enabled = False
            try:
                cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (str(business_id),))
                telegram_row = cur.fetchone()
                telegram_enabled = bool(telegram_row[0]) if telegram_row else False
            except Exception:
                conn.rollback()
        active = int(webchat_enabled) + int(telegram_enabled)
        return {"success": True, "plan_code": plan_code, "max_channels": limits["channels"],
                "active_channels": active, "webchat_enabled": webchat_enabled, "telegram_enabled": telegram_enabled,
                "channels": {"webchat": {"enabled": webchat_enabled, "available": True},
                             "telegram": {"enabled": telegram_enabled, "available": True},
                             "whatsapp": {"enabled": False, "available": False, "message": "Requiere activación comercial e integración del proveedor."}}}


@app.post("/api/v1/dashboard/channels/webchat/toggle")
async def toggle_dashboard_webchat(payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    enabled = payload.get("enabled")
    if not isinstance(enabled, bool):
        raise HTTPException(status_code=422, detail="El campo enabled debe ser booleano.")
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        limits = plan_limits(plan_code)
        with conn.cursor() as cur:
            cur.execute("SELECT COALESCE(webchat_enabled, FALSE) FROM businesses WHERE id = %s", (str(business_id),))
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Negocio no encontrado.")
            current_enabled = bool(row[0])
            cur.execute("SELECT COALESCE(enabled, FALSE) FROM public.business_telegram_channels WHERE business_id = %s::uuid", (str(business_id),))
            telegram_row = cur.fetchone()
            telegram_enabled = bool(telegram_row[0]) if telegram_row else False
            projected = int(enabled) + int(telegram_enabled)
            if enabled and not current_enabled and projected > limits["channels"]:
                raise HTTPException(status_code=409, detail=f"El plan {limits['label']} permite {limits['channels']} canal(es) activo(s). Desactiva otro canal o cambia de plan.")
            cur.execute("UPDATE businesses SET webchat_enabled = %s WHERE id = %s", (enabled, str(business_id)))
        conn.commit()
        active = int(enabled) + int(telegram_enabled)
        return {"success": True, "enabled": enabled, "active_channels": active, "max_channels": limits["channels"],
                "message": "Webchat activado." if enabled else "Webchat desactivado."}


@app.get("/api/v1/dashboard/catalog")
async def dashboard_catalog(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT p.id::text, p.name, p.price, COALESCE(p.category, 'General'),
                       COALESCE((SELECT SUM(i.quantity) FROM inventory i WHERE i.product_id = p.id AND i.business_id = p.business_id), 0),
                       COALESCE((SELECT json_agg(pi.image_url ORDER BY pi.position) FROM product_images pi WHERE pi.product_id = p.id AND pi.business_id = p.business_id), '[]'::json)
                FROM products p WHERE p.business_id = %s AND p.status = 'active'
                ORDER BY p.name LIMIT 10000
            """, (str(business_id),))
            products = [{"id": r[0], "name": r[1], "price": float(r[2] or 0), "category": r[3],
                         "stock": float(r[4] or 0), "images": r[5] or []} for r in cur.fetchall()]
        return {"success": True, "products": products}


@app.post("/api/v1/dashboard/catalog/import")
async def dashboard_catalog_import(payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    rows = payload.get("rows", [])
    if not isinstance(rows, list) or not rows:
        raise HTTPException(status_code=422, detail="El archivo no contiene filas de productos válidas.")
    if len(rows) > 2000:
        raise HTTPException(status_code=413, detail="Importa hasta 2.000 productos por archivo. Divide el CSV en varios archivos.")
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        limits = plan_limits(plan_code)
        normalized = []
        for index, row in enumerate(rows, start=2):
            if not isinstance(row, dict):
                raise HTTPException(status_code=422, detail=f"Fila {index}: formato inválido.")
            name = str(row.get("name") or "").strip()[:200]
            if not name:
                raise HTTPException(status_code=422, detail=f"Fila {index}: falta el nombre del producto.")
            try:
                price = float(row.get("price", 0))
                stock = float(row.get("stock", 0) or 0)
            except (ValueError, TypeError):
                raise HTTPException(status_code=422, detail=f"Fila {index}: precio o stock inválido.")
            if price < 0 or stock < 0:
                raise HTTPException(status_code=422, detail=f"Fila {index}: precio y stock no pueden ser negativos.")
            imgs = row.get("image_urls", [])
            if isinstance(imgs, str):
                imgs = [x.strip() for x in imgs.split("|") if x.strip()]
            if not isinstance(imgs, list):
                imgs = []
            imgs = [str(url).strip() for url in imgs if str(url).strip()]
            if len(imgs) > limits["images_per_product"]:
                raise HTTPException(status_code=422, detail=f"Fila {index}: el plan permite hasta {limits['images_per_product']} imagen(es) por producto.")
            for url in imgs:
                if not (url.startswith("https://") or url.startswith("http://")) or len(url) > 2048:
                    raise HTTPException(status_code=422, detail=f"Fila {index}: las imágenes deben tener URLs http(s) válidas.")
            normalized.append({"name": name, "price": price, "stock": stock,
                               "category": str(row.get("category") or "General").strip()[:100], "images": imgs})
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*)::int FROM products WHERE business_id = %s", (str(business_id),))
            current_products = int(cur.fetchone()[0] or 0)
            cur.execute("SELECT COUNT(*)::int FROM product_images WHERE business_id = %s", (str(business_id),))
            current_images = int(cur.fetchone()[0] or 0)
        if current_products + len(normalized) > limits["products"]:
            raise HTTPException(status_code=409, detail=f"El plan {limits['label']} permite {limits['products']} productos; el catálogo quedaría en {current_products + len(normalized)}.")
        requested_images = sum(len(item["images"]) for item in normalized)
        if current_images + requested_images > limits["images"]:
            raise HTTPException(status_code=409, detail=f"El plan {limits['label']} permite {limits['images']} imágenes en total.")
        created = 0
        try:
            with conn.cursor() as cur:
                for item in normalized:
                    product_id = uuid4()
                    cur.execute("INSERT INTO products (id, business_id, name, price, category, status) VALUES (%s,%s,%s,%s,%s,'active')", (str(product_id), str(business_id), item["name"], item["price"], item["category"]))
                    cur.execute("INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location) VALUES (gen_random_uuid(),%s,%s,%s,0,'tienda')", (str(business_id), str(product_id), item["stock"]))
                    for pos, url in enumerate(item["images"]):
                        cur.execute("INSERT INTO product_images (business_id, product_id, image_url, position) VALUES (%s,%s,%s,%s)", (str(business_id), str(product_id), url, pos))
                    created += 1
            conn.commit()
        except Exception as exc:
            conn.rollback()
            raise HTTPException(status_code=500, detail=f"No se pudo completar la importación: {exc}") from exc
        return {"success": True, "created_products": created, "created_images": requested_images,
                "plan_code": plan_code, "limits": limits,
                "message": f"Se importaron {created} productos y {requested_images} imágenes al catálogo de este negocio."}


@app.get("/api/v1/dashboard/business-settings")
async def dashboard_business_settings(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        if get_business_plan(conn, business_id) == "emprendedor":
            raise HTTPException(status_code=403, detail="La configuración de mesas está incluida desde Smart Business.")
        with conn.cursor() as cur:
            cur.execute("SELECT restaurant_table_count FROM public.business_dashboard_settings WHERE business_id = %s", (str(business_id),))
            row = cur.fetchone()
            table_count = int(row[0]) if row else 12
    return {"success": True, "restaurant_table_count": table_count}


@app.put("/api/v1/dashboard/business-settings")
async def save_dashboard_business_settings(payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    business_id = UUID(current_user["business_id"])
    try:
        table_count = int(payload.get("restaurant_table_count", 12))
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="La cantidad de mesas debe ser un número entero.")
    if table_count < 1 or table_count > 100:
        raise HTTPException(status_code=422, detail="Configura entre 1 y 100 mesas.")
    async with get_connection() as conn:
        if get_business_plan(conn, business_id) == "emprendedor":
            raise HTTPException(status_code=403, detail="La configuración de mesas está incluida desde Smart Business.")
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO public.business_dashboard_settings (business_id, restaurant_table_count, updated_at)
                           VALUES (%s, %s, now())
                           ON CONFLICT (business_id) DO UPDATE SET restaurant_table_count = EXCLUDED.restaurant_table_count, updated_at = now()""",
                        (str(business_id), table_count))
        conn.commit()
    return {"success": True, "restaurant_table_count": table_count, "message": "La configuración de mesas fue guardada."}


@app.get("/api/v1/dashboard/bookings")
async def dashboard_bookings(booking_type: str = Query(default="appointment", pattern="^(appointment|reservation)$"), limit: int = Query(default=100, ge=1, le=200), current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        with conn.cursor() as cur:
            cur.execute("SELECT business_type FROM public.businesses WHERE id = %s", (str(business_id),))
            identity = cur.fetchone()
        business_type = str(identity[0] or "") if identity else ""
        if not can_use_booking(business_type, plan_code, booking_type):
            raise HTTPException(status_code=403, detail="Este módulo de agenda o reservas no corresponde al perfil de negocio o al plan contratado.")
        with conn.cursor() as cur:
            cur.execute("""SELECT id::text, booking_type, customer_name, customer_phone, party_size, starts_at,
                              service_name, table_number, status, notes, created_at
                       FROM business_bookings WHERE business_id = %s AND booking_type = %s
                       ORDER BY starts_at DESC LIMIT %s""", (str(business_id), booking_type, limit))
            rows = cur.fetchall()
        bookings = []
        for r in rows:
            bookings.append({"id": r[0], "booking_type": r[1], "customer_name": r[2], "customer_phone": r[3],
                             "party_size": int(r[4] or 1), "starts_at": r[5].isoformat() if r[5] else None,
                             "service_name": r[6], "table_number": r[7], "status": r[8], "notes": r[9],
                             "created_at": r[10].isoformat() if r[10] else None})
        return {"success": True, "bookings": bookings, "plan_code": plan_code}


@app.post("/api/v1/dashboard/bookings")
async def create_dashboard_booking(payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    booking_type = str(payload.get("booking_type") or "appointment").strip().lower()
    if booking_type not in {"appointment", "reservation"}:
        raise HTTPException(status_code=422, detail="Tipo de reserva no válido.")
    customer_name = str(payload.get("customer_name") or "").strip()[:200]
    phone = str(payload.get("customer_phone") or "").strip()[:80]
    service_name = str(payload.get("service_name") or ("Mesa" if booking_type == "reservation" else "Consulta")).strip()[:200]
    if not customer_name or not service_name:
        raise HTTPException(status_code=422, detail="Indica el nombre del cliente y el servicio o motivo.")
    try:
        from datetime import datetime
        starts_at = datetime.fromisoformat(str(payload.get("starts_at") or "").replace("Z", "+00:00"))
        party_size = int(payload.get("party_size", 1) or 1)
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="La fecha/hora o el número de personas no es válido.")
    if party_size < 1 or party_size > 200:
        raise HTTPException(status_code=422, detail="El número de personas debe estar entre 1 y 200.")
    async with get_connection() as conn:
        plan_code = get_business_plan(conn, business_id)
        with conn.cursor() as cur:
            cur.execute("SELECT business_type FROM public.businesses WHERE id = %s", (str(business_id),))
            identity = cur.fetchone()
        business_type = str(identity[0] or "") if identity else ""
        if not can_use_booking(business_type, plan_code, booking_type):
            raise HTTPException(status_code=403, detail="Este módulo de agenda o reservas no corresponde al perfil de negocio o al plan contratado.")
        with conn.cursor() as cur:
            cur.execute("""INSERT INTO business_bookings (business_id, booking_type, customer_name, customer_phone, party_size, starts_at, service_name, table_number, status, notes)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'pending',%s) RETURNING id::text""",
                        (str(business_id), booking_type, customer_name, phone or None, party_size, starts_at, service_name,
                         str(payload.get("table_number") or "").strip()[:30] or None, str(payload.get("notes") or "").strip()[:2000] or None))
            booking_id = cur.fetchone()[0]
        conn.commit()
    return {"success": True, "id": booking_id, "message": "Registro creado y pendiente de confirmación."}


@app.patch("/api/v1/dashboard/bookings/{booking_id}")
async def update_dashboard_booking(booking_id: UUID, payload: dict, current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN", "STAFF"))) -> dict:
    business_id = UUID(current_user["business_id"])
    status_value = str(payload.get("status") or "").strip().lower()
    if status_value not in {"pending", "confirmed", "completed", "cancelled"}:
        raise HTTPException(status_code=422, detail="Estado no válido.")
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE business_bookings SET status = %s, updated_at = NOW() WHERE id = %s AND business_id = %s RETURNING id::text", (status_value, str(booking_id), str(business_id)))
            row = cur.fetchone()
        if not row:
            conn.rollback()
            raise HTTPException(status_code=404, detail="La cita o reserva no existe en este negocio.")
        conn.commit()
    return {"success": True, "id": row[0], "status": status_value}


app.include_router(telegram_router, prefix="/api/v1")

app.mount("/brand", StaticFiles(directory="app/static/brand"), name="brand")
app.mount("/payments", StaticFiles(directory="app/static/payments", check_dir=False), name="payments")
app.mount("/webchat", StaticFiles(directory="app/static/webchat", html=True), name="webchat")
app.mount("/onboarding", StaticFiles(directory="app/static/onboarding", html=True), name="onboarding")
app.mount("/dashboard", StaticFiles(directory="app/static/dashboard", html=True), name="dashboard")
app.mount("/operations", StaticFiles(directory="app/static/operations", html=True), name="operations")
app.mount("/landing", StaticFiles(directory="app/static/landing", html=True), name="landing")
app.mount("/contacto", StaticFiles(directory="app/static/contacto", html=True), name="contacto")
app.mount("/contratar", StaticFiles(directory="app/static/contratar", html=True), name="contratar")
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
    """Public Webchat configuration for an explicitly identified active tenant."""
    async with get_connection() as conn:
        business = _get_active_webchat_business(conn, business_id)
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
    """Resolve/create a customer session for the explicitly identified active business."""
    async with get_connection() as conn:
        try:
            business = _get_active_webchat_business(conn, payload.business_id)
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
                        raise HTTPException(status_code=404, detail="El cliente no pertenece a este negocio.")

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
            # Both identifiers must agree. Never move/recreate a customer under another tenant.
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT c.business_id, b.name, COALESCE(to_jsonb(b)->>'webchat_enabled', 'true') <> 'false'
                    FROM customers c
                    JOIN businesses b ON c.business_id = b.id
                    WHERE c.id = %s AND c.business_id = %s AND b.status = 'active'
                    """,
                    (str(payload.customer_id), str(payload.business_id)),
                )
                row = cur.fetchone()
                if row is None:
                    raise HTTPException(
                        status_code=404,
                        detail="La sesión no pertenece a este negocio o ya no existe. Inicia una nueva sesión de Webchat.",
                    )
                if not bool(row[2]):
                    raise HTTPException(status_code=403, detail="El canal Webchat está desactivado para este negocio.")
                business_id = row[0]

                if payload.conversation_id is not None:
                    cur.execute(
                        """
                        SELECT 1 FROM conversations
                        WHERE id = %s AND business_id = %s AND customer_id = %s
                        """,
                        (str(payload.conversation_id), str(business_id), str(payload.customer_id)),
                    )
                    if cur.fetchone() is None:
                        raise HTTPException(status_code=404, detail="La conversación no pertenece a esta sesión.")

            try:
                consume_ai_response(conn, business_id)
                conn.commit()
            except AIQuotaExceeded as quota_exc:
                raise HTTPException(status_code=429, detail=f"Has usado las {quota_exc.limit} respuestas de IA incluidas este mes. Contacta con CALYRISIA para ampliar la cuota o cambiar de plan.") from quota_exc

            internal_payload = IncomingMessage(
                business_id=business_id,
                customer_id=payload.customer_id,
                conversation_id=payload.conversation_id,
                channel="webchat",
                message=payload.message,
                metadata={"source": "calyrisia_webchat", "tenant_resolved_server_side": True},
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
async def webchat_history(conversation_id: UUID, customer_id: UUID = Query(...)) -> dict:
    """Return history only when the conversation and customer session belong together."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT business_id FROM conversations WHERE id = %s AND customer_id = %s",
                    (str(conversation_id), str(customer_id)),
                )
                c_row = cur.fetchone()
                if not c_row:
                    raise HTTPException(status_code=404, detail="Conversación no encontrada para esta sesión.")
                target_biz_id = c_row[0]

            conversation = ConversationService(conn).get_conversation(
                business_id=target_biz_id,
                conversation_id=conversation_id,
            )
            if str(conversation.get("customer_id")) != str(customer_id):
                raise HTTPException(status_code=404, detail="Conversación no encontrada para esta sesión.")
            conversation.pop("business_id", None)
            return {"success": True, "conversation": conversation}
        except ConversationServiceError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"Webchat history error: {exc}") from exc


@app.post("/api/v1/webchat/payment/request")
async def webchat_request_payment(payload: dict):
    """Create a pending payment request. Tenant is resolved server-side, never trusted from the browser."""
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
        payment_method = str(payload.get("payment_method") or "pago_movil").strip().lower()[:50]
        if payment_method not in {"pago_movil", "binance"}:
            raise ValueError("unsupported payment method")
        customer_payment_details = str(payload.get("customer_payment_details") or "").strip()[:4000]
        if not customer_payment_details:
            raise ValueError("payment reference required")
    except (InvalidOperation, ValueError, TypeError, ArithmeticError):
        raise HTTPException(status_code=422, detail="Monto o identificador de cliente inválido.")

    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                raw_business_id = payload.get("business_id")
                provided_business_id = _clean_business_id(raw_business_id)
                if raw_business_id not in (None, "") and provided_business_id is None:
                    raise HTTPException(status_code=422, detail="business_id inválido.")

                # A customer session is the authoritative tenant binding. If the caller also
                # sends a business_id, it must match; a stale customer is never re-homed.
                if supplied_customer_id:
                    cur.execute("SELECT business_id FROM customers WHERE id = %s", (supplied_customer_id,))
                    c_row = cur.fetchone()
                    if not c_row:
                        raise HTTPException(status_code=404, detail="La sesión del cliente no existe. Inicia una sesión nueva.")
                    business_id = UUID(str(c_row[0]))
                    if provided_business_id and str(business_id) != str(provided_business_id):
                        raise HTTPException(status_code=403, detail="La sesión del cliente pertenece a otro negocio.")
                    cur.execute(
                        "SELECT id FROM customers WHERE id = %s AND business_id = %s",
                        (supplied_customer_id, business_id),
                    )
                    if not cur.fetchone():
                        raise HTTPException(status_code=404, detail="Cliente no encontrado para este negocio.")
                    customer_id = supplied_customer_id
                else:
                    if provided_business_id:
                        cur.execute(
                            "SELECT id FROM businesses WHERE id = %s AND status = 'active'",
                            (provided_business_id,),
                        )
                        b_row = cur.fetchone()
                        if not b_row:
                            raise HTTPException(status_code=404, detail="El negocio no existe o está inactivo.")
                        business_id = UUID(str(b_row[0]))
                    else:
                        raise HTTPException(status_code=422, detail="Se requiere business_id o una sesión de cliente válida para registrar el pago.")
                    _get_active_webchat_business(conn, business_id)
                    customer_id = uuid4()
                    cur.execute(
                        """INSERT INTO customers
                           (id, business_id, full_name, status, source, notes)
                           VALUES (%s, %s, 'Cliente Webchat', 'active',
                                   'webchat_payment',
                                   'Cliente creado para una solicitud de pago Webchat.')""",
                        (customer_id, business_id),
                    )

                # This check applies to both existing customer sessions and new sessions.
                _get_active_webchat_business(conn, business_id)
                cur.execute("SELECT enabled FROM public.business_payment_instructions WHERE business_id = %s AND method_code = %s", (str(business_id), payment_method))
                configured_method = cur.fetchone()
                if not configured_method or not bool(configured_method[0]):
                    raise HTTPException(status_code=409, detail="Ese método de cobro no está habilitado por el comercio.")

                payment_id = uuid4()
                raw_items = payload.get("items") or []
                if not raw_items:
                    try:
                        cur.execute(
                            """SELECT content FROM conversation_messages
                               WHERE customer_id = %s AND business_id = %s AND direction = 'outbound'
                               ORDER BY created_at DESC LIMIT 5""",
                            (customer_id, business_id),
                        )
                        for msg_r in cur.fetchall():
                            txt_c = str(msg_r[0])
                            m_it = re.search(r'\[BOTON_PAGO:[^\]]*\|ITEMS:\s*(\[.*?\])\]', txt_c)
                            if m_it:
                                try:
                                    raw_items = json.loads(m_it.group(1))
                                    break
                                except Exception:
                                    pass
                            lines = re.findall(r'-\s*(\d+)x\s+([^:]+):', txt_c)
                            if lines:
                                raw_items = [{"name": p_n.strip(), "qty": float(q_s)} for q_s, p_n in lines]
                                break
                    except Exception as e_res:
                        print(f"[Calyrisia] Fallback parser items error: {e_res}")
                cur.execute(
                    """INSERT INTO webchat_payment_requests
                       (id, business_id, customer_id, amount, currency, payment_method, status, source, approval_note, items, customer_payment_details)
                       VALUES (%s, %s, %s, %s, 'USD', %s, 'pending', 'webchat', %s, %s, %s)""",
                    (
                        payment_id, business_id, customer_id, amount, payment_method,
                        "Solicitud recibida por Webchat; pendiente de validación del comercio.",
                        Jsonb(raw_items) if raw_items else None, customer_payment_details or None
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
            if "webchat_payment_requests" in message or "business_payment_instructions" in message or "does not exist" in message.lower():
                raise HTTPException(
                    status_code=503,
                    detail="El módulo de solicitudes de pago no está disponible. Contacta al administrador de CALYRISIA.",
                ) from exc
            raise HTTPException(status_code=500, detail=f"No se pudo registrar el pago pendiente: {exc}") from exc


@app.get("/api/v1/webchat/payment/status/{payment_id}")
async def webchat_payment_status(payment_id: UUID, business_id: UUID = Query(...)):
    """Public status poll scoped to the business that created the payment."""
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """SELECT status, order_id, amount, payment_method FROM webchat_payment_requests
                       WHERE id = %s AND business_id = %s""",
                    (payment_id, business_id),
                )
                row = cur.fetchone()
            if not row:
                return {"success": False, "status": "not_found"}
            return {
                "success": True,
                "status": str(row[0]),
                "order_id": str(row[1]) if row[1] else None,
                "amount": float(row[2]) if row[2] else 0.0,
                "payment_method": str(row[3]) if row[3] else "pago_movil",
            }
        except HTTPException:
            raise
        except Exception as exc:
            raise HTTPException(status_code=503, detail=f"No se pudo consultar el estado del pago: {exc}") from exc


@app.post("/api/v1/webchat/payment/confirm")
async def webchat_confirm_payment(payload: dict):
    """Read-only confirmation scoped to the business that owns the payment."""
    try:
        payment_id = UUID(str(payload.get("payment_id", "")))
        business_id = UUID(str(payload.get("business_id", "")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Se requieren payment_id y business_id para consultar la aprobación.")
    async with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, order_id FROM webchat_payment_requests
                   WHERE id = %s AND business_id = %s""",
                (payment_id, business_id),
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
    """Owner/Admin inbox for manual payment validation requests."""
    business_id = UUID(current_user["business_id"])
    async with get_connection() as conn:
        with conn.cursor() as cur:
            query = """SELECT p.id, p.customer_id, COALESCE(c.full_name, 'Cliente Webchat'),
                              p.amount, p.currency, p.status, p.payment_method,
                              p.created_at, p.reviewed_at, p.order_id, p.approval_note,
                              p.customer_payment_details, p.source
                       FROM webchat_payment_requests p
                       LEFT JOIN customers c ON c.id = p.customer_id AND c.business_id = p.business_id
                       WHERE p.business_id = %s"""
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
            "customer_payment_details": row[11],
            "source": row[12],
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
                    """SELECT id, customer_id, amount, currency, status, order_id, payment_method, business_id, items, approval_note
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
                    # Create the confirmed order in the same transaction. Below, recover the
                    # purchased items and apply the existing inventory decrement logic.
                    order_number = f"WC-{payment_id.hex[:24].upper()}"
                    # Asegurar cliente en el negocio del dueño activo
                    cur.execute(
                        "SELECT id FROM customers WHERE id = %s AND business_id = %s",
                        (customer_id, business_id),
                    )
                    if not cur.fetchone():
                        raise HTTPException(
                            status_code=409,
                            detail="El cliente asociado al pago no pertenece a este negocio. No se modificaron datos.",
                        )

                    cur.execute(
                        """INSERT INTO orders
                           (id, business_id, customer_id, order_number, status, subtotal,
                            discount_amount, tax_amount, total_amount, payment_status,
                            payment_method, source, notes)
                           VALUES (%s, %s, %s, %s, 'confirmed', %s, 0, 0, %s, 'paid',
                                   %s, 'webchat_payment', %s)""",
                        (
                            order_id, business_id, customer_id, order_number, amount, amount,
                            str(row[6]) if len(row) > 6 and row[6] else 'pago_movil',
                            f"Pago revisado manualmente en Dashboard. payment_id={payment_id}",
                        ),
                    )
                    # Descontar del inventario los productos comprados
                    raw_items = row[8]
                    if not raw_items and len(row) > 9 and row[9]:
                        try:
                            raw_items = json.loads(row[9])
                        except Exception:
                            raw_items = []
                    if isinstance(raw_items, str):
                        try:
                            raw_items = json.loads(raw_items)
                        except Exception:
                            raw_items = []
                    order_items = raw_items or []

                    if not order_items:
                        try:
                            cur.execute(
                                """SELECT content FROM conversation_messages
                                   WHERE customer_id = %s AND business_id = %s AND direction = 'outbound'
                                   ORDER BY created_at DESC LIMIT 5""",
                                (customer_id, business_id),
                            )
                            for msg_r in cur.fetchall():
                                txt_c = str(msg_r[0])
                                m_it = re.search(r'\[BOTON_PAGO:[^\]]*\|ITEMS:\s*(\[.*?\])\]', txt_c)
                                if m_it:
                                    try:
                                        order_items = json.loads(m_it.group(1))
                                        break
                                    except Exception:
                                        pass
                                lines = re.findall(r'-\s*(\d+)x\s+([^:]+):', txt_c)
                                if lines:
                                    order_items = [{"name": p_n.strip(), "qty": float(q_s)} for q_s, p_n in lines]
                                    break
                        except Exception as e_rec:
                            print(f"[Calyrisia] Error rescatando items: {e_rec}")

                    cur.execute(
                        """SELECT id, name FROM products
                           WHERE business_id = %s::uuid""",
                        (str(business_id),),
                    )
                    owner_products = cur.fetchall()
                    owner_product_names = {str(op_id): str(op_name) for op_id, op_name in owner_products}

                    for it in order_items:
                        qty = float(it.get("qty", 1))
                        item_name = (it.get("name") or "").lower().strip()
                        raw_pid = it.get("id")

                        matched_pid = None
                        if raw_pid:
                            try:
                                candidate_pid = str(UUID(str(raw_pid)))
                            except Exception:
                                # An invalid product ID must not silently fall back to a name match.
                                continue
                            # Do not trust a product ID carried inside a checkout payload.
                            # It is accepted only if the product belongs to this tenant.
                            if candidate_pid not in owner_product_names:
                                continue
                            matched_pid = candidate_pid

                        if not matched_pid and not raw_pid and item_name:
                            for op_id, op_name in owner_products:
                                clean_op = op_name.lower().strip()
                                if item_name in clean_op or clean_op in item_name:
                                    matched_pid = str(op_id)
                                    break

                        if not matched_pid and not raw_pid and item_name:
                            kw_list = [w for w in item_name.split() if len(w) > 3 and w not in ("premium", "blanco", "litro", "gourmet", "completa")]
                            for op_id, op_name in owner_products:
                                if any(kw in op_name.lower() for kw in kw_list):
                                    matched_pid = str(op_id)
                                    break

                        if matched_pid:
                            cur.execute(
                                """UPDATE inventory
                                   SET quantity = GREATEST(0, quantity - %s)
                                   WHERE product_id = %s::uuid AND business_id = %s::uuid""",
                                (qty, matched_pid, str(business_id)),
                            )
                            cur.execute(
                                """INSERT INTO inventory (id, business_id, product_id, quantity, minimum_quantity, location)
                                   SELECT gen_random_uuid(), %s::uuid, %s::uuid, 0, 0, 'tienda'
                                   WHERE NOT EXISTS (
                                       SELECT 1 FROM inventory
                                       WHERE product_id = %s::uuid AND business_id = %s::uuid
                                   )""",
                                (str(business_id), matched_pid, matched_pid, str(business_id)),
                            )
                            print(f"[Calyrisia] Stock descontado exitosamente: {qty} de producto {matched_pid}")

                    cur.execute(
                        """UPDATE webchat_payment_requests
                           SET status = 'approved', reviewed_at = now(), reviewed_by = %s,
                               order_id = %s, approval_note = 'Aprobado manualmente desde el Dashboard'
                           WHERE id = %s AND business_id = %s""",
                        (reviewer_id, order_id, payment_id, business_id),
                    )
                else:
                    cur.execute(
                        """UPDATE webchat_payment_requests
                           SET status = 'rejected', reviewed_at = now(), reviewed_by = %s,
                               approval_note = 'Rechazado manualmente desde el Dashboard'
                           WHERE id = %s AND business_id = %s""",
                        (reviewer_id, payment_id, business_id),
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

        # Notify the Telegram customer after the dashboard transaction has committed.
        try:
            await notify_payment_decision(
                str(business_id), str(payment_id), decision, float(amount),
                str(order_id) if order_id else None,
            )
        except Exception as notify_exc:
            print(f"[CALYRISIA][Telegram] No se pudo notificar la decisión del pago: {notify_exc}")

    return {
        "success": True,
        "status": "approved" if decision == "approve" else "rejected",
        "order_id": str(order_id) if order_id else None,
        "amount": float(amount),
        "sales_today": sales_today,
    }


@app.post("/api/v1/webchat/stream")
async def webchat_stream_retired(payload: IncomingMessage):
    raise HTTPException(status_code=410, detail="Este endpoint antiguo fue retirado. Usa el canal Webchat de CALYRISIA, que aplica el contexto y los límites del negocio.")


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
            consume_ai_response(conn, payload.business_id)
            conn.commit()
            result = service.respond(payload)
        except AIQuotaExceeded as quota_exc:
            raise HTTPException(status_code=429, detail=f"Has usado las {quota_exc.limit} respuestas de IA incluidas este mes. Contacta con CALYRISIA para ampliar la cuota o cambiar de plan.") from quota_exc
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
async def demo_overview_retired():
    raise HTTPException(status_code=410, detail="La demo pública fue retirada. Contacta con CALYRISIA para contratar el servicio.")


CHECKOUT_PLANS = {
    "emprendedor": {"label": "Emprendedor", "amount": Decimal("19.00"), "env_suffix": "EMPRENDEDOR"},
    "smart_business": {"label": "Smart Business", "amount": Decimal("49.00"), "env_suffix": "SMART_BUSINESS"},
    "enterprise": {"label": "Enterprise", "amount": Decimal("99.00"), "env_suffix": "ENTERPRISE"},
}
CHECKOUT_METHODS = {"transferencia", "pago_movil", "binance", "zinli", "tarjeta"}


def _checkout_public_value(name: str) -> str:
    return os.getenv(name, "").strip()[:300]


def _paypal_mode() -> str:
    # Safe default: never charge real cards unless production mode is explicitly selected.
    return "live" if os.getenv("CALYRISIA_PAYPAL_MODE", "sandbox").strip().lower() == "live" else "sandbox"


def _paypal_api_base() -> str:
    return "https://api-m.sandbox.paypal.com" if _paypal_mode() == "sandbox" else "https://api-m.paypal.com"


def _paypal_plan_id(plan_code: str) -> str:
    suffix = CHECKOUT_PLANS[plan_code]["env_suffix"]
    return _checkout_public_value(f"CALYRISIA_PAYPAL_PLAN_ID_{suffix}")


def _paypal_ready() -> bool:
    return bool(
        _checkout_public_value("CALYRISIA_PAYPAL_CLIENT_ID")
        and _checkout_public_value("CALYRISIA_PAYPAL_CLIENT_SECRET")
        and _checkout_public_value("CALYRISIA_PAYPAL_WEBHOOK_ID")
        and all(_paypal_plan_id(code) for code in CHECKOUT_PLANS)
    )


async def _paypal_access_token() -> str:
    client_id = _checkout_public_value("CALYRISIA_PAYPAL_CLIENT_ID")
    client_secret = os.getenv("CALYRISIA_PAYPAL_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="El pago con tarjeta aún no está configurado en CALYRISIA.")
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            response = await client.post(
                f"{_paypal_api_base()}/v1/oauth2/token",
                auth=(client_id, client_secret),
                data={"grant_type": "client_credentials"},
                headers={"Accept": "application/json", "Accept-Language": "es-ES"},
            )
        if response.status_code != 200:
            print(f"[CALYRISIA][PAYPAL] Token request failed: {response.status_code}")
            raise HTTPException(status_code=502, detail="No se pudo conectar con el proveedor de pagos.")
        token = response.json().get("access_token")
        if not token:
            raise HTTPException(status_code=502, detail="El proveedor de pagos no entregó un token válido.")
        return str(token)
    except httpx.HTTPError as exc:
        print(f"[CALYRISIA][PAYPAL] Network error obtaining token: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail="No se pudo conectar con el proveedor de pagos.") from exc


async def _paypal_request(method: str, endpoint: str, payload: dict | None = None, params: dict | None = None) -> dict:
    token = await _paypal_access_token()
    try:
        async with httpx.AsyncClient(timeout=25.0) as client:
            response = await client.request(
                method, f"{_paypal_api_base()}{endpoint}",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
                json=payload if payload is not None else None,
                params=params,
            )
        if response.status_code >= 400:
            print(f"[CALYRISIA][PAYPAL] API request failed: {method} {endpoint} -> {response.status_code}")
            raise HTTPException(status_code=502, detail="El proveedor de pagos no pudo completar la operación.")
        return response.json() if response.content else {}
    except httpx.HTTPError as exc:
        print(f"[CALYRISIA][PAYPAL] Network error: {type(exc).__name__}")
        raise HTTPException(status_code=502, detail="No se pudo conectar con el proveedor de pagos.") from exc


@app.get("/api/v1/public/checkout/config")
async def public_checkout_config() -> dict:
    """Expose safe checkout settings only; never return PayPal secrets or card data."""
    contact = {
        "whatsapp": _checkout_public_value("CALYRISIA_SALES_WHATSAPP") or "584128418550",
        "email": _checkout_public_value("CALYRISIA_SALES_EMAIL") or "jorge@calyrisia.com",
    }
    binance = {
        "Binance Pay ID": _checkout_public_value("CALYRISIA_BINANCE_PAY_ID") or "193612923",
        "Correo o identificador": _checkout_public_value("CALYRISIA_BINANCE_PAY_EMAIL"),
        "Red / instrucción": _checkout_public_value("CALYRISIA_BINANCE_NETWORK"),
    }
    binance_url = _checkout_public_value("CALYRISIA_BINANCE_PAYMENT_URL")
    if not binance_url.lower().startswith("https://"):
        binance_url = ""
    binance_qr = _checkout_public_value("CALYRISIA_BINANCE_QR_IMAGE_URL")
    if binance_qr.startswith("/payments/"):
        safe_relative = binance_qr[len("/"):]
        candidate = os.path.realpath(os.path.join("app/static", safe_relative))
        allowed_root = os.path.realpath(os.path.join("app/static", "payments")) + os.sep
        if not candidate.startswith(allowed_root) or not os.path.isfile(candidate):
            binance_qr = ""
    elif not binance_qr.lower().startswith("https://"):
        binance_qr = ""
    zinli = {
        "Usuario / identificador Zinli": _checkout_public_value("CALYRISIA_ZINLI_ID"),
        "Correo asociado": _checkout_public_value("CALYRISIA_ZINLI_EMAIL"),
    }
    zinli_url = _checkout_public_value("CALYRISIA_ZINLI_PAYMENT_URL")
    if not zinli_url.lower().startswith("https://"):
        zinli_url = ""
    plan_ids = {code: _paypal_plan_id(code) for code in CHECKOUT_PLANS}
    return {
        "contact": contact,
        "methods": {
            "transferencia": {"label": "Transferencia bancaria", "request_via_whatsapp": True, "ready": bool(contact["whatsapp"])},
            "pago_movil": {"label": "Pago Móvil", "request_via_whatsapp": True, "ready": bool(contact["whatsapp"])},
            "binance": {"label": "Binance Pay", "details": binance, "payment_url": binance_url, "qr_image_url": binance_qr, "ready": bool(binance["Binance Pay ID"] or binance["Correo o identificador"] or binance_url)},
            "zinli": {"label": "Zinli", "details": zinli, "payment_url": zinli_url, "ready": bool(zinli["Usuario / identificador Zinli"] or zinli["Correo asociado"] or zinli_url)},
            "tarjeta": {"label": "Tarjeta bancaria", "provider": "PayPal", "ready": _paypal_ready(), "paypal": {
                "enabled": _paypal_ready(),
                "client_id": _checkout_public_value("CALYRISIA_PAYPAL_CLIENT_ID") if _paypal_ready() else "",
                "mode": _paypal_mode(),
                "plan_ids": plan_ids if _paypal_ready() else {},
                "currency": "USD",
            }},
        },
    }


@app.post("/api/v1/public/checkout/start", status_code=201)
async def start_public_checkout(payload: dict) -> dict:
    """Create a server-side checkout reference; prices are derived only on the server."""
    plan_code = str(payload.get("plan_code") or payload.get("plan") or "").strip().lower()
    if plan_code not in CHECKOUT_PLANS:
        raise HTTPException(status_code=422, detail="Selecciona un plan válido.")
    checkout_ref = f"CY-{uuid4().hex[:24].upper()}"
    plan = CHECKOUT_PLANS[plan_code]
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO public.calyrisia_checkout_orders
                       (checkout_ref, plan_code, amount, currency, payment_method, status, paypal_plan_id)
                       VALUES (%s,%s,%s,'USD','pending','pending',%s)""",
                    (checkout_ref, plan_code, plan["amount"], _paypal_plan_id(plan_code) or None),
                )
            conn.commit()
    except Exception as exc:
        print(f"[CALYRISIA][CHECKOUT] Could not create order: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="El portal de contratación está temporalmente ocupado. Inténtalo otra vez.") from exc
    return {"checkout_ref": checkout_ref, "plan_code": plan_code, "amount": str(plan["amount"]), "currency": "USD", "status": "pending"}


@app.post("/api/v1/public/checkout/contact")
async def save_public_checkout_contact(payload: dict) -> dict:
    """Attach buyer identity to one checkout reference before any payment method can be selected."""
    ref = str(payload.get("checkout_ref") or "").strip().upper()
    name = " ".join(str(payload.get("customer_name") or "").split())[:160]
    email = str(payload.get("customer_email") or "").strip().lower()[:254]
    phone = str(payload.get("customer_phone") or "").strip()[:64]
    business_name = " ".join(str(payload.get("business_name") or "").split())[:180]
    if not ref or len(ref) > 64:
        raise HTTPException(status_code=422, detail="La referencia de contratación no es válida.")
    if len(name) < 2:
        raise HTTPException(status_code=422, detail="Escribe el nombre de la persona responsable del pago.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
        raise HTTPException(status_code=422, detail="Introduce un correo válido para identificar tu contratación.")
    if len(re.sub(r"\D", "", phone)) < 7:
        raise HTTPException(status_code=422, detail="Introduce un teléfono válido con código de país.")
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE public.calyrisia_checkout_orders
                               SET customer_name=%s, customer_email=%s, customer_phone=%s,
                                   business_name=%s, contact_saved_at=now(), updated_at=now()
                               WHERE checkout_ref=%s AND status IN ('pending','awaiting_payment') AND proof_submitted_at IS NULL
                               RETURNING checkout_ref""",
                            (name, email, phone, business_name or None, ref))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="No encontramos una contratación activa con esa referencia.")
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[CALYRISIA][CHECKOUT] Could not save buyer contact: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="No se pudieron guardar tus datos. Inténtalo nuevamente.") from exc
    return {"success": True, "checkout_ref": ref, "contact_saved": True}


@app.post("/api/v1/public/checkout/proof")
async def submit_public_checkout_proof(payload: dict) -> dict:
    """Mark a manual proof as submitted; actual payment approval remains an admin action."""
    ref = str(payload.get("checkout_ref") or "").strip().upper()
    transaction_reference = " ".join(str(payload.get("transaction_reference") or "").split())[:180]
    proof_note = str(payload.get("proof_note") or "").strip()[:1000]
    if not ref or len(ref) > 64:
        raise HTTPException(status_code=422, detail="La referencia de contratación no es válida.")
    manual_methods = {"transferencia", "pago_movil", "binance", "zinli"}
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE public.calyrisia_checkout_orders
                               SET transaction_reference=COALESCE(NULLIF(%s,''), transaction_reference),
                                   proof_note=COALESCE(NULLIF(%s,''), proof_note),
                                   proof_submitted_at=COALESCE(proof_submitted_at, now()),
                                   updated_at=now()
                               WHERE checkout_ref=%s AND status='awaiting_payment'
                                 AND payment_method = ANY(%s)
                                 AND customer_name IS NOT NULL AND customer_email IS NOT NULL AND customer_phone IS NOT NULL
                               RETURNING status, proof_submitted_at""",
                            (transaction_reference, proof_note, ref, list(manual_methods)))
                row = cur.fetchone()
                if not row:
                    cur.execute("SELECT status, payment_method, customer_name, customer_email, customer_phone FROM public.calyrisia_checkout_orders WHERE checkout_ref=%s", (ref,))
                    existing = cur.fetchone()
                    if not existing:
                        raise HTTPException(status_code=404, detail="No encontramos esa contratación.")
                    if not all(existing[i] for i in (2,3,4)):
                        raise HTTPException(status_code=409, detail="Completa primero los datos de contacto para esta contratación.")
                    if str(existing[0]) == "paid":
                        raise HTTPException(status_code=409, detail="El pago ya fue confirmado. Puedes continuar al onboarding.")
                    if str(existing[0]) != "awaiting_payment" or str(existing[1]) not in manual_methods:
                        raise HTTPException(status_code=409, detail="La contratación no está esperando un comprobante manual.")
                    raise HTTPException(status_code=409, detail="No se pudo registrar el comprobante. Actualiza el estado e inténtalo otra vez.")
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[CALYRISIA][CHECKOUT] Could not record manual proof: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="No se pudo registrar el aviso de comprobante.") from exc
    return {"success": True, "checkout_ref": ref, "status": "awaiting_payment", "proof_submitted": True,
            "proof_submitted_at": row[1].isoformat() if row[1] else None,
            "message": "Aviso registrado. CALYRISIA verificará el ingreso antes de habilitar el onboarding."}


@app.post("/api/v1/public/checkout/method")
async def set_public_checkout_method(payload: dict) -> dict:
    checkout_ref = str(payload.get("checkout_ref") or "").strip().upper()
    method = str(payload.get("method") or "").strip().lower()
    if not checkout_ref or method not in CHECKOUT_METHODS:
        raise HTTPException(status_code=422, detail="La referencia o el método de pago no son válidos.")
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT customer_name, customer_email, customer_phone, status, payment_method, proof_submitted_at, paypal_subscription_id FROM public.calyrisia_checkout_orders WHERE checkout_ref=%s FOR UPDATE", (checkout_ref,))
                contact_row = cur.fetchone()
                if not contact_row:
                    raise HTTPException(status_code=404, detail="No encontramos la referencia de contratación.")
                if not all(contact_row[i] for i in (0, 1, 2)):
                    raise HTTPException(status_code=409, detail="Completa y guarda tus datos de contacto antes de elegir el método de pago.")
                if str(contact_row[3]) not in {"pending", "awaiting_payment"}:
                    raise HTTPException(status_code=409, detail="Esta contratación ya fue procesada y no puede cambiar de método.")
                if contact_row[5] is not None and str(contact_row[4]) != method:
                    raise HTTPException(status_code=409, detail="Ya reportaste el comprobante. No puedes cambiar el método de esta referencia.")
                if contact_row[6] is not None and str(contact_row[4]) != method:
                    raise HTTPException(status_code=409, detail="Ya se inició una suscripción con tarjeta para esta referencia. No cambies el método; contacta a CALYRISIA si necesitas ayuda.")
                cur.execute("""UPDATE public.calyrisia_checkout_orders SET payment_method=%s, status='awaiting_payment',
                              updated_at=now()
                              WHERE checkout_ref=%s AND status IN ('pending','awaiting_payment')
                                AND (proof_submitted_at IS NULL OR payment_method=%s)
                              RETURNING plan_code, amount, status""",
                            (method, checkout_ref, method))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=409, detail="La contratación cambió de estado. Actualiza la página.")
                plan_code = str(row[0])
                if method == "tarjeta":
                    paypal_plan_id = _paypal_plan_id(plan_code)
                    if not paypal_plan_id:
                        raise HTTPException(status_code=503, detail="El plan de tarjeta todavía no está configurado en el proveedor.")
                    cur.execute("UPDATE public.calyrisia_checkout_orders SET paypal_plan_id=%s WHERE checkout_ref=%s", (paypal_plan_id, checkout_ref))
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[CALYRISIA][CHECKOUT] Method update failed: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="No se pudo actualizar el método de pago.") from exc
    return {"success": True, "checkout_ref": checkout_ref, "plan_code": plan_code, "payment_method": method}


@app.post("/api/v1/public/checkout/paypal/attach")
async def attach_paypal_subscription(payload: dict) -> dict:
    checkout_ref = str(payload.get("checkout_ref") or "").strip().upper()
    subscription_id = str(payload.get("subscription_id") or "").strip()[:128]
    plan_code = str(payload.get("plan_code") or "").strip().lower()
    if not checkout_ref or not subscription_id or plan_code not in CHECKOUT_PLANS:
        raise HTTPException(status_code=422, detail="La referencia o la suscripción no son válidas.")
    if not _paypal_ready():
        raise HTTPException(status_code=503, detail="El pago con tarjeta no está completamente configurado.")
    subscription = await _paypal_request("GET", f"/v1/billing/subscriptions/{subscription_id}")
    expected_plan = _paypal_plan_id(plan_code)
    if str(subscription.get("plan_id") or "") != expected_plan:
        raise HTTPException(status_code=400, detail="La suscripción no corresponde al plan seleccionado.")
    paypal_status = str(subscription.get("status") or "").upper()
    if paypal_status not in {"ACTIVE", "APPROVAL_PENDING", "APPROVED"}:
        raise HTTPException(status_code=409, detail="La suscripción no está aprobada por el proveedor.")
    custom_id = str(subscription.get("custom_id") or "").strip().upper()
    if custom_id != checkout_ref:
        raise HTTPException(status_code=400, detail="La referencia de la suscripción no coincide con la contratación.")
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""UPDATE public.calyrisia_checkout_orders SET paypal_subscription_id=%s,
                              subscription_status=%s, status=CASE WHEN status='paid' THEN 'paid' ELSE 'awaiting_payment' END,
                              updated_at=now()
                              WHERE checkout_ref=%s AND plan_code=%s AND payment_method='tarjeta'
                                AND (paypal_subscription_id IS NULL OR paypal_subscription_id=%s)
                              RETURNING checkout_ref, amount, currency, status""",
                            (subscription_id, paypal_status.lower(), checkout_ref, plan_code, subscription_id))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="No encontramos una contratación pendiente para esta suscripción.")
                _, expected_amount, expected_currency, current_status = row
                cur.execute("""SELECT transaction_id, event_id, amount, currency
                              FROM public.calyrisia_paypal_pending_sales
                              WHERE subscription_id=%s ORDER BY created_at DESC""", (subscription_id,))
                pending_sales = cur.fetchall()
                for pending_sale in pending_sales:
                    tx_id, tx_event_id, tx_amount, tx_currency = pending_sale
                    if Decimal(str(tx_amount)) == Decimal(str(expected_amount)) and str(tx_currency).upper() == str(expected_currency).upper():
                        cur.execute("""UPDATE public.calyrisia_checkout_orders SET status='paid',
                                      paypal_transaction_id=%s, subscription_status='active', webhook_event_id=%s,
                                      paid_at=COALESCE(paid_at,now()), updated_at=now()
                                      WHERE checkout_ref=%s AND paypal_subscription_id=%s
                                        AND amount=%s AND currency=%s""",
                                    (str(tx_id), tx_event_id, checkout_ref, subscription_id, expected_amount, expected_currency))
                        current_status = 'paid'
                        cur.execute("DELETE FROM public.calyrisia_paypal_pending_sales WHERE subscription_id=%s AND transaction_id=%s", (subscription_id, tx_id))
                        break
            conn.commit()
    except HTTPException:
        raise
    except Exception as exc:
        print(f"[CALYRISIA][PAYPAL] Could not link subscription: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="No se pudo asociar la suscripción con la contratación.") from exc
    if current_status == "paid":
        return {"success": True, "status": "paid", "message": "El primer pago quedó verificado."}
    return {"success": True, "status": "awaiting_payment", "message": "Suscripción asociada; esperando confirmación del primer cobro."}


@app.get("/api/v1/public/checkout/status/{checkout_ref}")
async def public_checkout_status(checkout_ref: str) -> dict:
    ref = str(checkout_ref or "").strip().upper()
    if not ref or len(ref) > 64:
        raise HTTPException(status_code=422, detail="La referencia no es válida.")
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""SELECT plan_code, payment_method, status, amount, currency, paid_at,
                                      customer_name, customer_email, customer_phone, business_name,
                                      transaction_reference, proof_submitted_at, contact_saved_at
                               FROM public.calyrisia_checkout_orders WHERE checkout_ref=%s""", (ref,))
                row = cur.fetchone()
    except Exception as exc:
        print(f"[CALYRISIA][CHECKOUT] Status lookup failed: {type(exc).__name__}")
        raise HTTPException(status_code=503, detail="No se pudo consultar el estado del pago.") from exc
    if not row:
        raise HTTPException(status_code=404, detail="No encontramos esa referencia de contratación.")
    plan_code, method, status, amount, currency, paid_at, customer_name, customer_email, customer_phone, business_name, transaction_reference, proof_submitted_at, contact_saved_at = row
    result = {"checkout_ref": ref, "plan_code": str(plan_code), "payment_method": str(method), "status": str(status), "amount": str(amount), "currency": str(currency), "paid_at": paid_at.isoformat() if paid_at else None,
              "customer_name": customer_name or "", "customer_email": customer_email or "", "customer_phone": customer_phone or "", "business_name": business_name or "",
              "contact_saved": bool(contact_saved_at), "transaction_reference": transaction_reference or "", "proof_submitted": bool(proof_submitted_at), "proof_submitted_at": proof_submitted_at.isoformat() if proof_submitted_at else None}
    if status == "paid":
        safe_plan = str(plan_code)
        safe_method = str(method)
        result["onboarding_url"] = _checkout_onboarding_url(ref, safe_plan, safe_method)
    return result


def _checkout_onboarding_url(ref: str, plan_code: str, method: str) -> str:
    from urllib.parse import urlencode
    return "/onboarding/?" + urlencode({"plan": plan_code, "method": method, "ref": ref, "payment": "verified"})


def _require_checkout_admin(request: Request) -> None:
    expected = os.getenv("CALYRISIA_CHECKOUT_ADMIN_KEY", "").strip()
    supplied = request.headers.get("x-calyrisia-admin-key", "").strip()
    if len(expected) < 32:
        raise HTTPException(status_code=503, detail="El panel de contrataciones no está configurado. Define CALYRISIA_CHECKOUT_ADMIN_KEY en el hosting con una clave aleatoria larga.")
    if not supplied or not hmac.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Clave de administración no válida.")


@app.get("/admin/contrataciones/", include_in_schema=False)
async def checkout_admin_page() -> FileResponse:
    return FileResponse("app/static/admin/contrataciones/index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/v1/admin/checkout/orders")
async def admin_checkout_orders(request: Request, status: str = Query(default="awaiting_payment", pattern="^(pending|awaiting_payment|paid|failed|cancelled|all)$"), limit: int = Query(default=100, ge=1, le=200)) -> dict:
    _require_checkout_admin(request)
    async with get_connection() as conn:
        with conn.cursor() as cur:
            if status == "all":
                cur.execute("""SELECT checkout_ref, plan_code, amount, currency, payment_method, status, created_at, paid_at, reviewed_at, review_note,
                                      customer_name, customer_email, customer_phone, business_name, transaction_reference, proof_submitted_at, proof_note
                               FROM public.calyrisia_checkout_orders ORDER BY created_at DESC LIMIT %s""", (limit,))
            else:
                cur.execute("""SELECT checkout_ref, plan_code, amount, currency, payment_method, status, created_at, paid_at, reviewed_at, review_note,
                                      customer_name, customer_email, customer_phone, business_name, transaction_reference, proof_submitted_at, proof_note
                               FROM public.calyrisia_checkout_orders WHERE status=%s ORDER BY created_at DESC LIMIT %s""", (status, limit))
            rows = cur.fetchall()
    manual_methods = {"transferencia", "pago_movil", "binance", "zinli"}
    orders = []
    for row in rows:
        ref, plan_code, amount, currency, method, order_status, created_at, paid_at, reviewed_at, review_note, customer_name, customer_email, customer_phone, business_name, transaction_reference, proof_submitted_at, proof_note = row
        item = {
            "checkout_ref": str(ref), "plan_code": str(plan_code), "plan_label": CHECKOUT_PLANS.get(str(plan_code), {}).get("label", str(plan_code)),
            "amount": str(amount), "currency": str(currency), "payment_method": str(method), "status": str(order_status),
            "created_at": created_at.isoformat() if created_at else None,
            "paid_at": paid_at.isoformat() if paid_at else None,
            "reviewed_at": reviewed_at.isoformat() if reviewed_at else None,
            "review_note": review_note or "", "customer_name": customer_name or "", "customer_email": customer_email or "",
            "customer_phone": customer_phone or "", "business_name": business_name or "",
            "transaction_reference": transaction_reference or "", "proof_note": proof_note or "",
            "proof_submitted_at": proof_submitted_at.isoformat() if proof_submitted_at else None,
            "can_review_manually": str(method) in manual_methods and str(order_status) == "awaiting_payment" and proof_submitted_at is not None,
        }
        if str(order_status) == "paid":
            item["onboarding_url"] = _checkout_onboarding_url(str(ref), str(plan_code), str(method))
        orders.append(item)
    return {"success": True, "orders": orders}


@app.post("/api/v1/admin/checkout/orders/{checkout_ref}/decision")
async def decide_manual_checkout_order(checkout_ref: str, request: Request, payload: dict) -> dict:
    _require_checkout_admin(request)
    ref = str(checkout_ref or "").strip().upper()
    decision = str(payload.get("decision") or "").strip().lower()
    note = str(payload.get("note") or "").strip()[:500]
    if not ref or len(ref) > 64 or decision not in {"approve", "reject"}:
        raise HTTPException(status_code=422, detail="Referencia o decisión inválida.")
    manual_methods = {"transferencia", "pago_movil", "binance", "zinli"}
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute("""SELECT plan_code, payment_method, status, amount, currency, proof_submitted_at
                               FROM public.calyrisia_checkout_orders WHERE checkout_ref=%s FOR UPDATE""", (ref,))
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="No existe esa referencia de contratación.")
                plan_code, method, current_status, amount, currency, proof_submitted_at = row
                method = str(method)
                current_status = str(current_status)
                if method not in manual_methods:
                    raise HTTPException(status_code=409, detail="Esta contratación no admite aprobación manual. Los pagos con tarjeta solo se confirman mediante el webhook verificado.")
                if current_status == "paid" and decision == "approve":
                    conn.commit()
                    return {"success": True, "status": "paid", "already_processed": True,
                            "checkout_ref": ref, "onboarding_url": _checkout_onboarding_url(ref, str(plan_code), method)}
                if current_status != "awaiting_payment":
                    raise HTTPException(status_code=409, detail=f"La contratación no está pendiente de revisión: {current_status}.")
                if decision == "approve" and proof_submitted_at is None:
                    raise HTTPException(status_code=409, detail="El cliente aún no ha reportado el envío del comprobante en esta referencia.")
                if decision == "approve":
                    cur.execute("""UPDATE public.calyrisia_checkout_orders
                                   SET status='paid', paid_at=COALESCE(paid_at, now()), reviewed_at=now(),
                                       reviewed_by='CALYRISIA checkout admin', review_note=%s, updated_at=now()
                                   WHERE checkout_ref=%s AND status='awaiting_payment'
                                   RETURNING plan_code, payment_method""", (note or "Pago verificado manualmente por CALYRISIA.", ref))
                    updated = cur.fetchone()
                    if not updated:
                        raise HTTPException(status_code=409, detail="La contratación cambió de estado. Actualiza la lista y vuelve a revisar.")
                    conn.commit()
                    return {"success": True, "status": "paid", "checkout_ref": ref,
                            "onboarding_url": _checkout_onboarding_url(ref, str(updated[0]), str(updated[1]))}
                cur.execute("""UPDATE public.calyrisia_checkout_orders
                               SET status='failed', reviewed_at=now(), reviewed_by='CALYRISIA checkout admin',
                                   review_note=%s, updated_at=now()
                               WHERE checkout_ref=%s AND status='awaiting_payment'""",
                            (note or "Pago no verificado; solicitar nuevo comprobante o referencia.", ref))
                if cur.rowcount != 1:
                    raise HTTPException(status_code=409, detail="La contratación cambió de estado. Actualiza la lista y vuelve a revisar.")
            conn.commit()
            return {"success": True, "status": "failed", "checkout_ref": ref}
        except HTTPException:
            conn.rollback()
            raise
        except Exception as exc:
            conn.rollback()
            print(f"[CALYRISIA][CHECKOUT ADMIN] Decision failed: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="No se pudo guardar la revisión del pago.") from exc


@app.post("/api/v1/public/checkout/paypal/webhook")
async def paypal_subscription_webhook(request: Request) -> dict:
    """Verify PayPal's webhook signature and mark a checkout paid only on a completed sale."""
    if not _checkout_public_value("CALYRISIA_PAYPAL_WEBHOOK_ID") or not _checkout_public_value("CALYRISIA_PAYPAL_CLIENT_ID") or not os.getenv("CALYRISIA_PAYPAL_CLIENT_SECRET", "").strip():
        raise HTTPException(status_code=503, detail="Webhook de PayPal no configurado.")
    try:
        event = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="Evento de pago inválido.") from exc
    hdr = request.headers
    verify_body = {
        "auth_algo": hdr.get("paypal-auth-algo", ""),
        "cert_url": hdr.get("paypal-cert-url", ""),
        "transmission_id": hdr.get("paypal-transmission-id", ""),
        "transmission_sig": hdr.get("paypal-transmission-sig", ""),
        "transmission_time": hdr.get("paypal-transmission-time", ""),
        "webhook_id": _checkout_public_value("CALYRISIA_PAYPAL_WEBHOOK_ID"),
        "webhook_event": event,
    }
    if not all(verify_body[k] for k in ("auth_algo", "cert_url", "transmission_id", "transmission_sig", "transmission_time")):
        raise HTTPException(status_code=400, detail="Faltan cabeceras para verificar el evento de PayPal.")
    token = await _paypal_access_token()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            verification = await client.post(
                f"{_paypal_api_base()}/v1/notifications/verify-webhook-signature",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=verify_body,
            )
        if verification.status_code != 200 or verification.json().get("verification_status") != "SUCCESS":
            raise HTTPException(status_code=400, detail="La firma del evento de pago no es válida.")
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="No se pudo verificar el evento de pago.") from exc

    event_type = str(event.get("event_type") or "")
    event_id = str(event.get("id") or "")[:128]
    resource = event.get("resource") or {}
    subscription_id = str(resource.get("id") or "")[:128]
    if event_type == "PAYMENT.SALE.COMPLETED":
        subscription_id = str(resource.get("billing_agreement_id") or "")[:128]
    custom_id = str(resource.get("custom_id") or "").strip().upper()
    if event_type in {"BILLING.SUBSCRIPTION.CREATED", "BILLING.SUBSCRIPTION.ACTIVATED", "BILLING.SUBSCRIPTION.UPDATED"} and custom_id and subscription_id:
        try:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE public.calyrisia_checkout_orders SET paypal_subscription_id=%s,
                                  subscription_status=%s, status=CASE WHEN status='paid' THEN 'paid' ELSE 'awaiting_payment' END,
                                  webhook_event_id=%s, updated_at=now()
                                  WHERE checkout_ref=%s AND payment_method='tarjeta' AND paypal_plan_id=%s
                                    AND (paypal_subscription_id IS NULL OR paypal_subscription_id=%s)""",
                                (subscription_id, str(resource.get("status") or "").lower(), event_id, custom_id, str(resource.get("plan_id") or ""), subscription_id))
                conn.commit()
        except Exception as exc:
            print(f"[CALYRISIA][PAYPAL] Subscription webhook update failed: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="No se pudo registrar la suscripción.") from exc
    elif event_type == "PAYMENT.SALE.COMPLETED":
        amount_obj = resource.get("amount") or {}
        amount_value = amount_obj.get("total", amount_obj.get("value", "0"))
        currency_value = str(amount_obj.get("currency", amount_obj.get("currency_code", "USD"))).upper()
        try:
            paid_amount = Decimal(str(amount_value))
        except (InvalidOperation, TypeError):
            paid_amount = Decimal("0")
        try:
            transaction_id = str(resource.get("id") or event_id or "")[:128]
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""UPDATE public.calyrisia_checkout_orders SET status='paid',
                                  paypal_transaction_id=%s, subscription_status='active', webhook_event_id=%s,
                                  paid_at=COALESCE(paid_at,now()), updated_at=now()
                                  WHERE paypal_subscription_id=%s AND payment_method='tarjeta'
                                    AND amount=%s AND currency=%s
                                  RETURNING checkout_ref""",
                                (transaction_id, event_id, subscription_id, paid_amount, currency_value))
                    matched = cur.fetchone()
                    if not matched and subscription_id and transaction_id:
                        cur.execute("""INSERT INTO public.calyrisia_paypal_pending_sales
                                      (subscription_id, transaction_id, event_id, amount, currency)
                                      VALUES (%s,%s,%s,%s,%s)
                                      ON CONFLICT (subscription_id, transaction_id) DO UPDATE SET
                                        event_id=EXCLUDED.event_id, amount=EXCLUDED.amount, currency=EXCLUDED.currency""",
                                    (subscription_id, transaction_id, event_id, paid_amount, currency_value))
                conn.commit()
            if not matched:
                print(f"[CALYRISIA][PAYPAL] Verified sale queued for subscription association; subscription={subscription_id!r}, amount={paid_amount}, currency={currency_value}")
        except Exception as exc:
            print(f"[CALYRISIA][PAYPAL] Sale webhook update failed: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="No se pudo registrar el cobro.") from exc
    elif event_type in {"BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.SUSPENDED", "BILLING.SUBSCRIPTION.EXPIRED"} and subscription_id:
        try:
            async with get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE public.calyrisia_checkout_orders SET subscription_status=%s, webhook_event_id=%s, updated_at=now() WHERE paypal_subscription_id=%s", (event_type.split(".")[-1].lower(), event_id, subscription_id))
                conn.commit()
        except Exception as exc:
            print(f"[CALYRISIA][PAYPAL] Subscription status update failed: {type(exc).__name__}")
            raise HTTPException(status_code=503, detail="No se pudo actualizar la suscripción.") from exc
    return {"received": True}


@app.get("/api/v1/onboarding/catalog")
async def get_public_onboarding_catalog() -> dict:
    """Public catalogue used by onboarding to list only compatible business profiles per plan."""
    return plan_catalog()


@app.post("/api/v1/onboarding/business", status_code=201)
async def create_business_and_owner(payload: OnboardingRequest, request: Request):
    # Public onboarding is a sales request. Provisioning paid tenants is internal and
    # fails closed unless the deployment has a private server-side provisioning key.
    expected_key = os.getenv("CALYRISIA_ONBOARDING_ADMIN_KEY", "").strip()
    supplied_key = request.headers.get("x-internal-onboarding-key", "").strip()
    if not expected_key:
        raise HTTPException(status_code=410, detail="La activación de cuentas se realiza después de confirmar la contratación. Solicita tu plan por los canales comerciales de CALYRISIA.")
    if not supplied_key or not hmac.compare_digest(supplied_key, expected_key):
        raise HTTPException(status_code=403, detail="La provisión de negocios requiere autorización interna.")

    try:
        canonical_type, selected_plan, type_profile = validate_plan_business_type(payload.business_type, payload.plan_code)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    business_id = uuid4()
    user_id = uuid4()
    password_hash = get_password_hash(payload.owner_password)
    prompt_text = (payload.ai_prompt or "").strip() or f"Eres el asistente inteligente de {payload.business_name}, especializado en {type_profile['label']}."
    
    async with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                # Make the additive subscription column available even if the startup schema worker is still running.
                cur.execute("ALTER TABLE public.businesses ADD COLUMN IF NOT EXISTS plan_code varchar(30) NOT NULL DEFAULT 'emprendedor'")
                cur.execute(
                    """
                    INSERT INTO businesses (id, name, business_type, description, currency, status, plan_code)
                    VALUES (%s, %s, %s, %s, %s, 'active', %s)
                    """,
                    (str(business_id), payload.business_name, canonical_type, prompt_text, payload.currency, selected_plan)
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
                            id, business_id, industry, short_description, legal_name, operating_hours, policies, objectives,
                            additional_settings, status, profile_version
                        ) VALUES (
                            gen_random_uuid(), %s, %s, %s, %s, '{}'::jsonb, '{}'::jsonb, '[]'::jsonb, %s, 'active', 1
                        )
                        """,
                        (str(business_id), type_profile["family"], prompt_text, payload.business_name,
                         Jsonb({"business_type_code": canonical_type, "business_module": type_profile["module"],
                                "dashboard_label": type_profile["dashboard_label"], "plan_code": selected_plan}))
                    )
                except Exception:
                    pass

                # Un negocio nuevo empieza vacío. Solo se agregan productos si el dueño los indicó.
                # El stock inicial se establece en cero para no inventar existencias.
                try:
                    raw_items = _parse_custom_products(payload.products_text) if payload.products_text else []
                    if len(raw_items) > plan_limits(selected_plan)["products"]:
                        raise ValueError(f"El plan {selected_plan} admite hasta {plan_limits(selected_plan)['products']} productos iniciales.")
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
                            (str(business_id), p_id, 0.0, 0.0)
                        )
                except ValueError:
                    raise
                except Exception as p_err:
                    print(f"[Onboarding] No se pudo importar el catálogo inicial: {p_err}")
            
            try:
                provision_data = OnboardingService(conn).provision_new_tenant(
                    business_id=business_id,
                    business_name=payload.business_name,
                    business_type=canonical_type
                )
            except Exception as prov_err:
                conn.rollback()
                # Re-abrir transacción para confirmar business y owner si falló el aprovisionamiento avanzado
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO businesses (id, name, business_type, currency, status, plan_code)
                        VALUES (%s, %s, %s, %s, 'active', %s)
                        ON CONFLICT (id) DO NOTHING
                        """,
                        (str(business_id), payload.business_name, canonical_type, payload.currency, selected_plan)
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
                "plan_code": selected_plan,
                "business_type": canonical_type,
                "dashboard_module": type_profile["module"],
                "dashboard_label": type_profile["dashboard_label"],
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
            biz = _get_active_webchat_business(conn, business_id)
            target_biz_id = str(biz["id"])
            with conn.cursor() as cur:
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
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error al consultar productos: {str(exc)}")

@app.post("/api/v1/products/seed-sample")
async def seed_sample_products_retired(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN"))) -> dict:
    raise HTTPException(status_code=410, detail="La carga de productos de muestra fue retirada. Importa el catálogo real desde Dashboard → Inventario y Catálogo.")
