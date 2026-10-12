from __future__ import annotations

import secrets
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"


def upsert(lines: list[str], key: str, value: str) -> list[str]:
    prefix = f"{key}="
    for i, line in enumerate(lines):
        if line.startswith(prefix):
            lines[i] = f"{prefix}{value}"
            return lines
    if lines and lines[-1].strip():
        lines.append("")
    lines.append(f"{prefix}{value}")
    return lines


def read_env() -> list[str]:
    return ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []


def get_value(lines: list[str], key: str) -> str:
    prefix = f"{key}="
    for line in lines:
        if line.startswith(prefix):
            return line[len(prefix):].strip().strip('"')
    return ""


if __name__ == "__main__":
    print("=" * 72)
    print("GALAXY PASO 39 — SECURITY / CONFIG SETUP")
    print("=" * 72)
    lines = read_env()

    jwt_secret = get_value(lines, "GALAXY_JWT_SECRET")
    if len(jwt_secret) < 32:
        jwt_secret = secrets.token_urlsafe(48)
        lines = upsert(lines, "GALAXY_JWT_SECRET", jwt_secret)
        print("[OK] GALAXY_JWT_SECRET generado y guardado en .env")
    else:
        print("[OK] GALAXY_JWT_SECRET ya estaba configurado")

    webhook_secret = get_value(lines, "TELEGRAM_WEBHOOK_SECRET")
    if not webhook_secret:
        webhook_secret = secrets.token_urlsafe(32)
        lines = upsert(lines, "TELEGRAM_WEBHOOK_SECRET", webhook_secret)
        print("[OK] TELEGRAM_WEBHOOK_SECRET generado y guardado en .env")
    else:
        print("[OK] TELEGRAM_WEBHOOK_SECRET ya estaba configurado")

    business_id = get_value(lines, "TELEGRAM_BUSINESS_ID")
    if not business_id:
        # Business Pilot Store validado en el proyecto actual.
        business_id = "bc8d44fc-3ab0-442f-acf8-a816a3bcf77f"
        lines = upsert(lines, "TELEGRAM_BUSINESS_ID", business_id)
        print(f"[OK] TELEGRAM_BUSINESS_ID configurado para el Pilot Store: {business_id}")
    else:
        print(f"[OK] TELEGRAM_BUSINESS_ID ya estaba configurado: {business_id}")

    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\nConfiguración completada. Reinicia Uvicorn después de ejecutar este script.")
