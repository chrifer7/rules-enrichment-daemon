from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "rules-enrichment-daemon"
    app_env: str = "local"
    app_version: str = "0.1.0"

    log_level: str = "INFO"
    log_ecs_enabled: bool = True
    log_to_stdout: bool = True
    log_to_file: bool = False
    log_file_path: str = "./logs/daemon.log"

    external_api_base_url: str = "http://localhost:8000"
    external_api_timeout_seconds: int = Field(default=8, ge=1)
    external_api_api_key: str = ""

    poll_interval_seconds: int = Field(default=10, ge=1)
    poll_batch_size: int = Field(default=25, ge=1, le=500)
    rule_cache_ttl_seconds: int = Field(default=30, ge=1)
    max_processing_attempts: int = Field(default=3, ge=1)
    outbox_publish_interval_seconds: int = Field(default=5, ge=1)

    database_url: str = "postgresql+psycopg://daemon:daemon@localhost:5433/rules_enrichment_daemon"
    use_sqlite: bool = False
    sqlite_database_url: str = "sqlite+pysqlite:///./rules_enrichment_daemon.db"

    enrichment_source_system: str = "rules-enrichment-daemon"
    enrichment_version: int = Field(default=1, ge=1)

    outbox_sink_mode: str = "log"
    outbox_webhook_url: str = ""

    elastic_apm_enabled: bool = False
    elastic_apm_server_url: str = ""
    elastic_apm_service_name: str = "rules-enrichment-daemon"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def effective_database_url(self) -> str:
        return self.sqlite_database_url if self.use_sqlite else self.database_url


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
