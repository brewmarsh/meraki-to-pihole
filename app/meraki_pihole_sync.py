# Python script to sync Meraki client IPs to Pi-hole
import os
import sys
import configparser
import requests
import logging
import time
import argparse

# Configure logging
logging.basicConfig(stream=sys.stdout, level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')

MERAKI_API_KEY_ENV_VAR = "MERAKI_API_KEY"
DEFAULT_CONFIG_PATH = "/config/config.ini"

def load_meraki_api_key():
    """Loads Meraki API key from environment variable."""
    api_key = os.getenv(MERAKI_API_KEY_ENV_VAR)
    if not api_key:
        logging.error(f"{MERAKI_API_KEY_ENV_VAR} environment variable not set.")
        sys.exit(1)
    return api_key

def load_configuration(config_path):
    """Loads configuration from the INI file."""
    if not os.path.exists(config_path):
        logging.error(f"Configuration file not found at {config_path}")
        sys.exit(1)

    config = configparser.ConfigParser()
    config.read(config_path)

    try:
        # Get Pi-hole details: Prioritize environment variables, then config file
        pihole_api_url_env = os.getenv("PIHOLE_API_URL")
        pihole_api_key_env = os.getenv("PIHOLE_API_KEY")

        app_config = {
            "meraki_org_id": config.get('meraki', 'organization_id'),
            "meraki_network_ids": [nid.strip() for nid in config.get('meraki', 'network_ids', fallback='').split(',') if nid.strip()],

            "pihole_api_url": pihole_api_url_env if pihole_api_url_env else config.get('pihole', 'api_url'),
            "pihole_api_key": pihole_api_key_env if pihole_api_key_env else config.get('pihole', 'api_key', fallback=None),

            "hostname_suffix": config.get('script', 'hostname_suffix', fallback='.local'),
            "sync_interval_seconds": config.getint('script', 'sync_interval_seconds', fallback=3600)
        }
    except configparser.NoSectionError as e:
        logging.error(f"Configuration error: Missing section in config file: {e}")
        sys.exit(1)
    except configparser.NoOptionError as e:
        logging.error(f"Configuration error: Missing option in config file: {e}")
        sys.exit(1)
    except ValueError as e:
        logging.error(f"Configuration error: Invalid value in config file: {e}")
        sys.exit(1)

    if not app_config["meraki_org_id"] or app_config["meraki_org_id"] == "YOUR_MERAKI_ORGANIZATION_ID":
        logging.error("Meraki Organization ID is not configured in the config file.")
        sys.exit(1)
    if not app_config["pihole_api_url"] or app_config["pihole_api_url"] == "YOUR_PIHOLE_API_URL":
        logging.error("Pi-hole API URL is not configured in the config file.")
        sys.exit(1)
    # pihole_api_key can be optional if Pi-hole is not password protected

    return app_config

def main():
    parser = argparse.ArgumentParser(description="Meraki to Pi-hole DNS Sync Script")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help=f"Path to the configuration file (default: {DEFAULT_CONFIG_PATH})")
    args = parser.parse_args()

    logging.info(f"Starting Meraki Pi-hole Sync Script using config: {args.config}")

    meraki_api_key = load_meraki_api_key()
    app_config = load_configuration(args.config)

    logging.info(f"Configuration loaded: Meraki Org ID {app_config['meraki_org_id']}, "
                 f"Pi-hole URL {app_config['pihole_api_url']}, "
                 f"Networks to sync: {app_config['meraki_network_ids'] if app_config['meraki_network_ids'] else 'All in Org'}")

    # Main sync logic will go here
    meraki_clients = get_all_relevant_meraki_clients(meraki_api_key, app_config)

    if not meraki_clients:
        logging.info("No relevant Meraki clients found or an error occurred. Exiting sync process.")
        return

    logging.info(f"Successfully fetched {len(meraki_clients)} potentially relevant clients from Meraki.")

    pihole_url = app_config["pihole_api_url"]
    pihole_key = app_config["pihole_api_key"]
    hostname_suffix = app_config["hostname_suffix"]

    # 1. Fetch existing custom DNS records from Pi-hole
    existing_pihole_records = get_pihole_custom_dns_records(pihole_url, pihole_key)
    logging.info(f"Found {len(existing_pihole_records)} existing custom domains in Pi-hole.")

    processed_hostnames = set()

    # 2. Iterate through Meraki clients and add/update records in Pi-hole
    for client in meraki_clients:
        client_name = client.get("name")
        client_ip = client.get("ip")

        if not client_name or not client_ip:
            logging.debug(f"Skipping Meraki client due to missing name or IP: {client}")
            continue

        # Clean client name: replace spaces and other problematic characters for hostnames
        # This is a simple cleaning. More robust might be needed depending on names.
        cleaned_client_name = "".join(c if c.isalnum() or c == '-' else '-' for c in client_name.strip())
        if not cleaned_client_name:
            logging.warning(f"Client name '{client_name}' resulted in empty string after cleaning. Skipping.")
            continue

        # Construct the full hostname
        # Ensure suffix starts with a dot if not empty, and handle empty suffix.
        if hostname_suffix and not hostname_suffix.startswith('.'):
            full_hostname = f"{cleaned_client_name}.{hostname_suffix.lstrip('.')}"
        elif hostname_suffix: # Starts with a dot
            full_hostname = f"{cleaned_client_name}{hostname_suffix}"
        else: # No suffix
            full_hostname = cleaned_client_name

        full_hostname = full_hostname.lower() # DNS is case-insensitive

        logging.info(f"Processing Meraki client: {client_name} (IP: {client_ip}) -> Target Pi-hole DNS: {full_hostname}")

        add_or_update_dns_record_in_pihole(pihole_url, pihole_key, full_hostname, client_ip, existing_pihole_records)
        processed_hostnames.add(full_hostname)

    # 3. (Optional) Stale record cleanup:
    # This part is to remove records from Pi-hole that were previously managed by this script
    # but are no longer present in the current Meraki client list.
    # We identify managed records by checking if they end with the configured hostname_suffix.
    logging.info("Starting stale DNS record cleanup process...")
    if hostname_suffix: # Only attempt cleanup if a suffix is defined (helps scope)
        managed_domain_suffix = hostname_suffix.lower()
        if not managed_domain_suffix.startswith('.'):
            managed_domain_suffix = '.' + managed_domain_suffix

        for domain, ips in existing_pihole_records.items():
            if domain.endswith(managed_domain_suffix) and domain not in processed_hostnames:
                logging.info(f"Found stale DNS record in Pi-hole: {domain}. It ends with '{managed_domain_suffix}' and was not in the latest Meraki client list.")
                for ip_addr in ips:
                    logging.info(f"Deleting stale record: {domain} -> {ip_addr}")
                    delete_dns_record_from_pihole(pihole_url, pihole_key, domain, ip_addr)
            elif not domain.endswith(managed_domain_suffix):
                logging.debug(f"Skipping record {domain} from stale check as it does not match suffix '{managed_domain_suffix}'.")

    logging.info("Meraki to Pi-hole DNS sync process completed.")


