# ------------------ tests/test_auth.py ------------------
import unittest
from unittest.mock import patch, MagicMock
from app import auth
from app.token_manager import AuthCodeMissingError, RefreshTokenError

class TestAuth(unittest.TestCase):

    @patch("app.auth._token_manager.get_access_token", return_value="abc123")
    def test_get_access_token_success(self, mock_get):
        token = auth.get_access_token()
        self.assertEqual(token, "abc123")

    @patch("app.auth._token_manager.get_access_token", return_value=None)
    def test_get_access_token_failure(self, mock_get):
        with self.assertRaises(AuthCodeMissingError):
            auth.get_access_token()

    @patch("app.auth._token_manager.refresh_token", return_value="refreshed123")
    def test_refresh_access_token_success(self, mock_refresh):
        token = auth.refresh_access_token()
        self.assertEqual(token, "refreshed123")

    @patch("app.auth._token_manager.refresh_token", side_effect=RefreshTokenError("Simulated failure"))
    def test_refresh_access_token_failure(self, mock_refresh):
        with self.assertRaises(RefreshTokenError):
            auth.refresh_access_token()

    @patch("app.auth._token_manager.get_auth_code_url", return_value="https://fyers-auth.url")
    def test_get_auth_code_url(self, mock_url):
        url = auth.get_auth_code_url()
        self.assertIn("https://", url)

    @patch("app.auth._token_manager.get_fyers_client")
    def test_get_fyers_success(self, mock_fyers):
        client = MagicMock()
        mock_fyers.return_value = client
        result = auth.get_fyers()
        self.assertEqual(result, client)

    @patch("app.auth._token_manager.get_fyers_client", side_effect=Exception("fail"))
    def test_get_fyers_failure(self, mock_fyers):
        with self.assertRaises(Exception):
            auth.get_fyers()

if __name__ == '__main__':
    unittest.main()
