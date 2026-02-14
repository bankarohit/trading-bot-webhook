# Gunicorn vs Uvicorn – and why this project uses Gunicorn

## Difference

| | **Gunicorn** | **Uvicorn** |
|---|--------------|-------------|
| **Protocol** | **WSGI** (synchronous Python web standard) | **ASGI** (async Python web standard) |
| **Typical use** | Django, Flask, other WSGI apps | FastAPI, Starlette, async frameworks |
| **Concurrency** | Multiple **processes** (workers): `-w 4` = 4 processes, each handling one request at a time (or more with gevent/eventlet) | Single **process**, one **event loop**: many concurrent connections via async I/O |
| **Our app** | Runs Flask **natively** (`main:app`) | Runs Flask only by **wrapping** it in ASGI (`WSGIMiddleware(app)` → `main:asgi_app`) |
| **Process model** | 1 master + N workers (e.g. `-w 1` or `-w 2`) | 1 process, no workers |

## How it affects this project

- The app is **Flask** (WSGI). It can be served by:
  - **Gunicorn** → direct: `gunicorn -b 0.0.0.0:8080 main:app`
  - **Uvicorn** → indirect: wrap Flask in `WSGIMiddleware`, then `uvicorn main:asgi_app`
- Some routes are `async def` (e.g. webhook, health_check) because they `await` Fyers calls. Under Gunicorn, Flask still runs these correctly (Flask 2.0+ supports async views); the async I/O benefit is mainly while waiting on Fyers/HTTP.
- **Cloud Run** scales by **instance**. Each instance runs one container. So:
  - **Gunicorn with `-w 1`**: one worker per instance, one request at a time per instance. Enough for low traffic.
  - **Gunicorn with `-w 2`**: two workers per instance, two concurrent requests per instance; more memory.
  - **Uvicorn (single process)**: one process, many concurrent I/O-bound requests in one event loop; but Flask is still run via a WSGI adapter, so you don’t get “pure” ASGI benefits.

For **personal use** and **TradingView-only** traffic, one or two requests at a time per instance is enough. Raw throughput difference between Gunicorn and Uvicorn is not critical here.

## Recommendation for this project: **Gunicorn**

1. **Matches README** – Docs already say “Gunicorn”; the Dockerfile was using Uvicorn, which caused the mismatch.
2. **Simpler** – No ASGI wrapper or `asgi_app` in the deploy path; Flask runs as intended for WSGI.
3. **Standard for Flask** – Gunicorn is the usual production server for Flask apps.
4. **Enough concurrency** – One worker (`-w 1`) is fine for your described use; you can use `-w 2` if you want a bit more concurrency per instance without much extra complexity.

**Current setup (non-blocking):** The Dockerfile uses **Gunicorn with Uvicorn workers** (`-k uvicorn.workers.UvicornWorker`) and serves `main:asgi_app`. So each worker runs an async event loop: one worker can handle many concurrent requests. While one request is waiting on Fyers or HTTP, the server can accept and process others. For local development you can still run `python main.py` or `uvicorn main:asgi_app`; production uses Gunicorn + Uvicorn worker for non-blocking behavior.
