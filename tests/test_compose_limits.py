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
    "compose.windows.yaml": {"/data"},      # item 625: the Windows route's data folder, an overlay on compose.yaml
    "compose.copy.yaml": {"/backups-out"},     # item 625: the one extra folder, an overlay on compose.yaml (the host folder for the copy-out of backups)
}
# The host paths a long-form bind mount may have, by file (item 638). A new host path is a decision too.
ALLOWED_SOURCES = {
    "compose.yaml": {"..", "${CLARK_DATA_DIR:-${HOME}/Library/Application Support/clark}"},
    "compose.front.yaml": {"./nginx.front.conf.template"},
    "compose.windows.yaml": {"${CLARK_DATA_DIR:-../../clark-data}"},
    "compose.copy.yaml": {"${CLARK_COPY_DIR:?name the folder in CLARK_COPY_DIR (a full path, in quotes)}"},
}
OVERLAYS = {"compose.copy.yaml", "compose.windows.yaml"}      # a file that only adds to compose.yaml: it sets no limits of its own, compose.yaml's stay in force
LIMIT_SHAPES = {"pids_limit": r"[1-9]\d*", "mem_limit": r"[1-9]\d*[kmg]"}  # a count, or a size with a unit like 1g / 256m; a bare number is not a size (the real files use a unit, test_limits_are_positive_numbers)
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


def _mapping(text, flow=False):
    """'a: 1, b: "x,y"' (or one block item's lines) as a dict of unquoted strings."""
    out = {}
    for part in (_split_flow(text) if flow else text.split("\n")):
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
        m = re.match(rf"^([ \t]*)(-\s+)?([\"']?){key}\3:(?:\s+(.*?))?\s*$", lines[i])
        i += 1
        if not m:
            continue
        indent, dashed, rest = len(m.group(1)), bool(m.group(2)), m.group(4) or ""
        while re.match(r"[&!]\S*(\s+|$)", rest):  # anchors and tags before the value
            rest = re.sub(r"^[&!]\S*\s*", "", rest)
        if not rest:  # a flow list may start on the next non-blank line
            j = i
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and lines[j].strip().startswith("["):
                rest, i = lines[j].strip(), j + 1
        if rest.startswith("["):  # flow list, maybe over several lines
            while rest.count("[") > rest.count("]") and i < len(lines):
                rest += " " + lines[i].strip()
                i += 1
            for raw in _split_flow(rest[1:rest.rindex("]")] if "]" in rest else rest[1:]):
                items.append(_mapping(raw[1:-1], True) if raw.startswith("{") else _unquote(raw))
            continue
        block = []
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent
                                  or (not dashed and re.match(rf"^ {{{indent}}}-(\s|$)", lines[i]))):  # same-indent items
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


def service_blocks(body):
    """{service name: its lines} for the entries directly under the top-level `services:`."""
    lines = body.splitlines()
    out, name, in_services, child = {}, None, False, None
    for line in lines:
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0:
            in_services, name, child = line.strip() == "services:", None, None
        elif in_services:
            if child is None:
                child = indent
            if indent == child and re.match(r"[\w.-]+:\s*$", line.strip()):
                name = line.strip()[:-1]
                out[name] = []
            elif name is not None:
                out[name].append(line)
    return out


def limit_problems(body):
    """Every service needs pids_limit and mem_limit as its own direct keys, with a positive number (or size)."""
    found = []
    services = service_blocks(body)
    if not services:
        return ["no services found"]
    for name, lines in services.items():
        indents = [len(l) - len(l.lstrip()) for l in lines]
        top = min(indents) if indents else 0
        for key, shape in LIMIT_SHAPES.items():
            values = [re.match(r"\s*[\w.-]+:\s*(.*?)\s*$", l).group(1) for l, i in zip(lines, indents)
                      if i == top and re.match(rf"\s*{key}:", l)]
            values = [_unquote(v) for v in values]
            if not values:
                found.append(f"service {name}: no {key}")
            elif not all(re.fullmatch(shape, v) for v in values):
                found.append(f"service {name}: {key} is not a positive number: {values[0]}")
    return found


