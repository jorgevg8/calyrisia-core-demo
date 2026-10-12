from uuid import UUID, uuid4

class OmnichannelGatewayError(Exception):
    pass

class OmnichannelGatewayService:
    def __init__(self, conn):
        self.conn = conn

    def process_message(self, business_id: UUID, channel: str, direction: str, message_content: str, customer_id: UUID = None, conversation_id: UUID = None) -> dict:
        """Unifica la entrada y salida de mensajes de múltiples canales."""
        with self.conn.cursor() as cur:
            msg_id = str(uuid4())
            
            if channel not in ['webchat', 'whatsapp', 'telegram']:
                raise OmnichannelGatewayError(f"Canal de comunicación no soportado o inválido: {channel}")
            
            cur.execute("""
                INSERT INTO omnichannel_messages (id, business_id, customer_id, conversation_id, channel, direction, message_content, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'delivered')
                RETURNING id, channel, direction, status, message_content
            """, (msg_id, str(business_id), str(customer_id) if customer_id else None, str(conversation_id) if conversation_id else None, channel, direction, message_content))
            
            row = cur.fetchone()
            self.conn.commit()
            
            return {
                "id": str(row[0]),
                "channel": row[1],
                "direction": row[2],
                "status": row[3],
                "message_content": row[4]
            }