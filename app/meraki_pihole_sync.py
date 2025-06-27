# Python script to sync Meraki client IPs to Pi-hole
import os
import sys
# import configparser # No longer needed
import requests
import logging
import time
# import argparse # No longer needed, config path removed

# Configure logging
LOG_FILE_PATH = "/app/logs/sync.log"
# Ensure the directory exists (though Dockerfile should create /app/logs)
os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE_PATH),
        logging.StreamHandler(sys.stdout) # Keep logging to stdout as well for `docker logs`
    ]
)

# Environment Variable Names
ENV_MERAKI_API_KEY = "MERAKI_API_KEY"
ENV_MERAKI_ORG_ID = "MERAKI_ORG_ID"
ENV_MERAKI_NETWORK_IDS = "MERAKI_NETWORK_IDS" # Comma-separated string
ENV_PIHOLE_API_URL = "PIHOLE_API_URL"
ENV_PIHOLE_API_KEY = "PIHOLE_API_KEY"
ENV_HOSTNAME_SUFFIX = "HOSTNAME_SUFFIX"
# ENV_SYNC_INTERVAL_SECONDS = "SYNC_INTERVAL_SECONDS" # Not used by cron runner

def load_app_config_from_env():
    """Loads all application configuration from environment variables."""
    config = {}
    missing_vars = []

    # Mandatory variables
    config["meraki_api_key"] = os.getenv(ENV_MERAKI_API_KEY)
    config["meraki_org_id"] = os.getenv(ENV_MERAKI_ORG_ID)
    config["pihole_api_url"] = os.getenv(ENV_PIHOLE_API_URL)
    config["hostname_suffix"] = os.getenv(ENV_HOSTNAME_SUFFIX)

    if not config["meraki_api_key"]: missing_vars.append(ENV_MERAKI_API_KEY)
    if not config["meraki_org_id"]: missing_vars.append(ENV_MERAKI_ORG_ID)
    if not config["pihole_api_url"]: missing_vars.append(ENV_PIHOLE_API_URL)
    if not config["hostname_suffix"]: missing_vars.append(ENV_HOSTNAME_SUFFIX) # Making suffix mandatory

    if missing_vars:
        logging.error(f"Missing mandatory environment variables: {', '.join(missing_vars)}")
        sys.exit(1)

    # Optional variables
    config["pihole_api_key"] = os.getenv(ENV_PIHOLE_API_KEY) # Can be None if Pi-hole not passworded

    meraki_network_ids_str = os.getenv(ENV_MERAKI_NETWORK_IDS, '')
    config["meraki_network_ids"] = [nid.strip() for nid in meraki_network_ids_str.split(',') if nid.strip()]

    # Validate placeholder values (simple check)
    if config["meraki_org_id"] == "YOUR_MERAKI_ORGANIZATION_ID":
        logging.error(f"Placeholder value detected for {ENV_MERAKI_ORG_ID}. Please set a valid Organization ID.")
        sys.exit(1)
    if config["pihole_api_url"] == "YOUR_PIHOLE_API_URL" or config["pihole_api_url"] == "http://your_pihole_ip_or_hostname/admin/api.php":
        logging.error(f"Placeholder value detected for {ENV_PIHOLE_API_URL}. Please set a valid Pi-hole API URL.")
        sys.exit(1)
    if config["hostname_suffix"] == ".local" or config["hostname_suffix"] == ".yourdomain.local" or config["hostname_suffix"] == ".yourcustomdomain.local": # Example placeholders
        logging.warning(f"Possible example value detected for {ENV_HOSTNAME_SUFFIX} ('{config['hostname_suffix']}'). Ensure this is your intended suffix.")


    logging.info("Successfully loaded configuration from environment variables.")
    return config

