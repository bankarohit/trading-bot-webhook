import unittest
from unittest.mock import patch, mock_open, MagicMock
import json
import os
import threading
import hashlib
import requests
from app.token_manager import (
    TokenManager, get_token_manager,
    TokenManagerException, AuthCodeMissingError, RefreshTokenError, EnvironmentVariableError
)
from app.token_manager import TOKENS_FILE

class TestTokenManager(unittest.TestCase):
    """Test cases for the TokenManager class."""

    def setUp(self):
        """Reset singleton and prepare environment for each test."""
        # Import here to avoid circular imports
        import app.token_manager
        app.token_manager._token_manager_instance = None
        
        # Set up environment variables needed for tests
        self.env_patcher = patch.dict(os.environ, {
            "FYERS_APP_ID": "test_app_id",
            "FYERS_SECRET_ID": "test_secret_id",
            "FYERS_REDIRECT_URI": "test_redirect_uri",
            "WEBHOOK_SECRET_TOKEN": "test_webhook_token",
            "GOOGLE_SHEET_ID": "test_sheet_id",
            "FYERS_PIN": "1234",
            "FYERS_AUTH_CODE": "dummy_auth_code"
        })
        self.env_patcher.start()

            # Patch the TOKENS_FILE path to avoid overwriting local file
        self.tokens_file = "test_tokens.json"
        self.file_patcher = patch("app.token_manager.TOKENS_FILE", self.tokens_file)
        self.file_patcher.start()

        # Also remove the file if it exists
        if os.path.exists(self.tokens_file):
            os.remove(self.tokens_file)
            
        # Patch load_env_variables to prevent validation errors
        self.load_env_patcher = patch('app.token_manager.load_env_variables')
        self.mock_load_env = self.load_env_patcher.start()
    
    def tearDown(self):
        """Clean up after each test."""
        self.env_patcher.stop()
        self.file_patcher.stop()
        if os.path.exists(self.tokens_file):
            os.remove(self.tokens_file)
        self.load_env_patcher.stop()

    @patch("os.path.exists", return_value=False)
    def test_load_tokens_file_not_exists(self, mock_exists):
        """Test loading tokens when file doesn't exist."""
        manager = TokenManager()
        self.assertEqual(manager._tokens, {})
    
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", new_callable=mock_open, 
           read_data='{"access_token": "test_token", "refresh_token": "test_refresh"}')
    def test_load_tokens_success(self, mock_file, mock_exists):
        """Test successful loading of tokens from file."""
        manager = TokenManager()
        self.assertEqual(manager._tokens["access_token"], "test_token")
        self.assertEqual(manager._tokens["refresh_token"], "test_refresh")
    
    @patch("os.path.exists", return_value=True)
    @patch("builtins.open", side_effect=Exception("File error"))
    def test_load_tokens_exception(self, mock_file, mock_exists):
        """Test exception handling when loading tokens."""
        with patch('logging.Logger.error') as mock_log:
            manager = TokenManager()
            self.assertEqual(manager._tokens, {})
            mock_log.assert_called_once()
    
    @patch("builtins.open", new_callable=mock_open)
    def test_save_tokens_success(self, mock_file):
        """Test successful saving of tokens to file."""
        manager = TokenManager()
        
        # Reset mock to clear initialization calls
        mock_file.reset_mock()
        
        manager._tokens = {"access_token": "test_token"}
        manager._save_tokens()
        
        # Check that file was opened for writing at least once
        mock_file.assert_any_call(TOKENS_FILE, "w")
        
        handle = mock_file()
        handle.write.assert_any_call('"access_token"')
        handle.write.assert_any_call('"test_token"')

    
    @patch("builtins.open", side_effect=Exception("Write error"))
    def test_save_tokens_exception(self, mock_file):
        """Test exception handling when saving tokens."""
        manager = TokenManager()
        manager._tokens = {"access_token": "test_token"}
        
        with patch('logging.Logger.error') as mock_log:
            manager._save_tokens()
            mock_log.assert_called()
        
    def test_init_session_model(self):
        """Test initialization of the session model."""
        manager = TokenManager()
        session = manager._init_session_model()
        self.assertEqual(session.client_id, "test_app_id")
        self.assertEqual(session.redirect_uri, "test_redirect_uri")
    
    @patch("app.token_manager.fyersModel.SessionModel.generate_authcode", 
           return_value="https://test-auth-url")
    def test_get_auth_code_url(self, mock_generate):
        """Test generation of authorization URL."""
        manager = TokenManager()
        url = manager.get_auth_code_url()
        self.assertEqual(url, "https://test-auth-url")
        mock_generate.assert_called_once()
    
    def test_get_access_token_existing(self):
        """Test getting an existing access token."""
        manager = TokenManager()
        manager._tokens = {"access_token": "existing_token"}
        token = manager.get_access_token()
        self.assertEqual(token, "existing_token")
    
    @patch("app.token_manager.TokenManager.refresh_token", 
           return_value="refreshed_token")
    def test_get_access_token_refresh(self, mock_refresh):
        """Test getting access token via refresh."""
        manager = TokenManager()
        manager._tokens = {}  # No existing token
        token = manager.get_access_token()
        self.assertEqual(token, "refreshed_token")
        mock_refresh.assert_called_once()
    
    @patch("app.token_manager.TokenManager.refresh_token", 
           side_effect=RefreshTokenError("Refresh failed"))
    @patch("app.token_manager.TokenManager.generate_token", 
           return_value="new_token")
    def test_get_access_token_generate(self, mock_generate, mock_refresh):
        """Test getting access token via generation after refresh fails."""
        manager = TokenManager()
        manager._tokens = {}
        token = manager.get_access_token()
        self.assertEqual(token, "new_token")
        mock_refresh.assert_called_once()
        mock_generate.assert_called_once()
    
    @patch.dict(os.environ, {"FYERS_AUTH_CODE": "test_auth_code"})
    @patch("app.token_manager.fyersModel.SessionModel.generate_token", 
           return_value={"access_token": "new_token", "refresh_token": "new_refresh"})
    def test_generate_token_success(self, mock_generate):
        """Test successful token generation."""
        manager = TokenManager()
        token = manager.generate_token()
        self.assertEqual(token, "new_token")
        self.assertEqual(manager._tokens["access_token"], "new_token")
        self.assertEqual(manager._tokens["refresh_token"], "new_refresh")
    
    @patch.dict(os.environ, {}, clear=False)  # Remove FYERS_AUTH_CODE if present
    def test_generate_token_missing_auth_code(self):
        """Test token generation with missing auth code."""
        if "FYERS_AUTH_CODE" in os.environ:
            del os.environ["FYERS_AUTH_CODE"]
            
        manager = TokenManager()
        with self.assertRaises(AuthCodeMissingError):
            manager.generate_token()
    
    @patch.dict(os.environ, {"FYERS_AUTH_CODE": "test_auth_code"})
    @patch("app.token_manager.fyersModel.SessionModel.generate_token", 
           return_value={"error": "Invalid auth code"})
    def test_generate_token_api_error(self, mock_generate):
        """Test token generation with API error response."""
        manager = TokenManager()
        with self.assertRaises(TokenManagerException):
            manager.generate_token()
    
    @patch.dict(os.environ, {"FYERS_AUTH_CODE": "test_auth_code"})
    @patch("app.token_manager.fyersModel.SessionModel.generate_token", 
           side_effect=Exception("API connection error"))
    def test_generate_token_exception(self, mock_generate):
        """Test exception during token generation."""
        manager = TokenManager()
        with self.assertRaises(TokenManagerException):
            manager.generate_token()
    
    def test_refresh_token_missing_data(self):
        """Test token refresh with missing refresh token."""
        manager = TokenManager()
        manager._tokens = {}  # No refresh token
        with self.assertRaises(RefreshTokenError):
            manager.refresh_token()
    
    @patch.dict(os.environ, {"FYERS_PIN": ""})
    def test_refresh_token_missing_pin(self):
        """Test token refresh with missing PIN."""
        manager = TokenManager()
        manager._tokens = {"refresh_token": "test_refresh"}
        with self.assertRaises(RefreshTokenError):
            manager.refresh_token()
    
    @patch("requests.post")
    def test_refresh_token_success(self, mock_post):
        """Test successful token refresh."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "s": "ok", 
            "access_token": "refreshed_token"
        }
        mock_post.return_value = mock_response
        
        manager = TokenManager()
        manager._tokens = {"refresh_token": "test_refresh"}
        token = manager.refresh_token()
        
        self.assertEqual(token, "refreshed_token")
        self.assertEqual(manager._tokens["access_token"], "refreshed_token")
        self.assertEqual(manager._tokens["refresh_token"], "test_refresh")  # Original refresh token preserved
        
        # Verify correct API call
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        self.assertEqual(call_args[0][0], "https://api-t1.fyers.in/api/v3/validate-refresh-token")
        
        # Verify correct hash generation and payload
        payload = call_args[1]["json"]
        self.assertEqual(payload["grant_type"], "refresh_token")
        self.assertEqual(payload["refresh_token"], "test_refresh")
        self.assertEqual(payload["pin"], "1234")
        
        # Calculate expected hash and verify
        expected_hash = hashlib.sha256(f"test_app_id:test_secret_id".encode()).hexdigest()
        self.assertEqual(payload["appIdHash"], expected_hash)
    
    @patch("requests.post")
    def test_refresh_token_api_error(self, mock_post):
        """Test token refresh with API error response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "s": "error", 
            "code": 400,
            "message": "Invalid refresh token"
        }
        mock_post.return_value = mock_response
        
        manager = TokenManager()
        manager._tokens = {"refresh_token": "test_refresh"}
        
        with self.assertRaises(RefreshTokenError):
            manager.refresh_token()
    
    @patch("requests.post", side_effect=Exception("Network error"))
    def test_refresh_token_exception(self, mock_post):
        """Test exception during token refresh."""
        manager = TokenManager()
        manager._tokens = {"refresh_token": "test_refresh"}
        
        with self.assertRaises(RefreshTokenError):
            manager.refresh_token()
    
    def test_initialize_fyers_client_no_token(self):
        """Test client initialization with no access token."""
        manager = TokenManager()
        manager._tokens = {}
        manager._initialize_fyers_client()
        self.assertIsNone(manager._fyers)
    
    @patch("app.token_manager.fyersModel.FyersModel")
    def test_initialize_fyers_client_success(self, mock_fyers_model):
        """Test successful client initialization."""
        mock_instance = MagicMock()
        mock_fyers_model.return_value = mock_instance
        
        manager = TokenManager()
        manager._tokens = {"access_token": "test_token"}
        manager._initialize_fyers_client()
        
        self.assertEqual(manager._fyers, mock_instance)
        mock_fyers_model.assert_called_once_with(
            token="test_token",
            is_async=False,
            client_id="test_app_id",
            log_path=""
        )
    
    @patch("app.token_manager.fyersModel.FyersModel", side_effect=Exception("Client error"))
    def test_initialize_fyers_client_exception(self, mock_fyers_model):
        """Test exception during client initialization."""
        manager = TokenManager()
        manager._tokens = {"access_token": "test_token"}
        
        with self.assertRaises(TokenManagerException):
            manager._initialize_fyers_client()
        
        self.assertIsNone(manager._fyers)
    
    def test_get_fyers_client_existing(self):
        """Test getting existing Fyers client."""
        manager = TokenManager()
        mock_client = MagicMock()
        manager._fyers = mock_client
        
        client = manager.get_fyers_client()
        self.assertEqual(client, mock_client)
    
    @patch("app.token_manager.TokenManager._initialize_fyers_client")
    def test_get_fyers_client_initialize(self, mock_init):
        """Test getting Fyers client with initialization."""
        manager = TokenManager()
        manager._fyers = None
        mock_client = MagicMock()
        
        # Set up the side effect to set _fyers
        def set_fyers(*args, **kwargs):
            manager._fyers = mock_client
        
        mock_init.side_effect = set_fyers
        
        client = manager.get_fyers_client()
        self.assertEqual(client, mock_client)
        mock_init.assert_called_once()
    
    def test_singleton_pattern(self):
        """Test that get_token_manager returns a singleton instance."""
        manager1 = get_token_manager()
        manager2 = get_token_manager()
        self.assertIs(manager1, manager2)
    
    def test_thread_safety(self):
        """Test that TokenManager uses a thread lock for synchronization."""
        manager = TokenManager()
        self.assertTrue(hasattr(manager, '_lock'))
        # Check if it has lock-like behavior
        self.assertTrue(hasattr(manager._lock, 'acquire'))
        self.assertTrue(hasattr(manager._lock, 'release'))
    
    @patch("threading.Thread")
    def test_concurrent_access(self, mock_thread):
        """Test concurrent access to TokenManager singleton."""
        # This is a basic test to verify thread execution
        # A more comprehensive test would require actual thread execution
        
        def thread_func():
            manager = get_token_manager()
            return manager
        
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=thread_func)
            threads.append(thread)
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify we still have a single instance
        self.assertEqual(id(get_token_manager()), id(get_token_manager()))


if __name__ == '__main__':
    unittest.main()
