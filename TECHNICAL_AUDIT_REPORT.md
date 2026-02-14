# Technical Audit Report – Trading Bot Webhook

**Audit Date:** January 26, 2026  
**Scope:** Full documentation review + codebase verification against docs and production expectations.

---

## 1. Documentation Understanding

### Architecture summary

- **Stated architecture:** Flask webhook receives TradingView alert JSON → validates token → resolves NSE F&O symbol from Fyers CSV → fetches LTP from Fyers → computes direction-aware SL/TP → (for BUY) checks existing short position → places order via Fyers REST API. Tokens stored in GCS; optional Pub/Sub/webhook notifications on failure.
- **Components (per docs):** `app/__init__.py` (factory, hooks), `app/routes.py` (endpoints), `app/auth.py` + `app/token_manager.py` (OAuth, GCS), `app/fyers_api.py` (LTP, positions, place_order), `app/utils.py` (symbol master, lot size), `main.py` (entry). Design doc also references future WebSocket monitor (not implemented).
- **Request flow:** before_request (request_id, start time) → route → after_request (log method, path, status, duration).

### Feature summary

- **Declared features:** Webhook (token validation, symbol resolution, LTP, SL/TP, idempotency, cover-only BUY check, retries, notifications); auth (token manager, GCS + local, refresh, generate); health (GET /readyz); logging (request_id, optional Cloud + file, configurable levels); deployment (Dockerfile, docker-compose, cloudbuild.yaml).

### Production readiness claim

- **PRODUCTION_READINESS.md:** “Already in good shape”: SL/TP direction-aware, validation, idempotency, logging, auth, retries. “Worth doing”: input validation + max qty, **MAX_CONTENT_LENGTH**, **timeouts** on Fyers/HTTP, **sanitize error responses**. “Optional/later”: DB audit, symbol refresh, richer health, graceful shutdown. “Skip”: rate limit, IP allowlist, CORS, circuit breaker, etc.
- **PROJECT_STATUS.md:** “Functional and suitable for personal Cloud Run use”; points to PRODUCTION_READINESS for “input validation + max qty, request size limit, timeouts, error sanitization” as next steps.

### Roadmap status

- **Completed (per docs):** Input validation + max qty are listed in “Worth doing” but are **implemented** in code (action/optionType/expiry/strikeprice/qty validation, WEBHOOK_MAX_QTY, get_lot_size_for_underlying). Idempotency implemented.
- **Not done (per PRODUCTION_READINESS):** MAX_CONTENT_LENGTH, timeouts on outbound calls, error sanitization.
- **Future (design.md):** WebSocket monitor for Fyers – not started.

---

## 2. Codebase Understanding

### Actual architecture inferred from code

- **Entry:** `main.py` → `load_env_variables()` → `configure_logging()` → `create_app()` → Flask app; also exposes `asgi_app = WSGIMiddleware(app)` for ASGI.
- **Server:** Dockerfile runs **uvicorn** with `main:asgi_app` (WSGI wrapped in ASGI). README states deployment uses **Gunicorn** (`gunicorn -b 0.0.0.0:8080 main:app`) – **mismatch** (see Discrepancies).
- **App factory:** `create_app()` in `app/__init__.py` registers blueprint, before/after_request hooks. **Does not set** `app.config["MAX_CONTENT_LENGTH"]`.
- **Dependencies:** Flask, fyers-apiv3, requests, google-cloud-storage, google-cloud-logging, google-cloud-pubsub, pandas, python-dotenv, certifi, uvicorn, gunicorn (both in requirements).

### Implemented modules

| Module | Purpose | Notes |
|--------|---------|--------|
| `app/__init__.py` | Factory, request_id, timing log | No MAX_CONTENT_LENGTH |
| `app/config.py` | load_env_variables, certifi SSL env | Required vars include GOOGLE_APPLICATION_CREDENTIALS |
| `app/auth.py` | Wrappers over token_manager | Thin |
| `app/routes.py` | /webhook, /readyz, /refresh-token, /generate-token, /auth-url | Async where Fyers is awaited; validation + max_contracts |
| `app/fyers_api.py` | get_ltp, has_short_position, place_order, _validate_order_params, _get_default_qty, _retry_api_call | No explicit timeouts on Fyers SDK usage |
| `app/utils.py` | load_symbol_master, get_symbol_from_csv, get_lot_size_for_underlying | urlopen **no timeout**; GCS helper in _get_storage_client |
| `app/token_manager.py` | Token load/save (GCS + local), refresh, generate, get_fyers_client | requests.post for refresh **no timeout** |
| `app/idempotency.py` | get_idempotency_key, IdempotencyStore (in-memory), get_store | TTL from env; **process-local** (multi-instance duplicates possible) |
| `app/notifications.py` | send_notification (Pub/Sub + POST URL) | requests.post(url, timeout=5) ✓ |
| `app/logging_config.py` | configure_logging, RequestIdFilter, get_request_id | Cloud + file handlers with safe setup |

