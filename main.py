"""Application entry point for the trading bot webhook service.

This module prepares the environment, sets up logging and creates the
Flask application instance. When run directly it starts the server on
``0.0.0.0:8080`` so that TradingView alerts can be processed.
"""

from app import create_app
from app.config import load_env_variables
from app.logging_config import configure_logging
from uvicorn.middleware.wsgi import WSGIMiddleware

load_env_variables()
configure_logging()

app = create_app()
asgi_app = WSGIMiddleware(app)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
