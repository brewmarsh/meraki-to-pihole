import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app


class TestClearLog(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.log_file_path = Path("/app/logs/sync.log")
        self.log_file_path.parent.mkdir(exist_ok=True)
        self.log_file_path.write_text("test log entry")

    def tearDown(self):
        if self.log_file_path.exists():
            self.log_file_path.unlink()

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
