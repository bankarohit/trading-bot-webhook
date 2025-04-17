# ------------------ tests/test_monitor.py ------------------
import unittest
from unittest.mock import patch, MagicMock
from app.monitor import start_monitoring_service, MonitorThread, result_queue
import threading
import time
from datetime import datetime, time as dt_time

class TestMonitor(unittest.TestCase):

    @patch("app.monitor.get_open_trades_from_sheet")
    @patch("app.monitor.update_trade_status_in_sheet")
    @patch("app.monitor.time.sleep", return_value=None)
    def test_start_monitoring_service_skips_and_processes(self, mock_sleep, mock_update, mock_get_trades):
        valid_trade = ["id2", "ts", "SYMBOL", "BUY", "75", "200", "10", "20"]
        invalid_trade = ["id1", "ts", "SYMBOL", "BUY", "75", "", "", ""]

        mock_get_trades.return_value = [invalid_trade, valid_trade]

        mock_thread = MagicMock()
        with patch("app.monitor.MonitorThread", return_value=mock_thread):
            with patch("app.monitor.result_queue.empty", side_effect=[True, True, False, True]):
                with patch("app.monitor.result_queue.get", return_value=(valid_trade, "CLOSED", 220, "TP")):
                    t = threading.Thread(target=start_monitoring_service)
                    t.daemon = True
                    t.start()
                    time.sleep(0.2)
                    t.join(timeout=0.5)
                    self.assertTrue(mock_thread.start.called)
                    self.assertTrue(mock_update.called)

    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_buy_hits_tp(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(14, 0)

        trade = ["t1", "", "SYMBOL", "BUY", "75", "200", "10", "20"]
        mock_ltp.side_effect = [200, 221]  # First LTP normal, second triggers TP at entry + 20
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 221, "TP"))

    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_sell_hits_sl(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(14, 0)

        trade = ["t2", "", "SYMBOL", "SELL", "75", "200", "10", "20"]
        mock_ltp.side_effect = [200, 210]  # First LTP normal, second triggers SL
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 210, "SL"))

    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_timed_exit(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(15, 26)

        trade = ["t3", "", "SYMBOL", "BUY", "75", "200", "10", "20"]
        mock_ltp.side_effect = [200, 205]  # Second value triggers time exit, LTP doesn't matter
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 200, "TIMELY EXIT"))

    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_sell_hits_tp(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(14, 0)

        trade = ["t4", "", "SYMBOL", "SELL", "75", "200", "10", "20"]
        mock_ltp.side_effect = [200, 179]  # First LTP normal, second triggers TP at entry - 20
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 179, "TP"))


    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_buy_hits_sl(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(14, 0)

        trade = ["t5", "", "SYMBOL", "BUY", "75", "200", "10", "20"]
        mock_ltp.side_effect = [200, 190]  # First LTP normal, second triggers SL for BUY
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 190, "SL"))
    
    @patch("app.monitor.get_ltp")
    @patch("app.monitor.result_queue.put")
    @patch("app.monitor.time.sleep", return_value=None)
    @patch("app.monitor.datetime")
    def test_monitor_thread_invalid_ltp_skips(self, mock_datetime, mock_sleep, mock_result, mock_ltp):
        mock_datetime.now.return_value.time.return_value = dt_time(14, 0)

        trade = ["t6", "", "SYMBOL", "BUY", "75", "200", "10", "20"]
        mock_ltp.side_effect = [None, 221]  # First LTP is invalid, second triggers TP
        thread = MonitorThread(trade, sheet_client=MagicMock(), fyers_client=MagicMock())
        thread.run()
        mock_result.assert_called_with((trade, "CLOSED", 221, "TP"))


if __name__ == '__main__':
    unittest.main()

