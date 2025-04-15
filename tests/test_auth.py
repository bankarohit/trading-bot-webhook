import unittest
from unittest.mock import patch, mock_open, MagicMock
from app import auth

class TestAuthTokenLogic(unittest.TestCase):

    @patch("app.auth.open", new_callable=mock_open, read_data='{"access_token": "abc", "refresh_token": "xyz"}')
    @patch("app.auth.os.path.exists", return_value=True)
    def test_load_tokens(self, mock_exists, mock_file):
        tokens = auth.load_tokens()
        self.assertEqual(tokens["access_token"], "abc")

    @patch("app.auth.open", new_callable=mock_open)
    def test_save_tokens(self, mock_file):
        sample = {"access_token": "abc", "refresh_token": "xyz"}
        auth.save_tokens(sample)
        mock_file.assert_called_once_with("tokens.json", "w")

    @patch("app.auth.refresh_access_token")
    @patch("app.auth.load_tokens", return_value={})
    def test_get_access_token_refresh(self, mock_load, mock_refresh):
        mock_refresh.return_value = "new_token"
        token = auth.get_access_token()
        self.assertEqual(token, "new_token")

    @patch("app.auth.fyersModel.SessionModel")
    def test_generate_tokens_from_auth_code(self, mock_session):
        os.environ["FYERS_AUTH_CODE"] = "authcode"
        session_instance = MagicMock()
        session_instance.generate_token.return_value = {"access_token": "abc"}
        mock_session.return_value = session_instance
        token = auth.generate_tokens_from_auth_code()
        self.assertEqual(token, "abc")

    @patch("app.auth.load_tokens", return_value={"refresh_token": "ref"})
    @patch("app.auth.fyersModel.SessionModel")
    def test_refresh_access_token_success(self, mock_session, mock_load):
        session_instance = MagicMock()
        session_instance.generate_token.return_value = {"access_token": "abc"}
        mock_session.return_value = session_instance
        token = auth.refresh_access_token()
        self.assertEqual(token, "abc")
    unittest.main()