def main():
    app_version = os.getenv("APP_VERSION", "unknown")
    commit_sha = os.getenv("COMMIT_SHA", "unknown")

    logging.info(f"Starting Meraki Pi-hole Sync Script - Version: {app_version}, Commit: {commit_sha}")

    app_config = load_app_config_from_env()
    meraki_api_key = app_config["meraki_api_key"]

    logging.info(f"Configuration loaded: Meraki Org ID {app_config['meraki_org_id']}, "
                 f"Pi-hole URL {app_config['pihole_api_url']}, "
                 f"Hostname Suffix: {app_config['hostname_suffix']}, "
                 f"Networks to sync: {app_config['meraki_network_ids'] if app_config['meraki_network_ids'] else 'All in Org'}")

    meraki_clients = get_all_relevant_meraki_clients(meraki_api_key, app_config)

    if not meraki_clients:
        logging.info("No relevant Meraki clients with fixed IPs found or an error occurred during client fetching. Sync process complete (no changes to Pi-hole based on Meraki data).")
        return

    logging.info(f"Successfully fetched {len(meraki_clients)} Meraki clients with fixed IPs to process for Pi-hole.")

    pihole_url = app_config["pihole_api_url"]
    pihole_key = app_config["pihole_api_key"]
    hostname_suffix = app_config["hostname_suffix"]

    existing_pihole_records = get_pihole_custom_dns_records(pihole_url, pihole_key)
    logging.info(f"Found {len(existing_pihole_records)} existing custom domains in Pi-hole.")

    processed_hostnames = set()

    for client in meraki_clients:
        client_name = client.get("name")
        client_ip = client.get("ip")

        if not client_name or not client_ip:
            logging.debug(f"Skipping Meraki client due to missing name or IP: {client}")
            continue

        cleaned_client_name = "".join(c if c.isalnum() or c == '-' else '-' for c in client_name.strip())
        if not cleaned_client_name:
            logging.warning(f"Client name '{client_name}' (Meraki ID: {client.get('meraki_client_id')}) resulted in empty string after cleaning. Skipping.")
            continue

        if hostname_suffix and not hostname_suffix.startswith('.'):
            full_hostname = f"{cleaned_client_name}.{hostname_suffix.lstrip('.')}"
        elif hostname_suffix:
            full_hostname = f"{cleaned_client_name}{hostname_suffix}"
        else:
            full_hostname = cleaned_client_name

        full_hostname = full_hostname.lower()

        logging.info(f"Processing Meraki client: '{client_name}' (IP: {client_ip}, Meraki ID: {client.get('meraki_client_id')}) -> Target Pi-hole DNS: {full_hostname}")

        add_or_update_dns_record_in_pihole(pihole_url, pihole_key, full_hostname, client_ip, existing_pihole_records)
        processed_hostnames.add(full_hostname)

    logging.info("Starting stale DNS record cleanup process...")
    if hostname_suffix:
        managed_domain_suffix = hostname_suffix.lower()
        if not managed_domain_suffix.startswith('.'):
            managed_domain_suffix = '.' + managed_domain_suffix

        for domain, ips in existing_pihole_records.items():
            if domain.endswith(managed_domain_suffix) and domain not in processed_hostnames:
                logging.info(f"Found stale DNS record in Pi-hole: {domain} (managed suffix '{managed_domain_suffix}'). It was not in the latest Meraki fixed IP client list.")
                for ip_addr in ips:
                    logging.info(f"Deleting stale record: {domain} -> {ip_addr}")
                    delete_dns_record_from_pihole(pihole_url, pihole_key, domain, ip_addr)
            elif not domain.endswith(managed_domain_suffix):
                logging.debug(f"Skipping record {domain} from stale check as it does not match suffix '{managed_domain_suffix}'.")

    logging.info("Meraki to Pi-hole DNS sync process completed.")


MERAKI_API_BASE_URL = "https://api.meraki.com/api/v1"

