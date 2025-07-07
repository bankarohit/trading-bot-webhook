from flask import Blueprint, request, jsonify
from app.logging_config import get_request_id
from app.fyers_api import get_ltp, place_order, _validate_order_params, has_short_position
from app.utils import get_symbol_from_csv
from app.notifications import send_notification
from app.auth import (
    get_fyers,
    get_auth_code_url,
    get_access_token,
    refresh_access_token,
    generate_access_token,
)
import os
import logging
import time
import inspect

logger = logging.getLogger(__name__)

webhook_bp = Blueprint("webhook", __name__)


@webhook_bp.route("/readyz", methods=["GET"])
async def health_check():
    """Perform a readiness check for the service.

    This endpoint verifies that a valid Fyers access token is available and
    that the Fyers API can be reached. It returns a JSON object with the
    current token status and a snippet of the user profile.

    **Returns**: ``200`` with status information if the check succeeds or
    ``500`` with an error message otherwise.
    """
    try:
        # 1. Check Access Token
        token = get_access_token()
        if not token:
            raise Exception("Access token unavailable")

        # 2. Ping Fyers API to get User Profile
        fyers = get_fyers()
        profile_response = fyers.get_profile()
        if inspect.iscoroutine(profile_response):
            profile_response = await profile_response

        if profile_response.get("s") != "ok":
            raise Exception(f"Fyers API ping failed: {profile_response}")

        return jsonify({
            "status": "ok",
            "token_status": "active",
            "fyers_status": "reachable",
            "profile": profile_response.get("data", {})
        }), 200

    except Exception as e:
        logger.exception("Health check failed: %s",
                         e,
                         extra={"request_id": get_request_id()})
        return jsonify({"status": "error", "message": str(e)}), 500


@webhook_bp.route("/refresh-token", methods=["POST"])
def refresh_token():
    """Refresh the current Fyers access token.

    **Request**: No payload is required.

    **Returns**: ``200`` with ``{"success": True}`` if the token was refreshed
    successfully, ``401`` if refreshing failed, or ``500`` for unexpected
    errors.
    """
    try:
        token = refresh_access_token()
        if token:
            return jsonify({
                "success": True,
                "message": "Token refreshed"
            }), 200
        logger.error("Token refresh returned None",
                     extra={"request_id": get_request_id()})
        return jsonify({
            "success": False,
            "message": "Failed to refresh token"
        }), 401
    except Exception as e:
        logger.exception("Error refreshing token: %s",
                         e,
                         extra={"request_id": get_request_id()})
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500


@webhook_bp.route("/generate-token", methods=["POST"])
def generate_token():
    """Generate a new Fyers access token using the stored auth code.

    **Request**: No payload is required.

    **Returns**: ``200`` on success with ``{"success": True}``, ``401`` if token
    generation fails, or ``500`` for any server error.
    """
    try:
        token = generate_access_token()
        if token:
            return jsonify({
                "success": True,
                "message": "Token refreshed"
            }), 200
        logger.error("Token refresh returned None",
                     extra={"request_id": get_request_id()})
        return jsonify({
            "success": False,
            "message": "Failed to refresh token"
        }), 401
    except Exception as e:
        logger.exception("Error refreshing token: %s",
                         e,
                         extra={"request_id": get_request_id()})
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500


@webhook_bp.route("/auth-url", methods=["GET"])
def get_auth_url():
    """Return the URL that users must visit to authorize the application.

    **Request**: none.

    **Returns**: ``200`` with ``{"auth_url": <url>}`` if successful or ``500``
    if the URL could not be generated.
    """
    try:
        url = get_auth_code_url()
        if not url:
            logger.error("Failed to generate auth URL",
                         extra={"request_id": get_request_id()})
            return jsonify({
                "success": False,
                "message": "Failed to generate auth URL"
            }), 500
        return jsonify({"success": True, "auth_url": url}), 200
    except Exception as e:
        logger.exception("Error getting auth URL: %s",
                         e,
                         extra={"request_id": get_request_id()})
        return jsonify({
            "success": False,
            "message": "Internal server error"
        }), 500


