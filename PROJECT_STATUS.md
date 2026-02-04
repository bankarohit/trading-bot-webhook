# Trading Bot Webhook – Project Status

**Last Updated:** January 26, 2026  
**Project Type:** Flask webhook service: TradingView alerts → Fyers API (options trading)

---

## Executive Summary

Flask service that receives TradingView alerts and places option orders on Fyers. It validates payloads, resolves NSE F&amp;O symbols, computes direction-aware SL/TP from LTP, and executes orders. Token storage is in GCS with auto-refresh.

**Status:** **Functional; NOT production ready.** See `PRODUCTION_READINESS.md` for gaps (rate limiting, input validation, audit trail, etc.).

---

## Entry Point & Control Flow

- **Entry:** `main.py` → `load_env_variables()` → `configure_logging()` → `create_app()` → server on `0.0.0.0:8080`.
- **Per request:** `before_request` sets `request_id` + start time → route handler → `after_request` logs method, path, status, duration.

---

## Data Flow (Main Webhook)

1. `POST /webhook` receives JSON (token, symbol, strikeprice, optionType, expiry, action, qty, …).
2. Validate secret token; reject if missing/invalid.
3. Resolve Fyers symbol from NSE_FO CSV (underlying + strike + optionType + expiry).
4. Get Fyers client (token manager; auto-refresh on expiry/401).
5. **If action = BUY:** ensure a short position exists (cover-only; option seller flow). Else 400.
6. Fetch LTP for the resolved symbol.
7. **SL/TP:** Always computed from LTP (user values ignored). Direction-aware price levels:
   - **BUY:** `sl = ltp * (1 - 0.15)`, `tp = ltp * (1 + 0.25)` (rounded to 2 decimals).
   - **SELL:** `sl = ltp * (1 + 0.15)`, `tp = ltp * (1 - 0.25)`.
8. If LTP unavailable or invalid → **400** (no order; no default SL/TP).
9. `_validate_order_params()`: normalizes qty (default from lot size), parses sl/tp (no 10/20 defaults; invalid → None). productType validated; invalid → "BO".
10. For BO/CO, if sl or tp is None after validation → `place_order` returns error; else place market order with retries.
11. Return success/error JSON.

---

## Current Features

### Webhook & order logic
- **POST /webhook:** Validates token and required fields; symbol resolution; LTP fetch; **direction-aware SL/TP from LTP only**; fail-fast 400 if LTP unavailable; BUY only when short exists (cover-only).
- **Order params:** qty from payload or symbol lot size; sl/tp only parsed/validated (no default 10/20); BO/CO require valid sl/tp or order is rejected.
- **Fyers:** get_ltp, has_short_position, place_order with 3-attempt exponential backoff; 401 → token refresh and retry.

### Auth & token
- Token manager: GCS + local cache; get/refresh/generate token; thread-safe singleton.
- **GET /auth-url**, **POST /generate-token**, **POST /refresh-token**.

### Health & ops
- **GET /readyz:** Token present + Fyers profile ping.
- **Logging:** Production-oriented: request_id, levels from env (LOG_LEVEL, optional CLOUD_LOG_LEVEL, FILE_LOG_LEVEL), optional Cloud + file handlers; errors in handler setup don’t crash the app; optional `LOG_FILE` with rotation (10MB, 5 backups, utf-8).

### Deployment
- Dockerfile, docker-compose, cloudbuild.yaml for Cloud Run; healthcheck uses `/readyz`.

---

## Project Structure

```
trading-bot-webhook-1/
├── app/
│   ├── __init__.py          # App factory, request hooks
│   ├── auth.py              # Token/auth wrappers
│   ├── config.py            # Env loading
│   ├── fyers_api.py         # Fyers API + _validate_order_params, place_order
│   ├── logging_config.py    # Production-style logging
│   ├── notifications.py    # Pub/Sub / webhook
│   ├── routes.py            # Webhook + auth/health routes
│   ├── token_manager.py     # Token storage & refresh
│   └── utils.py             # Symbol master, get_symbol_from_csv
├── tests/                   # 8 test modules, 107 tests
├── docs/design.md
├── main.py
├── FUNCTIONALITY.md         # Detailed flow & endpoints
├── PRODUCTION_READINESS.md  # What’s missing for production
└── README.md
```

---

## Endpoints

| Method | Path             | Purpose                    |
|--------|------------------|----------------------------|
| POST   | /webhook         | TradingView alert → order  |
| GET    | /readyz          | Health check               |
| GET    | /auth-url        | Fyers login URL            |
| POST   | /generate-token | Auth code → token          |
| POST   | /refresh-token   | Refresh access token       |

---

## Configuration (summary)

**Required:** `FYERS_APP_ID`, `FYERS_SECRET_ID`, `FYERS_REDIRECT_URI`, `FYERS_AUTH_CODE`, `FYERS_PIN`, `WEBHOOK_SECRET_TOKEN`, `GCS_BUCKET_NAME`, `GCS_TOKENS_FILE`, `GOOGLE_APPLICATION_CREDENTIALS`.

**Optional logging:** `LOG_LEVEL`, `LOG_FILE`, `USE_CLOUD_LOGGING`, `CLOUD_LOG_LEVEL`, `FILE_LOG_LEVEL`.

**Optional notifications:** `NOTIFICATION_TOPIC`, `NOTIFICATION_URL`.

---

## Testing

- **107 tests** across 8 modules; all passing.
- Run: `export PYTHONPATH=. && pytest -v` (or `pytest -q`).
- conftest.py provides GCS/logging stubs; no live Fyers needed.

---

## Recent Changes (functionality & robustness)

1. **SL/TP:** Always derived from LTP; direction-aware **price levels** (BUY: SL below LTP, TP above; SELL: opposite). User-provided sl/tp are intentionally overridden.
2. **No SL/TP defaulting:** `_validate_order_params()` no longer forces 10/20; invalid/missing sl/tp → None; BO/CO require valid sl/tp or order fails.
3. **Fail-fast:** If LTP is unavailable or invalid, webhook returns **400** instead of placing an order with default SL/TP.
4. **Validation:** sl/tp parsed via safe helper; non-numeric/invalid values become None (no exception thrown).
5. **Logging:** Production-style config: error handling around Cloud/file handlers, optional per-handler levels, utf-8 file logging; app continues if a handler fails to attach.
6. **BUY gating:** Kept as-is: BUY only when a short position exists (cover-only; option seller use case).

---

## What’s Not Done (production)

See **PRODUCTION_READINESS.md** for full list. Highlights: rate limiting, strict input validation and max qty, idempotency/duplicate protection, request timeouts, audit trail/DB, circuit breaker, symbol master refresh, and broader observability.

---

## Quick Reference

- **Flow details:** `FUNCTIONALITY.md`
- **Production gaps:** `PRODUCTION_READINESS.md`
- **Run locally:** `PYTHONPATH=. python main.py` or `docker compose up`
- **Deploy:** `gcloud builds submit --config cloudbuild.yaml`
