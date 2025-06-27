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

# --- Constants ---
MERAKI_API_BASE_URL = "https://api.meraki.com/api/v1"

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
        ENV_HOSTNAME_SUFFIX: "Hostname Suffix"
    }
    missing_vars_messages = []

    for var_name, desc in mandatory_vars.items():
        value = os.getenv(var_name)
        if not value:
            missing_vars_messages.append(f"{desc} ({var_name})")
        config[var_name.lower()] = value # Store keys in lowercase for consistent access

    if missing_vars_messages:
        logging.error(f"Missing mandatory environment variables: {', '.join(missing_vars_messages)}. Please set them and try again.")
        sys.exit(1)

    # Optional environment variables
    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY) # Can be None if Pi-hole auth is not used

    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, '') # Default to empty string
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(',') if nid.strip()]

    try:
        default_timespan = "86400" # 24 hours in seconds
        config["meraki_client_timespan"] = int(os.getenv(ENV_CLIENT_TIMESPAN, default_timespan))
    except ValueError:
        logging.warning(f"Invalid value for {ENV_CLIENT_TIMESPAN}: '{os.getenv(ENV_CLIENT_TIMESPAN)}'. Using default {default_timespan} seconds (24 hours).")
        config["meraki_client_timespan"] = int(default_timespan)

    # Sanity checks for placeholder values
    if config["meraki_org_id"].upper() == "YOUR_MERAKI_ORGANIZATION_ID":
        logging.error(f"Placeholder value detected for {ENV_MERAKI_ORG_ID}. Please set a valid Organization ID.")
        sys.exit(1)
    if config["pihole_api_url"].upper() == "YOUR_PIHOLE_API_URL" or \
       "YOUR_PIHOLE_IP_OR_HOSTNAME" in config["pihole_api_url"].upper():
        logging.error(f"Placeholder value detected for {ENV_PIHOLE_API_URL}. Please set a valid Pi-hole API URL.")
        sys.exit(1)
    # Check for common example/placeholder suffixes to warn the user
    example_suffixes = [".LOCAL", ".YOURDOMAIN.LOCAL", ".YOURCUSTOMDOMAIN.LOCAL", "YOUR_HOSTNAME_SUFFIX"]
    if config["hostname_suffix"].upper() in example_suffixes:
        logging.warning(f"Possible example/placeholder value detected for {ENV_HOSTNAME_SUFFIX} ('{config['hostname_suffix']}'). Ensure this is your intended suffix.")

    logging.info("Successfully loaded configuration from environment variables.")
    return config

def _meraki_api_request(api_key, method, endpoint, params=None, data=None, attempt=1, max_attempts=3):
    """
    Helper function to make requests to the Meraki API.
    Includes error handling, rate limit handling (429), and retries.
    """
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{MERAKI_API_BASE_URL}{endpoint}"

    try:
        logging.debug(f"Meraki API Request: {method} {url} Params: {params if params else 'None'}")
        response = requests.request(method, url, headers=headers, params=params, json=data, timeout=20)

        if response.status_code == 429: # Rate limit
            retry_after = int(response.headers.get("Retry-After", "60")) # Default to 60s if header missing
            logging.warning(f"Meraki API rate limit hit (Status 429) for {method} {url}. Retrying after {retry_after} seconds (attempt {attempt}/{max_attempts})...")
            if attempt < max_attempts:
                time.sleep(retry_after)
                return _meraki_api_request(api_key, method, endpoint, params, data, attempt + 1, max_attempts)
            else:
                logging.error(f"Meraki API rate limit hit, and max retries ({max_attempts}) reached for {method} {url}. Giving up.")
                return None

        response.raise_for_status() # Raises HTTPError for bad responses (4xx or 5xx)
        return response.json()
    except requests.exceptions.HTTPError as e:
        error_message = f"Meraki API HTTP error for {method} {url}: {e}."
        if e.response is not None:
            error_message += f" Status: {e.response.status_code}. Response: {e.response.text[:200] if e.response.text else 'No response text'}" # Truncate long responses
        logging.error(error_message)
    except requests.exceptions.RequestException as e: # Covers DNS errors, connection timeouts, etc.
        logging.error(f"Meraki API request failed for {method} {url} due to a network or request issue: {e}")
    return None

