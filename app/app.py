import json
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

import markdown
import meraki
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .clients.meraki_client import get_all_relevant_meraki_clients
from .clients.pihole_client import authenticate_to_pihole, get_pihole_custom_dns_records
from .meraki_pihole_sync import load_app_config_from_env
from .meraki_pihole_sync import main as run_sync_main
from .sync_runner import get_sync_interval

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start the sync thread on application startup
    sync_thread = threading.Thread(target=run_sync_main, daemon=True)
    sync_thread.start()
    yield
    # No cleanup needed on shutdown

app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request, "sync_interval": get_sync_interval()})


@app.post("/update-meraki")
async def update_meraki():
    """Triggers a Meraki data fetch and sync."""
    log.info("Meraki update requested via web UI.")
    try:
        # Running the sync in a separate thread to avoid blocking the web server
        sync_thread = threading.Thread(target=run_sync_main, args=("meraki",))
        sync_thread.start()
        return JSONResponse(content={"message": "Meraki update process started."})
    except Exception as e:
        log.error("Error starting Meraki update", error=e)
        return JSONResponse(content={"message": f"Meraki update failed to start: {e}"}, status_code=500)

@app.post("/update-pihole")
async def update_pihole():
    log.info("Pi-hole update requested via web UI.")
    try:
        # Running the sync in a separate thread to avoid blocking the web server
        sync_thread = threading.Thread(target=run_sync_main, args=("pihole",))
        sync_thread.start()
        return JSONResponse(content={"message": "Pi-hole update process started."})
    except Exception as e:
        log.error("Error starting Pi-hole update", error=e)
        return JSONResponse(content={"message": f"Pi-hole update failed to start: {e}"}, status_code=500)

@app.get("/check-pihole-error")
async def check_pihole_error():
    log_file = Path('/app/logs/sync.log')
    if log_file.exists():
        log_content = log_file.read_text()
        if "Pi-hole API returned a 'forbidden' error" in log_content:
            return JSONResponse(content={"error": "forbidden"})
    return JSONResponse(content={})

@app.get("/stream")
async def stream():
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

def _get_pihole_data(pihole_url, pihole_api_key):
    sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    if not sid or not csrf_token:
        log.error("Failed to authenticate to Pi-hole in _get_pihole_data.")
        return None, None

    pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)
    if pihole_records is None:
        log.error("Failed to get Pi-hole records in _get_pihole_data.")
        return None, None

    return sid, pihole_records

def _get_meraki_data(config):
    dashboard = meraki.DashboardAPI(
        api_key=config["meraki_api_key"],
        output_log=False,
        print_console=False,
        suppress_logging=True,
    )
    return get_all_relevant_meraki_clients(dashboard, config)

def _map_devices(meraki_clients, pihole_records):
    mapped_devices = []
    unmapped_meraki_devices = []
    pihole_ips = set(pihole_records.values())

    for client in meraki_clients:
        if client['ip'] in pihole_ips:
            for domain, ip in pihole_records.items():
                if client['ip'] == ip:
                    mapped_devices.append({
                        "meraki_name": client['name'],
                        "pihole_domain": domain,
                        "ip": ip
                    })
        else:
            unmapped_meraki_devices.append(client)

    return mapped_devices, unmapped_meraki_devices

def get_mappings_data():
    try:
        config = load_app_config_from_env()
        pihole_url = os.getenv("PIHOLE_API_URL")
        pihole_api_key = os.getenv("PIHOLE_API_KEY")

        sid, pihole_records = _get_pihole_data(pihole_url, pihole_api_key)
        if not sid:
            return {}

        meraki_clients = _get_meraki_data(config)
        mapped_devices, unmapped_meraki_devices = _map_devices(meraki_clients, pihole_records)

        return {"pihole": pihole_records, "meraki": meraki_clients, "mapped": mapped_devices, "unmapped_meraki": unmapped_meraki_devices}
    except Exception as e:
        log.error("Error in get_mappings_data", error=e)
        return {}

@app.get("/mappings")
async def get_mappings():
    return JSONResponse(content=get_mappings_data())

@app.post("/update-interval")
async def update_interval(request: Request):
    data = await request.json()
    interval = data.get("interval")
    if interval and interval.isdigit():
        Path("/app/sync_interval.txt").write_text(interval)
        log.info("Sync interval updated", interval=interval)
        return JSONResponse(content={"message": "Sync interval updated."})
    return JSONResponse(content={"message": "Invalid interval."}, status_code=400)

@app.post("/clear-log")
async def clear_log(request: Request):
    data = await request.json()
    log_type = data.get("log")
    if log_type == 'sync':
        try:
            Path('/app/logs/sync.log').write_text('')
            return JSONResponse(content={"message": "Sync log cleared."})
        except FileNotFoundError:
            return JSONResponse(content={"message": "Log file not found."}, status_code=404)
    return JSONResponse(content={"message": "Invalid log type."}, status_code=400)

@app.get("/docs", response_class=HTMLResponse)
async def docs(request: Request):
    content = Path('/app/README.md').read_text()
    return templates.TemplateResponse("docs.html", {"request": request, "content": markdown.markdown(content)})

@app.get("/health")
async def health_check():
    return JSONResponse(content={"status": "ok"})
