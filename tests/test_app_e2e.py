import os
import signal
import subprocess
import time
import unittest

import requests
from fastapi.testclient import TestClient

from app.app import app


class TestAppE2E(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        command = ["uvicorn", "app.app:app", "--host", "0.0.0.0", "--port", "8001"]
        print(f"Running command: {' '.join(command)}")
        self.server = subprocess.Popen(command)
        time.sleep(1)

    def tearDown(self):
        os.kill(self.server.pid, signal.SIGTERM)

    def test_update_interval(self):
        # Given
        new_interval = "600"

        # When
        response = requests.post("http://localhost:8001/update-interval", json={"interval": new_interval})

        # Then
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Sync interval updated."})


if __name__ == "__main__":
    unittest.main()
