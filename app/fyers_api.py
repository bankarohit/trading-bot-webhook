# ------------------ app/fyers_api.py ------------------
import os
import requests
from app.utils import get_option_symbol, get_nearest_strike, get_spot_price
from app.auth import get_access_token


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

def get_ltp(symbol):
    try:
        url = f"https://api.fyers.in/data-rest/v2/quotes/{symbol}"
        headers = {"Authorization": f"Bearer {get_access_token()}"}
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return response.json().get("d", {}).get("v", {}).get("lp")
    except Exception as e:
        print(f"[ERROR] Failed to get LTP for {symbol}: {e}")
        return None