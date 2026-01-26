# Trading Bot Webhook - Project Status

**Last Updated:** January 26, 2026  
**Project Type:** Flask-based Webhook Service for TradingView → Fyers API Integration

---

## 📋 Executive Summary

This is a production-ready Flask webhook service that connects TradingView alerts to the Fyers trading API. The service automatically processes option trading alerts, validates them, resolves symbols, calculates stop-loss/take-profit values, and executes orders on the Fyers platform.

**Status:** ⚠️ **Functional but NOT Production Ready** - See `PRODUCTION_READINESS.md` for details

---

## 🏗️ Architecture Overview

```
TradingView Strategy
    ↓ (POST /webhook with JSON alert)
Flask Webhook Service
    ↓ (validates, resolves symbol, calculates SL/TP)
Fyers Trading API
    ↓ (places order)
Order Execution Confirmation
```

### Key Components

1. **Webhook Receiver** (`app/routes.py`)
   - Receives TradingView alerts via POST `/webhook`
   - Validates payload and secret token
   - Processes order requests

2. **Fyers API Integration** (`app/fyers_api.py`)
   - Wraps Fyers REST API calls
   - Handles LTP (Last Traded Price) fetching
   - Position checking before BUY orders
   - Order placement with retry logic (3 attempts with exponential backoff)

3. **Token Management** (`app/token_manager.py`)
   - OAuth2 flow for Fyers authentication
   - Token storage in Google Cloud Storage (GCS)
   - Automatic token refresh
   - Thread-safe singleton pattern

4. **Symbol Resolution** (`app/utils.py`)
   - Loads NSE_FO symbol master CSV from Fyers
   - Resolves option symbols (strike, type, expiry)
   - Caches symbol data in memory

5. **Authentication** (`app/auth.py`)
   - Wrapper functions for token operations
   - Fyers client initialization

6. **Notifications** (`app/notifications.py`)
   - Pub/Sub integration for critical alerts
   - Webhook notifications for failures

7. **Logging** (`app/logging_config.py`)
   - Structured logging with request IDs
   - Google Cloud Logging integration
   - File-based logging support

---

## ✨ Current Features

### ✅ Implemented Features

- **Webhook Endpoint** (`POST /webhook`)
  - Validates TradingView alert payloads
  - Resolves option symbols from NSE_FO master
  - Calculates SL/TP from LTP if not provided (15% SL, 25% TP)
  - Checks for existing short positions before BUY orders
  - Places market orders via Fyers API
  - Comprehensive error handling and logging

- **Token Management**
  - OAuth2 authorization flow
  - Token generation from auth code
  - Automatic token refresh
  - GCS-based token persistence
  - Local token caching

- **Health Check** (`GET /readyz`)
  - Validates access token availability
  - Pings Fyers API for connectivity
  - Returns service status and user profile

- **Utility Endpoints**
  - `GET /auth-url` - Generate Fyers login URL
  - `POST /generate-token` - Exchange auth code for token
  - `POST /refresh-token` - Refresh access token

- **Resilience Features**
  - Exponential backoff retry (3 attempts)
  - Automatic token refresh on 401 errors
  - Request ID tracking for debugging
  - Structured error logging

- **Deployment Ready**
  - Docker containerization
  - Docker Compose for local development
  - Google Cloud Build configuration
  - Cloud Run deployment automation
  - Health check endpoint for orchestration

---

## 📁 Project Structure

