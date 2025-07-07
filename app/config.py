import os
import logging
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

def load_env_variables():
    """Load required environment variables and verify they are present."""

    load_dotenv()
    required_vars = [
        "FYERS_APP_ID",
        "FYERS_SECRET_ID",
        "FYERS_REDIRECT_URI",
        "WEBHOOK_SECRET_TOKEN",
        "FYERS_PIN",
        "FYERS_AUTH_CODE",
        "GCS_BUCKET_NAME",
        "GCS_TOKENS_FILE",
        "KMS_KEY_NAME",
    ]

    missing_vars = []
    for var in required_vars:
        if os.getenv(var):
            logger.debug("Environment variable %s is set", var)
        else:
            logger.debug("Environment variable %s is missing", var)
            missing_vars.append(var)

    if missing_vars:
        logger.error(
            "Missing required environment variables: %s",
            ", ".join(missing_vars),
        )
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )
