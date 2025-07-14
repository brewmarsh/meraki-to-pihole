import logging
import meraki

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
                appliance_dhcp_subnets = dashboard.appliance.getNetworkApplianceDhcpSubnets(networkId=network_id)
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
