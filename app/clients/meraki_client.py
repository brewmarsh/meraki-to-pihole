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
    relevant_clients = []
    devices = dashboard.organizations.getOrganizationDevices(org_id)

    for device in devices:
        if device['model'].startswith('MS'):
            interfaces = dashboard.switch.getDeviceSwitchRoutingInterfaces(device['serial'])
            for interface in interfaces:
                dhcp = dashboard.switch.getDeviceSwitchRoutingInterfaceDhcp(device['serial'], interface['interfaceId'])
                if dhcp.get('fixedIpAssignments'):
                    for mac, client_data in dhcp['fixedIpAssignments'].items():
                        relevant_clients.append({
                            "name": client_data.get('name') or mac,
                            "ip": client_data['ip'],
                            "network_id": device['networkId'],
                            "network_name": "N/A",
                            "meraki_client_id": mac,
                            "type": "Fixed IP"
                        })
        elif device['model'].startswith('MX'):
            vlans = dashboard.appliance.getNetworkApplianceVlans(device['networkId'])
            for vlan in vlans:
                if vlan.get('fixedIpAssignments'):
                    for mac, client_data in vlan['fixedIpAssignments'].items():
                        relevant_clients.append({
                            "name": client_data.get('name') or mac,
                            "ip": client_data['ip'],
                            "network_id": device['networkId'],
                            "network_name": vlan['name'],
                            "meraki_client_id": mac,
                            "type": "Fixed IP"
                        })

    return relevant_clients
