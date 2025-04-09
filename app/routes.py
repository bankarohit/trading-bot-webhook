# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
import os
from app.fyers_api import place_order

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/healthz", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("token") != os.getenv("WEBHOOK_SECRET_TOKEN"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    result = place_order(data)
    return jsonify(result)