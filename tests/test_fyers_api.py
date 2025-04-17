# ------------------ tests/test_fyers_api.py ------------------
import unittest
from unittest.mock import MagicMock, patch
from app import fyers_api

class TestFyersAPI(unittest.TestCase):

    def test_get_ltp_success(self):
        mock_fyers = MagicMock()
        mock_fyers.quotes.return_value = {
            "d": [{"v": {"lp": 215.45}}]
        }
        ltp = fyers_api.get_ltp("NSE:NIFTY245001CE", mock_fyers)
        self.assertEqual(ltp, 215.45)

    def test_get_ltp_failure(self):
        mock_fyers = MagicMock()
        mock_fyers.quotes.side_effect = Exception("API failure")
        result = fyers_api.get_ltp("NSE:XYZ", mock_fyers)
        self.assertEqual(result["code"], -1)
        self.assertIn("API failure", result["message"])

    @patch("app.fyers_api._symbol_cache")
    def test_get_default_qty_found(self, mock_cache):
        mock_cache.__getitem__.return_value = MagicMock()
        mock_cache.__getitem__.return_value.empty = False
        mock_cache.__getitem__.return_value.iloc = MagicMock()
        mock_cache.__getitem__.return_value.iloc.__getitem__.return_value = {"lot_size": 75}

        with patch("app.fyers_api.load_symbol_master"):
            qty = fyers_api.get_default_qty("NSE:NIFTY245001CE")
            self.assertEqual(qty, 75)

    @patch("app.fyers_api._symbol_cache")
    @patch("app.fyers_api.load_symbol_master")
    def test_get_default_qty_fallback(self, mock_loader, mock_cache):
        mock_loader.return_value = None
        mock_cache.__getitem__.return_value = MagicMock()
        mock_cache.__getitem__.return_value.empty = True
        qty = fyers_api.get_default_qty("UNKNOWN")
        self.assertEqual(qty, 1)

    @patch("app.fyers_api._symbol_cache")
    @patch("app.fyers_api.load_symbol_master")
    def test_validate_order_params_with_defaults(self, mock_loader, mock_cache):
        mock_loader.return_value = None
        mock_cache.__getitem__.return_value = MagicMock()
        mock_cache.__getitem__.return_value.empty = True
        qty, sl, tp, productType = fyers_api.validate_order_params("NSE:NIFTY245001CE", None, 0, None, "INVALID")
        self.assertEqual(qty, 1)  # fallback default
        self.assertEqual(sl, 10.0)
        self.assertEqual(tp, 20.0)
        self.assertEqual(productType, "BO")

    @patch("app.fyers_api._symbol_cache")
    @patch("app.fyers_api.load_symbol_master")
    def test_place_order_builds_payload(self, mock_loader, mock_cache):
        mock_loader.return_value = None
        mock_cache.__getitem__.return_value = MagicMock()
        mock_cache.__getitem__.return_value.empty = True

        mock_fyers = MagicMock()
        mock_fyers.place_order.return_value = {"code": 200, "id": "test_order"}

        response = fyers_api.place_order(
            symbol="NSE:NIFTY245001CE",
            qty=None,
            action="BUY",
            sl=5,
            tp=15,
            productType="INTRADAY",
            fyersModelInstance=mock_fyers
        )
        self.assertEqual(response["code"], 200)
        mock_fyers.place_order.assert_called_once()

if __name__ == '__main__':
    unittest.main()
