# ------------------ app/monitor.py ------------------
import time
import threading
from datetime import datetime, time as dt_time
from queue import Queue
from app.auth import get_fyers
from app.utils import get_gsheet_client
from app.utils import get_open_trades_from_sheet, update_trade_status_in_sheet
from app.fyers_api import get_ltp
import traceback
import os
import pytz
import logging
from app.config import load_env_variables

load_env_variables()
tz = pytz.timezone("Asia/Kolkata")
result_queue = Queue()
polling_interval = int(os.getenv("POLLING_INTERVAL", 30))
logger = logging.getLogger(__name__)

sheet_client = get_gsheet_client()
fyers_client = get_fyers()

def start_monitoring_service():
    monitored = {}
    while True:
        try:
            logger.info("[MONITOR] Fetching open trades")
            open_trades = get_open_trades_from_sheet(sheet_client)
            logger.info(f"[MONITOR] Open trades: {open_trades}")
            for trade in open_trades:
                trade_id = trade[0]
                if not (trade[5] and trade[6] and trade[7]):
                    logger.warning(f"[MONITOR] Skipping trade ID: {trade_id} due to missing entry/SL/TP")
                    continue
                if trade_id not in monitored:
                    logger.info(f"[MONITOR] Starting monitoring for trade ID: {trade_id} with entry={trade[5]}, sl={trade[6]}, tp={trade[7]}")
                    thread = MonitorThread(trade, sheet_client, fyers_client)
                    thread.start()
                    monitored[trade_id] = thread

            while not result_queue.empty():
                trade, status, ltp, reason = result_queue.get()
                logger.info(f"[MONITOR] Updating: Trade {trade[0]} status: {status}, LTP: {ltp}, Reason: {reason}")
                update_trade_status_in_sheet(sheet_client, trade, status, ltp, reason)
                trade_id = trade[0]
                if trade_id in monitored:
                    logger.info(f"[MONITOR] Cleaning up trade ID: {trade_id}")
                    monitored.pop(trade_id)

        except Exception as e:
            logger.exception(f"[MONITOR ERROR] {e}")
        time.sleep(polling_interval)

class MonitorThread(threading.Thread):
    def __init__(self, trade, sheet_client, fyers_client):
        super().__init__(daemon=True)
        self.trade = trade
        self.sheet_client = sheet_client
        self.fyers = fyers_client
        self.trade_id = trade[0]  # unique_id now in column 0
        self.symbol = trade[2]
        self.action = trade[3].upper()

    def run(self):
        try:
            while True:
                now = datetime.now(tz).time()
                ltp = get_ltp(self.fyers, self.symbol)
                logger.debug(f"[MONITOR] Current time: {now}")
                logger.debug(f"[MONITOR] LTP for {self.symbol}: {ltp}")
                if not isinstance(ltp, (float, int)):
                    continue

                try:
                    sl = float(self.trade[6]) if self.trade[6] else None
                except ValueError:
                    sl = None
                try:
                    tp = float(self.trade[7]) if self.trade[7] else None
                except ValueError:
                    tp = None

                if now >= dt_time(15, 25):
                    result_queue.put((self.trade, "CLOSED", ltp, "TIMELY EXIT"))
                    logger.info(f"[MONITOR] Thread ending for {self.symbol} due to TIMELY EXIT")
                    break

                try:
                    entry = float(self.trade[5]) if self.trade[5] else ltp
                except ValueError:
                    entry = ltp

                if self.action == "BUY":
                    if sl is not None and ltp <= entry - sl:
                        result_queue.put((self.trade, "CLOSED", ltp, "SL"))
                        break
                    elif tp is not None and ltp >= entry + tp:
                        result_queue.put((self.trade, "CLOSED", ltp, "TP"))
                        break
                elif self.action == "SELL":
                    if sl is not None and ltp >= entry + sl:
                        result_queue.put((self.trade, "CLOSED", ltp, "SL"))
                        break
                    elif tp is not None and ltp <= entry - tp:
                        result_queue.put((self.trade, "CLOSED", ltp, "TP"))
                        break
                time.sleep(polling_interval)
        except Exception as e:
            logger.exception(f"[MONITOR THREAD ERROR] {e}")
