# ------------------ tests/test_utils.py ------------------
import unittest
from unittest.mock import patch, MagicMock
from app import utils
from datetime import datetime
import pandas as pd
import gspread

class TestUtils(unittest.TestCase):

    @patch("app.utils.pd.read_csv")
    def test_load_symbol_master(self, mock_csv):
        mock_df = pd.DataFrame({"underlying_symbol": ["NIFTY"]})
        mock_csv.return_value = mock_df
        utils.load_symbol_master()
        self.assertIsNotNone(utils._symbol_cache)

    @patch("app.utils._symbol_cache", create=True)
    def test_get_symbol_from_csv_weekly(self, mock_cache):
        df = pd.DataFrame({
            "underlying_symbol": ["NIFTY"],
            "strike_price": [23000.0],
            "option_type": ["CE"],
            "expiry_date": [pd.Timestamp(datetime.now())],
            "symbol_ticker": ["NSE:NIFTY24042523000CE"]
        })
        mock_cache.copy.return_value = df
        symbol = utils.get_symbol_from_csv("NIFTY", 23000, "CE", "WEEKLY")
        self.assertEqual(symbol, "NSE:NIFTY24042523000CE")

    @patch("app.utils.get_gsheet_client")
    @patch("app.utils.os.getenv", return_value="dummy_id")
    def test_log_trade_to_sheet(self, mock_env, mock_client):
        mock_sheet = MagicMock()
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_sheet
        success = utils.log_trade_to_sheet("NIFTY", "BUY", 75, 123.5, 100, 150)
        self.assertTrue(success)
        mock_sheet.append_row.assert_called_once()

    @patch("app.utils.get_gsheet_client")
    @patch("app.utils.os.getenv", return_value="dummy_id")
    def test_get_open_trades_from_sheet(self, mock_env, mock_client):
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = [
            ["UUID", "Timestamp", "Symbol", "Action", "Qty", "Entry", "SL", "TP", "Status"],
            ["1", "2024-04-17 09:15", "NIFTY", "BUY", "75", "120.0", "100", "140", "OPEN"]
        ]
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_sheet
        result = utils.get_open_trades_from_sheet()
        self.assertEqual(len(result), 1)

    @patch("app.utils.get_gsheet_client")
    @patch("app.utils.os.getenv", return_value="dummy_id")
    def test_update_trade_status_in_sheet(self, mock_env, mock_client):
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = [
            ["UUID", "Timestamp"],
            ["1", "2024-04-17 09:15"]
        ]
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_sheet
        result = utils.update_trade_status_in_sheet("1", "CLOSED", 135.5, "TP HIT")
        self.assertTrue(result)
        mock_sheet.update_cell.assert_any_call(2, 9, "CLOSED")
        mock_sheet.update_cell.assert_any_call(2, 10, "135.5")
        mock_sheet.update_cell.assert_any_call(2, 11, unittest.mock.ANY)  # exit time
        mock_sheet.update_cell.assert_any_call(2, 12, "TP HIT")

    @patch("app.utils.get_gsheet_client")
    @patch("app.utils.os.getenv", return_value="dummy_id")
    def test_update_trade_not_found(self, mock_env, mock_client):
        mock_sheet = MagicMock()
        mock_sheet.get_all_values.return_value = [["UUID", "Timestamp"], ["2", "2024-04-17 09:15"]]
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_sheet
        result = utils.update_trade_status_in_sheet("1", "CLOSED", 120.0, "manual exit")
        self.assertFalse(result)

    @patch("app.utils.get_gsheet_client")
    @patch("app.utils.os.getenv", return_value="dummy_id")
    def test_log_trade_retry_on_failure(self, mock_env, mock_client):
        mock_sheet = MagicMock()

        # Create a mock response object with .json() and .text attributes
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": {"message": "Temporary fail","code": 500}}
        mock_response.text = "Temporary fail"

        error = gspread.exceptions.APIError(mock_response)

        mock_sheet.append_row.side_effect = [error, None]
        mock_client.return_value.open_by_key.return_value.worksheet.return_value = mock_sheet

        result = utils.log_trade_to_sheet("symbol", "BUY", 50, 183.75, 100, 200)
        self.assertTrue(result)
        self.assertEqual(mock_sheet.append_row.call_count, 2)

    @patch("app.utils._symbol_cache", create=True)
    def test_get_symbol_from_csv_no_match(self, mock_cache):
        df = pd.DataFrame({
            "underlying_symbol": ["BANKNIFTY"],
            "strike_price": [24000.0],
            "option_type": ["PE"],
            "expiry_date": [pd.Timestamp(datetime.now())],
            "symbol_ticker": ["NSE:BANKNIFTY24042524000PE"]
        })
        mock_cache.copy.return_value = df
        result = utils.get_symbol_from_csv("NIFTY", 23000, "CE", "WEEKLY")
        self.assertIsNone(result)

if __name__ == '__main__':
    unittest.main()
