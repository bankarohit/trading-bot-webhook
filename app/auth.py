# ------------------ app/auth.py ------------------
from app.token_manager import get_token_manager

_token_manager = get_token_manager()

def get_fyers():
    return _token_manager.get_fyers_client()

def get_auth_code_url():
    return _token_manager.get_auth_code_url()

def get_access_token():
    token = _token_manager.get_access_token()
    if token:
        return token
    else:
        print("[ERROR] Failed to get access token")
        return None

def refresh_access_token():
    try:
        token = _token_manager.refresh_token()
        if token:
            return token
        print("[ERROR] Token refresh returned None")
        return None
    except Exception as e:
        print(f"[FATAL] Error refreshing token: {str(e)}")
        return None
