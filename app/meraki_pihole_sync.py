# Python script to sync Meraki client IPs to Pi-hole
import os
import sys
import requests
import logging
import time

# --- Logging Setup ---
LOG_DIR = "/app/logs"
# Ensure the directory exists. This should ideally be done in the Dockerfile,
# but this provides a fallback if running outside Docker or if permissions are tricky.
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True) # exist_ok=True handles race conditions
    except OSError as e:
        # Fallback to printing to stderr if log directory creation fails
        print(f"CRITICAL: Could not create log directory {LOG_DIR}. Error: {e}", file=sys.stderr)
        # Attempt to continue by logging to stdout only, though file logging will fail.
        # This is better than crashing if the script is critical.
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
            handlers=[logging.StreamHandler(sys.stdout)]
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
    format='%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode='a'), # Append mode
        logging.StreamHandler(sys.stdout) # For `docker logs`
    ]
)
# --- End Logging Setup ---

# Environment Variable Names
ENV_APP_VERSION = "APP_VERSION"
ENV_COMMIT_SHA = "COMMIT_SHA"
ENV_MERAKI_API_KEY = "MERAKI_API_KEY"
ENV_MERAKI_ORG_ID = "MERAKI_ORG_ID"
ENV_MERAKI_NETWORK_IDS = "MERAKI_NETWORK_IDS" # Comma-separated string
ENV_PIHOLE_API_URL = "PIHOLE_API_URL"
ENV_PIHOLE_API_KEY = "PIHOLE_API_KEY"
ENV_HOSTNAME_SUFFIX = "HOSTNAME_SUFFIX"
ENV_CLIENT_TIMESPAN = "MERAKI_CLIENT_TIMESPAN_SECONDS" # Optional, defaults to 1 day (86400s)

MERAKI_API_BASE_URL = "https://api.meraki.com/api/v1"

def load_app_config_from_env():
    """Loads all application configuration from environment variables."""
    config = {}
    mandatory_vars = {
        ENV_MERAKI_API_KEY: "Meraki API Key",
        ENV_MERAKI_ORG_ID: "Meraki Organization ID",
        ENV_PIHOLE_API_URL: "Pi-hole API URL",
        ENV_HOSTNAME_SUFFIX: "Hostname Suffix"
    }
    missing_vars_messages = []

    for var_name, desc in mandatory_vars.items():
        value = os.getenv(var_name)
        if not value:
            missing_vars_messages.append(f"{desc} ({var_name})")
        config[var_name.lower()] = value

    if missing_vars_messages:
        logging.error(f"Missing mandatory environment variables: {', '.join(missing_vars_messages)}")
        sys.exit(1)

    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY)

    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, '')
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(',') if nid.strip()]

    try:
        config["meraki_client_timespan"] = int(os.getenv(ENV_CLIENT_TIMESPAN, "86400"))
    except ValueError:
        logging.warning(f"Invalid value for {ENV_CLIENT_TIMESPAN}: '{os.getenv(ENV_CLIENT_TIMESPAN)}'. Using default 86400 seconds (24 hours).")
        config["meraki_client_timespan"] = 86400

    if config["meraki_org_id"].upper() == "YOUR_MERAKI_ORGANIZATION_ID":
        logging.error(f"Placeholder value detected for {ENV_MERAKI_ORG_ID}. Please set a valid Organization ID.")
        sys.exit(1)
    if config["pihole_api_url"].upper() == "YOUR_PIHOLE_API_URL" or "YOUR_PIHOLE_IP_OR_HOSTNAME" in config["pihole_api_url"].upper():
        logging.error(f"Placeholder value detected for {ENV_PIHOLE_API_URL}. Please set a valid Pi-hole API URL.")
        sys.exit(1)
    if config["hostname_suffix"].upper() in [".LOCAL", ".YOURDOMAIN.LOCAL", ".YOURCUSTOMDOMAIN.LOCAL", "YOUR_HOSTNAME_SUFFIX"]:
        logging.warning(f"Possible example/placeholder value detected for {ENV_HOSTNAME_SUFFIX} ('{config['hostname_suffix']}'). Ensure this is your intended suffix.")

    logging.info("Successfully loaded configuration from environment variables.")
    return config

