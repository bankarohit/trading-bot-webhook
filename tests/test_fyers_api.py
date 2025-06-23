import os
import sys
import unittest
from unittest.mock import patch, MagicMock
import pandas as pd
import logging

# Make sure we can import the app package and provide required env variables
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("FYERS_APP_ID", "dummy")
os.environ.setdefault("FYERS_SECRET_ID", "dummy")
os.environ.setdefault("FYERS_REDIRECT_URI", "http://localhost")
os.environ.setdefault("WEBHOOK_SECRET_TOKEN", "dummy")
os.environ.setdefault("GOOGLE_SHEET_ID", "dummy")
os.environ.setdefault("FYERS_PIN", "0000")
os.environ.setdefault("FYERS_AUTH_CODE", "dummy")

from app.fyers_api import (
    _validate_order_params,
    _get_default_qty,
    get_ltp,
    place_order,
    valid_product_types
)

class TestFyersAPI(unittest.TestCase):
    """Test cases for the Fyers API module."""

    def setUp(self):
        """Set up test environment."""
        # Create a mock DataFrame for testing
        self.mock_symbol_df = pd.DataFrame({
            'symbol_ticker': ['NSE:SBIN-EQ', 'NSE:RELIANCE-EQ', 'NSE:INFY-EQ'],
            'lot_size': ['50', '100', '75']
        })
        
        # Create a mock Fyers model instance
        self.mock_fyers = MagicMock()

    def tearDown(self):
        """Clean up after each test."""
        pass

    # Tests for _validate_order_params
    def test_validate_order_params_with_valid_inputs(self):
        """Test _validate_order_params with all valid parameters."""
        qty, sl, tp, product_type = _validate_order_params(
            symbol="NSE:SBIN-EQ", 
            qty=10,
            sl=5.0,
            tp=15.0,
            productType="CNC"
        )
        
        self.assertEqual(qty, 10)
        self.assertEqual(sl, 5.0)
        self.assertEqual(tp, 15.0)
        self.assertEqual(product_type, "CNC")

    @patch('app.fyers_api._get_default_qty', return_value=50)
    def test_validate_order_params_with_missing_qty(self, mock_get_default_qty):
        """Test _validate_order_params with missing quantity."""
        qty, sl, tp, product_type = _validate_order_params(
            symbol="NSE:SBIN-EQ",
            qty=None,
            sl=5.0,
            tp=15.0,
            productType="CNC"
        )
        
        self.assertEqual(qty, 50)  # Should get default qty
        self.assertEqual(sl, 5.0)
        self.assertEqual(tp, 15.0)
        self.assertEqual(product_type, "CNC")
        mock_get_default_qty.assert_called_once_with("NSE:SBIN-EQ")

    def test_validate_order_params_with_invalid_sl_tp(self):
        """Test _validate_order_params with invalid stop-loss and take-profit values."""
        qty, sl, tp, product_type = _validate_order_params(
            symbol="NSE:SBIN-EQ",
            qty=10,
            sl=-5.0,  # Invalid
            tp=0,     # Invalid
            productType="CNC"
        )
        
        self.assertEqual(qty, 10)
        self.assertEqual(sl, 10.0)  # Default value
        self.assertEqual(tp, 20.0)  # Default value
        self.assertEqual(product_type, "CNC")

    @patch('app.fyers_api.logger')
    def test_validate_order_params_with_invalid_product_type(self, mock_logger):
        """Test _validate_order_params with invalid product type."""
        qty, sl, tp, product_type = _validate_order_params(
            symbol="NSE:SBIN-EQ",
            qty=10,
            sl=5.0,
            tp=15.0,
            productType="INVALID"  # Invalid product type
        )
        
        self.assertEqual(qty, 10)
        self.assertEqual(sl, 5.0)
        self.assertEqual(tp, 15.0)
        self.assertEqual(product_type, "BO")  # Default value
        mock_logger.warning.assert_called_once()

    def test_validate_order_params_with_string_sl_tp(self):
        """Test _validate_order_params with string SL/TP values that can be converted to float."""
        qty, sl, tp, product_type = _validate_order_params(
            symbol="NSE:SBIN-EQ",
            qty=10,
            sl="5.0",
            tp="15.0",
            productType="CNC"
        )
        
        self.assertEqual(qty, 10)
        self.assertEqual(sl, 5.0)
        self.assertEqual(tp, 15.0)
        self.assertEqual(product_type, "CNC")
    
    def test_get_default_qty_with_valid_symbol(self):
        """Test _get_default_qty with valid symbol in cache."""
        
        # Create a real test DataFrame with our test data
        test_df = pd.DataFrame({
            'symbol_ticker': ['NSE:SBIN-EQ', 'NSE:RELIANCE-EQ'],
            'lot_size': ['50', '100']
        })
        
        # Patch the global _symbol_cache variable directly
        with patch('app.utils._symbol_cache', test_df):
            # Now when the function runs, it will use our test DataFrame
            # with real pandas operations
            
            # Test with first symbol
            qty = _get_default_qty("NSE:SBIN-EQ")
            self.assertEqual(qty, 50)
            
            # Test with second symbol
            qty = _get_default_qty("NSE:RELIANCE-EQ") 
            self.assertEqual(qty, 100)
            
    @patch('app.utils._symbol_cache')
    @patch('app.fyers_api.logger')
    def test_get_default_qty_with_invalid_lot_size(self, mock_logger, mock_symbol_cache):
        """Test _get_default_qty with invalid lot size value."""
        # Create a mock DataFrame with invalid lot size
        invalid_df = pd.DataFrame({
            'symbol_ticker': ['NSE:SBIN-EQ'],
            'lot_size': ['invalid']  # Non-numeric lot size
        })
        
        mock_symbol_cache.__getitem__.return_value = invalid_df
        
        qty = _get_default_qty("NSE:SBIN-EQ")
        self.assertEqual(qty, 1)  # Default when lot size is invalid
        mock_logger.warning.assert_called_once()

    @patch('app.utils._symbol_cache')
    @patch('app.fyers_api.logger')
    def test_get_default_qty_with_nonexistent_symbol(self, mock_logger, mock_symbol_cache):
        """Test _get_default_qty with symbol not in cache."""
        # Create an empty DataFrame to simulate "no match found"
        empty_result = pd.DataFrame(columns=['symbol_ticker', 'lot_size'])
        
        # When the function does _symbol_cache[_symbol_cache['symbol_ticker'] == "NSE:NONEXISTENT-EQ"]
        # We want it to get our empty DataFrame
        mock_symbol_cache.__getitem__.return_value = empty_result
        
        qty = _get_default_qty("NSE:NONEXISTENT-EQ")
        self.assertEqual(qty, 1)  # Should return default value 1
        mock_logger.warning.assert_called_once()

    @patch('app.utils._symbol_cache', None)
    @patch('app.utils.load_symbol_master')
    def test_get_default_qty_with_none_cache(self, mock_load_symbol_master):
        """Test _get_default_qty when symbol cache is None."""
        # Use side_effect to set the cache after load_symbol_master is called
        def side_effect():
            import app.utils
            app.utils._symbol_cache = self.mock_symbol_df
        
        mock_load_symbol_master.side_effect = side_effect
        
        qty = _get_default_qty("NSE:SBIN-EQ")
        
        mock_load_symbol_master.assert_called_once()
        self.assertEqual(qty, 50)

    def test_get_ltp_success(self):
        """Test get_ltp with successful API response."""
        # Based on the error log, the get_ltp function is checking for
        # specific fields in the response that our mock doesn't have
        
        # Create a more complete mock response structure
        self.mock_fyers.quotes.return_value = {
            "s": "ok",  # Status field
            "code": 200,  # Response code
            "d": [
                {
                    "n": "NSE:SBIN-EQ",  # Name field
                    "s": "ok",  # Status field for this symbol
                    "v": {
                        "lp": 500.25,  # Last price field
                        # Add any other fields the function might be checking
                        "bid": 500.0,
                        "ask": 500.5
                    }
                }
            ],
            "message": ""  # Empty message field
        }
        
        result = get_ltp("NSE:SBIN-EQ", self.mock_fyers)
        
        # Verify the function returns the last price
        self.assertEqual(result, 500.25)
        # Verify the quotes method was called with correct parameters
        self.mock_fyers.quotes.assert_called_once_with({"symbols": "NSE:SBIN-EQ"})

    def test_get_ltp_empty_response(self):
        """Test get_ltp with empty API response."""
        # Mock empty response
        self.mock_fyers.quotes.return_value = {
            "d": []
        }
        
        result = get_ltp("NSE:SBIN-EQ", self.mock_fyers)
        
        # Verify function handles empty response gracefully
        self.assertIsNone(result)

    @patch('app.fyers_api.logger')
    def test_get_ltp_exception(self, mock_logger):
        """Test get_ltp with API exception."""
        # Mock exception
        self.mock_fyers.quotes.side_effect = Exception("API Error")
        
        result = get_ltp("NSE:SBIN-EQ", self.mock_fyers)
        
        # Verify function handles exception correctly
        self.assertEqual(result, {"code": -1, "message": "API Error"})
        mock_logger.exception.assert_called_once()

    # Tests for place_order
    @patch('app.fyers_api._validate_order_params', return_value=(10, 5.0, 15.0, "CNC"))
    @patch('app.fyers_api.logger')
    def test_place_order_success(self, mock_logger, mock_validate_params):
        """Test place_order with successful order placement."""
        # Mock successful order placement
        self.mock_fyers.place_order.return_value = {
            "code": 0,
            "message": "Success",
            "id": "order123"
        }
        
        result = place_order(
            symbol="NSE:SBIN-EQ",
            qty=10,
            action="BUY",
            sl=5.0,
            tp=15.0,
            productType="CNC",
            fyersModelInstance=self.mock_fyers
        )
        
        # Verify the function returns the expected response
        self.assertEqual(result, {"code": 0, "message": "Success", "id": "order123"})
        
        # Verify logger.debug was called
        self.assertEqual(mock_logger.debug.call_count, 2)
        
        # Verify place_order was called with correct parameters
        expected_order_data = {
            "symbol": "NSE:SBIN-EQ",
            "qty": 10,
            "type": 2,  # Market order
            "side": 1,  # Buy
            "productType": "CNC",
            "limitPrice": 0,
            "stopPrice": 0,
            "validity": "DAY",
            "disclosedQty": 0,
            "offlineOrder": False,
            "stopLoss": 5.0,
            "takeProfit": 15.0
        }
        self.mock_fyers.place_order.assert_called_once_with(expected_order_data)

    @patch('app.fyers_api._validate_order_params', return_value=(10, 5.0, 15.0, "CNC"))
    def test_place_order_sell(self, mock_validate_params):
        """Test place_order with SELL action."""
        # Test with SELL action
        self.mock_fyers.place_order.return_value = {"code": 0, "message": "Success"}
        
        result = place_order(
            symbol="NSE:SBIN-EQ",
            qty=10,
            action="SELL",  # Sell action
            sl=5.0,
            tp=15.0,
            productType="CNC",
            fyersModelInstance=self.mock_fyers
        )
        
        # Verify place_order was called with side=-1 (Sell)
        called_args = self.mock_fyers.place_order.call_args[0][0]
        self.assertEqual(called_args["side"], -1)

    @patch('app.fyers_api._validate_order_params', return_value=(10, 5.0, 15.0, "CNC"))
    @patch('app.fyers_api.logger')
    def test_place_order_exception(self, mock_logger, mock_validate_params):
        """Test place_order with API exception."""
        # Mock exception during order placement
        self.mock_fyers.place_order.side_effect = Exception("Order API Error")
        
        result = place_order(
            symbol="NSE:SBIN-EQ",
            qty=10,
            action="BUY",
            sl=5.0,
            tp=15.0,
            productType="CNC",
            fyersModelInstance=self.mock_fyers
        )
        
        # Verify function handles exception correctly
        self.assertEqual(result, {"code": -1, "message": "Order API Error"})
        mock_logger.exception.assert_called_once()


if __name__ == '__main__':
    unittest.main()