MERAKI_API_BASE_URL = "https://api.meraki.com/api/v1"

def _meraki_api_request(api_key, method, endpoint, params=None, data=None):
    """Helper function to make requests to the Meraki API."""
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json"
    }
    url = f"{MERAKI_API_BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, params=params, json=data, timeout=20)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        return response.json()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Meraki API HTTP error: {e} - {e.response.text}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Meraki API request failed: {e}")
    return None

def get_organization_networks(api_key, org_id):
    """Fetches all networks for a given Meraki organization ID."""
    logging.info(f"Fetching networks for organization ID: {org_id}")
    endpoint = f"/organizations/{org_id}/networks"
    networks = _meraki_api_request(api_key, "GET", endpoint)
    if networks is not None:
        logging.info(f"Found {len(networks)} networks in organization {org_id}.")
    return networks

def get_network_clients(api_key, network_id, timespan=86400): # Default timespan 1 day = 86400s
    """
    Fetches active clients for a given Meraki network ID.
    A client needs to have been active within the timespan to be listed.
    """
    logging.info(f"Fetching clients for network ID: {network_id}")
    # The /clients endpoint can be slow and return a lot of data.
    # Consider using ?perPage=1000 and handling pagination if necessary,
    # or a shorter timespan if only very recent clients are needed.
    # For static IPs, they should always be listed if they communicated recently.
    endpoint = f"/networks/{network_id}/clients"
    params = {"timespan": timespan, "perPage": 1000} # Get clients seen in the last day
    clients = _meraki_api_request(api_key, "GET", endpoint, params=params)

    if clients is not None:
        logging.info(f"Found {len(clients)} clients in network {network_id} within timespan {timespan}s.")
        # Filter for clients that have an IP and a description (often used as hostname)
        # Meraki API sometimes returns clients with no IP or description.
        # A 'fixedIp' field might exist if DHCP reservation is set, but 'ip' is the current one.
        # We are interested in clients that have a 'description' (often the hostname) and an 'ip'.
        # Clients with 'dhcpHostname' can also be useful.
        # Static IPs are usually configured on the client or via DHCP reservation.
        # The API shows the current IP. We assume this is what we want to map.

        # For now, returning all clients, filtering will happen in the main logic
    return clients


