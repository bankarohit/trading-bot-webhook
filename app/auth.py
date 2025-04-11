# ------------------ app/auth.py ------------------
import os
from fyers_apiv3 import fyersModel

ACCESS_TOKEN_FILE = "access_token.txt"

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")

def generate_access_token():
    session = fyersModel.SessionModel(
        client_id=APP_ID,
        secret_key=SECRET_ID,
        redirect_uri=REDIRECT_URI,
        response_type="code",
        state="sample"
    )
    session.set_token(AUTH_CODE)
    response = session.generate_token()
    if "access_token" in response:
        with open(ACCESS_TOKEN_FILE, "w") as f:
            f.write(response["access_token"])
        return response["access_token"]
    print("Error generating access token:", response)
    return None

def get_access_token():
    if os.path.exists(ACCESS_TOKEN_FILE):
        with open(ACCESS_TOKEN_FILE, "r") as f:
            return f.read().strip()
    return generate_access_token()

def get_fyers():
    return fyersModel.FyersModel(
        token=get_access_token(),
        is_async=False,
        client_id=APP_ID,
        log_path=""
    )
