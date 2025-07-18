"""Utility wrappers around the Fyers trading API used by webhook routes.

This module centralizes common interactions with the Fyers API such as
validating order parameters, retrieving instrument details and placing
orders. The helpers are intentionally thin so they can be easily mocked in
tests.
"""

import logging
import inspect
import asyncio
import app.utils as utils
from app.token_manager import get_token_manager

if utils._symbol_cache is None:
    utils.load_symbol_master()

logger = logging.getLogger(__name__)

valid_product_types = {"INTRADAY", "CNC", "DELIVERY", "BO", "CO"}

# Default retry configuration for Fyers API calls
DEFAULT_RETRIES = 3
INITIAL_DELAY = 1  # seconds
BACKOFF_FACTOR = 2


async def _retry_api_call(func, *, call_desc="API call", retries=DEFAULT_RETRIES,
                          delay=INITIAL_DELAY,
                          backoff=BACKOFF_FACTOR):
    """Execute ``func`` with retries and exponential backoff.

    Parameters
    ----------
    func : callable
        Function or coroutine to execute.
    call_desc : str, optional
        Description used in log messages.
    retries : int, optional
        Number of attempts before the error is raised.
    delay : int or float, optional
        Initial delay between retries in seconds.
    backoff : int or float, optional
        Factor by which the delay increases each retry.

    Returns
    -------
    Any
        Result of ``func`` if it succeeds.

    Raises
    ------
    Exception
        Propagates the last encountered exception after exhausting retries.
    """
    for attempt in range(1, retries + 1):
        try:
            result = func()
            if inspect.iscoroutine(result):
                result = await result
            return result
        except Exception as exc:  # pragma: no cover - log and retry
            if attempt < retries:
                wait_time = delay * (backoff ** (attempt - 1))
                logger.warning(
                    f"%s attempt %s failed: %s. Retrying in %ss", call_desc,
                    attempt, exc, wait_time)
                await asyncio.sleep(wait_time)
            else:
                logger.exception(
                    f"%s failed after %s attempts: %s", call_desc, retries,
                    exc)
                raise


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
        logger.warning(
            f"No lot size found for {symbol} in symbol master, defaulting to 1"
        )
        return 1


async def get_ltp(symbol, fyersModelInstance, retries=DEFAULT_RETRIES):
    """Fetch the latest traded price for a symbol from Fyers.

    Parameters
    ----------
    symbol : str
        Instrument ticker to query.
    fyersModelInstance : object
        Instance of :class:`fyers_apiv3.fyersModel.FyersModel` or a compatible
        mock with ``quotes`` method.
    retries : int, optional
        How many times to retry the API call on failure.

    Returns
    -------
    float or None or dict
        The last traded price as a ``float`` if available. ``None`` is returned
        when the symbol is not found or no price data is available. If an
        exception occurs, a dictionary of the form ``{"code": -1, "message" : str(e)}``
        is returned.
    """

    try:
        response = await _retry_api_call(
            lambda: fyersModelInstance.quotes({"symbols": symbol}),
            call_desc="quotes",
            retries=retries,
        )
        if response.get("code") == 401:
            get_token_manager().refresh_token()
            fyersModelInstance = get_token_manager().get_fyers_client()
            response = await _retry_api_call(
                lambda: fyersModelInstance.quotes({"symbols": symbol}),
                call_desc="quotes",
                retries=retries,
            )
        if response.get("s") == "ok" and response.get("d") and len(
                response["d"]) > 0:
            return response.get("d", [{}])[0].get("v", {}).get("lp")
        else:
            logger.warning(f"No valid price data for symbol {symbol}")
            logger.debug(f"Response from Fyers quotes API: {response}")
            return None
    except Exception as e:
        logger.exception(f"Exception in get_ltp for {symbol}: {str(e)}")
        return {"code": -1, "message": str(e)}


async def has_short_position(symbol, fyersModelInstance, retries=DEFAULT_RETRIES):
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
    retries : int, optional
        How many times to retry the API call on failure.

    Returns
    -------
    bool
        ``True`` if a matching short position exists, otherwise ``False``. If an
        exception occurs, ``False`` is returned and the error is logged.
    """

    try:
        response = await _retry_api_call(
            lambda: fyersModelInstance.positions(),
            call_desc="positions",
            retries=retries,
        )
        if response.get("code") == 401:
            get_token_manager().refresh_token()
            fyersModelInstance = get_token_manager().get_fyers_client()
            response = await _retry_api_call(
                lambda: fyersModelInstance.positions(),
                call_desc="positions",
                retries=retries,
            )
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
        logger.exception(
            f"Exception in has_short_position for {symbol}: {str(e)}")
        return False


async def place_order(symbol, qty, action, sl, tp, productType,
                      fyersModelInstance, retries=DEFAULT_RETRIES):
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
    retries : int, optional
        How many times to retry the API call on failure.

    Returns
    -------
    dict
        The raw response from ``fyersModelInstance.place_order``. In case of an
        exception a dictionary ``{"code": -1, "message": str(e)}`` is returned.
    """

    qty, sl, tp, productType = _validate_order_params(symbol, qty, sl, tp,
                                                      productType)
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
        response = await _retry_api_call(
            lambda: fyersModelInstance.place_order(order_data),
            call_desc="place_order",
            retries=retries,
        )
        if response.get("code") == 401:
            get_token_manager().refresh_token()
            fyersModelInstance = get_token_manager().get_fyers_client()
            response = await _retry_api_call(
                lambda: fyersModelInstance.place_order(order_data),
                call_desc="place_order",
                retries=retries,
            )
        logger.debug(f"Response from Fyers order API: {response}")
        return response
    except Exception as e:
        logger.exception(
            f"Exception while placing order for {symbol}: {str(e)}")
        return {"code": -1, "message": str(e)}
