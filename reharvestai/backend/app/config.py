from pathlib import Path

from pydantic_settings import BaseSettings

# Walk up from this file (backend/app/config.py) to find .env at the project root.
# This works regardless of which directory you run commands from.
_HERE = Path(__file__).resolve().parent          # backend/app/
_ENV_FILE = _HERE.parent.parent / ".env"         # project_root/.env


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str

    # Redis / Celery
    REDIS_URL: str

    # Copernicus Data Space Ecosystem credentials (optional — falls back to synthetic)
    CDSE_CLIENT_ID: str = ""
    CDSE_CLIENT_SECRET: str = ""

    # SAM3 segmentation model
    SAM3_CHECKPOINT_PATH: str = "/models/sam3_vit_h.pth"
    SAM3_MODEL_TYPE: str = "vit_h"

    # Sentinel-2 fetch behaviour
    SENTINEL_MAX_CLOUD_PCT: float = 30.0
    SENTINEL_LOOKBACK_DAYS: int = 10
    PIPELINE_USE_SYNTHETIC: bool = False

    # Supabase project (used by API layer — Person 2)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # App
    SECRET_KEY: str = "changeme"
    LOG_LEVEL: str = "INFO"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8"}


settings = Settings()
