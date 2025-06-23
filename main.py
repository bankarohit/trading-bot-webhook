from app import create_app
import threading
from app.config import load_env_variables
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)

load_env_variables()

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