def _meraki_api_request(api_key, method, endpoint, params=None, data=None, attempt=1, max_attempts=3):
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{MERAKI_API_BASE_URL}{endpoint}"
    try:
        logging.debug(f"Meraki API Request: {method} {url} Params: {params}")
        response = requests.request(method, url, headers=headers, params=params, json=data, timeout=20)

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", "60"))
            logging.warning(f"Meraki API rate limit hit (Status 429) for {method} {url}. Retrying after {retry_after} seconds (attempt {attempt}/{max_attempts})...")
            if attempt < max_attempts:
                time.sleep(retry_after)
                return _meraki_api_request(api_key, method, endpoint, params, data, attempt + 1, max_attempts)
            else:
                logging.error(f"Meraki API rate limit hit, and max retries ({max_attempts}) reached for {method} {url}.")
                return None

        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_message = f"Meraki API HTTP error for {method} {url}: {e}."
        if e.response is not None:
            error_message += f" Status: {e.response.status_code if e.response else 'N/A'}. Response: {e.response.text if e.response else 'No response text'}"
        logging.error(error_message)
    except requests.exceptions.RequestException as e:
        logging.error(f"Meraki API request failed for {method} {url}: {e}")
        logging.error(f"Meraki API request failed for {method} {url}: {e}")
    return None

def get_organization_networks(api_key, org_id):
    logging.info(f"Fetching networks for organization ID: {org_id}")
    endpoint = f"/organizations/{org_id}/networks"
    networks = _meraki_api_request(api_key, "GET", endpoint)
    if networks is not None:
        logging.info(f"Successfully fetched {len(networks)} networks for organization {org_id}.")
    else:
        logging.error(f"Failed to fetch networks for organization {org_id} (API request returned None or error).")
    return networks

def get_network_clients(api_key, network_id, timespan):
    logging.info(f"Fetching clients for network ID: {network_id} (timespan: {timespan}s)")
    endpoint = f"/networks/{network_id}/clients"
    params = {"timespan": str(timespan), "perPage": "1000"}
    clients = _meraki_api_request(api_key, "GET", endpoint, params=params)
    if clients is not None:
        logging.info(f"API returned {len(clients)} clients for network '{network_id}' (before filtering for fixed IPs).")
    else:
        logging.warning(f"API call for clients in network {network_id} did not return data.")
    return clients


