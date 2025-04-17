import pytest
from unittest.mock import patch, MagicMock, mock_open
import pandas as pd
from datetime import datetime, timedelta
import os
import sys
import logging

# Add the parent directory to the path so we can import utils
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.utils import (
    get_gsheet_client, load_symbol_master, get_symbol_from_csv,
    log_trade_to_sheet, get_open_trades_from_sheet, update_trade_status_in_sheet,
    symbol_master_columns, CREDS_FILE, SCOPE
)
import app.utils


@pytest.fixture
def sample_df():
    # Create a sample DataFrame for symbol master
    today = pd.Timestamp.now().normalize()
    weekly_expiry = today + timedelta(days=2)
    monthly_expiry = today + timedelta(days=30)
    
    sample_data = [
        # NIFTY weekly CE
        [123456, "NSE:NIFTY2541719000CE", "OPT", 50, 0.05, "INE123", "normal", 1234567890, 
         weekly_expiry.timestamp(), "NIFTY2541719000CE", "NSE", "OPT", 123,
         "NIFTY", 456, 19000, "CE", 789, "", "", ""],
        # NIFTY weekly PE
        [123457, "NSE:NIFTY2541719000PE", "OPT", 50, 0.05, "INE124", "normal", 1234567890, 
         weekly_expiry.timestamp(), "NIFTY2541719000PE", "NSE", "OPT", 124,
         "NIFTY", 456, 19000, "PE", 789, "", "", ""],
        # NIFTY monthly CE
        [123458, "NSE:NIFTY25APR19000CE", "OPT", 50, 0.05, "INE125", "normal", 1234567890, 
         monthly_expiry.timestamp(), "NIFTY25APR19000CE", "NSE", "OPT", 125,
         "NIFTY", 456, 19000, "CE", 789, "", "", ""],
        # BANKNIFTY weekly CE
        [123459, "NSE:BANKNIFTY2541719000CE", "OPT", 25, 0.05, "INE126", "normal", 1234567890, 
         weekly_expiry.timestamp(), "BANKNIFTY2541719000CE", "NSE", "OPT", 126,
         "BANKNIFTY", 457, 19000, "CE", 790, "", "", ""]
    ]
    
    return pd.DataFrame(sample_data, columns=symbol_master_columns)


@pytest.fixture(autouse=True)
def setup_and_teardown():
    # Setup - Reset module globals and mock logger
    app.utils._symbol_cache = None
    app.utils._gsheet_client = None
    
    mock_logger = MagicMock()
    original_logger = app.utils.logger
    app.utils.logger = mock_logger
    
    yield mock_logger  # Provide the mock logger to the test
    
    # Teardown - Restore original logger
    app.utils.logger = original_logger


def test_get_gsheet_client(monkeypatch):
    # Arrange
    mock_creds = MagicMock(name="mock_credentials")
    mock_client = MagicMock(name="mock_gspread_client")
    
    # Mock the imported modules
    mock_service_account = MagicMock()
    mock_service_account.ServiceAccountCredentials.from_json_keyfile_name.return_value = mock_creds
    
    mock_gspread = MagicMock()
    mock_gspread.authorize.return_value = mock_client
    
    monkeypatch.setattr(app.utils, "ServiceAccountCredentials", mock_service_account.ServiceAccountCredentials)
    monkeypatch.setattr(app.utils, "gspread", mock_gspread)
    
    # Act - First call should create a new client
    client1 = get_gsheet_client()
    
    # Act - Second call should return the cached client
    client2 = get_gsheet_client()
    
    # Assert
    mock_service_account.ServiceAccountCredentials.from_json_keyfile_name.assert_called_once_with(CREDS_FILE, SCOPE)
    mock_gspread.authorize.assert_called_once_with(mock_creds)
    assert client1 == mock_client
    assert client1 == client2  # Should return the same cached client


def test_load_symbol_master_success(monkeypatch, sample_df):
    # Arrange
    mock_read_csv = MagicMock(return_value=sample_df)
    monkeypatch.setattr(pd, "read_csv", mock_read_csv)
    
    # Act
    load_symbol_master()
    
    # Assert
    mock_read_csv.assert_called_once()
    assert app.utils._symbol_cache is not None
    assert len(app.utils._symbol_cache) == 4
    app.utils.logger.debug.assert_called_with("Loaded symbol master into memory")


