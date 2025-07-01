"""Utility wrappers around the Fyers trading API used by webhook routes.

This module centralizes common interactions with the Fyers API such as
validating order parameters, retrieving instrument details and placing
orders. The helpers are intentionally thin so they can be easily mocked in
tests.
"""

import logging
import app.utils as utils

if utils._symbol_cache is None:
    utils.load_symbol_master()

logger = logging.getLogger(__name__)

valid_product_types = {"INTRADAY", "CNC", "DELIVERY", "BO", "CO"}

def _validate_order_params(symbol, qty, sl, tp, productType):
    """Sanitise and fill default order parameters.

    Parameters
    ----------
    symbol : str
        Fyers instrument ticker (e.g. ``"NSE:SBIN-EQ"``).
    qty : int or ``None``
        Quantity to trade. If ``None`` a sensible default is derived using
        :func:`_get_default_qty`.
    sl : float or str or ``None``
        Desired stop loss in absolute points. Values ``<=0`` are replaced with
        the default ``10.0``.
    tp : float or str or ``None``
        Desired take profit in absolute points. Values ``<=0`` fall back to the
        default ``20.0``.
    productType : str
        Product type supported by Fyers (e.g. ``"CNC"``). Invalid values are
        logged and replaced with ``"BO"``.

    Returns
    -------
    tuple
        Normalised ``(qty, sl, tp, productType)`` tuple ready for the API call.
    """

    if not qty:
        qty = _get_default_qty(symbol)
    sl = float(sl) if sl and float(sl) > 0 else 10.0
    tp = float(tp) if tp and float(tp) > 0 else 20.0
    if productType not in valid_product_types:
        logger.warning(
            f"Invalid productType '{productType}' for symbol {symbol}, defaulting to 'BO'"
        )
        productType = "BO"
    return qty, sl, tp, productType

def _get_default_qty(symbol):
    """Return the lot size for a symbol from the loaded symbol master.

    Parameters
    ----------
    symbol : str
        Instrument ticker for which the default lot size is requested.

    Returns
    -------
    int
        Lot size for the symbol if available; otherwise ``1``. Any errors while
        reading the value are logged and ``1`` is returned.
    """

    if utils._symbol_cache is None:
        utils.load_symbol_master()

    match = utils._symbol_cache[utils._symbol_cache['symbol_ticker'] == symbol]
    if len(match) > 0:
        try:
            return int(float(match.iloc[0]['lot_size']))
        except Exception as e:
            logger.warning(f"Invalid lot size for symbol {symbol}: {e}")
            return 1
    else:
        logger.warning(f"No lot size found for {symbol} in symbol master, defaulting to 1")
        return 1

def get_ltp(symbol, fyersModelInstance):
    """Fetch the latest traded price for a symbol from Fyers.

    Parameters
    ----------
    symbol : str
        Instrument ticker to query.
    fyersModelInstance : object
        Instance of :class:`fyers_apiv3.fyersModel.FyersModel` or a compatible
        mock with ``quotes`` method.

    Returns
    -------
    float or None or dict
        The last traded price as a ``float`` if available. ``None`` is returned
        when the symbol is not found or no price data is available. If an
        exception occurs, a dictionary of the form ``{"code": -1, "message" : str(e)}``
        is returned.
    """

    try:
        response = fyersModelInstance.quotes({"symbols": symbol})
        if response.get("s") == "ok" and response.get("d") and len(response["d"]) > 0:
            return response.get("d", [{}])[0].get("v", {}).get("lp")
        else:
            logger.warning(f"No valid price data for symbol {symbol}")
            logger.debug(f"Response from Fyers quotes API: {response}")
            return None
    except Exception as e:
        logger.exception(f"Exception in get_ltp for {symbol}: {str(e)}")
        return {"code": -1, "message": str(e)}


def has_short_position(symbol, fyersModelInstance):
    """Return ``True`` if there is an open short position for ``symbol``.

    The function calls ``fyersModelInstance.positions()`` and inspects the
    returned ``netPositions`` list. A position is considered *short* when the
    ``netQty`` is negative or the ``side`` field equals ``-1``.

    Parameters
    ----------
    symbol : str
        Fyers instrument ticker to check.
    fyersModelInstance : object
        Instance of :class:`fyers_apiv3.fyersModel.FyersModel` or a compatible
        mock with ``positions`` method.

    Returns
    -------
    bool
        ``True`` if a matching short position exists, otherwise ``False``. If an
        exception occurs, ``False`` is returned and the error is logged.
    """

    try:
        response = fyersModelInstance.positions()
        logger.debug(f"Positions response: {response}")
        if response.get("s") != "ok":
            logger.warning(f"Positions API returned error: {response}")
            return False

        for pos in response.get("netPositions", []):
            if pos.get("symbol") == symbol:
                try:
                    net_qty = float(pos.get("netQty", 0))
                except Exception:
                    net_qty = 0
                side = pos.get("side")
                if net_qty < 0 or side == -1:
                    return True
        return False
    except Exception as e:
        logger.exception(f"Exception in has_short_position for {symbol}: {str(e)}")
        return False

def place_order(symbol, qty, action, sl, tp, productType, fyersModelInstance):
    """Place a market order with Fyers after validating parameters.

    Parameters
    ----------
    symbol : str
        Instrument ticker to trade.
    qty : int or ``None``
        Quantity for the order. ``None`` triggers lookup of the default lot
        size.
    action : str
        Either ``"BUY"`` or ``"SELL"`` (case-insensitive).
    sl : float or ``None``
        Stop loss value in points. ``None`` or values ``<=0`` default to
        ``10.0``.
    tp : float or ``None``
        Take profit value in points. ``None`` or values ``<=0`` default to
        ``20.0``.
    productType : str
        One of ``valid_product_types``. Invalid values fall back to ``"BO"``.
    fyersModelInstance : object
        Fyers client instance or mock providing ``place_order`` method.

    Returns
    -------
    dict
        The raw response from ``fyersModelInstance.place_order``. In case of an
        exception a dictionary ``{"code": -1, "message": str(e)}`` is returned.
    """

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
        logger.debug(f"Placing order with data: {order_data}")
        response = fyersModelInstance.place_order(order_data)
        logger.debug(f"Response from Fyers order API: {response}")
        return response
    except Exception as e:
        logger.exception(f"Exception while placing order for {symbol}: {str(e)}")
        return {"code": -1, "message": str(e)}
