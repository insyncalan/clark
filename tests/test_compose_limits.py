"""Item 638: the compose files stay small. Memory and process limits are set, and a test fails if a file gains docker.sock,
privileged, cap_add, network_mode, a volume beyond the ones listed here, or a port without 127.0.0.1.

Quick tier: no Docker, no browser. The files are read as text (standard library only), comments removed first.
Run: python3 dev/run_tests.py test_compose_limits"""
import re
import unittest

from _paths import ROOT

# The mounts each file may have, by target. A new mount is a decision: add it here in the same change.
ALLOWED_TARGETS = {
    "compose.yaml": {"/clark", "/data"},
    "compose.front.yaml": {"/etc/nginx/templates/default.conf.template"},
}
FORBIDDEN = (r"docker\.sock", r"(?<![\w-])privileged\b", r"\bcap_add\b", r"\bnetwork_mode\b")  # not no-new-privileges


def strip_comments(text):
    out = []
    for line in text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        out.append(re.sub(r"\s#.*$", "", line))
    return "\n".join(out) + "\n"


def problems(text, allowed):
    """What is wrong with one compose file's text, as a list of short sentences (empty when it is fine)."""
    body = strip_comments(text)
    found = [f"has {word}" for word in FORBIDDEN if re.search(word, body)]
    ports = re.search(r"^( *)ports:[ ]*\n((?:\1 +-.*\n)+)", body, re.M)
    for row in re.findall(r"-\s*[\"']?([^\"'\n]+)", ports.group(2)) if ports else []:
        if not row.startswith("127.0.0.1:"):
            found.append(f"port without 127.0.0.1: {row}")
    targets = set(re.findall(r"^\s*target:\s*[\"']?([^\"'\n]+?)[\"']?\s*$", body, re.M))
    # a short-form mount ("- ./a:/b") under volumes: counts as a volume too
    vol = re.search(r"^( *)volumes:[ ]*\n((?:\1 +.*\n)+)", body, re.M)
    if vol:
        for row in re.findall(r"^\s*-\s+(?!type:)(\S.*)$", vol.group(2), re.M):
            targets.add(row.strip())
    if targets != allowed:
        found.append(f"mounts {sorted(targets)} are not the allowed {sorted(allowed)}")
    for key in ("pids_limit", "mem_limit"):
        if not re.search(rf"^\s+{key}:\s*\S+", body, re.M):
            found.append(f"no {key}")
    return found


class ComposeFiles(unittest.TestCase):
    def test_each_file_is_within_its_limits(self):
        for name, allowed in ALLOWED_TARGETS.items():
            with self.subTest(name):
                text = (ROOT / "docker" / name).read_text(encoding="utf-8")
                self.assertEqual(problems(text, allowed), [])

    def test_every_compose_file_is_listed(self):
        self.assertEqual({p.name for p in (ROOT / "docker").glob("compose*.yaml")}, set(ALLOWED_TARGETS))

    def test_limits_are_positive_numbers(self):
        for name in ALLOWED_TARGETS:
            with self.subTest(name):
                text = strip_comments((ROOT / "docker" / name).read_text(encoding="utf-8"))
                self.assertRegex(text, r"(?m)^\s+pids_limit:\s*[1-9]\d*\s*$")
                self.assertRegex(text, r"(?m)^\s+mem_limit:\s*[1-9]\d*[kmg]\s*$")


class TheCheckCatchesChanges(unittest.TestCase):
    """The check itself, on small made-up files: each change below must be reported."""
    BASE = ("services:\n  a:\n    ports:\n      - \"127.0.0.1:1:2\"\n    pids_limit: 9\n    mem_limit: 1g\n"
            "    volumes:\n      - type: bind\n        source: .\n        target: /x\n")

    def test_the_base_is_fine(self):
        self.assertEqual(problems(self.BASE, {"/x"}), [])

    def test_each_change_is_reported(self):
        for label, text in {
            "socket": self.BASE + "      - /var/run/docker.sock:/var/run/docker.sock\n",
            "privileged": self.BASE + "    privileged: true\n",
            "cap_add": self.BASE + "    cap_add:\n      - NET_ADMIN\n",
            "network_mode": self.BASE + "    network_mode: host\n",
            "second volume": self.BASE + "      - type: bind\n        source: .\n        target: /y\n",
            "short volume": self.BASE + "      - ./a:/y\n",
            "open port": self.BASE.replace('"127.0.0.1:1:2"', '"1:2"'),
            "port on all": self.BASE.replace('"127.0.0.1:1:2"', '"0.0.0.0:1:2"'),
            "no pids": self.BASE.replace("    pids_limit: 9\n", ""),
            "no mem": self.BASE.replace("    mem_limit: 1g\n", ""),
        }.items():
            with self.subTest(label):
                self.assertTrue(problems(text, {"/x"}), label)

    def test_a_word_in_a_comment_is_not_a_change(self):
        self.assertEqual(problems("# no docker.sock, never privileged\n" + self.BASE, {"/x"}), [])


if __name__ == "__main__":
    unittest.main()