def get_all_relevant_meraki_clients(api_key, config):
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    client_timespan = config["meraki_client_timespan"]

    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: '{specified_network_ids}'. Client Timespan: {client_timespan}s.")
    all_clients_map = {}

    networks_to_query = []
    if not specified_network_ids:
        logging.info(f"No specific Meraki network IDs provided via {ENV_MERAKI_NETWORK_IDS}. Attempting to fetch all networks for organization ID: {org_id}.")
        organization_networks = get_organization_networks(api_key, org_id)
        if organization_networks is not None:
            if not organization_networks:
                 logging.info(f"Organization {org_id} has no networks according to API. No clients will be fetched.")
                 return []
            networks_to_query = organization_networks
        else:
            logging.warning(f"Failed to fetch networks for organization {org_id}. No clients will be fetched.")
            return []
    else:
        logging.info(f"Specific Meraki network IDs provided: {specified_network_ids}. Validating and fetching details for these networks.")
        organization_networks = get_organization_networks(api_key, org_id)
        if organization_networks is None:
            logging.warning(f"Could not fetch network list for organization {org_id} to validate specified IDs. Proceeding with specified IDs directly, but network names will be 'Unknown'.")
            networks_to_query = [{"id": nid, "name": f"Unknown (ID: {nid})"} for nid in specified_network_ids]
        else:
            name_map = {net['id']: net['name'] for net in organization_networks}
            valid_networks_to_query = []
            for nid_spec in specified_network_ids:
                if nid_spec in name_map:
                    valid_networks_to_query.append({"id": nid_spec, "name": name_map[nid_spec]})
                else:
                    logging.warning(f"Specified network ID {nid_spec} not found in organization {org_id}. It will be skipped.")
            networks_to_query = valid_networks_to_query
            if not networks_to_query:
                 logging.warning(f"None of the specified network IDs {specified_network_ids} were found/valid in organization {org_id}. No clients will be fetched.")
                 return []

    if not networks_to_query:
        logging.info("No networks to query after initial determination (e.g., all specified IDs were invalid or org has no networks). Exiting client search.")
    if not networks_to_query:
        logging.info("No networks to query after initial determination (e.g., all specified IDs were invalid or org has no networks). Exiting client search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query)}. Network IDs: {[n['id'] for n in networks_to_query]}")


    for network_idx, network in enumerate(networks_to_query):
        network_id = network["id"]
        network_name = network.get("name", f"ID-{network_id}")
        logging.info(f"--- Processing network {network_idx + 1}/{len(networks_to_query)}: '{network_name}' (ID: {network_id}) ---")

        clients_in_network = get_network_clients(api_key, network_id, client_timespan)

        if clients_in_network is not None:
            if clients_in_network:
                logging.debug(f"Fetched {len(clients_in_network)} clients from network '{network_name}'. Filtering for fixed IPs...")
                for client in clients_in_network:
                    client_name_desc = client.get('description')
                    client_name_dhcp = client.get('dhcpHostname')
                    client_name = client_name_desc or client_name_dhcp

                    client_ip = client.get('ip')
                    client_id = client.get('id')
                    fixed_ip_assignment_data = client.get('fixedIpAssignment')

                    if client_name and client_ip and client_id:
                        is_fixed_ip_client = False
                        if fixed_ip_assignment_data and isinstance(fixed_ip_assignment_data, dict):
                            assigned_ip = fixed_ip_assignment_data.get('ip')
                            if assigned_ip and assigned_ip == client_ip:
                                is_fixed_ip_client = True
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) has a matching fixed IP assignment: {assigned_ip} in network '{network_name}'.")
                            elif assigned_ip:
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' has a fixed IP assignment ({assigned_ip}) but current IP ({client_ip}) differs. Skipping.")
                            else:
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' has a fixedIpAssignment object without an 'ip' field. Skipping.")
                        else:
                            logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' does not have a fixed IP assignment. Skipping.")

                        if is_fixed_ip_client:
                            all_clients_map[client_id] = {
                                "name": client_name,
                                "ip": client_ip,
                                "network_id": network_id,
                                "network_name": network_name,
                                "meraki_client_id": client_id
                            }
                            logging.info(f"Relevant client with fixed IP: '{client_name}' ({client_ip}) in network '{network_name}' (Meraki ID: {client_id}) will be processed.")
                    else:
                        logging.debug(f"Skipping client (Meraki ID: {client.get('id')}, MAC: {client.get('mac')}) in network '{network_name}' due to missing name, current IP, or client ID prior to fixed IP check.")
            else:
                logging.info(f"No clients reported by API for network {network_name} (ID: {network_id}).")
        else:
            logging.warning(f"Failed to fetch clients for network {network_name} (ID: {network_id}). Skipping this network.")

        logging.info(f"--- Finished processing network {network_idx + 1}/{len(networks_to_query)}: {network_name} (ID: {network_id}) ---")

    return list(all_clients_map.values())

# --- Pi-hole API Functions ---

def _pihole_api_request(pihole_url, api_key, params):
    if not pihole_url.endswith("api.php"):
        pihole_url = pihole_url.rstrip('/') + "/api.php"

    if api_key:
        params['auth'] = api_key

    try:
        logging.debug(f"Pi-hole API Request: URL={pihole_url}, Params={params}")
        response = requests.get(pihole_url, params=params, timeout=10)
        response.raise_for_status()
        if response.text:
            try:
                json_response = response.json()
                logging.debug(f"Pi-hole API JSON Response: {json_response}")
                return json_response
            except ValueError:
                logging.debug(f"Pi-hole API response was not JSON: {response.text}")
                if response.ok and response.text.strip() == '[]':
                    return {"data": []}
                elif response.ok:
                    return {"success": True, "message": f"Action likely successful (non-JSON response: {response.text[:100]})"}
                return {"success": False, "message": f"Request failed, non-JSON response: {response.text[:100]}"}
        elif response.ok:
             return {"success": True, "message": "Action successful (empty response)."}
        else:
            return {"success": False, "message": f"Request failed with status {response.status_code} (empty response)."}
    except requests.exceptions.HTTPError as e:
        logging.error(f"Pi-hole API HTTP error: {e} - {e.response.text if e.response else 'No response text'}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Pi-hole API request failed: {e}")
    return None


