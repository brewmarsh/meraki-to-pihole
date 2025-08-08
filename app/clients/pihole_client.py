from urllib.parse import quote

import requests
import structlog
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

log = structlog.get_logger()


class PiholeClient:
    def __init__(self, pihole_url, pihole_api_key):
        self.pihole_url = pihole_url.rstrip("/")
        if self.pihole_url.endswith(("/admin", "/api.php")):
            self.pihole_url = self.pihole_url.rsplit("/", 1)[0]
        self.pihole_api_key = pihole_api_key
        self.session = self._get_requests_session()
        self.sid = None
        self.csrf_token = None
        self.authenticate()

    def _get_requests_session(self):
        retry_strategy = Retry(
            total=4,
            connect=4,
            read=4,
            redirect=4,
            other=4,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "PUT", "POST", "DELETE"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session = requests.Session()
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def authenticate(self):
        auth_url = f"{self.pihole_url}/api/auth"
        if self.sid and self.csrf_token:
            log.debug("Found cached Pi-hole session. Verifying...")
            try:
                if self.get_custom_dns_records() is not None:
                    log.debug("Cached Pi-hole session is still valid.")
                    return
            except requests.exceptions.RequestException as e:
                log.warning("Failed to verify Pi-hole session due to a network error.", error=e)

        log.info("No valid cached session. Authenticating to Pi-hole.", auth_url=auth_url)
        try:
            response = self.session.post(auth_url, json={"password": self.pihole_api_key}, timeout=10)
            response.raise_for_status()
            auth_data = response.json()
            session_data = auth_data.get("session", {})

            if session_data.get("valid"):
                self.sid = session_data.get("sid")
                self.csrf_token = session_data.get("csrf")
                log.info("Successfully authenticated to Pi-hole and cached new session.")
                if session_data.get("totp"):
                    log.warning("2FA is enabled on this Pi-hole; this script does not support it.")
            else:
                self.sid, self.csrf_token = None, None
                log.error("Failed to authenticate to Pi-hole", message=session_data.get('message', 'No error message provided.'))

        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 429:
                log.warning("Pi-hole auth API returned HTTP 429 (Too Many Requests). Will retry on next sync cycle.")
            else:
                log.error("Authentication to Pi-hole failed with HTTP error", error=e)
        except Exception as e:
            log.error("An unexpected error occurred during Pi-hole authentication", error=e)
            self.sid, self.csrf_token = None, None

    def _api_request(self, method, path, data=None):
        if not self.sid or not self.csrf_token:
            self.authenticate()
            if not self.sid or not self.csrf_token:
                log.error("Cannot make API request without a valid session.")
                return None

        url = f"{self.pihole_url}{path}"
        headers = {"X-CSRF-Token": self.csrf_token}
        cookies = {"SID": self.sid}

        try:
            log.debug("Pi-hole API Request", url=url, method=method, headers=headers, data=data)
            response = self.session.request(method, url, headers=headers, cookies=cookies, json=data, timeout=10)
            log.debug("Pi-hole API Response", url=response.url, headers=response.request.headers, status_code=response.status_code, text=response.text)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                log.warning("Pi-hole session appears to be invalid/expired. Attempting to re-authenticate.")
                self.sid, self.csrf_token = None, None
                return self._api_request(method, path, data)
            log.error(
                "Pi-hole API HTTP error",
                error=e,
                response=e.response.text[:200] if e.response and e.response.text else 'No response text'
            )
        except requests.exceptions.RequestException as e:
            log.error("Pi-hole API request failed due to network or request issue", error=e)
        return None

    def get_custom_dns_records(self):
        log.debug("Fetching existing custom DNS records from Pi-hole...")
        response_data = self._api_request("GET", "/api/config/dns/hosts")

        records = {}
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

    def add_or_update_dns_record(self, domain, new_ip):
        domain_cleaned = domain.strip().lower()
        new_ip_cleaned = new_ip.strip()

        if not domain_cleaned or not new_ip_cleaned:
            log.warning("Skipping invalid record", domain=domain, ip=new_ip)
            return False

        existing_records = self.get_custom_dns_records()
        if existing_records is None:
            log.error("Cannot add or update DNS record: existing Pi-hole records cache is None.")
            return False

        if existing_records.get(domain_cleaned) == new_ip_cleaned:
            log.debug("DNS record already exists in Pi-hole. No action needed.", domain=domain_cleaned, ip=new_ip_cleaned)
            return True

        path = f"/api/config/dns/hosts/{quote(new_ip_cleaned + ' ' + domain_cleaned)}"
        response = self._api_request("PUT", path)

        if response and response.get("success"):
            log.info("Successfully added/updated DNS record", domain=domain_cleaned, ip=new_ip_cleaned)
            return True
        elif response and response.get("error", {}).get("key") == "forbidden":
            log.error("Pi-hole API returned a 'forbidden' error. Please ensure 'webserver.api.app_sudo' is set to true in your Pi-hole configuration.")
            return False
        else:
            log.error("Failed to add/update DNS record", domain=domain_cleaned, ip=new_ip_cleaned, response=response)
            return False

    def remove_dns_record(self, domain, ip):
        domain_cleaned = domain.strip().lower()
        ip_cleaned = ip.strip()

        if not domain_cleaned or not ip_cleaned:
            log.warning("Skipping invalid record for removal", domain=domain, ip=ip)
            return False

        path = f"/api/config/dns/hosts/{quote(ip_cleaned + ' ' + domain_cleaned)}"
        response = self._api_request("DELETE", path)

        if response and response.get("success"):
            log.info("Successfully removed DNS record", domain=domain_cleaned, ip=ip_cleaned)
            return True
        else:
            log.error("Failed to remove DNS record", domain=domain_cleaned, ip=ip_cleaned, response=response)
            return False
