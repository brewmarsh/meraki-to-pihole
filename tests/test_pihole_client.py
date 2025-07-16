import sys
import os
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.clients.pihole_client import (
    authenticate_to_pihole,
    get_pihole_custom_dns_records,
    add_or_update_dns_record_in_pihole,
)

class TestPiholeClient(unittest.TestCase):

    def setUp(self):
        # Reset the cached session globals before each test
        patcher = patch('app.clients.pihole_client._pihole_sid', None)
        self.addCleanup(patcher.stop)
        patcher.start()

        patcher = patch('app.clients.pihole_client._pihole_csrf_token', None)
        self.addCleanup(patcher.stop)
        patcher.start()

    @patch('requests.post')
    @patch('app.clients.pihole_client._pihole_api_request')
    def test_authenticate_to_pihole_new_authentication(self, mock_api_request, mock_post):
        # Arrange
        mock_api_request.return_value = None  # Simulate no valid cached session
        mock_post.return_value.json.return_value = {"session": {"valid": True, "sid": "456", "csrf": "def"}}
        mock_post.return_value.raise_for_status = MagicMock()

        # Act
        sid, csrf = authenticate_to_pihole("http://pi.hole/admin", "password")

        # Assert
        self.assertEqual(sid, "456")
        self.assertEqual(csrf, "def")

    @patch('app.clients.pihole_client._pihole_api_request')
    def test_get_pihole_custom_dns_records(self, mock_request):
        # Arrange
        mock_request.return_value = {"config": {"dns": {"hosts": ["1.2.3.4 test.com", "5.6.7.8 example.com"]}}}

        # Act
        records = get_pihole_custom_dns_records("http://pi.hole", "sid", "csrf")

        # Assert
        self.assertEqual(records, {"test.com": "1.2.3.4", "example.com": "5.6.7.8"})

    @patch('app.clients.pihole_client._pihole_api_request')
    def test_get_pihole_custom_dns_records_no_records(self, mock_request):
        # Arrange
        mock_request.return_value = {"config": {"dns": {"hosts": []}}}

        # Act
        records = get_pihole_custom_dns_records("http://pi.hole", "sid", "csrf")

        # Assert
        self.assertEqual(records, {})

    @patch('app.clients.pihole_client._pihole_api_request')
    def test_add_or_update_dns_record_in_pihole_add(self, mock_request):
        # Arrange
        mock_request.return_value = {"success": True}
        existing_records = {}

        # Act
        result = add_or_update_dns_record_in_pihole("http://pi.hole", "sid", "csrf", "new.com", "9.9.9.9", existing_records)

        # Assert
        self.assertTrue(result)
        self.assertEqual(existing_records, {"new.com": "9.9.9.9"})

    @patch('app.clients.pihole_client._pihole_api_request')
    def test_add_or_update_dns_record_in_pihole_update(self, mock_request):
        # Arrange
        mock_request.return_value = {"success": True}
        existing_records = {"existing.com": "1.1.1.1"}

        # Act
        result = add_or_update_dns_record_in_pihole("http://pi.hole", "sid", "csrf", "existing.com", "2.2.2.2", existing_records)

        # Assert
        self.assertTrue(result)
        self.assertEqual(existing_records, {"existing.com": "2.2.2.2"})

    def test_add_or_update_dns_record_in_pihole_no_change(self):
        # Arrange
        existing_records = {"existing.com": "1.1.1.1"}

        # Act
        result = add_or_update_dns_record_in_pihole("http://pi.hole", "sid", "csrf", "existing.com", "1.1.1.1", existing_records)

        # Assert
        self.assertTrue(result)
