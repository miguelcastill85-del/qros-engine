"""Local TEST_ONLY authenticated read-only HTTP adapter. Loopback only.

The phone must NOT call this HTTP server across a network. A future production
HTTPS ingress and independent witness storage need separate security gates.
"""
from __future__ import annotations

import argparse
import hmac
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from protocol import EvidenceRejected, load_verified_snapshot

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")


class QrosDemoServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address, bearer_token: str, response: dict):
        if address[0] != "127.0.0.1":
            raise ValueError("LOCAL_ONLY_BIND_REQUIRED")
        if not _TOKEN.fullmatch(bearer_token):
            raise ValueError("INVALID_TOKEN_COMPLEXITY")
        self.bearer_token = bearer_token
        self.payload = json.dumps(response, ensure_ascii=True, sort_keys=True,
                                  separators=(",", ":")).encode("ascii")
        super().__init__(address, QrosHandler)


class QrosHandler(BaseHTTPRequestHandler):
    server: QrosDemoServer
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args) -> None:
        # Never log Authorization or untrusted user-provided raw paths.
        pass

    def _respond(self, status: int, payload: bytes, methods: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if methods:
            self.send_header("Allow", methods)
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        # Duplicate auth headers, malformed credentials and bearer prefix attacks fail closed.
        headers = self.headers.get_all("Authorization", [])
        if len(headers) != 1:
            return False
        prefix = "Bearer "
        candidate = headers[0]
        return (candidate.startswith(prefix) and _TOKEN.fullmatch(candidate[len(prefix):]) is not None and
                hmac.compare_digest(candidate[len(prefix):].encode("ascii"),
                                    self.server.bearer_token.encode("ascii")))

    def _route(self, method: str) -> None:
        if not self._authorized():
            self._respond(401, b'{"error":"UNAUTHORIZED"}')
            return
        url = urlsplit(self.path)
        # No user-controlled route params, query strings, fragments or filesystem paths.
        if url.query or url.fragment or url.path not in ("/v1/demo-snapshot", "/v1/status"):
            self._respond(404, b'{"error":"NOT_FOUND"}')
            return
        if method != "GET":
            self._respond(405, b'{"error":"READ_ONLY"}', "GET")
            return
        if url.path == "/v1/status":
            self._respond(200, b'{"schema":"QROS_MOBILE_STATUS_TEST_V1","mode":"TEST_ONLY_SYNTHETIC","engine_connected":false,"scientific_authority":"NONE"}')
            return
        self._respond(200, self.server.payload)

    def do_GET(self) -> None:
        self._route("GET")

    def do_POST(self) -> None:
        self._route("POST")

    def do_PUT(self) -> None:
        self._route("PUT")

    def do_PATCH(self) -> None:
        self._route("PATCH")

    def do_DELETE(self) -> None:
        self._route("DELETE")

    def do_OPTIONS(self) -> None:
        self._route("OPTIONS")


def main() -> None:
    parser = argparse.ArgumentParser(description="QROS Mobile synthetic readonly loopback server")
    parser.add_argument("--trust-root", type=Path, required=True)
    parser.add_argument("--signed-snapshot", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    # No default insecure token and never accept secrets as command-line args.
    token = os.environ.get("QROS_TEST_ONLY_BEARER_TOKEN", "")
    root_pin = os.environ.get("QROS_OUT_OF_BAND_TRUST_ROOT_SHA256", "")
    if not _TOKEN.fullmatch(token) or not re.fullmatch(r"[0-9a-f]{64}", root_pin):
        parser.error("TEST_ONLY_SECRET_AND_INDEPENDENT_TRUST_PIN_REQUIRED")
    try:
        verified = load_verified_snapshot(args.trust_root, root_pin, args.signed_snapshot)
    except EvidenceRejected as exc:
        parser.error("FAIL_CLOSED_FIXTURE_INVALID:" + str(exc))
    with QrosDemoServer(("127.0.0.1", args.port), token, verified.response) as server:
        print(f"QROS_READ_ONLY_TEST_ONLY loopback_port={server.server_port}", flush=True)
        server.serve_forever(poll_interval=0.2)


if __name__ == "__main__":
    main()
