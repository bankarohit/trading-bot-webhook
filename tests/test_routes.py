import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, json
from app.routes import webhook_bp

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(webhook_bp)
        self.client = self.app.test_client()

    @patch("app.routes.get_fyers")
    @patch("app.routes.get_access_token")
    def test_health_check_success(self, mock_get_token, mock_get_fyers):
        mock_get_token.return_value = "valid_token"
        mock_fyers = MagicMock()
        mock_fyers.get_profile.return_value = {"s": "ok", "data": {}}
        mock_get_fyers.return_value = mock_fyers

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 200)
        self.assertIn("ok", response.get_json()["status"])

    @patch("app.routes.get_access_token")
    def test_health_check_failure(self, mock_get_token):
        mock_get_token.return_value = None
        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 500)
        self.assertIn("error", response.get_json()["status"])

    @patch("app.routes.refresh_access_token")
    def test_refresh_token_success(self, mock_refresh):
        mock_refresh.return_value = "new_token"
        response = self.client.post("/refresh-token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    @patch("app.routes.refresh_access_token")
    def test_refresh_token_failure(self, mock_refresh):
        mock_refresh.return_value = None
        response = self.client.post("/refresh-token")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.get_auth_code_url")
    def test_get_auth_url(self, mock_url):
        mock_url.return_value = "https://auth.test"
        response = self.client.get("/auth-url")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["auth_url"], "https://auth.test")

    @patch("app.routes.log_trade_to_sheet", return_value=True)
    @patch("app.routes.place_order")
    @patch("app.routes.get_ltp", return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_success(self, mock_env, mock_resolve, mock_fyers, mock_ltp, mock_order, mock_log_sheet):
        mock_order.return_value = {"s": "ok", "message": "Order placed", "id": "order123"}
        mock_fyers.return_value = MagicMock()

        payload = {
            "token": "secret",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY",
            "qty": 75
        }
        response = self.client.post("/webhook", json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["order_response"]["s"], "ok")
        self.assertEqual(data["order_response"]["id"], "order123")
        self.assertTrue(data["logged_to_sheet"])
        mock_log_sheet.assert_called_once()

    def test_webhook_missing_fields(self):
        response = self.client.post("/webhook", json={"symbol": "NIFTY"})
        self.assertEqual(response.status_code, 400)

    def test_webhook_invalid_token(self):
        payload = {
            "token": "wrong",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY",
            "qty": 75
        }
        response = self.client.post("/webhook", json=payload)
        self.assertEqual(response.status_code, 401)

    @patch("app.routes.get_symbol_from_csv", return_value=None)
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_symbol_resolution_fail(self, mock_env, mock_resolve):
        payload = {
            "token": "secret",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY",
            "qty": 75
        }
        response = self.client.post("/webhook", json=payload)
        self.assertEqual(response.status_code, 403)

    @patch("app.routes.log_trade_to_sheet", return_value=True)
    @patch("app.routes.get_fyers")
    @patch("app.routes.get_ltp", return_value=None)
    @patch("app.routes.place_order")
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_ltp_none_uses_defaults(self, mock_env, mock_resolve, mock_order, mock_ltp, mock_fyers, mock_log_sheet):
        mock_order.return_value = {"s": "ok", "message": "Order placed", "id": "fallback-order"}
        mock_fyers.return_value = MagicMock()

        payload = {
            "token": "secret",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "SELL",
            "qty": 75
        }
        response = self.client.post("/webhook", json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["order_response"]["s"], "ok")
        self.assertEqual(data["order_response"]["id"], "fallback-order")
        self.assertTrue(data["logged_to_sheet"])
        mock_log_sheet.assert_called_once()

    @patch("app.routes.log_trade_to_sheet", return_value=True)
    @patch("app.routes.place_order")
    @patch("app.routes.get_ltp", return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret_token")
    def test_webhook_success_logs_to_sheet(self, mock_env, mock_resolve, mock_fyers, mock_ltp, mock_order, mock_log_sheet):
        mock_order.return_value = {"s": "ok", "id": "order123", "message": "Order executed"}

        payload = {
            "token": "secret_token",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "BUY",
            "qty": 75
        }

        response = self.client.post("/webhook", json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertTrue(data["logged_to_sheet"])
        mock_log_sheet.assert_called_once()

    @patch("app.routes.log_trade_to_sheet", side_effect=Exception("GSheet failure"))
    @patch("app.routes.place_order")
    @patch("app.routes.get_ltp", return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret_token")
    def test_webhook_log_to_sheet_failure(self, mock_env, mock_resolve, mock_fyers, mock_ltp, mock_order, mock_log_sheet):
        mock_order.return_value = {"s": "ok", "id": "order123", "message": "Order executed"}

        payload = {
            "token": "secret_token",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "SELL",
            "qty": 75
        }

        response = self.client.post("/webhook", json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 503)
        self.assertFalse(data["success"])
        self.assertEqual(data["error"], "Failed to log trade")
        self.assertEqual(data["order_id"], "order123")
        mock_log_sheet.assert_called_once()

if __name__ == '__main__':
    unittest.main()
