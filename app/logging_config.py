import os
import logging
from logging.handlers import RotatingFileHandler
from flask import g, has_request_context

try:
    from google.cloud.logging_v2.handlers import StructuredLogHandler
    import google.cloud.logging_v2 as cloud_logging
    CLOUD_LOGGING_AVAILABLE = True
except ImportError:
    CLOUD_LOGGING_AVAILABLE = False

logger = logging.getLogger(__name__)


def get_request_id() -> str:
    """Return the current request ID if available."""
    if has_request_context() and hasattr(g, "request_id"):
        return g.request_id
    return "-"


class RequestIdFilter(logging.Filter):
    """Inject the request_id from the Flask ``g`` object."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = get_request_id()
        return True


def configure_logging() -> None:
    """Configure application wide logging with production-ready error handling."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    log_file = os.getenv("LOG_FILE")
    cloud_log_level = os.getenv("CLOUD_LOG_LEVEL", log_level).upper()
    file_log_level = os.getenv("FILE_LOG_LEVEL", log_level).upper()

    # Map level name to numeric value, defaulting to INFO if invalid
    level = getattr(logging, log_level, logging.INFO)
    cloud_level = getattr(logging, cloud_log_level, level)
    file_level = getattr(logging, file_log_level, level)

    log_format = (
        "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s] - %(message)s"
    )

    # Configure basic logging first (this is safe to call multiple times)
    logging.basicConfig(
        level=level,
        format=log_format,
        force=True  # Override any existing configuration
    )

    root_logger = logging.getLogger()
    request_filter = RequestIdFilter()

    # Apply request filter to root logger (will propagate to all handlers)
    root_logger.addFilter(request_filter)

    # Configure Cloud Logging handler
    if os.getenv("USE_CLOUD_LOGGING"):
        if not CLOUD_LOGGING_AVAILABLE:
            logger.warning(
                "USE_CLOUD_LOGGING is set but google-cloud-logging is not available. "
                "Skipping Cloud Logging setup."
            )
        else:
            try:
                client = cloud_logging.Client()
                cloud_handler = StructuredLogHandler(client=client)
                cloud_handler.setLevel(cloud_level)
                cloud_handler.addFilter(request_filter)
                root_logger.addHandler(cloud_handler)
                logger.info("Cloud Logging handler configured successfully")
            except Exception as e:
                logger.error(
                    "Failed to configure Cloud Logging handler: %s. "
                    "Application will continue without Cloud Logging.",
                    e,
                    exc_info=True
                )

    # Configure file handler
    if log_file:
        try:
            # Validate and create log directory if needed
            log_dir = os.path.dirname(log_file)
            if log_dir and not os.path.exists(log_dir):
                os.makedirs(log_dir, mode=0o755, exist_ok=True)
                logger.info("Created log directory: %s", log_dir)

            file_handler = RotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,
                encoding="utf-8"
            )
            file_handler.setLevel(file_level)
            file_handler.setFormatter(logging.Formatter(log_format))
            file_handler.addFilter(request_filter)
            root_logger.addHandler(file_handler)
            logger.info("File logging handler configured: %s", log_file)
        except PermissionError:
            logger.error(
                "Permission denied when creating log file: %s. "
                "Application will continue without file logging.",
                log_file,
                exc_info=True
            )
        except OSError as e:
            logger.error(
                "Failed to configure file logging handler for %s: %s. "
                "Application will continue without file logging.",
                log_file,
                e,
                exc_info=True
            )
        except Exception as e:
            logger.error(
                "Unexpected error configuring file logging: %s. "
                "Application will continue without file logging.",
                e,
                exc_info=True
            )

    # Log configuration summary
    handler_count = len(root_logger.handlers)
    logger.info(
        "Logging configured: level=%s, handlers=%d, cloud=%s, file=%s",
        log_level,
        handler_count,
        "enabled" if os.getenv("USE_CLOUD_LOGGING") and CLOUD_LOGGING_AVAILABLE else "disabled",
        "enabled" if log_file else "disabled"
    )
