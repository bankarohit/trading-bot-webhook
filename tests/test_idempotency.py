import os
import sys
import unittest
from unittest.mock import patch, MagicMock

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

from app.idempotency import (
    get_idempotency_key,
    IdempotencyStore,
    get_store,
)


class TestIdempotencyKey(unittest.TestCase):
    def test_key_from_header(self):
        request = MagicMock()
        request.headers = {"Idempotency-Key": "  my-key-456  "}
        request.is_json = False
        self.assertEqual(get_idempotency_key(request), "my-key-456")

    def test_key_from_header_when_both_present(self):
        request = MagicMock()
        request.headers = {"Idempotency-Key": "header-key"}
        request.is_json = True
        request.get_json = MagicMock(return_value={"idempotency_key": "body-key"})
        self.assertEqual(get_idempotency_key(request), "header-key")

    def test_key_from_body_only(self):
        request = MagicMock()
        request.headers = {}
        request.is_json = True
        request.get_json = MagicMock(return_value={"idempotency_key": "body-only"})
        self.assertEqual(get_idempotency_key(request), "body-only")

    def test_no_key_returns_none(self):
        request = MagicMock()
        request.headers = {}
        request.is_json = True
        request.get_json = MagicMock(return_value={})
        self.assertIsNone(get_idempotency_key(request))


class TestIdempotencyStore(unittest.TestCase):
    def test_set_and_get(self):
        store = IdempotencyStore(ttl_seconds=60)
        store.set("k1", {"success": True}, 200)
        out = store.get("k1")
        self.assertIsNotNone(out)
        self.assertEqual(out[0], {"success": True})
        self.assertEqual(out[1], 200)

    def test_get_missing_returns_none(self):
        store = IdempotencyStore(ttl_seconds=60)
        self.assertIsNone(store.get("missing"))

    def test_get_expired_returns_none(self):
        store = IdempotencyStore(ttl_seconds=0)
        store.set("k1", {"x": 1}, 200)
        self.assertIsNone(store.get("k1"))

    def test_ttl_zero_does_not_store(self):
        store = IdempotencyStore(ttl_seconds=0)
        store.set("k1", {"x": 1}, 200)
        self.assertIsNone(store.get("k1"))


if __name__ == "__main__":
    unittest.main()
