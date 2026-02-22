"""Centralized logging configuration. No core or rule logic."""

import logging
import time

logger = logging.getLogger("payroll.api")


def configure_logging(level: int = logging.INFO) -> None:
    """Configure structured logging for the API."""
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.setLevel(level)


async def request_logging_middleware(request, call_next):
    """Lightweight request middleware: log method, path, status, duration."""
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "request %s %s %s %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response
