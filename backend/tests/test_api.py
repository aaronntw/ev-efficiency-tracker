"""Exercise the real HTTP API against a temporary database or TEST_BASE_URL."""
import base64
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ApiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = None
        cls.workspace = tempfile.TemporaryDirectory()
        cls.base_url = os.getenv("TEST_BASE_URL")
        if not cls.base_url:
            with socket.socket() as sock:
                sock.bind(("127.0.0.1", 0))
                port = sock.getsockname()[1]
            cls.base_url = f"http://127.0.0.1:{port}"
            env = os.environ.copy()
            env.setdefault("DB_TYPE", "sqlite")
            env["SQLITE_PATH"] = str(Path(cls.workspace.name) / "test.db")
            env["TZ"] = "Asia/Kuala_Lumpur"
            cls.log = open(Path(cls.workspace.name) / "server.log", "w+")
            cls.process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.app.main:app",
                 "--host", "127.0.0.1", "--port", str(port)],
                env=env, stdout=cls.log, stderr=cls.log,
            )
        try:
            for _ in range(100):
                try:
                    if cls.request("GET", "/api/health")[0] == 200:
                        return
                except (URLError, ConnectionError):
                    pass
                if cls.process and cls.process.poll() is not None:
                    cls.log.seek(0)
                    raise RuntimeError(cls.log.read())
                time.sleep(0.1)
            raise RuntimeError("API did not become ready")
        except Exception:
            cls.tearDownClass()
            raise

    @classmethod
    def tearDownClass(cls):
        if cls.process:
            if os.name == "nt":
                # Windows venv launchers have a child interpreter holding the DB.
                subprocess.run(["taskkill", "/PID", str(cls.process.pid), "/T", "/F"],
                               check=True, capture_output=True)
            else:
                cls.process.terminate()
            cls.process.wait(timeout=10)
            cls.log.close()
        cls.workspace.cleanup()

    @classmethod
    def request(cls, method, path, body=None, authenticated=True):
        headers = {"Content-Type": "application/json"}
        user = os.getenv("TEST_AUTH_USERNAME")
        if user and authenticated:
            token = base64.b64encode(
                f"{user}:{os.environ['TEST_AUTH_PASSWORD']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {token}"
        request = Request(
            cls.base_url + path, method=method, headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            response = urlopen(request, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            raw = response.read().decode()
            if "application/json" in response.headers.get("Content-Type", ""):
                raw = json.loads(raw)
            return response.status, raw

    def test_api_roundtrip_validation_and_export(self):
        self.assertEqual(self.request("GET", "/api/health")[0], 200)
        version = self.request("GET", "/api/version")[1]
        self.assertEqual(version["version"], "1.4.4")
        self.assertIn(version["database"], ("sqlite", "postgres"))
        self.assertEqual(self.request("GET", "/openapi.json")[0], 200)
        self.assertEqual(self.request("GET", "/docs")[0], 200)
        settings = {"vehicle_name": "Test EV", "usable_battery_kwh": 60,
                    "maximum_range_km": 400, "currency": "USD"}
        self.assertEqual(self.request("PUT", "/api/settings", settings), (200, settings))
        self.assertEqual(self.request("GET", "/api/settings")[1], settings)
        self.assertEqual(self.request("PUT", "/api/settings",
                                     dict(settings, usable_battery_kwh=10))[0], 422)
        name = "Release test " + str(time.time_ns())
        status, provider = self.request("POST", "/api/providers", {"name": name})
        self.assertEqual(status, 201)
        self.assertEqual(self.request("POST", "/api/providers", {"name": name})[0], 409)
        charge = {"charged_at": "2026-10-25T12:00:00+08:00", "odometer_km": 1000,
                  "soc_before": 20, "soc_after": 80, "kwh_charged": 36,
                  "amount_paid": 18, "connector_type": "AC", "provider": name,
                  "location": "Test", "notes": "Release verification"}
        status, saved = self.request("POST", "/api/charges", charge)
        self.assertEqual(status, 201)
        self.assertEqual(saved["charged_at"], "2026-10-25T04:00:00Z")
        self.assertEqual(saved["charging_cost_per_kwh"], 0.5)
        self.assertEqual(self.request("POST", "/api/charges",
                                     dict(charge, soc_before=101))[0], 422)
        self.assertEqual(self.request("POST", "/api/charges",
                                     dict(charge, charged_at="2026-10-25T12:00:00"))[0], 422)
        path = f"/api/charges/{saved['id']}"
        updated = dict(charge, location="Updated")
        self.assertEqual(self.request("PUT", path, updated)[1]["location"], "Updated")
        status, export = self.request("GET", "/api/export.csv")
        self.assertEqual(status, 200)
        self.assertIn("Updated", export)
        self.assertEqual(self.request("PUT", f"/api/providers/{provider['id']}",
                                     {"name": name + " renamed"})[0], 200)
        rows = self.request("GET", "/api/charges")[1]
        self.assertEqual(next(row for row in rows if row["id"] == saved["id"])["provider"],
                         name + " renamed")
        self.assertEqual(self.request("DELETE", path)[0], 200)
        self.assertEqual(self.request("PUT", path, updated)[0], 404)
        self.assertEqual(self.request("DELETE", f"/api/providers/{provider['id']}")[0], 200)

    @unittest.skipUnless(os.getenv("TEST_AUTH_USERNAME"), "Basic Auth enabled in container checks")
    def test_proxy_requires_authentication(self):
        for path in ("/", "/api/charges", "/docs", "/openapi.json"):
            self.assertEqual(self.request("GET", path, authenticated=False)[0], 401)


if __name__ == "__main__":
    unittest.main()
