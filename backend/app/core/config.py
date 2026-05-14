import uuid

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "Industrial Laundry API"
    environment: str = "development"
    debug: bool = False

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/industrial_laundry"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_stream_key: str = "operational_events"
    redis_consumer_group: str = "event_processors"

    # SSE
    sse_ping_interval: int = 15  # seconds

    # Alert thresholds
    stuck_batch_threshold_mins: int = 30
    station_inactivity_threshold_mins: int = 15
    asr_confidence_min: float = 0.75

    # CORS
    # Production: CORS_ORIGINS='["http://dashboard.factory.local"]'
    cors_origins: list[str] = ["*"]

    # Multi-tenancy
    # Single-factory deployments: set TENANT_ID to the factory's UUID in .env.
    # Multi-tenant SaaS: leave unset; use X-Tenant-ID header per request.
    tenant_id: uuid.UUID = DEFAULT_TENANT_ID

    # Consumer isolation
    # False (default/production): consumer runs as a separate `worker` Docker service.
    # True (dev convenience): consumer runs as an asyncio task inside the API process.
    run_consumer_in_process: bool = False


settings = Settings()
