import time
import structlog
from .sync_logic import sync_pihole_dns, get_sync_interval

log = structlog.get_logger()

def run_sync():
    """
    Runs the main sync script in a loop with a configurable sleep interval.
    """
    while True:
        try:
            log.info("Starting a new sync process...")
            sync_pihole_dns()
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
