import sys
import os
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.clients.meraki_client import get_all_relevant_meraki_clients

class TestMerakiClient(unittest.TestCase):

    def setUp(self):
        self.config = {
            "meraki_org_id": "12345",
            "meraki_network_ids": [],
            "meraki_client_timespan_seconds": 86400
        }

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_no_clients(self, mock_dashboard):
        # Arrange
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "net_123"}]
        mock_dashboard.networks.getNetworkClients.return_value = []

        # Act
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert
        self.assertEqual(clients, [])
        mock_dashboard.networks.getNetworkClients.assert_called_once_with(networkId="net_123", total_pages='all', timespan=86400)

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_with_clients_no_fixed_ip(self, mock_dashboard):
        # Arrange
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "net_123"}]
        mock_dashboard.networks.getNetworkClients.return_value = [{"id": "c_1", "mac": "00:11:22:33:44:55", "ip": "10.0.0.1"}]

        # Act
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert
        self.assertEqual(clients, [])

    @patch('meraki.DashboardAPI')
    def test_get_all_relevant_meraki_clients_with_clients_with_fixed_ip(self, mock_dashboard):
        # Arrange
        mock_dashboard.organizations.getOrganizationNetworks.return_value = [{"id": "net_123"}]
        mock_dashboard.networks.getNetworkClients.return_value = [
            {"mac": "mac_1", "description": "Test Client", "fixedIp": "1.2.3.4"}
        ]

        # Act
        clients = get_all_relevant_meraki_clients(mock_dashboard, self.config)

        # Assert
        self.assertEqual(len(clients), 1)
        self.assertEqual(clients[0]["name"], "Test Client")
        self.assertEqual(clients[0]["ip"], "1.2.3.4")
