import json
import os
import threading
import time
from contextlib import asynccontextmanager
from ipaddress import ip_address, ip_network
from pathlib import Path

import markdown
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from .sync_logic import get_mappings_data, sync_pihole_dns, get_sync_interval

log = structlog.get_logger()

def get_rate_limit():
    return os.getenv("RATE_LIMIT", "100/minute")

limiter = Limiter(key_func=get_remote_address)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the sync thread on application startup
    sync_thread = threading.Thread(target=sync_pihole_dns, daemon=True)
    sync_thread.start()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    yield
    # No cleanup needed on shutdown

app = FastAPI(lifespan=lifespan, docs_url="/api/docs", redoc_url="/api/redoc")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'; style-src 'self' https://cdn.jsdelivr.net; script-src 'self' https://cdn.jsdelivr.net"
        return response

app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(404)
async def not_found_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(request, "404.html", status_code=404)

@app.exception_handler(500)
async def internal_server_error_exception_handler(request: Request, exc: Exception):
    return templates.TemplateResponse(request, "500.html", status_code=500)


class IPWhitelistMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        allowed_subnets_str = os.getenv("ALLOWED_SUBNETS")
        if allowed_subnets_str:
            allowed_subnets = [ip_network(subnet.strip()) for subnet in allowed_subnets_str.split(",")]
            client_ip_str = request.headers.get("X-Forwarded-For", request.client.host)
            client_ip = ip_address(client_ip_str.split(",")[0].strip())
            if not any(client_ip in subnet for subnet in allowed_subnets):
                return JSONResponse(status_code=403, content={"detail": "Forbidden"})
        response = await call_next(request)
        return response


app.add_middleware(IPWhitelistMiddleware)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
@limiter.limit(get_rate_limit)
async def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "sync_interval": get_sync_interval(),
        "app_logo_url": os.getenv("APP_LOGO_URL"),
        "app_color_scheme": os.getenv("APP_COLOR_SCHEME"),
    })


@app.post("/update-meraki")
@limiter.limit(get_rate_limit)
async def update_meraki(request: Request):
    """Triggers a Meraki data fetch and sync."""
    log.info("Meraki update requested via web UI.")
    try:
        # Running the sync in a separate thread to avoid blocking the web server
        sync_thread = threading.Thread(target=sync_pihole_dns, args=("meraki",))
        sync_thread.start()
        return JSONResponse(content={"message": "Meraki update process started."})
    except Exception as e:
        log.error("Error starting Meraki update", error=e)
        return JSONResponse(content={"message": f"Meraki update failed to start: {e}"}, status_code=500)

@app.post("/update-pihole")
@limiter.limit(get_rate_limit)
async def update_pihole(request: Request):
    log.info("Pi-hole update requested via web UI.")
    try:
        # Running the sync in a separate thread to avoid blocking the web server
        sync_thread = threading.Thread(target=sync_pihole_dns, args=("pihole",))
        sync_thread.start()
        return JSONResponse(content={"message": "Pi-hole update process started."})
    except Exception as e:
        log.error("Error starting Pi-hole update", error=e)
        return JSONResponse(content={"message": f"Pi-hole update failed to start: {e}"}, status_code=500)

@app.get("/check-pihole-error")
@limiter.limit(get_rate_limit)
async def check_pihole_error(request: Request):
    log_file = Path('/app/logs/sync.log')
    if log_file.exists():
        log_content = log_file.read_text()
        if "Pi-hole API returned a 'forbidden' error" in log_content:
            return JSONResponse(content={"error": "forbidden"})
    return JSONResponse(content={})

@app.get("/stream")
@limiter.limit(get_rate_limit)
async def stream(request: Request):
    def event_stream():
        while True:
            try:
                log_file = Path('/app/logs/sync.log')
                if not log_file.exists():
                    log_file.touch()
                log_content = log_file.read_text()
                yield f"data: {json.dumps({'log': log_content})}\n\n"

                changelog_file = Path('/app/changelog.log')
                if not changelog_file.exists():
                    changelog_file.touch()
                changelog_content = changelog_file.read_text()
                yield f"data: {json.dumps({'changelog': changelog_content})}\n\n"

                mappings = get_mappings_data()
                yield f"data: {json.dumps({'mappings': mappings})}\n\n"
            except Exception as e:
                log.error("Error in event stream", error=e)
                yield f"data: {json.dumps({'error': 'An error occurred in the stream.'})}\n\n"
            finally:
                time.sleep(get_sync_interval())

    return StreamingResponse(event_stream(), media_type='text/event-stream')

@app.get("/mappings")
@limiter.limit(get_rate_limit)
async def get_mappings(request: Request):
    return JSONResponse(content=get_mappings_data())

class UpdateIntervalRequest(BaseModel):
    interval: int

@app.post("/update-interval")
@limiter.limit(get_rate_limit)
async def update_interval(request: Request, data: UpdateIntervalRequest):
    Path("/app/sync_interval.txt").write_text(str(data.interval))
    log.info("Sync interval updated", interval=data.interval)
    return JSONResponse(content={"message": "Sync interval updated."})


class ClearLogRequest(BaseModel):
    log: str


@app.post("/clear-log")
@limiter.limit(get_rate_limit)
async def clear_log(request: Request, data: ClearLogRequest):
    if data.log == 'sync':
        try:
            Path('/app/logs/sync.log').write_text('')
            return JSONResponse(content={"message": "Sync log cleared."})
        except FileNotFoundError:
            return JSONResponse(content={"message": "Log file not found."}, status_code=404)
    return JSONResponse(content={"message": "Invalid log type."}, status_code=400)

@app.get("/docs", response_class=HTMLResponse)
@limiter.limit(get_rate_limit)
async def docs(request: Request):
    content = Path('/app/README.md').read_text()
    return templates.TemplateResponse(request, "docs.html", {"content": markdown.markdown(content)})

@app.get("/health")
@limiter.limit(get_rate_limit)
async def health_check(request: Request):
    return JSONResponse(content={"status": "ok"})

@app.get("/history")
@limiter.limit(get_rate_limit)
async def get_history(request: Request):
    """Returns the history of the number of mapped devices."""
    try:
        with Path("/app/history.log").open() as f:
            history = f.readlines()
        return JSONResponse(content={"history": history})
    except FileNotFoundError:
        return JSONResponse(content={"history": []})

@app.get("/cache")
@limiter.limit(get_rate_limit)
async def get_cache(request: Request):
    """Returns the cached results."""
    try:
        with Path("/app/cache.json").open() as f:
            cache = json.load(f)
        return JSONResponse(content={"cache": cache})
    except FileNotFoundError:
        return JSONResponse(content={"cache": {}})
