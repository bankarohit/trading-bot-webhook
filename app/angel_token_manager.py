"""Utilities for managing Angel One SmartAPI tokens."""

import os
import json
import logging
import base64
from google.cloud import storage
import requests

logger = logging.getLogger(__name__)

TOKENS_FILE = "angel_tokens.json"
CREDS_FILE = "/secrets/service_account.json"


def _get_storage_client():
    """Return a Google Cloud Storage client using a service account if available."""
    cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", CREDS_FILE)
    if os.path.exists(cred_path):
        return storage.Client.from_service_account_json(cred_path)
    return storage.Client()


def _encrypt(data: bytes) -> str:
    try:
        return base64.b64encode(data).decode()
    except Exception as exc:
        logger.exception("Encryption failed: %s", exc)
        raise


def _decrypt(data: str) -> bytes:
    try:
        return base64.b64decode(data)
    except Exception as exc:
        logger.exception("Decryption failed: %s", exc)
        raise


def load_tokens(tokens_file: str = TOKENS_FILE):
    """Load tokens from GCS if present, otherwise from local file."""
    try:
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(os.getenv("GCS_BUCKET_NAME"))
        blob = bucket.blob(os.getenv("GCS_TOKENS_FILE", f"tokens/{tokens_file}"))
        if blob.exists():
            blob.download_to_filename(tokens_file)
            with open(tokens_file, "r") as fh:
                raw = fh.read()
            try:
                plaintext = _decrypt(raw)
            except Exception:
                logger.warning("Tokens file not encoded; loading plaintext")
                plaintext = raw.encode()
            return json.loads(plaintext.decode())
    except Exception as exc:
        logger.exception("GCS load failed: %s", exc)
    try:
        if os.path.exists(tokens_file):
            with open(tokens_file, "r") as fh:
                raw = fh.read()
            try:
                plaintext = _decrypt(raw)
            except Exception:
                logger.warning("Tokens file not encoded; loading plaintext")
                plaintext = raw.encode()
            return json.loads(plaintext.decode())
    except Exception as exc:
        logger.exception("Local load failed: %s", exc)
    return {}


def save_tokens(tokens: dict, tokens_file: str = TOKENS_FILE):
    """Save tokens locally and to GCS."""
    plaintext = json.dumps(tokens).encode()
    encrypted = _encrypt(plaintext)
    try:
        with open(tokens_file, "w") as fh:
            fh.write(encrypted)
        storage_client = _get_storage_client()
        bucket = storage_client.bucket(os.getenv("GCS_BUCKET_NAME"))
        blob = bucket.blob(os.getenv("GCS_TOKENS_FILE", f"tokens/{tokens_file}"))
        blob.upload_from_filename(tokens_file)
    except Exception as exc:
        logger.exception("GCS save failed: %s", exc)


def get_login_url() -> str:
    """Return the login URL for manual SmartAPI authentication."""
    api_key = os.getenv("ANGEL_API_KEY")
    redirect = os.getenv("ANGEL_REDIRECT_URI")
    state = os.getenv("ANGEL_STATE", "state")
    return (
        "https://smartapi.angelbroking.com/publisher-login?"
        f"api_key={api_key}&redirect_uri={redirect}&response_type=code&state={state}"
    )


def generate_tokens(auth_code: str):
    """Exchange an auth code for access and refresh tokens."""
    api_key = os.getenv("ANGEL_API_KEY")
    client_code = os.getenv("ANGEL_CLIENT_CODE")
    password = os.getenv("ANGEL_PASSWORD")
    url = (
        "https://apiconnect.angelbroking.com/rest/auth/angelbroking/jwt/v1/"
        "generateTokens"
    )
    payload = {
        "api_key": api_key,
        "clientcode": client_code,
        "password": password,
        "code": auth_code,
    }
    response = requests.post(url, json=payload).json()
    if response.get("status") in (True, "success"):
        data = response.get("data", response)
        tokens = {
            "access_token": data.get("access_token"),
            "refresh_token": data.get("refresh_token"),
        }
        save_tokens(tokens)
        return tokens
    raise Exception(f"Token generation failed: {response}")


def refresh_tokens():
    """Refresh and persist the access token using the stored refresh token."""
    tokens = load_tokens()
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise Exception("Missing refresh token")
    api_key = os.getenv("ANGEL_API_KEY")
    url = (
        "https://apiconnect.angelbroking.com/rest/auth/angelbroking/jwt/v1/"
        "generateTokens"
    )
    payload = {"api_key": api_key, "refresh_token": refresh_token}
    response = requests.post(url, json=payload).json()
    if response.get("status") in (True, "success"):
        data = response.get("data", response)
        tokens.update(
            {
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token", refresh_token),
            }
        )
        save_tokens(tokens)
        return tokens
    raise Exception(f"Token refresh failed: {response}")

