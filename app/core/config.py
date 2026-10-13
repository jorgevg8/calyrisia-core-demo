from functools import lru_cache
from urllib.parse import urlparse, unquote
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Galaxy Core", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="0.0.0.0", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Soporte dual: DATABASE_URL directa o variables individuales
    database_url: str = Field(default="", alias="DATABASE_URL")
    pg_host: str = Field(default="127.0.0.1", alias="PGHOST")
    pg_port: int = Field(default=5432, alias="PGPORT")
    pg_database: str = Field(default="galaxy_db", alias="PGDATABASE")
    pg_user: str = Field(default="postgres", alias="PGUSER")
    pg_password: str = Field(default="", alias="PGPASSWORD")
    pg_sslmode: str = Field(default="require", alias="PGSSLMODE")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")

    # Seguridad JWT con secreto robusto por defecto
    galaxy_jwt_secret: str = Field(
        default="calyrisia_super_secure_demo_secret_key_2026_production_safe_jwt_token",
        alias="GALAXY_JWT_SECRET",
    )
    jwt_algorithm: str = Field(default="HS256", alias="GALAXY_JWT_ALGORITHM")
    jwt_exp_minutes: int = Field(default=1440, alias="GALAXY_JWT_EXP_MINUTES", ge=5, le=10080)
    jwt_issuer: str = Field(default="galaxy-core", alias="GALAXY_JWT_ISSUER")

    # Integración Telegram
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(default="", alias="TELEGRAM_WEBHOOK_SECRET")
    telegram_business_id: str = Field(default="", alias="TELEGRAM_BUSINESS_ID")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @property
    def database_kwargs(self) -> dict:
        if self.database_url:
            try:
                url = urlparse(self.database_url)
                return {
                    "host": url.hostname or self.pg_host,
                    "port": url.port or self.pg_port,
                    "dbname": (url.path[1:] if url.path else "") or self.pg_database,
                    "user": unquote(url.username or "") or self.pg_user,
                    "password": unquote(url.password or "") or self.pg_password,
                    "sslmode": self.pg_sslmode or "require",
                }
            except Exception:
                pass
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "dbname": self.pg_database,
            "user": self.pg_user,
            "password": self.pg_password,
            "sslmode": self.pg_sslmode or "require",
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
