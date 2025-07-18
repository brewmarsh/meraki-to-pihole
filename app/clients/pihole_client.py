import logging
import requests
from urllib.parse import quote

# --- Globals for Session Caching ---
# These variables will hold the session ID and CSRF token to be reused across sync runs.
# This avoids re-authenticating for every single sync operation if the session is still valid.
_pihole_sid = None
_pihole_csrf_token = None


def authenticate_to_pihole(pihole_url, pihole_api_key):
    """
    Authenticates to the Pi-hole API, reusing a cached session if available and valid.
    If the session is invalid or expired, it attempts to re-authenticate.

    Args:
        pihole_url (str): The base URL of the Pi-hole instance.
        pihole_api_key (str): The API key (password) for Pi-hole.

    Returns:
        tuple: A tuple containing the session ID (str) and CSRF token (str).
               Returns (None, None) if authentication fails.
    """
    global _pihole_sid, _pihole_csrf_token

    base_url = pihole_url.rstrip("/")
    if base_url.endswith(("/admin", "/api.php")):
        base_url = base_url.rsplit("/", 1)[0]
    auth_url = f"{base_url}/api/auth"

    # 1. If we have a cached session, check if it's still valid
    if _pihole_sid and _pihole_csrf_token:
        logging.debug("Found cached Pi-hole session. Verifying...")
        try:
            # A lightweight way to check session validity is to make a simple, authenticated API call.
            # Fetching custom DNS hosts is a good candidate as it's a necessary part of the sync anyway.
            # We pass the cached credentials to the request function.
            verification_response = _pihole_api_request(
                pihole_url, _pihole_sid, _pihole_csrf_token, "GET", "/api/config/dns/hosts"
            )
            # If the request was successful (i.e., didn't return None), the session is valid.
            if verification_response is not None:
                logging.debug("Cached Pi-hole session is still valid.")
                return _pihole_sid, _pihole_csrf_token
            else:
                logging.warning("Cached Pi-hole session appears to be invalid/expired. Attempting to re-authenticate.")
        except requests.exceptions.RequestException as e:
            logging.warning(f"Failed to verify Pi-hole session due to a network error: {e}. Re-authenticating.")

    # 2. If no cached session or if it was invalid, perform full authentication
    logging.info(f"No valid cached session. Authenticating to Pi-hole at {auth_url}")
    try:
        response = requests.post(auth_url, json={"password": pihole_api_key}, timeout=10)
        response.raise_for_status()  # Raises HTTPError for bad responses (4xx or 5xx)
        auth_data = response.json()
        session = auth_data.get("session", {})

        if session.get("valid"):
            _pihole_sid = session.get("sid")
            _pihole_csrf_token = session.get("csrf")
            logging.info("Successfully authenticated to Pi-hole and cached new session.")
            if session.get("totp"):
                logging.warning("2FA is enabled on this Pi-hole; this script does not support it.")
            return _pihole_sid, _pihole_csrf_token
        else:
            # Clear any potentially stale credentials
            _pihole_sid, _pihole_csrf_token = None, None
            logging.error(f"Failed to authenticate to Pi-hole: {session.get('message', 'No error message provided.')}")
            return None, None

    except requests.exceptions.HTTPError as e:
        # Handle specific HTTP errors if needed, e.g., 429 Too Many Requests
        if e.response and e.response.status_code == 429:
            logging.warning("Pi-hole auth API returned HTTP 429 (Too Many Requests). Will retry on next sync cycle.")
        else:
            logging.error(f"Authentication to Pi-hole failed with HTTP error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred during Pi-hole authentication: {e}")

    # Ensure globals are cleared on failure
    _pihole_sid, _pihole_csrf_token = None, None
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
    """
    Fetches and parses all custom DNS records from the Pi-hole instance.

    Args:
        pihole_url (str): The base URL of the Pi-hole instance.
        sid (str): The active session ID for authentication.
        csrf_token (str): The CSRF token for the authenticated session.

    Returns:
        dict: A dictionary of existing custom DNS records, with the domain as the
              key and the IP address as the value (e.g., {'my-device.lan': '192.168.1.10'}).
              Returns None if the request fails or if the session is invalid.
    """
    if not sid or not csrf_token:
        logging.error("Cannot fetch Pi-hole DNS records without a valid session.")
        return None

    logging.debug("Fetching existing custom DNS records from Pi-hole...")
    response_data = _pihole_api_request(pihole_url, sid, csrf_token, "GET", "/api/config/dns/hosts")

    records = {}  # Store as {domain: ip}
    if response_data and "config" in response_data and "dns" in response_data["config"] and "hosts" in response_data["config"]["dns"]:
        for item in response_data["config"]["dns"]["hosts"]:
            parts = item.split()
            if len(parts) == 2:
                ip_address, domain = parts
                records[domain.strip().lower()] = ip_address.strip()
        logging.debug(
            f"Found {len(records)} custom DNS IP mappings in Pi-hole."
        )
    else:
        logging.error("Failed to fetch custom DNS records from Pi-hole (API request failed or returned None).")
        return None
    return records


def add_or_update_dns_record_in_pihole(pihole_url, sid, csrf_token, domain, new_ip, existing_records_cache):
    """
    Adds or updates a DNS record in Pi-hole.
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
    if existing_records_cache.get(domain_cleaned) == new_ip_cleaned:
        logging.debug(f"DNS record {domain_cleaned} -> {new_ip_cleaned} already exists in Pi-hole. No action needed.")
        return True

    # Add or update the record
    path = f"/api/config/dns/hosts/{quote(new_ip_cleaned + ' ' + domain_cleaned)}"
    response = _pihole_api_request(pihole_url, sid, csrf_token, "PUT", path)

    if response and response.get("success"):
        logging.info(f"Successfully added/updated DNS record: {domain_cleaned} -> {new_ip_cleaned}.")
        existing_records_cache[domain_cleaned] = new_ip_cleaned
        return True
    elif response and response.get("error", {}).get("key") == "forbidden":
        logging.error("Pi-hole API returned a 'forbidden' error. Please ensure 'webserver.api.app_sudo' is set to true in your Pi-hole configuration.")
        return False
    else:
        logging.error(f"Failed to add/update DNS record {domain_cleaned} -> {new_ip_cleaned}. Response: {response}")
        return False

def remove_dns_record_from_pihole(pihole_url, sid, csrf_token, domain, ip):
    """
    Removes a custom DNS record from Pi-hole.
    """
    domain_cleaned = domain.strip().lower()
    ip_cleaned = ip.strip()

    if not domain_cleaned or not ip_cleaned:
        logging.warning(f"Skipping invalid record for removal: domain='{domain}', ip='{ip}'")
        return False

    path = f"/api/config/dns/hosts/{quote(ip_cleaned + ' ' + domain_cleaned)}"
    response = _pihole_api_request(pihole_url, sid, csrf_token, "DELETE", path)

    if response and response.get("success"):
        logging.info(f"Successfully removed DNS record: {domain_cleaned} -> {ip_cleaned}.")
        return True
    else:
        logging.error(f"Failed to remove DNS record {domain_cleaned} -> {ip_cleaned}. Response: {response}")
        return False
