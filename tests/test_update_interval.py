import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.app import app


class TestUpdateInterval(unittest.TestCase):
    def setUp(self):
        print("Setting up TestUpdateInterval")
        self.client = TestClient(app)
        self.interval_file_path = Path("/app/sync_interval.txt")
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()

    def tearDown(self):
        if self.interval_file_path.exists():
            self.interval_file_path.unlink()

    def test_update_interval(self):
        # Given
        new_interval = "600"

        # When
        from app.app import update_interval
        from fastapi import Request
        from pydantic import BaseModel
        class UpdateIntervalRequest(BaseModel):
            interval: int
        request = Request({"type": "http", "method": "POST", "path": "/update-interval"})
        data = UpdateIntervalRequest(interval=new_interval)
        response = update_interval(request, data)

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.body, b'{"message":"Sync interval updated."}')
        content = self.interval_file_path.read_text().strip()
        self.assertEqual(content, new_interval)

    def test_update_interval_invalid(self):
        # Given
        new_interval = "not a number"

        # When
        response = self.client.post("/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
