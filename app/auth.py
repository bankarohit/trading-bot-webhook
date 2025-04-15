# ------------------ app/auth.py ------------------
import os
import json
import hashlib
import requests
from fyers_apiv3 import fyersModel
import traceback

TOKENS_FILE = "tokens.json"

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")
FYERS_PIN = os.getenv("FYERS_PIN")


def save_tokens(data):
    try:
        with open(TOKENS_FILE, "w") as f:
            json.dump(data, f)
        print("[AUTH] Tokens saved successfully.")
    except Exception as e:
        traceback.print_exc()
        print(f"[AUTH] Failed to save tokens: {e}")


def load_tokens():
    try:
        if os.path.exists(TOKENS_FILE):
            with open(TOKENS_FILE, "r") as f:
                return json.load(f)
    except Exception as e:
        traceback.print_exc()
        print(f"[AUTH] Failed to load tokens: {e}")
    return {}


def generate_tokens_from_auth_code():
    if not AUTH_CODE:
        print("[AUTH] Missing AUTH_CODE. Visit the auth URL to obtain it.")
        session = fyersModel.SessionModel(
            client_id=APP_ID,
            secret_key=SECRET_ID,
            redirect_uri=REDIRECT_URI,
            response_type="code",
            grant_type="authorization_code",
            state="sample"
        )
        print(session.generate_authcode())
        return None

    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
        state="sample"
    )
    session.set_token(AUTH_CODE)

    try:
        response = session.generate_token()
        if "access_token" in response:
            save_tokens(response)
            return response["access_token"]
        print(f"[AUTH] Failed to generate token: {response}")
    except Exception as e:
        traceback.print_exc()
        print(f"[AUTH] Exception during token generation: {e}")
    return None


def refresh_access_token():
    tokens = load_tokens()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("[AUTH] No refresh_token found in tokens.json")
        return None

    if not FYERS_PIN:
        print("[AUTH] FYERS_PIN environment variable not set")
        return None

    app_hash = hashlib.sha256(f"{APP_ID}:{SECRET_ID}".encode()).hexdigest()
    payload = {
        "grant_type": "refresh_token",
        "appIdHash": app_hash,
        "refresh_token": refresh_token,
        "pin": FYERS_PIN
    }
    headers = {"Content-Type": "application/json"}

    try:
        response = requests.post("https://api-t1.fyers.in/api/v3/validate-refresh-token",
                                 json=payload, headers=headers).json()
        if response.get("s") == "ok" and "access_token" in response:
            tokens["access_token"] = response["access_token"]
            save_tokens(tokens)
            return tokens["access_token"]
        print(f"[AUTH] Refresh token failed: {response}")
    except Exception as e:
        traceback.print_exc()
        print(f"[AUTH] Exception during token refresh: {e}")
    return None

def get_access_token():
    tokens = load_tokens()
    if "access_token" in tokens:
        return tokens["access_token"]

    return refresh_access_token() or generate_tokens_from_auth_code()


def get_auth_code_url():
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
        state="sample"
    )
    return session.generate_authcode()


def get_fyers():
    return fyersModel.FyersModel(
        token=get_access_token(),
        is_async=False,
        client_id=APP_ID,
        log_path=""
    )