def test_load_symbol_master_failure(monkeypatch):
    # Arrange
    mock_read_csv = MagicMock(side_effect=Exception("Connection error"))
    monkeypatch.setattr(pd, "read_csv", mock_read_csv)
    
    # Act
    load_symbol_master()
    
    # Assert
    mock_read_csv.assert_called_once()
    assert app.utils._symbol_cache is not None
    assert app.utils._symbol_cache.empty
    app.utils.logger.error.assert_called_with("Failed to load symbol master: Connection error")


def test_get_symbol_from_csv_nifty_weekly_ce(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = sample_df
    mock_load_master = MagicMock()
    monkeypatch.setattr(app.utils, "load_symbol_master", mock_load_master)
    
    # Act
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    
    # Assert
    assert result == "NIFTY2541719000CE"
    mock_load_master.assert_not_called()  # Should not reload as cache exists


def test_get_symbol_from_csv_nifty_monthly_ce(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = sample_df
    mock_load_master = MagicMock()
    monkeypatch.setattr(app.utils, "load_symbol_master", mock_load_master)
    
    # Act
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "MONTHLY")
    
    # Assert
    assert result == "NIFTY25APR19000CE"
    mock_load_master.assert_not_called()  # Should not reload as cache exists


def test_get_symbol_from_csv_empty_cache(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = None
    
    # Mock load_symbol_master to set the cache
    def mock_load():
        app.utils._symbol_cache = sample_df
    
    mock_load_master = MagicMock(side_effect=mock_load)
    monkeypatch.setattr(app.utils, "load_symbol_master", mock_load_master)
    
    # Act
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    
    # Assert
    assert result == "NIFTY2541719000CE"
    mock_load_master.assert_called_once()  # Should reload as cache is None


def test_get_symbol_from_csv_invalid_expiry_type(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = sample_df
    mock_load_master = MagicMock()
    monkeypatch.setattr(app.utils, "load_symbol_master", mock_load_master)
    
    # Act
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "QUARTERLY")
    
    # Assert
    assert result is None


def test_get_symbol_from_csv_no_matching_symbol(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = sample_df
    mock_load_master = MagicMock()
    monkeypatch.setattr(app.utils, "load_symbol_master", mock_load_master)
    
    # Act
    result = get_symbol_from_csv("SENSEX", 19000, "CE", "WEEKLY")
    
    # Assert
    assert result is None


def test_get_symbol_from_csv_exception(monkeypatch, sample_df):
    # Arrange
    app.utils._symbol_cache = sample_df
    
    # Create a mocked function that will raise an exception during processing
    def mock_df_copy(*args, **kwargs):
        raise Exception("Processing error")
    
    # Patch DataFrame.copy to raise an exception
    monkeypatch.setattr(pd.DataFrame, "copy", mock_df_copy)
    
    # Act
    result = get_symbol_from_csv("NIFTY", 19000, "CE", "WEEKLY")
    
    # Assert
    assert result is None
    app.utils.logger.error.assert_called_with("Exception in get_symbol_from_csv: Processing error")


def test_log_trade_to_sheet_success(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Act
    result = log_trade_to_sheet(mock_client, "NIFTY2541719000CE", "BUY", 50, 150.25, 145.75, 160.0)
    
    # Assert
    mock_client.open_by_key.assert_called_once_with("test_sheet_id")
    mock_sheet_instance.worksheet.assert_called_once_with("Trades")
    mock_sheet.append_row.assert_called_once_with([
        "2023-01-01 12:00:00", "NIFTY2541719000CE", "BUY", 50, 150.25, 145.75, 160.0, "OPEN", "", "", ""
    ])
    assert result is True


def test_log_trade_to_sheet_retry_success(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Mock time.sleep
    mock_sleep = MagicMock()
    monkeypatch.setattr(app.utils.time, "sleep", mock_sleep)
    
    # Create a proper API Error
    class MockAPIError(Exception):
        pass
    
    # Mock the gspread exceptions module
    mock_gspread = MagicMock()
    mock_gspread.exceptions.APIError = MockAPIError
    monkeypatch.setattr(app.utils, "gspread", mock_gspread)
    
    # First call raises error, second succeeds
    mock_sheet.append_row.side_effect = [
        MockAPIError("API error"),
        None
    ]
    
    # Act
    result = log_trade_to_sheet(mock_client, "NIFTY2541719000CE", "BUY", 50, 150.25, 145.75, 160.0)
    
    # Assert
    assert mock_sheet.append_row.call_count == 2
    mock_sleep.assert_called_once_with(1)  # 2^0 = 1
    assert result is True


def test_log_trade_to_sheet_max_retries(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Mock time.sleep
    mock_sleep = MagicMock()
    monkeypatch.setattr(app.utils.time, "sleep", mock_sleep)
    
    # Create a proper API Error
    class MockAPIError(Exception):
        pass
    
    # Mock the gspread exceptions module
    mock_gspread = MagicMock()
    mock_gspread.exceptions.APIError = MockAPIError
    monkeypatch.setattr(app.utils, "gspread", mock_gspread)
    
    # Create a proper TransportError
    class MockTransportError(Exception):
        pass
    
    monkeypatch.setattr(app.utils, "TransportError", MockTransportError)
    
    # All calls fail with API error
    mock_sheet.append_row.side_effect = MockAPIError("API error")
    
    # Act
    result = log_trade_to_sheet(mock_client, "NIFTY2541719000CE", "BUY", 50, 150.25, 145.75, 160.0, retries=3)
    
    # Assert
    assert mock_sheet.append_row.call_count == 3
    assert mock_sleep.call_count == 3
    assert result is False
    app.utils.logger.error.assert_called_with("Max retries reached. Could not log trade.")


def test_log_trade_to_sheet_exception(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_client.open_by_key.side_effect = Exception("Sheet access error")
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Act
    result = log_trade_to_sheet(mock_client, "NIFTY2541719000CE", "BUY", 50, 150.25, 145.75, 160.0)
    
    # Assert
    assert result is False
    app.utils.logger.error.assert_called_with("Failed to log trade to Google Sheet: Sheet access error")


def test_get_open_trades_from_sheet_success(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Header row and some data rows with varying status
    # Match the actual sheet columns: UUID, Timestamp, Symbol, Action, Qty, Entry Price, SL, TP, Status, Exit Price, Exit Time, Reason
    all_values = [
        ["UUID", "Timestamp", "Symbol", "Action", "Qty", "Entry Price", "SL", "TP", "Status", "Exit Price", "Exit Time", "Reason"],
        ["1", "2023-01-01 10:00:00", "NIFTY1", "BUY", "50", "100", "95", "110", "OPEN", "", "", ""],
        ["2", "2023-01-01 11:00:00", "NIFTY2", "SELL", "50", "200", "205", "190", "CLOSED", "195", "2023-01-01 12:00:00", "Target hit"],
        ["3", "2023-01-01 12:00:00", "NIFTY3", "BUY", "25", "300", "295", "310", "OPEN", "", "", ""]
    ]
    mock_sheet.get_all_values.return_value = all_values
    
    # Act
    result = get_open_trades_from_sheet(mock_client)
    
    # Assert
    mock_client.open_by_key.assert_called_once_with("test_sheet_id")
    mock_sheet_instance.worksheet.assert_called_once_with("Trades")
    
    # The expected open trades are rows 1 and 3 in all_values (indices 0 and 2)
    expected_open_trades = [all_values[1], all_values[3]]
    
    # Compare expected vs. actual results
    assert len(result) == len(expected_open_trades)
    
    # Check content of result
    if len(result) > 0 and len(expected_open_trades) > 0:
        assert result[0][2] == "NIFTY1"  # Symbol is now at index 2
        if len(result) > 1 and len(expected_open_trades) > 1:
            assert result[1][2] == "NIFTY3"  # Symbol is now at index 2
    
    app.utils.logger.debug.assert_called_with(f"Fetched {len(result)} open trades")


def test_get_open_trades_from_sheet_custom_sheet(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Match the actual sheet columns: UUID, Timestamp, Symbol, Action, Qty, Entry Price, SL, TP, Status, Exit Price, Exit Time, Reason
    values = [
        ["UUID", "Timestamp", "Symbol", "Action", "Qty", "Entry Price", "SL", "TP", "Status", "Exit Price", "Exit Time", "Reason"],
        ["1", "2023-01-01 10:00:00", "NIFTY1", "BUY", "50", "100", "95", "110", "OPEN", "", "", ""]
    ]
    mock_sheet.get_all_values.return_value = values
    
    # Act
    result = get_open_trades_from_sheet(mock_client, sheet_name="TestSheet")
    
    # Assert
    mock_sheet_instance.worksheet.assert_called_once_with("TestSheet")
    
    # Check the correct data is in the result
    assert len(result) == 1
    if len(result) > 0:
        assert result[0][2] == "NIFTY1"  # Symbol is now at index 2
        assert result[0][8] == "OPEN"    # Status stays at index 8


def test_get_open_trades_from_sheet_exception(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_client.open_by_key.side_effect = Exception("Sheet access error")
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Act
    result = get_open_trades_from_sheet(mock_client)
    
    # Assert
    assert result == []
    app.utils.logger.exception.assert_called_with("Failed to fetch open trades")


def test_update_trade_status_in_sheet_success(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Important: The function looks for trade_id in the FIRST column (index 0)
    trade_id = "2023-01-01 10:00:00"
    mock_sheet.get_all_values.return_value = [
        ["Time", "Symbol", "Action", "Qty", "LTP", "SL", "TP", "Status", "Exit Price", "Exit Time", "Reason"],
        [trade_id, "NIFTY1", "BUY", "50", "100", "95", "110", "OPEN", "", "", ""],
        ["2023-01-01 11:00:00", "NIFTY2", "SELL", "50", "200", "205", "190", "OPEN", "", "", ""]
    ]
    
    # Mock the side effects so we can track the calls
    mock_sheet.update_cell = MagicMock(return_value=None)
    
    # Act
    result = update_trade_status_in_sheet(
        mock_client, trade_id, "CLOSED", 105.5, "Target hit"
    )
    
    # Assert
    mock_client.open_by_key.assert_called_once_with("test_sheet_id")
    mock_sheet_instance.worksheet.assert_called_once_with("Trades")
    
    # Print call args to debug
    print(f"update_cell calls: {mock_sheet.update_cell.call_args_list}")
    
    # Check cells were updated
    assert mock_sheet.update_cell.call_count >= 4  # At least 4 calls should be made
    assert result is True
    app.utils.logger.debug.assert_called_with(
        f"Updated trade {trade_id} with status=CLOSED, exit_price=105.5"
    )


def test_update_trade_status_in_sheet_trade_not_found(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Important: The function looks for trade_id in the FIRST column (index 0)
    mock_sheet.get_all_values.return_value = [
        ["Time", "Symbol", "Action", "Qty", "LTP", "SL", "TP", "Status", "Exit Price", "Exit Time", "Reason"],
        ["2023-01-01 10:00:00", "NIFTY1", "BUY", "50", "100", "95", "110", "OPEN", "", "", ""]
    ]
    
    # Mock the update_cell method
    mock_sheet.update_cell = MagicMock(return_value=None)
    
    # Act - Try to update a trade that doesn't exist
    result = update_trade_status_in_sheet(
        mock_client, "2023-01-01 11:00:00", "CLOSED", 105.5, "Target hit"
    )
    
    # Assert
    assert result is False
    # No cells should be updated
    mock_sheet.update_cell.assert_not_called()
    app.utils.logger.warning.assert_called_with("Trade ID 2023-01-01 11:00:00 not found for update.")


def test_update_trade_status_in_sheet_exception(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_client.open_by_key.side_effect = Exception("Sheet access error")
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Act
    result = update_trade_status_in_sheet(
        mock_client, "2023-01-01 10:00:00", "CLOSED", 105.5, "Target hit"
    )
    
    # Assert
    assert result is False
    app.utils.logger.error.assert_called_with("Failed to update trade status: Sheet access error")


def test_update_trade_status_in_sheet_custom_sheet(monkeypatch):
    # Arrange
    mock_client = MagicMock()
    mock_sheet = MagicMock()
    mock_sheet_instance = MagicMock()
    mock_sheet_instance.worksheet.return_value = mock_sheet
    mock_client.open_by_key.return_value = mock_sheet_instance
    
    monkeypatch.setattr(os, "getenv", lambda x: "test_sheet_id")
    
    # Mock datetime at the module level
    class MockDateTime:
        @classmethod
        def now(cls):
            return datetime(2023, 1, 1, 12, 0, 0)
        
        @staticmethod
        def strftime(dt, fmt):
            return datetime.strftime(dt, fmt)
    
    monkeypatch.setattr(app.utils, "datetime", MockDateTime)
    
    # Important: The function looks for trade_id in the FIRST column (index 0)
    trade_id = "2023-01-01 10:00:00"
    mock_sheet.get_all_values.return_value = [
        ["Time", "Symbol", "Action", "Qty", "LTP", "SL", "TP", "Status", "Exit Price", "Exit Time", "Reason"],
        [trade_id, "NIFTY1", "BUY", "50", "100", "95", "110", "OPEN", "", "", ""]
    ]
    
    # Mock the update_cell method to track calls
    mock_sheet.update_cell = MagicMock(return_value=None)
    
    # Act
    result = update_trade_status_in_sheet(
        mock_client, trade_id, "CLOSED", 105.5, "Target hit", sheet_name="TestSheet"
    )
    
    # Assert
    mock_sheet_instance.worksheet.assert_called_once_with("TestSheet")
    assert mock_sheet.update_cell.call_count >= 4  # At least 4 calls should be made
    assert result is True