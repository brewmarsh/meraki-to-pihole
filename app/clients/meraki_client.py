import logging
import meraki

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki clients that have a fixed IP assignment (DHCP reservation).

    This function is optimized to:
    1. Fetch all clients in the organization efficiently.
    2. Filter for the specific networks if provided.
    3. Filter those clients to find ones with a "Fixed IP" (DHCP reservation).
    4. Return a list of these clients with the necessary information for DNS syncing.

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
    networks = specified_network_ids or [n['id'] for n in dashboard.organizations.getOrganizationNetworks(org_id)]

    for network_id in networks:
        try:
            logging.info(f"Fetching clients for network ID: {network_id}.")
            network_clients = dashboard.networks.getNetworkClients(
                networkId=network_id, total_pages='all', timespan=timespan
            )

            if not network_clients:
                logging.warning(f"No clients found in network {network_id}.")
                continue

            for client in network_clients:
                if client.get('fixedIp'):
                    relevant_clients.append({
                        "name": client.get('description') or client.get('mac'),
                        "ip": client['fixedIp'],
                        "network_id": network_id,
                        "network_name": "N/A",  # Network name is not available in this endpoint
                        "meraki_client_id": client['mac'],
                        "type": "Fixed IP"
                    })
                    logging.debug(f"Found relevant client with fixed IP: {client.get('description')} ({client['fixedIp']})")

        except meraki.exceptions.APIError as e:
            logging.error(f"Meraki API error while fetching clients for network {network_id}: {e}")
            continue
        except Exception as e:
            logging.error(f"An unexpected error occurred while processing clients for network {network_id}: {e}")

    return relevant_clients
