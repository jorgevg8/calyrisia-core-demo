"""Run CALYRISIA's FastAPI app and Telegram bot together for localhost testing.

This script uses Telegram long polling, so no Render deploy, webhook, tunnel, or
public HTTPS URL is needed. Secrets are stored only in the ignored
.env.telegram.local file. Do not commit or send that file to anyone.
"""
from __future__ import annotations

import asyncio
import getpass
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LOCAL_ENV = ROOT / ".env.telegram.local"
LOCAL_STATE = ROOT / ".telegram_local_state.json"
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def read_env_file(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"\"", "'"}:
            value = value[1:-1]
        result[key.strip()] = value
    return result


def write_env_file(values: dict[str, str]) -> None:
    current = read_env_file(LOCAL_ENV)
    current.update({k: str(v) for k, v in values.items()})
    lines = [
        "# LOCAL ONLY — ignored by Git. Never copy this file into a public repo or deployment.",
        *[f"{key}={json.dumps(value, ensure_ascii=False)}" for key, value in sorted(current.items())],
        "",
    ]
    LOCAL_ENV.write_text("\n".join(lines), encoding="utf-8")


def ensure_local_configuration() -> str:
    values = read_env_file(LOCAL_ENV)
    # For safety, deliberately do not fall back to a possibly stale token in .env.
    token = values.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        print("\n=== Configuración local de Telegram ===")
        print("Pega el token ACTUAL del bot. Lo ideal es regenerarlo en @BotFather porque el anterior se compartió en el chat.")
        token = getpass.getpass("Token del bot (no se mostrará mientras escribes): ").strip()
        if not token or ":" not in token:
            raise SystemExit("No recibí un token válido. No se inició el bot.")
        values["TELEGRAM_BOT_TOKEN"] = token

    owner_username = values.get("TELEGRAM_LOCAL_OWNER_USERNAME", "").strip().lstrip("@").lower()
    if not owner_username:
        owner_username = input("Tu @usuario de Telegram (sin @ también funciona): ").strip().lstrip("@").lower()
        if not owner_username:
            raise SystemExit("Necesito tu @usuario para registrar el chat del dueño sin dejar que otro usuario se apropie de él.")
        values["TELEGRAM_LOCAL_OWNER_USERNAME"] = owner_username

    # Force explicit, unmistakable non-payment instructions during local testing.
    # They enable the screenshot/review flow without sharing real bank or Binance details.
    if not values.get("TELEGRAM_PAGO_MOVIL_INFO", "").strip():
        values["TELEGRAM_PAGO_MOVIL_INFO"] = "MODO DE PRUEBA LOCAL — NO PAGAR NI REALIZAR TRANSFERENCIAS. Usa solo una captura ficticia con la palabra PRUEBA."
    if not values.get("TELEGRAM_BINANCE_INFO", "").strip():
        values["TELEGRAM_BINANCE_INFO"] = "MODO DE PRUEBA LOCAL — NO ENVIAR USDT NI REALIZAR PAGOS. Usa solo una captura ficticia con la palabra PRUEBA."
    write_env_file(values)
    return owner_username


def api_request(token: str, method: str, payload: dict[str, Any] | None = None, timeout: int = 25) -> Any:
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = json.dumps(payload or {}).encode("utf-8")
    request = urllib.request.Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            parsed = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        # Never include the request URL in errors; it embeds the bot token.
        raise RuntimeError(f"No se pudo conectar con Telegram ({method}: {type(exc).__name__}).") from exc
    if not parsed.get("ok"):
        detail = str(parsed.get("description", "error Telegram"))[:220]
        raise RuntimeError(f"Telegram rechazó {method}: {detail}")
    return parsed.get("result")


def save_owner_state(username: str, chat_id: str) -> None:
    LOCAL_STATE.write_text(
        json.dumps({"owner_username": username.lower(), "owner_chat_id": str(chat_id)}, indent=2),
        encoding="utf-8",
    )


def load_owner_state(username: str) -> str | None:
    try:
        data = json.loads(LOCAL_STATE.read_text(encoding="utf-8"))
        if str(data.get("owner_username", "")).lower() == username.lower() and data.get("owner_chat_id"):
            return str(data["owner_chat_id"])
    except Exception:
        pass
    return None