@webhook_bp.route("/webhook", methods=["POST"])
async def webhook():
    """Handle TradingView alerts to place option orders via Fyers.

    **Request JSON** should contain at least the following fields::

        {
            "token": "<secret>",
            "symbol": "<underlying>",
            "strikeprice": <int>,
            "optionType": "CE"|"PE",
            "expiry": "WEEKLY"|"MONTHLY",
            "action": "BUY"|"SELL",
            "qty": <int>,
            "sl": <float>,
            "tp": <float>,
            "productType": "BO" | "CO" | ...
        }

    ``sl``, ``tp`` and ``productType`` are optional. If ``sl`` and ``tp`` are not
    supplied they will be derived from the latest traded price.

    **Responses**:
    - ``200`` when the order is placed successfully with details in the
      response body.
    - ``400`` for validation errors.
    - ``401`` if the secret token is invalid.
    - ``403`` if the symbol cannot be resolved.
    - ``500`` for any unexpected failure.
    """
    try:
        data = request.get_json()

        masked_data = dict(data or {})
        if masked_data.get("token"):
            masked_data["token"] = "***"
        logger.info("Incoming payload: %s",
                    masked_data,
                    extra={"request_id": get_request_id()})

        if not data:
            return jsonify({
                "success": False,
                "error": "Empty or invalid JSON",
                "data": data
            }), 400

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
            logger.error(
                "Missing fields - symbol: %s, action: %s, strike: %s, option_type: %s, expiry: %s",
                symbol,
                action,
                strikeprice,
                optionType,
                expiry,
                extra={"request_id": get_request_id()},
            )
            return jsonify({
                "success": False,
                "error": "Missing required fields"
            }), 400

        if token != os.getenv("WEBHOOK_SECRET_TOKEN"):
            logger.error(
                "Unauthorized access from IP: %s",
                request.remote_addr,
                extra={"request_id": get_request_id()},
            )
            return jsonify({"success": False, "error": "Unauthorized"}), 401

        start = time.time()
        logger.info(
            "Resolving symbol for %s %s%s %s",
            symbol,
            strikeprice,
            optionType,
            expiry,
            extra={"request_id": get_request_id()},
        )
        fyers_symbol = get_symbol_from_csv(symbol, strikeprice, optionType,
                                           expiry)
        logger.info("getSymbol took %.2fs",
                    time.time() - start,
                    extra={"request_id": get_request_id()})

        if not fyers_symbol:
            logger.error("Could not resolve symbol",
                         extra={"request_id": get_request_id()})
            return jsonify({
                "success": False,
                "error": "Could not resolve symbol"
            }), 403

        ltp = None
        try:
            start = time.time()
            fyers = get_fyers()
            logger.info("getFyers took %.2fs",
                        time.time() - start,
                        extra={"request_id": get_request_id()})
            if not fyers:
                return jsonify({
                    "success": False,
                    "error": "Failed to initialize Fyers client"
                }), 500

            if action.upper() == "BUY" and not await has_short_position(
                    fyers_symbol, fyers):
                logger.error("No short position open for %s",
                             fyers_symbol,
                             extra={"request_id": get_request_id()})
                return jsonify({
                    "success": False,
                    "error": "No short position to cover"
                }), 400

            start = time.time()
            logger.info("Fetching LTP for %s",
                        fyers_symbol,
                        extra={"request_id": get_request_id()})
            ltp = await get_ltp(fyers_symbol, fyers)
            logger.info("getLTPs took %.2fs",
                        time.time() - start,
                        extra={"request_id": get_request_id()})
            if isinstance(ltp, (int, float)):
                sl = round(ltp * 0.15)
                tp = round(ltp * 0.25)
            else:
                logger.warning(
                    "LTP invalid for %s: %s",
                    fyers_symbol,
                    ltp,
                    extra={"request_id": get_request_id()},
                )
                sl = None
                tp = None
        except Exception as e:
            logger.exception(
                "Failed to get LTP for symbol %s: %s",
                symbol,
                e,
                extra={"request_id": get_request_id()},
            )
            ltp = None
            sl = None
            tp = None

        qty, sl, tp, productType = _validate_order_params(
            fyers_symbol, qty, sl, tp, productType)
        try:
            fyers = get_fyers()
            logger.info(
                "Placing order for %s qty=%s action=%s sl=%s tp=%s productType=%s",
                fyers_symbol,
                qty,
                action,
                sl,
                tp,
                productType,
                extra={"request_id": get_request_id()},
            )
            order_response = await place_order(
                fyers_symbol, qty, action, sl, tp, productType, fyers)
            if order_response.get("s") != "ok":
                logger.error(
                    "Fyers order failed: %s",
                    order_response,
                    extra={"request_id": get_request_id(), "event": "order_failed"},
                )
                send_notification(
                    f"Order failed for {fyers_symbol}",
                    event="order_failed",
                    response=order_response,
                )
                return (
                    jsonify({
                        "code": -1,
                        "message":
                        f"Fyers order failed: {order_response.get('message', 'Unknown error')}",
                        "details": order_response,
                    }),
                    500,
                )
        except Exception as e:
            logger.exception(
                "Exception occured while placing order: %s",
                e,
                extra={"request_id": get_request_id(), "event": "order_failed"},
            )
            send_notification(
                f"Order exception for {fyers_symbol}",
                event="order_failed",
                error=str(e),
            )
            return (
                jsonify({
                    "code": -1,
                    "message": f"Exception while placing order: {str(e)}",
                }),
                500,
            )

        logger.info("Order placement complete",
                    extra={"request_id": get_request_id()})
        return (
            jsonify({
                "success": True,
                "message": "order placed",
                "order_response": order_response,
            }),
            200,
        )

    except Exception as e:
        logger.exception("Unhandled error in webhook: %s",
                         e,
                         extra={"request_id": get_request_id(), "event": "order_failed"})
        send_notification(
            "Unhandled webhook error",
            event="order_failed",
            error=str(e),
        )
        return jsonify({"success": False, "error": str(e)}), 500
