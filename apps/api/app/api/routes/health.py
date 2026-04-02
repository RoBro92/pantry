from fastapi import APIRouter, Request

from app.core.config import get_settings

router = APIRouter(tags=["system"])


@router.get("/health")
async def health(request: Request):
    settings = get_settings()
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "request_id": getattr(request.state, "request_id", None),
    }

