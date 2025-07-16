from flask import Flask, render_template, jsonify, request
import os
import logging
from meraki_pihole_sync import main as run_sync_main
import threading

app = Flask(__name__)

@app.route('/')
def index():
    sync_interval = os.getenv("SYNC_INTERVAL_SECONDS", 300)
    return render_template('index.html', sync_interval=sync_interval)

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

@app.route('/stream')
def stream():
    def event_stream():
        while True:
            time.sleep(5)
            # Send log updates
            with open('/app/logs/sync.log', 'r') as f:
                log_content = f.read()
            yield f"data: {json.dumps({'log': log_content})}\n\n"

            # Send mapping updates
            mappings = get_mappings_data()
            yield f"data: {json.dumps({'mappings': mappings})}\n\n"

    return Response(event_stream(), mimetype='text/event-stream')

def get_mappings_data():
    pihole_url = os.getenv("PIHOLE_API_URL")
    pihole_api_key = os.getenv("PIHOLE_API_KEY")

    from clients.pihole_client import authenticate_to_pihole, get_pihole_custom_dns_records
    import meraki
    from meraki_pihole_sync import load_app_config_from_env
    from clients.meraki_client import get_all_relevant_meraki_clients

    try:
        sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    except Exception:
        return {}

    if not sid or not csrf_token:
        return {}

    pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)

    config = load_app_config_from_env()
    dashboard = meraki.DashboardAPI(
        api_key=config["meraki_api_key"],
        output_log=False,
        print_console=False,
        suppress_logging=True,
    )
    meraki_clients = get_all_relevant_meraki_clients(dashboard, config)

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

    return {"pihole": pihole_records, "meraki": meraki_clients, "mapped": mapped_devices, "unmapped_meraki": unmapped_meraki_devices}

@app.route('/mappings')
def get_mappings():
    pihole_url = os.getenv("PIHOLE_API_URL")
    pihole_api_key = os.getenv("PIHOLE_API_KEY")

    # Import here to avoid circular dependency
    from clients.pihole_client import authenticate_to_pihole, get_pihole_custom_dns_records
    import meraki
    from meraki_pihole_sync import load_app_config_from_env
    from clients.meraki_client import get_all_relevant_meraki_clients

    try:
        sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    except Exception as e:
        logging.error(f"Error authenticating to Pi-hole: {e}")
        return jsonify({"error": "Failed to authenticate to Pi-hole."}), 500

    if not sid or not csrf_token:
        return jsonify({"error": "Failed to authenticate to Pi-hole."}), 500

    pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)

    config = load_app_config_from_env()
    dashboard = meraki.DashboardAPI(
        api_key=config["meraki_api_key"],
        output_log=False,
        print_console=False,
        suppress_logging=True,
    )
    meraki_clients = get_all_relevant_meraki_clients(dashboard, config)

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

    return jsonify({"pihole": pihole_records, "meraki": meraki_clients, "mapped": mapped_devices, "unmapped_meraki": unmapped_meraki_devices})

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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('FLASK_PORT', 24653))
