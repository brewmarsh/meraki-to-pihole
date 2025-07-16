import logging
import requests
from urllib.parse import quote


def authenticate_to_pihole(pihole_url, pihole_api_key):
    """
    Authenticates to the Pi-hole API and returns a session object.
    """
    base_url = pihole_url.rstrip("/")
    if base_url.endswith("/admin"):
        base_url = base_url.replace("/admin", "")
    if base_url.endswith("/api.php"):
        base_url = base_url.replace("/api.php", "")
    auth_url = f"{base_url}/api/auth"

    try:
        # First, try a GET request to see if we already have a valid session
        response = requests.get(auth_url, timeout=10)
        auth_data = response.json()
        session = auth_data.get("session", {})

        if session.get("valid"):
            logging.info("Already authenticated to Pi-hole.")
            if session.get("totp"):
                logging.warning("2FA is enabled on this Pi-hole, but this script does not support it.")
            return session.get("sid"), session.get("csrf")
    except requests.exceptions.RequestException as e:
        logging.warning(f"GET request to /api/auth failed: {e}. Trying POST.")

    # If GET fails or session is not valid, try to authenticate with the API key
    try:
        logging.info(f"Authenticating to Pi-hole at {auth_url}")
        response = requests.post(auth_url, json={"password": pihole_api_key}, timeout=10)
        response.raise_for_status()
        auth_data = response.json()
        session = auth_data.get("session", {})

        if session.get("valid"):
            logging.info("Successfully authenticated to Pi-hole.")
            if session.get("totp"):
                logging.warning("2FA is enabled on this Pi-hole, but this script does not support it.")
            return session.get("sid"), session.get("csrf")
        else:
            logging.error(f"Failed to authenticate to Pi-hole: {session.get('message')}")
            return None, None
    except requests.exceptions.RequestException as e:
        logging.error(f"Authentication to Pi-hole failed: {e}")
        return None, None


