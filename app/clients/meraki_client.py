import logging
import meraki

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki clients that have a fixed IP assignment (DHCP reservation).

    This function is optimized to:
    1. Fetch all networks in the organization efficiently.
    2. Filter for the specific networks if provided.
    3. For each relevant network, fetch all clients.
    4. Filter those clients to find ones with a "Fixed IP" (DHCP reservation).
    5. Return a list of these clients with the necessary information for DNS syncing.

    Args:
        dashboard (meraki.DashboardAPI): Initialized Meraki Dashboard API client.
        config (dict): The application configuration dictionary.

    Returns:
        list: A list of client dictionaries, each representing a client with a
              fixed IP. Returns an empty list if no such clients are found or
              if there's an API error.
    """
    org_id = config["meraki_org_id"]
    specified_network_ids = config.get("meraki_network_ids", [])
    timespan = config.get("meraki_client_timespan_seconds", 86400)  # Default to 24 hours

    logging.debug(
        f"Starting Meraki client search. Org ID: {org_id}. "
        f"Specified Network IDs: {specified_network_ids or 'All'}. "
        f"Client Timespan: {timespan}s."
    )

    relevant_clients = []
    networks_to_query = []

    try:
        # Fetch all networks for the organization once.
        logging.info(f"Fetching all networks for organization ID: {org_id}.")
        all_org_networks = dashboard.organizations.getOrganizationNetworks(organizationId=org_id, total_pages='all')

        if not all_org_networks:
            logging.warning(f"No networks found in organization {org_id}. Cannot proceed.")
            return []

        # Create a map for easy lookup
        network_map = {net['id']: net for net in all_org_networks}

        # Determine which networks to query based on user config
        if specified_network_ids:
            logging.info(f"Filtering for specified network IDs: {specified_network_ids}")
            for net_id in specified_network_ids:
                if net_id in network_map:
                    networks_to_query.append(network_map[net_id])
                else:
                    logging.warning(f"Specified network ID {net_id} not found in organization. It will be skipped.")
            if not networks_to_query:
                logging.warning("None of the specified network IDs were found. No clients will be fetched.")
                return []
        else:
            logging.info("No specific network IDs provided. Querying all networks in the organization.")
            networks_to_query = all_org_networks

    except meraki.exceptions.APIError as e:
        logging.error(f"Meraki API error while fetching networks for organization {org_id}: {e}")
        return []

    logging.info(f"Will query for clients in {len(networks_to_query)} network(s).")

    # Iterate through the determined networks and find clients with fixed IPs
    for i, network in enumerate(networks_to_query):
        net_id = network["id"]
        net_name = network.get("name", f"ID-{net_id}")
        logging.info(f"--- ({i+1}/{len(networks_to_query)}) Processing network: '{net_name}' (ID: {net_id}) ---")

        try:
            # Fetch all clients in the network that have been seen within the timespan
            clients_in_network = dashboard.networks.getNetworkClients(
                net_id, timespan=timespan, total_pages='all'
            )

            if not clients_in_network:
                logging.info(f"No clients found in network '{net_name}' within the last {timespan} seconds.")
                continue

            # Filter for clients that have a fixed IP assignment
            for client in clients_in_network:
                # The key for a DHCP reservation is 'dhcpHostname' being present and a 'fixedIp' assignment
                if client.get("fixedIp"):
                    client_name = client.get("description") or client.get("dhcpHostname") or client.get("mac")
                    client_ip = client["fixedIp"]

                    # Ensure the client is currently assigned the fixed IP
                    if client.get("ip") == client_ip:
                        relevant_clients.append({
                            "name": client_name,
                            "ip": client_ip,
                            "network_id": net_id,
                            "network_name": net_name,
                            "meraki_client_id": client['id'],
                        })
                        logging.info(
                            f"Found relevant client: '{client_name}' (Fixed IP: {client_ip}) in network '{net_name}'."
                        )
                    else:
                        logging.debug(
                            f"Client '{client_name}' has a fixed IP ({client_ip}) but is currently using a different IP "
                            f"({client.get('ip', 'N/A')}). Skipping."
                        )
                else:
                    logging.debug(
                        f"Client with MAC {client.get('mac')} does not have a fixed IP assignment. Skipping."
                    )

        except meraki.exceptions.APIError as e:
            logging.warning(
                f"Could not retrieve or process clients for network '{net_name}' (ID: {net_id}): {e}"
            )
        finally:
            logging.info(f"--- Finished processing network '{net_name}' ---")

    return relevant_clients