### Incomplete modules

- **None** fully incomplete; “Worth doing” items are **partially** missing (MAX_CONTENT_LENGTH, timeouts, error sanitization).

### Dependency graph summary

- `main.py` → create_app, load_env_variables, configure_logging.
- `routes.py` → fyers_api, utils (get_symbol_from_csv, get_lot_size_for_underlying), notifications, auth, idempotency, logging_config.
- `fyers_api.py` → utils (symbol cache), token_manager.
- `token_manager.py` → config, notifications, utils._get_storage_client (GCS).
- `auth.py` → token_manager only.
- Symbol resolution and lot size use shared `utils._symbol_cache` (loaded from Fyers CSV over HTTP, no timeout).

### External integrations present

- **Fyers API** (REST): token refresh (requests.post), LTP/quotes, positions, place_order via fyers_apiv3 (async).
- **Google Cloud:** GCS (tokens blob), optional Cloud Logging, optional Pub/Sub (notifications).
- **HTTP:** Symbol master CSV `https://public.fyers.in/sym_details/NSE_FO.csv` (urllib.request.urlopen, no timeout).

---

## 3. Discrepancies Between Documentation and Code

### 3.1 Deployment: Gunicorn vs Uvicorn

- **Documentation claim:** README “Deployment” section: “The container runs using **Gunicorn** with the command: `gunicorn -b 0.0.0.0:8080 main:app`.”
- **Actual code state:** `Dockerfile` CMD: `["uvicorn", "main:asgi_app", "--host", "0.0.0.0", "--port", "8080"]`. No Gunicorn in Dockerfile.
- **Severity:** **Medium** (different server and process model; Gunicorn workers vs single Uvicorn process; docs wrong for current image).
- **Recommendation:** Either change Dockerfile to use Gunicorn (with a WSGI worker) and keep README, or update README and deployment docs to state Uvicorn and document that a single process is used (no multi-worker).

### 3.2 Test count

- **Documentation claim:** PROJECT_STATUS.md: “tests/ # 116 tests”.
- **Actual code state:** `pytest --co` collects **129 tests** (includes idempotency, get_lot_size_for_underlying, and other added tests).
- **Severity:** **Low** (outdated count only).
- **Recommendation:** Update PROJECT_STATUS.md to “129 tests” (or “tests/” without a fixed number).

### 3.3 Repository layout in README

- **Documentation claim:** README “Repository Layout” lists `app/auth.py`, `app/routes.py`, `app/token_manager.py`, `app/utils.py` and “main.py”, “tests/”. Does **not** list `app/config.py`, `app/logging_config.py`, `app/notifications.py`, `app/idempotency.py`, `app/fyers_api.py`.
- **Actual code state:** All of the above exist and are part of the app.
- **Severity:** **Low** (incomplete layout).
- **Recommendation:** Extend README layout to include config, logging_config, notifications, idempotency, fyers_api.

### 3.4 SL/TP formula in FUNCTIONALITY.md

- **Documentation claim:** FUNCTIONALITY.md “SL/TP Calculation”: “sl = round(ltp * 0.15)” (15% of LTP), “tp = round(ltp * 0.25)” (25% of LTP).
- **Actual code state:** `app/routes.py`: `sl_pct = 0.15`, `tp_pct = 0.25`; for BUY `sl = round(ltp * (1 - sl_pct), 2)`, `tp = round(ltp * (1 + tp_pct), 2)` (i.e. SL = 85% of LTP, TP = 125% of LTP). For SELL, SL above LTP, TP below.
- **Severity:** **Medium** (wrong formula in doc can mislead strategy design).
- **Recommendation:** Update FUNCTIONALITY.md to describe direction-aware levels: e.g. BUY: SL = LTP × (1 - 0.15), TP = LTP × (1 + 0.25); SELL: SL = LTP × (1 + 0.15), TP = LTP × (1 - 0.25).

### 3.5 Sample webhook payload symbol format

