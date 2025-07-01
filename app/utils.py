"""Utility helpers for working with the Fyers symbol master."""

from datetime import datetime
import os
import pandas as pd
import re
import logging
import threading
import ssl
import certifi
import urllib.request
import io

logger = logging.getLogger(__name__)

symbol_master_url = "https://public.fyers.in/sym_details/NSE_FO.csv"
symbol_master_columns = [
    "fytoken", "symbol_details", "exchange_instrument_type", "lot_size",
    "tick_size", "isin", "trading_session", "last_update", "expiry_date",
    "symbol_ticker", "exchange", "segment", "scrip_code",
    "underlying_symbol", "underlying_scrip_code", "strike_price",
    "option_type", "underlying_fytoken", "reserved_1", "reserved_2", "reserved_3"
]

_symbol_cache = None
_symbol_lock = threading.Lock()

def load_symbol_master():
    """Download the Fyers symbol master CSV and cache it.

    The CSV pointed to by :data:`symbol_master_url` is loaded into a
    :class:`pandas.DataFrame` stored in :data:`_symbol_cache`. Any errors are
    logged and an empty DataFrame is cached.
    """
    global _symbol_cache
    if _symbol_cache is not None:
        return
    with _symbol_lock:
        if _symbol_cache is not None:
            return
        try:
            context = ssl.create_default_context(cafile=certifi.where())
            with urllib.request.urlopen(symbol_master_url,
                                       context=context) as resp:
                data = resp.read()
            _symbol_cache = pd.read_csv(
                io.BytesIO(data),
                header=None,
                names=symbol_master_columns,
            )
            logger.debug("Loaded symbol master into memory")
        except Exception as e:
            logger.error(f"Failed to load symbol master: {e}")
            _symbol_cache = pd.DataFrame(columns=symbol_master_columns)

def get_symbol_from_csv(symbol, strike_price, option_type, expiry_type):
    """Return the Fyers ticker symbol from the cached symbol master.

    Parameters:
        symbol (str): The underlying symbol, e.g. ``NIFTY``.
        strike_price (float | int | str): Option strike price.
        option_type (str): ``CE`` or ``PE``.
        expiry_type (str): ``WEEKLY`` or ``MONTHLY``.

    Returns:
        str | None: Matching ticker symbol or ``None`` if not found.
    """
    global _symbol_cache
    try:
        logger.debug(f"Requested: symbol={symbol.upper()}, strike_price={round(float(strike_price))}, option_type={option_type.upper()}, expiry_type={expiry_type}")

        if _symbol_cache is None:
            load_symbol_master()

        df = _symbol_cache.copy()
        df = df[df['underlying_symbol'].str.upper() == symbol.upper()]
        df = df[df['strike_price'].astype(float).round() == round(float(strike_price))]
        df = df[df['option_type'].str.upper() == option_type.upper()]
        today = pd.Timestamp.now().normalize()
        df['expiry_date'] = pd.to_datetime(df['expiry_date'], unit='s', errors='coerce')
        df = df.dropna(subset=['expiry_date'])
        df = df[df['expiry_date'].dt.normalize() >= today]

        expiry = None
        if expiry_type.upper() == "WEEKLY":
            df = df.sort_values('expiry_date')
            expiry = df.iloc[0]['expiry_date'] if not df.empty else None
            logger.debug(f"Chosen weekly expiry: {expiry}")
        elif expiry_type.upper() == "MONTHLY":
            monthly_pattern = re.compile(rf"{symbol.upper()}\d{{2}}[A-Z]{{3}}")
            df = df[df['symbol_ticker'].str.contains(monthly_pattern)]
            df = df.sort_values('expiry_date')
            expiry = df.iloc[0]['expiry_date'] if not df.empty else None
            logger.debug(f"Chosen monthly expiry: {expiry}")
        else:
            return None

        result = df[df['expiry_date'] == expiry]
        fyersTickerSymbol = result.iloc[0]['symbol_ticker'] if not result.empty else None
        logger.debug(f"FyersTickerSymbol: {fyersTickerSymbol}")
        return fyersTickerSymbol

    except Exception as e:
        logger.exception(
            f"Exception in get_symbol_from_csv for symbol={symbol}, strike_price={strike_price}, option_type={option_type}, expiry_type={expiry_type}: {str(e)}"
        )
        return None
    
