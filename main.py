from app import create_app
from app.config import load_env_variables
from app.logging_config import configure_logging

load_env_variables()
configure_logging()

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
