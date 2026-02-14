# Trading Bot Webhook – Project Status

**Last Updated:** January 26, 2026  
**Project Type:** Flask webhook: TradingView alerts → Fyers API (options trading).

**Deployment context:** Personal use. You run the app on Cloud Run and give the webhook URL only to TradingView alerts. Only your TradingView strategies send JSON to the webhook—no public exposure.

---

## Executive Summary

Flask service that receives TradingView alerts and places option orders on Fyers. It validates the secret token, resolves NSE F&amp;O symbols, computes direction-aware SL/TP from LTP, and executes orders. Tokens are stored in GCS with auto-refresh. Idempotency avoids duplicate orders when TradingView retries.

**Status:** **Functional and suitable for personal Cloud Run use.** For extra robustness without over-engineering, see the short “Worth doing” list in `PRODUCTION_READINESS.md` (request size limit, timeouts, error sanitization). Input validation + max qty is implemented.

---

## Entry Point & Control Flow

- **Entry:** `main.py` → `load_env_variables()` → `configure_logging()` → `create_app()` → server on `0.0.0.0:8080`.
- **Per request:** `before_request` sets `request_id` + start time → route handler → `after_request` logs method, path, status, duration.

---

## Data Flow (Main Webhook)

1. `POST /webhook` receives JSON (token, symbol, strikeprice, optionType, expiry, action, qty, optional idempotency_key).
2. If `idempotency_key` present and cached response exists → return cached 200 (no Fyers call).
3. Validate secret token; reject if missing/invalid.
4. Resolve Fyers symbol from NSE_FO CSV (underlying + strike + optionType + expiry).
5. Get Fyers client (token manager; auto-refresh on expiry/401).
6. **If action = BUY:** ensure a short position exists (cover-only). Else 400.
7. Fetch LTP; compute direction-aware SL/TP from LTP; if LTP unavailable → 400.
8. Validate order params (qty, sl, tp, productType); BO/CO require valid sl/tp.
9. Place market order with retries; on success, cache response by idempotency key if provided.
10. Return success/error JSON.

---

## Current Features

- **Webhook:** Token validation, symbol resolution, LTP, direction-aware SL/TP, idempotency, cover-only BUY check, retries, notifications on failure.
- **Auth:** Token manager (GCS + local), refresh, generate; GET /auth-url, POST /generate-token, POST /refresh-token.
- **Health:** GET /readyz (token + Fyers ping).
- **Logging:** Request ID, optional Cloud + file handlers, safe setup, configurable levels.
- **Deployment:** Dockerfile, docker-compose, cloudbuild.yaml for Cloud Run.

---

## Project Structure

```
trading-bot-webhook-1/
├── app/
│   ├── __init__.py
│   ├── auth.py
│   ├── config.py
│   ├── fyers_api.py
│   ├── idempotency.py    # Idempotency key handling and store
│   ├── logging_config.py
│   ├── notifications.py
│   ├── routes.py
│   ├── token_manager.py
│   └── utils.py
├── tests/                 # 129 tests
├── docs/design.md
├── main.py
├── PRODUCTION_READINESS.md  # Context-aware; short “worth doing” list
└── README.md
```

---

## Endpoints

| Method | Path             | Purpose                    |
|--------|------------------|----------------------------|
| POST   | /webhook         | TradingView alert → order  |
| GET    | /readyz          | Health check               |
| GET    | /auth-url        | Fyers login URL            |
| POST   | /generate-token  | Auth code → token          |
| POST   | /refresh-token   | Refresh access token       |

---

## Configuration (summary)

**Required:** FYERS_APP_ID, FYERS_SECRET_ID, FYERS_REDIRECT_URI, FYERS_AUTH_CODE, FYERS_PIN, WEBHOOK_SECRET_TOKEN, GCS_BUCKET_NAME, GCS_TOKENS_FILE, GOOGLE_APPLICATION_CREDENTIALS.

**Optional:** LOG_LEVEL, LOG_FILE, USE_CLOUD_LOGGING, CLOUD_LOG_LEVEL, FILE_LOG_LEVEL; NOTIFICATION_TOPIC, NOTIFICATION_URL; IDEMPOTENCY_TTL_SECONDS.

---

## What to Do Next (optional robustness)

See **PRODUCTION_READINESS.md**. Short list: `MAX_CONTENT_LENGTH`, timeouts on outbound calls, sanitize error responses. (Input validation + max qty is done.) No rate limiting, IP whitelist, CORS, DB, or extra observability required for your personal TradingView-only setup.

---

## Quick Reference

- **Flow details:** `FUNCTIONALITY.md`
- **Robustness checklist (minimal):** `PRODUCTION_READINESS.md`
- **Run locally:** `PYTHONPATH=. python main.py` or `docker compose up`
- **Deploy:** `gcloud builds submit --config cloudbuild.yaml`