def _meraki_api_request(api_key, method, endpoint, params=None, data=None):
    headers = {
        "X-Cisco-Meraki-API-Key": api_key,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    url = f"{MERAKI_API_BASE_URL}{endpoint}"
    try:
        response = requests.request(method, url, headers=headers, params=params, json=data, timeout=20)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logging.error(f"Meraki API HTTP error for {method} {url}: {e} - Response: {e.response.text if e.response else 'No response object'}")
    except requests.exceptions.RequestException as e:
        logging.error(f"Meraki API request failed for {method} {url}: {e}")
    return None

def get_organization_networks(api_key, org_id):
    logging.info(f"Fetching networks for organization ID: {org_id}")
    endpoint = f"/organizations/{org_id}/networks"
    networks = _meraki_api_request(api_key, "GET", endpoint)
    if networks is not None: # Could be an empty list if org has no networks
        logging.info(f"Found {len(networks)} networks in organization {org_id}.")
    # If None, error was already logged by _meraki_api_request
    return networks

def get_network_clients(api_key, network_id, timespan=86400):
    logging.info(f"Fetching clients for network ID: {network_id} (timespan: {timespan}s)")
    endpoint = f"/networks/{network_id}/clients"
    params = {"timespan": timespan, "perPage": 1000}
    clients = _meraki_api_request(api_key, "GET", endpoint, params=params)
    if clients is not None: # Could be an empty list
        logging.info(f"API returned {len(clients)} clients for network {network_id}.")
    # If None, error was already logged
    return clients


def get_all_relevant_meraki_clients(api_key, config):
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: '{specified_network_ids}'")
    all_clients_map = {}

    networks_to_query = []
    if not specified_network_ids:
        logging.info(f"No specific Meraki network IDs provided in {ENV_MERAKI_NETWORK_IDS}. Attempting to fetch all networks for organization ID: {org_id}.")
        organization_networks = get_organization_networks(api_key, org_id) # API Call 1
        if organization_networks is not None: # Check for None (API error) vs empty list (no networks)
            if organization_networks: # Not an empty list
                networks_to_query = organization_networks
            else: # API returned empty list
                 logging.info(f"Organization {org_id} has no networks according to API. No clients will be fetched.")
                 return []
        else: # API call failed
            logging.warning(f"Failed to fetch networks for organization {org_id}. No clients will be fetched.")
            return []
    else:
        logging.info(f"Specific Meraki network IDs provided: {specified_network_ids}. Validating and fetching details for these networks.")
        organization_networks = get_organization_networks(api_key, org_id)
        if not organization_networks: # Covers None (API error) or empty list (no networks in org to validate against)
            logging.warning(f"Could not fetch any networks for organization {org_id} to validate specified IDs. Proceeding with specified IDs directly, but network names will be 'Unknown'.")
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
                 logging.warning(f"None of the specified network IDs {specified_network_ids} were found in organization {org_id}. No clients will be fetched.")
                 return []

    if not networks_to_query:
        logging.info("No networks to query after initial determination (e.g., all specified IDs were invalid or org has no networks). Exiting client search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query)}. Network IDs: {[n['id'] for n in networks_to_query]}")


    for network_idx, network in enumerate(networks_to_query):
        network_id = network["id"]
        network_name = network.get("name", "UnknownNetwork")
        logging.info(f"Starting processing for network {network_idx + 1}/{len(networks_to_query)}: {network_name} (ID: {network_id})")

        clients_in_network = get_network_clients(api_key, network_id) # API Call per network

        if clients_in_network is not None: # Check for API error (None) vs empty list
            if clients_in_network: # Not an empty list
                logging.debug(f"Found {len(clients_in_network)} clients in network {network_name} (ID: {network_id}) from API call to process.")
                for client in clients_in_network:
                    client_name = client.get('description') or client.get('dhcpHostname')
                    client_ip = client.get('ip')
                    client_id = client.get('id')
                    fixed_ip_assignment = client.get('fixedIpAssignment')

                    if client_name and client_ip and client_id:
                        is_fixed_ip_client = False
                        if fixed_ip_assignment and isinstance(fixed_ip_assignment, dict):
                            assigned_ip = fixed_ip_assignment.get('ip')
                            if assigned_ip and assigned_ip == client_ip:
                                is_fixed_ip_client = True
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) has a matching fixed IP assignment: {assigned_ip} in network '{network_name}'.")
                            elif assigned_ip:
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' has a fixed IP assignment ({assigned_ip}) that does NOT match its current IP ({client_ip}). Skipping.")
                            else:
                                logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' has a fixedIpAssignment object but no IP in it. Skipping.")
                        else:
                            logging.debug(f"Client '{client_name}' (ID: {client_id}) in network '{network_name}' does not have a valid fixedIpAssignment. Skipping.")

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
                        logging.debug(f"Skipping client (Meraki ID: {client.get('id')}, MAC: {client.get('mac')}) in network '{network_name}' due to missing name, current IP, or client ID.")
            else: # API returned empty list for clients
                logging.info(f"No clients reported by API for network {network_name} (ID: {network_id}).")
        else: # API call to get_network_clients failed (returned None)
            logging.warning(f"Failed to fetch clients for network {network_name} (ID: {network_id}). Skipping this network.")

        logging.info(f"Finished processing for network {network_idx + 1}/{len(networks_to_query)}: {network_name} (ID: {network_id})")

    return list(all_clients_map.values())

