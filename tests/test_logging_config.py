import os
import sys
import logging
from unittest.mock import MagicMock, patch
from flask import Flask, g

# Ensure the app package is importable and required env vars are set
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("GOOGLE_SHEET_ID", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

from app.logging_config import get_request_id, configure_logging, RequestIdFilter


def test_get_request_id_outside_context():
    assert get_request_id() == "-"


def test_get_request_id_inside_context():
    app = Flask(__name__)
    with app.test_request_context('/'):
        g.request_id = 'req-123'
        assert get_request_id() == 'req-123'


@patch('app.logging_config.logging.getLogger')
@patch('app.logging_config.logging.basicConfig')
def test_configure_logging_no_log_file(mock_basic, mock_get_logger):
    root_logger = MagicMock()
    handler = MagicMock()
    root_logger.handlers = [handler]
    mock_get_logger.return_value = root_logger

    with patch.dict(os.environ, {"LOG_LEVEL": "DEBUG"}, clear=False):
        os.environ.pop("LOG_FILE", None)
        with patch('app.logging_config.RotatingFileHandler') as mock_rot:
            configure_logging()
            mock_rot.assert_not_called()

    mock_basic.assert_called_once()
    assert mock_basic.call_args.kwargs["level"] == logging.DEBUG
    root_logger.addHandler.assert_not_called()
    root_logger.addFilter.assert_called_once()
    handler.addFilter.assert_called_once()


@patch('app.logging_config.logging.getLogger')
@patch('app.logging_config.logging.basicConfig')
def test_configure_logging_with_log_file(mock_basic, mock_get_logger):
    root_logger = MagicMock()
    handler = MagicMock()
    root_logger.handlers = [handler]
    mock_get_logger.return_value = root_logger

    file_handler = MagicMock()
    with patch.dict(os.environ, {"LOG_FILE": "app.log", "LOG_LEVEL": "INFO"}, clear=False):
        with patch('app.logging_config.RotatingFileHandler', return_value=file_handler) as mock_rot:
            configure_logging()
            mock_rot.assert_called_once_with('app.log', maxBytes=10 * 1024 * 1024, backupCount=5)
            root_logger.addHandler.assert_called_once_with(file_handler)
            file_handler.setFormatter.assert_called_once()
            file_handler.addFilter.assert_called_once()

    assert mock_basic.call_args.kwargs["level"] == logging.INFO
    root_logger.addFilter.assert_called_once()
    handler.addFilter.assert_called_once()


def test_request_id_filter_adds_request_id():
    filt = RequestIdFilter()
    record = logging.LogRecord("name", logging.INFO, __file__, 0, "msg", None, None)
    with patch("app.logging_config.get_request_id", return_value="abc"):
        result = filt.filter(record)
    assert result is True
    assert getattr(record, "request_id") == "abc"
