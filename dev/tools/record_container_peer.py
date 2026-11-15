#!/usr/bin/env python3
"""item 511: record the peer address clark sees on the first request inside a container (design 427, option B).

Why: server.py (local_peer, container_gateway) accepts the container's default gateway as the one non-loopback peer. That
rests on Docker presenting the gateway as the peer of a published-port request. It was never observed on a real run.
This tool is the recording step for that run. It listens like the container does (0.0.0.0), answers the first request,
and prints one JSON line: the peer address, the default gateway read the way server.py reads it, and whether
server.local_peer would accept that peer. It never starts clark and serves nothing else.

Procedure (needs Docker; see docs/handoff/design-427-docker-first-start.md, "Recording the peer"):
  docker compose -f docker/compose.yaml run --rm --service-ports --no-deps --entrypoint python3 clark \
      /clark/dev/tools/record_container_peer.py --port 8766
  then, on the host, open http://127.0.0.1:8766/ once. The line printed is the record. "accepted": false means clark
  would refuse the person's first request on that Docker.
Standard library only, Python 3.9.
"""
import argparse
import json
import os
import socketserver
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "src"))
from clark import server as sv  # noqa: E402


HEALTH_PATH = "/health"  # what docker/compose.yaml's healthcheck requests, from 127.0.0.1
CONNECTION_TIMEOUT = 5


class PeerServer(HTTPServer):
    """HTTPServer without its reverse lookup. HTTPServer.server_bind asks socket.getfqdn for the listening host's name,
    a lookup that can stall for seconds on a machine whose resolver is slow, before the server is ready. The tool never
    uses the name, so bind the plain way and fill server_name and server_port from the address itself."""

    def server_bind(self):
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = host
        self.server_port = port


def record(peer):
    """The record for one request's peer address: what clark's own rule says about it."""
    gateway = sv.container_gateway()
    return {
        "peer": peer,
        "gateway": gateway,
        "container_mode": sv.container_mode(),
        "is_gateway": gateway is not None and peer == gateway,
        "accepted": sv.local_peer(peer),
    }


def make_handler(sink):
    class Handler(BaseHTTPRequestHandler):
        timeout = CONNECTION_TIMEOUT  # a connection that sends nothing is dropped, not waited on

        def do_GET(self):
            if self.path.split("?", 1)[0] == HEALTH_PATH:
                body = b"ok\n"  # the compose healthcheck is not the person's request: answer it, record nothing
            else:
                sink.append(record(self.client_address[0]))
                body = b"peer recorded\n"
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass
    return Handler


def run(host, port, out=None):
    """Answer requests until one is a real first request (not the healthcheck, not an empty connection), print its
    record as one JSON line, return it."""
    sink = []
    httpd = PeerServer((host, port), make_handler(sink))
    try:
        while not sink:
            httpd.handle_request()
    finally:
        httpd.server_close()
    line = json.dumps(sink[0], sort_keys=True)
    print(line, file=out or sys.stdout, flush=True)
    return sink[0]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8766)
    ap.add_argument("--host", default=sv.CONTAINER_BIND)
    a = ap.parse_args(argv)
    run(a.host, a.port)
    return 0


if __name__ == "__main__":
    sys.exit(main())
