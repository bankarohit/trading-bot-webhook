# ------------------ app/token_manager.py ------------------
import os
import json
import hashlib
import requests
from fyers_apiv3 import fyersModel

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")
FYERS_PIN = os.getenv("FYERS_PIN")
TOKENS_FILE = "tokens.json"

_token_manager_instance = None

def get_token_manager():
    global _token_manager_instance
    if _token_manager_instance is None:
        _token_manager_instance = TokenManager()
    return _token_manager_instance

class TokenManager:
    def __init__(self, tokens_file=TOKENS_FILE):
        self.tokens_file = tokens_file
        self._tokens = self._load_tokens()
        self._session = self._init_session_model()
        self._fyers = None

    def _load_tokens(self):
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, "r") as f:
                    return json.load(f)
        except Exception as e:
            print(f"[TokenManager] Failed to load tokens: {e}")
        return {}

    def _save_tokens(self):
        try:
            with open(self.tokens_file, "w") as f:
                json.dump(self._tokens, f)
            print("[TokenManager] Tokens saved.")
        except Exception as e:
            print(f"[TokenManager] Failed to save tokens: {e}")

    def _init_session_model(self):
        return fyersModel.SessionModel(
            client_id=APP_ID,
            secret_key=SECRET_ID,
            redirect_uri=REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code",
            state="sample"
        )

    def get_auth_code_url(self):
        return self._session.generate_authcode()

    def get_access_token(self):
        if "access_token" in self._tokens:
            return self._tokens["access_token"]

        return self.refresh_token() or self.generate_token()

    def generate_token(self):
        if not AUTH_CODE:
            print("[TokenManager] Missing AUTH_CODE")
            print(self.get_auth_code_url())
            return None

        self._session.set_token(AUTH_CODE)
        try:
            response = self._session.generate_token()
            if "access_token" in response:
                self._tokens = response
                self._save_tokens()
                return response["access_token"]
        except Exception as e:
            print(f"[TokenManager] Token generation error: {e}")
        return None

    def refresh_token(self):
        refresh_token = self._tokens.get("refresh_token")
        if not refresh_token or not FYERS_PIN:
            print("[TokenManager] Cannot refresh token — missing refresh_token or pin")
            return None

        try:
            app_hash = hashlib.sha256(f"{APP_ID}:{SECRET_ID}".encode()).hexdigest()
            payload = {
                "grant_type": "refresh_token",
                "appIdHash": app_hash,
                "refresh_token": refresh_token,
                "pin": FYERS_PIN
            }
            headers = {"Content-Type": "application/json"}

            response = requests.post("https://api-t1.fyers.in/api/v3/validate-refresh-token",
                                     json=payload, headers=headers).json()
            if response.get("s") == "ok" and "access_token" in response:
                self._tokens["access_token"] = response["access_token"]
                self._save_tokens()
                self._fyers = None  # Invalidate fyers instance if token changes
                return response["access_token"]
        except Exception as e:
            print(f"[TokenManager] Refresh error: {e}")
        return None

    def get_fyers_client(self):
        if self._fyers is None:
            self._fyers = fyersModel.FyersModel(
                token=self.get_access_token(),
                is_async=False,
                client_id=APP_ID,
                log_path=""
            )
        return self._fyers