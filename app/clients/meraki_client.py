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
                vlans = dashboard.appliance.getNetworkApplianceVlans(network_id)
                if vlans:
                    for vlan in vlans:
                        if vlan.get('fixedIpAssignments'):
                            for mac, assignment_details in vlan['fixedIpAssignments'].items():
                                if mac and assignment_details.get('ip'):
                                    mac_to_reserved_ip_map[mac.lower()] = assignment_details['ip']
                                    logging.debug(f"Found configured DHCP reservation in network {network_id}: MAC {mac.lower()} -> IP {assignment_details['ip']} (Name: {assignment_details.get('name', 'N/A')})")
                logging.info(f"Found {len(mac_to_reserved_ip_map)} DHCP fixed IP reservations in network {network_name} (ID: {network_id}).")

            except meraki.exceptions.APIError as e:
                if e.status == 404 and "The requested URL was not found on the server." in str(e.message): # More specific check
                    logging.info(f"No DHCP subnet/VLAN configuration found via API for network {network_name} (ID: {network_id}) (Endpoint not found - likely not an MX network or no DHCP configured). Will rely on client.fixedIp if available.")
                else:
                    logging.warning(f"Could not retrieve DHCP subnet/VLANs info for network {network_name} (ID: {network_id}) to check reservations: {e}. Will rely on client.fixedIp if available.")


            # Fetch devices for the network
            devices_in_network = dashboard.networks.getNetworkDevices(network_id)

            if devices_in_network:
                logging.info(f"SDK returned {len(devices_in_network)} devices for network '{network_name}' (ID: {network_id}).")
                logging.debug(f"Filtering {len(devices_in_network)} devices from network '{network_name}'...")
                for device in devices_in_network:
                    serial = device.get("serial")
                    if not serial:
                        continue

                    try:
                        mgmt_interface = dashboard.devices.getDeviceManagementInterface(serial)
                        wan1 = mgmt_interface.get("wan1", {})
                        wan2 = mgmt_interface.get("wan2", {})

                        ip = None
                        if wan1.get("usingStaticIp"):
                            ip = wan1.get("staticIp")
                        elif wan2.get("usingStaticIp"):
                            ip = wan2.get("staticIp")

                        if ip:
                            client_name = device.get("name") or device.get("model")
                            client_id = device.get("serial")
                            all_clients_map[client_id] = {
                                "name": client_name,
                                "ip": ip,
                                "network_id": network_id,
                                "network_name": network_name,
                                "meraki_client_id": client_id,
                            }
                            logging.info(f"Relevant client: '{client_name}' (IP: {ip}, Meraki ID: {client_id}) in network '{network_name}'. Using static IP. Will be processed.")
                        else:
                            logging.debug(f"Device '{device.get('name')}' (Serial: {serial}) in network '{network_name}' does not have a static IP assignment. Skipping.")
                    except meraki.exceptions.APIError as e:
                        logging.warning(f"Could not retrieve management interface for device {serial} in network {network_name}: {e}")
            else:
                logging.info(f"No devices reported by SDK for network {network_name} (ID: {network_id}).")

        except meraki.exceptions.APIError as e:
            logging.error(f"Meraki API error during processing of network {network_name} (ID: {network_id}): {e}")
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing network {network_name} (ID: {network_id}): {e}", exc_info=True)

        logging.info(f"--- Finished processing network {network_idx + 1}/{len(networks_to_query_details)}: {network_name} (ID: {network_id}) ---")

    return list(all_clients_map.values())
