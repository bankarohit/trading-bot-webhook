### ------------------ Dockerfile ------------------
    FROM python:3.10-slim

    # Set environment variables
    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1

    WORKDIR /app
    
    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt
    
    COPY . .
    
    EXPOSE 8080
    
    HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl --fail http://localhost:8080/readyz || exit 1
    
    CMD ["python", "main.py"]

### ------------------ Dockerfile -------------------
