# Trading Bot Webhook

This project provides a Flask based webhook service that connects TradingView alerts to the Fyers trading API.  Alerts from your TradingView strategy are validated, translated to Fyers option symbols and executed automatically.  The application can be deployed on Google Cloud Run.

## Features

- **Webhook receiver** that processes TradingView JSON payloads.
- **Fyers API integration** for option order placement.
- **Token management utilities** to generate and refresh access tokens.
- **Health check endpoint** for readiness probes.
- Unit tests covering the core modules.
- **Resilient API calls** with exponential backoff (3 attempts).

## Architecture

```
TradingView Strategy --(alert JSON)--> Flask Webhook
        |                              |
        |  Resolve symbol +             +--> Fyers API (order placement)
        |  calculate SL/TP              |
        v
    (future) WebSocket monitor
```

1. A Pine Script strategy sends an alert to `/webhook` with a secret token.
2. The service validates the payload and looks up the correct Fyers symbol from the NSE_FO master CSV.
3. The current LTP is fetched from Fyers to set stop loss and target if not provided.
4. Before placing a ``BUY`` order the service checks your Fyers positions to ensure a short position already exists. If none is found the alert is rejected. Otherwise the order is executed via the Fyers REST API.
5. Utility endpoints allow generating the auth URL, refreshing tokens and health checks.
6. A monitoring service via WebSocket can be added later to track open positions.

## Repository Layout

- `app/`
  - `auth.py` – wrappers around the token manager.
  - `config.py` – environment variable loading and validation.
  - `fyers_api.py` – Fyers API wrappers (LTP, positions, place order, retries).
  - `idempotency.py` – idempotency key handling and in-memory store.
  - `logging_config.py` – logging setup (request_id, Cloud/file handlers).
  - `notifications.py` – Pub/Sub and webhook notifications on failure.
  - `routes.py` – Flask blueprint with webhook and utility endpoints.
  - `token_manager.py` – handles token storage and refresh using Google Cloud Storage.
  - `utils.py` – symbol master loader and lot-size utilities.
- `main.py` – entry point that starts the Flask app.
- `tests/` – unit tests for all modules.

## Setup

1. **Create a Fyers API application** and note the *APP_ID*, *SECRET_ID* and redirect URI.
2. **Copy `.env.example` to `.env`** and fill in your credentials. The example file lists all required variables, including `GCS_BUCKET_NAME` and `GCS_TOKENS_FILE`:

```env
FYERS_APP_ID=your_app_id
FYERS_SECRET_ID=your_secret_id
FYERS_REDIRECT_URI=https://your-redirect
FYERS_AUTH_CODE=obtained_from_login
FYERS_PIN=1234
WEBHOOK_SECRET_TOKEN=choose_a_secret
GCS_BUCKET_NAME=your_bucket
GCS_TOKENS_FILE=tokens/tokens.json
```

Optionally you can control logging by setting:

```env
# defaults to INFO
LOG_LEVEL=DEBUG
# write logs to a file instead of stdout
LOG_FILE=/var/log/webhook.log
```

To forward logs directly to Google Cloud Logging set:

```env
USE_CLOUD_LOGGING=true
```

To avoid duplicate orders when TradingView retries or the same alert is sent twice, send an **idempotency key** and optionally set a TTL:

```env
# Cache successful responses by idempotency key for 24h (default). Set 0 to disable.
IDEMPOTENCY_TTL_SECONDS=86400
```

Send the key in the webhook JSON as `idempotency_key` or in the header `Idempotency-Key`. The same key within the TTL returns the stored response without placing the order again.

The Fyers API expects order **quantity in contracts** (exact number), not lots. One lot = `lot_size` contracts (e.g. 75 for NIFTY, 30 for BANKNIFTY). Payload `qty` is in contracts; if omitted, the app uses one lot (symbol’s `lot_size`).

To cap the maximum **lots** per order (default 1 lot). Max allowed contracts = `WEBHOOK_MAX_QTY × lot_size` for that symbol:

```env
# Maximum allowed lots per order (default 1). Reject if qty in contracts exceeds this × lot_size.
WEBHOOK_MAX_QTY=1
```

