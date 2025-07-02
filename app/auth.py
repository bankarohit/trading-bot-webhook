import logging
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
    """Return a ready-to-use Fyers client instance.

    This utility calls the underlying :class:`TokenManager` to obtain an
    authenticated ``FyersModel`` client.  No parameters are required because
    the token manager handles all credential storage internally.

    Returns:
        fyers_apiv3.fyersModel.FyersModel: Configured client for making
        requests to the Fyers REST API.

    Raises:
        Exception: Propagates any exception raised by the token manager
        while creating the client.
    """
    try:
        return get_token_manager().get_fyers_client()
    except Exception as e:
        logger.exception("[AUTH] Failed to get Fyers client: %s", e)
        raise

def get_auth_code_url():
    """Generate the authorization URL for manual login.

    The URL directs the user to Fyers' login page where an authorization code
    can be retrieved.  This is typically used during initial setup to obtain
    the first access token.

    Returns:
        str: Fully qualified authorization URL.

    Raises:
        Exception: If token manager fails to build the URL.
    """
    try:
        return get_token_manager().get_auth_code_url()
    except Exception as e:
        logger.exception("[AUTH] Failed to get auth code URL: %s", e)
        raise

def get_access_token():
    """Retrieve the current access token.

    Returns the existing valid access token or attempts to obtain a new one via
    the :class:`TokenManager`.  If a token cannot be retrieved, an
    :class:`AuthCodeMissingError` is raised.

    Returns:
        str: Active access token string.

    Raises:
        AuthCodeMissingError: If no access token could be obtained.
        Exception: For any unexpected error during retrieval.
    """
    try:
        token = get_token_manager().get_access_token()
        if token:
            return token
        logger.error("[AUTH] Access token is None")
        raise AuthCodeMissingError("Access token could not be retrieved.")
    except Exception as e:
        logger.exception("[AUTH] Exception in get_access_token: %s", e)
        raise

def refresh_access_token():
    """Force a token refresh using the stored refresh token.

    Returns:
        str: Newly refreshed access token.

    Raises:
        RefreshTokenError: If the refresh attempt fails.
        Exception: For unexpected errors during refresh.
    """
    try:
        return get_token_manager().refresh_token()
    except RefreshTokenError as e:
        logger.error(f"[AUTH] Token refresh failed: {e}")
        raise  # Propagate so caller knows it's critical
    except Exception as e:
        logger.exception("[AUTH] Error refreshing token: %s", e)
        raise

def generate_access_token():
    """Generate a new access token using the configured auth code.

    This function delegates to the :class:`TokenManager` to perform the full
    token generation flow with Fyers.  It is typically used when no valid token
    exists or the refresh token has expired.

    Returns:
        str: Newly generated access token on success, otherwise ``None``.

    Raises:
        Exception: Propagates unexpected errors from the token manager.
    """
    try:
        token = get_token_manager().generate_token()
        if token:
            return token
        else:
            logger.error("[AUTH] Token generation returned None")
    except Exception as e:
        logger.exception("[AUTH] Error generating token: %s", e)
        raise

