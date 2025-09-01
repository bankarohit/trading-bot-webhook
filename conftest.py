"""Pytest configuration to stub optional Google Cloud logging dependency.

This prevents ImportError during test collection when `google-cloud-logging`
is not installed locally. The application only needs the handler and client
types for wiring, so lightweight stubs are sufficient for tests.
"""

import sys
import types
import logging


def _install_google_cloud_logging_stubs() -> None:
    # Create module stubs
    google_mod = types.ModuleType("google")
    cloud_mod = types.ModuleType("google.cloud")
    logging_v2_mod = types.ModuleType("google.cloud.logging_v2")
    handlers_mod = types.ModuleType("google.cloud.logging_v2.handlers")
    storage_mod = types.ModuleType("google.cloud.storage")

    # Minimal StructuredLogHandler implementation compatible with logging
    class StructuredLogHandler(logging.Handler):
        def __init__(self, *args, **kwargs):  # pragma: no cover - simple stub
            super().__init__()

    # Minimal Client stub
    class Client:  # pragma: no cover - simple stub
        def __init__(self, *args, **kwargs):
            pass

    # Attach attributes
    handlers_mod.StructuredLogHandler = StructuredLogHandler
    logging_v2_mod.handlers = handlers_mod
    logging_v2_mod.Client = Client

    # Minimal GCS stubs used by code paths in tests
    class _GCSBlob:  # pragma: no cover - simple stub
        def __init__(self, bucket, name):
            self._bucket = bucket
            self.name = name
            self.cache_control = None

        def upload_from_string(self, data, content_type=None):
            return None

        def download_as_text(self, encoding="utf-8"):
            return "{}"  # empty JSON by default

    class _GCSBucket:  # pragma: no cover - simple stub
        def __init__(self, name):
            self.name = name

        def blob(self, name):
            return _GCSBlob(self, name)

        def get_blob(self, name):
            # Simulate not found by default; tests patch when needed
            return None

    class _StorageClient:  # pragma: no cover - simple stub
        def __init__(self):
            pass

        @classmethod
        def from_service_account_json(cls, path):
            return cls()

        def bucket(self, name):
            return _GCSBucket(name)

    storage_mod.Client = _StorageClient

    # Link module hierarchy
    cloud_mod.logging_v2 = logging_v2_mod
    cloud_mod.storage = storage_mod
    google_mod.cloud = cloud_mod

    # Register in sys.modules so imports succeed
    sys.modules.setdefault("google", google_mod)
    sys.modules.setdefault("google.cloud", cloud_mod)
    sys.modules.setdefault("google.cloud.logging_v2", logging_v2_mod)
    sys.modules.setdefault("google.cloud.logging_v2.handlers", handlers_mod)
    sys.modules.setdefault("google.cloud.storage", storage_mod)


_install_google_cloud_logging_stubs()
