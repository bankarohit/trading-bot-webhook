FROM python:3.12-slim

WORKDIR /app

# Install build dependencies and Python packages
COPY requirements.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libffi-dev \
        libssl-dev \
        ca-certificates \
        curl && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get purge -y --auto-remove build-essential && \
    rm -rf /var/lib/apt/lists/*


# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY . .

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl --fail http://localhost:8080/readyz || exit 1

# UvicornWorker = async event loop per worker: one worker can handle many concurrent requests (non-blocking).
# While one request awaits Fyers/HTTP, others are served. Use -w 2 for two async workers if needed.
CMD ["gunicorn", "main:asgi_app", "-w", "1", "-k", "uvicorn.workers.UvicornWorker", "-b", "0.0.0.0:8080"]

