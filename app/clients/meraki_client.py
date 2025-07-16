import logging
import meraki

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki clients that have a fixed IP assignment.
    It queries either all networks in the organization or a specified list of
    network IDs. Clients are filtered to include only those with a
    'fixedIpAssignment'.
    Args:
        dashboard (meraki.DashboardAPI): Initialized Meraki Dashboard API client.
        config (dict): The application configuration dictionary.
    Returns:
        list: A list of client dictionaries, each representing a client with a
              fixed IP. Returns an empty list if no such
              clients are found or if network fetching fails.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config["meraki_network_ids"]
    client_timespan = config["meraki_client_timespan_seconds"]

    logging.debug(f"Entering get_all_relevant_meraki_clients. Org ID: {org_id}. Specified Network IDs: {specified_network_ids if specified_network_ids else 'All'}. Client Timespan: {client_timespan}s.")
    all_clients_map = {}

    networks_to_query_details = []
    try:
        if not specified_network_ids:
            logging.info(f"No specific Meraki network IDs provided. Fetching all networks for organization ID: {org_id}.")
            organization_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')
            if not organization_networks:
                logging.info(f"Organization {org_id} has no networks according to API. No clients will be fetched.")
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
                    logging.warning(f"None of the specified network IDs {specified_network_ids} were found/valid in organization {org_id}. No clients will be fetched.")
                    return []
    except meraki.exceptions.APIError as e:
        logging.error(f"Meraki API error while fetching networks for organization {org_id}: {e}")
        return []

    if not networks_to_query_details:
        logging.info("No networks to query after initial determination. Exiting client search.")
        return []
    else:
        logging.info(f"Total networks to query: {len(networks_to_query_details)}. Network IDs: {[n['id'] for n in networks_to_query_details]}")

    for network_idx, network_detail in enumerate(networks_to_query_details):
        network_id = network_detail["id"]
        network_name = network_detail.get("name", f"ID-{network_id}")
        logging.info(f"--- Processing network {network_idx + 1}/{len(networks_to_query_details)}: '{network_name}' (ID: {network_id}) ---")

        try:
            clients_in_network = dashboard.networks.getNetworkClients(network_id, timespan=client_timespan, perPage=1000, total_pages='all')
            if not clients_in_network:
                logging.info(f"No clients found in network '{network_name}' (ID: {network_id}) within the timespan.")
                continue

            for client in clients_in_network:
                if client.get('fixedIp'):
                    client_id = client['id']
                    all_clients_map[client_id] = {
                        "name": client.get('description') or client.get('mac'),
                        "ip": client['fixedIp'],
                        "network_id": network_id,
                        "network_name": network_name,
                        "meraki_client_id": client_id,
                    }
                    logging.info(f"Relevant client: '{all_clients_map[client_id]['name']}' (IP: {client['fixedIp']}, Meraki ID: {client_id}) in network '{network_name}'. Using fixed IP. Will be processed.")
                else:
                    logging.debug(f"Client '{client.get('description') or client.get('mac')}' in network '{network_name}' does not have a fixed IP assignment. Skipping.")
        except meraki.exceptions.APIError as e:
            logging.warning(f"Could not retrieve clients for network {network_name}: {e}")

        logging.info(f"--- Finished processing network {network_idx + 1}/{len(networks_to_query_details)}: {network_name} (ID: {network_id}) ---")

    return list(all_clients_map.values())
