"""Item 1100: Docker only fronts clark's own server, which runs on the Mac (docker/front.command, compose.front.yaml, nginx.front.conf.template).

Quick tier: no Docker, no nginx, no browser. docker, curl and the Mac server are stubs first on PATH that record their arguments. The proxy's
Host and Origin rules are read out of the settings file and applied by a small stand-in for nginx's map, so hostile inputs are checked
against what the file says, not against what we hope.
Run: python3 dev/run_tests.py test_docker_front"""
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

DOCKER = ROOT / "docker"
TEMPLATE = (DOCKER / "nginx.front.conf.template").read_text(encoding="utf-8")
COMPOSE = (DOCKER / "compose.front.yaml").read_text(encoding="utf-8")


def read_map(name, port=8766, sport=8767):
    """The rows of `map $http_x $name { ... }` from the template with the two ports filled in, as {from: to}, plus 'default'."""
    body = re.search(r"map \$http_\w+ \$" + name + r" \{(.*?)\n\}", TEMPLATE, re.S).group(1)
    rows = {}
    for key, value in re.findall(r'^\s*(default|"[^"]*")\s+("[^"]*");', body, re.M):
        fill = lambda s: s.strip('"').replace("${CLARK_PORT}", str(port)).replace("${CLARK_SERVER_PORT}", str(sport))
        rows[fill(key) if key != "default" else key] = fill(value)
    return rows


def through(name, sent, port=8766, sport=8767):
    """What the server would be sent for a header value `sent` (None: header absent, which nginx passes on as absent)."""
    if sent is None:
        return None
    rows = read_map(name, port, sport)
    return rows.get(sent, sent if rows["default"] == "$http_" + ("host" if name == "clark_host" else "origin") else rows["default"])


class ProxyRules(unittest.TestCase):
    def test_the_front_port_becomes_the_server_port_only_for_this_computers_own_names(self):
        self.assertEqual(through("clark_host", "127.0.0.1:8766"), "127.0.0.1:8767")
        self.assertEqual(through("clark_host", "localhost:8766"), "localhost:8767")
        self.assertEqual(through("clark_origin", "http://127.0.0.1:8766"), "http://127.0.0.1:8767")
        self.assertEqual(through("clark_origin", "http://localhost:8766"), "http://localhost:8767")

    def test_a_bad_host_or_another_sites_origin_goes_on_unchanged_so_the_server_refuses_it(self):
        for host in ("evil.example", "evil.example:8766", "192.168.1.5:8766", "127.0.0.1:8767", "127.0.0.1:9999", "127.0.0.1", "LOCALHOST:8766",
                     "127.0.0.1:8766.evil.example", "localhost:8766@evil.example", ""):
            self.assertEqual(through("clark_host", host), host, host)
        for origin in ("http://evil.example", "https://evil.example:8766", "null", "http://127.0.0.1:8767", "http://localhost:9999",
                       "https://localhost:8766", "http://localhost:8766.evil.example", ""):
            self.assertEqual(through("clark_origin", origin), origin, origin)

    def test_no_origin_stays_no_origin(self):
        self.assertIsNone(through("clark_origin", None))

    def test_ports_are_filled_in_from_the_settings_not_fixed(self):
        self.assertEqual(through("clark_host", "localhost:8800", 8800, 8900), "localhost:8900")
        self.assertEqual(through("clark_host", "localhost:8766", 8800, 8900), "localhost:8766")

    def test_the_proxy_passes_the_changed_host_and_origin_and_adds_nothing_the_server_could_trust(self):
        self.assertIn("proxy_set_header Host $clark_host;", TEMPLATE)
        self.assertIn("proxy_set_header Origin $clark_origin;", TEMPLATE)
        code = "\n".join(l for l in TEMPLATE.splitlines() if not l.lstrip().startswith("#"))
        for word in ("X-Forwarded", "X-Real-IP", "Forwarded", "0.0.0.0", "proxy_set_header Origin \"", "allow ", "listen 80;"):
            self.assertNotIn(word, code)
        self.assertEqual(re.findall(r"proxy_pass (\S+);", code), ["http://host.docker.internal:${CLARK_SERVER_PORT}"])

    def test_the_down_page_is_plain_words_and_names_the_command(self):
        self.assertIn("error_page 502 503 504 @down;", TEMPLATE)
        self.assertIn("clark is not running", TEMPLATE)
        self.assertIn("bash docker/front.command server", TEMPLATE)


