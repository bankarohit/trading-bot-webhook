# Functionality Overview

## Entry Point
- **File:** `main.py`
- **Flow:** `load_env_variables()` → `configure_logging()` → `create_app()` → Flask server on port 8080

## Control Flow

### Application Startup (`app/__init__.py`)
1. Load environment variables
2. Create Flask app
3. Register request hooks (before_request, after_request)
4. Register webhook blueprint

### Request Lifecycle
1. **before_request:** Generate request ID, start timer
2. **Route handler:** Process request
3. **after_request:** Log request duration

## Data Flow

### Main Webhook Flow (`POST /webhook`)

```
TradingView Alert (JSON)
    ↓
1. Extract & validate payload fields
    ↓
2. Verify secret token
    ↓
3. Resolve Fyers symbol from CSV master
    (symbol + strike + optionType + expiry → fyers_symbol)
    ↓
4. Get Fyers client (with token refresh if needed)
    ↓
5. If BUY action: Check for existing short position
    ↓
6. Fetch LTP (Last Traded Price)
    ↓
7. Calculate SL/TP if not provided (15% SL, 25% TP of LTP)
    ↓
8. Validate & normalize order parameters
    ↓
9. Place order via Fyers API
    ↓
10. Return success/error response
```

## Endpoints

### 1. `POST /webhook` - Main Trading Endpoint
- **Input:** TradingView alert JSON
- **Process:** Symbol resolution → Position check → LTP fetch → Order placement
- **Output:** Order confirmation or error

### 2. `GET /readyz` - Health Check
- **Checks:** Access token availability, Fyers API connectivity
- **Returns:** Service status

### 3. `GET /auth-url` - Get Authorization URL
- **Returns:** Fyers login URL for OAuth

### 4. `POST /generate-token` - Generate Access Token
- **Process:** Exchange auth code for access/refresh tokens
- **Stores:** Tokens in GCS + local cache

### 5. `POST /refresh-token` - Refresh Access Token
- **Process:** Use refresh token to get new access token
- **Updates:** Token storage

## Core Functions

### Symbol Resolution (`app/utils.py`)
- `load_symbol_master()` - Download NSE_FO CSV, cache in memory
- `get_symbol_from_csv()` - Match symbol + strike + type + expiry → Fyers ticker

### Fyers API (`app/fyers_api.py`)
- `get_ltp()` - Fetch last traded price (with retry)
- `has_short_position()` - Check if short position exists
- `place_order()` - Execute market order (with retry)
- `_validate_order_params()` - Normalize qty, sl, tp, productType
- `_get_default_qty()` - Get lot size from symbol master

### Token Management (`app/token_manager.py`)
- `get_access_token()` - Get valid token (refresh if expired)
- `generate_token()` - Create new token from auth code
- `refresh_token()` - Refresh using refresh token
- `get_fyers_client()` - Get authenticated Fyers client
- `_load_tokens()` - Load from GCS or local file
- `_save_tokens()` - Save to GCS + local file

### Authentication (`app/auth.py`)
- Wrapper functions around token_manager

### Notifications (`app/notifications.py`)
- `send_notification()` - Send to Pub/Sub topic or webhook URL

## Key Data Structures

### Webhook Payload

The `symbol` field is the **underlying** (e.g. `NIFTY`, `BANKNIFTY`), not the full Fyers ticker.

```json
{
  "token": "secret",
  "symbol": "BANKNIFTY",
  "strikeprice": 48400,
  "optionType": "PE",
  "expiry": "WEEKLY",
  "action": "SELL",
  "qty": 25,
  "sl": 10.0,      // optional
  "tp": 20.0,      // optional
  "productType": "BO"  // optional, defaults to "BO"
}
```

### Token Storage (GCS/local JSON)
```json
{
  "access_token": "...",
  "refresh_token": "...",
  "issued_at": "2026-01-26T...",
  "expires_at": "2026-01-27T..."
}
```

## Business Logic

### SL/TP Calculation
- If `sl` or `tp` not provided or invalid, the service uses direction-aware levels from LTP (15% / 25% bands):
  - **BUY:** `sl = round(ltp * (1 - 0.15), 2)` (15% below LTP), `tp = round(ltp * (1 + 0.25), 2)` (25% above LTP).
  - **SELL:** `sl = round(ltp * (1 + 0.15), 2)` (15% above LTP), `tp = round(ltp * (1 - 0.25), 2)` (25% below LTP).

### Position Validation
- **BUY orders:** Must have existing short position
- **SELL orders:** No position check

### Symbol Resolution Logic
- Filter by underlying symbol
- Filter by strike price (rounded)
- Filter by option type (CE/PE)
- Filter by expiry type:
  - **WEEKLY:** Next weekly expiry
  - **MONTHLY:** Next monthly expiry (matches pattern like `BANKNIFTY24JAN`)
- Return first matching symbol_ticker

### Order Parameters
- **qty:** From payload or lot size from symbol master (default: 1)
- **sl:** From payload or calculated (default: 10.0)
- **tp:** From payload or calculated (default: 20.0)
- **productType:** From payload or "BO" (default)

## Error Handling

### Retry Logic
- 3 attempts with exponential backoff
- Applied to: `get_ltp()`, `has_short_position()`, `place_order()`

### Token Refresh
- Auto-refresh on 401 errors
- Fallback to token generation if refresh fails

### Error Responses
- `400` - Validation errors, missing fields
- `401` - Invalid secret token
- `403` - Symbol resolution failed
- `500` - Order placement failed, exceptions

## Configuration

### Required Environment Variables
- `FYERS_APP_ID`, `FYERS_SECRET_ID`, `FYERS_REDIRECT_URI`
- `FYERS_AUTH_CODE`, `FYERS_PIN`
- `WEBHOOK_SECRET_TOKEN`
- `GCS_BUCKET_NAME`, `GCS_TOKENS_FILE`
- `GOOGLE_APPLICATION_CREDENTIALS`

### Optional
- `LOG_LEVEL`, `LOG_FILE`, `USE_CLOUD_LOGGING`
- `NOTIFICATION_TOPIC`, `NOTIFICATION_URL`
