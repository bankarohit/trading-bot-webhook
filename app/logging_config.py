import os
import logging
from logging.handlers import RotatingFileHandler

class RequestIdFilter(logging.Filter):
    """Ensure log records have a request_id attribute."""
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = "-"
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

    if log_file:
        file_handler = RotatingFileHandler(log_file, maxBytes=10 * 1024 * 1024, backupCount=5)
        file_handler.setFormatter(logging.Formatter(log_format))
        root_logger.addHandler(file_handler)
