# ------------------ app/routes.py ------------------
from flask import Blueprint, request, jsonify
from app.fyers_api import get_ltp, place_order, _validate_order_params
from app.utils import log_trade_to_sheet, get_symbol_from_csv, get_gsheet_client,get_Redis_client
from app.auth import get_fyers, get_auth_code_url, get_access_token, refresh_access_token , generate_access_token
import os
import logging
import time

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)

@webhook_bp.route("/readyz", methods=["GET"])
def health_check():
    try:
        # 1. Check Access Token
        token = get_access_token()
        if not token:
            raise Exception("Access token unavailable")

        # 2. Ping Fyers API to get User Profile
        fyers = get_fyers()
        profile_response = fyers.get_profile()

        if profile_response.get("s") != "ok":
            raise Exception(f"Fyers API ping failed: {profile_response}")
        
        return jsonify({
            "status": "ok",
            "token_status": "active",
            "fyers_status": "reachable",
            "profile": profile_response.get("data", {})
        }), 200

    except Exception as e:
        logger.exception(f"Health check failed: {e}")
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@webhook_bp.route("/refresh-token", methods=["POST"])
def refresh_token():
    try:
        token = refresh_access_token()
        if token:
            return jsonify({"success": True, "message": "Token refreshed"}), 200
        logger.error("Token refresh returned None")
        return jsonify({"success": False, "message": "Failed to refresh token"}), 401
    except Exception as e:
        logger.exception(f"Error refreshing token: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500
    
@webhook_bp.route("/generate-token", methods=["POST"])
def generate_token():
    try:
        token = generate_access_token()
        if token:
            return jsonify({"success": True, "message": "Token refreshed"}), 200
        logger.error("Token refresh returned None")
        return jsonify({"success": False, "message": "Failed to refresh token"}), 401
    except Exception as e:
        logger.exception(f"Error refreshing token: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

@webhook_bp.route("/auth-url", methods=["GET"])
def get_auth_url():
    try:
        url = get_auth_code_url()
        if not url:
            logger.error("Failed to generate auth URL")
            return jsonify({"success": False, "message": "Failed to generate auth URL"}), 500
        return jsonify({"success": True, "auth_url": url}), 200
    except Exception as e:
        logger.exception(f"Error getting auth URL: {e}")
        return jsonify({"success": False, "message": "Internal server error"}), 500

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
            logger.error(f"Missing fields - symbol: {symbol}, action: {action}, strike: {strikeprice}, option_type: {optionType}, expiry: {expiry}, token: {token}")
            return jsonify({"success": False, "error": "Missing required fields"}), 400

        if token != os.getenv("WEBHOOK_SECRET_TOKEN"):
            logger.error(f"Unauthorized access from IP: {request.remote_addr}. Token provided: {token}")
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        start = time.time()
        fyers_symbol = get_symbol_from_csv(symbol, strikeprice, optionType, expiry)
        logger.info(f"getSymbol took {time.time() - start:.2f}s")

        if not fyers_symbol:
            return jsonify({"success": False, "error": "Could not resolve symbol"}), 403

        ltp = None
        try:
            start = time.time()
            fyers = get_fyers()
            logger.info(f"getFyers took {time.time() - start:.2f}s")
            if not fyers:
                return jsonify({"success": False, "error": "Failed to initialize Fyers client"}), 500
            
            start = time.time()
            
            ltp = get_ltp(fyers_symbol, fyers)
            logger.info(f"getLTPs took {time.time() - start:.2f}s")
            if ltp is not None:
                sl = round(ltp * 0.05)
                tp = round(ltp * 0.1)
            else:
                logger.warning(f"LTP returned None for symbol {fyers_symbol}, using default SL/TP from fyers_api")
                sl = None
                tp = None
        except Exception as e:
            logger.exception(f"Failed to get LTP for symbol {symbol}: {e}")
            ltp = None
            sl = None
            tp = None

        qty, sl, tp, productType = _validate_order_params(fyers_symbol, qty, sl, tp, productType)
        try:
            start = time.time()
            _trade_logged = log_trade_to_sheet(fyers_symbol, action, qty, ltp, sl, tp, sheet_name="Trades")
            logger.info(f"logTrade took {time.time() - start:.2f}s")
        except Exception as e:
            logger.exception(f"Failed to log trade to sheet: {e}")
            _trade_logged = False
        try:
            fyers = get_fyers()
            order_response = place_order(fyers_symbol, qty, action, sl, tp, productType, fyers)
            if order_response.get("s") != "ok":
                redis = get_Redis_client()
                redis.set(f"order_error_{fyers_symbol}", order_response.get("message", "Unknown error"))
                logger.error(f"Fyers order failed: {order_response}")
                return jsonify({  
                    "code": -1,
                    "message": f"Fyers order failed: {order_response.get('message', 'Unknown error')}",
                    "details": order_response
                }), 500            
        except Exception as e:
            logger.exception(f"Exception occured while placing order: {e}")
            return jsonify({
                "code": -1,
                "message": f"Exception while placing order: {str(e)}"
            }), 500

        # redis = get_Redis_client()
        # redis.set(fyers_symbol, "OPEN")
        return jsonify({"success": True, 
                        "message": "order placed", 
                        "order_response": order_response, 
                        "logged_to_sheet": _trade_logged 
                        }), 200

    except Exception as e:
        logger.exception(f"Unhandled error in webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
