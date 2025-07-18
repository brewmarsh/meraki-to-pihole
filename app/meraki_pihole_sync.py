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
from datetime import datetime

import meraki
from clients.meraki_client import get_all_relevant_meraki_clients
from clients.pihole_client import (
    add_or_update_dns_record_in_pihole,
    authenticate_to_pihole,
    get_pihole_custom_dns_records,
)

# --- Logging Setup ---
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    stream=sys.stdout,
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
        config["meraki_client_timespan_seconds"] = int(os.getenv(ENV_CLIENT_TIMESPAN, default_timespan))
    except ValueError:
        logging.warning(
            f"Invalid value for {ENV_CLIENT_TIMESPAN}: '{os.getenv(ENV_CLIENT_TIMESPAN)}'. Using default {default_timespan} seconds (24 hours)."
        )
        config["meraki_client_timespan_seconds"] = int(default_timespan)

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


def update_meraki_data():
    """
    Fetches and returns relevant Meraki clients.
    """
    config = load_app_config_from_env()
    meraki_api_key = config["meraki_api_key"]
    dashboard = meraki.DashboardAPI(
        api_key=meraki_api_key,
        output_log=False,
        print_console=False,
        suppress_logging=True,
    )
    return get_all_relevant_meraki_clients(dashboard, config)

def update_pihole_data(meraki_clients):
    """
    Updates Pi-hole with the given Meraki clients.
    """
    config = load_app_config_from_env()
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config["pihole_api_key"]
    hostname_suffix = config["hostname_suffix"]

    sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    if not sid or not csrf_token:
        logging.error("Could not authenticate to Pi-hole. Halting sync.")
        return

    existing_pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)
    if existing_pihole_records is None:
        logging.error("Could not fetch Pi-hole DNS records. Halting to prevent errors.")
        return

    successful_syncs = 0
    failed_syncs = 0
    with open("app/changelog.log", "a+") as f:
        f.seek(0)
        previous_mappings = f.readlines()
        f.seek(0)
        f.truncate()
        for client in meraki_clients:
            if not client.get("name"):
                logging.warning(f"Skipping client with no name and IP {client.get('ip')}")
                continue
            client_name_sanitized = client["name"].replace(" ", "-").lower()
            domain_to_sync = f"{client_name_sanitized}{hostname_suffix}"
            ip_to_sync = client["ip"]

            if add_or_update_dns_record_in_pihole(
                pihole_url,
                sid,
                csrf_token,
                domain_to_sync,
                ip_to_sync,
                existing_pihole_records,
            ):
                timestamp = datetime.now()
                mapping_line = f"{timestamp}: Mapped {domain_to_sync} to {ip_to_sync}\n"
                if mapping_line not in previous_mappings:
                    f.write(mapping_line)
                successful_syncs += 1
            else:
                failed_syncs += 1
                logging.warning(
                    f"Failed to sync client '{client['name']}' (DNS: {domain_to_sync} -> {ip_to_sync}) to Pi-hole."
                )

    logging.info("--- Meraki to Pi-hole Sync Summary ---")
    logging.info(f"Successfully synced/verified {successful_syncs} client(s).")
    if failed_syncs > 0:
        logging.warning(f"Failed to sync {failed_syncs} client(s). Check logs for details.")
    logging.info(f"Total Meraki clients processed: {len(meraki_clients)}")
    logging.info("--- Sync process complete ---")

def main(update_type=None):
    """
    Main function to run the Meraki to Pi-hole sync process.
    Loads configuration, fetches Meraki clients, gets Pi-hole records,
    and syncs them.
    """
    app_version = os.getenv("APP_VERSION", "Not Set")
    commit_sha = os.getenv("COMMIT_SHA", "Not Set")
    logging.info(f"--- Starting Meraki Pi-hole Sync Script --- Version: {app_version}, Commit: {commit_sha}")

    meraki_clients = update_meraki_data()
    if update_type is None or update_type == "pihole":
        if meraki_clients:
            update_pihole_data(meraki_clients)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in main: {e}", exc_info=True)
        sys.exit(1)
