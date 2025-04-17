# ------------------ tests/test_routes.py ------------------
import unittest
from unittest.mock import patch, MagicMock
from flask import Flask, json
from app.routes import webhook_bp

class TestRoutes(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.register_blueprint(webhook_bp)
        self.client = self.app.test_client()

    @patch("app.routes.get_access_token")
    def test_health_check_success(self, mock_get_token):
        mock_get_token.return_value = "valid_token"
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
        self.assertEqual(response.status_code, 501)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.get_auth_code_url")
    def test_get_auth_url(self, mock_url):
        mock_url.return_value = "https://auth.test"
        response = self.client.get("/auth-url")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["auth_url"], "https://auth.test")

    @patch("app.routes.place_order")
    @patch("app.routes.get_ltp")
    @patch("app.routes.get_fyers")
    @patch("app.routes.get_symbol_from_csv")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_success(self, mock_env, mock_resolve, mock_fyers, mock_ltp, mock_order):
        mock_resolve.return_value = "NSE:NIFTY245001CE"
        mock_ltp.return_value = 200
        mock_order.return_value = {"code": 200, "id": "order123"}
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
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    def test_webhook_missing_fields(self):
        response = self.client.post("/webhook", json={"symbol": "NIFTY"})
        self.assertEqual(response.status_code, 401)

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
        self.assertEqual(response.status_code, 402)

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

    @patch("app.routes.get_fyers")
    @patch("app.routes.get_ltp", return_value=None)
    @patch("app.routes.place_order")
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_ltp_none_uses_defaults(self, mock_env, mock_resolve, mock_order, mock_ltp, mock_fyers):
        mock_order.return_value = {"code": 200, "id": "fallback-order"}
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
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

if __name__ == '__main__':
    unittest.main()
