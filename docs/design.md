# Architecture Design

This document gives an overview of the webhook service and planned extensions.

## Overview

The application exposes a Flask API that receives alerts from TradingView and translates them into orders on the Fyers trading platform. Authentication tokens are stored in Google Cloud Storage so that multiple services can share credentials.

```
TradingView --(alert JSON)--> Flask Webhook --(REST)--> Fyers API
      |                             |
      |  Symbol lookup + SL/TP calc  |
      |                              v
      +--> Token storage (GCS)   (future) WebSocket monitor
```

### Components

- **`app/__init__.py`** – application factory configuring request hooks and registering routes.
- **`app/routes.py`** – HTTP endpoints including `/webhook`, `/refresh-token` and utilities.
- **`app/auth.py`** and **`app/token_manager.py`** – handle OAuth flow and persist tokens in GCS.
- **`app/fyers_api.py`** – thin wrappers around Fyers REST methods for fetching LTP and placing orders.
- **`app/utils.py`** – loads the NSE option master file and resolves symbols and lot sizes.
- **`main.py`** – entry point used by development and Gunicorn.

## Request Flow

1. A TradingView strategy sends a POST request to `/webhook` with a secret token and order details.
2. The service validates the payload, resolves the option symbol and derives stop loss or take profit from the latest price when required.
3. The Fyers API is called to place the order. Responses are logged with a request identifier.
4. Auxiliary endpoints allow generating auth URLs and refreshing or creating tokens.

## WebSocket Monitoring (Planned)

A future enhancement is a background service that connects to the Fyers WebSocket API. This monitor will subscribe to symbols for active positions, record price updates and optionally trigger alerts when targets or stop losses are hit. The monitor can run in a separate process or container but reuse the same credentials through `token_manager`. Collected events could be forwarded to messaging platforms or stored for analytics.