async def main() -> None:
    owner_username = ensure_local_configuration()

    # Import settings only after .env.telegram.local has been created.
    from app.core.config import get_settings
    settings = get_settings()
    token = settings.telegram_bot_token.strip()
    if not token:
        raise SystemExit("TELEGRAM_BOT_TOKEN está vacío en la configuración local.")
    try:
        uuid.UUID(settings.telegram_business_id.strip())
    except (ValueError, AttributeError):
        business_id = input("UUID del negocio de prueba (TELEGRAM_BUSINESS_ID): ").strip()
        try:
            uuid.UUID(business_id)
        except ValueError as exc:
            raise SystemExit("Falta TELEGRAM_BUSINESS_ID o el UUID no tiene un formato válido.") from exc
        write_env_file({"TELEGRAM_BUSINESS_ID": business_id})
        get_settings.cache_clear()
        settings = get_settings()
        token = settings.telegram_bot_token.strip()

    owner_chat = settings.telegram_owner_chat_id.strip() or load_owner_state(owner_username)
    if owner_chat:
        settings.telegram_owner_chat_id = owner_chat
        write_env_file({"TELEGRAM_OWNER_CHAT_ID": owner_chat})

    me = api_request(token, "getMe", {}, timeout=20)
    print(f"\nBot conectado: @{me.get('username', 'sin_usuario')} (ID {me.get('id', 'n/a')}).")
    webhook_info = api_request(token, "getWebhookInfo", {}, timeout=20) or {}
    webhook_url = str(webhook_info.get("url") or "").strip()
    if webhook_url:
        print("\nEste bot ya tiene un webhook configurado:")
        print(webhook_url)
        answer = input("Para usar polling local hay que quitar ese webhook; podría interrumpir el bot publicado. ¿Lo quitamos? Escribe SI para confirmar: ").strip()
        if answer != "SI":
            raise SystemExit("No se cambió el webhook. Para proteger el entorno existente, se canceló el modo local.")
        api_request(token, "deleteWebhook", {"drop_pending_updates": False}, timeout=20)
        print("Webhook eliminado. El bot solo recibirá actualizaciones mientras este modo local esté ejecutándose.")

    # Load the existing app only after local secret/config setup.
    import uvicorn
    from app.main import app
    from app.db import pool
    from app.api.telegram import process_message, send_to_telegram

    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=8000, log_level="info", access_log=False))
    server_task = asyncio.create_task(server.serve())
    for _ in range(200):
        if server.started:
            break
        if server_task.done():
            await server_task
            raise SystemExit("El servidor local se cerró antes de arrancar.")
        await asyncio.sleep(0.1)
    if not server.started:
        server.should_exit = True
        raise SystemExit("El servidor no pudo arrancar en http://127.0.0.1:8000.")

    # Validate the tenant and wait for the app's idempotent Telegram schema setup.
    # The FastAPI lifespan schedules additive DDL asynchronously, so the runner
    # must not poll messages before those tables are ready.
    try:
        deadline = time.monotonic() + 45
        business = None
        schema_ready = False
        last_db_error = None
        while time.monotonic() < deadline:
            try:
                with pool.connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT id, name, status FROM public.businesses WHERE id = %s LIMIT 1",
                            (settings.telegram_business_id,),
                        )
                        business = cur.fetchone()
                        if not business or str(business[2] or "").lower() != "active":
                            raise SystemExit(
                                "TELEGRAM_BUSINESS_ID no corresponde a un negocio activo en la base configurada. "
                                "Revisa .env / .env.telegram.local."
                            )
                        cur.execute("""
                            SELECT to_regclass('public.telegram_customer_sessions'),
                                   to_regclass('public.telegram_update_events')
                        """)
                        tables = cur.fetchone()
                        schema_ready = bool(tables and tables[0] and tables[1])
                if schema_ready:
                    break
            except SystemExit:
                raise
            except Exception as exc:
                last_db_error = type(exc).__name__
            await asyncio.sleep(0.75)
        if not business:
            raise RuntimeError(last_db_error or "business_not_found")
        if not schema_ready:
            raise SystemExit(
                "La base de datos conectó, pero las tablas de Telegram no estuvieron listas en 45 segundos. "
                "Revisa los logs de CALYRISIA y los permisos de DDL del usuario de PostgreSQL."
            )
        print(f"Negocio de prueba confirmado: {business[1]} ({business[2]}).")
        print("Tablas de sesiones y actualizaciones de Telegram confirmadas.")
    except SystemExit:
        server.should_exit = True
        await server_task
        raise
    except Exception as exc:
        server.should_exit = True
        await server_task
        raise SystemExit(
            f"No pude validar la base de datos. Revisa PGHOST/PGDATABASE/PGUSER/PGPASSWORD del .env: {type(exc).__name__}."
        ) from exc

    print("\nCALYRISIA local: http://127.0.0.1:8000")
    print("Modo Telegram long polling activo; no hay webhook público.")
    print(f"Administrador autorizado para registro local: @{owner_username}")
    print("Abre Telegram, entra al bot y envía /start. Para registrar las notificaciones del dueño, envía /miid desde esa cuenta.")
    print("Los métodos de pago están marcados como PRUEBA; no envíes dinero real.")
    print("Pulsa Ctrl+C aquí para detener el servidor y el bot.")

    offset: int | None = None
    registered_owner = bool(settings.telegram_owner_chat_id.strip())
    try:
        while not server.should_exit:
            try:
                payload: dict[str, Any] = {"timeout": 45, "allowed_updates": ["message", "edited_message", "callback_query"]}
                if offset is not None:
                    payload["offset"] = offset
                updates = await asyncio.to_thread(api_request, token, "getUpdates", payload, 55)
                for update in updates or []:
                    offset = int(update.get("update_id", 0)) + 1
                    message = update.get("message") or update.get("edited_message") or {}
                    sender = message.get("from") or {}
                    chat = message.get("chat") or {}
                    message_text = str(message.get("text") or "").strip().lower()
                    sender_username = str(sender.get("username") or "").lstrip("@").lower()
                    chat_id = str(chat.get("id") or "")
                    if message_text in {"/miid", "/chatid"} and chat_id and sender_username == owner_username:
                        settings.telegram_owner_chat_id = chat_id
                        os.environ["TELEGRAM_OWNER_CHAT_ID"] = chat_id
                        write_env_file({"TELEGRAM_OWNER_CHAT_ID": chat_id})
                        save_owner_state(owner_username, chat_id)
                        registered_owner = True
                        print("Chat del dueño registrado localmente. Las notificaciones llegarán a esta cuenta.")
                    await process_message(update, str(uuid.uuid4()))
                    if message_text in {"/miid", "/chatid"} and sender_username == owner_username:
                        send_to_telegram(chat_id, "✅ Chat de dueño registrado para esta prueba local. Aquí llegarán los comprobantes y avisos de delivery.")
            except asyncio.CancelledError:
                raise
            except KeyboardInterrupt:
                break
            except Exception as exc:
                print(f"No pude leer nuevas actualizaciones de Telegram ({type(exc).__name__}). Reintentando en 3 segundos.")
                await asyncio.sleep(3)
    finally:
        server.should_exit = True
        try:
            await server_task
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nCALYRISIA local detenido.")
