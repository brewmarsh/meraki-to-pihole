import logging
import meraki

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki devices that have a static IP assignment.
    It queries either all networks in the organization or a specified list of
    network IDs. Devices are filtered to include only those with a
    static IP assignment.
    Args:
        dashboard (meraki.DashboardAPI): Initialized Meraki Dashboard API client.
        config (dict): The application configuration dictionary.
    Returns:
        list: A list of device dictionaries, each representing a device with a
              static IP. Returns an empty list if no such
              devices are found or if network fetching fails.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]

    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: {specified_network_ids if specified_network_ids else 'All'}.")
    all_devices_map = {}

    networks_to_query_details = []
    try:
        if not specified_network_ids:
            logging.info(f"No specific Meraki network IDs provided. Fetching all networks for organization ID: {org_id}.")
            organization_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
            if not organization_networks:
                logging.info(f"Organization {org_id} has no networks according to API. No devices will be fetched.")
                return []
            networks_to_query_details = organization_networks
        else:
            logging.info(f"Specific Meraki network IDs provided: {specified_network_ids}. Validating and fetching details for these networks.")
            all_org_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
            if not all_org_networks:
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
                    logging.warning(f"None of the specified network IDs {specified_network_ids} were found/valid in organization {org_id}. No devices will be fetched.")
                    return []
    except meraki.exceptions.APIError as e:
        logging.error(f"Meraki API error while fetching networks for organization {org_id}: {e}")
        return []

    if not networks_to_query_details:
        logging.info("No networks to query after initial determination. Exiting device search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query_details)}. Network IDs: {[n['id'] for n in networks_to_query_details]}")

    for network_idx, network_detail in enumerate(networks_to_query_details):
        network_id = network_detail["id"]
        network_name = network_detail.get("name", f"ID-{network_id}")
        logging.info(f"--- Processing network {network_idx + 1}/{len(networks_to_query_details)}: '{network_name}' (ID: {network_id}) ---")

        try:
            devices_in_network = dashboard.networks.getNetworkDevices(network_id)
            if not devices_in_network:
                logging.info(f"No devices found in network '{network_name}' (ID: {network_id}).")
                continue

            for device in devices_in_network:
                try:
                    mgmt_interface = dashboard.devices.getDeviceManagementInterface(device['serial'])
                    if mgmt_interface.get('wan1', {}).get('usingStaticIp'):
                        device_id = device['serial']
                        all_devices_map[device_id] = {
                            "name": device.get('name') or device.get('mac'),
                            "ip": mgmt_interface['wan1']['staticIp'],
                            "network_id": network_id,
                            "network_name": network_name,
                            "meraki_device_id": device_id,
                        }
                        logging.info(f"Relevant device: '{all_devices_map[device_id]['name']}' (IP: {mgmt_interface['wan1']['staticIp']}, Meraki ID: {device_id}) in network '{network_name}'. Using static IP. Will be processed.")
                    else:
                        logging.debug(f"Device '{device.get('name') or device.get('mac')}' in network '{network_name}' does not have a static IP assignment. Skipping.")
                except meraki.exceptions.APIError as e:
                    logging.warning(f"Could not retrieve management interface for device {device['serial']} in network {network_name}: {e}")
        except meraki.exceptions.APIError as e:
            logging.warning(f"Could not retrieve devices for network {network_name}: {e}")

        logging.info(f"--- Finished processing network {network_idx + 1}/{len(networks_to_query_details)}: {network_name} (ID: {network_id}) ---")

    return list(all_devices_map.values())