def source_problems(body, allowed_sources=None):
    """A long-form mount may not have source / or, when a list is given, a host path outside that list."""
    found = []
    for row in list_items(body, "volumes"):
        if not isinstance(row, dict) or "source" not in row:
            continue
        src = row["source"]
        if src.rstrip("/") == "" or (allowed_sources is not None and src not in allowed_sources):
            found.append(f"mount source not allowed: {src}")
    return found


def problems(text, allowed, allowed_sources=None):
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
    found += source_problems(body, allowed_sources)
    found += limit_problems(body)
    return found


class ComposeFiles(unittest.TestCase):
    def test_each_file_is_within_its_limits(self):
        for name, allowed in ALLOWED_TARGETS.items():
            with self.subTest(name):
                text = (ROOT / "docker" / name).read_text(encoding="utf-8")
                found = problems(text, allowed, ALLOWED_SOURCES[name])
                if name in OVERLAYS:      # compose.yaml's limits stay in force under an overlay
                    found = [f for f in found if not f.endswith(("no pids_limit", "no mem_limit"))]
                self.assertEqual(found, [])

    def test_every_compose_file_is_listed(self):
        self.assertEqual({p.name for p in (ROOT / "docker").glob("compose*.yaml")}, set(ALLOWED_TARGETS))

    def test_limits_are_positive_numbers(self):
        for name in ALLOWED_TARGETS:
            if name in OVERLAYS:
                continue
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

    def test_item_638_layout_gaps(self):
        """Item 638 review gaps: same-indent list, flow list on the next line, anchor or tag, tab, quoted key."""
        b = self.BASE
        old = '    ports:\n      - "127.0.0.1:1:2"\n'
        bad = {
            "same-indent ports": b.replace(old, '    ports:\n    - "0.0.0.0:1:2"\n'),
            "same-indent second item": b.replace(old, '    ports:\n    - "127.0.0.1:1:2"\n    - "3:4"\n'),
            "same-indent volumes": b.replace("      - type: bind\n        source: .\n        target: /x\n", '    - "/x"\n    - "/y"\n'),
            "flow on next line": b.replace(old, '    ports:\n      ["0.0.0.0:1:2"]\n'),
            "flow on next line, not indented": b.replace(old, '    ports:\n["0.0.0.0:1:2"]\n'),
            "anchor before flow": b.replace(old, '    ports: &p ["0.0.0.0:1:2"]\n'),
            "tag before flow": b.replace(old, '    ports: !override ["0.0.0.0:1:2"]\n'),
            "tag and anchor before flow": b.replace(old, '    ports: !override &p ["0.0.0.0:1:2"]\n'),
            "tag then block": b.replace(old, '    ports: !override\n      - "0.0.0.0:1:2"\n'),
            "tab after colon": b.replace(old, '    ports:\t["0.0.0.0:1:2"]\n'),
            "tab after colon, block": b.replace(old, '    ports:\t\n      - "0.0.0.0:1:2"\n'),
            "double-quoted key": b.replace(old, '    "ports":\n      - "0.0.0.0:1:2"\n'),
            "single-quoted key": b.replace(old, "    'ports': [\"0.0.0.0:1:2\"]\n"),
            "quoted volumes key": b.replace("    volumes:\n", '    "volumes":\n').replace("target: /x", "target: /y"),
        }
        for label, text in bad.items():
            with self.subTest(label):
                self.assertTrue(problems(text, {"/x"}), label)
        fine = {
            "same-indent ports": b.replace(old, '    ports:\n    - "127.0.0.1:1:2"\n'),
            "flow on next line": b.replace(old, '    ports:\n      ["127.0.0.1:1:2"]\n'),
            "anchor before flow": b.replace(old, '    ports: &p ["127.0.0.1:1:2"]\n'),
            "tag before flow": b.replace(old, '    ports: !override ["127.0.0.1:1:2"]\n'),
            "tab after colon": b.replace(old, '    ports:\t["127.0.0.1:1:2"]\n'),
            "quoted key": b.replace(old, '    "ports":\n      - "127.0.0.1:1:2"\n'),
        }
        for label, text in fine.items():
            with self.subTest("fine " + label):
                self.assertEqual(problems(text, {"/x"}), [], label)

    def test_limits_are_needed_in_every_service(self):
        two = self.TWO
        self.assertEqual(problems(two, {"/x"}), [])
        for label, text in {
            "second has no pids": two[:two.index("  b:")] + two[two.index("  b:"):].replace("    pids_limit: 9\n", ""),
            "second has no mem": two[:two.index("  b:")] + two[two.index("  b:"):].replace("    mem_limit: 1g\n", ""),
            "minus one": self.BASE.replace("pids_limit: 9", "pids_limit: -1"),
            "zero pids": self.BASE.replace("pids_limit: 9", "pids_limit: 0"),
            "zero mem": self.BASE.replace("mem_limit: 1g", "mem_limit: 0"),
            "zero size": self.BASE.replace("mem_limit: 1g", "mem_limit: 0m"),
            "variable pids": self.BASE.replace("pids_limit: 9", "pids_limit: ${X}"),
            "variable mem": self.BASE.replace("mem_limit: 1g", "mem_limit: ${X:-1g}"),
            "empty": self.BASE.replace("mem_limit: 1g", "mem_limit:"),
            "words": self.BASE.replace("mem_limit: 1g", "mem_limit: lots"),
            "pids under labels": self.BASE.replace("    pids_limit: 9\n", "    labels:\n      pids_limit: 9\n"),
            "mem under labels": self.BASE.replace("    mem_limit: 1g\n", "    labels:\n      mem_limit: 1g\n"),
            "both only in the first service": self.TWO.replace("  b:\n    ports:\n      - \"127.0.0.1:3:4\"\n    pids_limit: 9\n    mem_limit: 1g\n",
                                                               "  b:\n    ports:\n      - \"127.0.0.1:3:4\"\n"),
        }.items():
            with self.subTest(label):
                self.assertTrue(problems(text, {"/x"}), label)

    def test_fine_limit_values(self):
        for pids, mem in (("1", "1k"), ("4096", "256m"), ("9", "1g"), ('"9"', '"512k"')):
            with self.subTest(f"{pids} {mem}"):
                text = self.BASE.replace("pids_limit: 9", f"pids_limit: {pids}").replace("mem_limit: 1g", f"mem_limit: {mem}")
                self.assertEqual(problems(text, {"/x"}), [])

    def test_a_bare_number_is_not_a_size(self):
        text = self.BASE.replace("mem_limit: 1g", "mem_limit: 1048576")
        self.assertEqual(problems(text, {"/x"}), ["service a: mem_limit is not a positive number: 1048576"])

    def test_a_capital_size_is_not_accepted(self):
        # the check takes lowercase sizes only (1g, 256m); a 2G is flagged, not passed
        text = self.BASE.replace("mem_limit: 1g", "mem_limit: 2G")
        self.assertEqual(problems(text, {"/x"}), ["service a: mem_limit is not a positive number: 2G"])

    def test_long_form_mount_source(self):
        root = self.BASE.replace("source: .", "source: /")
        self.assertEqual(problems(root, {"/x"}), ["mount source not allowed: /"])
        self.assertTrue(problems(root, {"/x"}, {"/"}))  # / is refused even when somebody lists it
        flow = self.BASE.replace("    volumes:\n      - type: bind\n        source: .\n        target: /x\n",
                                 "    volumes: [{type: bind, source: /, target: /x}]\n")
        self.assertTrue(problems(flow, {"/x"}))
        etc = self.BASE.replace("source: .", "source: /etc")
        self.assertEqual(problems(etc, {"/x"}, {"."}), ["mount source not allowed: /etc"])
        self.assertEqual(problems(self.BASE, {"/x"}, {"."}), [])
        self.assertEqual(problems(self.BASE.replace("source: .", "source: ${HOME}/.ssh"), {"/x"}, {"."}),
                         ["mount source not allowed: ${HOME}/.ssh"])

    def test_a_word_in_a_comment_is_not_a_change(self):
        self.assertEqual(problems("# no docker.sock, never privileged\n" + self.BASE, {"/x"}), [])


if __name__ == "__main__":
    unittest.main()
