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
        self.pihole_url = "http://pi.hole"
        self.session_cookie = "test_session_cookie"
        self.csrf_token = "test_csrf_token"

    @patch("app.clients.pihole_client._pihole_api_request")
    def test_get_pihole_custom_dns_records(self, mock_request):
        # Mock the API response
        mock_request.return_value = ["1.2.3.4 test.com"]

        # Call the function
        records = get_pihole_custom_dns_records(
            self.pihole_url, self.session_cookie, self.csrf_token
        )

        # Assert the result
        self.assertEqual(records, {"test.com": ["1.2.3.4"]})
        mock_request.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "GET",
            "/api/config/dns.hosts",
        )

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
            "PUT",
            "/api/config/dns.hosts/1.2.3.4%20test.com",
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
            "/api/config/dns.hosts/1.2.3.4%20test.com",
        )

    @patch("app.clients.pihole_client.delete_dns_record_from_pihole")
    @patch("app.clients.pihole_client.add_dns_record_to_pihole")
    def test_add_or_update_dns_record_in_pihole_add(self, mock_add, mock_delete):
        # Mock the return values
        mock_add.return_value = True
        mock_delete.return_value = True

        # Call the function
        existing_records = {}
        result = add_or_update_dns_record_in_pihole(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
            existing_records,
        )

        # Assert the result
        self.assertTrue(result)
        self.assertEqual(existing_records, {"test.com": ["1.2.3.4"]})
        mock_add.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "1.2.3.4",
        )
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
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "2.2.2.2",
            existing_records,
        )

        # Assert the result
        self.assertTrue(result)
        self.assertEqual(existing_records, {"test.com": ["2.2.2.2"]})
        mock_delete.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "1.1.1.1",
        )
        mock_add.assert_called_once_with(
            self.pihole_url,
            self.session_cookie,
            self.csrf_token,
            "test.com",
            "2.2.2.2",
        )


if __name__ == "__main__":
    unittest.main()