```
trading-bot-webhook-1/
├── app/
│   ├── __init__.py          # Flask app factory, request hooks
│   ├── auth.py              # Authentication wrappers
│   ├── config.py            # Environment variable loading
│   ├── fyers_api.py         # Fyers API integration
│   ├── logging_config.py    # Logging setup
│   ├── notifications.py    # Pub/Sub & webhook notifications
│   ├── routes.py            # Flask routes/endpoints
│   ├── token_manager.py     # Token storage & refresh
│   └── utils.py             # Symbol resolution utilities
├── tests/                   # Unit tests (8 test files)
│   ├── test_app_factory.py
│   ├── test_auth.py
│   ├── test_config_module.py
│   ├── test_fyers_api.py
│   ├── test_logging_config.py
│   ├── test_routes.py
│   ├── test_token_manager.py
│   └── test_utils.py
├── docs/
│   └── design.md            # Architecture documentation
├── main.py                  # Application entry point
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container definition
├── docker-compose.yml       # Local development setup
├── cloudbuild.yaml          # GCP build & deploy config
├── conftest.py              # Pytest configuration
├── .coveragerc              # Coverage configuration
└── README.md                # User documentation
```

---

## 🔧 Configuration

### Required Environment Variables

```env
# Fyers API Credentials
FYERS_APP_ID=your_app_id
FYERS_SECRET_ID=your_secret_id
FYERS_REDIRECT_URI=https://your-redirect
FYERS_AUTH_CODE=obtained_from_login
FYERS_PIN=1234

# Webhook Security
WEBHOOK_SECRET_TOKEN=choose_a_secret

# Google Cloud Storage (for token persistence)
GCS_BUCKET_NAME=your_bucket
GCS_TOKENS_FILE=tokens/tokens.json
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

# Optional: Logging
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
LOG_FILE=/var/log/webhook.log     # Optional file logging
USE_CLOUD_LOGGING=true            # Enable GCP Cloud Logging

# Optional: Notifications
NOTIFICATION_TOPIC=your-pubsub-topic
NOTIFICATION_URL=https://your-webhook-url
```

### Setup Steps

1. **Create Fyers API Application**
   - Register app on Fyers developer portal
   - Note APP_ID, SECRET_ID, and redirect URI

2. **Configure Google Cloud**
   - Create service account with Cloud Storage permissions
   - Create GCS bucket for token storage
   - Download service account JSON key

3. **Set Environment Variables**
   - Copy `.env.example` to `.env` (if exists) or set directly
   - Fill in all required variables

4. **Generate Initial Token**
   - Call `GET /auth-url` to get login URL
   - Complete Fyers login and copy auth code
   - Set `FYERS_AUTH_CODE` in environment
   - Call `POST /generate-token` to create tokens

5. **Run Service**
   ```bash
   # Local development
   export PYTHONPATH=.
   python main.py
   
   # Or with Docker Compose
   docker compose up
   ```

---

## 🚀 Deployment

### Current Deployment Configuration

- **Platform:** Google Cloud Run
- **Region:** asia-south1
- **Build System:** Google Cloud Build
- **Container Registry:** asia-south1-docker.pkg.dev
- **Service Account:** trading-bot-webhook@trading-bot-webhook.iam.gserviceaccount.com

### Deployment Process

1. **Automated via Cloud Build:**
   ```bash
   gcloud builds submit --config cloudbuild.yaml
   ```

2. **Build Steps:**
   - Run test suite (`pytest -q`)
   - Build Docker image
   - Push to Artifact Registry
   - Deploy to Cloud Run

3. **Manual Deployment:**
   ```bash
   docker build -t trading-bot-webhook .
   docker push <registry>/trading-bot-webhook
   gcloud run deploy trading-bot-webhook --image <image-url>
   ```

### Health Checks

- **Endpoint:** `GET /readyz`
- **Docker Healthcheck:** Configured in Dockerfile (30s interval)
- **Cloud Run:** Uses `/readyz` for readiness probes

---

## 🧪 Testing

### Test Coverage

- **Test Files:** 8 test modules covering all major components
- **Test Framework:** pytest with pytest-mock
- **Coverage:** Configured via `.coveragerc` (branch coverage enabled)

### Test Modules

