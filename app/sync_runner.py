import os
import time
from pathlib import Path

import structlog

from .meraki_pihole_sync import main

log = structlog.get_logger()


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
        interval_file = Path("/app/sync_interval.txt")
        if interval_file.exists():
            interval = int(interval_file.read_text().strip())
            log.debug("Using sync interval from file", interval=interval)
            return interval
    except (OSError, ValueError):
        # File not found or contains invalid data, proceed to the next source
        pass

    # Check for the environment variable next
    try:
        interval = int(os.getenv("SYNC_INTERVAL_SECONDS"))
        log.debug("Using sync interval from environment variable", interval=interval)
        return interval
    except (TypeError, ValueError):
        # Env var is not set or is not a valid integer, proceed to default
        pass

    # Use the default value as a final fallback
    default_interval = 300  # 5 minutes
    log.debug("Using default sync interval", interval=default_interval)
    return default_interval

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    while True:
        try:
            log.info("Starting a new sync process...")
            main()
            log.info("Sync process completed successfully.")
        except SystemExit as e:
            log.warning("Sync script exited", exit_code=e.code)
        except Exception:
            log.critical("An unhandled exception occurred during sync", exc_info=True)

        sync_interval = get_sync_interval()
        log.info("Sleeping before next sync", sleep_interval=sync_interval)
        time.sleep(sync_interval)

if __name__ == "__main__":
    run_sync()
