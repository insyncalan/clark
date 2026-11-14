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


def _unquote(item):
    item = item.strip()
    if len(item) >= 2 and item[0] == item[-1] and item[0] in "\"'":
        return item[1:-1]
    return item


def _split_flow(inner):
    """Split the inside of a flow list on commas that are not inside quotes, braces or brackets."""
    items, cur, quote, depth = [], "", "", 0
    for ch in inner:
        if quote:
            cur += ch
            quote = "" if ch == quote else quote
        elif ch in "\"'":
            quote = ch
            cur += ch
        elif ch in "[{":
            depth += 1
            cur += ch
        elif ch in "]}":
            depth -= 1
            cur += ch
        elif ch == "," and depth == 0:
            items.append(cur)
            cur = ""
        else:
            cur += ch
    items.append(cur)
    return [i.strip() for i in items if i.strip()]


def _mapping(text):
    """'a: 1, b: "x,y"' (or one block item's lines) as a dict of unquoted strings."""
    out = {}
    for part in re.split(r"\n|(?<![\"'\w]),(?![^\"']*[\"']\s*(?:,|$))", text):
        m = re.match(r"\s*-?\s*([\w.-]+):\s*(.*?)\s*$", part)
        if m:
            out[m.group(1)] = _unquote(m.group(2))
    return out


def list_items(body, key):
    """Every item of every `key:` list in the text, block or flow style, in any service.
    Each item is a string (short form) or a dict (a mapping item such as `- type: bind` or `{type: bind, target: /x}`)."""
    lines = body.splitlines()
    items, i = [], 0
    while i < len(lines):
        m = re.match(rf"^( *)(?:-\s+)?{key}:[ ]*(.*?)\s*$", lines[i])
        i += 1
        if not m:
            continue
        indent, rest = len(m.group(1)), m.group(2)
        if rest.startswith("["):  # flow list, maybe over several lines
            while rest.count("[") > rest.count("]") and i < len(lines):
                rest += " " + lines[i].strip()
                i += 1
            for raw in _split_flow(rest[1:rest.rindex("]")] if "]" in rest else rest[1:]):
                items.append(_mapping(raw[1:-1]) if raw.startswith("{") else _unquote(raw))
            continue
        block = []
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
            block.append(lines[i])
            i += 1
        cur = None
        for line in block:
            if re.match(r"^\s*-(\s|$)", line) and (cur is None or len(line) - len(line.lstrip()) <= cur[0]):
                cur = [len(line) - len(line.lstrip()), [line]]
                items.append(cur)
            elif cur is not None and line.strip():
                cur[1].append(line)
        for n, it in enumerate(items):
            if isinstance(it, list):
                first = it[1][0].split("-", 1)[1].strip()
                if len(it[1]) == 1 and not re.match(r"[\w.-]+:(\s|$)", first):
                    items[n] = _unquote(first)
                else:
                    items[n] = _mapping("\n".join(it[1]))
    return items


