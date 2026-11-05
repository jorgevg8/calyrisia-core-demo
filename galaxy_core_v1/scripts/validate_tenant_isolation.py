from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main = (ROOT / "app/main.py").read_text(encoding="utf-8")
schemas = (ROOT / "app/schemas.py").read_text(encoding="utf-8")
widget = (ROOT / "app/static/webchat/app.js").read_text(encoding="utf-8")
dashboard = (ROOT / "app/static/dashboard/index.html").read_text(encoding="utf-8")
migration = (ROOT / "migration_webchat_payment_approval.sql").read_text(encoding="utf-8")

resolver = main[main.index("def _get_active_webchat_business"):main.index("class OwnerRegistrationRequest")]
product_list = main[main.index('@app.get("/api/v1/products/list")'):main.index('@app.post("/api/v1/products/seed-sample")')]
onboarding = main[main.index("async def create_business_and_owner"):main.index("async def register_owner")]

checks = {
    "dashboard payments are filtered only by tenant": "WHERE p.business_id = %s" in main and "OR p.source = 'webchat_demo'" not in main,
    "payment decision locks a row within its tenant": "WHERE id = %s AND business_id = %s\n                       FOR UPDATE" in main,
    "payment status is scoped by business": "SELECT status, order_id, amount, payment_method FROM webchat_payment_requests\n                       WHERE id = %s AND business_id = %s" in main,
    "payment confirmation is scoped by business": "SELECT status, order_id FROM webchat_payment_requests\n                   WHERE id = %s AND business_id = %s" in main,
    "legacy customer reassignment is removed": "ON CONFLICT (id) DO UPDATE SET business_id = EXCLUDED.business_id" not in main,
    "webchat message validates business and customer together": "WHERE c.id = %s AND c.business_id = %s AND b.status = 'active'" in main,
    "new webchat payload requires business_id": "class WebchatMessageRequest(BaseModel):\n    business_id: UUID\n    customer_id: UUID" in schemas,
    "public payment polling passes business_id": "payment/status/${paymentId}?business_id=${encodeURIComponent(state.businessId)}" in widget,
    "webchat does not inherit another tenant from localStorage": 'localStorage.getItem("calyrisia_current_business_id") || null' not in widget,
    "dashboard no longer uses shared fixed customer ID": "11111111-1111-1111-1111-111111111111" not in dashboard and "22222222-2222-2222-2222-222222222222" not in dashboard,
    "default webchat never chooses the newest tenant": "ORDER BY created_at DESC" not in resolver and "WHERE id = %s AND status = 'active'" in resolver,
    "catalog listing is read-only": "INSERT INTO products" not in product_list,
    "new onboarding does not auto-seed products": "_get_default_10_products" not in onboarding and "raw_items = _parse_custom_products(payload.products_text) if payload.products_text else []" in onboarding,
    "database migration binds payment customer to same business": "fk_webchat_payment_customer_tenant" in migration and "FOREIGN KEY (customer_id, business_id)" in migration,
    "payment item fallback is customer-and-tenant scoped": main.count("WHERE customer_id = %s AND business_id = %s AND direction = 'outbound'") >= 2,
    "inventory writes are tenant scoped": "WHERE product_id = %s::uuid AND business_id = %s::uuid" in main,
    "approval does not rewrite the payment tenant": "SET status = 'approved', business_id = %s" not in main and "SET status = 'rejected', business_id = %s" not in main,
    "sample products endpoint requires owner/admin auth": 'async def seed_sample_products_retired(current_user: dict = Depends(auth.require_roles("OWNER", "ADMIN")))' in main,
    "foreign product IDs cannot trigger another tenant inventory match": "if candidate_pid not in owner_product_names:\n                                continue" in main,
}

failed = [name for name, ok in checks.items() if not ok]
for name, ok in checks.items():
    print(("OK  " if ok else "FAIL ") + name)
if failed:
    raise SystemExit(1)
print(f"OK: {len(checks)} tenant-isolation checks passed.")
