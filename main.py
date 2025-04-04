from flask import Flask, request, jsonify
import os
import requests
from dotenv import load_dotenv
from datetime import datetime
import math

load_dotenv()

app = Flask(__name__)

# Environment Variables
APP_ID = os.getenv("FYERS_APP_ID")
SECRET_ID = os.getenv("FYERS_SECRET_ID")
REDIRECT_URI = os.getenv("FYERS_REDIRECT_URI")
AUTH_CODE = os.getenv("FYERS_AUTH_CODE")  # Generated manually from login URL
SECRET_TOKEN = os.getenv("WEBHOOK_SECRET_TOKEN")
ACCESS_TOKEN_FILE = "access_token.txt"

# === Token Management ===
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
    else:
        print("Error generating access token:", data)
        return None

def get_access_token():
    if os.path.exists(ACCESS_TOKEN_FILE):
        with open(ACCESS_TOKEN_FILE, "r") as f:
            return f.read().strip()
    return generate_access_token()

# === Option Symbol Helper ===
def get_option_symbol(index_name, strike_price, option_type):
    today = datetime.now()
    expiry_day = today.replace(day=today.day + (3 - today.weekday()) % 7)  # assuming Thursday expiry
    expiry_str = expiry_day.strftime("%y%b").upper()
    return f"NSE:{index_name}{expiry_str}{strike_price}{option_type.upper()}"

# === Auto Strike Price Logic ===
def get_spot_price(index_symbol):
    url = f"https://api.fyers.in/data-rest/v2/quotes/{index_symbol}"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
    }
    response = requests.get(url, headers=headers)
    data = response.json()
    if "d" in data and "v" in data["d"]:
        return data["d"]["v"].get("lp")  # last traded price
    return None

def get_nearest_strike(price, step=50):
    return int(round(price / step) * step)

# === Fyers Order Placement ===
def place_order(payload):
    url = "https://api.fyers.in/api/v2/orders"
    headers = {
        "Authorization": f"Bearer {get_access_token()}"
    }

    # Construct symbol if not provided
    if "symbol" not in payload:
        index = payload.get("index", "NIFTY")
        option_type = payload.get("option_type", "CE")
        
        # Get spot price and calculate strike
        index_symbol = "NSE:NIFTY-INDEX" if index.upper() == "NIFTY" else f"NSE:{index.upper()}-INDEX"
        spot_price = get_spot_price(index_symbol)
        if not spot_price:
            return {"success": False, "error": "Unable to fetch spot price."}
        strike = get_nearest_strike(spot_price, 50)

        symbol = get_option_symbol(index, strike, option_type)
    else:
        symbol = payload.get("symbol")

    order_payload = {
        "symbol": symbol,
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
    response = requests.post(url, json=order_payload, headers=headers)
    return response.json()

# === Webhook Endpoint ===
@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("token") != SECRET_TOKEN:
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    result = place_order(data)
    return jsonify(result)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)