- **Documentation claim:** README “Sample Webhook Payload”: `"symbol": "NSE:BANKNIFTY"`.
- **Actual code state:** `get_symbol_from_csv(symbol, ...)` filters by `underlying_symbol` (e.g. `NIFTY`, `BANKNIFTY`). Payload must send underlying like `"BANKNIFTY"` or `"NIFTY"`, not `NSE:BANKNIFTY`.
- **Severity:** **High** (copy-paste from README would cause symbol resolution to fail or behave unexpectedly if CSV uses underlying only).
- **Recommendation:** Change sample to `"symbol": "BANKNIFTY"` and add one line that symbol is the underlying (e.g. NIFTY, BANKNIFTY), not the full Fyers ticker.

### 3.6 Production readiness “Worth doing” vs implementation

- **Documentation claim:** PRODUCTION_READINESS “Worth doing” item 1: “Input validation + max quantity” – “Validate action, optionType, expiry, strikeprice; enforce WEBHOOK_MAX_QTY”.
- **Actual code state:** **Done** in routes (action, optionType, expiry, strikeprice, qty vs max_contracts from get_lot_size_for_underlying × WEBHOOK_MAX_QTY).
- **Severity:** **Low** (doc not updated to reflect done).
- **Recommendation:** In PRODUCTION_READINESS and PROJECT_STATUS, mark “Input validation + max qty” as done; keep only MAX_CONTENT_LENGTH, timeouts, error sanitization under “Do next”.

### 3.7 MAX_CONTENT_LENGTH not set

- **Documentation claim:** PRODUCTION_READINESS “Worth doing” item 2: Set `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024` in the app factory.
- **Actual code state:** `create_app()` in `app/__init__.py` does **not** set `MAX_CONTENT_LENGTH`.
- **Severity:** **Medium** (large body could be accepted; doc says to add it).
- **Recommendation:** Add in `create_app()`: `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024` (and document in README if desired).

### 3.8 Timeouts on outbound calls

- **Documentation claim:** PRODUCTION_READINESS “Worth doing” item 3: “Timeouts on requests / Fyers SDK calls (and notification POST if used).”
- **Actual code state:** `app/notifications.py` uses `requests.post(url, json=data, timeout=5)`. `app/token_manager.py` `requests.post(...)` to Fyers validate-refresh-token has **no timeout**. `app/utils.py` `urllib.request.urlopen(symbol_master_url, ...)` has **no timeout**. Fyers SDK (quotes, positions, place_order) is used via fyers_apiv3 with **no explicit timeout** in this codebase (SDK may have its own defaults).
- **Severity:** **Medium** (stuck Fyers or symbol-master call can hang request).
- **Recommendation:** Add timeout to token_manager refresh `requests.post` (e.g. 15–30s). Add timeout to `urllib.request.urlopen` (e.g. 30s). If Fyers SDK supports timeout, set it; otherwise document the risk.

### 3.9 Error response sanitization

- **Documentation claim:** PRODUCTION_READINESS “Worth doing” item 4: “Catch exceptions, log details internally, return generic messages (e.g. ‘Order placement failed’) to the client.”
- **Actual code state:** `app/routes.py`: Health check returns `str(e)` (line 61). Order failure returns `f"Exception while placing order: {str(e)}"` (line 454) and unhandled webhook returns `str(e)` (line 479). On Fyers order API error, returns `"details": order_response` (line 436) which can expose Fyers response shape.
- **Severity:** **Medium** (internal/exception text and API details can leak to client).
- **Recommendation:** In routes, on 500/error paths log full exception and response; return fixed messages to client (e.g. “Order placement failed”, “Health check failed”) and avoid attaching `details` or raw `str(e)` in production responses.

### 3.10 .env.example missing GOOGLE_APPLICATION_CREDENTIALS

- **Documentation claim:** README says copy `.env.example` and fill credentials; config.py requires `GOOGLE_APPLICATION_CREDENTIALS`.
- **Actual code state:** `.env.example` does **not** include `GOOGLE_APPLICATION_CREDENTIALS`. README later says “set GOOGLE_APPLICATION_CREDENTIALS … or mount the key at /secrets/service_account.json”.
- **Severity:** **Low** (README mentions it elsewhere; .env.example is incomplete).
- **Recommendation:** Add `GOOGLE_APPLICATION_CREDENTIALS=` to .env.example with a short comment (path to service account JSON).

### 3.11 Idempotency store is process-local

- **Documentation claim:** Docs describe idempotency as avoiding “duplicate orders when TradingView retries or the same alert is sent twice.”
- **Actual code state:** `app/idempotency.py` uses an in-memory `IdempotencyStore` singleton. On Cloud Run, multiple instances do not share this store; the same idempotency key sent to two instances can both pass the “replay” check and place two orders.
- **Severity:** **Medium** (acceptable for single-instance; under load/scaling, duplicate orders possible).
- **Recommendation:** Document that idempotency is per-instance only. If multi-instance dedup is required, implement a shared store (e.g. Redis, Firestore) or constrain Cloud Run to a single instance.