def get_organization_networks(api_key, org_id):
    """Fetches all networks for a given Meraki organization ID."""
    logging.info(f"Fetching networks for organization ID: {org_id}")
    endpoint = f"/organizations/{org_id}/networks"
    networks = _meraki_api_request(api_key, "GET", endpoint)
    if networks is not None:
        logging.info(f"Successfully fetched {len(networks)} networks for organization {org_id}.")
    else:
        logging.error(f"Failed to fetch networks for organization {org_id} (API request returned None or error).")
    return networks

def get_network_clients(api_key, network_id, timespan):
    """
    Fetches clients for a specific Meraki network ID seen within a given timespan.
    """
    # This is the only place this log message should appear for a given network_id per call to get_all_relevant_meraki_clients
    logging.info(f"Fetching clients for network ID: {network_id} (timespan: {timespan}s)")
    endpoint = f"/networks/{network_id}/clients"
    params = {"timespan": str(timespan), "perPage": "1000"} # Fetch up to 1000 clients, pagination not implemented for >1000
    clients = _meraki_api_request(api_key, "GET", endpoint, params=params)

    if clients is not None:
        logging.info(f"API returned {len(clients)} clients for network '{network_id}' (before filtering for fixed IPs).")
    else:
        # _meraki_api_request would have logged the error already.
        logging.warning(f"API call for clients in network {network_id} did not return data or failed.")
    return clients