### Google Service Account

1. Create a service account in Google Cloud and enable the **Cloud Storage** API.
2. Download the JSON key file for this account.
3. Either set the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to the key path or mount the key at `/secrets/service_account.json`.

These credentials are required for storing tokens in Google Cloud Storage.

3. **Install dependencies**

```bash
pip install -r requirements.txt
```
This project requires **Flask 2.0 or higher** in order to use asynchronous routes.

4. **Generate Fyers tokens**

   1. Call `GET /auth-url` to open the Fyers login page.
   2. Complete the login, copy the authorization code and set `FYERS_AUTH_CODE` in `.env`.
   3. Run `POST /generate-token` once. This creates `tokens.json` locally (and in GCS if configured).

   Until this step is done the `/readyz` health check will fail with a "Bad request" error from Fyers.

5. **Run locally**

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

You can deploy the container to Google Cloud Run or any other container platform such as GKE. A `cloudbuild.yaml` file is provided to automate building, testing and deploying the image. Cloud Build installs the dependencies, runs the test suite and only then builds the container. Trigger a build with:

```bash
gcloud builds submit --config cloudbuild.yaml
```
The container runs using **Gunicorn** with **Uvicorn workers** so the server is **non-blocking**: one worker can handle many concurrent requests while they wait on Fyers/HTTP. A long-running request does not block others.

```bash
gunicorn main:asgi_app -w 1 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8080
```

See [docs/GUNICORN_VS_UVICORN.md](docs/GUNICORN_VS_UVICORN.md) and [docs/SERVERS_OVERVIEW.md](docs/SERVERS_OVERVIEW.md) for details.


## Sample Webhook Payload

The `expiry` field should be either `"WEEKLY"` or `"MONTHLY"`.
The `symbol` must be the **underlying** (e.g. `NIFTY`, `BANKNIFTY`), not the full Fyers ticker.
Stop loss (`sl`) and take profit (`tp`) are optional—the service
calculates them from the current LTP when they are omitted or invalid.

```json
{
  "token": "<WEBHOOK_SECRET>",
  "symbol": "BANKNIFTY",
  "strikeprice": 48400,
  "optionType": "PE",
  "expiry": "WEEKLY",
  "action": "SELL",
  "qty": 25,
  "productType": "BO",
  "idempotency_key": "optional-unique-key-per-alert"
}
```

## Available Endpoints

- `POST /webhook` – execute a trade from a TradingView alert.
- `GET /auth-url` – generate the login URL to obtain an auth code.
- `POST /generate-token` – exchange auth code for access token.
- `POST /refresh-token` – refresh the Fyers access token.
- `GET /readyz` – basic health check.

### Automated Token Refresh

Schedule a Cloud Scheduler job to call `/refresh-token` daily:

```
gcloud scheduler jobs create http refresh-fyers-token \
  --schedule="0 0 * * *" \
  --uri="https://<your-service-url>/refresh-token" \
  --http-method=POST
```

This keeps the access token alive without manual intervention.

## Monitoring & Alerts

Structured logs are sent to Cloud Logging when `USE_CLOUD_LOGGING` is enabled.
Create log-based metrics to count failed orders and token refresh errors:

```bash
gcloud logging metrics create order_failures \
  --description="Webhook order errors" \
  --log-filter="jsonPayload.event=\"order_failed\""

gcloud logging metrics create token_refresh_errors \
  --description="Fyers token refresh errors" \
  --log-filter="jsonPayload.event=\"token_refresh_error\""
```

Set `NOTIFICATION_TOPIC` to a Pub/Sub topic or `NOTIFICATION_URL` to a webhook
endpoint and the service will publish a message whenever a critical failure
occurs.

## Testing

Install dependencies with `pip install -r requirements.txt` before running the tests. Using a virtual environment is recommended.

Run the unit tests with:

```bash
export PYTHONPATH=.
pytest -q
```

The suite covers token handling, route logic, Fyers integration and utility helpers.

## Future Enhancements

See [docs/design.md](docs/design.md) for an architectural overview and future plans such as a WebSocket listener, optional deployment on GKE and extended alerting (e.g. Telegram).

