import asyncio
import importlib
import os
import sqlite3
import tempfile
import unittest


_database_dir = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR") or os.getcwd())
_original_connect = sqlite3.connect


def _connect_to_scratch(database, *args, **kwargs):
    if database == "automation.db":
        database = os.path.join(_database_dir.name, "automation.db")
    return _original_connect(database, *args, **kwargs)


sqlite3.connect = _connect_to_scratch
try:
    app_module = importlib.import_module("app")
finally:
    sqlite3.connect = _original_connect


class ApiOriginMiddlewareTests(unittest.TestCase):
    def request(self, method, path, headers=(), body=b""):
        async def dispatch():
            messages = []
            received = False
            raw_path = path.encode("ascii")
            host = next((value for name, value in headers if name.lower() == b"host"), b"127.0.0.1:8000")

            async def receive():
                nonlocal received
                if received:
                    return {"type": "http.disconnect"}
                received = True
                return {"type": "http.request", "body": body, "more_body": False}

            async def send(message):
                messages.append(message)

            scope = {
                "type": "http",
                "asgi": {"version": "3.0", "spec_version": "2.3"},
                "http_version": "1.1",
                "method": method,
                "scheme": "http",
                "path": path,
                "raw_path": raw_path,
                "query_string": b"",
                "root_path": "",
                "headers": list(headers),
                "client": ("127.0.0.1", 43120),
                "server": (host.decode("ascii").split(":")[0], 8000),
            }
            await app_module.app(scope, receive, send)
            response_start = next(message for message in messages if message["type"] == "http.response.start")
            return response_start["status"], dict(response_start["headers"])

        return asyncio.run(dispatch())

    def test_rejects_cross_origin_mutation_before_endpoint_runs(self):
        status, headers = self.request(
            "POST",
            "/api/run",
            [
                (b"host", b"127.0.0.1:8000"),
                (b"origin", b"https://attacker.example"),
                (b"sec-fetch-site", b"cross-site"),
                (b"content-type", b"application/json"),
            ],
            b"{}",
        )
        self.assertEqual(status, 403)
        self.assertNotIn(b"access-control-allow-origin", headers)

    def test_rejects_mutations_without_origin_or_fetch_metadata(self):
        status, _headers = self.request(
            "POST",
            "/api/run",
            [(b"host", b"127.0.0.1:8000"), (b"content-type", b"application/json")],
            b"{}",
        )
        self.assertEqual(status, 403)

    def test_vite_development_origin_reaches_the_api(self):
        origin = b"http://localhost:5173"
        status, headers = self.request(
            "POST",
            "/api/run",
            [
                (b"host", b"127.0.0.1:8000"),
                (b"origin", origin),
                (b"sec-fetch-site", b"cross-site"),
                (b"content-type", b"application/json"),
            ],
            b"{}",
        )
        self.assertEqual(status, 422)
        self.assertEqual(headers.get(b"access-control-allow-origin"), origin)

    def test_rejects_requests_with_non_loopback_host(self):
        status, _headers = self.request(
            "GET",
            "/api/status",
            [(b"host", b"attacker.example:8000"), (b"origin", b"http://attacker.example")],
        )
        self.assertEqual(status, 403)


if __name__ == "__main__":
    unittest.main()
