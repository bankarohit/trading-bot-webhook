# ------------------ app/utils.py ------------------
from datetime import datetime
import math
import requests
from app.auth import get_access_token
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/secrets/service_account.json"

symbol_master_url = "https://public.fyers.in/sym_details/NSE_FO.csv"

symbol_master_columns = [
    "fytoken", "symbol_details", "exchange_instrument_type", "lot_size",
    "tick_size", "isin", "trading_session", "last_update", "expiry_date",
    "symbol_ticker", "exchange", "segment", "scrip_code",
    "underlying_symbol", "underlying_scrip_code", "strike_price",
    "option_type", "underlying_fytoken", "reserved_1", "reserved_2", "reserved_3"
]

def get_symbol_from_csv(symbol, strike_price, option_type, expiry_type):
    try:
        print(f"[DEBUG] Requested: symbol={symbol.upper()}, strike_price={round(float(strike_price))}, option_type={option_type.upper()}, expiry_type={expiry_type}")
        df = pd.read_csv(symbol_master_url, header=None, names=symbol_master_columns)
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
            print(f"[DEBUG] Chosen weekly expiry: {expiry}")
        elif expiry_type.upper() == "MONTHLY":
            # Match symbols like NIFTY25APR, BANKNIFTY26JAN etc.
            monthly_pattern = re.compile(rf"{symbol.upper()}\d{{2}}[A-Z]{{3}}")
            df = df[df['symbol_ticker'].str.contains(monthly_pattern)]
            df = df.sort_values('expiry_date')
            expiry = df.iloc[0]['expiry_date'] if not df.empty else None
            print(f"[DEBUG] Chosen monthly expiry: {expiry}")
        else:
            return None
        result = df[df['expiry_date'] == expiry]
        fyersTickerSymbol = result.iloc[0]['symbol_ticker'] if not result.empty else None
        print(f"FyersTickerSYmbol: {fyersTickerSymbol}")
        return fyersTickerSymbol
    except Exception as e:
        print(f"[ERROR] Exception in get_symbol_from_csv: {str(e)}")
        return None


def log_trade_to_sheet(symbol, action, qty, ltp, sl, tp):
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [now, symbol, action, qty, ltp, sl, tp, "OPEN", "", "", ""]
        sheet.append_row(row)
        return True
    except Exception as e:
        print(f"[ERROR] Failed to log trade to Google Sheet: {str(e)}")
        return False