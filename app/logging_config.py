import os
import logging
from logging.handlers import RotatingFileHandler
from flask import g, has_request_context

def request_id_extra() -> dict:
    """Return logging extras with the current request ID if available."""
    if has_request_context() and hasattr(g, "request_id"):
        return {"request_id": g.request_id}
    return {"request_id": "-"}


class RequestIdFilter(logging.Filter):
    """Inject the request ID from ``flask.g`` into log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_extra()["request_id"]
        return True


def configure_logging() -> None:
    """Configure application wide logging."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")

    # Map level name to numeric value, defaulting to INFO if invalid
    level = getattr(logging, log_level, logging.INFO)

    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] - %(message)s"
    )

    logging.basicConfig(level=level, format=log_format)

    root_logger = logging.getLogger()
    root_logger.addFilter(RequestIdFilter())
    for handler in root_logger.handlers:
        handler.addFilter(RequestIdFilter())

    if log_file:
        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
