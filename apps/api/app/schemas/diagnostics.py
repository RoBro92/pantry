from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.releases import ReleaseCheckResponse
from app.schemas.settings import PublicBaseURLSummary
from app.schemas.smtp import SMTPConfigResponse


class AppDiagnosticsSummary(BaseModel):
    service: str
    environment: str
    version: str
    deployment_mode: str
    started_at: datetime
    uptime_seconds: int


class ServiceHealthSummary(BaseModel):
    status: str
    message: str | None = None


class WorkerDiagnosticsSummary(BaseModel):
    status: str
    service: str | None
    version: str | None
    mode: str | None
    poll_interval_seconds: int | None
    started_at: datetime | None
    last_seen_at: datetime | None
    heartbeat_age_seconds: int | None
    message: str | None = None


class RedisDiagnosticsSummary(BaseModel):
    status: str
    latency_ms: float | None
    message: str | None = None


class QueueDiagnosticsSummary(BaseModel):
    backend: str
    queued_import_jobs: int
    processing_import_jobs: int
    stale_processing_import_jobs: int
    failed_import_jobs: int
    completed_import_jobs: int
    confirmed_import_jobs: int
    imports: dict[str, int]
    recipe_url_imports: dict[str, int]
    product_intelligence_runs: dict[str, int]
    message: str


class DatabaseDiagnosticsSummary(BaseModel):
    status: str
    engine: str
    latency_ms: float | None
    database_name: str | None
    size_bytes: int | None
    size_pretty: str | None
    note: str | None


class EntityCountsSummary(BaseModel):
    households: int
    users: int
    products: int
    stock_lots: int
    recipes: int
    import_jobs: int


class AIProviderDiagnosticsSummary(BaseModel):
    configured: bool
    provider_type: str | None
    is_enabled: bool
    health_status: str | None
    default_model: str | None
    last_success_at: datetime | None


class DiagnosticsResponse(BaseModel):
    generated_at: datetime
    policy: str
    app: AppDiagnosticsSummary
    api: ServiceHealthSummary
    worker: WorkerDiagnosticsSummary
    redis: RedisDiagnosticsSummary
    queue: QueueDiagnosticsSummary
    database: DatabaseDiagnosticsSummary
    counts: EntityCountsSummary
    ai_provider: AIProviderDiagnosticsSummary
    release_check: ReleaseCheckResponse
    smtp: SMTPConfigResponse
    public_base_url: PublicBaseURLSummary
    limitations: list[str]