def get_all_relevant_meraki_clients(api_key, config):
    """
    Fetches all Meraki clients that have a fixed IP assignment.

    It queries either all networks in the organization or a specified list of
    network IDs. Clients are filtered to include only those with a
    'fixedIpAssignment' that matches their current IP address.

    Args:
        api_key (str): The Meraki API key.
        config (dict): The application configuration dictionary.

    Returns:
        list: A list of client dictionaries, each representing a client with a
              fixed IP. Returns an empty list if no such clients are found or
              if network fetching fails.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    client_timespan = config["meraki_client_timespan"]

    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: {specified_network_ids if specified_network_ids else 'All'}. Client Timespan: {client_timespan}s.")
    all_clients_map = {} # Using a map keyed by client ID to ensure uniqueness if a client appears in multiple API calls (though unlikely for this use case)

    networks_to_query = []
    if not specified_network_ids:
        logging.info(f"No specific Meraki network IDs provided via {ENV_MERAKI_NETWORK_IDS}. Attempting to fetch all networks for organization ID: {org_id}.")
        organization_networks = get_organization_networks(api_key, org_id) # This is a list of dicts
        if organization_networks is not None: # API call was successful
            if not organization_networks: # Successfully fetched, but the list is empty
                 logging.info(f"Organization {org_id} has no networks according to API. No clients will be fetched.")
                 return [] # Return empty list, no networks to process
            networks_to_query = organization_networks
        else: # API call failed
            logging.warning(f"Failed to fetch networks for organization {org_id}. No clients will be fetched.")
            return [] # Return empty list
    else:
        logging.info(f"Specific Meraki network IDs provided: {specified_network_ids}. Validating and fetching details for these networks.")
        # Fetch all org networks to get names and validate IDs
        organization_networks = get_organization_networks(api_key, org_id)
        if organization_networks is None:
            logging.warning(f"Could not fetch network list for organization {org_id} to validate specified IDs. Proceeding with specified IDs directly, but network names will be 'Unknown'.")
            # Create a list of network-like dicts for consistency
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
            if not networks_to_query: # All specified IDs were invalid
                 logging.warning(f"None of the specified network IDs {specified_network_ids} were found/valid in organization {org_id}. No clients will be fetched.")
                 return []

    if not networks_to_query: # This check covers cases where specified_network_ids was empty and org had no networks, or all specified IDs were invalid.
        logging.info("No networks to query after initial determination. Exiting client search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query)}. Network IDs: {[n['id'] for n in networks_to_query]}")


    for network_idx, network in enumerate(networks_to_query):
        network_id = network["id"] # network is a dict e.g. {'id': 'L_123', 'name': 'My Network'}
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
        if response.text: # Response has content
            try:
                json_response = response.json()
                logging.debug(f"Pi-hole API JSON Response: {json_response}")
                return json_response
            except ValueError: # Not JSON
                logging.debug(f"Pi-hole API response was not JSON: {response.text[:200]}") # Log snippet
                # Handle common non-JSON success cases for add/delete if possible, or treat as success if status is OK.
                if response.ok:
                    if response.text.strip() == '[]': # Empty JSON array often means "no data" for 'get'
                        return {"data": []}
                    # For add/delete, Pi-hole might return simple strings or empty body on success
                    return {"success": True, "message": f"Action likely successful (non-JSON response, HTTP {response.status_code}): {response.text[:100]}"}
                # If not response.ok and not JSON:
                return {"success": False, "message": f"Request failed with status {response.status_code}, non-JSON response: {response.text[:100]}"}
        elif response.ok: # Response has no content but status is OK (e.g., 200 OK with empty body)
             logging.debug("Pi-hole API request successful with empty response body.")
             return {"success": True, "message": "Action successful (empty response)."}
        else: # Response has no content and status is not OK
            return {"success": False, "message": f"Request failed with status {response.status_code} (empty response)."}
    except requests.exceptions.HTTPError as e:
        logging.error(f"Pi-hole API HTTP error: {e} - Response: {e.response.text[:200] if e.response and e.response.text else 'No response text'}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Pi-hole API request failed due to network or request issue: {e}")
    return None # Indicates a failure in the request execution itself


def get_pihole_custom_dns_records(pihole_url, api_key):
    """Fetches and parses custom DNS records from Pi-hole."""
    logging.info("Fetching existing custom DNS records from Pi-hole...")
    params = {"customdns": "", "action": "get"} # Auth is added by _pihole_api_request
    response_data = _pihole_api_request(pihole_url, api_key, params)

    records = {} # Store as {domain: [ip1, ip2]}
    if response_data and isinstance(response_data.get('data'), list):
        # Pi-hole's get customdns returns: {"data": [["domain1.com", "1.2.3.4"], ["domain2.com", "5.6.7.8"]]}
        for item in response_data['data']:
            if isinstance(item, list) and len(item) == 2:
                domain, ip_address = item
                # Ensure domain is stored consistently, e.g., lowercased
                domain_cleaned = domain.strip().lower()
                if domain_cleaned not in records:
                    records[domain_cleaned] = []
                records[domain_cleaned].append(ip_address.strip())
            else:
                logging.warning(f"Unexpected item format in Pi-hole custom DNS data: {item}")
        logging.info(f"Found {len(records)} unique domains with {sum(len(ips) for ips in records.values())} total custom DNS IP mappings in Pi-hole.")
    elif response_data: # Response received, but format is not as expected
        logging.warning(f"Pi-hole custom DNS response format unexpected or 'data' field missing/not a list: {str(response_data)[:200]}")
    else: # _pihole_api_request returned None (request failed)
        logging.error("Failed to fetch custom DNS records from Pi-hole (API request failed or returned None).")
        return None # Critical failure, cannot proceed with sync logic accurately
    return records

def add_dns_record_to_pihole(pihole_url, api_key, domain, ip_address):
    """Adds a single DNS record to Pi-hole."""
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "add", "domain": domain, "ip": ip_address}
    # Pi-hole add API typically returns {"success":true,"message":"Custom DNS entry [...] added"} or similar
    if response and response.get("success") is True: # Check for explicit success field
        logging.info(f"Successfully added DNS record: {domain} -> {ip_address}. Pi-hole message: {response.get('message', 'OK')}")
        return True
    # Fallback for older/different Pi-hole versions or unexpected success responses
    elif response and isinstance(response.get("message"), str) and "added" in response.get("message").lower():
        logging.info(f"Processed add DNS record for: {domain} -> {ip_address} (inferred success). Pi-hole Response: {response.get('message')}")
        return True
    else:
        logging.error(f"Failed to add DNS record {domain} -> {ip_address}. Response: {str(response)[:200]}")
        return False

def delete_dns_record_from_pihole(pihole_url, api_key, domain, ip_address):
    """Deletes a single DNS record from Pi-hole."""
    logging.info(f"Deleting DNS record from Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "delete", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    # Pi-hole delete API typically returns {"success":true,"message":"Custom DNS entry [...] deleted"} or "... does not exist"
    if response and response.get("success") is True:
        logging.info(f"Successfully deleted DNS record: {domain} -> {ip_address}. Pi-hole message: {response.get('message', 'OK')}")
        return True
    # Fallback for older/different Pi-hole versions or messages indicating non-existence (which is a successful deletion outcome)
    elif response and isinstance(response.get("message"), str) and \
         ("deleted" in response.get("message").lower() or "does not exist" in response.get("message").lower()):
        logging.info(f"Processed delete DNS record for: {domain} -> {ip_address} (inferred success/already gone). Pi-hole Response: {response.get('message')}")
        return True
    else:
        logging.error(f"Failed to delete DNS record {domain} -> {ip_address}. Response: {str(response)[:200]}")
        return False

def add_or_update_dns_record_in_pihole(pihole_url, api_key, domain, new_ip, existing_records_cache):
    """
    Adds or updates a DNS record in Pi-hole.
    If the domain exists with a different IP, the old IP(s) are deleted first.
    The `existing_records_cache` is modified by this function upon successful deletions/additions.
    """
    domain_cleaned = domain.strip().lower()
    new_ip_cleaned = new_ip.strip()

    if not domain_cleaned or not new_ip_cleaned: # Basic validation
        logging.warning(f"Skipping invalid record: domain='{domain}', ip='{new_ip}'")
        return False

    if existing_records_cache is None: # Should have been checked by caller, but defensive
        logging.error("Cannot add or update DNS record: existing Pi-hole records cache is None.")
        return False

    # Check if the exact domain-ip pair already exists
    if domain_cleaned in existing_records_cache and new_ip_cleaned in existing_records_cache[domain_cleaned]:
        logging.info(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True

    # If domain exists, but with different IP(s), remove old ones first
    if domain_cleaned in existing_records_cache:
        logging.info(f"Domain {domain_cleaned} found in Pi-hole with IP(s): {existing_records_cache[domain_cleaned]}. Will ensure only {new_ip_cleaned} remains for this domain.")
        for old_ip in list(existing_records_cache[domain_cleaned]): # Iterate over a copy for safe removal from cache
            if old_ip != new_ip_cleaned:
                logging.info(f"Deleting old IP {old_ip} for domain {domain_cleaned} before adding new IP {new_ip_cleaned}.")
                if delete_dns_record_from_pihole(pihole_url, api_key, domain_cleaned, old_ip):
                    if old_ip in existing_records_cache[domain_cleaned]: # Update cache on successful deletion
                        existing_records_cache[domain_cleaned].remove(old_ip)
                    if not existing_records_cache[domain_cleaned]: # If all IPs for this domain were removed
                        del existing_records_cache[domain_cleaned]
                else:
                    logging.error(f"Failed to delete old record {domain_cleaned} -> {old_ip}. Halting update for this domain to avoid potential IP conflicts or orphaned entries.")
                    return False # Stop processing this domain to prevent issues

    # Add the new record
    if add_dns_record_to_pihole(pihole_url, api_key, domain_cleaned, new_ip_cleaned):
        # Update cache on successful addition
        if domain_cleaned not in existing_records_cache:
            existing_records_cache[domain_cleaned] = []
        if new_ip_cleaned not in existing_records_cache[domain_cleaned]: # Avoid duplicates if somehow added again
            existing_records_cache[domain_cleaned].append(new_ip_cleaned)
        return True
    return False

def main():
    """
    Main function to run the Meraki to Pi-hole sync process.
    Loads configuration, fetches Meraki clients, gets Pi-hole records,
    and syncs them.
    """
    # Log application version and commit SHA if available
    app_version = os.getenv(ENV_APP_VERSION, "Not Set")
    commit_sha = os.getenv(ENV_COMMIT_SHA, "Not Set")
    logging.info(f"--- Starting Meraki Pi-hole Sync Script --- Version: {app_version}, Commit: {commit_sha}")

    config = load_app_config_from_env()
    api_key = config["meraki_api_key"]
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config.get("pihole_api_key") # Use .get() as it can be None
    hostname_suffix = config["hostname_suffix"]

    # Fetch relevant Meraki clients with fixed IP assignments
    # This function now iterates through all configured/discovered networks.
    meraki_clients = get_all_relevant_meraki_clients(api_key, config)

    if not meraki_clients:
        # This means no clients with fixed IPs were found across ALL processed networks.
        # Or, network fetching itself failed. get_all_relevant_meraki_clients would have logged details.
        logging.info("No relevant Meraki clients (with fixed IP assignments) found after checking all configured/discovered networks, or network fetching failed. No sync to Pi-hole will be performed for new entries.")
        # Potentially, one might want to proceed to cleanup old entries from Pi-hole even if no new Meraki clients are found.
        # For now, the script exits, matching previous behavior. If cleanup is desired, this logic would change.
        # Consider if existing_records should be fetched and cleanup performed regardless.
        # For this iteration, keeping it simple: no new clients = no changes to Pi-hole.
        logging.info("--- Sync process complete (no clients to sync) ---")
        return

    logging.info(f"Found {len(meraki_clients)} Meraki client(s) with fixed IP assignments to process.")

    # Fetch existing Pi-hole DNS records to compare against
    # This is now a cache that add_or_update_dns_record_in_pihole will modify.
    existing_pihole_records_cache = get_pihole_custom_dns_records(pihole_url, pihole_api_key)
    if existing_pihole_records_cache is None: # This means API call failed critically
        logging.error("Could not fetch existing Pi-hole DNS records. Halting sync to prevent erroneous changes.")
        logging.info("--- Sync process failed (Pi-hole record fetch error) ---")
        return

    successful_syncs = 0
    failed_syncs = 0
    # Sync each relevant Meraki client to Pi-hole
    for client in meraki_clients:
        # Ensure client name is sanitized for use in a hostname.
        # Replace spaces with hyphens, convert to lowercase. Other characters might need handling.
        client_name_sanitized = client['name'].replace(" ", "-").lower()
        # Further sanitization could be added here if client names contain problematic characters for hostnames.

        domain_to_sync = f"{client_name_sanitized}{hostname_suffix}"
        ip_to_sync = client["ip"]

        logging.info(f"Processing Meraki client: Name='{client['name']}', IP='{ip_to_sync}', Target DNS: {domain_to_sync} -> {ip_to_sync}")

        if add_or_update_dns_record_in_pihole(pihole_url, pihole_api_key, domain_to_sync, ip_to_sync, existing_pihole_records_cache):
            successful_syncs += 1
        else:
            failed_syncs +=1
            logging.warning(f"Failed to sync client '{client['name']}' (DNS: {domain_to_sync} -> {ip_to_sync}) to Pi-hole.")

    # TODO (Future Enhancement): Implement cleanup of stale DNS records in Pi-hole.
    # This would involve:
    # 1. Identifying all DNS records in `existing_pihole_records_cache` that match `hostname_suffix`.
    # 2. Comparing them against the list of `meraki_clients` just processed.
    # 3. If a record from Pi-hole (matching the suffix) is NOT in the `meraki_clients` list (i.e., no longer a fixed IP client),
    #    then delete it from Pi-hole.
    # This was mentioned in the README but not implemented in the original script.

    logging.info(f"--- Meraki to Pi-hole Sync Summary ---")
    logging.info(f"Successfully synced/verified {successful_syncs} client(s).")
    if failed_syncs > 0:
        logging.warning(f"Failed to sync {failed_syncs} client(s). Check logs above for details.")
    logging.info(f"Total Meraki clients processed: {len(meraki_clients)}")
    logging.info(f"--- Sync process complete ---")


if __name__ == "__main__":
    # This is the main entry point of the script
    try:
        main()
    except Exception as e:
        logging.critical(f"An unhandled exception occurred in main: {e}", exc_info=True)
        sys.exit(1)