def problems(text, allowed):
    """What is wrong with one compose file's text, as a list of short sentences (empty when it is fine)."""
    body = strip_comments(text)
    found = [f"has {word}" for word in FORBIDDEN if re.search(word, body)]
    for row in list_items(body, "ports"):
        if isinstance(row, dict):  # long form: published/target/host_ip
            if row.get("host_ip") != "127.0.0.1":
                found.append(f"port without 127.0.0.1: {row}")
        elif not row.startswith("127.0.0.1:"):
            found.append(f"port without 127.0.0.1: {row}")
    targets = set()
    for row in list_items(body, "volumes"):
        # a short-form mount ("./a:/b") counts as a volume too, under its whole text
        targets.add(row.get("target", str(row)) if isinstance(row, dict) else row)
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

    TWO = ("services:\n  a:\n    ports:\n      - \"127.0.0.1:1:2\"\n    pids_limit: 9\n    mem_limit: 1g\n"
           "    volumes:\n      - type: bind\n        source: .\n        target: /x\n"
           "  b:\n    ports:\n      - \"127.0.0.1:3:4\"\n    pids_limit: 9\n    mem_limit: 1g\n")

    def test_every_ports_block_is_checked_not_only_the_first(self):
        self.assertEqual(problems(self.TWO, {"/x"}), [])
        bad = self.TWO.replace('"127.0.0.1:3:4"', '"3:4"')
        self.assertEqual(problems(bad, {"/x"}), ["port without 127.0.0.1: 3:4"])
        again = self.TWO + "    ports:\n      - 0.0.0.0:5:6\n"
        self.assertIn("port without 127.0.0.1: 0.0.0.0:5:6", problems(again, {"/x"}))

    def test_every_item_of_one_block_is_checked(self):
        text = self.BASE.replace('      - "127.0.0.1:1:2"\n', '      - "127.0.0.1:1:2"\n      - 9:9\n')
        self.assertEqual(problems(text, {"/x"}), ["port without 127.0.0.1: 9:9"])

    def test_volumes_in_a_second_service_are_checked(self):
        text = self.TWO + "    volumes:\n      - ./a:/y\n"
        self.assertTrue(problems(text, {"/x"}))

    def test_flow_style_ports(self):
        base = self.BASE.replace('    ports:\n      - "127.0.0.1:1:2"\n', "    ports: %s\n")
        for label, value, bad in (
            ("one fine", '["127.0.0.1:1:2"]', []),
            ("empty", "[]", []),
            ("two fine", "['127.0.0.1:1:2', \"127.0.0.1:3:4\"]", []),
            ("open", '["1:2"]', ["1:2"]),
            ("second one open", '["127.0.0.1:1:2", "0.0.0.0:3:4"]', ["0.0.0.0:3:4"]),
            ("unquoted", "[127.0.0.1:1:2, 8:8]", ["8:8"]),
            ("no space after colon", "[ 8080:80 ]", ["8080:80"]),
        ):
            with self.subTest(label):
                self.assertEqual(problems(base % value, {"/x"}), [f"port without 127.0.0.1: {b}" for b in bad])

    def test_flow_ports_over_several_lines(self):
        text = self.BASE.replace('    ports:\n      - "127.0.0.1:1:2"\n', '    ports: [\n      "127.0.0.1:1:2",\n      "5:6",\n    ]\n')
        self.assertEqual(problems(text, {"/x"}), ["port without 127.0.0.1: 5:6"])

    def test_flow_style_volumes(self):
        base = self.BASE.replace("    volumes:\n      - type: bind\n        source: .\n        target: /x\n", "    volumes: %s\n")
        for label, value, fine in (
            ("short fine", '["/x"]', True),
            ("short other", '["./a:/y"]', False),
            ("two", '["/x", "/y"]', False),
            ("mapping fine", "[{type: bind, source: ., target: /x}]", True),
            ("mapping other", "[{type: bind, source: ., target: /y}]", False),
            ("mapping extra", "[{type: bind, target: /x}, {type: bind, target: /z}]", False),
            ("socket", '["/var/run/docker.sock:/var/run/docker.sock"]', False),
            ("empty", "[]", False),
        ):
            with self.subTest(label):
                self.assertEqual(not problems(base % value, {"/x"}), fine, label)

    def test_hostile_text_does_not_hide_a_change(self):
        for label, text in {
            "comma in a quote": self.BASE.replace('- "127.0.0.1:1:2"', '- "127.0.0.1:1:2,0.0.0.0:3:4"') + "    ports: [\"a,b\", \"7:7\"]\n",
            "good port in a comment": self.BASE.replace('"127.0.0.1:1:2"', "5:5  # 127.0.0.1:5:5"),
            "bracket in a quote": self.BASE.replace("    pids_limit", "    ports: [\"]\", \"8:8\"]\n    pids_limit"),
            "long form without host_ip": self.BASE.replace('- "127.0.0.1:1:2"', "- target: 2\n        published: 1"),
            "long form wrong host_ip": self.BASE.replace('- "127.0.0.1:1:2"', "- target: 2\n        host_ip: 0.0.0.0"),
            "text above the real key": "x: ports: [127.0.0.1:1:1]\n" + self.BASE.replace('"127.0.0.1:1:2"', '"1:2"'),
            "flow volume after a block volume": self.BASE + "    volumes: [\"/y\"]\n",
        }.items():
            with self.subTest(label):
                self.assertTrue(problems(text, {"/x"}), label)

    def test_hostile_text_that_is_fine_stays_fine(self):
        text = self.BASE.replace('- "127.0.0.1:1:2"', '- "127.0.0.1:1:2"  # was 0.0.0.0:1:2, ports: [3:3]')
        self.assertEqual(problems(text, {"/x"}), [])
        long_form = self.BASE.replace('- "127.0.0.1:1:2"', "- target: 2\n        published: 1\n        host_ip: 127.0.0.1")
        self.assertEqual(problems(long_form, {"/x"}), [])

    def test_a_word_in_a_comment_is_not_a_change(self):
        self.assertEqual(problems("# no docker.sock, never privileged\n" + self.BASE, {"/x"}), [])


if __name__ == "__main__":
    unittest.main()
