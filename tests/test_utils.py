import unittest
from unittest.mock import patch, MagicMock
from app import utils
from datetime import datetime
import pandas as pd

class TestUtils(unittest.TestCase):

    def test_get_nearest_strike(self):
        self.assertEqual(utils.get_nearest_strike(183.75), 200)
        self.assertEqual(utils.get_nearest_strike(174), 150)

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

    @patch("pandas.read_csv")
    def test_get_symbol_from_csv_weekly(self, mock_csv):
        df = pd.DataFrame({
            "underlying_symbol": ["NIFTY"],
            "strike_price": [23000.0],
            "option_type": ["CE"],
            "expiry_date": [pd.Timestamp(datetime.now().date())],
            "symbol_ticker": ["NSE:NIFTY24042523000CE"]
        })
        mock_csv.return_value = df
        symbol = utils.get_symbol_from_csv("NIFTY", 23000, "CE", "WEEKLY")
        self.assertEqual(symbol, "NSE:NIFTY24042523000CE")

    @patch("pandas.read_csv")
    def test_get_symbol_from_csv_empty(self, mock_csv):
        mock_csv.return_value = pd.DataFrame(columns=utils.symbol_master_columns)
        symbol = utils.get_symbol_from_csv("NIFTY", 23000, "CE", "WEEKLY")
        self.assertIsNone(symbol)

if __name__ == '__main__':
    unittest.main()