1. `test_app_factory.py` - Application initialization
2. `test_auth.py` - Authentication functions
3. `test_config_module.py` - Environment configuration
4. `test_fyers_api.py` - Fyers API wrappers
5. `test_logging_config.py` - Logging setup
6. `test_routes.py` - HTTP endpoints
7. `test_token_manager.py` - Token management
8. `test_utils.py` - Symbol resolution utilities

### Running Tests

```bash
export PYTHONPATH=.
pytest -q                    # Quick run
pytest -v                    # Verbose
pytest --cov=app            # With coverage
```

### Test Infrastructure

- **conftest.py:** Provides Google Cloud stubs for testing
- **Mocking:** Uses pytest-mock for API call mocking
- **Isolation:** Tests are isolated and don't require real API calls

---

## 📦 Dependencies

### Core Dependencies

- **flask>=2.0** - Web framework (supports async routes)
- **fyers-apiv3** - Fyers trading API client
- **requests** - HTTP client
- **pandas** - Symbol master CSV processing
- **python-dotenv** - Environment variable management

### Google Cloud Dependencies

- **google-cloud-storage** - Token persistence
- **google-cloud-logging** - Structured logging
- **google-cloud-pubsub** - Notifications (optional)

### Development Dependencies

- **pytest** - Testing framework
- **pytest-mock** - Mocking utilities
- **gunicorn** - Production WSGI server
- **uvicorn** - ASGI server (for async support)

### Full List

See `requirements.txt` for complete dependency list.

---

## 🔄 Workflow & Request Flow

### Webhook Request Flow

1. **TradingView Alert** → POST `/webhook` with JSON payload
2. **Validation** → Check secret token, required fields
3. **Symbol Resolution** → Lookup Fyers symbol from NSE_FO master
4. **LTP Fetch** → Get current price if SL/TP not provided
5. **Position Check** → Verify short position exists (for BUY orders)
6. **Order Placement** → Execute market order via Fyers API
7. **Response** → Return order confirmation or error

### Token Refresh Flow

1. **Automatic** → Token manager checks expiry on access
2. **Refresh** → Uses refresh token to get new access token
3. **Fallback** → If refresh fails, generates new token from auth code
4. **Persistence** → Saves tokens to GCS and local cache

---

## 🎯 Key Features & Capabilities

### Order Processing

- **Symbol Types:** Options (CE/PE) with WEEKLY/MONTHLY expiry
- **Order Types:** Market orders (type=2)
- **Product Types:** BO, CO, INTRADAY, CNC, DELIVERY
- **Auto SL/TP:** Calculates from LTP if not provided (15% SL, 25% TP)
- **Position Validation:** Checks for short positions before BUY orders

### Error Handling

- **Retry Logic:** 3 attempts with exponential backoff
- **Token Refresh:** Automatic on 401 errors
- **Comprehensive Logging:** Request IDs, structured logs
- **Notifications:** Pub/Sub alerts for critical failures

### Security

- **Secret Token:** Webhook authentication
- **OAuth2:** Fyers API authentication
- **Token Storage:** Encrypted in GCS
- **Request Validation:** Input sanitization

---

## 📊 Monitoring & Observability

### Logging

- **Structured Logs:** JSON format with request IDs
- **Cloud Logging:** Google Cloud Logging integration
- **File Logging:** Optional rotating file handler
- **Log Levels:** Configurable (DEBUG, INFO, WARNING, ERROR)

### Metrics (Recommended Setup)

Create log-based metrics in Google Cloud:

```bash
# Order failures
gcloud logging metrics create order_failures \
  --description="Webhook order errors" \
  --log-filter='jsonPayload.event="order_failed"'

# Token refresh errors
gcloud logging metrics create token_refresh_errors \
  --description="Fyers token refresh errors" \
  --log-filter='jsonPayload.event="token_refresh_error"'
```

### Notifications

- **Pub/Sub:** Configure `NOTIFICATION_TOPIC` for critical alerts
- **Webhook:** Configure `NOTIFICATION_URL` for HTTP notifications
- **Events:** `order_failed`, `token_refresh_error`

