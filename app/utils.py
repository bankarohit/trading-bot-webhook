from datetime import datetime
import os
import pandas as pd
import re
import time
import gspread
import logging
from oauth2client.service_account import ServiceAccountCredentials
from google.auth.exceptions import TransportError
import ssl
import certifi
import urllib.request
import uuid
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

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/secrets/service_account.json"


_symbol_cache = None
_gsheet_client = None

def get_gsheet_client():
    global _gsheet_client
    if _gsheet_client is None:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        _gsheet_client = gspread.authorize(creds)
    return _gsheet_client

def load_symbol_master():
    global _symbol_cache
    try:
        context = ssl.create_default_context(cafile=certifi.where())
        with urllib.request.urlopen(symbol_master_url, context=context) as resp:
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

def log_trade_to_sheet(symbol, action, qty, ltp, sl, tp, sheet_name="Trades", retries=3):
    """
    Logs a trade entry to Google Sheets with a unique UUID for tracking.
    
    Returns:
    - True if logged successfully.
    - False if logging fails.
    """
    trade_id = str(uuid.uuid4())
    try:
        client = get_gsheet_client()
        sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet(sheet_name)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        row = [trade_id, now, symbol, action, qty, ltp, sl, tp, "OPEN", "", "", ""]

        for attempt in range(retries):
            try:
                sheet.append_row(row)
                logger.info(f"Trade logged successfully | ID: {trade_id} | Symbol: {symbol} | Action: {action} | Qty: {qty}")
                return True
            except (gspread.exceptions.APIError, TransportError) as retryable:
                logger.warning(f"Retry {attempt+1}/{retries} - Failed to log trade ID {trade_id}: {retryable}")
                time.sleep(2 ** attempt)

        logger.error(f"Max retries reached. Could not log trade ID {trade_id}.")
        return False

    except Exception as e:
        logger.exception(
            f"Failed to log trade to Google Sheet for symbol {symbol} (ID: {trade_id}): {str(e)}"
        )
        return False
    
def get_open_trades_from_sheet(_client, sheet_name="Trades"):
    try:
        sheet = _client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet(sheet_name)
        rows = sheet.get_all_values()
        open_trades = [row for row in rows[1:] if len(row) >= 9 and row[8] == "OPEN"]
        logger.debug(f"Fetched {len(open_trades)} open trades")
        return open_trades
    except Exception as e:
        logger.exception(
            f"Failed to fetch open trades from sheet {sheet_name}: {str(e)}"
        )
        return []

def update_trade_status_in_sheet(_client, trade_id, status, exit_price, reason="", sheet_name="Trades"):
    try:
        sheet = _client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet(sheet_name)
        rows = sheet.get_all_values()
        for idx, row in enumerate(rows[1:], start=2):  # skip header row
            if row[0] == trade_id:  # assume unique timestamp as ID
                sheet.update_cell(idx, 9, status)  # column I (9th) - status
                sheet.update_cell(idx, 11, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))  # column K (11th) - exit time  # column K (11th) - reason  # column I (9th) - status
                sheet.update_cell(idx, 10, str(exit_price))  # column J (10th) - exit price
                sheet.update_cell(idx, 12, reason)  # column L (12th) - reason  # column J (10th) - exit price
                logger.debug(f"Updated trade {trade_id} with status={status}, exit_price={exit_price}")
                return True
        logger.warning(f"Trade ID {trade_id} not found for update.")
        return False
    except Exception as e:
        logger.exception(
            f"Failed to update trade status for {trade_id}: {str(e)}"
        )
        return False
    