def _pihole_api_request(pihole_url, sid, csrf_token, method, path, data=None):
    base_url = pihole_url.rstrip("/")
    if base_url.endswith("/admin"):
        base_url = base_url.replace("/admin", "")
    if base_url.endswith("/api.php"):
        base_url = base_url.replace("/api.php", "")

    url = f"{base_url}{path}"
    headers = {
        "X-CSRF-Token": csrf_token,
    }
    cookies = {"SID": sid}

    try:
        logging.debug(f"Pi-hole API Request: URL={url}, Method={method}, Headers={headers}, Data={data}")
        response = requests.request(method, url, headers=headers, cookies=cookies, json=data, timeout=10)
        logging.debug(f"Pi-hole API Request URL: {response.url}")
        logging.debug(f"Pi-hole API Request Headers: {response.request.headers}")
        logging.debug(f"Pi-hole API Response Status Code: {response.status_code}")
        logging.debug(f"Pi-hole API Response Text: {response.text}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        logging.error(
            f"Pi-hole API HTTP error: {e} - Response: {e.response.text[:200] if e.response and e.response.text else 'No response text'}"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Pi-hole API request failed due to network or request issue: {e}")
    return None


def get_pihole_custom_dns_records(pihole_url, sid, csrf_token):
    """Fetches and parses custom DNS records from Pi-hole."""
    if not sid or not csrf_token:
        logging.error("Cannot fetch Pi-hole DNS records without a valid session.")
        return None

    logging.info("Fetching existing custom DNS records from Pi-hole...")
    response_data = _pihole_api_request(pihole_url, sid, csrf_token, "GET", "/api/domains")

    records = {}  # Store as {domain: [ip1, ip2]}
    if response_data and 'data' in response_data:
        for item in response_data['data']:
            if item['type'] == 'A' or item['type'] == 'AAAA':
                domain = item['domain'].strip().lower()
                ip_address = item['ip'].strip()
                if domain not in records:
                    records[domain] = []
                records[domain].append(ip_address)
        logging.info(
            f"Found {len(records)} unique domains with {sum(len(ips) for ips in records.values())} total custom DNS IP mappings in Pi-hole."
        )
    else:
        logging.error("Failed to fetch custom DNS records from Pi-hole (API request failed or returned None).")
        return None
    return records


def add_dns_record_to_pihole(pihole_url, sid, csrf_token, domain, ip_address):
    """Adds a single DNS record to Pi-hole."""
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    data = {"domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, sid, csrf_token, "POST", "/api/domains", data=data)
    if response and response.get("success"):
        logging.info(f"Successfully added DNS record: {domain} -> {ip_address}.")
        return True
    else:
        logging.error(f"Failed to add DNS record {domain} -> {ip_address}. Response: {response}")
        return False


def delete_dns_record_from_pihole(pihole_url, sid, csrf_token, domain, ip_address):
    """Deletes a single DNS record from Pi-hole."""
    logging.info(f"Deleting DNS record from Pi-hole: {domain} -> {ip_address}")
    data = {"domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, sid, csrf_token, "DELETE", "/api/domains", data=data)
    if response and response.get("success"):
        logging.info(f"Successfully deleted DNS record: {domain} -> {ip_address}.")
        return True
    else:
        logging.error(f"Failed to delete DNS record {domain} -> {ip_address}. Response: {response}")
        return False


def add_or_update_dns_record_in_pihole(pihole_url, sid, csrf_token, domain, new_ip, existing_records_cache):
    """
    Adds or updates a DNS record in Pi-hole.
    If the domain exists with a different IP, the old IP(s) are deleted first.
    The `existing_records_cache` is modified by this function upon successful deletions/additions.
    """
    domain_cleaned = domain.strip().lower()
    new_ip_cleaned = new_ip.strip()

    if not domain_cleaned or not new_ip_cleaned:  # Basic validation
        logging.warning(f"Skipping invalid record: domain='{domain}', ip='{new_ip}'")
        return False

    if existing_records_cache is None:  # Should have been checked by caller, but defensive
        logging.error("Cannot add or update DNS record: existing Pi-hole records cache is None.")
        return False

    # Check if the exact domain-ip pair already exists
    if domain_cleaned in existing_records_cache and new_ip_cleaned in existing_records_cache[domain_cleaned]:
        logging.info(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True

    # If domain exists, but with different IP(s), remove old ones first
    if domain_cleaned in existing_records_cache:
        logging.info(
            f"Domain {domain_cleaned} found in Pi-hole with IP(s): {existing_records_cache[domain_cleaned]}. Will ensure only {new_ip_cleaned} remains for this domain."
        )
        for old_ip in list(existing_records_cache[domain_cleaned]):  # Iterate over a copy for safe removal from cache
            if old_ip != new_ip_cleaned:
                logging.info(
                    f"Deleting old IP {old_ip} for domain {domain_cleaned} before adding new IP {new_ip_cleaned}."
                )
                if delete_dns_record_from_pihole(pihole_url, sid, csrf_token, domain_cleaned, old_ip):
                    if old_ip in existing_records_cache[domain_cleaned]:  # Update cache on successful deletion
                        existing_records_cache[domain_cleaned].remove(old_ip)
                    if not existing_records_cache[domain_cleaned]:  # If all IPs for this domain were removed
                        del existing_records_cache[domain_cleaned]
                else:
                    logging.error(
                        f"Failed to delete old record {domain_cleaned} -> {old_ip}. Halting update for this domain to avoid potential IP conflicts or orphaned entries."
                    )
                    return False  # Stop processing this domain to prevent issues

    # Add the new record
    if add_dns_record_to_pihole(pihole_url, sid, csrf_token, domain_cleaned, new_ip_cleaned):
        # Update cache on successful addition
        if domain_cleaned not in existing_records_cache:
            existing_records_cache[domain_cleaned] = []
        if new_ip_cleaned not in existing_records_cache[domain_cleaned]:  # Avoid duplicates if somehow added again
            existing_records_cache[domain_cleaned].append(new_ip_cleaned)
        return True
    return False
