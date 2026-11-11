"""item 427: the container setting in src/clark/server.py (guarded). The default, with no setting, is the Mac's: 127.0.0.1 only.

Run: python3 dev/run_tests.py test_server_container
Only the one setting (CLARK_CONTAINER=1, inside a container) lets the server listen on 0.0.0.0 and trust the container's
gateway as a local peer. Nothing here starts a container or needs Docker.
"""
import http.client
import io
import json
import re
import threading
import unittest
from unittest import mock

from _paths import ROOT, SRC  # noqa: F401  (SRC puts src/ on the path)

from clark import server as sv

ROUTE = ("Iface\tDestination\tGateway\tFlags\tRefCnt\tUse\tMetric\tMask\tMTU\tWindow\tIRTT\n"
         "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
         "eth0\t000012AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n")      # default via 172.18.0.1


def in_container(gateway="172.18.0.1"):
    """The server as the shipped container runs it: the setting on, the marker file there, the gateway as given."""
    return (mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}),
            mock.patch("os.path.exists", lambda p: p == "/.dockerenv"),
            mock.patch.object(sv, "container_gateway", lambda: gateway))


class Handler:
    """Enough of a request handler for csp_local: a peer, a Host and some headers."""
    def __init__(self, peer, host="127.0.0.1:8766", headers=None):
        self.client_address = (peer, 50000)
        self.headers = {"Host": host, **(headers or {})}

    def host_ok(self):
        return sv.host_allowed(self.headers.get("Host"))


def local(handler):
    return sv.csp_local(handler)


class Default(unittest.TestCase):
    """With no setting nothing changes."""

    def test_it_is_not_container_mode(self):
        self.assertFalse(sv.container_mode())

    def test_only_loopback_peers_are_local(self):
        for peer in ("127.0.0.1", "::1", "::ffff:127.0.0.1"):
            self.assertTrue(sv.local_peer(peer), peer)
        for peer in ("172.18.0.1", "172.17.0.1", "192.168.1.10", "10.0.0.5", "0.0.0.0", ""):
            self.assertFalse(sv.local_peer(peer), peer)

    def test_the_gateway_is_not_trusted_without_the_setting(self):
        with mock.patch.object(sv, "container_gateway", lambda: "172.18.0.1"):
            self.assertFalse(sv.local_peer("172.18.0.1"))
            self.assertFalse(local(Handler("172.18.0.1")))

    def test_the_server_still_refuses_every_other_address(self):
        for address in ("0.0.0.0", "", "localhost", "::", "192.168.1.10"):
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer((address, 0))

    def test_the_setting_alone_is_not_enough(self):
        """Set on a Mac (no container marker file): still the Mac's way."""
        with mock.patch.dict("os.environ", {"CLARK_CONTAINER": "1"}), mock.patch("os.path.exists", lambda p: False):
            self.assertFalse(sv.container_mode())
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer(("0.0.0.0", 0))
            self.assertFalse(sv.local_peer("172.18.0.1"))

    def test_the_marker_file_alone_is_not_enough(self):
        with mock.patch("os.path.exists", lambda p: p == "/.dockerenv"):
            self.assertFalse(sv.container_mode())

    def test_any_other_value_is_off(self):
        for value in ("", "0", "true", "yes", "1 "):
            with mock.patch.dict("os.environ", {"CLARK_CONTAINER": value}), mock.patch("os.path.exists", lambda p: True):
                self.assertFalse(sv.container_mode(), repr(value))


