import os
import json
from fyers_apiv3 import fyersModel

TOKENS_FILE = "tokens.json"

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")

def save_tokens(data):
    with open(TOKENS_FILE, "w") as f:
        json.dump(data, f)

def load_tokens():
    if os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "r") as f:
            return json.load(f)
    return {}

def generate_tokens_from_auth_code():
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        grant_type="authorization_code",
        state="sample"
    )

    if not AUTH_CODE:
        print("[INFO] Please visit the Fyers auth URL to get auth_code:")
        print(session.generate_authcode())
        return None

    session.set_token(AUTH_CODE)
    response = session.generate_token()
    if "access_token" in response:
        save_tokens(response)
        return response["access_token"]
    print("[ERROR] Auth code login failed:", response)
    return None

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

def refresh_access_token():
    tokens = load_tokens()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        return None

    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        grant_type="refresh_token",
        state="sample"
    )
    session.set_token(refresh_token)
    response = session.generate_token()
    if "access_token" in response:
        save_tokens(response)
        print("[INFO] Refreshed access token successfully.")
        return response["access_token"]
    print("[ERROR] Refresh token failed:", response)
    return None

def get_access_token():
    tokens = load_tokens()
    if "access_token" in tokens:
        return tokens["access_token"]

    token = refresh_access_token()
    if token:
        return token

    return generate_tokens_from_auth_code()

def get_fyers():
    return fyersModel.FyersModel(
        token=get_access_token(),
        is_async=False,
        client_id=APP_ID,
        log_path=""
    )