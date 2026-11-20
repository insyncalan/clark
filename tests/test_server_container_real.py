"""item 511: the peer address Docker really presents to a published port is the container's default gateway (src/clark/server.py, item 427).

Run: python3 dev/run_tests.py test_server_container_real
This starts a real container (the image docker/compose.yaml names), publishes a port on 127.0.0.1 only, connects to it from this
machine, and checks that the peer the container sees is the default-route gateway that container_gateway() reads. A computer with
no running Docker skips these tests with a plain reason; nothing else in the suite needs Docker.
"""
import re
import shutil
import socket
import subprocess
import textwrap
import threading
import uuid
import unittest

from _paths import ROOT, SRC  # noqa: F401  (SRC puts src/ on the path)


IMAGE = re.search(r"^\s*image:\s*(\S+)", (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8"), re.M).group(1)

PROBE = textwrap.dedent("""
    import socket, sys
    sys.path.insert(0, "/clark/vendor"); sys.path.insert(0, "/clark/src")
    from clark import server as sv
    s = socket.socket(); s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind(("0.0.0.0", 9000)); s.listen(1)
    print("READY gateway=%s" % sv.container_gateway(), flush=True)
    c, peer = s.accept()
    print("PEER %s" % peer[0], flush=True)
    c.close()
""")


def docker_up():
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def image_ready():
    """The image is on this computer, or can be pulled in a bounded time (a slow first pull must not hang the run)."""
    if subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True, timeout=60).returncode == 0:
        return True
    try:
        return subprocess.run(["docker", "pull", "-q", IMAGE], capture_output=True, timeout=600).returncode == 0
    except subprocess.TimeoutExpired:
        return False


@unittest.skipUnless(docker_up(), "no running Docker on this computer")
class RealContainerPeer(unittest.TestCase):
    def test_the_published_port_peer_is_the_default_route_gateway(self):
        if not image_ready():
            self.skipTest("the image %s is not here and could not be pulled" % IMAGE)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        name = "clark-test-511-" + uuid.uuid4().hex[:8]
        cmd = ["docker", "run", "--rm", "-i", "--name", name, "-w", "/clark", "-p", "127.0.0.1:%d:9000" % port,
               "--mount", "type=bind,source=%s,target=/clark,readonly" % ROOT,
               "-e", "CLARK_CONTAINER=1", "-e", "PYTHONDONTWRITEBYTECODE=1", IMAGE, "python3", "-u", "-c", PROBE]
        proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        # A stuck container must end the run, not hang it: killing the client ends the reads below.
        watchdog = threading.Timer(120, proc.kill)
        watchdog.start()
        try:
            ready = proc.stdout.readline()
            self.assertTrue(ready.startswith("READY"), ready)
            gateway = ready.split("gateway=")[1].strip()
            with socket.create_connection(("127.0.0.1", port), timeout=10):
                pass
            words = proc.stdout.readline().split()
            self.assertTrue(words, "the container printed no peer")
            peer = words[-1]
        finally:
            watchdog.cancel()
            proc.kill()
            proc.wait()
            # Killing the client does not stop the container; remove it by name.
            subprocess.run(["docker", "rm", "-f", name], capture_output=True, timeout=60)
        self.assertNotEqual(gateway, "None")
        self.assertEqual(peer, gateway)


if __name__ == "__main__":
    unittest.main()
