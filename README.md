# Trading Bot Webhook

This project provides a Flask based webhook service that connects TradingView alerts to the Fyers trading API.  Alerts from your TradingView strategy are validated, translated to Fyers option symbols and executed automatically.  All trades are recorded in Google Sheets and the application can be deployed on Google Cloud Run.

## Features

- **Webhook receiver** that processes TradingView JSON payloads.
- **Fyers API integration** for option order placement.
- **Google Sheets logging** of every executed trade.
- **Token management utilities** to generate and refresh access tokens.
- **Health check endpoint** for readiness probes.
- Unit tests covering the core modules.

## Architecture

```
TradingView Strategy --(alert JSON)--> Flask Webhook
        |                              |
        |  Resolve symbol +             +--> Fyers API (order placement)
        |  calculate SL/TP              |
        |                              +--> Google Sheets (trade log)
        v
    (future) WebSocket monitor
```

1. A Pine Script strategy sends an alert to `/webhook` with a secret token.
2. The service validates the payload and looks up the correct Fyers symbol from the NSE_FO master CSV.
3. The current LTP is fetched from Fyers to set stop loss and target if not provided.
4. The order is placed using the Fyers REST API and the details are logged to Google Sheets.
5. Utility endpoints allow generating the auth URL, refreshing tokens and health checks.
6. A monitoring service via WebSocket can be added later to track open positions.

## Repository Layout

- `app/`
  - `auth.py` – wrappers around the token manager.
  - `routes.py` – Flask blueprint with webhook and utility endpoints.
  - `token_manager.py` – handles token storage and refresh using Google Cloud Storage.
  - `utils.py` – symbol master loader and Google Sheets helpers.
- `main.py` – entry point that starts the Flask app.
- `tests/` – unit tests for all modules.

## Setup

1. **Create a Fyers API application** and note the *APP_ID*, *SECRET_ID* and redirect URI.
2. **Copy `.env.example` to `.env`** and fill in your credentials. The example file lists all required variables:

```env
FYERS_APP_ID=your_app_id
FYERS_SECRET_ID=your_secret_id
FYERS_REDIRECT_URI=https://your-redirect
FYERS_AUTH_CODE=obtained_from_login
FYERS_PIN=1234
WEBHOOK_SECRET_TOKEN=choose_a_secret
GOOGLE_SHEET_ID=your_google_sheet_id
GCS_BUCKET_NAME=your_bucket
GCS_TOKENS_FILE=tokens/tokens.json
```

`GCS_BUCKET_NAME` sets the Google Cloud Storage bucket used for token storage.
`GCS_TOKENS_FILE` is the object path inside that bucket where `tokens.json` is
saved.

3. **Install dependencies**

```bash
pip install -r requirements.txt
```

4. **Run locally**

```bash
export PYTHONPATH=.
python main.py
```

The service will start on port `8080`.

Alternatively you can spin up the app using Docker Compose:

```bash
docker compose up
```

## Deployment

You can deploy the container to Google Cloud Run or any other container platform such as GKE. A `cloudbuild.yaml` file is provided to automate building and deploying the image. Run the following command:

```bash
gcloud builds submit --config cloudbuild.yaml
```

## Sample Webhook Payload

```json
{
  "token": "<WEBHOOK_SECRET>",
  "symbol": "NSE:BANKNIFTY",
  "strikeprice": 48400,
  "optionType": "PE",
  "expiry": "2025-05-22",
  "action": "SELL",
  "qty": 25,
  "sl": 50,
  "tp": 100,
  "productType": "BO"
}
```

## Available Endpoints

- `POST /webhook` – execute a trade from a TradingView alert.
- `GET /auth-url` – generate the login URL to obtain an auth code.
- `POST /generate-token` – exchange auth code for access token.
- `POST /refresh-token` – refresh the Fyers access token.
- `GET /readyz` – basic health check.

## Testing

Run the unit tests with:

```bash
export PYTHONPATH=.
pytest -q
```

The suite covers token handling, route logic, Fyers integration and utility helpers.

## Future Enhancements

The design document outlines additional components such as a WebSocket listener to update trade status in Google Sheets, plus optional deployment on GKE or extended alerting (e.g. Telegram).  These can be built on top of the core webhook service contained here.

