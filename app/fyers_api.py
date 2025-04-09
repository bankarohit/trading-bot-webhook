# ------------------ app/fyers_api.py ------------------
import os
import requests
from app.utils import get_option_symbol, get_nearest_strike, get_spot_price

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


def place_order(payload):
    token = get_access_token()
    url = "https://api.fyers.in/api/v2/orders"
    headers = {"Authorization": f"Bearer {token}"}

    if "symbol" not in payload:
        index = payload.get("index", "NIFTY")
        option_type = payload.get("option_type", "CE")
        index_symbol = "NSE:NIFTY-INDEX" if index.upper() == "NIFTY" else f"NSE:{index.upper()}-INDEX"
        spot_price = get_spot_price(index_symbol, token)
        if not spot_price:
            return {"success": False, "error": "Unable to fetch spot price."}
        strike = get_nearest_strike(spot_price)
        payload["symbol"] = get_option_symbol(index, strike, option_type)

    order_payload = {
        "symbol": payload["symbol"],
        "qty": payload.get("qty", 50),
        "type": 2 if payload.get("order_type", "MARKET").upper() == "MARKET" else 1,
        "side": 1 if payload.get("action", "BUY").upper() == "BUY" else -1,
        "productType": payload.get("product_type", "MIS"),
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stopLoss": 0,
        "takeProfit": 0
    }
    return requests.post(url, json=order_payload, headers=headers).json()