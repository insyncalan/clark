"""#45: the published file carries the report's section style (publish.section_style, add_glance, data_block; guarded: the publish module).

Run: python3 dev/run_tests.py test_publish_style
The style is one of slim, roomy, grey or card; anything else is replaced by slim. All rows are fictional.
"""
import os
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

from clark import publish
from test_glance import ON, RULES, data, sections


def inputs(**more):
    d = data()
    return {"data": d, "hidden": [], "sections": sections(), "label_rules": RULES, "as_at": ON, "glance_tiles": [], **more}


def block(i):
    published = publish.add_glance(publish.select(i), i)
    text = publish.data_block(published, ON)
    return json.loads(re.search(r">(.*)</script>", text, re.S).group(1)), text


def need_node(test):
    """node on the path, or: skip on a computer without it, but fail where CI is set (CI has node; a skip there would hide the test)."""
    node = shutil.which("node")
    if not node:
        if os.environ.get("CI"):
            test.fail("node is missing but CI is set: these tests must run in CI, not skip")
        test.skipTest("node is not installed on this computer (CI has it)")
    return node


class Style(unittest.TestCase):
    def test_the_four_styles_are_carried_next_to_as_at(self):
        self.assertEqual(publish.STYLES, ("slim", "roomy", "grey", "card"))
        for name in publish.STYLES:
            got, text = block(inputs(section_style=name))
            self.assertEqual((got["style"], got["as_at"]), (name, ON))
            self.assertLess(text.index('"as_at"'), text.index('"style"'), "sorted keys: as_at, data, sections, style, tabs, v")

    def test_nothing_stored_gives_slim(self):
        self.assertEqual(block(inputs())[0]["style"], "slim")

    def test_anything_else_is_replaced_by_slim(self):
        for bad in ("", "Slim", "wide", "slim ", "card\n", None, 3, True, ["card"], {"a": 1}, "<script>"):
            self.assertEqual(block(inputs(section_style=bad))[0]["style"], "slim", repr(bad))

    def test_data_block_never_carries_an_unknown_word_even_when_published_was_changed_by_hand(self):
        published = publish.add_glance(publish.select(inputs()), inputs())
        for bad in ("wide", None, 3, "<b>"):
            published["style"] = bad
            got = json.loads(re.search(r">(.*)</script>", publish.data_block(published, ON), re.S).group(1))
            self.assertEqual(got["style"], "slim")

    def test_the_style_is_a_word_the_page_knows(self):
        # item 1025: the page speaks two densities and sends each as one of the words publish knows (the bridge in density.js)
        page = (Path(publish.__file__).parent / "page" / "src" / "stores" / "density.js").read_text(encoding="utf-8")
        self.assertIn('export const IDS = ["compact", "comfortable"];', page)
        self.assertIn('sectionWord = (d) => (d === "comfortable" ? "roomy" : "card")', page)
        self.assertLessEqual({"roomy", "card"}, set(publish.STYLES))

    def test_comfortable_publishes_as_roomy_and_compact_as_card(self):
        # item 1025: run the page's own density.js in node (signals stubbed), choose each density, and publish with the word it sends
        node = need_node(self)
        src = (Path(publish.__file__).parent / "page" / "src" / "stores" / "density.js").read_text(encoding="utf-8")
        src = re.sub(r"^import .*signals.*$", "const signal = (v) => ({ value: v });", src, flags=re.M)
        code = ("globalThis.localStorage = { getItem: () => null, setItem() {} };\n" + src +
                "\nconst out = {};\nfor (const d of ['comfortable', 'compact']) { setDensity(d); out[d] = sectionWord(density.value); }\n"
                "setDensity('bogus'); out.bogus = sectionWord(density.value);\nconsole.log(JSON.stringify(out));")
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        sent = json.loads(done.stdout)
        self.assertEqual(sent, {"comfortable": "roomy", "compact": "card", "bogus": "card"})
        self.assertEqual(block(inputs(section_style=sent["comfortable"]))[0]["style"], "roomy")
        self.assertEqual(block(inputs(section_style=sent["compact"]))[0]["style"], "card")

    def test_an_unknown_density_is_ignored_and_never_remembered(self):
        # item 1025: setDensity with anything but compact or comfortable changes nothing: not the signal, not the page, not the stored word
        node = need_node(self)
        src = (Path(publish.__file__).parent / "page" / "src" / "stores" / "density.js").read_text(encoding="utf-8")
        src = re.sub(r"^import .*signals.*$", "const signal = (v) => ({ value: v });", src, flags=re.M)
        code = ("const kept = {};\nglobalThis.localStorage = { getItem: () => null, setItem(k, v) { kept[k] = v; } };\n"
                "globalThis.document = { documentElement: { dataset: {} } };\n" + src +
                "\nsetDensity('comfortable');\nfor (const bad of ['bogus', 'roomy', '', null, 3, 'Compact']) setDensity(bad);\n"
                "console.log(JSON.stringify({ now: density.value, painted: document.documentElement.dataset.density, kept }));")
        done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), {"now": "comfortable", "painted": "comfortable", "kept": {"clark.density": "comfortable"}})


class NodeIsRequiredInCi(unittest.TestCase):
    def test_a_missing_node_fails_where_ci_is_set_and_skips_elsewhere(self):
        from unittest import mock
        with mock.patch("shutil.which", return_value=None):
            with mock.patch.dict(os.environ, {"CI": "true"}):
                with self.assertRaises(self.failureException):
                    need_node(self)
            env = {k: v for k, v in os.environ.items() if k != "CI"}
            with mock.patch.dict(os.environ, env, clear=True):
                with self.assertRaises(unittest.SkipTest):
                    need_node(self)


if __name__ == "__main__":
    unittest.main()