def get_all_relevant_meraki_clients(api_key, config):
    """
    Fetches all clients from specified (or all) Meraki networks
    that have a description and an IP address.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    all_clients_map = {} # Using a map to ensure unique client entries if IDs overlap or for future structure

    networks_to_query = []
    if not specified_network_ids:
        logging.info(f"No specific network IDs provided, fetching all networks for org {org_id}.")
        organization_networks = get_organization_networks(api_key, org_id)
        if organization_networks:
            networks_to_query = organization_networks
        else:
            logging.warning(f"Could not fetch networks for organization {org_id}. Cannot proceed.")
            return {} # Return empty dict
    else:
        # If specific network IDs are given, we might want to fetch their names for logging/domain construction
        # For now, just use the IDs.
        # We create a list of dicts similar to what get_organization_networks would return for structure.
        logging.info(f"Fetching data for specified network IDs: {specified_network_ids}")
        # To get network names, we'd ideally call get_organization_networks and filter.
        # Or, call getNetwork for each ID. For simplicity now, we'll assume IDs are enough.
        # If we need network names later for DNS entry construction (e.g. client.networkname.local),
        # we'll need to adjust this.
        # The current config sample for hostname_suffix is just ".local", not network-dependent.
        organization_networks = get_organization_networks(api_key, org_id)
        if not organization_networks:
            logging.warning(f"Could not fetch networks for organization {org_id} to validate specified IDs.")
            # Fallback: try to use specified IDs directly
            networks_to_query = [{"id": nid, "name": "Unknown (specified by ID)"} for nid in specified_network_ids]
        else:
            name_map = {net['id']: net['name'] for net in organization_networks}
            for nid in specified_network_ids:
                if nid in name_map:
                    networks_to_query.append({"id": nid, "name": name_map[nid]})
                else:
                    logging.warning(f"Specified network ID {nid} not found in organization {org_id}. Skipping.")


    for network in networks_to_query:
        network_id = network["id"]
        network_name = network.get("name", "UnknownNetwork") # Get network name for context
        logging.info(f"Processing network: {network_name} (ID: {network_id})")
        clients_in_network = get_network_clients(api_key, network_id)
        if clients_in_network:
            for client in clients_in_network:
                # A client is relevant if it has an IP and a description (hostname)
                # 'description' is often manually set or is the device name.
                # 'dhcpHostname' is what the device sends in DHCP request.
                # 'mdnsName' is from Bonjour/mDNS.
                # We will prioritize 'description', then 'dhcpHostname'.
                client_name = client.get('description') or client.get('dhcpHostname')
                client_ip = client.get('ip')
                client_id = client.get('id') # Unique client ID from Meraki

                if client_name and client_ip and client_id:
                    # Ensure unique entries per client ID, preferring the most recent info if somehow duplicated
                    # (though get_network_clients for a single network shouldn't duplicate client IDs)
                    all_clients_map[client_id] = {
                        "name": client_name,
                        "ip": client_ip,
                        "network_id": network_id,
                        "network_name": network_name,
                        "meraki_client_id": client_id
                    }
                    logging.debug(f"Found relevant client: {client_name} ({client_ip}) in network {network_name}")
                else:
                    logging.debug(f"Skipping client (ID: {client.get('id')}, MAC: {client.get('mac')}) due to missing name or IP in network {network_name}.")
        else:
            logging.info(f"No clients found or error fetching clients for network {network_name} (ID: {network_id}).")

    return list(all_clients_map.values())

# --- Pi-hole API Functions ---

def _pihole_api_request(pihole_url, api_key, params):
    """Helper function to make requests to the Pi-hole API."""
    if not pihole_url.endswith("api.php"):
        logging.warning(f"Pi-hole URL {pihole_url} does not end with api.php. Appending it.")
        pihole_url = pihole_url.rstrip('/') + "/api.php"

    # Ensure 'auth' token is part of params if api_key is provided
    if api_key:
        params['auth'] = api_key

    try:
        response = requests.get(pihole_url, params=params, timeout=10)
        response.raise_for_status()
        # Pi-hole API often returns JSON but sometimes just a simple string or empty on success for actions
        # For GET customdns, it returns {'data': [[domain, ip], ...]}
        # For actions like add/delete, it might return {"success": true, "message": "..."} or be empty on success
        if response.text:
            try:
                return response.json()
            except ValueError: # Not JSON
                logging.debug(f"Pi-hole API response was not JSON: {response.text}")
                # For some successful actions, Pi-hole returns an empty body or non-JSON.
                # We can check status code for success if content is not JSON.
                if response.ok:
                    return {"success": True, "message": "Action likely successful (non-JSON response)."}
                return {"success": False, "message": f"Request failed, non-JSON response: {response.text}"}

        elif response.ok: # Empty response but status OK
             return {"success": True, "message": "Action successful (empty response)."}
        else: # Empty response and status not OK
            return {"success": False, "message": f"Request failed with status {response.status_code} (empty response)."}

    except requests.exceptions.HTTPError as e:
        logging.error(f"Pi-hole API HTTP error: {e} - {e.response.text if e.response else 'No response text'}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Pi-hole API request failed: {e}")
    return None


def get_pihole_custom_dns_records(pihole_url, api_key):
    """Fetches all custom DNS records from Pi-hole."""
    logging.info("Fetching existing custom DNS records from Pi-hole...")
    params = {"customdns": "", "action": "get"}
    response_data = _pihole_api_request(pihole_url, api_key, params)

    records = {}
    if response_data and 'data' in response_data:
        # Pi-hole v5.x returns: {'data': [['domain1', 'ip1'], ['domain2', 'ip2']]}
        for domain, ip_address in response_data['data']:
            if domain not in records:
                records[domain] = []
            records[domain].append(ip_address)
        logging.info(f"Found {len(records)} unique domains with custom DNS records in Pi-hole.")
    elif response_data: # Check for older Pi-hole versions or different structures if necessary
        # Older Pi-hole might return a flat list or different structure.
        # This script targets Pi-hole v5+ API behavior.
        logging.warning(f"Pi-hole custom DNS response format unexpected or empty: {response_data}")
    else:
        logging.error("Failed to fetch custom DNS records from Pi-hole.")
    return records

def add_dns_record_to_pihole(pihole_url, api_key, domain, ip_address):
    """Adds a custom DNS record to Pi-hole."""
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "add", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and response.get("success", False): # Pi-hole add success is often an empty JSON {} or non-JSON success
        logging.info(f"Successfully added DNS record: {domain} -> {ip_address}. Response: {response.get('message', '')}")
        return True
    else:
        logging.error(f"Failed to add DNS record {domain} -> {ip_address}. Response: {response}")
        return False

def delete_dns_record_from_pihole(pihole_url, api_key, domain, ip_address):
    """Deletes a custom DNS record from Pi-hole."""
    logging.info(f"Deleting DNS record from Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "delete", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and response.get("success", False): # Pi-hole delete success is often an empty JSON {} or non-JSON success
        logging.info(f"Successfully deleted DNS record: {domain} -> {ip_address}. Response: {response.get('message', '')}")
        return True
    else:
        logging.error(f"Failed to delete DNS record {domain} -> {ip_address}. Response: {response}")
        return False

def add_or_update_dns_record_in_pihole(pihole_url, api_key, domain, new_ip, existing_records):
    """
    Adds a new DNS record or updates an existing one in Pi-hole.
    If the domain exists with a different IP, the old IP(s) for that domain are deleted first.
    If the domain exists with the same IP, no action is taken.
    """
    domain_cleaned = domain.strip().lower()
    new_ip_cleaned = new_ip.strip()

    if not domain_cleaned or not new_ip_cleaned:
        logging.warning(f"Skipping invalid record: domain='{domain}', ip='{new_ip}'")
        return False

    # Check if the exact record already exists
    if domain_cleaned in existing_records and new_ip_cleaned in existing_records[domain_cleaned]:
        logging.info(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True # Record already exists and is correct

    # If domain exists, but with different IP(s), delete old entries for this domain
    if domain_cleaned in existing_records:
        for old_ip in existing_records[domain_cleaned]:
            if old_ip != new_ip_cleaned:
                logging.info(f"Found old IP {old_ip} for domain {domain_cleaned}. Deleting it before adding new IP {new_ip_cleaned}.")
                delete_dns_record_from_pihole(pihole_url, api_key, domain_cleaned, old_ip)

    # Add the new record
    return add_dns_record_to_pihole(pihole_url, api_key, domain_cleaned, new_ip_cleaned)


if __name__ == "__main__":
    main()
