# ------------------ app/auth.py ------------------
import os
import requests

ACCESS_TOKEN_FILE = "access_token.txt"

APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")


def generate_access_token():
    url = "https://api.fyers.in/api/v2/token"
    payload = {
        "grant_type": "authorization_code",
        "appIdHash": APP_ID,
        "code": AUTH_CODE,
        "secretKey": SECRET_ID,
        "redirectUri": REDIRECT_URI
    }
    response = requests.post(url, json=payload)
    data = response.json()
    if "access_token" in data:
        with open(ACCESS_TOKEN_FILE, "w") as f:
            f.write(data["access_token"])
        return data["access_token"]
    print("Error generating access token:", data)
    return None


def get_access_token():
    if os.path.exists(ACCESS_TOKEN_FILE):
        with open(ACCESS_TOKEN_FILE, "r") as f:
            return f.read().strip()
    return generate_access_token()
