import unittest
from unittest.mock import patch, MagicMock
from app.clients.pihole_client import (
    get_pihole_custom_dns_records,
    add_dns_record_to_pihole,
    delete_dns_record_from_pihole,
)

class TestPiholeClient(unittest.TestCase):
    def setUp(self):
        self.pihole_url = "http://pi.hole"
        self.session_cookie = "test_session_cookie"
        self.csrf_token = "test_csrf_token"

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_get_pihole_custom_dns_records(self, mock_request):
        # Mock the API response
        mock_request.return_value = {
            "data": [
                {"type": "A", "domain": "test.com", "ip": "1.2.3.4"},
                {"type": "CNAME", "domain": "alias.com", "target": "test.com"},
            ]
        }

        # Call the function
        records = get_pihole_custom_dns_records(
            self.pihole_url, self.session_cookie, self.csrf_token
        )

        # Assert the result
        self.assertEqual(records, {"test.com": ["1.2.3.4"]})

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_get_pihole_custom_dns_records_no_records(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"data": []}

        # Call the function
        records = get_pihole_custom_dns_records(
            self.pihole_url, self.session_cookie, self.csrf_token
        )

        # Assert the result
        self.assertEqual(records, {})

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_add_dns_record_to_pihole(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"success": True}

        # Call the function
        result = add_dns_record_to_pihole(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
        )

        # Assert the result
        self.assertTrue(result)
        mock_request.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "POST",
            "/api/domains",
            data={"domain": "test.com", "ip": "1.2.3.4"},
        )

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_delete_dns_record_from_pihole(self, mock_request):
        # Mock the API response
        mock_request.return_value = {"success": True}

        # Call the function
        result = delete_dns_record_from_pihole(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
        )

        # Assert the result
        self.assertTrue(result)
        mock_request.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "DELETE",
            "/api/domains",
            data={"domain": "test.com", "ip": "1.2.3.4"},
        )
