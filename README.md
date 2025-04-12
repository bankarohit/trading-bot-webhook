# Fyers Webhook Trading Bot

This is a Flask-based webhook server designed for Cloud Run that listens for TradingView alerts and places option orders via the Fyers API.

## 🔧 Setup Instructions

1. Create a Fyers API App and get:
   - App ID
   - Secret ID
   - Redirect URI
   - Authorization Code

2. Paste these into a `.env` file based on `.env.example`.

3. Push this project to GitHub.

4. Deploy using **Google Cloud Run**:
   - Source: GitHub repo
   - Port: 8080
   - Allow unauthenticated requests

5. Use the Cloud Run URL as your **Webhook URL** in TradingView.

## 📬 Sample Payload (TradingView Alert)

```
{
  "token": "your_secret_token",
  "index": "NIFTY",
  "option_type": "CE",
  "qty": 50,
  "action": "BUY"
}
```
# rebuild
# rebuild