class ComposeRules(unittest.TestCase):
    def test_the_port_is_published_to_this_computer_only(self):
        ports = re.findall(r'^\s*-\s*"([^"]*:\d+)"', COMPOSE, re.M)
        self.assertEqual(ports, ["127.0.0.1:${CLARK_PORT:-8766}:8080"])

    def test_it_holds_no_clark_code_no_data_and_no_server(self):
        code = "\n".join(l for l in COMPOSE.splitlines() if not l.lstrip().startswith("#"))
        for word in ("python", "CLARK_CONTAINER", "CLARK_DATA", "/data", "build:", "user:", "network_mode"):
            self.assertNotIn(word, code)
        self.assertNotRegex(code, r"\bprivileged:")
        self.assertEqual(re.findall(r"source: (\S+)", code), ["./nginx.front.conf.template"])
        self.assertEqual(len(re.findall(r"read_only: true", code)), 2)      # the mount and the container

    def test_it_is_locked_down_and_does_not_come_back_alone(self):
        for line in ("cap_drop:", "- ALL", "no-new-privileges:true", 'restart: "no"', "host.docker.internal:host-gateway"):
            self.assertIn(line, COMPOSE)
        self.assertRegex(COMPOSE, r"image: \S+:\d+\.\d+\.\d+")       # pinned by tag, never latest
        self.assertNotIn(":latest", COMPOSE)

    def test_the_old_compose_file_is_not_changed_so_both_routes_exist(self):
        self.assertTrue((DOCKER / "compose.yaml").exists())


