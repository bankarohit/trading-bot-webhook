from flask import Flask, g, request
from app.routes import webhook_bp
from app.config import load_env_variables
import logging
import time
import uuid

logger = logging.getLogger(__name__)


def create_app():
    load_env_variables()
    app = Flask(__name__)

    def before_request():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.time()

    def after_request(response):
        duration = time.time() - getattr(g, "start_time", time.time())
        logger.info(
            "%s %s -> %s in %.2fs",
            request.method,
            request.path,
            response.status_code,
            duration,
            extra={"request_id": g.request_id},
        )
        return response

    app.before_request(before_request)
    app.after_request(after_request)

    app.register_blueprint(webhook_bp)
    logger.info("Application initialized")
    return app