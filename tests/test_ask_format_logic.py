"""Row 1217: ask clark answers drawn formatted: the parser (src/clark/page/src/edit/askFormat.js) and that the panel draws only its data.

Run: python3 dev/run_tests.py test_ask_format_logic
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skips without node). Fictional text only.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import SRC

import esbuild  # noqa: E402  (dev/tools)

EDIT = SRC / "clark" / "page" / "src" / "edit"


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "af.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AF", str(EDIT / "askFormat.js"), f"--outfile={out}"], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = Path(tmp) / "probe.js"
        script.write_text(out.read_text(encoding="utf-8") + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        got = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert got.returncode == 0, got.stderr
        return json.loads(got.stdout)


def parse(text):
    return run_node("AF.parseAnswer(" + json.dumps(text) + ")")


def flat(nodes):
    """Every word of a node list, marks gone."""
    return "".join(n["v"] if "v" in n else flat(n["c"]) for n in nodes)


class Blocks(unittest.TestCase):
    def test_bold_headings_lists_and_paragraphs(self):
        b = parse("**Overall health:** steady.\n\n## Main concerns\n- Supplier delay\n- Kit late\n\n1. First\n2. Second\n\nDone.")
        self.assertEqual([x["t"] for x in b], ["p", "h", "ul", "ol", "p"])
        self.assertEqual(b[0]["lines"][0][0], {"t": "strong", "c": [{"t": "text", "v": "Overall health:"}]})
        self.assertEqual(flat(b[1]["c"]), "Main concerns")
        self.assertEqual([flat(i[0]) for i in b[2]["items"]], ["Supplier delay", "Kit late"])
        self.assertEqual([flat(i[0]) for i in b[3]["items"]], ["First", "Second"])

    def test_no_mark_symbols_survive_in_what_is_drawn(self):
        b = parse("# Title\n**bold** and *it* and _it2_ and `code`\n- item **x**\n")
        text = json.dumps(b)
        self.assertNotIn("**", text)
        self.assertNotIn("`", text)
        self.assertEqual(flat(b[1]["lines"][0]), "bold and it and it2 and code")

    def test_a_single_line_break_is_kept_and_a_blank_line_splits(self):
        b = parse("one\ntwo\n\nthree")
        self.assertEqual([len(x["lines"]) for x in b], [2, 1])

    def test_fenced_code_is_kept_as_it_is(self):
        b = parse("```\n**not bold**\n- not a list\n```")
        self.assertEqual(b, [{"t": "pre", "v": "**not bold**\n- not a list"}])

    def test_markup_links_and_images_stay_text(self):
        src = '<img src=x onerror=1> [a link](http://example.test) ![pic](http://example.test/p.png) <b>x</b>'
        b = parse(src)
        self.assertEqual(flat(b[0]["lines"][0]), src)
        self.assertEqual({n["t"] for n in b[0]["lines"][0]}, {"text"})

    def test_a_mark_with_no_partner_stays_as_written(self):
        self.assertEqual(flat(parse("2 * 3 * 4 and snake_case_name and **open")[0]["lines"][0]), "2 * 3 * 4 and snake_case_name and **open")

    def test_dates_ids_and_numbers_read_as_they_do(self):
        s = "ABC-A-001 is due 2026-11-15 (3.5 days)."
        self.assertEqual(flat(parse(s)[0]["lines"][0]), s)
        self.assertEqual(flat(parse("- ABC-A-001: 12")[0]["items"][0][0]), "ABC-A-001: 12")

    def test_a_doubled_underscore_is_text_not_an_italic(self):
        self.assertEqual(flat(parse("a window.__pwn=1 and window.__pwn=2")[0]["lines"][0]), "a window.__pwn=1 and window.__pwn=2")

    def test_a_numbered_list_keeps_its_start(self):
        self.assertEqual(parse("3. c\n4. d")[0]["start"], 3)

    def test_a_heading_deeper_than_three_is_drawn_as_the_third_level(self):
        # the page draws level + 2 as the element, so a level over 3 would be h6 to h8 (h7 and h8 are not elements)
        self.assertEqual([x["level"] for x in parse("# a\n\n## b\n\n### c\n\n#### d\n\n###### e")], [1, 2, 3, 3, 3])

    def test_a_plus_bullet_is_a_list_like_a_dash_and_a_star(self):
        for mark in ("-", "*", "+"):
            with self.subTest(mark):
                b = parse(f"{mark} one\n{mark} two")
                self.assertEqual([x["t"] for x in b], ["ul"])
                self.assertEqual([flat(i[0]) for i in b[0]["items"]], ["one", "two"])


class Streaming(unittest.TestCase):
    def test_an_unfinished_mark_is_closed_or_dropped(self):
        c = lambda s: run_node("AF.closeOpen(" + json.dumps(s) + ")")
        self.assertEqual(c("Steady **areas"), "Steady **areas**")
        self.assertEqual(c("Steady **"), "Steady")
        self.assertEqual(c("run `x"), "run `x`")
        self.assertEqual(c("a *"), "a ")
        self.assertEqual(c("```\ncode"), "```\ncode\n```")
        self.assertEqual(c("**done** all"), "**done** all")

    def test_a_streamed_prefix_never_shows_a_lone_mark(self):
        full = "**Main concerns** and `code` here"
        for n in range(1, len(full) + 1):
            shown = run_node("AF.parseAnswer(AF.closeOpen(" + json.dumps(full[:n]) + "))")
            self.assertNotIn("**", json.dumps(shown), full[:n])


class Source(unittest.TestCase):
    def test_the_panel_draws_nodes_never_markup_and_leaves_the_stored_text(self):
        jsx = (EDIT / "AskFormat.jsx").read_text(encoding="utf-8")
        self.assertNotIn("dangerouslySetInnerHTML", jsx)
        self.assertNotIn("innerHTML", jsx)
        panel = (EDIT / "AskPanel.jsx").read_text(encoding="utf-8")
        self.assertIn("<FormattedAnswer text={t.text} sources={cited(t)} open={openCite} />", panel)
        self.assertIn("text: b.answer", panel)       # the turn (and the kept chat) holds the model's own words


if __name__ == "__main__":
    unittest.main()
