# ------------------ app/monitor.py ------------------
import time
import threading
from datetime import datetime, time as dt_time
from queue import Queue
from app.auth import get_fyers
from app.utils import get_open_trades_from_sheet, update_trade_status_in_sheet
from app.fyers_api import get_ltp
import traceback
import os
result_queue = Queue()
polling_interval = int(os.getenv("POLLING_INTERVAL", 30))

def start_monitoring_service():
    monitored = {}
    while True:
        try:
            print("[MONITOR] Fetching open trades")
            open_trades = get_open_trades_from_sheet()
            print(f"[MONITOR] Open trades: {open_trades}")
            for trade in open_trades:
                trade_id = trade[0]  # unique ID
                if trade_id not in monitored:
                    print(f"[MONITOR] Starting monitoring for trade ID: {trade_id}")
                    thread = MonitorThread(trade)
                    thread.start()
                    monitored[trade_id] = thread

            # Collect completed trades and update GSheet
            while not result_queue.empty():
                #TODO : this is only update either SL or TP hit. 
                #need to add monitor for trades that are closed when opposite signal is received
                trade, status, ltp = result_queue.get()
                print(f"[MONITOR] Updating: Trade {trade[0]} status: {status}, LTP: {ltp}")
                update_trade_status_in_sheet(trade, status, ltp)

        except Exception as e:
            traceback.print_exc()
            print(f"[MONITOR ERROR] {e}")
        time.sleep(polling_interval)

class MonitorThread(threading.Thread):
    def __init__(self, trade):
        super().__init__(daemon=True)
        self.trade = trade
        self.fyers = get_fyers()
        self.trade_id = trade[0]  # unique_id now in column 0
        self.symbol = trade[2]
        self.action = trade[3].upper()

    def run(self):
        try:
            while True:
                now = datetime.now().time()
                ltp = get_ltp(self.symbol, self.fyers)
                if not isinstance(ltp, (float, int)):
                    continue

                sl = float(self.trade[6])
                tp = float(self.trade[7])

                if now >= dt_time(15, 25):
                    result_queue.put((self.trade, "TIME EXIT", ltp))
                    break

                if self.action == "BUY":
                    if ltp <= sl:
                        result_queue.put((self.trade, "STOPLOSS HIT", ltp))
                        break
                    elif ltp >= tp:
                        result_queue.put((self.trade, "TARGET HIT", ltp))
                        break
                elif self.action == "SELL":
                    if ltp >= sl:
                        result_queue.put((self.trade, "STOPLOSS HIT", ltp))
                        break
                    elif ltp <= tp:
                        result_queue.put((self.trade, "TARGET HIT", ltp))
                        break
                time.sleep(polling_interval)
        except Exception as e:
            traceback.print_exc()
            print(f"[MONITOR THREAD ERROR] {e}")