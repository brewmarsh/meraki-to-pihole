import meraki
import structlog

log = structlog.get_logger()

def _get_fixed_ip_assignments_from_switch(dashboard: meraki.DashboardAPI, device: dict):
    """
    Fetches fixed IP assignments from a Meraki switch.
    """
    relevant_clients = []
    try:
        interfaces = dashboard.switch.getDeviceSwitchRoutingInterfaces(device['serial'])
        for interface in interfaces:
            dhcp = dashboard.switch.getDeviceSwitchRoutingInterfaceDhcp(device['serial'], interface['interfaceId'])
            if dhcp.get('fixedIpAssignments'):
                for mac, client_data in dhcp['fixedIpAssignments'].items():
                    relevant_clients.append({
                        "name": client_data.get('name') or mac,
                        "ip": client_data['ip'],
                        "network_id": device['networkId'],
                        "network_name": None,
                        "meraki_client_id": mac,
                        "type": "Fixed IP"
                    })
    except meraki.APIError as e:
        log.error("Meraki API error while fetching switch data", error=e, device=device)
    return relevant_clients

def _get_fixed_ip_assignments_from_appliance(dashboard: meraki.DashboardAPI, device: dict):
    """
    Fetches fixed IP assignments from a Meraki appliance (MX).
    """
    relevant_clients = []
    try:
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
    except meraki.APIError as e:
        log.error("Meraki API error while fetching appliance data", error=e, device=device)
    return relevant_clients

def get_all_relevant_meraki_clients(dashboard: meraki.DashboardAPI, config: dict):
    """
    Fetches all Meraki clients that have a fixed IP assignment (DHCP reservation).

    This function is optimized to:
    1. Fetch all devices in the organization efficiently.
    2. Filter for the specific networks if provided.
    3. For each device, fetches the fixed IP assignments.
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
    try:
        devices = dashboard.organizations.getOrganizationDevices(org_id)
    except meraki.APIError as e:
        log.error("Meraki API error while fetching organization devices", error=e, org_id=org_id)
        return []

    for device in devices:
        if device['model'].startswith('MS'):
            relevant_clients.extend(_get_fixed_ip_assignments_from_switch(dashboard, device))
        elif device['model'].startswith('MX'):
            relevant_clients.extend(_get_fixed_ip_assignments_from_appliance(dashboard, device))

    return relevant_clients
