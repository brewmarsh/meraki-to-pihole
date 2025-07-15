import unittest
from unittest.mock import MagicMock, patch

from app.clients.meraki_client import get_all_relevant_meraki_clients


class TestMerakiClient(unittest.TestCase):
    def setUp(self):
        self.config = {"meraki_org_id": "12345", "meraki_network_ids": [], "meraki_client_timespan": 86400}
        self.dashboard = MagicMock()

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_no_networks(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_networks_no_devices(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [
            {"id": "N_1", "name": "Network 1"},
            {"id": "N_2", "name": "Network 2"},
        ]
        mock_dashboard.networks.getNetworkDevices.return_value = []

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_devices_no_static_ip(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "N_1", "name": "Network 1"}]
        mock_dashboard.networks.getNetworkDevices.return_value = [{"serial": "Q2QN-9J8L-SLPD"}]
        mock_dashboard.devices.getDeviceManagementInterface.return_value = {
            "wan1": {"usingStaticIp": False},
            "wan2": {"usingStaticIp": False},
        }

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(clients, [])

    @patch("meraki.DashboardAPI")
    def test_get_all_relevant_meraki_clients_with_devices_with_static_ip(self, mock_dashboard):
        # Mock the API calls
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "N_1", "name": "Network 1"}]
        mock_dashboard.networks.getNetworkDevices.return_value = [{"serial": "Q2QN-9J8L-SLPD", "name": "Test Device"}]
        mock_dashboard.devices.getDeviceManagementInterface.return_value = {
            "wan1": {"usingStaticIp": True, "staticIp": "1.2.3.4"},
            "wan2": {"usingStaticIp": False},
        }

        # Call the function
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert the result
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Device")
        self.assertEqual(clients[0]["ip"], "1.2.3.4")


if __name__ == "__main__":
    unittest.main()
