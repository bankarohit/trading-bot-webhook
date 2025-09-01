import os
import logging
from dotenv import load_dotenv

# Ensure TLS verification works out-of-the-box for aiohttp and requests.
# Many macOS Python installs lack a system CA bundle visible to OpenSSL.
# By pointing SSL/Requests to certifi's CA file here, downstream clients
# (including Fyers' aiohttp usage) succeed without extra setup.
try:
    import certifi  # requests dependency; should be available
    _CERT_PATH = certifi.where()
    os.environ.setdefault("SSL_CERT_FILE", _CERT_PATH)
    os.environ.setdefault("REQUESTS_CA_BUNDLE", _CERT_PATH)
except Exception:
    # If certifi isn't available for some reason, proceed without forcing it.
    # Requests will still use its own bundle; aiohttp may fail on some hosts.
    pass

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
        "GOOGLE_APPLICATION_CREDENTIALS",
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
