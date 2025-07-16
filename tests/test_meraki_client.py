import unittest
from unittest.mock import patch, MagicMock
from app.clients.meraki_client import get_all_relevant_meraki_clients

class TestMerakiClient(unittest.TestCase):
    def setUp(self):
        self.config = {
            "meraki_org_id": "12345",
            "meraki_network_ids": [],
            "meraki_client_timespan_seconds": 86400,
        }

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_no_networks(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])
        mock_dashboard.organizations.getOrganizationNetworks.assert_called_once_with(
            organizationId="12345", total_pages="all"
        )

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_networks_no_clients(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [
            {"id": "N_1", "name": "Network 1"},
            {"id": "N_2", "name": "Network 2"},
        ]
        mock_dashboard.networks.getNetworkClients.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])
        self.assertEqual(mock_dashboard.networks.getNetworkClients.call_count, 2)

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_clients_no_fixed_ip(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "N_1", "name": "Network 1"}]
        mock_dashboard.networks.getNetworkClients.return_value = [{"id": "c_1", "mac": "00:11:22:33:44:55"}]

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_clients_with_fixed_ip(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "N_1", "name": "Network 1"}]
        mock_dashboard.networks.getNetworkClients.return_value = [
            {"id": "c_1", "mac": "00:11:22:33:44:55", "fixedIp": "1.2.3.4", "description": "Test Client"}
        ]

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Client")
        self.assertEqual(clients[0]["ip"], "1.2.3.4")
