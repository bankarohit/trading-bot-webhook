"""Handle Fyers API authentication tokens.

This module manages access and refresh tokens for the Fyers trading API. It
supports persisting tokens to Google Cloud Storage or a local ``tokens.json``
file and exposes a thread-safe :class:`TokenManager` singleton through
``get_token_manager``.
"""

import os
import json
import hashlib
import requests
import logging
import threading
import base64
from datetime import datetime, timedelta
from fyers_apiv3 import fyersModel
from app.config import load_env_variables
from app.notifications import send_notification
from app.utils import _get_storage_client

logger = logging.getLogger(__name__)

TOKENS_FILE = "tokens.json"

# Thread-safe singleton
_token_manager_instance = None
_token_manager_lock = threading.Lock()


class TokenManagerException(Exception):
    """Base exception for TokenManager errors."""
    pass


class AuthCodeMissingError(TokenManagerException):
    """Raised when auth code is missing."""
    pass


class RefreshTokenError(TokenManagerException):
    """Raised when token refresh fails."""
    pass


class EnvironmentVariableError(TokenManagerException):
    """Raised when required environment variables are missing."""
    pass


def get_token_manager():
    """Get or create the singleton instance of TokenManager in a thread-safe way."""
    global _token_manager_instance

    if _token_manager_instance is None:
        with _token_manager_lock:
            # Double-check pattern to avoid race condition
            if _token_manager_instance is None:
                _token_manager_instance = TokenManager()
                logger.info("TokenManager singleton instance created")
    return _token_manager_instance
    
