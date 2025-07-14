import unittest
from unittest.mock import MagicMock, patch
from app.clients.meraki_client import get_all_relevant_meraki_clients

class TestMerakiClient(unittest.TestCase):

    def setUp(self):
        self.config = {
            "meraki_org_id": "12345",
            "meraki_network_ids": [],
            "meraki_client_timespan": 86400
        }
        self.dashboard = MagicMock()

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_no_networks(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_with_networks_no_clients(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [
            {"id": "N_1", "name": "Network 1"},
            {"id": "N_2", "name": "Network 2"}
        ]
        mock_dashboard.appliance.getNetworkApplianceDhcpSubnets.return_value = []
        mock_dashboard.networks.getNetworkClients.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_with_clients(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [
            {"id": "N_1", "name": "Network 1"}
        ]
        mock_dashboard.appliance.getNetworkApplianceDhcpSubnets.return_value = [{
            "fixedIpAssignments": {
                "AA:BB:CC:DD:EE:FF": {
                    "ip": "192.168.1.100",
                    "name": "Test Client"
                }
            }
        }]
        mock_dashboard.networks.getNetworkClients.return_value = [
            {
                "id": "c_1",
                "description": "Test Client",
                "dhcpHostname": "test-client",
                "ip": "192.168.1.100",
                "mac": "aa:bb:cc:dd:ee:ff",
                "fixedIp": "192.168.1.100"
            }
        ]

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Client")
        self.assertEqual(clients[0]["ip"], "192.168.1.100")

if __name__ == '__main__':
    unittest.main()
