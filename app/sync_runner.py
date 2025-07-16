import os
import time
import logging
from meraki_pihole_sync import main, load_app_config_from_env

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    config = load_app_config_from_env()
    sync_interval = config.get("sync_interval", 300)

    while True:
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
