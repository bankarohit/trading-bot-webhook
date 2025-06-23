import logging
from app.auth import get_fyers
import app.utils as utils
from app.logging_config import request_id_extra

if utils._symbol_cache is None:
    utils.load_symbol_master()

logger = logging.getLogger(__name__)

valid_product_types = {"INTRADAY", "CNC", "DELIVERY", "BO", "CO"}

def _validate_order_params(symbol, qty, sl, tp, productType):
    if not qty:
        qty = _get_default_qty(symbol)
    sl = float(sl) if sl and float(sl) > 0 else 10.0
    tp = float(tp) if tp and float(tp) > 0 else 20.0
    if productType not in valid_product_types:
        logger.warning(
            f"Invalid productType '{productType}', defaulting to 'BO'",
            extra=request_id_extra(),
        )
        productType = "BO"
    return qty, sl, tp, productType

def _get_default_qty(symbol):
    if utils._symbol_cache is None:
        utils.load_symbol_master()

    match = utils._symbol_cache[utils._symbol_cache['symbol_ticker'] == symbol]
    if len(match) > 0:
        try:
            return int(float(match.iloc[0]['lot_size']))
        except Exception as e:
            logger.warning(
                f"Invalid lot size for symbol {symbol}: {e}", extra=request_id_extra()
            )
            return 1
    else:
        logger.warning(
            f"No lot size found for {symbol} in symbol master, defaulting to 1",
            extra=request_id_extra(),
        )
        return 1

def get_ltp(symbol, fyersModelInstance):
    try:
        response = fyersModelInstance.quotes({"symbols": symbol})
        if response.get("s") == "ok" and response.get("d") and len(response["d"]) > 0:
            return response.get("d", [{}])[0].get("v", {}).get("lp")
        else:
            logger.warning(
                f"No valid price data for symbol {symbol}", extra=request_id_extra()
            )
            logger.debug(
                f"Response from Fyers quotes API: {response}", extra=request_id_extra()
            )
            return None
    except Exception as e:
        logger.error(f"Exception in get_ltp: {str(e)}", extra=request_id_extra())
        return {"code": -1, "message": str(e)}

def place_order(symbol, qty, action, sl, tp, productType, fyersModelInstance):
    qty, sl, tp, productType = _validate_order_params(symbol, qty, sl, tp, productType)
    order_data = {
        "symbol": symbol,
        "qty": qty,
        "type": 2,  # Market order
        "side": 1 if action.upper() == "BUY" else -1,
        "productType": productType,
        "limitPrice": 0,
        "stopPrice": 0,
        "validity": "DAY",
        "disclosedQty": 0,
        "offlineOrder": False,
        "stopLoss": sl,
        "takeProfit": tp
    }

    try:
        logger.debug(f"Placing order with data: {order_data}", extra=request_id_extra())
        response = fyersModelInstance.place_order(order_data)
        logger.debug(
            f"Response from Fyers order API: {response}", extra=request_id_extra()
        )
        return response
    except Exception as e:
        logger.error(
            f"Exception while placing order: {str(e)}", extra=request_id_extra()
        )
        return {"code": -1, "message": str(e)}
