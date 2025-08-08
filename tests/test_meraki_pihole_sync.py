import unittest
from unittest.mock import patch

from app.sync_logic import sync_pihole_dns


class TestMerakiPiholeSync(unittest.TestCase):

    @patch('app.sync_logic.load_app_config_from_env')
    @patch('app.sync_logic.get_meraki_data')
    @patch('app.sync_logic.PiholeClient')
    def test_sync_pihole_dns_success_flow(self, mock_pihole_client, mock_get_meraki_data, mock_load_config):
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
        mock_get_meraki_data.return_value = [
            {"name": "Test-Client-1", "ip": "192.168.1.10"}
        ]
        mock_pihole_client.return_value.get_custom_dns_records.return_value = {}
        mock_pihole_client.return_value.add_or_update_dns_record.return_value = True

        # Act
        sync_pihole_dns()

        # Assert
        self.assertEqual(mock_get_meraki_data.call_count, 1)
        mock_pihole_client.return_value.add_or_update_dns_record.assert_called_once_with(
            "test-client-1.lan", "192.168.1.10"
        )

    @patch('app.sync_logic.load_app_config_from_env')
    @patch('app.sync_logic.get_meraki_data')
    @patch('app.sync_logic.PiholeClient')
    def test_sync_pihole_dns_handles_client_with_no_name(self, mock_pihole_client, mock_get_meraki_data, mock_load_config):
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
        mock_get_meraki_data.return_value = [
            {"name": None, "ip": "192.168.1.11"}
        ]
        mock_pihole_client.return_value.get_custom_dns_records.return_value = {}
        mock_pihole_client.return_value.add_or_update_dns_record.return_value = True

        # Act
        sync_pihole_dns()

        # Assert
        mock_pihole_client.return_value.add_or_update_dns_record.assert_not_called()

if __name__ == '__main__':
    unittest.main()
