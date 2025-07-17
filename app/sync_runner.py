import time
import logging
import os
import sys
from meraki_pihole_sync import main, load_app_config_from_env

def get_sync_interval():
    """
    Determines the sync interval in seconds, checking three sources in order:
    1. A temporary file (`/app/sync_interval.txt`) which can be created by the web UI.
    2. The `SYNC_INTERVAL_SECONDS` environment variable.
    3. A hardcoded default value (300 seconds).

    Returns:
        int: The sync interval in seconds.
    """
    # Check for the UI-generated file first
    try:
        with open("/app/sync_interval.txt", "r") as f:
            interval = int(f.read().strip())
            logging.debug(f"Using sync interval from file: {interval} seconds.")
            return interval
    except (IOError, ValueError):
        # File not found or contains invalid data, proceed to the next source
        pass

    # Check for the environment variable next
    try:
        interval = int(os.getenv("SYNC_INTERVAL_SECONDS"))
        logging.debug(f"Using sync interval from environment variable: {interval} seconds.")
        return interval
    except (TypeError, ValueError):
        # Env var is not set or is not a valid integer, proceed to default
        pass

    # Use the default value as a final fallback
    default_interval = 300  # 5 minutes
    logging.debug(f"Using default sync interval: {default_interval} seconds.")
    return default_interval

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
