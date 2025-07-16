#!/usr/local/bin/python3
# Python script to sync Meraki client IPs to Pi-hole
"""
Meraki Pi-hole DNS Sync

This script synchronizes client information from the Meraki API to a Pi-hole instance.
It identifies Meraki clients with Fixed IP Assignments (DHCP Reservations) and
creates corresponding custom DNS records in Pi-hole. This ensures reliable local
DNS resolution for these statically assigned devices.

The script fetches clients from specified Meraki networks (or all networks in an
organization if none are specified). It then compares these clients against existing
custom DNS records in Pi-hole and makes necessary additions or updates.

Configuration is managed entirely through environment variables.
"""

import logging
import os
import sys

import meraki
from clients.meraki_client import get_all_relevant_meraki_clients
from clients.pihole_client import (
    add_or_update_dns_record_in_pihole,
    authenticate_to_pihole,
    get_pihole_custom_dns_records,
)

# --- Logging Setup ---
LOG_DIR = "/app/logs"
# Ensure the directory exists. This should ideally be done in the Dockerfile,
# but this provides a fallback if running outside Docker or if permissions are tricky.
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)  # exist_ok=True handles race conditions
    except OSError as e:
        # Fallback to printing to stderr if log directory creation fails
        print(f"CRITICAL: Could not create log directory {LOG_DIR}. Error: {e}", file=sys.stderr)
        # Attempt to continue by logging to stdout only, though file logging will fail.
        # This is better than crashing if the script is critical.
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)],
        )
        logging.error(f"Log directory {LOG_DIR} could not be created. Logging to stdout only.")

LOG_FILE_PATH = os.path.join(LOG_DIR, "sync.log")

# Configure root logger
# Clear any existing handlers to prevent duplicate logs if this script/module is reloaded
logger = logging.getLogger()
if logger.hasHandlers():
    logger.handlers.clear()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode="a"),  # Append mode
        logging.StreamHandler(sys.stdout),  # For `docker logs`
    ],
)
# --- End Logging Setup ---

# --- Constants ---
# MERAKI_API_BASE_URL will be handled by the SDK

# Environment Variable Names (used for consistency)
ENV_APP_VERSION = "APP_VERSION"
ENV_COMMIT_SHA = "COMMIT_SHA"
ENV_MERAKI_API_KEY = "MERAKI_API_KEY"
ENV_MERAKI_ORG_ID = "MERAKI_ORG_ID"
ENV_MERAKI_NETWORK_IDS = "MERAKI_NETWORK_IDS"
ENV_PIHOLE_API_URL = "PIHOLE_API_URL"
ENV_PIHOLE_API_KEY = "PIHOLE_API_KEY"
ENV_HOSTNAME_SUFFIX = "HOSTNAME_SUFFIX"
ENV_CLIENT_TIMESPAN = "MERAKI_CLIENT_TIMESPAN_SECONDS"
# --- End Constants ---


