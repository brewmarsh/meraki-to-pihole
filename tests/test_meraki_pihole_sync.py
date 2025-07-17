import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add the app directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'app')))

from meraki_pihole_sync import main

class TestMerakiPiholeSync(unittest.TestCase):

    @patch('meraki_pihole_sync.update_meraki_data')
    @patch('meraki_pihole_sync.update_pihole_data')
    def test_main_success_flow(self, mock_update_pihole_data, mock_update_meraki_data):
        # Arrange
        mock_update_meraki_data.return_value = [
            {"name": "Test-Client-1", "ip": "192.168.1.10"}
        ]

        # Act
        main()

        # Assert
        self.assertEqual(mock_update_meraki_data.call_count, 1)
        mock_update_pihole_data.assert_called_once_with(
            [{"name": "Test-Client-1", "ip": "192.168.1.10"}]
        )

    @patch('meraki_pihole_sync.load_app_config_from_env')
    @patch('meraki_pihole_sync.authenticate_to_pihole')
    @patch('meraki_pihole_sync.get_all_relevant_meraki_clients')
    @patch('meraki_pihole_sync.get_pihole_custom_dns_records')
    @patch('meraki_pihole_sync.add_or_update_dns_record_in_pihole')
    @patch('meraki.DashboardAPI')
    def test_main_handles_client_with_no_name(self, mock_dashboard_api, mock_add_or_update, mock_get_dns, mock_get_clients, mock_auth, mock_load_config):
        # Arrange
        mock_load_config.return_value = {
            "meraki_api_key": "fake_meraki_key",
            "pihole_api_url": "http://fake-pihole.local",
            "pihole_api_key": "fake_pihole_key",
            "hostname_suffix": ".lan",
            "meraki_org_id": "fake_org_id",
            "meraki_network_ids": [],
            "meraki_client_timespan_seconds": 86400,
        }
        mock_auth.return_value = ("fake_sid", "fake_csrf")
        mock_get_clients.return_value = [
            {"name": None, "ip": "192.168.1.11"}
        ]
        mock_get_dns.return_value = {}
        mock_add_or_update.return_value = True

        # Act
        main()

        # Assert
        mock_add_or_update.assert_not_called()

if __name__ == '__main__':
    unittest.main()
