# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
from app.fyers_api import get_ltp, place_order
from app.utils import log_trade_to_sheet, get_symbol_from_csv, get_sheet_client
from app.auth import get_fyers, get_auth_code_url, get_access_token, refresh_access_token
import traceback
import os
import math

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/readyz", methods=["GET"])
def health_check():
    try:
        token = get_access_token()
        if not token:
            raise Exception("Access token unavailable")
        return jsonify({"status": "ok", "token_status": "active"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@webhook_bp.route("/refresh-token", methods=["POST"])
def refresh_token():
    try:
        token = refresh_access_token()
        if token:
            return jsonify({"success": True, "message": "Token refreshed"}), 200
        print("[ERROR] Token refresh returned None")
        return jsonify({"success": False, "message": "Failed to refresh token"}), 501
    except Exception as e:
        traceback.print_exc()
        print(f"[FATAL] Error refreshing token: {str(e)}")
        return jsonify({"success": False, "message": "Internal server error"}), 502
    
@webhook_bp.route("/auth-url", methods=["GET"])
def get_auth_url():
    url = get_auth_code_url()
    return jsonify({"auth_url": url})

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()

        if not data:
            return jsonify({"success": False, "error": "Empty or invalid JSON", "data": data}), 400

        token = data.get("token")
        symbol = data.get("symbol")
        strikeprice = data.get("strikeprice")
        optionType = data.get("optionType")
        expiry = data.get("expiry")
        action = data.get("action")
        qty = data.get("qty")
        sl = data.get("sl")
        tp = data.get("tp")
        productType = data.get("productType", "BO")

        if not symbol or not action or not strikeprice or not optionType or not expiry or not token:
            print(f"[ERROR] Missing fields - symbol: {symbol}, action: {action}, strike: {strikeprice}, option_type: {optionType}, expiry: {expiry}, token: {token}")
            return jsonify({"success": False, "error": "Missing required fields"}), 401

        if token != os.getenv("WEBHOOK_SECRET_TOKEN"):
            print(f"[ERROR] Unauthorized access from IP: {request.remote_addr}. Token provided: {token}")
            return jsonify({"success": False, "error": "Unauthorized"}), 402
        
        fyers = get_fyers()
        gSheetClient = get_sheet_client()
        fyers_symbol = get_symbol_from_csv(symbol, strikeprice, optionType, expiry)
        
        if not fyers_symbol:
            return jsonify({"success": False, "error": "Could not resolve symbol"}), 403
        
        try:
            ltp = get_ltp(fyers, fyers_symbol)
            sl = round(ltp * .05)
            tp = round(ltp * .1)
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] Failed to get LTP for symbol {symbol}: {str(e)}")
            ltp = "N/A"
        try:
            order_response = place_order(fyers, fyers_symbol, action, qty, sl, tp, productType)
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] Failed to place order, {order_response} , {str(e)}")

        try:
            gSheetresponse = log_trade_to_sheet(gSheetClient, fyers_symbol, action, qty, ltp, sl, tp)
        except Exception as e:
            traceback.print_exc()
            print(f"[ERROR] Failed to log trade to sheet: {str(e)}")

        return jsonify({"success": True, "message": "Trade logged and order placed", "ltp": ltp, "order_response": order_response, "gSheetresponse": gSheetresponse}), 200

    except Exception as e:
        traceback.print_exc()
        print(f"[FATAL] Unhandled error in webhook: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 505