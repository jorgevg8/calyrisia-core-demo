"""Cliente asíncrono para Evolution API (WhatsApp Multitenant / QR).

Permite levantar instancias dinámicas por cada `tenant_id`, obtener el código QR
para escanear desde el teléfono y enviar respuestas generadas por la IA mediante
peticiones HTTP asíncronas (`httpx`).
"""
from __future__ import annotations

import base64
import hashlib
import logging
import re
from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EvolutionAPIError(RuntimeError):
    """Error normalizado devuelto por Evolution API o por su transporte."""


class EvolutionWhatsAppService:
    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = (settings.evolution_api_url or "").strip().rstrip("/")
        self.api_key = (settings.evolution_api_key or "").strip()
        self.webhook_url = (
            (settings.evolution_webhook_url or "").strip()
            or f"{(settings.public_base_url or '').rstrip('/')}/api/webhooks/whatsapp"
        )
        self.timeout = httpx.Timeout(25.0, connect=8.0)

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.api_key)

    @staticmethod
    def build_instance_name(tenant_id: str) -> str:
        compact = re.sub(r"[^a-fA-F0-9]", "", str(tenant_id))
        if len(compact) == 32:
            return f"calyrisia_{compact.lower()}"
        safe = re.sub(r"[^a-zA-Z0-9_-]", "", str(tenant_id))[:48]
        return f"calyrisia_{safe or 'tenant'}"

    @staticmethod
    def extract_tenant_prefix_from_instance(instance_name: str | None) -> str | None:
        value = str(instance_name or "").strip()
        match = re.fullmatch(r"calyrisia[_-]([0-9a-fA-F]{32})", value)
        if not match:
            return None
        compact = match.group(1)
        return f"{compact[:8]}-{compact[8:12]}-{compact[12:16]}-{compact[16:20]}-{compact[20:]}".lower()

    @staticmethod
    def _normalize_qr_data_url(raw_qr: Any) -> str | None:
        if not raw_qr:
            return None
        value = str(raw_qr).strip()
        if value.startswith("data:image/"):
            return value
        if value.startswith("<svg") or value.startswith("<?xml"):
            encoded = base64.b64encode(value.encode("utf-8")).decode("ascii")
            return f"data:image/svg+xml;base64,{encoded}"
        try:
            decoded = base64.b64decode(value, validate=False)
            if decoded.startswith(b"\x89PNG\r\n\x1a\n"):
                return f"data:image/png;base64,{value}"
            if decoded.startswith(b"\xff\xd8\xff"):
                return f"data:image/jpeg;base64,{value}"
        except Exception:
            pass
        if len(value) > 100:
            return f"data:image/png;base64,{value}"
        return None

    async def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.is_configured:
            raise EvolutionAPIError("Evolution API no está configurada. Define EVOLUTION_API_URL y EVOLUTION_API_KEY.")
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"apikey": self.api_key, "Accept": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise EvolutionAPIError(f"No se pudo conectar con Evolution API: {exc}") from exc

        body_text = response.text[:2000]
        try:
            body = response.json() if response.content else {}
        except ValueError:
            body = {"raw": body_text}
        if not response.is_success:
            detail = body.get("message") if isinstance(body, dict) else None
            if isinstance(detail, list):
                detail = "; ".join(str(x) for x in detail)
            detail = str(detail or body.get("error") or body_text or response.reason_phrase) if isinstance(body, dict) else body_text
            raise EvolutionAPIError(f"Evolution API ({response.status_code}): {detail}")
        return body if isinstance(body, dict) else {"data": body}

    @staticmethod
    def _extract_qr(payload: dict[str, Any]) -> tuple[str | None, str | None]:
        data = payload.get("data") if isinstance(payload.get("data"), dict) else payload
        qrcode = data.get("qrcode") if isinstance(data.get("qrcode"), dict) else {}
        qr_value = (
            qrcode.get("base64")
            or qrcode.get("code")
            or data.get("base64")
            or data.get("qr")
            or data.get("code")
        )
        pairing = qrcode.get("pairingCode") or data.get("pairingCode") or data.get("pairing_code")
        return EvolutionWhatsAppService._normalize_qr_data_url(qr_value), str(pairing) if pairing else None

    async def create_or_connect_instance(self, tenant_id: str, pairing_phone: str = "") -> dict[str, Any]:
        instance_name = self.build_instance_name(tenant_id)
        webhook = {
            "url": self.webhook_url,
            "enabled": bool(self.webhook_url),
            "base64": False,
            "events": ["MESSAGES_UPSERT", "CONNECTION_UPDATE", "QRCODE_UPDATED"],
        }
        create_payload: dict[str, Any] = {
            "instanceName": instance_name,
            "integration": "WHATSAPP-BAILEYS",
            "qrcode": True,
            "webhook": webhook,
        }
        if pairing_phone.strip():
            create_payload["number"] = re.sub(r"\D", "", pairing_phone)

        try:
            response = await self._request("POST", "/instance/create", create_payload)
        except EvolutionAPIError as exc:
            message = str(exc).lower()
            if not any(token in message for token in ("already", "exist", "já existe", "duplicat", "409", "403")):
                raise
            response = await self._request("GET", f"/instance/connect/{quote(instance_name, safe='')}")

        qr_data_url, pairing_code = self._extract_qr(response)
        if not qr_data_url:
            try:
                connect_res = await self._request("GET", f"/instance/connect/{quote(instance_name, safe='')}")
                qr_data_url, pairing_code = self._extract_qr(connect_res)
                response = connect_res or response
            except Exception:
                pass

        data = response.get("instance") if isinstance(response.get("instance"), dict) else response.get("data", {})
        state = str(
            (data.get("state") if isinstance(data, dict) else "")
            or response.get("state")
            or response.get("connectionStatus")
            or ""
        ).lower()
        status = "connected" if state in {"open", "connected"} else ("qr_ready" if qr_data_url else "starting")

        try:
            await self._request(
                "POST",
                f"/webhook/set/{quote(instance_name, safe='')}",
                {"webhook": webhook},
            )
        except EvolutionAPIError as exc:
            logger.info("Evolution webhook no se pudo configurar por endpoint dedicado: %s", exc)

        return {
            "instance_name": instance_name,
            "status": status,
            "qr_code_data_url": qr_data_url,
            "qr_code_base64": qr_data_url,
            "pairing_code": pairing_code,
            "webhook_url": self.webhook_url,
            "raw": response,
        }

    async def send_whatsapp_message(
        self,
        tenant_id: str,
        recipient_phone: str,
        text: str,
        instance_name: str | None = None,
    ) -> dict[str, Any]:
        """Envía asíncronamente (vía httpx) la respuesta de la IA a la instancia de WhatsApp del tenant en Evolution API."""
        target = instance_name or self.build_instance_name(tenant_id)
        number = re.sub(r"\D", "", str(recipient_phone or ""))
        if not number:
            raise EvolutionAPIError("El número de WhatsApp del destinatario está vacío o no es válido.")
        response = await self._request(
            "POST",
            f"/message/sendText/{quote(target, safe='')}",
            {"number": number, "text": str(text), "delay": 800},
        )
        return {
            "sent": True,
            "provider": "evolution",
            "instance_name": target,
            "recipient": number,
            "response": response,
        }

    async def disconnect_instance(self, tenant_id: str) -> dict[str, Any]:
        instance_name = self.build_instance_name(tenant_id)
        try:
            return await self._request("DELETE", f"/instance/logout/{quote(instance_name, safe='')}")
        except EvolutionAPIError as exc:
            if any(token in str(exc).lower() for token in ("not connected", "not found", "does not exist")):
                return {"success": True, "already_disconnected": True}
            raise

    @staticmethod
    def generate_fallback_qr_data_url(instance_name: str, tenant_id: str) -> str:
        """Genera un QR SVG en base64 para entornos de prueba sin salida a internet ni Evolution API externa."""
        digest = hashlib.sha256(f"{instance_name}:{tenant_id}".encode("utf-8")).digest()
        cells = []
        size = 21
        cell_px = 8
        margin = 16
        total = size * cell_px + margin * 2
        for r in range(size):
            for c in range(size):
                in_finder = (r < 7 and c < 7) or (r < 7 and c >= size - 7) or (r >= size - 7 and c < 7)
                if in_finder:
                    rr = r if r < 7 else r - (size - 7)
                    cc = c if c < 7 else c - (size - 7)
                    on = rr in (0, 6) or cc in (0, 6) or (2 <= rr <= 4 and 2 <= cc <= 4)
                else:
                    idx = (r * size + c) % len(digest)
                    bit = (digest[idx] >> ((r + c) % 8)) & 1
                    on = bool(bit)
                if on:
                    x = margin + c * cell_px
                    y = margin + r * cell_px
                    cells.append(f'<rect x="{x}" y="{y}" width="{cell_px}" height="{cell_px}" fill="#0f172a"/>')
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total} {total}" width="260" height="260">'
            f'<rect width="100%" height="100%" rx="12" fill="#ffffff"/>'
            + "".join(cells)
            + "</svg>"
        )
        b64 = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return f"data:image/svg+xml;base64,{b64}"
