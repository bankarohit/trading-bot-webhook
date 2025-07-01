import os
import sys
import unittest
from unittest.mock import patch, MagicMock
from flask import Blueprint, Flask

# Ensure the application package is importable and env vars exist
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

from app import create_app


class TestAppFactory(unittest.TestCase):
    @patch("app.load_env_variables")
    def test_create_app_registers_blueprint_and_hooks(self, mock_load_env):
        test_bp = Blueprint("test", __name__)

        @test_bp.route("/ping")
        def ping():
            return "pong"

        with patch("app.webhook_bp", test_bp), \
             patch("app.logger") as mock_logger:
            app = create_app()
            self.assertIsInstance(app, Flask)
            self.assertIn("test", app.blueprints)

            client = app.test_client()
            response = client.get("/ping")
            self.assertEqual(response.status_code, 200)

            # Verify after_request logged with request_id
            has_request_id = any(
                kwargs.get("extra") and "request_id" in kwargs["extra"]
                for _, kwargs in mock_logger.info.call_args_list
            )
            self.assertTrue(has_request_id)

        mock_load_env.assert_called_once()


if __name__ == "__main__":
    unittest.main()
