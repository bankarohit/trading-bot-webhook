# ------------------ main.py ------------------
from app import create_app
import threading
from app.monitor import start_monitoring_service

app = create_app()

if __name__ == "__main__":
    monitorThread = threading.Thread(target=start_monitoring_service, daemon=True)
    monitorThread.start()
    app.run(host="0.0.0.0", port=8080)