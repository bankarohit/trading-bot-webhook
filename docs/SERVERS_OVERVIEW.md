# Python Web Servers: Brief Overview

When you run a web app (Flask, Django, FastAPI, etc.), something has to **listen for HTTP requests** and **run your code** to handle them. That “something” is a **web server** (or **application server**). It sits in front of your app and is what actually binds to a port (e.g. 8080) and talks to the internet.

Your app code (e.g. “when someone POSTs to /webhook, do this”) is separate from the server. The server’s job is to accept connections, pass the request to your app, and send back the response.

---

## Gunicorn (Green Unicorn)

**What it is:** A production-grade **WSGI** server for Python. WSGI is the standard interface between a web server and sync Python web apps (Flask, Django, etc.). Gunicorn runs your app in one or more **worker processes** and handles incoming requests by giving each request to a worker.

**Use cases:**
- Running **Flask** or **Django** in production
- Deploying on Linux (very common on VMs, Docker, Cloud Run, etc.)
- When you want **multiple processes** (workers) to handle several requests at once

**Benefits:**
- Mature, widely used, lots of docs and examples
- Simple to run: `gunicorn -w 2 -b 0.0.0.0:8080 main:app`
- You can scale by adding workers (`-w 4`, etc.) or by adding more machines/containers
- No need to change your Flask/Django app; it “just works” with WSGI

**Limitation:** It’s built for **WSGI** (sync). For fully async frameworks (e.g. FastAPI written in async style), people often use an ASGI server instead (e.g. Uvicorn), though Gunicorn can also run ASGI apps via a worker class.

---

## Uvicorn

**What it is:** A fast **ASGI** server for Python. ASGI is the async counterpart to WSGI: it supports async/await and long-lived connections (e.g. WebSockets). Uvicorn uses a single process with an **event loop**: one process can handle many concurrent connections while they’re waiting on I/O (network, database).

**Use cases:**
- Running **FastAPI**, **Starlette**, or other **ASGI** apps
- When you want high concurrency with **async** code (many connections, few CPU-bound tasks)
- WebSockets, streaming, or other long-lived connections

**Benefits:**
- Very fast for I/O-bound, async workloads
- Single process can serve many concurrent requests without one request blocking another (while waiting on network/DB)
- Native fit for modern async frameworks

**Limitation:** Your app must speak **ASGI**. Traditional Flask/Django apps speak WSGI; to run them under Uvicorn you wrap them (e.g. with `WSGIMiddleware`), so you don’t get the full async benefits of a “native” ASGI app.

---

## Other tools you can use instead

| Tool | Type | Typical use | Note |
|------|------|-------------|------|
| **uWSGI** | WSGI (and more) | Django, Flask, high-traffic sites | Very configurable, can do caching, static files, multiple apps. Steeper learning curve. |
| **Waitress** | WSGI | Flask, Django, Windows or cross‑platform | Pure Python, no C extensions. Easy to install; good for moderate traffic and when you want to avoid native dependencies. |
| **Hypercorn** | ASGI | FastAPI, Starlette, Quart | Similar role to Uvicorn; supports HTTP/2 and can run async apps. |
| **Daphne** | ASGI | Django Channels, async Django | Originally for Django Channels (WebSockets); can run ASGI apps. |
| **Flask dev server** (`app.run()`) | WSGI | Local development only | Single-threaded, not secure or scalable; never use for production. |

So:
- **Flask/Django in production:** often **Gunicorn** or **uWSGI** (WSGI).
- **FastAPI / async apps:** often **Uvicorn** or **Hypercorn** (ASGI).
- **Simple or Windows-friendly:** **Waitress** (WSGI) is an option.

For this project (Flask, personal use, Cloud Run), **Gunicorn** is a good fit: it’s the usual choice for Flask and matches how the app is written. See [GUNICORN_VS_UVICORN.md](GUNICORN_VS_UVICORN.md) for why we use Gunicorn here instead of Uvicorn.
