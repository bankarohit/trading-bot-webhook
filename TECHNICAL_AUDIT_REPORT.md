# Technical Audit Report – Trading Bot Webhook

**Audit Date:** January 26, 2026  
**Scope:** Full documentation review + codebase verification against docs and production expectations.

---

## 1. Documentation Understanding

### Architecture summary

- **Stated architecture:** Flask webhook receives TradingView alert JSON → validates token → resolves NSE F&O symbol from Fyers CSV → fetches LTP from Fyers → computes direction-aware SL/TP → (for BUY) checks existing short position → places order via Fyers REST API. Tokens stored in GCS; optional Pub/Sub/webhook notifications on failure.
- **Components (per docs):** `app/__init__.py` (factory, hooks), `app/routes.py` (endpoints), `app/auth.py` + `app/token_manager.py` (OAuth, GCS), `app/fyers_api.py` (LTP, positions, place_order), `app/utils.py` (symbol master, lot size), `app/config.py`, `app/logging_config.py`, `app/notifications.py`, `app/idempotency.py`; `main.py` (entry). Design doc references future WebSocket monitor (not implemented).
- **Request flow:** before_request (request_id, start time) → route → after_request (log method, path, status, duration).
- **Deployment:** README and Dockerfile state Gunicorn with Uvicorn workers (`main:asgi_app`), non-blocking; one worker can handle many concurrent requests.

### Feature summary

- **Declared features:** Webhook (token validation, symbol resolution, LTP, direction-aware SL/TP, idempotency, cover-only BUY check, retries, notifications); input validation + max qty (action, optionType, expiry, strikeprice, WEBHOOK_MAX_QTY); auth (token manager, GCS + local, refresh, generate); health (GET /readyz); logging (request_id, optional Cloud + file, configurable levels); deployment (Dockerfile, docker-compose, cloudbuild.yaml).

### Production readiness claim

- **PRODUCTION_READINESS.md:** “Already in good shape”: SL/TP direction-aware, validation, idempotency, logging, auth, retries, **129 tests**, **input validation + max qty**. “Worth doing”: **MAX_CONTENT_LENGTH**, **timeouts** on Fyers/HTTP, **sanitize error responses**. “Optional/later”: DB audit, symbol refresh, richer health, graceful shutdown. “Skip”: rate limit, IP allowlist, CORS, circuit breaker, etc.
- **PROJECT_STATUS.md:** “Functional and suitable for personal Cloud Run use”; input validation + max qty implemented; remaining: request size limit, timeouts, error sanitization.

### Roadmap status

- **Completed (per docs):** Input validation + max qty, idempotency, non-blocking server (Gunicorn + UvicornWorker). FUNCTIONALITY.md webhook payload sample now shows `"symbol": "BANKNIFTY"` with note that symbol is the underlying.
- **Not done (per PRODUCTION_READINESS):** MAX_CONTENT_LENGTH, timeouts on outbound calls, error sanitization.
- **Future (design.md):** WebSocket monitor for Fyers – not started.

---

## 2. Codebase Understanding

### Actual architecture inferred from code

- **Entry:** `main.py` → `load_env_variables()` → `configure_logging()` → `create_app()` → Flask app; exposes `asgi_app = WSGIMiddleware(app)` for ASGI (used by Dockerfile).
- **Server:** `Dockerfile` CMD: `gunicorn main:asgi_app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080`. Matches README deployment section.
- **App factory:** `create_app()` in `app/__init__.py` registers blueprint, before/after_request hooks. **Does not set** `app.config["MAX_CONTENT_LENGTH"]`.
- **Dependencies:** Flask, fyers-apiv3, requests, google-cloud-storage, google-cloud-logging, google-cloud-pubsub, pandas, python-dotenv, certifi, uvicorn, gunicorn (requirements.txt).

### Implemented modules

| Module | Purpose | Notes |
|--------|---------|--------|
| `app/__init__.py` | Factory, request_id, timing log | No MAX_CONTENT_LENGTH |
| `app/config.py` | load_env_variables, certifi SSL env | Required vars include GOOGLE_APPLICATION_CREDENTIALS |
| `app/auth.py` | Wrappers over token_manager | Thin |
| `app/routes.py` | /webhook, /readyz, /refresh-token, /generate-token, /auth-url | Async where Fyers awaited; validation + max_contracts; returns str(e) and "details" in some 500s |
| `app/fyers_api.py` | get_ltp, has_short_position, place_order, _validate_order_params, _get_default_qty, _retry_api_call | No explicit timeouts on Fyers SDK |
| `app/utils.py` | load_symbol_master, get_symbol_from_csv, get_lot_size_for_underlying | urlopen **no timeout**; GCS in _get_storage_client |
| `app/token_manager.py` | Token load/save (GCS + local), refresh, generate, get_fyers_client | requests.post for refresh **no timeout** |
| `app/idempotency.py` | get_idempotency_key, IdempotencyStore (in-memory), get_store | TTL from env; **process-local** (multi-instance duplicates possible) |
| `app/notifications.py` | send_notification (Pub/Sub + POST URL) | requests.post(url, timeout=5) ✓ |
| `app/logging_config.py` | configure_logging, RequestIdFilter, get_request_id | Cloud + file handlers with safe setup |