class TokenManager:
    TOKEN_VALIDITY_SECONDS = 86400

    def __init__(self, tokens_file=TOKENS_FILE):
        """Initialize the TokenManager and prepare the environment.

        Environment variables are validated and any previously saved tokens are
        loaded from Google Cloud Storage or the local ``tokens_file``. A Fyers
        session model is also initialized.
        """
        # This will validate all required environment variables
        load_env_variables(
        )  # This already calls load_dotenv() and validates variables

        self.tokens_file = tokens_file
        bucket_name = os.getenv("GCS_BUCKET_NAME")
        blob_name = os.getenv("GCS_TOKENS_FILE", "tokens/tokens.json")
        logger.info(
            "Using tokens_file=%s, bucket=%s, blob=%s",
            self.tokens_file,
            bucket_name,
            blob_name,
        )
        self._tokens = self._load_tokens()
        self._session = self._init_session_model()
        self._fyers = None  # Will be lazily initialized when needed
        self._lock = threading.RLock()  # Reentrant lock for thread safety
        self.token_validity_seconds = self.TOKEN_VALIDITY_SECONDS

    def _is_token_expired(self) -> bool:
        """Return True if now is past ``expires_at`` or token is missing."""
        token = self._tokens.get("access_token")
        if not token:
            return True

        expires_at_str = self._tokens.get("expires_at")
        if not expires_at_str:
            # Backwards-compatible behavior: if we have an access_token but no
            # expiry metadata, assume it's usable and let API calls fail/refresh
            # as needed (prevents unnecessary token generation in tests/legacy).
            return False

        try:
            # Accept plain ISO or Z-suffix
            exp_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        except Exception:
            return True

        now = datetime.now(exp_dt.tzinfo) if getattr(exp_dt, "tzinfo", None) else datetime.now()
        return now >= exp_dt

    def _load_tokens(self):
            """
            Load tokens from local plain-JSON file if present; otherwise try GCS.
            On successful GCS read, cache to local file atomically.
            Return dict on success, or None if not found anywhere.
            """
            local_path = self.tokens_file
            gcs_bucket_name = os.getenv("GCS_BUCKET_NAME")
            gcs_object_name = os.getenv("GCS_TOKENS_FILE", "tokens/tokens.json")

            # 1) Try LOCAL first
            try:
                if local_path and os.path.exists(local_path):
                    with open(local_path, "r", encoding="utf-8") as f:
                        tokens = json.load(f)
                    logger.info("Loaded tokens from local file %s", local_path)
                    return tokens
            except Exception:
                logger.exception("Failed reading/parsing local tokens file %s", local_path)

            # 2) Try GCS
            try:
                if not gcs_bucket_name:
                    logger.warning("GCS_BUCKET_NAME not set; skipping cloud lookup.")
                else:
                    storage_client = _get_storage_client()
                    bucket = storage_client.bucket(gcs_bucket_name)
                    blob = bucket.get_blob(gcs_object_name)  # returns None if missing

                    if blob is not None:
                        json_text = blob.download_as_text(encoding="utf-8")
                        tokens = json.loads(json_text)

                        gcs_path = f"gs://{bucket.name}/{blob.name}"
                        logger.info("Loaded tokens from %s", gcs_path)

                        # Cache locally (atomic write)
                        try:
                            if local_path:
                                tmp = f"{local_path}.tmp"
                                os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
                                with open(tmp, "w", encoding="utf-8") as f:
                                    f.write(json_text)
                                os.replace(tmp, local_path)
                                logger.info("Cached tokens to local file %s", local_path)
                        except Exception:
                            logger.warning("Failed caching GCS tokens to local file %s", local_path, exc_info=True)

                        return tokens
                    else:
                        logger.warning("Tokens not found in GCS at gs://%s/%s",
                                    gcs_bucket_name, gcs_object_name)
            except Exception:
                logger.exception("GCS load failed.")

            # 3) Nothing found
            return {}

    def _save_tokens(self):
        """
        Save tokens locally as plain JSON (atomic write) and upload plain JSON to GCS.
        Also writes an optional encrypted sidecar locally (<file>.enc) for recovery.
        """
        # 1) Gather env/config up front
        gcs_bucket_name = os.getenv("GCS_BUCKET_NAME")
        gcs_object_name = os.getenv("GCS_TOKENS_FILE", "tokens/tokens.json")
        if not gcs_bucket_name:
            logger.error("GCS_BUCKET_NAME env var is not set.")
            return
        if not self.tokens_file:
            logger.error("tokens_file path is not configured.")
            return

        # 2) Serialize to JSON once (as text)
        try:
            json_text = json.dumps(self._tokens, ensure_ascii=False, separators=(",", ":"))
        except Exception:
            logger.exception("Failed to serialize tokens to JSON.")
            return

        # 3) Atomically write PLAIN JSON locally
        try:
            tokens_dir = os.path.dirname(self.tokens_file)
            if tokens_dir:
                os.makedirs(tokens_dir, exist_ok=True)

            tmp_path = f"{self.tokens_file}.tmp"
            # Write as text with explicit UTF-8; then atomic replace
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(json_text)
            os.replace(tmp_path, self.tokens_file)
        except Exception:
            logger.exception("Failed to save plain JSON tokens locally.")
            return

        # 4) Upload PLAIN JSON to GCS
        try:
            storage_client = _get_storage_client()
            bucket = storage_client.bucket(gcs_bucket_name)
            blob = bucket.blob(gcs_object_name)
            blob.cache_control = "no-cache"

            # Upload the plain JSON text directly
            blob.upload_from_string(json_text, content_type="application/json; charset=utf-8")

            gcs_path = f"gs://{bucket.name}/{blob.name}"
            logger.info("Saved plain JSON locally to %s and uploaded to %s", self.tokens_file, gcs_path)
        except Exception:
            logger.exception("GCS upload failed.")

    def _init_session_model(self):
        """Initialize and return a SessionModel for Fyers API."""
        app_id = os.getenv("FYERS_APP_ID")
        secret_id = os.getenv("FYERS_SECRET_ID")
        redirect_uri = os.getenv("FYERS_REDIRECT_URI")

        return fyersModel.SessionModel(client_id=app_id,
                                       secret_key=secret_id,
                                       redirect_uri=redirect_uri,
                                       response_type="code",
                                       grant_type="authorization_code",
                                       state="sample")

    def get_auth_code_url(self):
        """Generate and return the authorization code URL."""
        return self._session.generate_authcode()

    def get_access_token(self):
        """Get a valid access token, refreshing or generating if necessary."""
        with self._lock:
            # If we have a non-expired token, return it
            if not self._is_token_expired():
                return self._tokens.get("access_token")

            # Token is missing or expired: try refresh first
            try:
                token = self.refresh_token()
                if token:
                    return token
            except RefreshTokenError as e:
                logger.info("Token refresh failed, generating new token: %s", e)

            # If refresh failed, generate a new token
            return self.generate_token()

    def generate_token(self):
        """Generate a new access token using the authorization code."""
        with self._lock:
            auth_code = os.getenv("FYERS_AUTH_CODE", "").strip()
            if not auth_code:
                logger.error("Missing AUTH_CODE. Visit the auth URL to obtain it.")
                raise AuthCodeMissingError("FYERS_AUTH_CODE not set in environment")

            try:
                self._session.set_token(auth_code)
                response = self._session.generate_token()  # FYERS SDK call
            except Exception as e:
                logger.exception("Token generation error during SDK call")
                raise TokenManagerException(f"Token generation error: {e}")

            # Happy path
            if isinstance(response, dict) and response.get("s") == "ok" and "access_token" in response:
                now = datetime.now()
                self._tokens["access_token"] = response["access_token"]
                if "refresh_token" in response:
                    self._tokens["refresh_token"] = response["refresh_token"]
                self._tokens["issued_at"] = now.isoformat()
                self._tokens["expires_at"] = (
                    now + timedelta(seconds=self.token_validity_seconds)
                ).isoformat()

                self._save_tokens()

                # Recreate client with fresh token
                self._fyers = None
                self._initialize_fyers_client()
                logger.info("Access token generated successfully at %s", now.isoformat())
                return response["access_token"]

            # Error path — log sanitized info
            s = response.get("s") if isinstance(response, dict) else None
            code = response.get("code") if isinstance(response, dict) else None
            message = response.get("message") if isinstance(response, dict) else str(response)
            error_message = f"Token generation failed: s={s}, code={code}, message={message}"
            logger.error(error_message)
            raise TokenManagerException(error_message)

    def refresh_token(self):
        """Refresh the access token using the refresh token."""
        with self._lock:
            refresh_token = self._tokens.get("refresh_token")
            fyers_pin = os.getenv("FYERS_PIN")
            app_id = os.getenv("FYERS_APP_ID")
            secret_id = os.getenv("FYERS_SECRET_ID")

            if not (refresh_token and fyers_pin):
                message = "Missing refresh_token or FYERS_PIN"
                logger.error(message)
                send_notification(message, event="token_refresh_error")
                raise RefreshTokenError(message)

            logger.info("Refreshing access token...")
            try:
                app_hash = hashlib.sha256(
                    f"{app_id}:{secret_id}".encode()).hexdigest()
                payload = {
                    "grant_type": "refresh_token",
                    "appIdHash": app_hash,
                    "refresh_token": refresh_token,
                    "pin": fyers_pin
                }
                headers = {"Content-Type": "application/json"}

                response = requests.post(
                    "https://api-t1.fyers.in/api/v3/validate-refresh-token",
                    json=payload,
                    headers=headers).json()

                if response.get("s") == "ok" and "access_token" in response:
                    # Store the current refresh token since it's not returned in the response
                    current_refresh_token = self._tokens.get("refresh_token")

                    # Update only the access token
                    self._tokens["access_token"] = response["access_token"]

                    # Ensure we don't lose the refresh token
                    if current_refresh_token and "refresh_token" not in response:
                        self._tokens["refresh_token"] = current_refresh_token

                    now = datetime.utcnow()
                    self._tokens["issued_at"] = now.isoformat()
                    self._tokens["expires_at"] = (
                        now + timedelta(seconds=self.token_validity_seconds)
                    ).isoformat()

                    self._save_tokens()

                    # Immediately initialize a new Fyers client
                    self._fyers = None  # Clear existing instance
                    self._initialize_fyers_client(
                    )  # Create new instance with updated token

                    logger.info("Access token refreshed successfully at %s",
                                datetime.now().isoformat())
                    return response["access_token"]

                error_message = f"Token refresh failed: {response}"
                logger.error(error_message, extra={"event": "token_refresh_error"})
                send_notification(error_message, event="token_refresh_error")
                raise RefreshTokenError(error_message)
            except Exception as e:
                logger.exception("Refresh token error: %s", e)
                send_notification(str(e), event="token_refresh_error")
                raise RefreshTokenError(f"Refresh token error: {e}")

    def _initialize_fyers_client(self):
        """Initialize a new Fyers client with the current access token."""
        try:
            app_id = os.getenv("FYERS_APP_ID")
            token = self._tokens.get("access_token")

            if token:
                self._fyers = fyersModel.FyersModel(token=token,
                                                    is_async=True,
                                                    client_id=app_id,
                                                    log_path="")
                # Optionally verify the client works by making a simple API call
                logger.debug("Fyers client initialized successfully")
            else:
                logger.warning(
                    "Cannot initialize Fyers client: No access token available"
                )
        except Exception as e:
            logger.exception("Failed to initialize Fyers client: %s", e)
            self._fyers = None  # Ensure it's None if initialization fails
            raise TokenManagerException(
                f"Failed to initialize Fyers client: {e}")

    def get_fyers_client(self):
        """Get a configured Fyers client with a valid access token."""
        with self._lock:
            if self._is_token_expired():
                try:
                    self.refresh_token()
                except RefreshTokenError as e:
                    logger.error("Auto refresh failed: %s", e)
            if self._fyers is None:
                self._initialize_fyers_client()
            return self._fyers
