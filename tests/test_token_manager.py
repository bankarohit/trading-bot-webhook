# ------------------ tests/test_token_manager.py ------------------
import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
from app.token_manager import TokenManager, AuthCodeMissingError, RefreshTokenError

class TestTokenManager(unittest.TestCase):

    @patch("builtins.open", new_callable=mock_open, read_data='{"access_token": "abc", "refresh_token": "xyz"}')
    @patch("os.path.exists", return_value=True)
    def test_load_tokens_success(self, mock_exists, mock_file):
        manager = TokenManager()
        self.assertEqual(manager._tokens["access_token"], "abc")

    @patch("builtins.open", new_callable=mock_open)
    def test_save_tokens_success(self, mock_file):
        manager = TokenManager()
        manager._tokens = {"access_token": "abc"}
        manager._save_tokens()
        mock_file.assert_any_call("tokens.json", "w")

    def test_get_auth_code_url_returns_url(self):
        manager = TokenManager()
        url = manager.get_auth_code_url()
        self.assertTrue("https://" in url)

    @patch("app.token_manager.AUTH_CODE", new=None)
    def test_generate_token_missing_auth_code(self):
        manager = TokenManager()
        with self.assertRaises(AuthCodeMissingError):
            manager.generate_token()

    @patch("app.token_manager.TokenManager._save_tokens")
    @patch("app.token_manager.TokenManager._init_session_model")
    def test_generate_token_success(self, mock_session_init, mock_save):
        mock_session = MagicMock()
        mock_session.generate_token.return_value = {"access_token": "abc"}
        mock_session_init.return_value = mock_session

        with patch("app.token_manager.AUTH_CODE", "dummy_auth_code"):
            manager = TokenManager()
            manager._session = mock_session
            token = manager.generate_token()
            self.assertEqual(token, "abc")

    def test_refresh_token_missing_values(self):
        manager = TokenManager()
        manager._tokens = {}
        with self.assertRaises(RefreshTokenError):
            manager.refresh_token()

    @patch("requests.post")
    def test_refresh_token_success(self, mock_post):
        mock_post.return_value.json.return_value = {"s": "ok", "access_token": "new_token"}
        manager = TokenManager()
        manager._tokens = {"refresh_token": "ref"}

        with patch("app.token_manager.FYERS_PIN", "1234"):
            token = manager.refresh_token()
            self.assertEqual(token, "new_token")

    @patch("app.token_manager.TokenManager.get_access_token", return_value="token")
    def test_get_fyers_client_lazy_init(self, mock_token):
        manager = TokenManager()
        fyers = manager.get_fyers_client()
        self.assertTrue(hasattr(fyers, "get_profile"))  # FyersModel should have this method

if __name__ == '__main__':
    unittest.main()