class InAContainer(unittest.TestCase):
    def setUp(self):
        for patch in in_container():
            patch.start()
            self.addCleanup(patch.stop)

    def test_it_is_container_mode(self):
        self.assertTrue(sv.container_mode())

    def test_the_podman_marker_counts_too(self):
        with mock.patch("os.path.exists", lambda p: p == "/run/.containerenv"):
            self.assertTrue(sv.container_mode())

    def test_it_may_listen_on_0_0_0_0_and_nothing_else_new(self):
        sv.LocalServer(("0.0.0.0", 0)).server_close()
        sv.LocalServer(("127.0.0.1", 0)).server_close()
        for address in ("", "::", "192.168.1.10", "localhost"):
            with self.assertRaisesRegex(ValueError, "127.0.0.1 only"):
                sv.LocalServer((address, 0))

    def test_the_gateway_and_loopback_are_local_and_no_other_peer(self):
        self.assertTrue(sv.local_peer("172.18.0.1"))
        self.assertTrue(sv.local_peer("127.0.0.1"))
        for peer in ("172.18.0.5", "172.18.0.2", "172.17.0.1", "192.168.1.10", "10.0.0.5", ""):
            self.assertFalse(sv.local_peer(peer), peer)

    def test_no_gateway_means_loopback_only(self):
        with mock.patch.object(sv, "container_gateway", lambda: None):
            self.assertFalse(sv.local_peer("172.18.0.1"))
            self.assertFalse(sv.local_peer(""))
            self.assertFalse(sv.local_peer(None))
            self.assertTrue(sv.local_peer("127.0.0.1"))

    def test_the_host_and_origin_checks_are_unchanged(self):
        gateway = "172.18.0.1"
        self.assertTrue(local(Handler(gateway)))
        self.assertTrue(local(Handler(gateway, headers={"Origin": "http://127.0.0.1:8766"})))
        self.assertTrue(local(Handler(gateway, host="localhost:8766")))
        for host in ("evil.example", "172.18.0.1:8766", "0.0.0.0:8766", "127.0.0.1.evil.example", "", None):
            self.assertFalse(local(Handler(gateway, host=host)), repr(host))
        self.assertFalse(local(Handler(gateway, headers={"Origin": "http://evil.example"})))
        self.assertFalse(local(Handler(gateway, headers={"Origin": "http://127.0.0.1:9999"})))
        self.assertFalse(local(Handler(gateway, headers={"Sec-Fetch-Site": "cross-site"})))
        self.assertFalse(local(Handler("172.18.0.5")))