def load_app_config_from_env():
    """
    Loads all application configuration from environment variables.

    Returns:
        dict: A dictionary containing the configuration parameters.
              Exits the script if mandatory variables are missing or if placeholder
              values are detected for critical settings.
    """
    config = {}
    mandatory_vars = {
        ENV_MERAKI_API_KEY: "Meraki API Key",
        ENV_MERAKI_ORG_ID: "Meraki Organization ID",
        ENV_PIHOLE_API_URL: "Pi-hole API URL",
        ENV_PIHOLE_API_KEY: "Pi-hole API Key",
        ENV_HOSTNAME_SUFFIX: "Hostname Suffix",
    }
    missing_vars_messages = []

    for var_name, desc in mandatory_vars.items():
        value = os.getenv(var_name)
        if not value:
            missing_vars_messages.append(f"{desc} ({var_name})")
        config[var_name.lower()] = value  # Store keys in lowercase for consistent access

    if missing_vars_messages:
        logging.error(
            f"Missing mandatory environment variables: {', '.join(missing_vars_messages)}. Please set them and try again."
        )
        sys.exit(1)

    # Optional environment variables
    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY)
    logging.debug(f"Pi-hole API Key loaded from environment: {config['pihole_api_key']}")

    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, "")  # Default to empty string
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(",") if nid.strip()]

    try:
        default_timespan = "86400"  # 24 hours in seconds
        config["meraki_client_timespan"] = int(os.getenv(ENV_CLIENT_TIMESPAN, default_timespan))
    except ValueError:
        logging.warning(
            f"Invalid value for {ENV_CLIENT_TIMESPAN}: '{os.getenv(ENV_CLIENT_TIMESPAN)}'. Using default {default_timespan} seconds (24 hours)."
        )
        config["meraki_client_timespan"] = int(default_timespan)

    # Sanity checks for placeholder values
    if config["meraki_org_id"].upper() == "YOUR_MERAKI_ORGANIZATION_ID":
        logging.error(f"Placeholder value detected for {ENV_MERAKI_ORG_ID}. Please set a valid Organization ID.")
        sys.exit(1)
    if (
        config["pihole_api_url"].upper() == "YOUR_PIHOLE_API_URL"
        or "YOUR_PIHOLE_IP_OR_HOSTNAME" in config["pihole_api_url"].upper()
    ):
        logging.error(f"Placeholder value detected for {ENV_PIHOLE_API_URL}. Please set a valid Pi-hole API URL.")
        sys.exit(1)
    # Check for common example/placeholder suffixes to warn the user
    example_suffixes = [".LOCAL", ".YOURDOMAIN.LOCAL", ".YOURCUSTOMDOMAIN.LOCAL", "YOUR_HOSTNAME_SUFFIX"]
    if config["hostname_suffix"].upper() in example_suffixes:
        logging.warning(
            f"Possible example/placeholder value detected for {ENV_HOSTNAME_SUFFIX} ('{config['hostname_suffix']}'). Ensure this is your intended suffix."
        )

    logging.info("Successfully loaded configuration from environment variables.")
    return config


