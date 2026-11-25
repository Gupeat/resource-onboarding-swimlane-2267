# -*- coding: utf-8 -*-
"""S1-INT mock (stdlib only).

Serves the fictional fixture over 127.0.0.1 so the diagram pipeline can be
exercised before the real S1-INT service exists. It never reaches the network
and never reads credentials.

Run:
    python integrations/s1_int_mock/mock_server.py
    # PORT=8765 by default; override with the PORT environment variable.

Endpoints:
    GET /healthz
    GET /api/v1/interviews?project=2267
    GET /api/v1/sop-cards?project=2267
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURE = os.path.join(HERE, "fixtures", "fictional-notes.json")


def load_fixture():
    with open(FIXTURE, encoding="utf-8") as f:
        return json.load(f)


class Handler(BaseHTTPRequestHandler):
    server_version = "S1INTMock/1.0"

    def _send(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        qs = parse_qs(parsed.query)
        project = (qs.get("project") or ["2267"])[0]
        if project != "2267":
            self._send(404, {"error": "project_not_found", "project": project})
            return
        try:
            data = load_fixture()
        except (OSError, json.JSONDecodeError) as e:
            self._send(500, {"error": "fixture_unreadable", "detail": str(e)})
            return

        if parsed.path == "/healthz":
            self._send(200, {"status": "ok", "fictional": True, "source": "S1-INT-mock"})
        elif parsed.path == "/api/v1/interviews":
            self._send(200, {"meta": data["meta"], "data": data["interviews"]})
        elif parsed.path == "/api/v1/sop-cards":
            self._send(200, {"meta": data["meta"], "data": data["sop_cards"]})
        else:
            self._send(404, {"error": "not_found", "path": parsed.path})

    def log_message(self, fmt, *args):  # keep stdout quiet in acceptance runs
        if os.environ.get("S1INT_VERBOSE"):
            super().log_message(fmt, *args)


def main():
    host = os.environ.get("S1INT_HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    if host not in ("127.0.0.1", "localhost"):
        raise SystemExit("E-BIND: mock must bind to 127.0.0.1 only")
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"S1-INT mock (fictional fixture) on http://127.0.0.1:{port}")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
