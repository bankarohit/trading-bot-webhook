# ------------------ app/utils.py ------------------
from datetime import datetime
from app.auth import get_access_token
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import re, uuid, time
import threading
import traceback

lock = threading.Lock()

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

_gspread_client = None

def get_sheet_client():
    global _gspread_client
    if _gspread_client is None:
        print("[DEBUG] Initializing gspread client")
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        _gspread_client = gspread.authorize(creds)
    return _gspread_client

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
        traceback.print_exc()
        print(f"[ERROR] Exception in get_symbol_from_csv: {str(e)}")
        return None


def log_trade_to_sheet(symbol, action, qty, ltp, sl = 30, tp = 60):
    if not qty:
        if symbol.startswith("NSE:NIFTY"):
            qty = 75 # Lot size of nifty is 75
        elif symbol.startswith("NSE:BANKNIFTY"):
            qty = 30 # Lot size of bankNifty is 30
        else:
            qty = 1 # Default size for other symbols
    try:
        client = get_sheet_client()
        sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")
        unique_id = str(uuid.uuid4())
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [unique_id, now, symbol, action, qty, ltp, sl, tp, "OPEN", "", "", ""]
        sheet.append_row(row)
        return True
    except Exception as e:
        traceback.print_exc()
        print(f"[ERROR] Failed to log trade to Google Sheet: {str(e)}")
        return False
    
def get_open_trades_from_sheet():
    for attempt in range(3):
        try:
            client = get_sheet_client()
            sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")
            rows = sheet.get_all_values()
            return [row for row in rows[1:] if row[8] == "OPEN"]  # assuming row[8] is status now
        except Exception as e:
            traceback.print_exc()
            print(f"[RETRY {attempt+1}] Failed to fetch open trades: {e}")
            time.sleep(2)
    return []

def update_trade_status_in_sheet(trade, status, exit_price):
    for attempt in range(3):
        try:
            with lock:
                client = get_sheet_client()
                sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")
                all_rows = sheet.get_all_values()
                for idx, row in enumerate(all_rows):
                    if row[0] == trade[0]:
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sheet.update_cell(idx + 1, 9, status)  # status
                        sheet.update_cell(idx + 1, 10, exit_price)  # exit price
                        sheet.update_cell(idx + 1, 11, now)  # exit time
                        sheet.update_cell(idx + 1, 12, "AUTO")  # reason
                        return
        except Exception as e:
            traceback.print_exc()
            print(f"[RETRY {attempt+1}] Failed to update trade status: {e}")
            time.sleep(2)