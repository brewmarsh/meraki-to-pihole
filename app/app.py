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

@app.route('/logs')
def get_logs():
    try:
        with open('/app/logs/sync.log', 'r') as f:
            sync_log = f.read()
    except FileNotFoundError:
        sync_log = "Log file not found."
    return jsonify({"sync_log": sync_log})

@app.route('/mappings')
def get_mappings():
    # This is a placeholder. A more robust solution would be to
    # have the sync script write the mappings to a file that can be read here.
    return jsonify({})

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
