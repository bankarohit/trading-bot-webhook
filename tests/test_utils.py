import os
import sys
import pytest
from unittest.mock import MagicMock
import pandas as pd
import urllib.request
from datetime import datetime, timedelta

# Ensure app package importability and set required environment variables
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils import (
    load_symbol_master, get_symbol_from_csv,
    symbol_master_columns
)
import app.utils


@pytest.fixture
def sample_df():
    today = pd.Timestamp.now().normalize()
    weekly_expiry = today + timedelta(days=2)
    monthly_expiry = today + timedelta(days=30)

    sample_data = [
        [123456, "NSE:NIFTY2541719000CE", "OPT", 50, 0.05, "INE123", "normal", 1234567890,
         weekly_expiry.timestamp(), "NIFTY2541719000CE", "NSE", "OPT", 123,
         "NIFTY", 456, 19000, "CE", 789, "", "", ""],
        [123457, "NSE:NIFTY2541719000PE", "OPT", 50, 0.05, "INE124", "normal", 1234567890,
         weekly_expiry.timestamp(), "NIFTY2541719000PE", "NSE", "OPT", 124,
         "NIFTY", 456, 19000, "PE", 789, "", "", ""],
        [123458, "NSE:NIFTY25APR19000CE", "OPT", 50, 0.05, "INE125", "normal", 1234567890,
         monthly_expiry.timestamp(), "NIFTY25APR19000CE", "NSE", "OPT", 125,
         "NIFTY", 456, 19000, "CE", 789, "", "", ""],
        [123459, "NSE:BANKNIFTY2541719000CE", "OPT", 25, 0.05, "INE126", "normal", 1234567890,
         weekly_expiry.timestamp(), "BANKNIFTY2541719000CE", "NSE", "OPT", 126,
         "BANKNIFTY", 457, 19000, "CE", 790, "", "", ""]
    ]
    return pd.DataFrame(sample_data, columns=symbol_master_columns)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    app.utils._symbol_cache = None
    mock_logger = MagicMock()
    original_logger = app.utils.logger
    app.utils.logger = mock_logger
    yield mock_logger
    app.utils.logger = original_logger


def test_load_symbol_master_success(monkeypatch, sample_df):
    mock_read_csv = MagicMock(return_value=sample_df)
    monkeypatch.setattr(pd, "read_csv", mock_read_csv)
    mock_response = MagicMock()
    mock_response.read.return_value = b"dummy"
    mock_response.__enter__.return_value = mock_response
    monkeypatch.setattr(urllib.request, "urlopen", MagicMock(return_value=mock_response))

    load_symbol_master()

    mock_read_csv.assert_called_once()
    assert app.utils._symbol_cache is not None
    assert len(app.utils._symbol_cache) == 4
    app.utils.logger.debug.assert_called_with("Loaded symbol master into memory")


def test_load_symbol_master_failure(monkeypatch):
    mock_read_csv = MagicMock(side_effect=Exception("Connection error"))
    monkeypatch.setattr(pd, "read_csv", mock_read_csv)
    mock_response = MagicMock()
    mock_response.read.return_value = b"dummy"
    mock_response.__enter__.return_value = mock_response
    monkeypatch.setattr(urllib.request, "urlopen", MagicMock(return_value=mock_response))

    load_symbol_master()

    mock_read_csv.assert_called_once()
    assert app.utils._symbol_cache is not None
    assert app.utils._symbol_cache.empty
    app.utils.logger.error.assert_called_with("Failed to load symbol master: Connection error")


def test_get_symbol_from_csv_nifty_weekly_ce(monkeypatch, sample_df):
    app.utils._symbol_cache = sample_df
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    assert result == "NIFTY2541719000CE"


def test_get_symbol_from_csv_nifty_monthly_ce(monkeypatch, sample_df):
    app.utils._symbol_cache = sample_df
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "MONTHLY")
    assert result == "NIFTY25APR19000CE"


def test_get_symbol_from_csv_empty_cache(monkeypatch, sample_df):
    app.utils._symbol_cache = None

    def mock_load():
        app.utils._symbol_cache = sample_df

    monkeypatch.setattr(app.utils, "load_symbol_master", MagicMock(side_effect=mock_load))
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    assert result == "NIFTY2541719000CE"


def test_get_symbol_from_csv_invalid_expiry_type(monkeypatch, sample_df):
    app.utils._symbol_cache = sample_df
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "QUARTERLY")
    assert result is None


def test_get_symbol_from_csv_no_matching_symbol(monkeypatch, sample_df):
    app.utils._symbol_cache = sample_df
    result = get_symbol_from_csv("SENSEX", 19000, "CE", "WEEKLY")
    assert result is None


def test_get_symbol_from_csv_exception(monkeypatch, sample_df):
    app.utils._symbol_cache = sample_df

    def mock_df_copy(*args, **kwargs):
        raise Exception("Processing error")

    monkeypatch.setattr(pd.DataFrame, "copy", mock_df_copy)
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    assert result is None
    app.utils.logger.exception.assert_called_with(
        "Exception in get_symbol_from_csv for symbol=NIFTY, strike_price=19000, option_type=CE, expiry_type=WEEKLY: Processing error"
    )

