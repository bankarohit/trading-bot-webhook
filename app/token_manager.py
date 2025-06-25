import os
import json
import hashlib
import requests
import logging
import threading
from datetime import datetime
from fyers_apiv3 import fyersModel
from app.config import load_env_variables
from google.cloud import storage

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
    def __init__(self, tokens_file=TOKENS_FILE):
        """Initialize the TokenManager with the specified tokens file."""
        # This will validate all required environment variables
        load_env_variables()  # This already calls load_dotenv() and validates variables

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
    
    def _load_tokens(self):
        try:
            storage_client = storage.Client()
            bucket = storage_client.bucket(os.getenv("GCS_BUCKET_NAME"))
            blob = bucket.blob(os.getenv("GCS_TOKENS_FILE", "tokens/tokens.json"))

            if blob.exists():
                blob.download_to_filename(self.tokens_file)
                gcs_path = f"gs://{bucket.name}/{blob.name}"
                logger.info(
                    "Loaded tokens from %s into %s", gcs_path, self.tokens_file)
                with open(self.tokens_file, "r") as f:
                    return json.load(f)
            else:
                gcs_path = f"gs://{bucket.name}/{blob.name}"
                logger.warning(
                    "tokens.json not found in GCS at %s, starting fresh.",
                    gcs_path)
        except Exception as e:
            logger.exception("GCS load failed: %s", e)
        # Fallback to local file if available
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, "r") as f:
                    logger.info("Loaded tokens from local file %s", self.tokens_file)
                    return json.load(f)
            else:
                logger.warning("Local tokens file %s not found, starting fresh.", self.tokens_file)
        except Exception as e:
            logger.exception("Local file load failed: %s", e)
        return {}

    def _save_tokens(self):
        """Save tokens to the tokens file with thread safety."""
        with self._lock:
            try:
                with open(self.tokens_file, "w") as f:
                    json.dump(self._tokens, f)

                storage_client = storage.Client()
                bucket = storage_client.bucket(os.getenv("GCS_BUCKET_NAME"))
                blob = bucket.blob(os.getenv("GCS_TOKENS_FILE", "tokens/tokens.json"))
                blob.upload_from_filename(self.tokens_file)

                gcs_path = f"gs://{bucket.name}/{blob.name}"
                logger.info(
                    "Saved tokens from %s to %s", self.tokens_file, gcs_path)
            except Exception as e:
                logger.exception("GCS save failed: %s", e)

    def _init_session_model(self):
        """Initialize and return a SessionModel for Fyers API."""
        app_id = os.getenv("FYERS_APP_ID")
        secret_id = os.getenv("FYERS_SECRET_ID")
        redirect_uri = os.getenv("FYERS_REDIRECT_URI")
        
        return fyersModel.SessionModel(
            client_id=app_id,
            secret_key=secret_id,
            redirect_uri=redirect_uri,
            response_type="code",
            grant_type="authorization_code",
            state="sample"
        )

    def get_auth_code_url(self):
        """Generate and return the authorization code URL."""
        return self._session.generate_authcode()

    def get_access_token(self):
        """Get a valid access token, refreshing or generating if necessary."""
        with self._lock:
            # If we have a token, use it
            if "access_token" in self._tokens:
                return self._tokens["access_token"]
            
            # Try to refresh the token
            try:
                token = self.refresh_token()
                if token:
                    return token
            except RefreshTokenError as e:
                logger.info("Token refresh failed, trying to generate new token: %s", e)
            
            # If refresh failed, try to generate a new token
            return self.generate_token()

    def generate_token(self):
        """Generate a new access token using the authorization code."""
        with self._lock:
            auth_code = os.getenv("FYERS_AUTH_CODE")
            if not auth_code:
                logger.error("Missing AUTH_CODE. Visit the auth URL to obtain it.")
                raise AuthCodeMissingError("FYERS_AUTH_CODE not set in environment")

            try:
                # Set the auth code in the session model
                self._session.set_token(auth_code)
                
                # Use the session model's generate_token method
                response = self._session.generate_token()
                
                if "access_token" in response:
                    # Update token fields individually instead of replacing the entire dictionary
                    self._tokens["access_token"] = response["access_token"]
                    if "refresh_token" in response:
                        self._tokens["refresh_token"] = response["refresh_token"]
                    
                    self._save_tokens()
                    
                    # Immediately initialize a new Fyers client
                    self._fyers = None  # Clear existing instance
                    self._initialize_fyers_client()  # Create new instance with updated token
                    
                    logger.info(
                        "Access token generated successfully at %s",
                        datetime.now().isoformat())
                    return response["access_token"]
                
                error_message = f"Token generation failed: {response}"
                logger.error(error_message)
                raise TokenManagerException(error_message)
            except Exception as e:
                logger.exception("Token generation error: %s", e)
                raise TokenManagerException(f"Token generation error: {e}")

    def refresh_token(self):
        """Refresh the access token using the refresh token."""
        with self._lock:
            refresh_token = self._tokens.get("refresh_token")
            fyers_pin = os.getenv("FYERS_PIN")
            app_id = os.getenv("FYERS_APP_ID")
            secret_id = os.getenv("FYERS_SECRET_ID")
            
            if not (refresh_token and fyers_pin):
                logger.error("Missing refresh_token or FYERS_PIN")
                raise RefreshTokenError("Missing refresh_token or FYERS_PIN")
                
            logger.info("Refreshing access token...")
            try:
                app_hash = hashlib.sha256(f"{app_id}:{secret_id}".encode()).hexdigest()
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
                    headers=headers
                ).json()
                
                if response.get("s") == "ok" and "access_token" in response:
                    # Store the current refresh token since it's not returned in the response
                    current_refresh_token = self._tokens.get("refresh_token")
                    
                    # Update only the access token
                    self._tokens["access_token"] = response["access_token"]
                    
                    # Ensure we don't lose the refresh token
                    if current_refresh_token and "refresh_token" not in response:
                        self._tokens["refresh_token"] = current_refresh_token
                    
                    self._save_tokens()
                    
                    # Immediately initialize a new Fyers client
                    self._fyers = None  # Clear existing instance
                    self._initialize_fyers_client()  # Create new instance with updated token
                    
                    logger.info(
                        "Access token refreshed successfully at %s",
                        datetime.now().isoformat())
                    return response["access_token"]
                
                error_message = f"Token refresh failed: {response}"
                logger.error(error_message)
                raise RefreshTokenError(error_message)
            except Exception as e:
                logger.exception("Refresh token error: %s", e)
                raise RefreshTokenError(f"Refresh token error: {e}")

    def _initialize_fyers_client(self):
        """Initialize a new Fyers client with the current access token."""
        try:
            app_id = os.getenv("FYERS_APP_ID")
            token = self._tokens.get("access_token")
            
            if token:
                self._fyers = fyersModel.FyersModel(
                    token=token,
                    is_async=False,
                    client_id=app_id,
                    log_path=""
                )
                # Optionally verify the client works by making a simple API call
                logger.debug("Fyers client initialized successfully")
            else:
                logger.warning("Cannot initialize Fyers client: No access token available")
        except Exception as e:
            logger.exception("Failed to initialize Fyers client: %s", e)
            self._fyers = None  # Ensure it's None if initialization fails
            raise TokenManagerException(f"Failed to initialize Fyers client: {e}")

    def get_fyers_client(self):
        """Get a configured Fyers client with a valid access token."""
        with self._lock:
            if self._fyers is None:
                self._initialize_fyers_client()
            return self._fyers
