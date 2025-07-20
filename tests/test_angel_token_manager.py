import os
import sys
import unittest
from unittest.mock import patch, MagicMock, mock_open

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import angel_token_manager as atm


class TestAngelTokenManager(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {
            "ANGEL_API_KEY": "key",
            "ANGEL_REDIRECT_URI": "http://localhost",
            "ANGEL_CLIENT_CODE": "client",
            "ANGEL_PASSWORD": "pass",
            "GCS_BUCKET_NAME": "bucket",
            "GCS_TOKENS_FILE": "tokens/angel.json",
        })
        self.env.start()

        self.client_mock = MagicMock()
        patcher = patch('app.angel_token_manager._get_storage_client', return_value=self.client_mock)
        self.mock_storage = patcher.start()
        self.addCleanup(patcher.stop)

        enc = patch('app.angel_token_manager._encrypt', side_effect=lambda b: b.decode())
        dec = patch('app.angel_token_manager._decrypt', side_effect=lambda s: s.encode())
        self.mock_enc = enc.start()
        self.mock_dec = dec.start()
        self.addCleanup(enc.stop)
        self.addCleanup(dec.stop)

    def tearDown(self):
        self.env.stop()

    def test_get_login_url(self):
        url = atm.get_login_url()
        self.assertIn("key", url)
        self.assertIn("http://localhost", url)

    @patch('app.angel_token_manager.save_tokens')
    @patch('requests.post')
    def test_generate_tokens_success(self, mock_post, mock_save):
        mock_post.return_value.json.return_value = {
            "status": "success",
            "data": {"access_token": "a", "refresh_token": "r"}
        }
        tokens = atm.generate_tokens('code')
        self.assertEqual(tokens['access_token'], 'a')
        mock_save.assert_called_once()

    @patch('requests.post')
    def test_generate_tokens_failure(self, mock_post):
        mock_post.return_value.json.return_value = {"status": "error"}
        with self.assertRaises(Exception):
            atm.generate_tokens('code')

    @patch('app.angel_token_manager.save_tokens')
    @patch('requests.post')
    @patch('app.angel_token_manager.load_tokens', return_value={'refresh_token': 'r'})
    def test_refresh_tokens_success(self, mock_load, mock_post, mock_save):
        mock_post.return_value.json.return_value = {
            "status": "success",
            "data": {"access_token": "new", "refresh_token": "nr"}
        }
        tokens = atm.refresh_tokens()
        self.assertEqual(tokens['access_token'], 'new')
        mock_save.assert_called_once()

    @patch('app.angel_token_manager.load_tokens', return_value={})
    def test_refresh_tokens_missing(self, mock_load):
        with self.assertRaises(Exception):
            atm.refresh_tokens()

    @patch('os.path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{"a":"b"}')
    def test_load_tokens_file_not_exists(self, mopen, mexists):
        bucket = self.client_mock.bucket.return_value
        blob = bucket.blob.return_value
        blob.exists.return_value = False
        tokens = atm.load_tokens('f.json')
        self.assertEqual(tokens, {'a': 'b'})
        mopen.assert_called_with('f.json', 'r')

    @patch('builtins.open', new_callable=mock_open)
    def test_save_tokens_success(self, mopen):
        bucket = self.client_mock.bucket.return_value
        blob = bucket.blob.return_value
        atm.save_tokens({'a': 'b'}, 'file.json')
        mopen.assert_called_with('file.json', 'w')
        blob.upload_from_filename.assert_called_once()


if __name__ == '__main__':
    unittest.main()
