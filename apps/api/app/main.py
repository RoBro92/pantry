from contextlib import asynccontextmanager
from time import perf_counter
from uuid import uuid4

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.api.routes.admin import router as admin_router
from app.api.routes.auth import router as auth_router
from app.api.routes.health import router as health_router
from app.api.routes.households import router as households_router
from app.api.routes.imports import router as imports_router
from app.api.routes.pantry import router as pantry_router
from app.api.routes.recipes import router as recipes_router
from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(service_name=settings.service_name, log_level=settings.log_level)
logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "api.starting",
        environment=settings.environment,
        version=settings.app_version,
        database_url=settings.safe_database_url,
        redis_url=settings.safe_redis_url,
    )
    yield
    logger.info("api.stopping")


app = FastAPI(
    title="Pantry API",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret_key,
    session_cookie=settings.session_cookie_name,
    max_age=settings.session_max_age_seconds,
    same_site=settings.session_same_site,
    https_only=settings.session_https_only,
)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    started = perf_counter()

    request.state.request_id = request_id
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        service=settings.service_name,
        request_id=request_id,
        method=request.method,
        path=request.url.path,
    )

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.exception("http.request.failed", duration_ms=duration_ms)
        raise
    else:
        duration_ms = round((perf_counter() - started) * 1000, 2)
        logger.info(
            "http.request.completed",
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        response.headers["x-request-id"] = request_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


app.include_router(health_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(admin_router, prefix="/api")
app.include_router(households_router, prefix="/api")
app.include_router(pantry_router, prefix="/api")
app.include_router(recipes_router, prefix="/api")
app.include_router(imports_router, prefix="/api")
