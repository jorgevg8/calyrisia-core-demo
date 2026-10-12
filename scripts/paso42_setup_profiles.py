
import asyncio
import json
from pathlib import Path
from uuid import uuid4

from app.db import get_connection, open_pool, close_pool

MIGRATION = Path(__file__).resolve().parents[1] / "migration_paso_42_business_type_profiles.sql"
PROFILES = {'retail': {'display_name': 'Retail', 'description': 'Tiendas y comercios que venden productos y necesitan foco en catálogo, inventario y ventas.', 'aliases': ['retail', 'tienda', 'comercio', 'ecommerce', 'technology / retail'], 'tone': 'claro, comercial y orientado a producto', 'priorities': ['ventas', 'inventario', 'disponibilidad', 'respuesta rápida'], 'operational_focus': ['productos', 'precios', 'stock', 'pedidos', 'clientes'], 'faq_topics': ['productos', 'precios', 'stock', 'envíos', 'cambios y devoluciones'], 'default_actions': ['consultar_producto', 'consultar_inventario', 'preparar_pedido'], 'approval_required': ['cambios_de_precio', 'reembolsos', 'compras_a_proveedor', 'ajustes_de_inventario'], 'response_rules': ['priorizar disponibilidad real', 'no prometer stock sin consultar inventario']}, 'services': {'display_name': 'Servicios', 'description': 'Negocios de servicios donde la conversión depende de entender la necesidad y coordinar la prestación.', 'aliases': ['servicios', 'service', 'agency', 'agencia'], 'tone': 'consultivo, claro y orientado a resolver la necesidad', 'priorities': ['calificación', 'agenda', 'seguimiento', 'conversión'], 'operational_focus': ['servicios', 'disponibilidad', 'leads', 'citas', 'seguimientos'], 'faq_topics': ['servicios', 'precios', 'disponibilidad', 'proceso', 'tiempos'], 'default_actions': ['calificar_lead', 'consultar_servicio', 'crear_cita', 'crear_seguimiento'], 'approval_required': ['descuentos', 'cambios_de_precio', 'reembolsos'], 'response_rules': ['identificar la necesidad antes de recomendar', 'proponer siguiente paso claro']}, 'clinic': {'display_name': 'Clínica', 'description': 'Clínicas y centros de atención donde la coordinación y el manejo prudente de información son prioritarios.', 'aliases': ['clinica', 'clínica', 'clinic', 'salud', 'healthcare', 'medical'], 'tone': 'profesional, prudente y orientado a coordinación', 'priorities': ['agenda', 'seguimiento', 'atención humana', 'claridad de proceso'], 'operational_focus': ['servicios', 'citas', 'pacientes', 'seguimiento', 'handoff'], 'faq_topics': ['servicios', 'horarios', 'ubicación', 'preparación', 'citas'], 'default_actions': ['consultar_servicio', 'consultar_disponibilidad', 'crear_cita', 'handoff_humano'], 'approval_required': ['cambios_de_precio', 'reembolsos', 'acciones clínicas', 'acciones sensibles sobre pacientes'], 'response_rules': ['no inventar información clínica', 'derivar a humano cuando corresponda', 'separar coordinación de diagnóstico']}, 'restaurant': {'display_name': 'Restaurante', 'description': 'Restaurantes y negocios de alimentos con foco en menú, disponibilidad, pedidos y horarios.', 'aliases': ['restaurante', 'restaurant', 'food', 'cafeteria', 'cafe', 'bar'], 'tone': 'rápido, amable y orientado al pedido', 'priorities': ['pedidos', 'disponibilidad', 'horarios', 'tiempos de preparación'], 'operational_focus': ['menú', 'productos', 'pedidos', 'stock', 'horarios'], 'faq_topics': ['menú', 'precios', 'ingredientes', 'horarios', 'entrega'], 'default_actions': ['consultar_producto', 'consultar_inventario', 'preparar_pedido'], 'approval_required': ['reembolsos', 'cambios_de_precio', 'ajustes_de_inventario'], 'response_rules': ['priorizar rapidez y disponibilidad real', 'confirmar detalles críticos del pedido']}, 'professional': {'display_name': 'Profesional', 'description': 'Profesionales independientes y despachos donde el valor está en el conocimiento, agenda y seguimiento.', 'aliases': ['profesional', 'professional', 'consultor', 'consultoria', 'abogado', 'contador', 'freelance'], 'tone': 'profesional, consultivo y preciso', 'priorities': ['leads', 'agenda', 'seguimiento', 'conversión'], 'operational_focus': ['servicios', 'citas', 'clientes', 'seguimientos', 'conocimiento'], 'faq_topics': ['servicios', 'tarifas', 'disponibilidad', 'proceso', 'agenda'], 'default_actions': ['consultar_servicio', 'calificar_lead', 'crear_cita', 'crear_seguimiento'], 'approval_required': ['descuentos', 'cambios_de_precio', 'reembolsos'], 'response_rules': ['ser preciso', 'pedir solo los datos necesarios', 'proponer siguiente paso']}}

async def main():
    sql = MIGRATION.read_text(encoding="utf-8")
    open_pool()
    try:
        async with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                for key, payload in PROFILES.items():
                    cur.execute(
                        "SELECT id FROM business_type_profiles WHERE profile_key = %s",
                        (key,),
                    )
                    if cur.fetchone():
                        cur.execute(
                            """
                            UPDATE business_type_profiles
                            SET display_name=%s, description=%s, config=%s, updated_at=NOW(), enabled=TRUE
                            WHERE profile_key=%s
                            """,
                            (payload["display_name"], payload["description"], json.dumps(payload, ensure_ascii=False), key),
                        )
                    else:
                        cur.execute(
                            """
                            INSERT INTO business_type_profiles (id, profile_key, display_name, description, version, config, enabled)
                            VALUES (%s,%s,%s,%s,1,%s,TRUE)
                            """,
                            (str(uuid4()), key, payload["display_name"], payload["description"], json.dumps(payload, ensure_ascii=False)),
                        )
            conn.commit()
    finally:
        close_pool()

    print("=" * 72)
    print("GALAXY PASO 42 — BUSINESS TYPE PROFILES SETUP")
    print("=" * 72)
    print("[PASS] Tabla business_type_profiles lista")
    print(f"[PASS] {len(PROFILES)} perfiles base sembrados/actualizados")
    print("[INFO] Los perfiles son datos; puedes añadir/editar verticales sin cambiar el Core.")
    print("=" * 72)

if __name__ == "__main__":
    asyncio.run(main())
