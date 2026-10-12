
import getpass
import time
from typing import Any

import httpx

BASE = "http://127.0.0.1:8000"


def post_json(client, path, payload, headers=None):
    r = client.post(BASE + path, json=payload, headers=headers or {})
    r.raise_for_status()
    return r.json()


def login(client, email, password):
    r = client.post(BASE + "/api/v1/auth/login", data={"username": email, "password": password})
    r.raise_for_status()
    return r.json()


def check_profile(client, token):
    r = client.get(BASE + "/api/v1/business-type-profiles/current", headers={"Authorization": f"Bearer {token}"})
    r.raise_for_status()
    return r.json()["profile"]


def main():
    print("=" * 72)
    print("GALAXY PASO 42 — BUSINESS TYPE PROFILES TEST")
    print("=" * 72)
    with httpx.Client(timeout=30) as client:
        email_a = f"step42.retail.{int(time.time())}@galaxy.test"
        email_b = f"step42.clinic.{int(time.time())}@galaxy.test"
        password = "GalaxyStep42!2026"

        retail = post_json(client, "/api/v1/onboarding/business", {
            "name": "Step42 Retail Test",
            "business_type": "Retail",
            "industry": "Retail",
            "country": "United States",
        })
        clinic = post_json(client, "/api/v1/onboarding/business", {
            "name": "Step42 Clinic Test",
            "business_type": "Clínica",
            "industry": "Healthcare",
            "country": "United States",
        })
        print("[PASS] Se crearon Business A (Retail) y Business B (Clínica)")

        for bid, email, name in [
            (retail["business_id"], email_a, "Owner Retail"),
            (clinic["business_id"], email_b, "Owner Clinic"),
        ]:
            post_json(client, f"/api/v1/onboarding/business/{bid}/owner", {
                "email": email,
                "password": password,
                "full_name": name,
                "phone": "555-0100",
            })
        print("[PASS] Cada tenant recibió su OWNER")

        tok_a = login(client, email_a, password)["access_token"]
        tok_b = login(client, email_b, password)["access_token"]
        prof_a = check_profile(client, tok_a)
        prof_b = check_profile(client, tok_b)
        assert prof_a["profile_key"] == "retail"
        assert prof_b["profile_key"] == "clinic"
        print(f"[PASS] Retail resolvió profile_key={prof_a['profile_key']}")
        print(f"[PASS] Clínica resolvió profile_key={prof_b['profile_key']}")

        same_question = "¿Qué debería priorizar Galaxy al atender a un cliente?"
        print(f"[INFO] Misma pregunta conceptual: {same_question}")
        print(f"[INFO] Retail prioridades: {prof_a['config']['priorities']}")
        print(f"[INFO] Clínica prioridades: {prof_b['config']['priorities']}")
        assert prof_a["config"]["priorities"] != prof_b["config"]["priorities"]
        print("[PASS] Los perfiles cambian prioridades y comportamiento base")

        # Integration with the real Galaxy ContextManager (the Brain consumes this context).
        ctx_a = client.get(
            BASE + "/api/v1/context",
            params={"business_id": retail["business_id"]},
            headers={"Authorization": f"Bearer {tok_a}"},
        )
        ctx_a.raise_for_status()
        context_profile_a = ctx_a.json()["context"]["business_type_profile"]
        assert context_profile_a["profile_key"] == "retail"
        print("[PASS] ContextManager inyecta business_type_profile al contexto del Brain")

        ctx_cross = client.get(
            BASE + "/api/v1/context",
            params={"business_id": clinic["business_id"]},
            headers={"Authorization": f"Bearer {tok_a}"},
        )
        assert ctx_cross.status_code == 403
        print("[PASS] Multi-tenant: Retail no puede leer el contexto de Clínica")

        # Override without code changes.
        override = {
            "overrides": {
                "tone": "muy directo y comercial",
                "priorities": ["ventas", "stock", "clientes VIP"],
                "response_rules": ["usar tono breve", "priorizar siguiente paso"]
            }
        }
        patched = client.patch(BASE + "/api/v1/business-type-profiles/current/overrides", json=override, headers={"Authorization": f"Bearer {tok_a}"})
        patched.raise_for_status()
        p2 = patched.json()["profile"]
        assert p2["config"]["tone"] == override["overrides"]["tone"]
        assert p2["config"]["priorities"] == override["overrides"]["priorities"]
        print("[PASS] OWNER puede aplicar overrides por negocio sin editar código")

        cleared = client.delete(BASE + "/api/v1/business-type-profiles/current/overrides", headers={"Authorization": f"Bearer {tok_a}"})
        cleared.raise_for_status()
        p3 = cleared.json()["profile"]
        assert p3["config"]["priorities"] == prof_a["config"]["priorities"]
        print("[PASS] OWNER puede restaurar el perfil base")

    print("=" * 72)
    print("PASO 42 — BUSINESS TYPE PROFILES TEST: PASSED")
    print("=" * 72)

if __name__ == "__main__":
    main()