def main():
    """
    Main function to run the Meraki to Pi-hole sync process.
    Loads configuration, fetches Meraki clients, gets Pi-hole records,
    and syncs them.
    """
    # Log application version and commit SHA if available
    app_version = os.getenv("APP_VERSION", "Not Set")
    commit_sha = os.getenv("COMMIT_SHA", "Not Set")
    logging.info(f"--- Starting Meraki Pi-hole Sync Script --- Version: {app_version}, Commit: {commit_sha}")

    config = load_app_config_from_env()
    meraki_api_key = config["meraki_api_key"]  # Renamed for clarity with SDK
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config["pihole_api_key"]
    hostname_suffix = config["hostname_suffix"]

    # Initialize Meraki Dashboard API client
    # SDK handles API key, retries, logging (can be configured), etc.
    # `suppress_logging=True` for SDK's internal logger if we want to rely solely on our script's logger for Meraki calls.
    # Or, let SDK log at its default level (INFO) or configure it via `log_level`.
    # For now, let's allow SDK's default logging and see.
    # `output_log=False` might also be relevant if we don't want SDK to print to console by default.
    # Let's start simple and adjust if SDK logging is too verbose or conflicts.
    # The SDK will use the MERAKI_PYTHON_SDK_LOG_FILE and MERAKI_PYTHON_SDK_LOG_LEVEL env vars if set.
    # We can also pass `logger` instance to it.
    # For now, let's use `print_console=False` to avoid duplicate console output if SDK also logs to console.
    # The SDK's logger can be noisy with DEBUG level; our script's DEBUG is more targeted.
    dashboard = meraki.DashboardAPI(
        api_key=meraki_api_key,
        output_log=False,  # We handle our own logging to console/file via script's logger
        print_console=False,  # Explicitly false
        suppress_logging=True,  # Suppress SDK's own logger; we will log API calls if needed at debug level
    )

    # Fetch relevant Meraki clients with fixed IP assignments using the SDK
    meraki_clients = get_all_relevant_meraki_clients(dashboard, config)

    if not meraki_clients:
        # This means no clients with fixed IPs (matching current IP) were found across ALL processed networks.
        # Or, network fetching itself failed. get_all_relevant_meraki_clients would have logged details.
        logging.info(
            "No relevant Meraki clients (with fixed IP assignments) were found after checking all configured/discovered networks, or network/client fetching failed."
        )

        # Check current log level. logging.getLogger().getEffectiveLevel() gives the numeric level.
        # logging.DEBUG is 10, logging.INFO is 20.
        if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
            logging.info(
                "Consider setting LOG_LEVEL=DEBUG in your .env file and restarting to get detailed client processing information if you expected clients to be found."
            )

        logging.info("No new DNS entries will be synced to Pi-hole.")
        # Potentially, one might want to proceed to cleanup old entries from Pi-hole even if no new Meraki clients are found.
        # For now, the script exits, matching previous behavior. If cleanup is desired, this logic would change.
        # For this iteration, keeping it simple: no new clients = no changes to Pi-hole based on Meraki data.
        logging.info("--- Sync process complete (no Meraki clients to sync to Pi-hole) ---")
        return

    logging.info(f"Found {len(meraki_clients)} Meraki client(s) with fixed IP assignments to process for Pi-hole sync.")

    # Authenticate to Pi-hole to get session details
    sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    if not sid or not csrf_token:
        logging.error("Could not authenticate to Pi-hole. Halting sync.")
        logging.info("--- Sync process failed (Pi-hole authentication error) ---")
        return

    # Fetch existing Pi-hole DNS records to compare against
    # This is now a cache that add_or_update_dns_record_in_pihole will modify.
    existing_pihole_records_cache = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)
    if existing_pihole_records_cache is None:  # This means API call failed critically
        logging.error("Could not fetch existing Pi-hole DNS records. Halting sync to prevent erroneous changes.")
        logging.info("--- Sync process failed (Pi-hole record fetch error) ---")
        return

    successful_syncs = 0
    failed_syncs = 0
    # Sync each relevant Meraki client to Pi-hole
    for client in meraki_clients:
        # Ensure client name is sanitized for use in a hostname.
        # Replace spaces with hyphens, convert to lowercase. Other characters might need handling.
        client_name_sanitized = client["name"].replace(" ", "-").lower()
        # Further sanitization could be added here if client names contain problematic characters for hostnames.

        domain_to_sync = f"{client_name_sanitized}{hostname_suffix}"
        ip_to_sync = client["ip"]

        logging.info(
            f"Processing Meraki client: Name='{client['name']}', IP='{ip_to_sync}', Target DNS: {domain_to_sync} -> {ip_to_sync}"
        )

        if add_or_update_dns_record_in_pihole(
            pihole_url,
            sid,
            csrf_token,
            domain_to_sync,
            ip_to_sync,
            existing_pihole_records_cache,
        ):
            successful_syncs += 1
        else:
            failed_syncs += 1
            logging.warning(
                f"Failed to sync client '{client['name']}' (DNS: {domain_to_sync} -> {ip_to_sync}) to Pi-hole."
            )

    # TODO (Future Enhancement): Implement cleanup of stale DNS records in Pi-hole.
    # This would involve:
    # 1. Identifying all DNS records in `existing_pihole_records_cache` that match `hostname_suffix`.
    # 2. Comparing them against the list of `meraki_clients` just processed.
    # 3. If a record from Pi-hole (matching the suffix) is NOT in the `meraki_clients` list (i.e., no longer a fixed IP client),
    #    then delete it from Pi-hole.
    # This was mentioned in the README but not implemented in the original script.

    logging.info("--- Meraki to Pi-hole Sync Summary ---")
    logging.info(f"Successfully synced/verified {successful_syncs} client(s).")
    if failed_syncs > 0:
        logging.warning(f"Failed to sync {failed_syncs} client(s). Check logs above for details.")
    logging.info(f"Total Meraki clients processed: {len(meraki_clients)}")
    logging.info("--- Sync process complete ---")


if __name__ == "__main__":
    # This is the main entry point of the script
    try:
        main()
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in main: {e}", exc_info=True)
        sys.exit(1)

main()
