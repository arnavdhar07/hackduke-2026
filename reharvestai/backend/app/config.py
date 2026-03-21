from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=["../.env", ".env"],  # works from both backend/ and reharvestai/
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database (Supabase PostgreSQL)
    database_url: str = "postgresql://postgres:password@db.kdsgnodshdzulpupvlka.supabase.co:5432/postgres"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Anthropic
    anthropic_api_key: str = ""

    # Copernicus / Sentinel-2
    copernicus_user: str = ""
    copernicus_password: str = ""
    use_mock_satellite: bool = True  # set False to use real Sentinel-2 data

    # App
    app_env: str = "development"
    cors_origins: str = "*"


settings = Settings()
