# ------------------ app/config.py ------------------
import os
from dotenv import load_dotenv

def load_env_variables():
    load_dotenv()

    required_vars = ["FYERS_APP_ID", "FYERS_SECRET_ID", "FYERS_REDIRECT_URI", "WEBHOOK_SECRET_TOKEN","GOOGLE_SHEET_ID","FYERS_PIN"]
    for var in required_vars:
        if not os.getenv(var):
            raise EnvironmentError(f"Missing required environment variable: {var}")