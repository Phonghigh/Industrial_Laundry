from pydantic_settings import BaseSettings, SettingsConfigDict


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


settings = Settings()
