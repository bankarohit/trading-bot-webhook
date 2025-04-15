# ------------------ app/utils.py ------------------
from datetime import datetime
import math
import requests
from app.auth import get_access_token
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

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
        print(f"[DEBUG] Loaded symbol file with {len(df)} rows")

        df = df[df['underlying_symbol'].str.upper() == symbol.upper()]
        print(f"[DEBUG] Rows after symbol match: {len(df)}")

        df = df[df['strike_price'].astype(float).round() == round(float(strike_price))]
        print(f"[DEBUG] Rows after strike match: {len(df)}")
        print("[DEBUG] DataFrame after strike match:")
        print(df[['underlying_symbol','symbol_ticker', 'strike_price', 'option_type', 'expiry_date']].to_string(index=False))


        df = df[df['option_type'].str.upper() == option_type.upper()]
        print(f"[DEBUG] Rows after option type match: {len(df)}")
        print("[DEBUG] DataFrame after strike match:")
        print(df[['underlying_symbol','symbol_ticker', 'strike_price', 'option_type', 'expiry_date']].to_string(index=False))


        today = pd.Timestamp.now().normalize()

        print(f"[DEBUG] Today's date: {today}")
        df['expiry_date'] = pd.to_datetime(df['expiry_date'], unit='s', errors='coerce')
        df = df.dropna(subset=['expiry_date'])
        df = df[df['expiry_date'].dt.normalize() >= today]
        print(f"[DEBUG] Rows after expiry_date >= today: {len(df)}")

        expiry = None
        if expiry_type.upper() == "WEEKLY":
            df = df.sort_values('expiry_date')
            expiry = df.iloc[0]['expiry_date'] if not df.empty else None
            print(f"[DEBUG] Chosen weekly expiry: {expiry}")

        elif expiry_type.upper() == "MONTHLY":
            df['month'] = df['expiry_date'].dt.to_period('M')
            df = df.sort_values(['month', 'expiry_date'])
            df = df.groupby('month').tail(1)
            df = df.sort_values('expiry_date')
            expiry = df.iloc[0]['expiry_date'] if not df.empty else None
            print(f"[DEBUG] Chosen monthly expiry: {expiry}")
        else:
            print(f"[ERROR] Invalid expiry_type: {expiry_type}")
            return None

        result = df[df['expiry_date'] == expiry]
        print(f"[DEBUG] Final match count: {len(result)}")
        return result.iloc[0]['symbol_ticker'] if not result.empty else None

    except Exception as e:
        print("[ERROR] Exception in get_symbol_from_csv:", e)
        return None

def get_option_symbol(index_name, strike_price, option_type):
    today = datetime.now()
    expiry_day = today.replace(day=today.day + (3 - today.weekday()) % 7)
    expiry_str = expiry_day.strftime("%y%b").upper()
    return f"NSE:{index_name}{expiry_str}{strike_price}{option_type.upper()}"

def get_spot_price(index_symbol, token):
    url = f"https://api.fyers.in/data-rest/v2/quotes/{index_symbol}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers).json()
    return response.get("d", {}).get("v", {}).get("lp")

def get_nearest_strike(price, step=50):
    return int(round(price / step) * step)

def log_trade_to_sheet(symbol, action, qty, ltp, sl, tp):
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        row = [now, symbol, action, qty, ltp, sl, tp, "OPEN", "", "", ""]
        sheet.append_row(row)
    except Exception as e:
        print(f"[ERROR] Failed to log trade to Google Sheet: {str(e)}")
