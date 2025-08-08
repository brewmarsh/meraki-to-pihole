import unittest
from unittest.mock import patch, MagicMock
from app.clients.pihole_client import PiholeClient

class TestPiholeClient(unittest.TestCase):

    @patch('app.clients.pihole_client.requests.Session')
    def test_authenticate_success(self, mock_session):
        # Arrange
        mock_response = MagicMock()
        mock_response.json.return_value = {"session": {"valid": True, "sid": "123", "csrf": "abc"}}
        mock_session.return_value.post.return_value = mock_response

        # Act
        client = PiholeClient("http://pi.hole", "password")

        # Assert
        self.assertEqual(client.sid, "123")
        self.assertEqual(client.csrf_token, "abc")

    @patch('app.clients.pihole_client.requests.Session')
    def test_get_custom_dns_records_success(self, mock_session):
        # Arrange
        client = PiholeClient("http://pi.hole", "password")
        client.sid = "123"
        client.csrf_token = "abc"
        mock_response = MagicMock()
        mock_response.json.return_value = {"config": {"dns": {"hosts": ["1.2.3.4 test.com", "5.6.7.8 example.com"]}}}
        mock_session.return_value.request.return_value = mock_response

        # Act
        records = client.get_custom_dns_records()

        # Assert
        self.assertEqual(records, {"test.com": "1.2.3.4", "example.com": "5.6.7.8"})

    @patch('app.clients.pihole_client.PiholeClient.get_custom_dns_records')
    @patch('app.clients.pihole_client.PiholeClient._api_request')
    def test_add_or_update_dns_record_add(self, mock_api_request, mock_get_records):
        # Arrange
        mock_get_records.return_value = {}
        mock_api_request.return_value = {"success": True}
        client = PiholeClient("http://pi.hole", "password")
        client.sid = "123"
        client.csrf_token = "abc"

        # Act
        result = client.add_or_update_dns_record("new.com", "9.9.9.9")

        # Assert
        self.assertTrue(result)
        mock_api_request.assert_called_once_with("PUT", "/api/config/dns/hosts/9.9.9.9%20new.com")

    @patch('app.clients.pihole_client.PiholeClient.get_custom_dns_records')
    @patch('app.clients.pihole_client.PiholeClient._api_request')
    def test_add_or_update_dns_record_update(self, mock_api_request, mock_get_records):
        # Arrange
        mock_get_records.return_value = {"existing.com": "1.1.1.1"}
        mock_api_request.return_value = {"success": True}
        client = PiholeClient("http://pi.hole", "password")
        client.sid = "123"
        client.csrf_token = "abc"

        # Act
        result = client.add_or_update_dns_record("existing.com", "2.2.2.2")

        # Assert
        self.assertTrue(result)
        mock_api_request.assert_called_once_with("PUT", "/api/config/dns/hosts/2.2.2.2%20existing.com")

    @patch('app.clients.pihole_client.PiholeClient.get_custom_dns_records')
    @patch('app.clients.pihole_client.PiholeClient._api_request')
    def test_add_or_update_dns_record_no_change(self, mock_api_request, mock_get_records):
        # Arrange
        mock_get_records.return_value = {"existing.com": "1.1.1.1"}
        client = PiholeClient("http://pi.hole", "password")
        client.sid = "123"
        client.csrf_token = "abc"

        # Act
        result = client.add_or_update_dns_record("existing.com", "1.1.1.1")

        # Assert
        self.assertTrue(result)
        mock_api_request.assert_not_called()

if __name__ == '__main__':
    unittest.main()
