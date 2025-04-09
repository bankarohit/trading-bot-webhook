# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
import os
from app.fyers_api import place_order

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/readyz", methods=["GET"])
def health_check():
    return jsonify({"status": "ok"}), 200

@webhook_bp.route("/webhook", methods=["POST"])
def webhook():
    data = request.json
    if data.get("token") != os.getenv("WEBHOOK_SECRET_TOKEN"):
        return jsonify({"success": False, "error": "Unauthorized"}), 403
    result = place_order(data)
    return jsonify(result)

@webhook_bp.route("/__routes", methods=["GET"])
def list_routes():
    import urllib
    from flask import current_app
    output = []
    for rule in current_app.url_map.iter_rules():
        methods = ','.join(rule.methods)
        url = urllib.parse.unquote(str(rule))
        output.append(f"{methods} {url}")
    return {"routes": output}