from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.meta_schemas import NormalizedOmnichannelPayload


class OmnichannelGatewayError(Exception):
    """Error de validación o enrutamiento en el Gateway Omnicanal."""


class OmnichannelGatewayService:
    """Servicio centralizador y normalizador para WhatsApp, Instagram Direct, Facebook Messenger, Telegram y Webchat."""

    VALID_CHANNELS = {"webchat", "whatsapp", "telegram", "instagram", "facebook", "messenger"}

    def __init__(self, conn: Any):
        self.conn = conn

    def process_message(
        self,
        business_id: UUID,
        channel: str,
        direction: str,
        message_content: str,
        customer_id: UUID | None = None,
        conversation_id: UUID | None = None,
    ) -> dict[str, Any]:
        """Unifica la entrada y salida de mensajes de múltiples canales en `omnichannel_messages`."""
        clean_channel = str(channel or "").strip().lower()
        if clean_channel not in self.VALID_CHANNELS:
            raise OmnichannelGatewayError(f"Canal de comunicación no soportado o inválido: {channel}")
        if clean_channel == "messenger":
            clean_channel = "facebook"

        msg_id = str(uuid4())
        with self.conn.cursor() as cur:
            try:
                cur.execute("SAVEPOINT sp_omni_table")
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS public.omnichannel_messages (
                        id uuid PRIMARY KEY,
                        business_id uuid NOT NULL,
                        customer_id uuid,
                        conversation_id uuid,
                        channel varchar(40) NOT NULL,
                        direction varchar(20) NOT NULL,
                        message_content text NOT NULL,
                        status varchar(30) NOT NULL DEFAULT 'delivered',
                        created_at timestamptz NOT NULL DEFAULT now()
                    )
                    """
                )
                cur.execute("RELEASE SAVEPOINT sp_omni_table")
            except Exception:
                try:
                    cur.execute("ROLLBACK TO SAVEPOINT sp_omni_table")
                except Exception:
                    pass

            cur.execute(
                """
                INSERT INTO omnichannel_messages (id, business_id, customer_id, conversation_id, channel, direction, message_content, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'delivered')
                RETURNING id, channel, direction, status, message_content
                """,
                (
                    msg_id,
                    str(business_id),
                    str(customer_id) if customer_id else None,
                    str(conversation_id) if conversation_id else None,
                    clean_channel,
                    direction,
                    message_content,
                ),
            )
            row = cur.fetchone()
        self.conn.commit()

        return {
            "id": str(row[0]),
            "channel": row[1],
            "direction": row[2],
            "status": row[3],
            "message_content": row[4],
        }

    @staticmethod
    def _parse_timestamp(raw_ts: Any) -> datetime:
        if isinstance(raw_ts, datetime):
            return raw_ts if raw_ts.tzinfo else raw_ts.replace(tzinfo=timezone.utc)
        if raw_ts is not None:
            try:
                val = float(raw_ts)
                if val > 1e12:
                    val = val / 1000.0
                if val > 0:
                    return datetime.fromtimestamp(val, tz=timezone.utc)
            except (ValueError, TypeError, OSError):
                pass
            if isinstance(raw_ts, str) and raw_ts.strip():
                try:
                    dt = datetime.fromisoformat(raw_ts.strip().replace("Z", "+00:00"))
                    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
                except ValueError:
                    pass
        return datetime.now(timezone.utc)

    @staticmethod
    def _extract_evolution_message_text(msg_obj: dict[str, Any]) -> str:
        """Extrae el texto limpio de un objeto `message` de Evolution API / Baileys."""
        if not isinstance(msg_obj, dict):
            return ""
        inner = msg_obj.get("message") if isinstance(msg_obj.get("message"), dict) else msg_obj
        if not isinstance(inner, dict):
            return ""

        # Desempaquetar contenedores efímeros o viewOnce si existen
        for wrapper_key in ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2", "documentWithCaptionMessage"):
            wrapped = inner.get(wrapper_key)
            if isinstance(wrapped, dict) and isinstance(wrapped.get("message"), dict):
                inner = wrapped["message"]

        candidates = [
            inner.get("conversation"),
            (inner.get("extendedTextMessage") or {}).get("text") if isinstance(inner.get("extendedTextMessage"), dict) else None,
            (inner.get("imageMessage") or {}).get("caption") if isinstance(inner.get("imageMessage"), dict) else None,
            (inner.get("videoMessage") or {}).get("caption") if isinstance(inner.get("videoMessage"), dict) else None,
            (inner.get("documentMessage") or {}).get("caption") if isinstance(inner.get("documentMessage"), dict) else None,
            (inner.get("buttonsResponseMessage") or {}).get("selectedDisplayText") if isinstance(inner.get("buttonsResponseMessage"), dict) else None,
            (inner.get("buttonsResponseMessage") or {}).get("selectedButtonId") if isinstance(inner.get("buttonsResponseMessage"), dict) else None,
            (inner.get("listResponseMessage") or {}).get("title") if isinstance(inner.get("listResponseMessage"), dict) else None,
            ((inner.get("listResponseMessage") or {}).get("singleSelectReply") or {}).get("selectedRowId")
            if isinstance(inner.get("listResponseMessage"), dict)
            else None,
            (inner.get("templateButtonReplyMessage") or {}).get("selectedDisplayText")
            if isinstance(inner.get("templateButtonReplyMessage"), dict)
            else None,
            msg_obj.get("text") if isinstance(msg_obj.get("text"), str) else None,
            msg_obj.get("message_text") if isinstance(msg_obj.get("message_text"), str) else None,
            msg_obj.get("body") if isinstance(msg_obj.get("body"), str) else None,
        ]
        for c in candidates:
            if isinstance(c, str) and c.strip():
                return c.strip()
        return ""

    @staticmethod
    def _extract_evolution_sender_phone(item: dict[str, Any]) -> str:
        """Extrae el número de teléfono limpio del remitente desde `key` o campos directos."""
        key = item.get("key") if isinstance(item.get("key"), dict) else {}
        remote_jid = str(key.get("remoteJid") or item.get("remoteJid") or item.get("from") or "").strip()
        sender_pn = str(
            key.get("senderPn")
            or key.get("remoteJidAlt")
            or item.get("senderPn")
            or item.get("sender_phone")
            or item.get("sender_id")
            or item.get("phone")
            or ""
        ).strip()

        # En WhatsApp multi-device con identificadores @lid, usar senderPn/remoteJidAlt si está disponible
        raw_target = sender_pn if (remote_jid.endswith("@lid") and sender_pn) else (remote_jid or sender_pn)
        base_part = raw_target.split("@")[0].split(":")[0]
        digits = re.sub(r"\D", "", base_part)
        return digits or base_part.strip()

    @classmethod
    def normalize_whatsapp_webhook(
        cls,
        raw_body: dict[str, Any],
        tenant_id: str | UUID,
        instance_name: str | None = None,
    ) -> list[NormalizedOmnichannelPayload]:
        """Convierte cualquier payload entrante de Evolution API / WhatsApp en una lista de `NormalizedOmnichannelPayload`."""
        if not isinstance(raw_body, dict):
            return []
        tenant_uuid = UUID(str(tenant_id).strip())
        resolved_instance = str(
            instance_name
            or raw_body.get("instance")
            or (raw_body.get("data") if isinstance(raw_body.get("data"), dict) else {}).get("instance")
            or ""
        ).strip()

        raw_items: list[dict[str, Any]] = []
        data_field = raw_body.get("data")
        if isinstance(data_field, list):
            raw_items.extend(x for x in data_field if isinstance(x, dict))
        elif isinstance(data_field, dict):
            if isinstance(data_field.get("messages"), list):
                raw_items.extend(x for x in data_field["messages"] if isinstance(x, dict))
            else:
                raw_items.append(data_field)
        elif isinstance(raw_body.get("messages"), list):
            raw_items.extend(x for x in raw_body["messages"] if isinstance(x, dict))
        else:
            raw_items.append(raw_body)

        normalized: list[NormalizedOmnichannelPayload] = []
        for item in raw_items:
            key = item.get("key") if isinstance(item.get("key"), dict) else {}
            if bool(key.get("fromMe") or item.get("fromMe")):
                continue
            remote_jid = str(key.get("remoteJid") or item.get("remoteJid") or "").strip().lower()
            if remote_jid and (
                remote_jid == "status@broadcast"
                or remote_jid.endswith("@g.us")
                or remote_jid.endswith("@newsletter")
            ):
                continue

            text = cls._extract_evolution_message_text(item)
            if not text and isinstance(raw_body.get("message_text"), str):
                text = raw_body["message_text"].strip()
            if not text and isinstance(raw_body.get("message"), str):
                text = raw_body["message"].strip()
            if not text:
                continue

            sender_id = cls._extract_evolution_sender_phone(item)
            if not sender_id:
                sender_id = cls._extract_evolution_sender_phone(raw_body)
            if not sender_id:
                continue

            sender_name = str(
                item.get("pushName")
                or raw_body.get("pushName")
                or item.get("sender_name")
                or raw_body.get("sender_name")
                or f"Cliente WhatsApp ({sender_id[-4:]})"
            ).strip()[:180]
            msg_id = str(key.get("id") or item.get("id") or item.get("message_id") or "").strip() or None
            ts = cls._parse_timestamp(item.get("messageTimestamp") or item.get("timestamp") or raw_body.get("date_time"))

            normalized.append(
                NormalizedOmnichannelPayload(
                    tenant_id=tenant_uuid,
                    channel="whatsapp",
                    sender_id=sender_id[:160],
                    sender_name=sender_name,
                    message_text=text[:10000],
                    timestamp=ts,
                    external_message_id=msg_id,
                    instance_or_page_id=resolved_instance or None,
                    metadata={
                        "provider": "evolution",
                        "instance_name": resolved_instance,
                        "remote_jid": remote_jid or f"{sender_id}@s.whatsapp.net",
                    },
                )
            )

        return normalized

    @classmethod
    def normalize_meta_webhook(
        cls,
        raw_body: dict[str, Any],
        tenant_id: str | UUID | None = None,
    ) -> list[NormalizedOmnichannelPayload]:
        """Normaliza eventos `messages` y `messaging_postbacks` de Facebook Messenger, Instagram Direct y WhatsApp Cloud."""
        if not isinstance(raw_body, dict):
            return []
        obj_type = str(raw_body.get("object") or "").strip().lower()
        entries = raw_body.get("entry") if isinstance(raw_body.get("entry"), list) else []
        if not entries:
            return []

        fallback_tenant = UUID(str(tenant_id).strip()) if tenant_id else UUID(int=0)
        results: list[NormalizedOmnichannelPayload] = []

        if obj_type == "whatsapp_business_account":
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                changes = entry.get("changes") if isinstance(entry.get("changes"), list) else []
                for change in changes:
                    if not isinstance(change, dict) or change.get("field") not in (None, "messages"):
                        continue
                    value = change.get("value") if isinstance(change.get("value"), dict) else {}
                    metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else {}
                    phone_id = str(metadata.get("phone_number_id") or "").strip()
                    contacts = value.get("contacts") if isinstance(value.get("contacts"), list) else []
                    messages = value.get("messages") if isinstance(value.get("messages"), list) else []
                    for msg in messages:
                        if not isinstance(msg, dict):
                            continue
                        sender_id = str(msg.get("from") or "").strip()
                        msg_type = str(msg.get("type") or "").lower()
                        text = ""
                        if msg_type == "text":
                            text = str((msg.get("text") or {}).get("body") or "").strip()
                        elif msg_type == "interactive":
                            inter = msg.get("interactive") or {}
                            rep = inter.get("button_reply") or inter.get("list_reply") or {}
                            text = str(rep.get("title") or rep.get("id") or "").strip()
                        elif msg_type == "button":
                            text = str((msg.get("button") or {}).get("text") or "").strip()
                        if not sender_id or not text:
                            continue
                        sender_name = f"Cliente WhatsApp ({sender_id[-4:]})"
                        for c in contacts:
                            if isinstance(c, dict) and str(c.get("wa_id") or "") == sender_id:
                                prof = c.get("profile") if isinstance(c.get("profile"), dict) else {}
                                sender_name = str(prof.get("name") or sender_name)
                                break
                        results.append(
                            NormalizedOmnichannelPayload(
                                tenant_id=fallback_tenant,
                                channel="whatsapp",
                                sender_id=sender_id[:160],
                                sender_name=sender_name[:180],
                                message_text=text[:10000],
                                timestamp=cls._parse_timestamp(msg.get("timestamp")),
                                external_message_id=str(msg.get("id") or "") or None,
                                instance_or_page_id=phone_id or None,
                                metadata={"object": obj_type, "phone_number_id": phone_id},
                            )
                        )
            return results

        if obj_type not in {"page", "instagram"}:
            return []

        channel = "instagram" if obj_type == "instagram" else "facebook"
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            entry_id = str(entry.get("id") or "").strip()
            messaging_events = entry.get("messaging") if isinstance(entry.get("messaging"), list) else []
            for evt in messaging_events:
                if not isinstance(evt, dict):
                    continue
                msg = evt.get("message") if isinstance(evt.get("message"), dict) else {}
                if bool(msg.get("is_echo")):
                    continue
                postback = evt.get("postback") if isinstance(evt.get("postback"), dict) else {}
                quick_reply = msg.get("quick_reply") if isinstance(msg.get("quick_reply"), dict) else {}
                text_value = (
                    msg.get("text")
                    or quick_reply.get("payload")
                    or postback.get("title")
                    or postback.get("payload")
                )
                text = str(text_value or "").strip()
                sender = evt.get("sender") if isinstance(evt.get("sender"), dict) else {}
                sender_id = str(sender.get("id") or "").strip()
                recipient = evt.get("recipient") if isinstance(evt.get("recipient"), dict) else {}
                recipient_id = str(recipient.get("id") or entry_id).strip()
                if not text or not sender_id or sender_id in {recipient_id, entry_id}:
                    continue

                event_type = "messaging_postbacks" if postback and not msg.get("text") else "messages"
                sender_name = f"Usuario {'IG' if channel == 'instagram' else 'FB'} #{sender_id[-4:]}"
                results.append(
                    NormalizedOmnichannelPayload(
                        tenant_id=fallback_tenant,
                        channel=channel,
                        sender_id=sender_id[:160],
                        sender_name=sender_name,
                        message_text=text[:10000],
                        timestamp=cls._parse_timestamp(evt.get("timestamp") or entry.get("time")),
                        external_message_id=str(msg.get("mid") or postback.get("mid") or "") or None,
                        instance_or_page_id=recipient_id or entry_id or None,
                        metadata={
                            "object": obj_type,
                            "event_type": event_type,
                            "entry_id": entry_id,
                            "recipient_id": recipient_id,
                        },
                    )
                )

        return results