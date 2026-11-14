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
import unittest

from _paths import ROOT, SRC  # noqa: F401  (SRC puts src/ on the path)


IMAGE = re.search(r"image:\s*(\S+)", (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")).group(1)

PROBE = textwrap.dedent("""
    import socket, sys
    sys.path.insert(0, "/clark/src")
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


@unittest.skipUnless(docker_up(), "no running Docker on this computer")
class RealContainerPeer(unittest.TestCase):
    def test_the_published_port_peer_is_the_default_route_gateway(self):
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        cmd = ["docker", "run", "--rm", "-i", "-p", "127.0.0.1:%d:9000" % port, "-v", "%s:/clark:ro" % ROOT,
               "-e", "CLARK_CONTAINER=1", IMAGE, "python3", "-u", "-c", PROBE]
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            ready = proc.stdout.readline()
            self.assertTrue(ready.startswith("READY"), ready)
            gateway = ready.split("gateway=")[1].strip()
            with socket.create_connection(("127.0.0.1", port), timeout=10):
                pass
            peer = proc.stdout.readline().split()[-1]
        finally:
            proc.kill()
            proc.wait()
        self.assertNotEqual(gateway, "None")
        self.assertEqual(peer, gateway)


if __name__ == "__main__":
    unittest.main()
