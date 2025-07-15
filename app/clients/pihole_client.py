import logging
import requests


def _pihole_api_request(pihole_url, api_key, params):
    if pihole_url.endswith("/api.php"):
        pihole_url = pihole_url[:-7]

    # Correct the URL to not include /admin
    if "/admin" in pihole_url:
        pihole_url = pihole_url.replace("/admin", "")

    if api_key:
        params["auth"] = api_key

    try:
        logging.debug(f"Pi-hole API Request: URL={pihole_url}, Params={params}")
        response = requests.get(pihole_url, params=params, timeout=10)
        logging.debug(f"Pi-hole API Request URL: {response.url}")
        logging.debug(f"Pi-hole API Request Headers: {response.request.headers}")
        logging.debug(f"Pi-hole API Response Status Code: {response.status_code}")
        logging.debug(f"Pi-hole API Response Text: {response.text}")
        response.raise_for_status()
        if response.text:  # Response has content
            try:
                json_response = response.json()
                logging.debug(f"Pi-hole API JSON Response: {json_response}")
                return json_response
            except ValueError:  # Not JSON
                logging.debug(f"Pi-hole API response was not JSON: {response.text[:200]}")  # Log snippet
                # Handle common non-JSON success cases for add/delete if possible, or treat as success if status is OK.
                if response.ok:
                    if response.text.strip() == "[]":  # Empty JSON array often means "no data" for 'get'
                        return {"data": []}
                    # For add/delete, Pi-hole might return simple strings or empty body on success
                    return {
                        "success": True,
                        "message": f"Action likely successful (non-JSON response, HTTP {response.status_code}): {response.text[:100]}",
                    }
                # If not response.ok and not JSON:
                return {
                    "success": False,
                    "message": f"Request failed with status {response.status_code}, non-JSON response: {response.text[:100]}",
                }
        elif response.ok:  # Response has no content but status is OK (e.g., 200 OK with empty body)
            logging.debug("Pi-hole API request successful with empty response body.")
            return {"success": True, "message": "Action successful (empty response)."}
        else:  # Response has no content and status is not OK
            return {"success": False, "message": f"Request failed with status {response.status_code} (empty response)."}
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            logging.error(
                "Pi-hole API returned a 400 Bad Request. This can be caused by an incorrect API key. Please check your PIHOLE_API_KEY."
            )
        logging.error(
            f"Pi-hole API HTTP error: {e} - Response: {e.response.text[:200] if e.response and e.response.text else 'No response text'}"
        )
    except requests.exceptions.RequestException as e:
        logging.error(f"Pi-hole API request failed due to network or request issue: {e}")
    return None  # Indicates a failure in the request execution itself


def get_pihole_custom_dns_records(pihole_url, api_key):
    """Fetches and parses custom DNS records from Pi-hole."""
    logging.info("Fetching existing custom DNS records from Pi-hole...")
    params = {"customdns": "", "action": "get"}  # Auth is added by _pihole_api_request
    response_data = _pihole_api_request(pihole_url, api_key, params)

    records = {}  # Store as {domain: [ip1, ip2]}
    if response_data and isinstance(response_data.get("data"), list):
        # Pi-hole's get customdns returns: {"data": [["domain1.com", "1.2.3.4"], ["domain2.com", "5.6.7.8"]]}
        for item in response_data["data"]:
            if isinstance(item, list) and len(item) == 2:
                domain, ip_address = item
                # Ensure domain is stored consistently, e.g., lowercased
                domain_cleaned = domain.strip().lower()
                if domain_cleaned not in records:
                    records[domain_cleaned] = []
                records[domain_cleaned].append(ip_address.strip())
            else:
                logging.warning(f"Unexpected item format in Pi-hole custom DNS data: {item}")
        logging.info(
            f"Found {len(records)} unique domains with {sum(len(ips) for ips in records.values())} total custom DNS IP mappings in Pi-hole."
        )
    elif response_data:  # Response received, but format is not as expected
        logging.warning(
            f"Pi-hole custom DNS response format unexpected or 'data' field missing/not a list: {str(response_data)[:200]}"
        )
    else:  # _pihole_api_request returned None (request failed)
        logging.error("Failed to fetch custom DNS records from Pi-hole (API request failed or returned None).")
        return None  # Critical failure, cannot proceed with sync logic accurately
    return records


def add_dns_record_to_pihole(pihole_url, api_key, domain, ip_address):
    """Adds a single DNS record to Pi-hole."""
    logging.info(f"Adding DNS record to Pi-hole: {domain} -> {ip_address}")
    params = {"customdns": "", "action": "add", "domain": domain, "ip": ip_address}
    response = _pihole_api_request(pihole_url, api_key, params)
    # Pi-hole add API typically returns {"success":true,"message":"Custom DNS entry [...] added"} or similar
    if response and response.get("success") is True:  # Check for explicit success field
        logging.info(
            f"Successfully added DNS record: {domain} -> {ip_address}. Pi-hole message: {response.get('message', 'OK')}"
        )
        return True
    # Fallback for older/different Pi-hole versions or unexpected success responses
    elif response and isinstance(response.get("message"), str) and "added" in response.get("message").lower():
        logging.info(
            f"Processed add DNS record for: {domain} -> {ip_address} (inferred success). Pi-hole Response: {response.get('message')}"
        )
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
        logging.info(
            f"Successfully deleted DNS record: {domain} -> {ip_address}. Pi-hole message: {response.get('message', 'OK')}"
        )
        return True
    # Fallback for older/different Pi-hole versions or messages indicating non-existence (which is a successful deletion outcome)
    elif (
        response
        and isinstance(response.get("message"), str)
        and ("deleted" in response.get("message").lower() or "does not exist" in response.get("message").lower())
    ):
        logging.info(
            f"Processed delete DNS record for: {domain} -> {ip_address} (inferred success/already gone). Pi-hole Response: {response.get('message')}"
        )
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
                if delete_dns_record_from_pihole(pihole_url, api_key, domain_cleaned, old_ip):
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
    if add_dns_record_to_pihole(pihole_url, api_key, domain_cleaned, new_ip_cleaned):
        # Update cache on successful addition
        if domain_cleaned not in existing_records_cache:
            existing_records_cache[domain_cleaned] = []
        if new_ip_cleaned not in existing_records_cache[domain_cleaned]:  # Avoid duplicates if somehow added again
            existing_records_cache[domain_cleaned].append(new_ip_cleaned)
        return True
    return False
