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
from pathlib import Path

import meraki

# --- Logging Setup ---
import structlog

from .clients.meraki_client import get_all_relevant_meraki_clients
from .clients.pihole_client import (
    add_or_update_dns_record_in_pihole,
    authenticate_to_pihole,
    get_pihole_custom_dns_records,
)

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(message)s",
    stream=sys.stdout,
)

structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

log = structlog.get_logger()
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
        log.error(
            "Missing mandatory environment variables", missing_vars=missing_vars_messages
        )
        sys.exit(1)

    # Optional environment variables
    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY)
    log.debug(f"Pi-hole API Key loaded from environment: {config['pihole_api_key']}")

    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, "")  # Default to empty string
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(",") if nid.strip()]

    try:
        default_timespan = "86400"  # 24 hours in seconds
        config["meraki_client_timespan_seconds"] = int(os.getenv(ENV_CLIENT_TIMESPAN, default_timespan))
    except ValueError:
        log.warning(
            "Invalid value for MERAKI_CLIENT_TIMESPAN_SECONDS, using default",
            invalid_value=os.getenv(ENV_CLIENT_TIMESPAN),
            default_value=default_timespan,
        )
        config["meraki_client_timespan_seconds"] = int(default_timespan)

    # Sanity checks for placeholder values
    if config["meraki_org_id"].upper() == "YOUR_MERAKI_ORGANIZATION_ID":
        log.error("Placeholder value detected for MERAKI_ORG_ID")
        sys.exit(1)
    if (
        config["pihole_api_url"].upper() == "YOUR_PIHOLE_API_URL"
        or "YOUR_PIHOLE_IP_OR_HOSTNAME" in config["pihole_api_url"].upper()
    ):
        log.error("Placeholder value detected for PIHOLE_API_URL")
        sys.exit(1)
    # Check for common example/placeholder suffixes to warn the user
    example_suffixes = [".LOCAL", ".YOURDOMAIN.LOCAL", ".YOURCUSTOMDOMAIN.LOCAL", "YOUR_HOSTNAME_SUFFIX"]
    if config["hostname_suffix"].upper() in example_suffixes:
        log.warning(
            "Possible example/placeholder value detected for HOSTNAME_SUFFIX",
            hostname_suffix=config["hostname_suffix"],
        )

    log.info("Successfully loaded configuration from environment variables.")
    return config


def update_meraki_data():
    """
    Initializes the Meraki dashboard API and fetches all relevant clients.

    This function loads the application configuration, sets up the Meraki
    dashboard API client, and then calls the client function to retrieve
    all devices with fixed IP assignments.

    Returns:
        list: A list of client dictionaries from Meraki, or an empty list
              if no relevant clients are found or an error occurs.
    """
    config = load_app_config_from_env()
    meraki_api_key = config["meraki_api_key"]
    dashboard = meraki.DashboardAPI(
        api_key=meraki_api_key,
        output_log=False,  # Suppress SDK's own logging to stdout
        print_console=False,
        suppress_logging=True,  # Suppress SDK's handler setup
    )
    return get_all_relevant_meraki_clients(dashboard, config)


def update_pihole_data(meraki_clients):
    """
    Synchronizes Meraki client data to Pi-hole's custom DNS records.

    This function orchestrates the entire Pi-hole update process:
    1. Loads configuration.
    2. Authenticates to Pi-hole to get a session.
    3. Fetches the current custom DNS records from Pi-hole.
    4. Iterates through the provided Meraki clients.
    5. For each client, it adds or updates the corresponding DNS record in Pi-hole.
    6. Logs the outcome of the sync process.

    Args:
        meraki_clients (list): A list of client dictionaries fetched from Meraki.
    """
    config = load_app_config_from_env()
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config["pihole_api_key"]
    hostname_suffix = config["hostname_suffix"]

    sid, csrf_token = authenticate_to_pihole(pihole_url, pihole_api_key)
    if not sid or not csrf_token:
        log.error("Could not authenticate to Pi-hole. Halting sync.")
        return

    existing_pihole_records = get_pihole_custom_dns_records(pihole_url, sid, csrf_token)
    if existing_pihole_records is None:
        log.error("Could not fetch Pi-hole DNS records. Halting to prevent errors.")
        return

    successful_syncs = 0
    failed_syncs = 0
    meraki_clients_by_ip = {client['ip']: client for client in meraki_clients}
    meraki_clients_by_name = {client['name'].replace(" ", "-").lower(): client for client in meraki_clients if client.get('name')}

    changelog_path = Path(__file__).parent / 'changelog.log'
    if not changelog_path.exists():
        changelog_path.touch()

    with changelog_path.open("a+") as f:
        f.seek(0)
        previous_mappings = f.readlines()
        f.seek(0)
        f.truncate()

        # Process updates and additions from Meraki
        for client in meraki_clients:
            if not client.get("name"):
                log.warning("Skipping client with no name", client_ip=client.get("ip"))
                continue

            # Basic validation for hostname compatibility
            client_name = client["name"]
            if ":" in client_name:
                log.warning("Skipping client with invalid characters in name", client_name=client_name)
                continue

            client_name_sanitized = client_name.replace(" ", "-").lower()
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
                log.warning(
                    "Failed to sync client to Pi-hole",
                    client_name=client["name"],
                    domain=domain_to_sync,
                    ip=ip_to_sync,
                )

        # Process deletions
        for domain, ip in existing_pihole_records.items():
            pihole_hostname = domain.replace(hostname_suffix, "")
            if ip not in meraki_clients_by_ip and pihole_hostname not in meraki_clients_by_name:
                from .clients.pihole_client import remove_dns_record_from_pihole
                if remove_dns_record_from_pihole(pihole_url, sid, csrf_token, domain, ip):
                    timestamp = datetime.now()
                    f.write(f"{timestamp}: Removed {domain} -> {ip}\n")
                else:
                    log.warning("Failed to remove stale DNS record", domain=domain, ip=ip)

    log.info(
        "Meraki to Pi-hole Sync Summary",
        successful_syncs=successful_syncs,
        failed_syncs=failed_syncs,
        total_clients=len(meraki_clients),
    )

import time

def main(update_type=None):
    """
    Main function to run the Meraki to Pi-hole sync process.
    Loads configuration, fetches Meraki clients, gets Pi-hole records,
    and syncs them.
    """
    app_version = os.getenv("APP_VERSION", "Not Set")
    commit_sha = os.getenv("COMMIT_SHA", "Not Set")
    log.info("Starting Meraki Pi-hole Sync Script", version=app_version, commit=commit_sha)

    meraki_clients = update_meraki_data()
    if (update_type is None or update_type == "pihole") and meraki_clients:
        update_pihole_data(meraki_clients)

        config = load_app_config_from_env()
        sid, csrf_token = authenticate_to_pihole(config["pihole_api_url"], config["pihole_api_key"])
        if sid and csrf_token:
            existing_pihole_records = get_pihole_custom_dns_records(config["pihole_api_url"], sid, csrf_token)
            if existing_pihole_records is not None:
                mapped_devices = 0
                for client in meraki_clients:
                    client_name_sanitized = client["name"].replace(" ", "-").lower()
                    domain_to_sync = f"{client_name_sanitized}{config['hostname_suffix']}"
                    if domain_to_sync in existing_pihole_records:
                        mapped_devices += 1
                with open("/app/history.log", "a") as f:
                    f.write(f"{int(time.time())},{mapped_devices}\n")

if __name__ == "__main__":
    try:
        main()
    except Exception:
        log.critical("An unhandled exception occurred in main", exc_info=True)
        sys.exit(1)
