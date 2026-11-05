"""FastAPI application entry point for Tamil Voice POS."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.routers import auth, config, inventory, products, reports, sales, system, voice
from app.routers.system import make_maintenance_guard
from app.utils.config import settings, validate_startup_configuration
from app.utils.seed import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("tamil_voice_pos.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Validate configuration and initialize SQLite schema + hackathon seed on startup."""
    validate_startup_configuration()
    init_db()
    logger.info("Tamil Voice POS backend is ready.")
    yield


app = FastAPI(
    title="Tamil Voice POS API",
    description="AI-Powered Tamil & English Voice-Controlled Point of Sale and Inventory Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    logger.exception("Database error during %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred while processing your request."},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    messages = []
    for err in exc.errors():
        loc = " -> ".join(str(part) for part in err.get("loc", []) if part != "body")
        msg = err.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": "; ".join(messages) or "Invalid input payload."},
    )


# Authentication, System Maintenance Admin API, and Public Config remain accessible during maintenance
app.include_router(auth.router)
app.include_router(system.router)
app.include_router(config.router)

# Protected POS & AI Routers independently enforce HTTP 503 during blocking maintenance / disabled features
app.include_router(
    products.router,
    dependencies=[
        Depends(make_maintenance_guard("productManagement", mutating_only_feature=True))
    ],
)
app.include_router(
    inventory.router,
    dependencies=[
        Depends(make_maintenance_guard("inventoryAdjustments", mutating_only_feature=True))
    ],
)
app.include_router(
    sales.router,
    dependencies=[
        Depends(make_maintenance_guard("posBilling", mutating_only_feature=True))
    ],
)
app.include_router(
    voice.router,
    dependencies=[Depends(make_maintenance_guard("voiceAssistant"))],
)
app.include_router(
    reports.router,
    dependencies=[Depends(make_maintenance_guard("reportsAnalytics"))],
)


@app.get("/api/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "service": "Tamil Voice POS API",
        "currency": settings.CURRENCY,
        "ai_provider": settings.AI_PROVIDER,
        "ollama_model": settings.OLLAMA_MODEL,
    }