# --- Pi-hole API Functions ---

def _pihole_api_request(pihole_url, api_key, params):
    if not pihole_url.endswith("api.php"):
        # This warning was a bit noisy if URL is correct but just missing /api.php
        # logging.warning(f"Pi-hole URL {pihole_url} does not end with api.php. Appending it.")
        pihole_url = pihole_url.rstrip('/') + "/api.php"

    if api_key:
        params['auth'] = api_key

    try:
        response = requests.get(pihole_url, params=params, timeout=10)
        response.raise_for_status()
        if response.text:
            try:
                return response.json()
            except ValueError:
                logging.debug(f"Pi-hole API response was not JSON: {response.text}")
                if response.ok:
                    return {"success": True, "message": "Action likely successful (non-JSON response)."}
                return {"success": False, "message": f"Request failed, non-JSON response: {response.text}"}
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
    if response_data and 'data' in response_data:
        for domain, ip_address in response_data['data']:
            if domain not in records:
                records[domain] = []
            records[domain].append(ip_address)
        logging.info(f"Found {len(records)} unique domains with custom DNS records in Pi-hole.")
    elif response_data:
        logging.warning(f"Pi-hole custom DNS response format unexpected or empty: {response_data}")
    else:
        logging.error("Failed to fetch custom DNS records from Pi-hole or API error.")
    return records

def add_dns_record_to_pihole(pihole_url, api_key, domain, ip_address):
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "add", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and response.get("success", False):
        logging.info(f"Successfully added DNS record: {domain} -> {ip_address}. Message: {response.get('message', 'OK')}")
        return True
    else:
        logging.error(f"Failed to add DNS record {domain} -> {ip_address}. Response: {response}")
        return False

def delete_dns_record_from_pihole(pihole_url, api_key, domain, ip_address):
    logging.info(f"Deleting DNS record from Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "delete", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    if response and response.get("success", False):
        logging.info(f"Successfully deleted DNS record: {domain} -> {ip_address}. Message: {response.get('message', 'OK')}")
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

    if domain_cleaned in existing_records and new_ip_cleaned in existing_records[domain_cleaned]:
        logging.info(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True

    if domain_cleaned in existing_records:
        for old_ip in existing_records[domain_cleaned]:
            if old_ip != new_ip_cleaned:
                logging.info(f"Found old IP {old_ip} for domain {domain_cleaned}. Deleting it before adding new IP {new_ip_cleaned}.")
                delete_dns_record_from_pihole(pihole_url, api_key, domain_cleaned, old_ip)

    return add_dns_record_to_pihole(pihole_url, api_key, domain_cleaned, new_ip_cleaned)


if __name__ == "__main__":
    main()
