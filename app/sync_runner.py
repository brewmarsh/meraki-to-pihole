import os
import time
import logging
from meraki_pihole_sync import main, load_app_config_from_env
import requests
from clients.pihole_client import authenticate_to_pihole

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    config = load_app_config_from_env()
    sync_interval = config.get("sync_interval", 300)
    pihole_url = config.get("pihole_api_url")
    pihole_api_key = config.get("pihole_api_key")

    sid = None
    csrf_token = None

    while True:
        if not sid or not csrf_token:
            try:
                sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429:
                    logging.warning(f"Pi-hole auth API returned HTTP 429 (Too Many Requests). Waiting for {sync_interval} seconds.")
                    time.sleep(sync_interval)
                    continue
                else:
                    logging.error(f"Authentication to Pi-hole failed: {e}")
                    time.sleep(sync_interval)
                    continue

        try:
            logging.info("Starting a new sync process...")
            main(sid, csrf_token)
            logging.info("Sync process completed successfully.")
        except SystemExit as e:
            logging.warning(f"Sync script exited with code {e.code}.")
        except Exception as e:
            logging.critical(f"An unhandled exception occurred during sync: {e}", exc_info=True)
            sid, csrf_token = None, None # Invalidate session on error

        logging.info(f"Sleeping for {sync_interval} seconds before next sync.")
        time.sleep(sync_interval)

if __name__ == "__main__":
    run_sync()
