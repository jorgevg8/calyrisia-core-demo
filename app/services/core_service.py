from uuid import UUID

import psycopg
from fastapi import HTTPException

from app.services.tenant_guard import TenantGuard, TenantIsolationError
from app.schemas import IncomingMessage
from app.services.customer_360_service import Customer360Service


class GalaxyCoreService:
    def __init__(self, conn):
        self.conn = conn
        self.tenant = TenantGuard(conn)

    def _business_exists(self, business_id: UUID) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM businesses WHERE id = %s",
                (business_id,),
            )
            return cur.fetchone() is not None

    def _conversation_belongs_to_business(self, conversation_id: UUID, business_id: UUID) -> bool:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM conversations WHERE id = %s AND business_id = %s",
                (conversation_id, business_id),
            )
            return cur.fetchone() is not None

    def handle_incoming_message(self, payload: IncomingMessage) -> dict:
        try:
            self.tenant.require_business(payload.business_id)
            self.tenant.require_optional_resource(
                business_id=payload.business_id, resource_type="customer", resource_id=payload.customer_id
            )
        except TenantIsolationError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        if payload.conversation_id:
            try:
                self.tenant.require_resource(
                    business_id=payload.business_id, resource_type="conversation", resource_id=payload.conversation_id
                )
            except TenantIsolationError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
            conversation_id = payload.conversation_id
        else:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (
                        business_id,
                        customer_id,
                        channel,
                        status,
                        started_at,
                        last_message_at,
                        metadata
                    )
                    VALUES (%s, %s, %s, 'active', NOW(), NOW(), %s::jsonb)
                    RETURNING id
                    """,
                    (
                        payload.business_id,
                        payload.customer_id,
                        payload.channel,
                        psycopg.types.json.Jsonb(payload.metadata),
                    ),
                )
                conversation_id = cur.fetchone()[0]

        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO conversation_messages (
                    business_id,
                    conversation_id,
                    customer_id,
                    sender_type,
                    direction,
                    message_type,
                    content,
                    metadata
                )
                VALUES (%s, %s, %s, 'customer', 'inbound', 'text', %s, %s::jsonb)
                RETURNING id
                """,
                (
                    payload.business_id,
                    conversation_id,
                    payload.customer_id,
                    payload.message,
                    psycopg.types.json.Jsonb(payload.metadata),
                ),
            )
            message_id = cur.fetchone()[0]

            cur.execute(
                """
                UPDATE conversations
                SET last_message_at = NOW(), updated_at = NOW()
                WHERE id = %s AND business_id = %s
                """,
                (conversation_id, payload.business_id),
            )

        # Actualización ligera dentro de la misma transacción: mantiene la actividad
        # del cliente sin reconstruir Customer 360 en el camino crítico.
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    "UPDATE customers SET last_interaction_at = NOW() WHERE id = %s AND business_id = %s",
                    (payload.customer_id, payload.business_id),
                )
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise

        return {
            "success": True,
            "stage": "received",
            "business_id": payload.business_id,
            "customer_id": payload.customer_id,
            "conversation_id": conversation_id,
            "message_id": message_id,
            "next_component": "galaxy_brain",
        }