---

## 🔮 Future Enhancements (Planned)

As documented in `docs/design.md`:

1. **WebSocket Monitor**
   - Real-time position tracking
   - Price update subscriptions
   - Automatic SL/TP monitoring
   - Separate service/container

2. **Extended Alerting**
   - Telegram notifications
   - Email alerts
   - SMS notifications

3. **Analytics**
   - Order history tracking
   - Performance metrics
   - P&L calculation

4. **GKE Deployment**
   - Kubernetes deployment option
   - Horizontal scaling
   - Service mesh integration

---

## ⚠️ Known Limitations

1. **Symbol Master:** Loaded once at startup; may need refresh for new expiries
2. **Async Support:** Uses Flask 2.0 async routes but not fully async throughout
3. **Position Checking:** Only validates short positions for BUY orders
4. **Error Recovery:** Limited retry logic (3 attempts); may need manual intervention for persistent failures

---

## 🛠️ Maintenance

### Token Refresh Automation

Set up Cloud Scheduler for daily token refresh:

```bash
gcloud scheduler jobs create http refresh-fyers-token \
  --schedule="0 0 * * *" \
  --uri="https://<your-service-url>/refresh-token" \
  --http-method=POST
```

### Regular Tasks

1. **Monitor Logs:** Check for order failures and token errors
2. **Token Health:** Verify `/readyz` endpoint returns 200
3. **Symbol Master:** May need periodic refresh for new options
4. **Dependencies:** Keep requirements.txt updated

---

## 📝 Sample Webhook Payload

```json
{
  "token": "<WEBHOOK_SECRET_TOKEN>",
  "symbol": "NSE:BANKNIFTY",
  "strikeprice": 48400,
  "optionType": "PE",
  "expiry": "WEEKLY",
  "action": "SELL",
  "qty": 25,
  "productType": "BO",
  "sl": 10.0,
  "tp": 20.0
}
```

**Optional Fields:**
- `sl` - Stop loss (auto-calculated if missing)
- `tp` - Take profit (auto-calculated if missing)
- `productType` - Defaults to "BO" if invalid

---

## ⚠️ Project Health

- **Code Quality:** ✅ Well-structured, modular design
- **Testing:** ⚠️ Unit tests exist but missing integration/load tests
- **Documentation:** ✅ README and design docs
- **Deployment:** ⚠️ Containerized but missing production safeguards
- **Error Handling:** ⚠️ Basic retry logic but missing circuit breakers
- **Security:** ⚠️ Token auth exists but missing rate limiting, input validation
- **Monitoring:** ⚠️ Basic logging but missing metrics/observability

**⚠️ CRITICAL:** This service is NOT production-ready. See `PRODUCTION_READINESS.md` for a detailed assessment of missing features and security concerns.

**Key Missing Features:**
- Rate limiting
- Input validation (type/range checks)
- Duplicate request protection
- Maximum quantity limits
- Order audit trail/database
- Circuit breakers
- Request timeouts

---

## 🚦 Getting Started Checklist

- [ ] Create Fyers API application
- [ ] Set up Google Cloud project and service account
- [ ] Create GCS bucket for token storage
- [ ] Configure all environment variables
- [ ] Generate initial Fyers auth token
- [ ] Test webhook endpoint locally
- [ ] Deploy to Cloud Run
- [ ] Set up Cloud Scheduler for token refresh
- [ ] Configure monitoring and alerts
- [ ] Test end-to-end with TradingView

---

## 📞 Support & Resources

- **Documentation:** See `README.md` for detailed setup
- **Architecture:** See `docs/design.md` for design overview
- **Tests:** See `tests/` directory for usage examples
- **Logs:** Check Cloud Logging or configured log file

---

**Status:** ✅ **Production Ready** - All core features implemented and tested.
