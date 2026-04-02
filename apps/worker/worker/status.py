from worker.core.config import WorkerSettings


def build_status_snapshot(settings: WorkerSettings) -> dict[str, object]:
    return {
        "status": "ok",
        "service": settings.service_name,
        "environment": settings.environment,
        "version": settings.app_version,
        "mode": "placeholder",
        "poll_interval_seconds": settings.poll_interval_seconds,
    }

