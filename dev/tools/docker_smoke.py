"""The Docker smoke test (row 626; development only, never shipped).

Run (needs Docker running, from a checkout whose pages are built, or from the unzipped download):
    python3 dev/tools/docker_smoke.py [--port 8799] [--wait 120]

It starts clark the way a person does, with docker/compose.yaml, a new empty data folder and a spare port, waits for the page to answer,
checks what must hold from outside the container, and always stops it again (docker compose down) and removes the data folder:
 - /health answers 200 with ok true and a version;
 - the page (GET /) answers 200 with this run's token in its boot block;
 - a request with a Host that is not this computer is refused (403), for the page and for /health;
 - a change sent without the token, or with a wrong one, is refused (403).
It prints one line per check (PASS or FAIL) and exits 0 only when every check passed, 1 when one failed, 2 when clark never answered.
Not checked here: that a change saves and that a backup is written (they need the token's own page calls; a later slice).
Standard library only. The checks take the two doors (the commands, the HTTP calls) as arguments, so tests/test_docker_smoke.py
runs the logic with fakes where Docker is absent.
"""
import argparse
import http.client
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
COMPOSE = REPO / "docker" / "compose.yaml"
TOKEN_HEADER = "X-Clark-Token"
BOOT = re.compile(r'id="clark-boot">(\{.*?\})</script>', re.S)


def http_fetch(port):
    """The real HTTP door: fetch(method, path, headers, body) -> (status, bytes), to 127.0.0.1:port."""
    def fetch(method, path, headers=None, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        try:
            conn.request(method, path, body=body, headers=headers or {})
            r = conn.getresponse()
            return r.status, r.read()
        finally:
            conn.close()
    return fetch


def checks(fetch, port):
    """Run every check. Returns a list of (name, passed, detail). `fetch` raising OSError is a failed check, not a crash."""
    out = []

    def check(name, fn):
        try:
            ok, detail = fn()
        except (OSError, ValueError) as e:
            ok, detail = False, type(e).__name__
        out.append((name, bool(ok), detail))

    def health():
        status, body = fetch("GET", "/health", {})
        data = json.loads(body or b"{}")
        return status == 200 and data.get("ok") is True and bool(data.get("version")), f"status {status}"

    token = {}

    def page():
        status, body = fetch("GET", "/", {})
        m = BOOT.search(body.decode("utf-8", "replace"))
        token["value"] = json.loads(m.group(1)).get("token", "") if m else ""
        return status == 200 and bool(token["value"]), f"status {status}, token {'there' if token['value'] else 'missing'}"

    def foreign_host(path):
        def run():
            status, _ = fetch("GET", path, {"Host": f"evil.example:{port}"})
            return status == 403, f"status {status}"
        return run

    def change(headers):
        def run():
            status, _ = fetch("POST", "/api/change", {"Content-Type": "application/json", **headers}, b"{}")
            return status == 403, f"status {status}"
        return run

    check("health says ok with a version", health)
    check("the page carries a token", page)
    check("a foreign Host is refused on the page", foreign_host("/"))
    check("a foreign Host is refused on /health", foreign_host("/health"))
    check("a change without a token is refused", change({}))
    check("a change with a wrong token is refused", change({TOKEN_HEADER: "wrong-" + token.get("value", "")}))
    return out


def run(port=8799, wait_seconds=120, command=subprocess.run, fetch=None, pause=None, say=print, data_dir=None):
    """Start, check, stop. `command(args, env=..., ...)` is subprocess.run's shape; `pause(seconds)` waits (never a sleep call)."""
    fetch = fetch or http_fetch(port)
    pause = pause or threading.Event().wait
    own_dir = data_dir is None
    data_dir = data_dir or tempfile.mkdtemp(prefix="clark-smoke-")
    env = {**os.environ, "CLARK_DATA_DIR": str(data_dir), "CLARK_PORT": str(port)}
    base = ["docker", "compose", "-f", str(COMPOSE)]
    try:
        up = command(base + ["up", "-d"], env=env, capture_output=True, text=True)
        if up.returncode != 0:
            say("FAIL docker compose up did not start clark")
            return 2
        for _ in range(int(wait_seconds)):
            try:
                if fetch("GET", "/health", {})[0] == 200:
                    break
            except OSError:
                pass
            pause(1)
        else:
            say("FAIL clark did not answer in time")
            return 2
        results = checks(fetch, port)
        for name, ok, detail in results:
            say(f"{'PASS' if ok else 'FAIL'} {name} ({detail})")
        return 0 if all(ok for _, ok, _ in results) else 1
    finally:
        command(base + ["down"], env=env, capture_output=True, text=True)
        if own_dir:
            shutil.rmtree(data_dir, ignore_errors=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--port", type=int, default=8799)
    p.add_argument("--wait", type=int, default=120)
    a = p.parse_args(argv)
    if shutil.which("docker") is None:
        print("Docker is not installed or not on the path; nothing was started.")
        return 2
    return run(a.port, a.wait)


if __name__ == "__main__":
    sys.exit(main())
