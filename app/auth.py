# ------------------ app/auth.py ------------------
import logging
from app.token_manager import get_token_manager, AuthCodeMissingError, RefreshTokenError

logger = logging.getLogger(__name__)
_token_manager = get_token_manager()

def get_fyers():
    try:
        return _token_manager.get_fyers_client()
    except Exception as e:
        logger.exception("[AUTH] Failed to get Fyers client: %s", e)
        raise

def get_auth_code_url():
    try:
        return _token_manager.get_auth_code_url()
    except Exception as e:
        logger.exception("[AUTH] Failed to get auth code URL: %s", e)
        raise

def get_access_token():
    try:
        token = _token_manager.get_access_token()
        if token:
            return token
        logger.error("[AUTH] Access token is None")
        raise AuthCodeMissingError("Access token could not be retrieved.")
    except Exception as e:
        logger.exception("[AUTH] Exception in get_access_token: %s", e)
        raise

def refresh_access_token():
    try:
        token = _token_manager.refresh_token()
        if token:
            return token
        logger.error("[AUTH] Token refresh returned None")
        raise RefreshTokenError("Token refresh failed.")
    except Exception as e:
        logger.exception("[AUTH] Error refreshing token: %s", e)
        raise
