### ----------------------------- tests/test_utils.py -----------------------------
import unittest
from unittest.mock import patch, MagicMock
from app import utils
from datetime import datetime

class TestUtils(unittest.TestCase):

    def test_get_nearest_strike(self):
        self.assertEqual(utils.get_nearest_strike(183.75), 200)
        self.assertEqual(utils.get_nearest_strike(174), 150)  # fixed expectation

    def test_get_option_symbol_format(self):
        result = utils.get_option_symbol("NIFTY", 18500, "CE")
        self.assertTrue(result.startswith("NSE:NIFTY"))
        self.assertTrue(result.endswith("18500CE"))

    @patch("app.utils.gspread.authorize")
    @patch("app.utils.ServiceAccountCredentials.from_json_keyfile_name")
    @patch("app.utils.os.getenv", return_value="sheet_id")
    def test_log_trade_to_sheet(self, mock_getenv, mock_creds, mock_auth):
        mock_client = MagicMock()
        mock_sheet = MagicMock()
        mock_auth.return_value = mock_client
        mock_client.open_by_key.return_value.worksheet.return_value = mock_sheet

        utils.log_trade_to_sheet("symbol", "BUY", 50, 183.75, 100, 200)
        mock_sheet.append_row.assert_called_once()

if __name__ == '__main__':
    unittest.main()