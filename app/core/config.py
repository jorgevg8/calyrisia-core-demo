from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import unquote, urlparse

from pydantic import Field

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
    _HAS_PYDANTIC_SETTINGS = True
except Exception:  # pragma: no cover
    from pydantic import BaseModel as BaseSettings  # type: ignore
    _HAS_PYDANTIC_SETTINGS = False

    def SettingsConfigDict(**kwargs):  # type: ignore
        return kwargs


def _load_dotenv_into_environ() -> None:
    """Ensure .env is loaded into os.environ even if pydantic_settings or python-dotenv is absent."""
    env_candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
    ]
    for env_path in env_candidates:
        if not env_path.is_file():
            continue
        try:
            for raw_line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
                    val = val[1:-1]
                if key and key not in os.environ:
                    os.environ[key] = val
        except Exception:
            pass


_load_dotenv_into_environ()


def _env_str(key: str, default: str = "") -> str:
    val = os.environ.get(key, default)
    if val is None:
        return default
    val = str(val).strip()
    if len(val) >= 2 and ((val[0] == '"' and val[-1] == '"') or (val[0] == "'" and val[-1] == "'")):
        val = val[1:-1]
    return val


def _env_int(key: str, default: int) -> int:
    raw = _env_str(key, "")
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Settings(BaseSettings):
    app_name: str = Field(default_factory=lambda: _env_str("APP_NAME", "Galaxy Core"), alias="APP_NAME")
    app_env: str = Field(default_factory=lambda: _env_str("APP_ENV", "development"), alias="APP_ENV")
    app_host: str = Field(default_factory=lambda: _env_str("APP_HOST", "127.0.0.1"), alias="APP_HOST")
    app_port: int = Field(default_factory=lambda: _env_int("APP_PORT", 8000), alias="APP_PORT")
    log_level: str = Field(default_factory=lambda: _env_str("LOG_LEVEL", "INFO"), alias="LOG_LEVEL")
    public_base_url: str = Field(default_factory=lambda: _env_str("PUBLIC_BASE_URL", "https://calyrisia.com"), alias="PUBLIC_BASE_URL")

    database_url: str = Field(default_factory=lambda: _env_str("DATABASE_URL", ""), alias="DATABASE_URL")
    pg_host: str = Field(default_factory=lambda: _env_str("PGHOST", "127.0.0.1"), alias="PGHOST")
    pg_port: int = Field(default_factory=lambda: _env_int("PGPORT", 5432), alias="PGPORT")
    pg_database: str = Field(default_factory=lambda: _env_str("PGDATABASE", "galaxy_db"), alias="PGDATABASE")
    pg_user: str = Field(default_factory=lambda: _env_str("PGUSER", "postgres"), alias="PGUSER")
    pg_password: str = Field(default_factory=lambda: _env_str("PGPASSWORD", ""), alias="PGPASSWORD")
    pg_sslmode: str = Field(default_factory=lambda: _env_str("PGSSLMODE", "require"), alias="PGSSLMODE")

    gemini_api_key: str = Field(default_factory=lambda: _env_str("GEMINI_API_KEY", ""), alias="GEMINI_API_KEY")
    gemini_model: str = Field(default_factory=lambda: _env_str("GEMINI_MODEL", "gemini-2.5-flash"), alias="GEMINI_MODEL")

    galaxy_jwt_secret: str = Field(default_factory=lambda: _env_str("GALAXY_JWT_SECRET", ""), alias="GALAXY_JWT_SECRET")
    jwt_algorithm: str = Field(default_factory=lambda: _env_str("GALAXY_JWT_ALGORITHM", "HS256"), alias="GALAXY_JWT_ALGORITHM")
    jwt_exp_minutes: int = Field(default_factory=lambda: _env_int("GALAXY_JWT_EXP_MINUTES", 1440), alias="GALAXY_JWT_EXP_MINUTES", ge=5, le=10080)
    jwt_issuer: str = Field(default_factory=lambda: _env_str("GALAXY_JWT_ISSUER", "galaxy-core"), alias="GALAXY_JWT_ISSUER")

    telegram_bot_token: str = Field(default_factory=lambda: _env_str("TELEGRAM_BOT_TOKEN", ""), alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default_factory=lambda: _env_str("TELEGRAM_WEBHOOK_SECRET", ""), alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_business_id: str = Field(default_factory=lambda: _env_str("TELEGRAM_BUSINESS_ID", ""), alias="TELEGRAM_BUSINESS_ID")

    # Evolution API (WhatsApp Multitenant QR / Instancias Dinámicas)
    evolution_api_url: str = Field(default_factory=lambda: _env_str("EVOLUTION_API_URL", ""), alias="EVOLUTION_API_URL")
    evolution_api_key: str = Field(default_factory=lambda: _env_str("EVOLUTION_API_KEY", ""), alias="EVOLUTION_API_KEY")
    evolution_webhook_url: str = Field(default_factory=lambda: _env_str("EVOLUTION_WEBHOOK_URL", ""), alias="EVOLUTION_WEBHOOK_URL")
    wa_provider: str = Field(default_factory=lambda: _env_str("WA_PROVIDER", "auto"), alias="WA_PROVIDER")

    # Meta OAuth & Graph API (Instagram Direct & Facebook Messenger)
    meta_app_id: str = Field(default_factory=lambda: _env_str("META_APP_ID", "2456430845105397"), alias="META_APP_ID")
    meta_app_secret: str = Field(default_factory=lambda: _env_str("META_APP_SECRET", ""), alias="META_APP_SECRET")
    meta_config_id: str = Field(default_factory=lambda: _env_str("META_CONFIG_ID", "1831235794732615"), alias="META_CONFIG_ID")
    meta_facebook_config_id: str = Field(default_factory=lambda: _env_str("META_FACEBOOK_CONFIG_ID", ""), alias="META_FACEBOOK_CONFIG_ID")
    meta_redirect_uri: str = Field(default_factory=lambda: _env_str("META_REDIRECT_URI", "https://calyrisia.com/api/auth/meta/callback"), alias="META_REDIRECT_URI")
    meta_webhook_verify_token: str = Field(default_factory=lambda: _env_str("META_WEBHOOK_VERIFY_TOKEN", ""), alias="META_WEBHOOK_VERIFY_TOKEN")
    meta_graph_api_version: str = Field(default_factory=lambda: _env_str("META_GRAPH_API_VERSION", "v26.0"), alias="META_GRAPH_API_VERSION")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def database_kwargs(self) -> dict:
        clean_pw = self.pg_password.strip()
        if len(clean_pw) >= 2 and ((clean_pw[0] == '"' and clean_pw[-1] == '"') or (clean_pw[0] == "'" and clean_pw[-1] == "'")):
            clean_pw = clean_pw[1:-1]
        if self.database_url and self.database_url.strip():
            parsed = urlparse(self.database_url.strip())
            if parsed.hostname:
                return {
                    "host": parsed.hostname,
                    "port": parsed.port or self.pg_port or 5432,
                    "dbname": (parsed.path or "").lstrip("/") or self.pg_database or "postgres",
                    "user": unquote(parsed.username or self.pg_user),
                    "password": unquote(parsed.password or clean_pw),
                    "sslmode": self.pg_sslmode or "require",
                    "prepare_threshold": None,
                }
        return {
            "host": self.pg_host.strip(),
            "port": self.pg_port,
            "dbname": self.pg_database.strip(),
            "user": self.pg_user.strip(),
            "password": clean_pw,
            "sslmode": self.pg_sslmode.strip() or "require",
            "prepare_threshold": None,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv_into_environ()
    return Settings()
