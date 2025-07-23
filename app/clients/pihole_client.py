from urllib.parse import quote

import requests
import structlog
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

log = structlog.get_logger()

# --- Globals for Session Caching ---
_pihole_sid = None
_pihole_csrf_token = None
_session = None

def get_requests_session():
    """
    Creates and configures a requests session with a retry mechanism.
    """
    global _session
    if _session:
        return _session

    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS", "PUT", "POST", "DELETE"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session = requests.Session()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    _session = session
    return _session

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

    session = get_requests_session()
    base_url = pihole_url.rstrip("/")
    if base_url.endswith(("/admin", "/api.php")):
        base_url = base_url.rsplit("/", 1)[0]
    auth_url = f"{base_url}/api/auth"

    # 1. If we have a cached session, check if it's still valid
    if _pihole_sid and _pihole_csrf_token:
        log.debug("Found cached Pi-hole session. Verifying...")
        try:
            verification_response = _pihole_api_request(
                pihole_url, _pihole_sid, _pihole_csrf_token, "GET", "/api/config/dns/hosts"
            )
            if verification_response is not None:
                log.debug("Cached Pi-hole session is still valid.")
                return _pihole_sid, _pihole_csrf_token
            else:
                log.warning("Cached Pi-hole session appears to be invalid/expired. Attempting to re-authenticate.")
        except requests.exceptions.RequestException as e:
            log.warning("Failed to verify Pi-hole session due to a network error.", error=e)

    # 2. If no cached session or if it was invalid, perform full authentication
    log.info("No valid cached session. Authenticating to Pi-hole.", auth_url=auth_url)
    try:
        response = session.post(auth_url, json={"password": pihole_api_key}, timeout=10)
        response.raise_for_status()
        auth_data = response.json()
        session_data = auth_data.get("session", {})

        if session_data.get("valid"):
            _pihole_sid = session_data.get("sid")
            _pihole_csrf_token = session_data.get("csrf")
            log.info("Successfully authenticated to Pi-hole and cached new session.")
            if session_data.get("totp"):
                log.warning("2FA is enabled on this Pi-hole; this script does not support it.")
            return _pihole_sid, _pihole_csrf_token
        else:
            _pihole_sid, _pihole_csrf_token = None, None
            log.error("Failed to authenticate to Pi-hole", message=session_data.get('message', 'No error message provided.'))
            return None, None

    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code == 429:
            log.warning("Pi-hole auth API returned HTTP 429 (Too Many Requests). Will retry on next sync cycle.")
        else:
            log.error("Authentication to Pi-hole failed with HTTP error", error=e)
    except Exception as e:
        log.error("An unexpected error occurred during Pi-hole authentication", error=e)

    _pihole_sid, _pihole_csrf_token = None, None
    return None, None


def _pihole_api_request(pihole_url, sid, csrf_token, method, path, data=None):
    session = get_requests_session()
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
        log.debug("Pi-hole API Request", url=url, method=method, headers=headers, data=data)
        response = session.request(method, url, headers=headers, cookies=cookies, json=data, timeout=10)
        log.debug("Pi-hole API Response", url=response.url, headers=response.request.headers, status_code=response.status_code, text=response.text)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.HTTPError as e:
        log.error(
            "Pi-hole API HTTP error",
            error=e,
            response=e.response.text[:200] if e.response and e.response.text else 'No response text'
        )
    except requests.exceptions.RequestException as e:
        log.error("Pi-hole API request failed due to network or request issue", error=e)
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
        log.error("Cannot fetch Pi-hole DNS records without a valid session.")
        return None

    log.debug("Fetching existing custom DNS records from Pi-hole...")
    response_data = _pihole_api_request(pihole_url, sid, csrf_token, "GET", "/api/config/dns/hosts")

    records = {}  # Store as {domain: ip}
    if response_data and "config" in response_data and "dns" in response_data["config"] and "hosts" in response_data["config"]["dns"]:
        for item in response_data["config"]["dns"]["hosts"]:
            parts = item.split()
            if len(parts) == 2:
                ip_address, domain = parts
                records[domain.strip().lower()] = ip_address.strip()
        log.debug("Found custom DNS IP mappings in Pi-hole", count=len(records))
    else:
        log.error("Failed to fetch custom DNS records from Pi-hole (API request failed or returned None).")
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
        log.warning("Skipping invalid record", domain=domain, ip=new_ip)
        return False

    if existing_records_cache is None:  # Should have been checked by caller, but defensive
        log.error("Cannot add or update DNS record: existing Pi-hole records cache is None.")
        return False

    # Check if the exact domain-ip pair already exists
    if existing_records_cache.get(domain_cleaned) == new_ip_cleaned:
        log.debug("DNS record already exists in Pi-hole. No action needed.", domain=domain_cleaned, ip=new_ip_cleaned)
        return True

    # Add or update the record
    path = f"/api/config/dns/hosts/{quote(new_ip_cleaned + ' ' + domain_cleaned)}"
    response = _pihole_api_request(pihole_url, sid, csrf_token, "PUT", path)

    if response and response.get("success"):
        log.info("Successfully added/updated DNS record", domain=domain_cleaned, ip=new_ip_cleaned)
        existing_records_cache[domain_cleaned] = new_ip_cleaned
        return True
    elif response and response.get("error", {}).get("key") == "forbidden":
        log.error("Pi-hole API returned a 'forbidden' error. Please ensure 'webserver.api.app_sudo' is set to true in your Pi-hole configuration.")
        return False
    else:
        log.error("Failed to add/update DNS record", domain=domain_cleaned, ip=new_ip_cleaned, response=response)
        return False

def remove_dns_record_from_pihole(pihole_url, sid, csrf_token, domain, ip):
    """
    Removes a custom DNS record from Pi-hole.
    """
    domain_cleaned = domain.strip().lower()
    ip_cleaned = ip.strip()

    if not domain_cleaned or not ip_cleaned:
        log.warning("Skipping invalid record for removal", domain=domain, ip=ip)
        return False

    path = f"/api/config/dns/hosts/{quote(ip_cleaned + ' ' + domain_cleaned)}"
    response = _pihole_api_request(pihole_url, sid, csrf_token, "DELETE", path)

    if response and response.get("success"):
        log.info("Successfully removed DNS record", domain=domain_cleaned, ip=ip_cleaned)
        return True
    else:
        log.error("Failed to remove DNS record", domain=domain_cleaned, ip=ip_cleaned, response=response)
        return False
