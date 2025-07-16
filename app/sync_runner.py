import os
import time
import logging
from meraki_pihole_sync import main, load_app_config_from_env

def get_sync_interval():
    """
    Gets the sync interval from the sync_interval.txt file, or from the environment.
    """
    try:
        with open("sync_interval.txt", "r") as f:
            return int(f.read())
    except (IOError, ValueError):
        config = load_app_config_from_env()
        return config.get("sync_interval", 300)

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    while True:
        try:
            logging.info("Starting a new sync process...")
            main()
            logging.info("Sync process completed successfully.")
        except SystemExit as e:
            logging.warning(f"Sync script exited with code {e.code}.")
        except Exception as e:
            logging.critical(f"An unhandled exception occurred during sync: {e}", exc_info=True)

        sync_interval = get_sync_interval()
        logging.info(f"Sleeping for {sync_interval} seconds before next sync.")
        time.sleep(sync_interval)

if __name__ == "__main__":
    run_sync()
