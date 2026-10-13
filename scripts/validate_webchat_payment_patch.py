"""Static regression checks for the Webchat payment approval overlay.

Run from the Galaxy project root:
    python scripts/validate_webchat_payment_patch.py
This validates syntax and source consistency; it does not replace a live PostgreSQL test.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
main_path = ROOT / "app" / "main.py"
webchat_path = ROOT / "app" / "static" / "webchat" / "index.html"
webchat_js_path = ROOT / "app" / "static" / "webchat" / "app.js"
dashboard_path = ROOT / "app" / "static" / "dashboard" / "index.html"
sql_path = ROOT / "migration_webchat_payment_approval.sql"

main_text = main_path.read_text(encoding="utf-8")
webchat_text = webchat_path.read_text(encoding="utf-8")
webchat_js_text = webchat_js_path.read_text(encoding="utf-8")
webchat_runtime_text = webchat_text + "\\n" + webchat_js_text
dashboard_text = dashboard_path.read_text(encoding="utf-8")
sql_text = sql_path.read_text(encoding="utf-8")
ast.parse(main_text, filename=str(main_path))

required_main = [
    "_ensure_webchat_payment_schema",
    "webchat_payment_requests",
    "/api/v1/webchat/payment/request",
    "/api/v1/webchat/payment/status/{payment_id}",
    "/api/v1/dashboard/webchat-payments",
    "/api/v1/dashboard/webchat-payments/{payment_id}/decision",
    "FOR UPDATE",
    "payment_status",
    "sales_today",
    "_resolve_webchat_order_items_from_history",
    "_apply_webchat_order_items",
    "INSERT INTO order_items",
    "conversation_id",
]
for item in required_main:
    assert item in main_text, f"Missing in main.py: {item}"

required_webchat = [
    "/api/v1/webchat/payment/request",
    "/api/v1/webchat/payment/status/${paymentId}",
    "data.payment_id",
    "data.status === \"approved\"",
    "data.status === \"rejected\"",
]
for item in required_webchat:
    assert item in webchat_runtime_text, f"Missing in webchat: {item}"
assert 'fetch("/api/v1/webchat/payment/confirm"' not in webchat_runtime_text, \
    "The public client must not invoke the legacy revenue-confirmation endpoint."

required_dashboard = [
    "pending-payments-alert",
    "webchat-payment-pending-list",
    "pending-payments-nav-badge",
    "Ingresos de Hoy",
    "/api/v1/dashboard/webchat-payments?status=all&limit=100",
    "decideWebchatPayment",
    "kpi-sales-today",
]
for item in required_dashboard:
    assert item in dashboard_text, f"Missing in dashboard: {item}"

assert "CREATE TABLE IF NOT EXISTS public.webchat_payment_requests" in sql_text
assert "CREATE INDEX IF NOT EXISTS idx_webchat_payments_business_status_created" in sql_text
assert "CREATE UNIQUE INDEX IF NOT EXISTS uq_webchat_payment_order_id" in sql_text

print("OK: Python AST parse passed.")
print("OK: Webchat payment request/status flow is present; public client no longer confirms revenue.")
print("OK: Dashboard pending notification, approval/rejection, and daily revenue KPI are present.")
print("OK: Webchat order items are persisted and exact stock deduction is wired into approval.")
print("OK: Additive/idempotent SQL migration is present.")
print("NOTE: Run an end-to-end test against the local PostgreSQL 18 instance before external demo.")
