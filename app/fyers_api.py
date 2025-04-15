# ------------------ app/fyers_api.py ------------------
from app.auth import get_fyers

def get_ltp(symbol, fyersModelInstance):
    try:
        response = fyersModelInstance.quotes({"symbols": symbol})
        return response.get("d", [{}])[0].get("v", {}).get("lp")
    except Exception as e:
        print(f"[ERROR] Exception in get_ltp: {str(e)}")
        return None

def place_order(symbol, qty, action, sl, tp, productType, fyersModelInstance):
    order_data = {
        "symbol": symbol,
        "qty": qty or 50,
        "type": 2, # Market order
        "side": 1 if action.upper() == "BUY" else -1,
        "productType": "BO",
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stopLoss": 1, # random value for testing
        "takeProfit": 2  # random value for testing
    }
    try:
        print("[DEBUG] Placing order with data:", order_data)
        response = fyersModelInstance.place_order(order_data)
        print("[DEBUG] Response from Fyers order API:", response)
        return response
    except Exception as e:
        print(f"[ERROR] Exception while placing order: {str(e)}")
        return {"code": -1, "message": str(e)}