---

## 4. Production Risk Assessment

### Deployment risks

- **Server mismatch:** Docker runs Uvicorn; README says Gunicorn. Deployments following README literally would not match the built image. **Medium.**
- **Single process:** Uvicorn single process; no multi-worker. One stuck request can block others. **Low** for low concurrency; document.
- **Cloud Run --allow-unauthenticated:** Service is publicly reachable; auth is only via `WEBHOOK_SECRET_TOKEN` in body. Token in URL or logs would be a security issue. **Document** that the URL must be treated as secret and only shared with TradingView.

### Security gaps

- **Error messages:** Raw exceptions and Fyers `details` in JSON responses (see 3.9). **Medium.**
- **No request body size limit:** MAX_CONTENT_LENGTH not set; very large payloads accepted. **Low–Medium.**
- **Token in payload:** Secret in JSON body is fine for server-to-server; ensure TLS and no logging of body (masking in routes is done for token). **Low.**

### Performance bottlenecks

- **Symbol master load:** First request that needs symbol resolution can trigger CSV download with no timeout; large CSV. **Mitigate:** add timeout; consider caching in build or at startup.
- **No connection pooling documented:** requests/urllib used; Fyers SDK may pool. **Low.**

### Observability / logging gaps

- **Structured logs:** request_id, duration, event fields used; suitable for Cloud Logging. **Adequate.**
- **No metrics/traces:** No Prometheus or OpenTelemetry; doc explicitly defers. **Acceptable** for stated scope.
- **Health check:** /readyz checks token + Fyers ping; no GCS or symbol-master check. **Acceptable** per doc.

### Testing coverage gaps

- **129 unit tests;** no integration tests against live Fyers; no load tests. Conftest stubs Google Cloud so no real GCS/Cloud Logging in tests. **Acceptable** for personal use; document that E2E is manual.
- **Coverage:** .coveragerc exists (branch, source=app); no coverage threshold or CI gate seen in cloudbuild (only `pytest -q`). **Low.**

---

## 5. Suggested Next Actions (Prioritized)

1. **High – Fix sample payload (README):** Change `"symbol": "NSE:BANKNIFTY"` to `"symbol": "BANKNIFTY"` and clarify that symbol is the underlying index name. Prevents user errors and support confusion.

2. **Medium – Align deployment with docs:** Either switch Dockerfile to Gunicorn (and document workers) or update README and any runbooks to state that the container uses Uvicorn and single process.

3. **Medium – Error sanitization (PRODUCTION_READINESS item 4):** In `app/routes.py`, for 500 and error responses: log full exception and Fyers response server-side; return generic messages to client; remove or restrict `details` in JSON.

4. **Medium – MAX_CONTENT_LENGTH (PRODUCTION_READINESS item 2):** In `create_app()`, set `app.config["MAX_CONTENT_LENGTH"] = 64 * 1024`. Document in README if needed.

5. **Medium – Timeouts:** Add timeout to `token_manager` refresh `requests.post`; add timeout to `urllib.request.urlopen` in `load_symbol_master`. Optionally document or configure Fyers SDK timeout if supported.

6. **Medium – Idempotency scope:** Document in README or PRODUCTION_READINESS that idempotency is per instance; if only one Cloud Run instance is used, state that. If duplicates under scale are unacceptable, design a shared idempotency store.

7. **Low – FUNCTIONALITY.md SL/TP:** Correct SL/TP formula to direction-aware (e.g. 85%/125% of LTP for BUY, inverse for SELL).

8. **Low – PROJECT_STATUS / PRODUCTION_READINESS:** Update test count to 129; mark “Input validation + max qty” as done; list only MAX_CONTENT_LENGTH, timeouts, error sanitization as remaining “Worth doing.”

9. **Low – README layout and .env.example:** Add config, logging_config, notifications, idempotency, fyers_api to Repository Layout; add `GOOGLE_APPLICATION_CREDENTIALS` to .env.example.

---

**Summary:** The application matches the described architecture and is suitable for personal Cloud Run use with TradingView as the only client. The main gaps are: (1) README/deployment server mismatch and sample payload symbol format, (2) missing production hardening from PRODUCTION_READINESS (MAX_CONTENT_LENGTH, timeouts, error sanitization), and (3) idempotency being process-local. Addressing the high and medium items above will align the system with the documented production-readiness goals and reduce risk.
