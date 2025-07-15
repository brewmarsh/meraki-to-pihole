from flask import Flask, render_template, jsonify, request
import subprocess
import os
from clients.pihole_client import get_pihole_custom_dns_records
from meraki_pihole_sync import main as run_sync

app = Flask(__name__)

LOG_DIR = "/app/logs"
SYNC_LOG = os.path.join(LOG_DIR, "sync.log")
CRON_LOG = os.path.join(LOG_DIR, "cron_output.log")

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/logs")
def logs():
    with open(SYNC_LOG, "r") as f:
        sync_log = f.read()
    with open(CRON_LOG, "r") as f:
        cron_log = f.read()
    return jsonify({"sync_log": sync_log, "cron_log": cron_log})

@app.route("/force-refresh", methods=["POST"])
def force_refresh():
    try:
        run_sync()
        return jsonify({"status": "success", "message": "Sync process triggered."})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/mappings")
def mappings():
    pihole_url = os.getenv("PIHOLE_API_URL")
    pihole_api_key = os.getenv("PIHOLE_API_KEY")
    records = get_pihole_custom_dns_records(pihole_url, pihole_api_key)
    return jsonify(records)

@app.route("/clear-log", methods=["POST"])
def clear_log():
    log_type = request.json.get("log")
    if log_type == "sync":
        log_file = SYNC_LOG
    elif log_type == "cron":
        log_file = CRON_LOG
    else:
        return jsonify({"status": "error", "message": "Invalid log type"})

    with open(log_file, "w") as f:
        f.write("")

    return jsonify({"status": "success", "message": f"{log_type} log cleared."})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=24653)
