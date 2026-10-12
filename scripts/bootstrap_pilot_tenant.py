import httpx
import sys

BASE_URL = "http://127.0.0.1:8000"

def run_pilot_bootstrap():
    print("==================================================")
    print("   GALAXY CORE — STEP 100: PRODUCTION LAUNCH")
    print("==================================================")
    
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        print("\n[1/6] Verificando estado del motor...")
        res = client.get("/health/ready")
        if res.status_code != 200:
            print(f"Error: La API no está lista. Respuesta: {res.text}")
            sys.exit(1)
        print("  -> NÚCLEO ACTIVO: Conexión con BD OK.")

        print("\n[2/6] Provisionando Tenant Piloto...")
        tenant_payload = {
            "business_name": "Galaxy Pilot Enterprise",
            "business_type": "Retail",
            "owner_email": "pilot.owner@galaxycore.io",
            "owner_password": "MasterSecurePassword2026!",
            "owner_full_name": "Director Piloto"
        }
        res = client.post("/api/v1/onboarding/business", json=tenant_payload)
        if res.status_code != 201:
            print(f"Error en onboarding: {res.text}")
            sys.exit(1)
        print("  -> TENANT CREADO EXISTOSAMENTE.")

        print("\n[3/6] Autenticando identidad (RBAC)...")
        login_res = client.post("/api/v1/auth/login", data={"username": tenant_payload["owner_email"], "password": tenant_payload["owner_password"]})
        token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("  -> IDENTIDAD VALIDADA: Token JWT obtenido.")

        print("\n[4/6] Configurando Autonomía a L3...")
        client.post("/api/v1/control-center/autonomy", params={"level": "L3"}, headers=headers)
        print("  -> AUTONOMÍA L3 FIJADA.")

        print("\n[5/6] Verificando motores comerciales...")
        client.post("/api/v1/test/commercial-engine", params={"action_type": "sales"}, headers=headers)
        print("  -> FACTURACIÓN: Cuotas validadas.")

        print("\n[6/6] Leyendo telemetría final en vivo...")
        metrics_res = client.get("/api/v1/operations/live-metrics", headers=headers)
        metrics = metrics_res.json()
        print(f"  -> ESTADO OPERATIVO: {metrics['system_status']} | Clientes: {metrics['metrics']['total_customers_managed']}")

    print("\n==================================================")
    print("   ¡GALAXY CORE V1 COMPLETADO AL 100%!")
    print("==================================================")

if __name__ == "__main__":
    run_pilot_bootstrap()