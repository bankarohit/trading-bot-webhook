# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
import os
from app.fyers_api import get_ltp
from app.utils import log_trade_to_sheet

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/readyz", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("token") != os.getenv("WEBHOOK_SECRET_TOKEN"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403

    symbol = data.get("symbol")
    action = data.get("action")
    qty = data.get("qty", 50)
    sl = data.get("sl")
    tp = data.get("tp")

    ltp = get_ltp(symbol)
    if not ltp:
        return jsonify({"success": False, "error": "Unable to fetch LTP"}), 400

    log_trade_to_sheet(symbol, action, qty, ltp, sl, tp)
    return jsonify({"success": True, "message": "Trade logged", "ltp": ltp}), 200