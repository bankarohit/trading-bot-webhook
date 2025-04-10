# ------------------ app/utils.py ------------------
from datetime import datetime
import math
import requests
from app.auth import get_access_token
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
CREDS_FILE = "/secrets/service_account.json"


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
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(os.getenv("GOOGLE_SHEET_ID")).worksheet("Trades")

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    row = [now, symbol, action, qty, ltp, sl, tp, "OPEN", "", "", ""]
    sheet.append_row(row)