class Compose(unittest.TestCase):
    """The compose file's published port is a security control (see docs/handoff/design-427-docker-first-start.md)."""

    @staticmethod
    def published(text):
        """The published ports as a list of entries, and the network_mode values. A short entry ("host:port:port", any quoting) is
        {"short": text}; a long entry is its keys (target, published, host_ip). Read by structure, whatever the indentation."""
        entries, modes, inside, base = [], [], False, 0
        for line in text.splitlines():
            line = line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indent, body = len(line) - len(line.lstrip()), line.strip()
            if body.startswith("network_mode:"):
                modes.append(body.partition(":")[2].strip().strip("\"'"))
            if body == "ports:":
                inside, base = True, indent
                continue
            if inside and indent <= base and not body.startswith("- "):
                inside = False
            if not inside:
                continue
            if body.startswith("- "):
                entries.append({})
                body = body[2:].strip()
                if not re.match(r"^\w+:(\s|$)", body):
                    entries[-1]["short"] = body.strip("\"'")
                    continue
            key, _, value = body.partition(":")
            if entries:
                entries[-1][key.strip()] = value.strip().strip("\"'")
        return entries, modes

    def bad_ports(self, text):
        """What is wrong with how the text publishes its ports (an empty list when it is 127.0.0.1 only)."""
        entries, modes = self.published(text)
        problems = ["network_mode: " + m for m in modes if m == "host"]
        if not entries:
            problems.append("no published port found")
        for entry in entries:
            if "short" in entry:
                if not entry["short"].startswith("127.0.0.1:"):
                    problems.append(entry["short"])
            elif entry.get("host_ip") != "127.0.0.1":
                problems.append(repr(entry))
        return problems

    def test_every_published_port_is_on_127_0_0_1_only(self):
        """The short form, the long form (host_ip), a host taken from an env variable and network_mode: host are all checked."""
        text = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertEqual(self.bad_ports(text), [])

    def test_the_port_check_catches_every_way_of_publishing_wide(self):
        head = "services:\n  clark:\n    image: x\n"
        long_form = "    ports:\n      - target: 8766\n        published: 8766\n"
        good = ['    ports:\n      - "127.0.0.1:8766:8766"\n',
                long_form + "        host_ip: 127.0.0.1\n"]
        bad = ['    ports:\n      - "8766:8766"\n',
               '    ports:\n      - "0.0.0.0:8766:8766"\n',
               '    ports:\n      - "${CLARK_HOST:-127.0.0.1}:8766:8766"\n',
               "    ports:\n      - 8766:8766\n",
               long_form,
               long_form + "        host_ip: 0.0.0.0\n",
               long_form + "        host_ip: ${CLARK_HOST}\n",
               '    network_mode: host\n    ports:\n      - "127.0.0.1:8766:8766"\n',
               '    network_mode: "host"\n']
        for block in good:
            self.assertEqual(self.bad_ports(head + block), [], block)
        for block in bad:
            self.assertTrue(self.bad_ports(head + block), block)

    def test_the_port_check_reads_ranges_protocol_suffixes_and_ipv6_samples(self):
        """Ranges, /tcp and /udp suffixes and a bracketed IPv6 host are read like any other short entry: only 127.0.0.1 passes
        (the check is strict on purpose: [::1] is flagged too, the compose file says 127.0.0.1)."""
        head = "services:\n  clark:\n    image: x\n    ports:\n"
        good = ['      - "127.0.0.1:8080:80/tcp"\n', "      - 127.0.0.1:8080:80/udp\n",
                '      - "127.0.0.1:8000-8010:8000-8010"\n', '      - "127.0.0.1:8000-8010:8000-8010/tcp"\n']
        bad = ['      - "8000-8010:8000-8010"\n', "      - 8080:80/tcp\n", '      - "0.0.0.0:8080:80/udp"\n',
               '      - "0.0.0.0:8000-8010:8000-8010/tcp"\n', '      - "[::1]:8080:80"\n', "      - [::1]:8080:80\n",
               '      - "[::]:8080:80/tcp"\n', '      - "127.0.0.1:8080:80"\n      - "8081:81/udp"\n']
        for entry in good:
            self.assertEqual(self.bad_ports(head + entry), [], entry)
        for entry in bad:
            self.assertTrue(self.bad_ports(head + entry), entry)
        self.assertEqual(self.bad_ports(head + '      - "8000-8010:8000-8010"\n'), ["8000-8010:8000-8010"])
        self.assertEqual(self.bad_ports(head + '      - "[::1]:8080:80"\n'), ["[::1]:8080:80"])

    def test_a_flow_style_ports_list_is_not_read_so_the_guard_says_no_port_was_found(self):
        """"ports: [...]" is not read as a list; that must never pass as 'nothing is published', it fires the guard."""
        head = "services:\n  clark:\n    image: x\n"
        for block in ('    ports: ["0.0.0.0:8766:8766"]\n', '    ports: [ "127.0.0.1:8766:8766" ]\n', "    ports: [8766:8766]\n",
                      "    ports: []\n", "    image: y\n"):
            self.assertEqual(self.bad_ports(head + block), ["no published port found"], block)
        self.assertEqual(self.bad_ports(head + '    ports:\n      - "127.0.0.1:8766:8766"\n'), [])

    def service(self):
        return (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")

    @staticmethod
    def mounts(text):
        """The service's volume list read by its structure (a "- " item and its keys), whatever the indentation or key order."""
        items, inside, base = [], False, 0
        for line in text.splitlines():
            line = line.split("#", 1)[0].rstrip()
            if not line.strip():
                continue
            indent, body = len(line) - len(line.lstrip()), line.strip()
            if body == "volumes:":
                inside, base = True, indent
            elif inside and indent <= base:
                inside = False
            elif inside:
                if body.startswith("- "):
                    items.append({})
                    body = body[2:]
                key, _, value = body.partition(":")
                if value.strip() and items:
                    items[-1][key.strip()] = value.strip()
        return items

    def test_it_runs_a_stock_python_image_pinned_by_tag_and_builds_nothing(self):
        """The owner's direction (item 427): only a stock Python image runs in Docker; nothing of clark is built into an image."""
        text = self.service()
        self.assertRegex(text, r"(?m)^    image: python:3\.\d+\.\d+-slim-bookworm$")
        for word in ("build:", "dockerfile", "pull_policy", "clark:local"):
            self.assertNotIn(word, text.lower(), word)
        self.assertFalse((ROOT / "docker" / "Dockerfile").exists(), "no image of clark's own")
        self.assertNotRegex(text, r"(?m)^version:")

    def test_the_whole_local_folder_is_bind_mounted_and_the_data_is_kept_in_it(self):
        """clark's code and its data stay in the unzipped folder on the computer: nothing is kept only inside the container."""
        text = self.service()
        self.assertIn("      - type: bind\n        source: ..\n        target: /clark\n        read_only: true\n", text)
        self.assertIn("      - type: bind\n        source: ${CLARK_DATA_DIR:-${HOME}/Library/Application Support/clark}\n        target: /data\n        bind:\n"
                      "          create_host_path: true\n", text)
        self.assertRegex(text, r"(?m)^    working_dir: /clark$")
        self.assertEqual(len(re.findall(r"(?m)^\s*target:", text)), 2, "the code (read-only) and its data folder, nothing else")
        self.assertEqual(text.count("read_only: true"), 2, "the code mount and the container itself; the data mount is the one written")

    def test_no_mount_target_sits_inside_the_read_only_share(self):
        """#695: Docker cannot make a mountpoint inside a read-only share, so a data target under /clark failed on a first start
        with CLARK_DATA_DIR named (no data folder beside compose.yaml yet). The data folder is mounted outside the share."""
        text = self.service()
        mounts = self.mounts(text)
        shared = [m["target"] for m in mounts if m.get("read_only") == "true"]
        self.assertEqual(shared, ["/clark"])
        self.assertEqual(len(mounts), 2, "the code and the data folder, nothing else")
        for m in mounts:
            if m["target"] != shared[0]:
                self.assertFalse(m["target"].startswith(shared[0] + "/"), f"{m['target']} is inside the read-only share {shared[0]}")
        self.assertIn("      - type: bind\n        source: ${CLARK_DATA_DIR:-${HOME}/Library/Application Support/clark}\n        target: /data\n", text)
        self.assertIn('"--data", "/data"', text, "clark is told the folder that is mounted")

    def test_it_runs_as_an_ordinary_user_not_root(self):
        """item 462: a stock image runs as root, and would write the owner's folder as root."""
        text = self.service()
        self.assertRegex(text, r'(?m)^    user: "\$\{UID:-1000\}:\$\{GID:-1000\}"$')
        self.assertNotIn("CLARK_DATA:", text, "the mount fixes the data folder; CLARK_DATA_SOURCE only names it")
        self.assertNotRegex(text, r"(?m)^volumes:", "no named volume at the top level")

    def test_the_command_starts_clark_as_the_terminal_does_with_the_mounted_data(self):
        """python3 -m clark builds the pages (page.ensure_built, item 495) before it serves, as on the Terminal route."""
        text = self.service()
        self.assertIn('    command: ["python3", "-m", "clark", "--data", "/data", "--port", "8766"]', text)
        self.assertTrue((ROOT / "clark" / "__main__.py").is_file(), "the stand-in that python3 -m clark runs from /clark")
        main = (ROOT / "src" / "clark" / "__main__.py").read_text(encoding="utf-8")
        self.assertLess(main.index("page.ensure_built()"), main.index("done = serve("))

    def test_the_container_setting_is_set_in_the_compose_file(self):
        self.assertRegex(self.service(), r'(?m)^      CLARK_CONTAINER: "1"$')

    def test_the_service_comes_back_after_docker_or_the_computer_restarts_unless_it_was_stopped(self):
        """item 1080: restart "no" left clark stopped after a Docker Desktop quit, update or Mac restart. unless-stopped brings it
        back with Docker, while docker compose down or stop still stop it for good."""
        text = self.service()
        block = text.split("services:\n  clark:\n", 1)[1]
        self.assertRegex(block, r"(?m)^    restart: unless-stopped$")
        self.assertNotRegex(block, r'(?m)^    restart: "?no"?$')
        self.assertNotRegex(block, r"(?m)^    restart: always$", "always would restart a container someone stopped on purpose")


class ComposeIsLanSafe(unittest.TestCase):
    """The compose file's 127.0.0.1 prefix is the whole defence against the LAN, so the file may say nothing that sidesteps it (item 427)."""
    TEXT = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
    CODE = "\n".join(line.split("#", 1)[0] for line in TEXT.splitlines())        # the file without its comments

    def test_it_publishes_exactly_one_port_in_the_short_form_on_loopback(self):
        self.assertEqual(len(re.findall(r"(?m)^\s*ports:\s*$", self.CODE)), 1)
        listed = re.findall(r"(?m)^\s*-\s*(.+?)\s*$", self.CODE.split("ports:", 1)[1].split("volumes:", 1)[0])
        self.assertEqual([p.strip("\"'") for p in listed], ["127.0.0.1:${CLARK_PORT:-8766}:8766"])

    def test_nothing_in_it_can_put_the_container_on_the_hosts_network_or_another_address(self):
        for word in ("network_mode", "host_ip", "0.0.0.0", "expose:", "extra_hosts", "privileged", "pid:", "ipc:"):
            self.assertNotIn(word, self.CODE, word)
        ports_block = self.CODE.split("ports:", 1)[1].split("volumes:", 1)[0]
        for word in ("published:", "target:", "mode:"):                      # the long form of a port (the volume below has its own target)
            self.assertNotIn(word, ports_block, word)
        ports_line = next(line for line in self.CODE.splitlines() if "}:8766" in line)
        self.assertEqual(ports_line.count("${"), 1, "only the host port is read from the environment, never the address")
        self.assertRegex(ports_line, r'^      - "127\.0\.0\.1:\$\{CLARK_PORT:-8766\}:8766"$')

    def test_the_host_port_can_be_changed_but_the_address_and_the_container_port_cannot(self):
        """CLARK_PORT moves the port on this computer (8766 when unset); the address stays 127.0.0.1 and clark still listens on 8766 inside."""
        ports_line = next(line for line in self.CODE.splitlines() if "CLARK_PORT:-" in line)
        address, rest = ports_line.split('"')[1].split(":", 1)
        self.assertEqual(address, "127.0.0.1")
        self.assertEqual(rest, "${CLARK_PORT:-8766}:8766")
        self.assertIn('"--port", "8766"]', self.CODE)
        self.assertRegex(self.CODE, r'(?m)^      CLARK_PORT: "8766"$')
        for unsafe in ("${CLARK_PORT}", "${CLARK_PORT:-0.0.0.0", "${HOST", "${CLARK_HOST"):
            self.assertNotIn(unsafe, self.CODE, unsafe)

    def test_the_published_port_is_handed_in_for_the_start_up_line(self):
        """item 652: the start-up line names the port the person opens, so compose passes the same ${CLARK_PORT:-8766}."""
        self.assertRegex(self.CODE, r'(?m)^      CLARK_PUBLISHED_PORT: "\$\{CLARK_PORT:-8766\}"$')

    def test_the_data_default_is_outside_the_clark_folder_and_the_same_for_the_check(self):
        """issue 694: the clark folder is replaced by a newer download of the same name, so the data default must not be inside it.
        It is the folder clark.command uses; the OneDrive check is handed the same default, so it sees the folder that is mounted."""
        default = "${HOME}/Library/Application Support/clark"
        self.assertRegex(self.CODE, r"(?m)^        source: \$\{CLARK_DATA_DIR:-" + re.escape(default) + r"\}$")
        self.assertRegex(self.CODE, r'(?m)^      CLARK_DATA_SOURCE: "\$\{CLARK_DATA_DIR:-' + re.escape(default) + r'\}"$')
        self.assertNotIn("../data", self.CODE, "no default inside the clark folder")
        self.assertNotIn("KNOWN LIMIT", self.TEXT, "the default no longer depends on the folder compose is started in")
        self.assertIn('CLARK_DATA_DIR="/full/path/to/the/folder" docker compose -f docker/compose.yaml up -d', self.TEXT,
                      "the comment shows how to name another folder, quoted")


class GetFromAnotherPeer(unittest.TestCase):
    """A real server, a real request: in container mode the page and /health answer this machine only (item 427, a reader's finding:
    GET checked the Host header and nothing else, and the container's 0.0.0.0 bind lets in any peer on the Docker network)."""

    def get(self, path, peer_is_local, container):
        httpd = sv.LocalServer((sv.HOST, 0), page_html=lambda: "<html><head></head><body>ZQ-THE-PAGE</body></html>")
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        with mock.patch.object(sv, "container_mode", lambda: container), mock.patch.object(sv, "local_peer", lambda address: peer_is_local):
            conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
            try:
                conn.request("GET", path, headers={"Host": f"127.0.0.1:{httpd.server_port}"})
                answer = conn.getresponse()
                return answer.status, answer.read().decode("utf-8", "replace")
            finally:
                conn.close()

    def test_the_page_and_health_are_refused_to_a_peer_that_is_not_this_machine(self):
        for path in ("/", "/health"):
            status, body = self.get(path, peer_is_local=False, container=True)
            self.assertEqual(status, 403, path)
            self.assertNotIn("ZQ-THE-PAGE", body, "no page and no token reach it")
            self.assertNotIn(sv.TOKEN, body)

    def test_the_page_and_health_answer_this_machine_and_the_container_gateway(self):
        self.assertEqual(self.get("/health", peer_is_local=True, container=True)[0], 200)
        status, body = self.get("/", peer_is_local=True, container=True)
        self.assertEqual(status, 200)
        self.assertIn("ZQ-THE-PAGE", body)

    def test_outside_a_container_nothing_changes(self):
        self.assertEqual(self.get("/health", peer_is_local=False, container=False)[0], 200)


class AlwaysAnswered(unittest.TestCase):
    """The owner's run in Docker: Chrome said the page sent no answer at all. A peer is never dropped silently: in container
    mode the real peer check (not a stand-in) lets in loopback and the default route's gateway and answers every other peer
    with a 403; and a page that cannot be made is a 500, not a closed connection."""

    def get(self, peer, path="/", page_html=None):
        class FromPeer(sv.Handler):
            def setup(self):
                super().setup()
                self.client_address = (peer, 50000)          # as a published port's connection would arrive

        httpd = sv.LocalServer((sv.HOST, 0), handler=FromPeer,
                               page_html=page_html or (lambda: "<html><head></head><body>ZQ-THE-PAGE</body></html>"))
        self.addCleanup(httpd.server_close)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.shutdown)
        conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
        self.addCleanup(conn.close)
        conn.request("GET", path, headers={"Host": f"localhost:{httpd.server_port}"})
        answer = conn.getresponse()
        return answer.status, answer.getheader("Content-Type"), answer.read().decode("utf-8", "replace")

    def setUp(self):
        for patch in (mock.patch.object(sv, "container_mode", lambda: True), mock.patch.object(sv, "container_gateway", lambda: "172.18.0.1")):
            patch.start()
            self.addCleanup(patch.stop)

    def test_loopback_and_the_gateway_get_the_page(self):
        for peer in ("127.0.0.1", "172.18.0.1"):
            status, _, body = self.get(peer)
            self.assertEqual(status, 200, peer)
            self.assertIn("ZQ-THE-PAGE", body, peer)

    def test_another_container_in_the_subnet_and_a_lan_address_get_a_plain_403_page_that_names_the_cause(self):
        for peer in ("172.18.0.2", "172.18.0.5", "172.18.255.255", "172.17.0.1", "192.168.1.10", "10.0.0.5", "0.0.0.0"):
            for path in ("/", "/health"):
                status, ctype, body = self.get(peer, path)
                self.assertEqual(status, 403, (peer, path))
                self.assertEqual(ctype, "text/html; charset=utf-8")
                self.assertIn("<p>This connection was refused. clark is running in Docker and only answers this computer.</p>", body, (peer, path))
                self.assertNotIn("Reload the page", body)
                self.assertNotIn("ZQ-THE-PAGE", body)
                self.assertNotIn(sv.TOKEN, body)

    def test_the_log_names_each_refused_peer_and_the_gateway_once_and_holds_no_token(self):
        log = io.StringIO()
        with mock.patch.object(sv, "_REFUSED_PEERS", set()), mock.patch("sys.stderr", log):
            for peer in ("172.18.0.5", "172.18.0.5", "192.168.1.10", "172.18.0.5", "127.0.0.1", "172.18.0.1"):
                for path in ("/", "/health"):
                    self.get(peer, path)
        lines = log.getvalue().splitlines()
        self.assertEqual(lines, [
            "Refused a connection from 172.18.0.5: in Docker only 127.0.0.1 and the container's gateway (172.18.0.1) are accepted.",
            "Refused a connection from 192.168.1.10: in Docker only 127.0.0.1 and the container's gateway (172.18.0.1) are accepted."])
        self.assertNotIn(sv.TOKEN, log.getvalue())

    def test_a_refused_post_is_logged_once_too_and_the_log_is_bounded(self):
        log = io.StringIO()
        with mock.patch.object(sv, "_REFUSED_PEERS", set()), mock.patch("sys.stderr", log), \
                mock.patch.object(sv, "REFUSED_PEERS_KEPT", 2):
            for peer in ("172.18.0.7", "172.18.0.7", "172.18.0.8", "172.18.0.9"):
                self.assertFalse(local(Handler(peer, headers={sv.TOKEN_HEADER: sv.TOKEN})))
        self.assertEqual([line.split(":")[0] for line in log.getvalue().splitlines()],
                         ["Refused a connection from 172.18.0.7", "Refused a connection from 172.18.0.8"])
        self.assertNotIn(sv.TOKEN, log.getvalue())

    def test_outside_a_container_nothing_is_logged(self):
        log = io.StringIO()
        with mock.patch.object(sv, "container_mode", lambda: False), mock.patch.object(sv, "_REFUSED_PEERS", set()), \
                mock.patch("sys.stderr", log):
            self.assertFalse(local(Handler("192.168.1.10")))
        self.assertEqual(log.getvalue(), "")

    def test_a_page_that_cannot_be_made_is_answered_not_dropped(self):
        def missing():
            raise OSError("no page files")
        with self.assertLogs("clark.server", "ERROR"):
            status, _, body = self.get("172.18.0.1", page_html=missing)
        self.assertEqual(status, 500)
        self.assertEqual(json.loads(body), sv.error_body("server_error"))
        self.assertNotIn("no page files", body)


