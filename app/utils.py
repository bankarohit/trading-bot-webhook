# ------------------ app/utils.py ------------------
from datetime import datetime
import math
import requests
from app.auth import get_access_token


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