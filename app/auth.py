import logging
from app.logging_config import request_id_extra
from app.token_manager import (
    get_token_manager,
    AuthCodeMissingError,
    RefreshTokenError,
)

logger = logging.getLogger(__name__)


def _token_manager():
    """Helper to lazily obtain the TokenManager instance."""
    return get_token_manager()

def get_fyers():
    try:
        return get_token_manager().get_fyers_client()
    except Exception as e:
        logger.exception("[AUTH] Failed to get Fyers client: %s", e, extra=request_id_extra())
        raise

def get_auth_code_url():
    try:
        return get_token_manager().get_auth_code_url()
    except Exception as e:
        logger.exception("[AUTH] Failed to get auth code URL: %s", e, extra=request_id_extra())
        raise

def get_access_token():
    try:
        token = get_token_manager().get_access_token()
        if token:
            return token
        logger.error("[AUTH] Access token is None", extra=request_id_extra())
        raise AuthCodeMissingError("Access token could not be retrieved.")
    except Exception as e:
        logger.exception("[AUTH] Exception in get_access_token: %s", e, extra=request_id_extra())
        raise

def refresh_access_token():
    try:
        return get_token_manager().refresh_token()
    except RefreshTokenError as e:
        logger.error(f"[AUTH] Token refresh failed: {e}", extra=request_id_extra())
        raise  # Propagate so caller knows it's critical
    except Exception as e:
        logger.exception("[AUTH] Error refreshing token: %s", e, extra=request_id_extra())
        raise

def generate_access_token():
    try:
        token = get_token_manager().generate_token()
        if token:
            return token
        else:
            logger.error("[AUTH] Token generation returned None", extra=request_id_extra())
    except Exception as e:
        logger.exception("[AUTH] Error generating token: %s", e, extra=request_id_extra())

