import unittest
from unittest.mock import patch, MagicMock
from app.clients.pihole_client import (
    get_pihole_custom_dns_records,
    add_or_update_dns_record_in_pihole,
)

class TestPiholeClient(unittest.TestCase):
    def setUp(self):
        self.pihole_url = "http://pi.hole"
        self.sid = "test_sid"
        self.csrf_token = "test_csrf_token"

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_get_pihole_custom_dns_records(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"hosts": ["1.2.3.4 test.com", "5.6.7.8 example.com"]}

        # Call the function
        records = get_pihole_custom_dns_records(self.pihole_url, self.sid, self.csrf_token)

        # Assert the result
        self.assertEqual(records, {"test.com": "1.2.3.4", "example.com": "5.6.7.8"})

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_get_pihole_custom_dns_records_no_records(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"hosts": []}

        # Call the function
        records = get_pihole_custom_dns_records(self.pihole_url, self.sid, self.csrf_token)

        # Assert the result
        self.assertEqual(records, {})

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_add_or_update_dns_record_in_pihole_add(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"success": True}

        # Call the function
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url,
            self.sid,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
            {},
        )

        # Assert the result
        self.assertTrue(result)
        mock_request.assert_called_once()

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_add_or_update_dns_record_in_pihole_update(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"success": True}

        # Call the function
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url,
            self.sid,
            self.csrf_token,
            "test.com",
            "5.6.7.8",
            {"test.com": "1.2.3.4"},
        )

        # Assert the result
        self.assertTrue(result)
        mock_request.assert_called_once()

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_add_or_update_dns_record_in_pihole_no_change(self, mock_request):
        # Call the function
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url,
            self.sid,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
            {"test.com": "1.2.3.4"},
        )

        # Assert the result
        self.assertTrue(result)
        mock_request.assert_not_called()
