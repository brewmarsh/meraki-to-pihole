import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app


class TestUpdateInterval(unittest.TestCase):
    def setUp(self):

        self.client = TestClient(app, client=("127.0.0.1", 12345))
        self.interval_file_path = Path("/app/sync_interval.txt")
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()

    def tearDown(self):
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()

    def test_update_interval(self):
        # Given
        new_interval = 600

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Sync interval updated."})
        content = self.interval_file_path.read_text().strip()
        self.assertEqual(content, str(new_interval))

    def test_update_interval_invalid(self):
        # Given
        new_interval = "not a number"

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 422)


    def test_update_interval_zero_invalid(self):
        # Given
        new_interval = 0

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 422)


    def test_update_interval_negative_invalid(self):
        # Given
        new_interval = -10

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 422)

if __name__ == "__main__":
    unittest.main()
