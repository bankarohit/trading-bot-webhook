### ----------------------------- tests/test_routes.py -----------------------------
import unittest
import os
from app import create_app
import json

class TestRoutes(unittest.TestCase):

    def setUp(self):
        os.environ["FYERS_APP_ID"] = "test"
        os.environ["FYERS_SECRET_ID"] = "test"
        os.environ["FYERS_REDIRECT_URI"] = "http://localhost"
        os.environ["WEBHOOK_SECRET_TOKEN"] = "dummy"
        os.environ["GOOGLE_SHEET_ID"] = "test"
        self.app = create_app().test_client()

    def test_health_check(self):
        res = self.app.get("/readyz")
        self.assertEqual(res.status_code, 200)
        self.assertIn("ok", res.json["status"])

    def test_webhook_missing_fields(self):
        payload = {"token": "dummy"}
        res = self.app.post("/webhook", json=payload)
        self.assertEqual(res.status_code, 400)
        self.assertFalse(res.json["success"])

    def test_webhook_invalid_token(self):
        payload = {
            "token": "wrong",
            "symbol": "NIFTY",
            "strikeprice": 23000,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY"
        }
        res = self.app.post("/webhook", json=payload)
        self.assertEqual(res.status_code, 401)

    @unittest.mock.patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY24042523000CE")
    @unittest.mock.patch("app.routes.get_ltp", return_value=180.5)
    @unittest.mock.patch("app.routes.place_order", return_value={"code": 200, "message": "Order Placed"})
    @unittest.mock.patch("app.routes.log_trade_to_sheet")
    def test_webhook_success(self, mock_log, mock_order, mock_ltp, mock_symbol):
        payload = {
            "token": "dummy",
            "symbol": "NIFTY",
            "strikeprice": 23000,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY"
        }
        res = self.app.post("/webhook", json=payload)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json["success"])

    @unittest.mock.patch("app.routes.get_symbol_from_csv", return_value=None)
    def test_webhook_symbol_resolution_fail(self, mock_symbol):
        payload = {
            "token": "dummy",
            "symbol": "NIFTY",
            "strikeprice": 23000,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY"
        }
        res = self.app.post("/webhook", json=payload)
        self.assertEqual(res.status_code, 403)

if __name__ == '__main__':
    unittest.main()