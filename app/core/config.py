from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Galaxy Core", alias="APP_NAME")
    app_env: str = Field(default="development", alias="APP_ENV")
    app_host: str = Field(default="127.0.0.1", alias="APP_HOST")
    app_port: int = Field(default=8000, alias="APP_PORT")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    pg_host: str = Field(default="127.0.0.1", alias="PGHOST")
    pg_port: int = Field(default=5432, alias="PGPORT")
    pg_database: str = Field(default="galaxy_db", alias="PGDATABASE")
    pg_user: str = Field(default="postgres", alias="PGUSER")
    pg_password: str = Field(alias="PGPASSWORD")
    pg_sslmode: str = Field(default="require", alias="PGSSLMODE")

    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-1.5-flash", alias="GEMINI_MODEL")

    # Paso 38 — secretos de seguridad. Nunca deben quedar hardcodeados.
    galaxy_jwt_secret: str = Field(default="", alias="GALAXY_JWT_SECRET")
    jwt_algorithm: str = Field(default="HS256", alias="GALAXY_JWT_ALGORITHM")
    jwt_exp_minutes: int = Field(default=1440, alias="GALAXY_JWT_EXP_MINUTES", ge=5, le=10080)
    jwt_issuer: str = Field(default="galaxy-core", alias="GALAXY_JWT_ISSUER")

    # Paso 36 — integración Telegram configurable por entorno.
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
        return {
            "host": self.pg_host,
            "port": self.pg_port,
            "dbname": self.pg_database,
            "user": self.pg_user,
            "password": self.pg_password,
            "sslmode": self.pg_sslmode,
        }


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
