from flask import Flask, g, request
from app.routes import webhook_bp
from app.config import load_env_variables
from app.logging_config import request_id_extra
import logging
import os
import time
import uuid

logger = logging.getLogger(__name__)


def create_app():
    load_env_variables()
    app = Flask(__name__)
    app.register_blueprint(webhook_bp)

    @app.before_request
    def _start_timer():
        g.request_id = str(uuid.uuid4())
        g.start_time = time.perf_counter()

    @app.after_request
    def _log_request(response):
        duration = time.perf_counter() - getattr(g, "start_time", time.perf_counter())
        logger.info(
            "%s %s %s %.4fs",
            request.method,
            request.path,
            response.status_code,
            duration,
            extra=request_id_extra(),
        )
        return response

    return app
