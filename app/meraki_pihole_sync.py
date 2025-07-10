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
import os
import sys
import requests # Still needed for Pi-hole calls
import logging
import time
import meraki # Import the Meraki SDK

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

# Removed _meraki_api_request, get_organization_networks, get_network_clients
# as these will be replaced by Meraki SDK calls.

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki clients that have a fixed IP assignment.

    It queries either all networks in the organization or a specified list of
    network IDs. Clients are filtered to include only those with a
    'fixedIpAssignment' that matches their current IP address.

    Args:
        dashboard (meraki.DashboardAPI): Initialized Meraki Dashboard API client.
        config (dict): The application configuration dictionary.

    Returns:
        list: A list of client dictionaries, each representing a client with a
              fixed IP matching its current IP. Returns an empty list if no such
              clients are found or if network fetching fails.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    client_timespan = config["meraki_client_timespan"] # In seconds

    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: {specified_network_ids if specified_network_ids else 'All'}. Client Timespan: {client_timespan}s.")
    all_clients_map = {}

    networks_to_query_details = []
    try:
        if not specified_network_ids:
            logging.info(f"No specific Meraki network IDs provided. Fetching all networks for organization ID: {org_id}.")
            # total_pages='all' should handle pagination for networks if there are many.
            organization_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
            if not organization_networks:
                logging.info(f"Organization {org_id} has no networks according to API. No clients will be fetched.")
                return []
            networks_to_query_details = organization_networks
        else:
            logging.info(f"Specific Meraki network IDs provided: {specified_network_ids}. Validating and fetching details for these networks.")
            # Fetch all org networks to get names and validate IDs, then filter.
            all_org_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
            if not all_org_networks: # Should not happen if IDs are specified, but defensive.
                logging.warning(f"Could not fetch network list for organization {org_id} to validate specified IDs. Proceeding with specified IDs directly, but network names will be 'Unknown'.")
                networks_to_query_details = [{"id": nid, "name": f"Unknown (ID: {nid})"} for nid in specified_network_ids]
            else:
                name_map = {net['id']: net['name'] for net in all_org_networks}
                for nid_spec in specified_network_ids:
                    if nid_spec in name_map:
                        networks_to_query_details.append({"id": nid_spec, "name": name_map[nid_spec]})
                    else:
                        logging.warning(f"Specified network ID {nid_spec} not found in organization {org_id}. It will be skipped.")
                if not networks_to_query_details:
                    logging.warning(f"None of the specified network IDs {specified_network_ids} were found/valid in organization {org_id}. No clients will be fetched.")
                    return []
    except meraki.exceptions.APIError as e:
        logging.error(f"Meraki API error while fetching networks for organization {org_id}: {e}")
        return [] # Critical error, cannot proceed

    if not networks_to_query_details:
        logging.info("No networks to query after initial determination. Exiting client search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query_details)}. Network IDs: {[n['id'] for n in networks_to_query_details]}")

    for network_idx, network_detail in enumerate(networks_to_query_details):
        network_id = network_detail["id"]
        network_name = network_detail.get("name", f"ID-{network_id}")
        logging.info(f"--- Processing network {network_idx + 1}/{len(networks_to_query_details)}: '{network_name}' (ID: {network_id}) ---")

        mac_to_reserved_ip_map = {}
        try:
            # Attempt to get DHCP subnet configurations, which should include fixed IP assignments.
            # This endpoint is typically for networks with an MX appliance.
            # Using a more general approach: getNetworkApplianceDhcpSubnets
            # This might return a list of subnets for the network.
            # Each subnet object could have 'fixedIpAssignments' or 'reservedIpRanges'.
            # The SDK documentation for getNetworkApplianceDhcpSubnets indicates it returns a list of subnet DHCP settings.
            # Each item in this list can have a "fixedIpAssignments" key, which is a list of assignment objects.
            # Each assignment object has "mac", "name", "ip".
            logging.debug(f"Fetching DHCP subnet info for network {network_id} to find fixed IP assignments.")
            # This call might fail if the network is not an Appliance network or has no DHCP settings.
            # The SDK might return an empty list or raise an APIError (e.g., 404 if endpoint not applicable).
            appliance_dhcp_subnets = []
            try:
                # Check if network is an appliance network first.
                # This might be an over-optimization; let's try fetching directly and handle errors.
                # network_info = dashboard.networks.getNetwork(network_id)
                # if 'appliance' in network_info.get('productTypes', []):
                appliance_dhcp_subnets = dashboard.appliance.get_network_appliance_dhcp_subnets(networkId=network_id)
                # else:
                #    logging.info(f"Network {network_name} (ID: {network_id}) is not an Appliance network or does not have DHCP subnets configured via API. Skipping DHCP reservation check for it.")

            except meraki.exceptions.APIError as e:
                if e.status == 404 and "The requested URL was not found on the server." in str(e.message): # More specific check
                    logging.info(f"No DHCP subnet/VLAN configuration found via API for network {network_name} (ID: {network_id}) (Endpoint not found - likely not an MX network or no DHCP configured). Will rely on client.fixedIp if available.")
                else:
                    logging.warning(f"Could not retrieve DHCP subnet/VLANs info for network {network_name} (ID: {network_id}) to check reservations: {e}. Will rely on client.fixedIp if available.")

            if appliance_dhcp_subnets: # Could be a list of subnets/VLANs
                for subnet_info in appliance_dhcp_subnets: # Iterate through each subnet/VLAN's DHCP settings
                    if subnet_info and 'fixedIpAssignments' in subnet_info:
                        for mac, assignment_details in subnet_info['fixedIpAssignments'].items(): # It's a dict keyed by MAC
                            # assignment_details is like: {"ip": "192.168.1.10", "name": "mydevice"}
                            if mac and assignment_details.get('ip'):
                                mac_to_reserved_ip_map[mac.lower()] = assignment_details['ip']
                                logging.debug(f"Found configured DHCP reservation in network {network_id}: MAC {mac.lower()} -> IP {assignment_details['ip']} (Name: {assignment_details.get('name', 'N/A')})")
                logging.info(f"Found {len(mac_to_reserved_ip_map)} DHCP fixed IP reservations in network {network_name} (ID: {network_id}).")


            # Fetch clients for the network
            clients_in_network = dashboard.networks.getNetworkClients(networkId=network_id, timespan=client_timespan, perPage=1000, total_pages='all')

            if clients_in_network:
                logging.info(f"SDK returned {len(clients_in_network)} clients for network '{network_name}' (ID: {network_id}).")
                logging.debug(f"Filtering {len(clients_in_network)} clients from network '{network_name}'...")
                for client in clients_in_network:
                    # SDK returns client objects as dictionaries.
                    # Attributes to check: 'description', 'dhcpHostname', 'ip', 'id', and 'fixedIp' (for reserved IP) or 'ip' for current.
                    # The key: is the client's *configured* "Fixed IP" (often called DHCP reservation in UI) the same as its *current* `ip`?
                    # The Meraki client object from getNetworkClients has:
                    # - `ip`: Current IP address of the client.
                    # - `dhcpHostname`: The hostname of a client as reported by DHCP.
                    # - `description`: The description of the client.
                    # - `fixedIp`: The fixed IP address of the client (if assigned). IMPORTANT: This is the *configured* fixed IP.
                    # - `id`: The Meraki client ID.

                    client_name_desc = client.get('description')
                    client_name_dhcp = client.get('dhcpHostname')
                    client_name = client_name_desc or client_name_dhcp

                    current_ip = client.get('ip')
                    client_id = client.get('id')
                    client_mac = client.get('mac')

                    # Try to get configured fixed IP from DHCP reservations map first
                    configured_fixed_ip = None
                    if client_mac:
                        configured_fixed_ip = mac_to_reserved_ip_map.get(client_mac.lower())
                        if configured_fixed_ip:
                            logging.debug(f"Client '{client_name}' (MAC: {client_mac.lower()}) found in DHCP reservations with IP {configured_fixed_ip}.")

                    # Fallback or alternative: check client.get('fixedIp') if not found in DHCP reservations
                    # This field might be populated for non-DHCP fixed IP assignments or by different Meraki device types.
                    if not configured_fixed_ip and client.get('fixedIp'):
                        configured_fixed_ip_from_client_obj = client.get('fixedIp')
                        logging.debug(f"Client '{client_name}' (MAC: {client_mac.lower()}) not in DHCP reservations map, but client object has fixedIp: {configured_fixed_ip_from_client_obj}. Using this.")
                        configured_fixed_ip = configured_fixed_ip_from_client_obj
                        # No, if it's not in the authoritative reservation list, we should not use client.fixedIp as it was unreliable.
                        # We only trust the DHCP reservation list now.
                        # However, if the reservation list is empty (e.g. non-MX network), client.fixedIp is our only hope.
                        # Let's refine: if mac_to_reserved_ip_map is populated, it's the source of truth.
                        # If mac_to_reserved_ip_map is empty (e.g. API call failed or no reservations), then we can try client.get('fixedIp') as a fallback.
                        if mac_to_reserved_ip_map: # If we have an authoritative list, ignore client.fixedIp
                             configured_fixed_ip = None # Ensure we only use the map if it exists
                        # If map is empty, then client.get('fixedIp') is the only info we might have.
                        # This logic is getting complex. Let's simplify:
                        # Priority 1: DHCP reservations.
                        # Priority 2 (fallback if no DHCP reservations found for the *entire network*): client.get('fixedIp').

                    if not configured_fixed_ip and not mac_to_reserved_ip_map: # If no DHCP reservations were found for the network at all
                        configured_fixed_ip = client.get('fixedIp') # Fallback to the client's reported fixedIp
                        if configured_fixed_ip:
                             logging.debug(f"No DHCP reservations found for network {network_name}. Client '{client_name}' (MAC: {client_mac.lower()}) has fixedIp attribute: {configured_fixed_ip}. Using this as potential configured IP.")


                    if client_name and current_ip and client_id:
                        if configured_fixed_ip and configured_fixed_ip == current_ip:
                            all_clients_map[client_id] = {
                                "name": client_name, "ip": current_ip,
                                "network_id": network_id, "network_name": network_name,
                                "meraki_client_id": client_id
                            }
                            logging.info(f"Relevant client: '{client_name}' (IP: {current_ip}, Meraki ID: {client_id}) in network '{network_name}'. Configured Fixed IP ({configured_fixed_ip}) matches current IP. Will be processed.")
                        elif configured_fixed_ip:
                            logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' has configured Fixed IP ({configured_fixed_ip}) but current IP ({current_ip}) differs. Skipping.")
                        else:
                            logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' does not have a usable Fixed IP assignment (Configured: '{configured_fixed_ip}', MAC in map: {bool(client_mac and client_mac.lower() in mac_to_reserved_ip_map)}). Skipping.")
                    else:
                        logging.debug(f"Skipping client (Meraki ID: {client.get('id')}, MAC: {client.get('mac')}) in network '{network_name}' due to missing name, current IP, or client ID.")
            else:
                logging.info(f"No clients reported by SDK for network {network_name} (ID: {network_id}).")

        except meraki.exceptions.APIError as e:
            logging.error(f"Meraki API error during processing of network {network_name} (ID: {network_id}): {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing network {network_name} (ID: {network_id}): {e}", exc_info=True)

        logging.info(f"--- Finished processing network {network_idx + 1}/{len(networks_to_query_details)}: {network_name} (ID: {network_id}) ---")

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
    meraki_api_key = config["meraki_api_key"] # Renamed for clarity with SDK
    pihole_url = config["pihole_api_url"]
    pihole_api_key = config.get("pihole_api_key") # Use .get() as it can be None
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
        output_log=False, # We handle our own logging to console/file via script's logger
        print_console=False, # Explicitly false
        suppress_logging=True # Suppress SDK's own logger; we will log API calls if needed at debug level
    )


    # Fetch relevant Meraki clients with fixed IP assignments using the SDK
    meraki_clients = get_all_relevant_meraki_clients(dashboard, config)

    if not meraki_clients:
        # This means no clients with fixed IPs (matching current IP) were found across ALL processed networks.
        # Or, network fetching itself failed. get_all_relevant_meraki_clients would have logged details.
        logging.info("No relevant Meraki clients (with fixed IP assignments) were found after checking all configured/discovered networks, or network/client fetching failed.")

        # Check current log level. logging.getLogger().getEffectiveLevel() gives the numeric level.
        # logging.DEBUG is 10, logging.INFO is 20.
        if logging.getLogger().getEffectiveLevel() > logging.DEBUG:
            logging.info(f"Consider setting LOG_LEVEL=DEBUG in your .env file and restarting to get detailed client processing information if you expected clients to be found.")

        logging.info("No new DNS entries will be synced to Pi-hole.")
        # Potentially, one might want to proceed to cleanup old entries from Pi-hole even if no new Meraki clients are found.
        # For now, the script exits, matching previous behavior. If cleanup is desired, this logic would change.
        # For this iteration, keeping it simple: no new clients = no changes to Pi-hole based on Meraki data.
        logging.info("--- Sync process complete (no Meraki clients to sync to Pi-hole) ---")
        return

    logging.info(f"Found {len(meraki_clients)} Meraki client(s) with fixed IP assignments to process for Pi-hole sync.")

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
