import sys
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app

# Add the project root to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


class TestApp(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        # Ensure a clean state for the sync interval file
        self.interval_file_path = Path("/app/sync_interval.txt")
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()

        # Ensure a clean state for the log file
        self.log_file_path = Path("/app/logs/sync.log")
        self.log_file_path.parent.mkdir(exist_ok=True)
        self.log_file_path.write_text("test log entry")

    def tearDown(self):
        # Clean up the sync interval file after tests
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()
        # Clean up the log file
        if self.log_file_path.exists():
            self.log_file_path.unlink()

    def test_update_interval(self):
        # Given
        new_interval = "600"

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Sync interval updated."})

        # Verify the file was written correctly
        content = self.interval_file_path.read_text().strip()
        self.assertEqual(content, new_interval)

    def test_update_interval_invalid(self):
        # Given
        new_interval = "not a number"

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "Invalid interval."})

        # Verify the file was not created
        self.assertFalse(self.interval_file_path.exists())

    def test_clear_log(self):
        # Given
        self.assertTrue(self.log_file_path.exists())
        self.assertGreater(self.log_file_path.stat().st_size, 0)

        # When
        response = self.client.post("/clear-log", json={"log": "sync"})

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Sync log cleared."})
        self.assertTrue(self.log_file_path.exists())
        self.assertEqual(self.log_file_path.stat().st_size, 0)

    def test_clear_log_invalid(self):
        # Given
        self.assertTrue(self.log_file_path.exists())
        initial_size = self.log_file_path.stat().st_size

        # When
        response = self.client.post("/clear-log", json={"log": "invalid"})

        # Then
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"message": "Invalid log type."})
        self.assertEqual(self.log_file_path.stat().st_size, initial_size)

if __name__ == "__main__":
    unittest.main()