class Script(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.bin = Path(self.tmp) / "bin"
        self.bin.mkdir()
        self.log = Path(self.tmp) / "calls.log"
        real = shutil.which("python3")
        self.stub("docker", 'echo "docker $@ port=$CLARK_PORT sport=$CLARK_SERVER_PORT" >> "$CALLS"')
        self.stub("curl", 'echo "curl $@" >> "$CALLS"; [ "$FAKE_HEALTH" = 1 ] && echo \'{"ok": true}\' && exit 0; exit 7')
        self.stub("python3", f'if [ "$1" = "-m" ]; then echo "python3 $@ port=$CLARK_PUBLISHED_PORT" >> "$CALLS"; exit 0; fi; exec {real} "$@"')

    def stub(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
        path.chmod(0o755)

    def run_script(self, *args, health=True, **env):
        e = {"PATH": f"{self.bin}:{os.environ['PATH']}", "HOME": self.tmp, "CALLS": str(self.log), "FAKE_HEALTH": "1" if health else "0",
             "CLARK_DATA_DIR": f"{self.tmp}/data"}
        e.update(env)
        e = {k: v for k, v in e.items() if v is not None}
        return subprocess.run(["bash", str(DOCKER / "front.command"), *args], env=e, capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def calls(self):
        return self.log.read_text(encoding="utf-8").splitlines() if self.log.exists() else []

    def test_with_the_server_running_it_starts_the_front_on_the_default_ports(self):
        r = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls()[-1], f"docker compose -f {ROOT}/docker/compose.front.yaml up -d port=8766 sport=8767")
        self.assertIn("http://localhost:8766", r.stdout)

    def test_the_container_started_first_is_refused_before_docker_is_reached(self):
        r = self.run_script(health=False)
        self.assertEqual(r.returncode, 1)
        self.assertIn("clark is not running on this Mac yet", r.stderr)
        self.assertIn("bash docker/front.command server", r.stderr)
        self.assertFalse([c for c in self.calls() if c.startswith("docker")], "docker must not start without the Mac server")

    def test_the_server_is_asked_on_loopback_only(self):
        self.run_script(CLARK_SERVER_PORT="8800")
        self.assertIn("curl -fsS --max-time 3 http://127.0.0.1:8800/health", self.calls())

    def test_bad_ports_stop_everything(self):
        for name in ("CLARK_PORT", "CLARK_SERVER_PORT"):
            for bad in ("abc", "80", "1023", "65536", "99999999", "8766;touch x", "$(id)", "-1", "8 8", "0x1F90", "८०८०"):
                r = self.run_script(**{name: bad})
                self.assertEqual(r.returncode, 1, (name, bad))
                self.assertIn(f"{name} must be a number from 1024 to 65535", r.stderr)
                self.assertEqual(self.calls(), [], (name, bad))
        self.assertFalse((Path(self.tmp) / "x").exists())

    def test_empty_ports_are_refused_not_silently_defaulted(self):
        self.assertEqual(self.run_script(CLARK_PORT="").returncode, 1)
        self.assertEqual(self.run_script(CLARK_SERVER_PORT="").returncode, 1)

    def test_the_two_ports_must_differ(self):
        r = self.run_script(CLARK_PORT="8800", CLARK_SERVER_PORT="8800")
        self.assertEqual(r.returncode, 1)
        self.assertIn("two different numbers", r.stderr)
        self.assertEqual(self.calls(), [])

    def test_a_synced_data_folder_stops_before_anything_starts(self):
        for mode in ("", "server"):
            r = self.run_script(*([mode] if mode else []), CLARK_DATA_DIR=f"{self.tmp}/OneDrive - Test/clark")
            self.assertEqual(r.returncode, 1, mode)
            self.assertIn("because it is inside OneDrive", r.stderr)
            self.assertEqual(self.calls(), [])

    def test_no_docker_says_to_use_the_terminal_route(self):
        (self.bin / "docker").unlink()
        r = subprocess.run(["bash", str(DOCKER / "front.command")], env={"PATH": f"{self.bin}:/usr/bin:/bin", "HOME": self.tmp, "CALLS": str(self.log),
                           "FAKE_HEALTH": "1", "CLARK_DATA_DIR": f"{self.tmp}/data"}, capture_output=True, text=True, cwd=self.tmp, timeout=60)
        if shutil.which("docker", path="/usr/bin:/bin"):
            self.skipTest("a real docker is in /usr/bin")
        self.assertEqual(r.returncode, 1)
        self.assertIn("bash clark.command", r.stderr)

    def test_a_docker_failure_says_clark_itself_is_still_running(self):
        self.stub("docker", "exit 1")
        r = self.run_script(CLARK_SERVER_PORT="8800")
        self.assertEqual(r.returncode, 1)
        self.assertIn("clark itself is still running", r.stderr)
        self.assertIn("http://127.0.0.1:8800", r.stderr)

    def test_server_starts_clarks_own_server_on_the_server_port_and_names_the_front_port(self):
        r = self.run_script("server", CLARK_PORT="8800", CLARK_SERVER_PORT="8900")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(), [f"python3 -m clark --data {self.tmp}/data --port 8900 port=8800"])

    def test_stop_runs_compose_down_and_unknown_words_do_nothing(self):
        self.assertEqual(self.run_script("stop").returncode, 0)
        self.assertEqual(self.calls(), [f"docker compose -f {ROOT}/docker/compose.front.yaml down port= sport="])
        self.log.unlink()
        r = self.run_script("--rm-everything")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(self.calls(), [])


class MovementFilesAreNotInTheWay(unittest.TestCase):
    def test_no_server_or_launcher_file_is_touched_by_this_route(self):
        names = subprocess.run(["git", "diff", "--name-only", "origin/main", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.split()
        guarded = {"schema.sql", "store.py", "changes.py", "use_cases_read.py", "publish.py", "launch.py", "package.py", "brands.py", "excel_import.py"}
        for n in names:
            self.assertNotIn(Path(n).name, guarded, n)
            self.assertFalse(n.startswith("src/clark/server/") or n == "src/clark/server.py", n)


if __name__ == "__main__":
    unittest.main()
