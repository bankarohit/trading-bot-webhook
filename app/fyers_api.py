# ------------------ app/fyers_api.py ------------------
import traceback

def get_ltp(symbol, fyersModelInstance):
    try:
        response = fyersModelInstance.quotes({"symbols": symbol})
        return response.get("d", [{}])[0].get("v", {}).get("lp")
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] Exception in get_ltp: {str(e)}")
        return {"code": -1, "message": str(e)}
        

def place_order(fyersModelInstance,symbol, action, qty, sl = 30, tp = 60, productType = "BO"):
    if not qty:
        if symbol.startswith("NSE:NIFTY"):
            qty = 75 # Lot size of nifty is 75
        elif symbol.startswith("NSE:BANKNIFTY"):
            qty = 30 # Lot size of bankNifty is 30
        else:
            qty = 1 # Default size for other symbols
    order_data = {
        "symbol": symbol,
        "qty": qty,
        "type": 2, # Market order
        "side": 1 if action.upper() == "BUY" else -1,
        "productType": productType,
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stopLoss": sl, # random value for testing
        "takeProfit": tp  # random value for testing
    }
    try:
        print("[DEBUG] Placing order with data:", order_data)
        response = fyersModelInstance.place_order(order_data)
        print("[DEBUG] Response from Fyers order API:", response)
        return response
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] Exception while placing order: {str(e)}")
        return {"code": -1, "message": str(e)}