# ------------------ app/__init__.py ------------------
from flask import Flask
from app.routes import webhook_bp
from app.config import load_env_variables

def create_app():
    load_env_variables()
    app = Flask(__name__)
    app.register_blueprint(webhook_bp)
    return app