class GatewayRead(unittest.TestCase):
    def read(self, text):
        return mock.patch("builtins.open", mock.mock_open(read_data=text))

    def test_the_default_route_is_the_gateway(self):
        with self.read(ROUTE):
            self.assertEqual(sv.container_gateway(), "172.18.0.1")

    def test_a_table_with_no_default_route_is_none(self):
        with self.read(ROUTE.splitlines()[0] + "\n" + ROUTE.splitlines()[2] + "\n"):
            self.assertIsNone(sv.container_gateway())

    def test_only_a_true_default_route_counts(self):
        """A half-default route (0.0.0.0/1, as a VPN adds) is not the default route; the real one after it is."""
        half = "eth1\t00000000\t0A0A0A0A\t0003\t0\t0\t0\t00000080\t0\t0\t0\n"
        lines = ROUTE.splitlines(keepends=True)
        with self.read(lines[0] + half + lines[2]):
            self.assertIsNone(sv.container_gateway())
        with self.read(lines[0] + half + lines[1]):
            self.assertEqual(sv.container_gateway(), "172.18.0.1")

    def test_a_route_without_the_gateway_flag_is_not_one(self):
        with self.read(ROUTE.replace("\t0003\t", "\t0001\t", 1)):
            self.assertIsNone(sv.container_gateway())

    def test_nonsense_and_a_missing_file_are_none(self):
        for text in ("", "Iface\n", "Iface\neth0 00000000\n", "Iface\neth0 00000000 zz 0003\n"):
            with self.read(text):
                self.assertIsNone(sv.container_gateway(), repr(text))
        with mock.patch("builtins.open", side_effect=FileNotFoundError):
            self.assertIsNone(sv.container_gateway())


class Ipv4OnlyListener(unittest.TestCase):
    """item 462 (1): the peer check is IPv4 only on purpose. The listener is an IPv4 socket, so no request has an IPv6 peer; if that
    ever changes, these fail and the change must add the IPv6 gateway (/proc/net/ipv6_route) with its own tests."""

    def test_the_listener_is_ipv4_only(self):
        import socket
        self.assertEqual(sv.LocalServer.address_family, socket.AF_INET)

    def test_an_ipv6_peer_is_refused_in_a_container(self):
        with mock.patch.object(sv, "container_mode", lambda: True), mock.patch.object(sv, "container_gateway", lambda: "172.18.0.1"):
            for peer in ("fe80::1", "fd00::1", "2001:db8::1", "::ffff:172.18.0.2"):
                self.assertFalse(sv.local_peer(peer), peer)
            self.assertTrue(sv.local_peer("172.18.0.1"))


if __name__ == "__main__":
    unittest.main()
