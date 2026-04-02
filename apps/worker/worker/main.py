import argparse
import json
import time
from uuid import uuid4

import structlog

from app.services.import_processing import process_next_import_job
from worker.core.config import get_settings
from worker.core.logging import configure_logging
from worker.status import build_status_snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Pantry background worker")
    parser.add_argument("--status", action="store_true", help="Print a status snapshot")
    parser.add_argument("--once", action="store_true", help="Run a single placeholder cycle")
    args = parser.parse_args()

    settings = get_settings()
    configure_logging(service_name=settings.service_name, log_level=settings.log_level)
    logger = structlog.get_logger(__name__)

    if args.status:
        print(json.dumps(build_status_snapshot(settings)))
        return

    run_id = str(uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(service=settings.service_name, run_id=run_id)

    logger.info(
        "worker.started",
        environment=settings.environment,
        version=settings.app_version,
        database_url=settings.safe_database_url,
        redis_url=settings.safe_redis_url,
        import_storage_root=settings.import_storage_root,
    )
    logger.info("worker.status", **build_status_snapshot(settings))

    if args.once or settings.run_once:
        processed = process_next_import_job()
        logger.info("worker.exiting", reason="single_run", processed_job=processed)
        return

    while True:
        processed = process_next_import_job()
        if processed:
            logger.info("worker.poll.completed", queue="imports", result="processed_job")
            continue

        logger.info(
            "worker.heartbeat",
            queue="imports",
            status="idle",
            poll_interval_seconds=settings.poll_interval_seconds,
        )
        time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()
