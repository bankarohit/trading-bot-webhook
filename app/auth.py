# ------------------ app/auth.py ------------------
import os
from fyers_apiv3 import accessToken, fyersModel
import webbrowser

ACCESS_TOKEN_FILE = "access_token.txt"

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")
GRANT_TYPE = "authorization_code"
RESPONSE_TYPE = "code"
STATE = "sample"

def generate_access_token():
    session = accessToken.SessionModel(
        client_id=APP_ID,
        redirect_uri=REDIRECT_URI,
        response_type=RESPONSE_TYPE,
        state=STATE,
        secret_key=SECRET_ID,
        grant_type=GRANT_TYPE
    )

    if not AUTH_CODE:
        print("\n[INFO] Visit the following URL to authorize the app and get your auth_code:\n")
        auth_url = session.generate_authcode()
        print(auth_url)
        webbrowser.open(auth_url, new=1)
        return None

    session.set_token(AUTH_CODE)
    response = session.generate_token()
    try:
        access_token = response["access_token"]
        with open(ACCESS_TOKEN_FILE, "w") as f:
            f.write(access_token)
        return access_token
    except Exception as e:
        print("[ERROR] Token generation failed:", e)
        print("Response:", response)
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