def get_pihole_custom_dns_records(pihole_url, api_key):
    logging.info("Fetching existing custom DNS records from Pi-hole...")
    params = {"customdns": "", "action": "get"}
    response_data = _pihole_api_request(pihole_url, api_key, params)

    records = {}
    if response_data and isinstance(response_data.get('data'), list):
        for item in response_data['data']:
            if isinstance(item, list) and len(item) == 2:
                domain, ip_address = item
                if domain not in records:
                    records[domain] = []
                records[domain].append(ip_address)
        logging.info(f"Found {len(records)} unique domains with {sum(len(v) for v in records.values())} total custom DNS records in Pi-hole.")
    elif response_data:
        logging.warning(f"Pi-hole custom DNS response format unexpected or 'data' field missing/not a list: {response_data}")
    else:
        logging.error("Failed to fetch custom DNS records from Pi-hole or API error.")
        return None
    return records

def add_dns_record_to_pihole(pihole_url, api_key, domain, ip_address):
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "add", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and (response == {} or response.get("success") is True or (isinstance(response.get("message"), str) and "added" in response.get("message").lower())):
        logging.info(f"Successfully processed add DNS record for: {domain} -> {ip_address}. Pi-hole Response: {response.get('message', 'OK') if isinstance(response, dict) else 'Empty success response'}")
        return True
    else:
        logging.error(f"Failed to add DNS record {domain} -> {ip_address}. Response: {response}")
        return False

def delete_dns_record_from_pihole(pihole_url, api_key, domain, ip_address):
    logging.info(f"Deleting DNS record from Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "delete", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and (response == {} or response.get("success") is True or (isinstance(response.get("message"), str) and ("deleted" in response.get("message").lower() or "does not exist" in response.get("message").lower()))):
        logging.info(f"Successfully processed delete DNS record for: {domain} -> {ip_address}. Pi-hole Response: {response.get('message', 'OK') if isinstance(response, dict) else 'Empty success response'}")
        return True
    else:
        logging.error(f"Failed to delete DNS record {domain} -> {ip_address}. Response: {response}")
        return False

def add_or_update_dns_record_in_pihole(pihole_url, api_key, domain, new_ip, existing_records):
    domain_cleaned = domain.strip().lower()
    new_ip_cleaned = new_ip.strip()

    if not domain_cleaned or not new_ip_cleaned:
        logging.warning(f"Skipping invalid record: domain='{domain}', ip='{new_ip}'")
        return False

    if existing_records is None:
        logging.error("Cannot add or update DNS record because existing Pi-hole records could not be fetched.")
        return False

    if domain_cleaned in existing_records and new_ip_cleaned in existing_records[domain_cleaned]:
        logging.info(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True
        return True

    if domain_cleaned in existing_records:
        logging.info(f"Domain {domain_cleaned} found in Pi-hole with IP(s): {existing_records[domain_cleaned]}. Will ensure only {new_ip_cleaned} remains.")
        for old_ip in list(existing_records[domain_cleaned]):
            if old_ip != new_ip_cleaned:
                logging.info(f"Deleting old IP {old_ip} for domain {domain_cleaned} before adding new IP {new_ip_cleaned}.")
                if not delete_dns_record_from_pihole(pihole_url, api_key, domain_cleaned, old_ip):
                    logging.error(f"Failed to delete old record {domain_cleaned} -> {old_ip}. Halting update for this domain to avoid duplicates.")
                    return False
                if old_ip in existing_records[domain_cleaned]:
                    existing_records[domain_cleaned].remove(old_ip)
        if not existing_records[domain_cleaned]:
            del existing_records[domain_cleaned]

    return add_dns_record_to_pihole(pihole_url, api_key, domain_cleaned, new_ip_cleaned)


def main():
    config = load_app_config_from_env()
    api_key = config["meraki_api_key"]
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config["pihole_api_key"]
    hostname_suffix = config["hostname_suffix"]

    # Fetch relevant Meraki clients
    clients = get_all_relevant_meraki_clients(api_key, config)
    if not clients:
        logging.info("No relevant Meraki clients found. Exiting.")
        return

    # Fetch existing Pi-hole DNS records
    existing_records = get_pihole_custom_dns_records(pihole_url, pihole_api_key)
    if existing_records is None:
        logging.error("Could not fetch existing Pi-hole DNS records. Exiting.")
        return

    # Sync each client to Pi-hole
    for client in clients:
        domain = f"{client['name']}{hostname_suffix}".lower().replace(" ", "-")
        ip = client["ip"]
        add_or_update_dns_record_in_pihole(pihole_url, pihole_api_key, domain, ip, existing_records)

if __name__ == "__main__":
    main()