### Incomplete modules

- None fully incomplete. “Worth doing” items not implemented: MAX_CONTENT_LENGTH, timeouts (token_manager refresh, utils urlopen, Fyers SDK), error response sanitization.

### Dependency graph summary

- `main.py` → create_app, load_env_variables, configure_logging.
- `routes.py` → fyers_api, utils (get_symbol_from_csv, get_lot_size_for_underlying), notifications, auth, idempotency, logging_config.
- `fyers_api.py` → utils (symbol cache), token_manager.
- `token_manager.py` → config, notifications, utils._get_storage_client (GCS).
- `auth.py` → token_manager only.
- Symbol resolution and lot size use shared `utils._symbol_cache` (loaded from Fyers CSV over HTTP, no timeout).

### External integrations present

- **Fyers API** (REST): token refresh via `requests.post` (no timeout), LTP/quotes, positions, place_order via fyers_apiv3 (async).
- **Google Cloud:** GCS (tokens blob), optional Cloud Logging, optional Pub/Sub (notifications).
- **HTTP:** Symbol master CSV `https://public.fyers.in/sym_details/NSE_FO.csv` (urllib.request.urlopen, no timeout).

---

## 3. Discrepancies Between Documentation and Code

### 3.1 FUNCTIONALITY.md – Webhook payload symbol format

- **Documentation claim:** FUNCTIONALITY.md “Key Data Structures” → “Webhook Payload” was historically shown as `"symbol": "NSE:BANKNIFTY"`.
- **Actual code state:** As of this audit, FUNCTIONALITY.md has been updated: sample shows `"symbol": "BANKNIFTY"` and includes the line “The `symbol` field is the **underlying** (e.g. `NIFTY`, `BANKNIFTY`), not the full Fyers ticker.” `get_symbol_from_csv(symbol, ...)` in `app/utils.py` filters by `underlying_symbol`; payload must send underlying. **No remaining discrepancy.**
- **Severity:** N/A (fixed).
- **Recommendation:** None.

### 3.2 MAX_CONTENT_LENGTH not set

- **Documentation claim:** PRODUCTION_READINESS.md “Worth doing” item 1: Set `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024` in the app factory.
- **Actual code state:** `create_app()` in `app/__init__.py` does **not** set `MAX_CONTENT_LENGTH`.
- **Severity:** **Medium** (large request bodies accepted; doc says to add it).
- **Recommendation:** Add in `create_app()`: `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024`, or remove from “Worth doing” if not desired.

### 3.3 Timeouts on outbound calls

- **Documentation claim:** PRODUCTION_READINESS.md “Worth doing” item 2: Timeouts on requests / Fyers SDK calls (and notification POST if used).
- **Actual code state:** `app/notifications.py` uses `requests.post(url, json=data, timeout=5)`. `app/token_manager.py` line 327: `requests.post(...)` to Fyers validate-refresh-token has **no timeout**. `app/utils.py` lines 44–45: `urllib.request.urlopen(symbol_master_url, ...)` has **no timeout**. Fyers SDK (quotes, positions, place_order) has **no explicit timeout** in this codebase.
- **Severity:** **Medium** (stuck Fyers or symbol-master call can hang request).
- **Recommendation:** Add timeout to token_manager refresh `requests.post` (e.g. 15–30s). Add timeout to `urllib.request.urlopen` (e.g. 30s). If Fyers SDK supports timeout, set it; otherwise document the risk.

### 3.4 Error response sanitization

- **Documentation claim:** PRODUCTION_READINESS.md “Worth doing” item 3: Catch exceptions, log details internally, return generic messages (e.g. "Order placement failed") to the client.
- **Actual code state:** `app/routes.py`: health check returns `str(e)` (line 61). Order failure returns `f"Exception while placing order: {str(e)}"` (line 454) and includes `"details": order_response` (line 436). Unhandled webhook exception returns `str(e)` (line 479). Internal exception text and Fyers response shape can leak to client.
- **Severity:** **Medium** (internal/exception details and API response shape exposed to client).
- **Recommendation:** In routes, on 500/error paths log full exception and response server-side; return fixed messages to client (e.g. "Order placement failed", "Health check failed"); avoid attaching `details` or raw `str(e)` in production responses.

