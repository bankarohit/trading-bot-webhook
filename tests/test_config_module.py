import os
import sys
import unittest
from unittest.mock import patch

# Ensure the application package is importable
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import load_env_variables


class TestConfigModule(unittest.TestCase):
    @patch("app.config.load_dotenv")
    def test_load_env_variables_success(self, mock_load):
        env = {
            "FYERS_APP_ID": "id",
            "FYERS_SECRET_ID": "secret",
            "FYERS_REDIRECT_URI": "http://localhost",
            "WEBHOOK_SECRET_TOKEN": "token",
            "FYERS_PIN": "1234",
            "FYERS_AUTH_CODE": "code",
        }
        with patch.dict(os.environ, env, clear=True):
            # Should not raise when all variables are present
            load_env_variables()

    @patch("app.config.load_dotenv")
    def test_load_env_variables_missing_var(self, mock_load):
        env = {
            "FYERS_APP_ID": "id",
            "FYERS_SECRET_ID": "secret",
            "FYERS_REDIRECT_URI": "http://localhost",
            "WEBHOOK_SECRET_TOKEN": "token",
            "FYERS_PIN": "1234",
            # FYERS_AUTH_CODE intentionally omitted
        }
        with patch.dict(os.environ, env, clear=True):
            with self.assertRaises(EnvironmentError) as cm:
                load_env_variables()
            self.assertIn("FYERS_AUTH_CODE", str(cm.exception))


if __name__ == "__main__":
    unittest.main()
