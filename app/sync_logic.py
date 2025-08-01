import os
import sys
import time
from datetime import datetime
from pathlib import Path

import meraki
import structlog

from .clients.meraki_client import get_all_relevant_meraki_clients
from .clients.pihole_client import PiholeClient

log = structlog.get_logger()

ENV_MERAKI_API_KEY = "MERAKI_API_KEY"
ENV_MERAKI_ORG_ID = "MERAKI_ORG_ID"
ENV_MERAKI_NETWORK_IDS = "MERAKI_NETWORK_IDS"
ENV_PIHOLE_API_URL = "PIHOLE_API_URL"
ENV_PIHOLE_API_KEY = "PIHOLE_API_KEY"
ENV_HOSTNAME_SUFFIX = "HOSTNAME_SUFFIX"
ENV_CLIENT_TIMESPAN = "MERAKI_CLIENT_TIMESPAN_SECONDS"


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
        config[var_name.lower()] = value

    if missing_vars_messages:
        log.error(
            "Missing mandatory environment variables", missing_vars=missing_vars_messages
        )
        sys.exit(1)

    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY)
    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, "")
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(",") if nid.strip()]

    try:
        default_timespan = "86400"
        config["meraki_client_timespan_seconds"] = int(os.getenv(ENV_CLIENT_TIMESPAN, default_timespan))
    except ValueError:
        log.warning(
            "Invalid value for MERAKI_CLIENT_TIMESPAN_SECONDS, using default",
            invalid_value=os.getenv(ENV_CLIENT_TIMESPAN),
            default_value=default_timespan,
        )
        config["meraki_client_timespan_seconds"] = int(default_timespan)

    if config["meraki_org_id"].upper() == "YOUR_MERAKI_ORGANIZATION_ID":
        log.error("Placeholder value detected for MERAKI_ORG_ID")
        sys.exit(1)
    if (
        config["pihole_api_url"].upper() == "YOUR_PIHOLE_API_URL"
        or "YOUR_PIHOLE_IP_OR_HOSTNAME" in config["pihole_api_url"].upper()
    ):
        log.error("Placeholder value detected for PIHOLE_API_URL")
        sys.exit(1)
    example_suffixes = [".LOCAL", ".YOURDOMAIN.LOCAL", ".YOURCUSTOMDOMAIN.LOCAL", "YOUR_HOSTNAME_SUFFIX"]
    if config["hostname_suffix"].upper() in example_suffixes:
        log.warning(
            "Possible example/placeholder value detected for HOSTNAME_SUFFIX",
            hostname_suffix=config["hostname_suffix"],
        )

    log.info("Successfully loaded configuration from environment variables.")
    return config


def get_meraki_data(config):
    dashboard = meraki.DashboardAPI(
        api_key=config["meraki_api_key"],
        output_log=False,
        print_console=False,
        suppress_logging=True,
    )
    return get_all_relevant_meraki_clients(dashboard, config)


def get_mappings_data():
    try:
        config = load_app_config_from_env()
        pihole_client = PiholeClient(config["pihole_api_url"], config["pihole_api_key"])
        pihole_records = pihole_client.get_custom_dns_records()
        if not pihole_records:
            return {}

        meraki_clients = get_meraki_data(config)
        mapped_devices, unmapped_meraki_devices = map_devices(meraki_clients, pihole_records)

        return {"pihole": pihole_records, "meraki": meraki_clients, "mapped": mapped_devices, "unmapped_meraki": unmapped_meraki_devices}
    except Exception as e:
        log.error("Error in get_mappings_data", error=e)
        return {}

def map_devices(meraki_clients, pihole_records):
    mapped_devices = []
    unmapped_meraki_devices = []
    pihole_ips = set(pihole_records.values())

    for client in meraki_clients:
        if client['ip'] in pihole_ips:
            for domain, ip in pihole_records.items():
                if client['ip'] == ip:
                    mapped_devices.append({
                        "meraki_name": client['name'],
                        "pihole_domain": domain,
                        "ip": ip
                    })
        else:
            unmapped_meraki_devices.append(client)

    return mapped_devices, unmapped_meraki_devices

def get_sync_interval():
    """
    Determines the sync interval in seconds, checking three sources in order:
    1. A temporary file (`/app/sync_interval.txt`) which can be created by the web UI.
    2. The `SYNC_INTERVAL_SECONDS` environment variable.
    3. A hardcoded default value (300 seconds).

    Returns:
        int: The sync interval in seconds.
    """
    try:
        interval_file = Path("/app/sync_interval.txt")
        if interval_file.exists():
            interval = int(interval_file.read_text().strip())
            log.debug("Using sync interval from file", interval=interval)
            return interval
    except (OSError, ValueError):
        pass

    try:
        interval = int(os.getenv("SYNC_INTERVAL_SECONDS"))
        log.debug("Using sync interval from environment variable", interval=interval)
        return interval
    except (TypeError, ValueError):
        pass

    default_interval = 300
    log.debug("Using default sync interval", interval=default_interval)
    return default_interval

def sync_pihole_dns(update_type=None):
    """
    Main function to run the Meraki to Pi-hole sync process.
    Loads configuration, fetches Meraki clients, gets Pi-hole records,
    and syncs them.
    """
    app_version = os.getenv("APP_VERSION", "Not Set")
    commit_sha = os.getenv("COMMIT_SHA", "Not Set")
    log.info("Starting Meraki Pi-hole Sync Script", version=app_version, commit=commit_sha)

    config = load_app_config_from_env()
    meraki_clients = get_meraki_data(config)
    if (update_type is None or update_type == "pihole") and meraki_clients:
        pihole_client = PiholeClient(config["pihole_api_url"], config["pihole_api_key"])
        existing_pihole_records = pihole_client.get_custom_dns_records()

        if existing_pihole_records is not None:
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

                for client in meraki_clients:
                    if not client.get("name"):
                        log.warning("Skipping client with no name", client_ip=client.get("ip"))
                        continue

                    client_name = client["name"]
                    if ":" in client_name:
                        log.warning("Skipping client with invalid characters in name", client_name=client_name)
                        continue

                    client_name_sanitized = client_name.replace(" ", "-").lower()
                    domain_to_sync = f"{client_name_sanitized}{config['hostname_suffix']}"
                    ip_to_sync = client["ip"]

                    if pihole_client.add_or_update_dns_record(domain_to_sync, ip_to_sync):
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

                for domain, ip in existing_pihole_records.items():
                    pihole_hostname = domain.replace(config['hostname_suffix'], "")
                    if ip not in meraki_clients_by_ip and pihole_hostname not in meraki_clients_by_name:
                        if pihole_client.remove_dns_record(domain, ip):
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

            mapped_devices = 0
            unmapped_meraki_devices = []
            for client in meraki_clients:
                if client.get("name"):
                    client_name_sanitized = client["name"].replace(" ", "-").lower()
                    domain_to_sync = f"{client_name_sanitized}{config['hostname_suffix']}"
                    if domain_to_sync in existing_pihole_records:
                        mapped_devices += 1
                    else:
                        unmapped_meraki_devices.append(client)
                else:
                    unmapped_meraki_devices.append(client)
            with Path("/app/history.log").open("a") as f:
                f.write(f"{int(time.time())},{mapped_devices}\n")

            with Path("/app/cache.json").open("w") as f:
                import json
                json.dump({
                    "pihole": existing_pihole_records,
                    "meraki": meraki_clients,
                    "mapped": mapped_devices,
                    "unmapped_meraki": unmapped_meraki_devices,
                }, f)
