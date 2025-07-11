import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Ensure the application package is importable and required env vars are set
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

from app import auth
from app.token_manager import AuthCodeMissingError, RefreshTokenError

class TestAuth(unittest.TestCase):

    @patch("app.auth.get_token_manager")
    def test_get_access_token_success(self, mock_get_mgr):
        manager = MagicMock()
        manager.get_access_token.return_value = "abc123"
        mock_get_mgr.return_value = manager

        token = auth.get_access_token()
        self.assertEqual(token, "abc123")

    @patch("app.auth.get_token_manager")
    def test_get_access_token_failure(self, mock_get_mgr):
        manager = MagicMock()
        manager.get_access_token.return_value = None
        mock_get_mgr.return_value = manager

        with self.assertRaises(AuthCodeMissingError):
            auth.get_access_token()

    @patch("app.auth.get_token_manager")
    def test_refresh_access_token_success(self, mock_get_mgr):
        manager = MagicMock()
        manager.refresh_token.return_value = "refreshed123"
        mock_get_mgr.return_value = manager

        token = auth.refresh_access_token()
        self.assertEqual(token, "refreshed123")

    @patch("app.auth.get_token_manager")
    def test_refresh_access_token_failure(self, mock_get_mgr):
        manager = MagicMock()
        manager.refresh_token.side_effect = RefreshTokenError("Simulated failure")
        mock_get_mgr.return_value = manager

        with self.assertRaises(RefreshTokenError):
            auth.refresh_access_token()

    @patch("app.auth.get_token_manager")
    def test_get_auth_code_url(self, mock_get_mgr):
        manager = MagicMock()
        manager.get_auth_code_url.return_value = "https://fyers-auth.url"
        mock_get_mgr.return_value = manager

        url = auth.get_auth_code_url()
        self.assertIn("https://", url)

    @patch("app.auth.get_token_manager")
    def test_get_fyers_success(self, mock_get_mgr):
        client = MagicMock()
        manager = MagicMock()
        manager.get_fyers_client.return_value = client
        mock_get_mgr.return_value = manager

        result = auth.get_fyers()
        self.assertEqual(result, client)

    @patch("app.auth.get_token_manager")
    def test_get_fyers_failure(self, mock_get_mgr):
        manager = MagicMock()
        manager.get_fyers_client.side_effect = Exception("fail")
        mock_get_mgr.return_value = manager

        with self.assertRaises(Exception):
            auth.get_fyers()

    @patch("app.auth.get_token_manager")
    def test_get_auth_code_url_exception(self, mock_get_mgr):
        manager = MagicMock()
        manager.get_auth_code_url.side_effect = Exception("boom")
        mock_get_mgr.return_value = manager

        with self.assertRaises(Exception):
            auth.get_auth_code_url()

    @patch("app.auth.get_token_manager")
    def test_refresh_access_token_general_exception(self, mock_get_mgr):
        manager = MagicMock()
        manager.refresh_token.side_effect = Exception("oops")
        mock_get_mgr.return_value = manager

        with self.assertRaises(Exception):
            auth.refresh_access_token()

    @patch("app.auth.get_token_manager")
    def test_generate_access_token_none(self, mock_get_mgr):
        manager = MagicMock()
        manager.generate_token.return_value = None
        mock_get_mgr.return_value = manager

        token = auth.generate_access_token()
        self.assertIsNone(token)
        manager.generate_token.assert_called_once()

    @patch("app.auth.get_token_manager")
    def test_generate_access_token_exception(self, mock_get_mgr):
        manager = MagicMock()
        manager.generate_token.side_effect = Exception("err")
        mock_get_mgr.return_value = manager

        with self.assertRaises(Exception):
            auth.generate_access_token()
        manager.generate_token.assert_called_once()

if __name__ == '__main__':
    unittest.main()