### 3.5 .env.example missing GOOGLE_APPLICATION_CREDENTIALS

- **Documentation claim:** README says copy `.env.example` and fill credentials; `app/config.py` requires `GOOGLE_APPLICATION_CREDENTIALS`.
- **Actual code state:** `.env.example` does **not** include `GOOGLE_APPLICATION_CREDENTIALS`. README later mentions setting it or mounting the key.
- **Severity:** **Low** (README mentions it elsewhere; .env.example incomplete).
- **Recommendation:** Add `GOOGLE_APPLICATION_CREDENTIALS=` to .env.example with a short comment (path to service account JSON).

### 3.6 Idempotency store is process-local

- **Documentation claim:** Docs describe idempotency as avoiding “duplicate orders when TradingView retries or the same alert is sent twice.”
- **Actual code state:** `app/idempotency.py` uses an in-memory `IdempotencyStore` singleton. On Cloud Run, multiple instances do not share this store; the same idempotency key sent to two instances can both pass the replay check and place two orders.
- **Severity:** **Medium** (acceptable for single-instance; under scaling, duplicate orders possible).
- **Recommendation:** Document that idempotency is per-instance only. If multi-instance dedup is required, implement a shared store (e.g. Redis, Firestore) or constrain Cloud Run to one instance.

---

## 4. Production Risk Assessment

### Deployment risks

- **Cloud Run --allow-unauthenticated:** `cloudbuild.yaml` deploys with `--allow-unauthenticated`. Service is publicly reachable; auth is only via `WEBHOOK_SECRET_TOKEN` in body. URL and token must be treated as secret; only share with TradingView.
- **Single async worker:** One Uvicorn worker; sufficient for personal low concurrency. If scaling to multiple instances, idempotency is not shared (see 3.6).

### Security gaps

- **Error messages:** Raw exceptions and Fyers `details` in JSON responses (see 3.4). **Medium.**
- **No request body size limit:** MAX_CONTENT_LENGTH not set; very large payloads accepted. **Low–Medium.**
- **Token in payload:** Secret in JSON body is acceptable for server-to-server; TLS and no logging of body (token is masked in routes). **Low.**

### Performance bottlenecks

- **Symbol master load:** First request that needs symbol resolution can trigger CSV download with no timeout; large CSV. Add timeout; consider caching at startup or in image.
- **No connection pooling documented:** requests/urllib used; Fyers SDK may pool. **Low.**

### Observability / logging gaps

- **Structured logs:** request_id, duration, event fields used; suitable for Cloud Logging. **Adequate.**
- **No metrics/traces:** No Prometheus or OpenTelemetry; doc explicitly defers. **Acceptable** for stated scope.
- **Health check:** /readyz checks token + Fyers ping; no GCS or symbol-master check. **Acceptable** per doc.

### Testing coverage gaps

- **129 unit tests;** no integration tests against live Fyers; no load tests. Conftest stubs Google Cloud. **Acceptable** for personal use; document that E2E is manual.
- **Coverage:** .coveragerc exists (branch, source=app); no coverage threshold or CI gate in cloudbuild (only `pytest -q`). **Low.**

---

## 5. Suggested Next Actions (Prioritized)

1. **Medium – Error sanitization:** In `app/routes.py`, for 500 and error responses: log full exception and Fyers response server-side; return generic messages to client (e.g. "Order placement failed", "Health check failed"); remove or restrict `details` in JSON.

2. **Medium – MAX_CONTENT_LENGTH:** In `create_app()` in `app/__init__.py`, set `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024`.

3. **Medium – Timeouts:** Add timeout to `app/token_manager.py` refresh `requests.post`; add timeout to `urllib.request.urlopen` in `app/utils.py` `load_symbol_master`. Document or configure Fyers SDK timeout if supported.

4. **Medium – Idempotency scope:** Document in README or PRODUCTION_READINESS that idempotency is per instance; if only one Cloud Run instance is used, state that. If duplicates under scale are unacceptable, design a shared idempotency store.

5. **Low – .env.example:** Add `GOOGLE_APPLICATION_CREDENTIALS=` with a brief comment.

---

**Summary:** The application matches the documented architecture and deployment (Gunicorn + Uvicorn workers, non-blocking). Test count (129) and “input validation + max qty” status are correctly stated in PROJECT_STATUS and PRODUCTION_READINESS. FUNCTIONALITY.md symbol format is now correct. Remaining gaps are: (1) PRODUCTION_READINESS “Worth doing” items not yet in code (MAX_CONTENT_LENGTH, timeouts, error sanitization), (2) idempotency per-instance behavior not documented, (3) .env.example incomplete. Addressing the medium items above will align the system with the documented production-readiness goals.
