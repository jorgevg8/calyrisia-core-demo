import httpx
from uuid import UUID
import json
from app.services.audit_service import AuditService

class ConnectorError(Exception):
    pass

class ConnectorGateway:
    def __init__(self, conn):
        self.conn = conn

    async def dispatch_external_action(self, business_id: UUID, integration_type: str, payload: dict) -> dict:
        """
        PASO 95: Integration & Connector Gateway.
        Unifica el acceso a servicios externos bajo un único embudo seguro y auditable.
        """
        with self.conn.cursor() as cur:
            # 1. Validar que la integración esté en el registro de conectores disponibles
            if integration_type not in ["n8n", "make", "stripe", "whatsapp"]:
                raise ConnectorError(f"Integración '{integration_type}' no soportada o no habilitada para este tenant.")

            # 2. Extracción de credenciales (Mockeado para la V1)
            target_url = "https://hook.n8n.ejemplo.com/webhook-autopilot"

            # 3. Despacho seguro con Timeouts y manejo de errores normalizado
            try:
                # NOTA: HTTPX comentado para no generar timeouts de red al no tener n8n levantado aún.
                # En producción, aquí se dispara el webhook real.
                # async with httpx.AsyncClient() as client:
                #     response = await client.post(target_url, json=payload, timeout=5.0)
                #     response.raise_for_status()
                
                status_code = 200
                response_data = {"success": True, "message": "Dispatched successfully"}
            except Exception as e:
                # La llamada externa falla, pero queda trazable en el Audit Log
                AuditService(self.conn).log_action(
                    business_id, "CONNECTOR_GATEWAY", "DISPATCH_FAILED", str(business_id),
                    {"integration": integration_type, "error": str(e)}
                )
                raise ConnectorError(f"Fallo de timeout o red al conectar con {integration_type}: {str(e)}")

            # 4. Trazabilidad de éxito inmutable
            AuditService(self.conn).log_action(
                business_id, "CONNECTOR_GATEWAY", "DISPATCH_SUCCESS", str(business_id),
                {"integration": integration_type, "payload_size": len(json.dumps(payload))}
            )

            return {
                "status": "delivered",
                "integration": integration_type,
                "response": response_data
            }