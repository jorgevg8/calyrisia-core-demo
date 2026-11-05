import urllib.request
import urllib.error
import json
import uuid
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

# Tus IDs reales y validados en la base de datos
REAL_BUSINESS_ID = "bc8d44fc-3ab0-442f-acf8-a816a3bcf77f"
REAL_CUSTOMER_ID = "b30c1eff-dfb7-489b-b3d6-eaac24b2960c"

def request_api(endpoint: str, method: str = "GET", data: dict = None) -> dict:
    url = f"{BASE_URL}{endpoint}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode("utf-8") if data else None
    
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        print(f"❌ Error HTTP {e.code} en {endpoint}: {err_body}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error de conexión en {endpoint}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    print("="*72)
    print("GALAXY PASO 40 — PRIMER PILOT REAL (END-TO-END SIMULATION)")
    print("="*72)
    
    print(f"\n[1/5] Usando Business ID real: {REAL_BUSINESS_ID}")
    print(f"       Usando Customer ID real: {REAL_CUSTOMER_ID}")
    
    # 2. Simular interacción del cliente por Autopilot utilizando los IDs reales
    print("\n[2/5] Simulando interacción del cliente (Autopilot con Tenant válido)...")
    conv_id = str(uuid.uuid4())
    
    chat_payload = {
        "business_id": REAL_BUSINESS_ID,
        "customer_id": REAL_CUSTOMER_ID,
        "conversation_id": conv_id,
        "channel": "webchat",
        "message": "Hola, ¿tienen productos disponibles y cuáles son sus precios?"
    }
    
    res_chat = request_api("/autopilot/respond", method="POST", data=chat_payload)
    print(f"🤖 Respuesta de la IA al cliente:\n   --> \"{res_chat.get('response')}\"")
    
    # 3. Analizar negocio con Business Brain
    print("\n[3/5] Ejecutando análisis del Business Brain...")
    analysis_payload = {
        "business_id": REAL_BUSINESS_ID,
        "focus": "sales_and_inventory"
    }
    res_analysis = request_api("/business-brain/analyze", method="POST", data=analysis_payload)
    print(f"🧠 Business Brain ejecutado. Insights generados: {len(res_analysis.get('insights', []))}")
    
    # 4. Consultar métricas de salud del Tenant
    print("\n[4/5] Verificando aislamiento y salud del Tenant...")
    res_health = request_api(f"/tenant/{REAL_BUSINESS_ID}/health")
    print(f"🛡️ Conteos aislados en DB: {res_health.get('tenant_counts')}")
    
    # 5. Validación de Analíticas / Dashboard
    print("\n[5/5] Consultando resumen de Analytics del Piloto...")
    res_analytics = request_api(f"/analytics/overview?business_id={REAL_BUSINESS_ID}")
    print(f"📊 Analíticas del Piloto: {res_analytics.get('analytics')}")
    
    print("\n" + "="*72)
    print("🎉 ¡PASO 40 SUPERADO CON ÉXITO! EL PILOTO REAL ESTÁ OPERATIVO.")
    print("="*72)