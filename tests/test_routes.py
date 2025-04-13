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

if __name__ == '__main__':
    unittest.main()