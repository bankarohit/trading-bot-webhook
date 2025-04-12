# ------------------ app/fyers_api.py ------------------
from app.auth import get_fyers

def get_ltp(symbol, fyersModelInstance):
    response = fyersModelInstance.quotes({"symbols": symbol})
    return response.get("d", [{}])[0].get("v", {}).get("lp")

def place_order(symbol, qty, action, sl, tp, fyersModelInstance):
    order_data = {
        "symbol": symbol,
        "qty": qty,
        "type": 2,  # Market order
        "side": 1 if action.upper() == "BUY" else -1,
        "productType": "INTRADAY",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stopLoss": sl or 0,
        "takeProfit": tp or 0
    }
    print("[DEBUG] Placing order with data:", order_data)
    response = fyersModelInstance.place_order(order_data)
    print("[DEBUG] Response from Fyers order API:", response)
    return response
