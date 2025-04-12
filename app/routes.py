# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
import os
from app.fyers_api import get_ltp, place_order
from app.utils import log_trade_to_sheet
from app.auth import get_fyers

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/readyz", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.get_json()
        print("[DEBUG] Incoming webhook payload:", data)

        if not data:
            print("[ERROR] Empty or invalid JSON payload.")
            print("[DEBUG] Request headers:", dict(request.headers))
            print("[DEBUG] Raw body:", request.data.decode("utf-8"))
            return jsonify({"success": False, "error": "Empty or invalid JSON"}), 400

        token = data.get("token")
        if token != os.getenv("WEBHOOK_SECRET_TOKEN"):
            print(f"[ERROR] Unauthorized access from IP: {request.remote_addr}. Token provided: {token}")
            return jsonify({"success": False, "error": "Unauthorized"}), 403

        symbol = data.get("symbol")
        action = data.get("action")
        qty = data.get("qty", 50)
        sl = data.get("sl")
        tp = data.get("tp")
        productType = data.get("productType")

        if not symbol or not action or not productType:
            print(f"[ERROR] Missing fields - symbol: {symbol}, action: {action}, qty: {qty}")
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        fyers = get_fyers()
        try:
            ltp = get_ltp(symbol, fyers)
        except Exception as e:
            print(f"[ERROR] Failed to get LTP for symbol {symbol}: {str(e)}")
            ltp = "N/A"

        order_response = place_order(symbol, qty, action, sl, tp, productType, fyers)
        log_trade_to_sheet(symbol, action, qty, ltp, sl, tp)

        print("[INFO] Trade processed and logged successfully.")
        return jsonify({"success": True, "message": "Trade logged and order placed", "ltp": ltp, "order_response": order_response})

    except Exception as e:
        print(f"[FATAL] Unhandled error in webhook: {str(e)}")
        return jsonify({"success": False, "error": "Internal server error"}), 500