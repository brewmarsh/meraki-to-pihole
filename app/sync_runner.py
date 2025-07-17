import time
import logging
import os
import sys
from meraki_pihole_sync import main, load_app_config_from_env

def get_sync_interval():
    try:
        with open("/app/sync_interval.txt", "r") as f:
            return int(f.read().strip())
    except (IOError, ValueError):
        return int(os.getenv("SYNC_INTERVAL_SECONDS", 300))

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    # --- Logging Setup ---
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
        stream=sys.stdout,
    )
    # --- End Logging Setup ---
    while True:
        sync_interval = get_sync_interval()
        try:
            logging.info("Starting a new sync process...")
            main()
            logging.info("Sync process completed successfully.")
        except SystemExit as e:
            logging.warning(f"Sync script exited with code {e.code}.")
        except Exception as e:
            logging.critical(f"An unhandled exception occurred during sync: {e}", exc_info=True)

        logging.info(f"Sleeping for {sync_interval} seconds before next sync.")
        time.sleep(sync_interval)

if __name__ == "__main__":
    run_sync()
