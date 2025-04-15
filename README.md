### ----------------------------- README.md -----------------------------
# Fyers Webhook Trading Bot

A Flask-based webhook listener for TradingView alerts that places option orders on Fyers.
Deployed on **Google Cloud Run**.

## 🚀 Features
- ✅ Webhook listener for TradingView alerts
- ✅ Auto-refresh of Fyers access token using refresh_token
- ✅ Real-time symbol resolution using Fyers NSE_FO.csv
- ✅ Accurate expiry detection (WEEKLY/MONTHLY)
- ✅ Google Sheets integration to log trades
- ✅ Healthcheck, token utilities, and modular code
- ✅ Unit tests with 100% coverage

## 🛠 Setup Instructions

### 🔑 Step 1: Create Fyers API App
- Register at Fyers developer console
- Obtain `APP_ID`, `SECRET_ID`, and set `REDIRECT_URI`

### 🔐 Step 2: `.env` Variables
Create a `.env` file:
```
FYERS_APP_ID=...
FYERS_SECRET_ID=...
FYERS_REDIRECT_URI=...
WEBHOOK_SECRET_TOKEN=...
GOOGLE_SHEET_ID=...
```

### 🔁 Step 3: Get Your Auth Code
Visit:
```
GET /auth-url
```
Use the returned URL to log in → copy the `auth_code` param → paste into `.env` as `FYERS_AUTH_CODE`.

### ☁️ Step 4: Deploy to Cloud Run
```bash
gcloud builds submit --config cloudbuild.yaml
```
Use the generated URL as your webhook endpoint in TradingView.

## 📬 Sample TradingView Webhook
```json
{
  "token": "<secretToken>",
  "symbol": "NIFTY", 
  "strikeprice": 23000,
  "optionType": "PE",
  "action": "SELL",
  "expiry": "WEEKLY"
}
```

## 📦 Endpoints
- `POST /webhook` → Execute trade based on alert
- `GET /auth-url` → Get Fyers login URL
- `POST /refresh-token` → Refresh expired token
- `GET /readyz` → Health check

## 🧪 Testing
```bash
pytest tests/
```
Covers: token management, webhook, utils, expiry detection



