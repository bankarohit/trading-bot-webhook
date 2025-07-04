import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock
from flask import Flask

# Provide environment variables and import the blueprint
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

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
        mock_fyers.get_profile = AsyncMock(return_value={
            "s": "ok",
            "data": {}
        })
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

    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=True)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_success(self, mock_env, mock_resolve, mock_short,
                             mock_fyers, mock_ltp, mock_order):
        mock_order.return_value = {
            "s": "ok",
            "message": "Order placed",
            "id": "order123"
        }
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
        self.assertNotIn("logged_to_sheet", data)

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

    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_ltp", new_callable=AsyncMock)
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=False)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_buy_without_short(self, mock_env, mock_resolve,
                                       mock_short, mock_fyers, mock_ltp,
                                       mock_order):
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

        self.assertEqual(response.status_code, 400)
        mock_order.assert_not_called()

    @patch("app.routes.get_fyers")
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=None)
    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_ltp_none_uses_defaults(self, mock_env, mock_resolve,
                                            mock_order, mock_ltp, mock_fyers):
        mock_order.return_value = {
            "s": "ok",
            "message": "Order placed",
            "id": "fallback-order"
        }
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
        self.assertNotIn("logged_to_sheet", data)

    @patch("app.routes.get_fyers")
    @patch(
        "app.routes.get_ltp",
        new_callable=AsyncMock,
        return_value={"code": -1, "message": "bad"},
    )
    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_ltp_error_dict_defaults(self, mock_env, mock_resolve,
                                             mock_order, mock_ltp, mock_fyers):
        mock_order.return_value = {
            "s": "ok",
            "message": "Order placed",
            "id": "dict-order",
        }
        mock_fyers.return_value = MagicMock()

        payload = {
            "token": "secret",
            "symbol": "NIFTY",
            "strikeprice": 24500,
            "optionType": "CE",
            "expiry": "WEEKLY",
            "action": "SELL",
            "qty": 75,
        }
        response = self.client.post("/webhook", json=payload)
        data = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertTrue(data["success"])
        self.assertEqual(data["order_response"]["id"], "dict-order")
        args = mock_order.call_args[0]
        self.assertEqual(args[3], 10.0)
        self.assertEqual(args[4], 20.0)

    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.generate_access_token", return_value="tok")
    def test_generate_token_success(self, mock_gen, mock_get_fyers,
                                    mock_get_ltp, mock_place):
        response = self.client.post("/generate-token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["success"])

    @patch("app.routes.generate_access_token", return_value=None)
    def test_generate_token_none(self, mock_gen):
        response = self.client.post("/generate-token")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.get_json()["success"])

    def test_webhook_empty_json(self):
        response = self.client.post("/webhook", json={})
        self.assertEqual(response.status_code, 400)

    @patch("app.routes._validate_order_params", side_effect=Exception("bad"))
    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=True)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_unhandled_exception(self, mock_env, mock_resolve,
                                         mock_short, mock_fyers, mock_ltp,
                                         mock_order, mock_validate):
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
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.get_fyers")
    @patch("app.routes.get_access_token")
    def test_health_check_profile_error(self, mock_get_token, mock_get_fyers):
        mock_get_token.return_value = "valid"
        mock_fyers = MagicMock()
        mock_fyers.get_profile = AsyncMock(return_value={"s": "error"})
        mock_get_fyers.return_value = mock_fyers

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.get_fyers")
    @patch("app.routes.get_access_token")
    def test_health_check_exception(self, mock_get_token, mock_get_fyers):
        mock_get_token.return_value = "valid"
        mock_get_fyers.side_effect = Exception("boom")

        response = self.client.get("/readyz")
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.refresh_access_token", side_effect=Exception("err"))
    def test_refresh_token_exception(self, mock_refresh):
        response = self.client.post("/refresh-token")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.generate_access_token", side_effect=Exception("err"))
    def test_generate_token_exception(self, mock_generate):
        response = self.client.post("/generate-token")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.get_auth_code_url", return_value=None)
    def test_get_auth_url_none(self, mock_url):
        response = self.client.get("/auth-url")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.get_auth_code_url", side_effect=Exception("boom"))
    def test_get_auth_url_exception(self, mock_url):
        response = self.client.get("/auth-url")
        self.assertEqual(response.status_code, 500)
        self.assertFalse(response.get_json()["success"])

    @patch("app.routes.get_fyers", return_value=None)
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.place_order", new_callable=AsyncMock)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_fyers_init_fail(self, mock_env, mock_resolve, mock_order,
                                     mock_ltp, mock_fyers):
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
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.place_order",
           new_callable=AsyncMock,
           return_value={
               "s": "error",
               "message": "bad"
           })
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=True)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_order_api_error(self, mock_env, mock_resolve, mock_short,
                                     mock_fyers, mock_ltp, mock_order):
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
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.place_order",
           new_callable=AsyncMock,
           side_effect=Exception("fail"))
    @patch("app.routes.get_ltp", new_callable=AsyncMock, return_value=200)
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=True)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_order_exception(self, mock_env, mock_resolve, mock_short,
                                     mock_fyers, mock_ltp, mock_order):
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
        self.assertEqual(response.status_code, 500)

    @patch("app.routes.place_order",
           new_callable=AsyncMock,
           return_value={"s": "ok"})
    @patch("app.routes.get_ltp",
           new_callable=AsyncMock,
           side_effect=Exception("ltp"))
    @patch("app.routes.get_fyers")
    @patch("app.routes.has_short_position",
           new_callable=AsyncMock,
           return_value=True)
    @patch("app.routes.get_symbol_from_csv", return_value="NSE:NIFTY245001CE")
    @patch("app.routes.os.getenv", return_value="secret")
    def test_webhook_get_ltp_exception(self, mock_env, mock_resolve,
                                       mock_short, mock_fyers, mock_ltp,
                                       mock_order):
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


if __name__ == '__main__':
    unittest.main()
