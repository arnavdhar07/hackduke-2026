from pathlib import Path

from pydantic_settings import BaseSettings

# Walk up from backend/app/config.py to find .env at the project root.
_HERE = Path(__file__).resolve().parent        # backend/app/
_ENV_FILE = _HERE.parent.parent / ".env"       # reharvestai/.env


class Settings(BaseSettings):
    # ── Database ──────────────────────────────────────────────────────────────
    DATABASE_URL: str

    # ── Redis / Celery ────────────────────────────────────────────────────────
    # Person 3's celery_app.py derives broker + backend from REDIS_URL directly.
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── AI Agent (Person 2) ───────────────────────────────────────────────────
    ANTHROPIC_API_KEY: str = ""

    # ── Satellite pipeline (Person 3) ─────────────────────────────────────────
    CDSE_CLIENT_ID: str = ""
    CDSE_CLIENT_SECRET: str = ""
    SAM3_CHECKPOINT_PATH: str = "/models/sam3_vit_h.pth"
    SAM3_MODEL_TYPE: str = "vit_h"
    SENTINEL_MAX_CLOUD_PCT: float = 30.0
    SENTINEL_LOOKBACK_DAYS: int = 10
    PIPELINE_USE_SYNTHETIC: bool = True   # True = use synthetic data (no real satellite needed)

    # ── App ───────────────────────────────────────────────────────────────────
    SECRET_KEY: str = "changeme"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = "*"

    model_config = {"env_file": str(_ENV_FILE), "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
