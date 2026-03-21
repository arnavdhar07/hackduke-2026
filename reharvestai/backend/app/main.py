from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(name)s  %(message)s")
logger = logging.getLogger("api")

from app import database
from app import redis as redis_module
from app.routers import fields, zones, recommendations, agent


# ---------------------------------------------------------------------------
# Lifespan — initialise / tear-down shared resources
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start up: open DB pool and Redis client.
    Shut down: close both gracefully.
    """
    await database.init_db_pool()
    await redis_module.init_redis()

    yield  # application runs here

    await database.close_db_pool()
    await redis_module.close_redis()


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ReHarvestAI API",
    description="Precision agriculture backend — field analytics, zone NDVI, AI recommendations.",
    version="1.0.0",
    lifespan=lifespan,
)

# ── Request/response logger ─────────────────────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    logger.info(
        "%s %s → %d  (%.0fms)",
        request.method, request.url.path, response.status_code, ms,
    )
    return response


# ── CORS (hackathon demo — allow everything) ────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ─────────────────────────────────────────────────────────────────
API_PREFIX = "/api/v1"

app.include_router(fields.router, prefix=API_PREFIX)
app.include_router(zones.router, prefix=API_PREFIX)
app.include_router(recommendations.router, prefix=API_PREFIX)
app.include_router(agent.router, prefix=API_PREFIX)


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    """Liveness probe — returns 200 OK when the server is running."""
    return {"status": "ok"}
