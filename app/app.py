from flask import Flask, render_template, jsonify, request, Response
import os
import logging
from meraki_pihole_sync import main as run_sync_main
import threading
import json
import time

app = Flask(__name__)

from sync_runner import get_sync_interval

@app.route('/')
def index():
    return render_template('index.html', sync_interval=get_sync_interval())

@app.route('/force-sync', methods=['POST'])
def force_sync():
    logging.info("Force sync requested via web UI.")
    try:
        # Running the sync in a separate thread to avoid blocking the web server
        sync_thread = threading.Thread(target=run_sync_main)
        sync_thread.start()
        return jsonify({"message": "Sync process started."})
    except Exception as e:
        logging.error(f"Error starting forced sync: {e}")
        return jsonify({"message": f"Sync failed to start: {e}"}), 500

@app.route('/check-pihole-error', methods=['GET'])
def check_pihole_error():
    with open('/app/logs/sync.log', 'r') as f:
        log_content = f.read()
    if "Pi-hole API returned a 'forbidden' error" in log_content:
        return jsonify({"error": "forbidden"})
    return jsonify({})

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            try:
                with open('/app/logs/sync.log', 'r') as f:
                    log_content = f.read()
                yield f"data: {json.dumps({'log': log_content})}\n\n"

                mappings = get_mappings_data()
                yield f"data: {json.dumps({'mappings': mappings})}\n\n"
            except Exception as e:
                logging.error(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': 'An error occurred in the stream.'})}\n\n"
            finally:
                time.sleep(get_sync_interval())

    return Response(event_stream(), mimetype='text/event-stream')

def _get_pihole_data(pihole_url, pihole_api_key):
    from clients.pihole_client import authenticate_to_pihole, get_pihole_custom_dns_records
    sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    if not sid or not csrf_token:
        logging.error("Failed to authenticate to Pi-hole in _get_pihole_data.")
        return None, None

    pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)
    if pihole_records is None:
        logging.error("Failed to get Pi-hole records in _get_pihole_data.")
        return None, None

    return sid, pihole_records

def _get_meraki_data(config):
    import meraki
    from clients.meraki_client import get_all_relevant_meraki_clients
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
    meraki_ips = {client['ip'] for client in meraki_clients}
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
        from meraki_pihole_sync import load_app_config_from_env
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
        logging.error(f"Error in get_mappings_data: {e}")
        return {}

@app.route('/mappings')
def get_mappings():
    return jsonify(get_mappings_data())

@app.route('/update-interval', methods=['POST'])
def update_interval():
    data = request.get_json()
    interval = data.get('interval')
    if interval and interval.isdigit():
        with open("/app/sync_interval.txt", "w") as f:
            f.write(interval)
        logging.info(f"Sync interval updated to {interval} seconds.")
        return jsonify({"message": "Sync interval updated."})
    return jsonify({"message": "Invalid interval."}), 400

@app.route('/clear-log', methods=['POST'])
def clear_log():
    data = request.get_json()
    log_type = data.get('log')
    if log_type == 'sync':
        try:
            with open('/app/logs/sync.log', 'w') as f:
                f.write('')
            return jsonify({"message": "Sync log cleared."})
        except FileNotFoundError:
            return jsonify({"message": "Log file not found."}), 404
    return jsonify({"message": "Invalid log type."}), 400

import markdown

@app.route('/docs')
def docs():
    with open('/app/README.md', 'r') as f:
        content = f.read()
    return render_template('docs.html', content=markdown.markdown(content))

@app.route('/health')
def health_check():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # When running locally, start the sync runner in a background thread
    if not os.environ.get("gunicorn"):
        from sync_runner import run_sync
        sync_thread = threading.Thread(target=run_sync)
        sync_thread.daemon = True
        sync_thread.start()
    app.run(host='0.0.0.0', port=os.environ.get('FLASK_PORT', 24653))
