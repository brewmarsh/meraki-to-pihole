import unittest
from unittest.mock import MagicMock, patch

from app.clients.pihole_client import (
    add_dns_record_to_pihole,
    add_or_update_dns_record_in_pihole,
    delete_dns_record_from_pihole,
    get_pihole_custom_dns_records,
)


class TestPiholeClient(unittest.TestCase):
    def setUp(self):
        self.pihole_url = "http://pi.hole/admin/"
        self.api_key = "test_key"

    @patch("requests.get")
    def test_get_pihole_custom_dns_records(self, mock_get):
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"data": [["test.com", "1.2.3.4"]]}
        mock_get.return_value = mock_response

        # Call the function
        records = get_pihole_custom_dns_records(self.pihole_url, self.api_key)

        # Assert the result
        self.assertEqual(records, {"test.com": ["1.2.3.4"]})
        mock_get.assert_called_once_with(
            "http://pi.hole/admin/api.php",
            params={"customdns": "", "action": "get", "auth": "test_key"},
            timeout=10,
        )

    @patch("requests.get")
    def test_add_dns_record_to_pihole(self, mock_get):
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "Custom DNS entry [...] added"}
        mock_get.return_value = mock_response

        # Call the function
        result = add_dns_record_to_pihole(self.pihole_url, self.api_key, "test.com", "1.2.3.4")

        # Assert the result
        self.assertTrue(result)

    @patch("requests.get")
    def test_delete_dns_record_from_pihole(self, mock_get):
        # Mock the API response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": True, "message": "Custom DNS entry [...] deleted"}
        mock_get.return_value = mock_response

        # Call the function
        result = delete_dns_record_from_pihole(self.pihole_url, self.api_key, "test.com", "1.2.3.4")

        # Assert the result
        self.assertTrue(result)

    @patch("app.clients.pihole_client.delete_dns_record_from_pihole")
    @patch("app.clients.pihole_client.add_dns_record_to_pihole")
    def test_add_or_update_dns_record_in_pihole_add(self, mock_add, mock_delete):
        # Mock the return values
        mock_add.return_value = True
        mock_delete.return_value = True

        # Call the function
        existing_records = {}
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url, self.api_key, "test.com", "1.2.3.4", existing_records
        )

        # Assert the result
        self.assertTrue(result)
        self.assertEqual(existing_records, {"test.com": ["1.2.3.4"]})
        mock_add.assert_called_once_with(self.pihole_url, self.api_key, "test.com", "1.2.3.4")
        mock_delete.assert_not_called()

    @patch("app.clients.pihole_client.delete_dns_record_from_pihole")
    @patch("app.clients.pihole_client.add_dns_record_to_pihole")
    def test_add_or_update_dns_record_in_pihole_update(self, mock_add, mock_delete):
        # Mock the return values
        mock_add.return_value = True
        mock_delete.return_value = True

        # Call the function
        existing_records = {"test.com": ["1.1.1.1"]}
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url, self.api_key, "test.com", "2.2.2.2", existing_records
        )

        # Assert the result
        self.assertTrue(result)
        self.assertEqual(existing_records, {"test.com": ["2.2.2.2"]})
        mock_delete.assert_called_once_with(self.pihole_url, self.api_key, "test.com", "1.1.1.1")
        mock_add.assert_called_once_with(self.pihole_url, self.api_key, "test.com", "2.2.2.2")


if __name__ == "__main__":
    unittest.main()
