"""Row 1214: half width pairs, in the real grid, at 1400 and at 900 only.

At 1400 a section on its own can take half of a row: the middle of it offers its left or right half, and the drop makes a pair whose two
halves are each half the row. Over a pair only a row above or below is offered, never a half, so a row holds two across at most. At 900
the grid is one column (shell.css): only full width places are offered (columns 1, from drag.js), a pair already there stacks, and no drop
makes a new pair.

Run: python3 dev/run_tests.py test_pair_widths_1214
The page is bare: the real shell.css and tokens on a page with the real logic/placement.js (bundled by the pinned esbuild in a temporary
folder), the sections drawn with the slot classes placement gives, the rectangles read from Chrome. The columns value is the very
expression drag.js uses, copied out of its source. The Mutants class changes one thing at a time (the query, the expression, the CSS, the
logic) and requires the same checks to fail. Chrome is required: these tests fail, never skip, without it.
"""
import contextlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark.page import strip_css_comments  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "pair_layout_demo.js"
DRAG = (PAGE_SRC / "edit" / "drag.js").read_text(encoding="utf-8")
SHELL = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")
TOKENS = (SRC / "clark" / "brand" / "tokens.css").read_text(encoding="utf-8")
PLACEMENT = (PAGE_SRC / "logic" / "placement.js").read_text(encoding="utf-8")


def sec(id, title, beside=0):
    return {"id": id, "type": "text", "title": title, "beside": beside, "hidden": 0}


# Fictional. Rows: [a] [b] [c d] [e] [f]
SECTIONS = [sec("a", "Summary"), sec("b", "Milestones"), sec("c", "This week", beside=1), sec("d", "Next week"),
            sec("e", "Risks and issues"), sec("f", "Decisions")]
GAP_TOL = 1.5          # px: rounding of a grid track
REACH = 24             # px: a pair's right half reaches back across the column gap (shell.css, .sec.slot-right: margin-left -24px, padding-left 24px)


def page_html(shell=SHELL, drag=DRAG, placement=PLACEMENT):
    """The test page for the given sources (the real ones, or one changed)."""
    query = re.search(r'const STACKED = "([^"]+)";', drag)
    expr = re.search(r"const columns = ([^;]+);", drag)
    assert query and expr, "drag.js still reads its columns the way this test copies"
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "src" / "logic").mkdir(parents=True)
        (Path(tmp) / "src" / "logic" / "placement.js").write_text(placement, encoding="utf-8")
        out = Path(tmp) / "t.js"
        done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                            *build_page.preact_flags(), f"--alias:@src={Path(tmp) / 'src'}", str(DEMO), f"--outfile={out}"],
                           cwd=tmp, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
    css = strip_css_comments(TOKENS + shell).replace("</style", "<\\/style")
    glue = f"const STACKED = {json.dumps(query.group(1))}; window.columnsNow = () => {expr.group(1)};"
    return (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title><style>{css}\nbody {{ margin: 0; }}</style></head>\n'
            f'<body><div id="root"></div>\n<script>{glue}</script>\n<script>{script}</script>\n</body></html>\n')


class Browser(unittest.TestCase):
    """One server and one headless Chrome for the class; `source` is what the page is built from."""
    source = {}

    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.html = None
        cls.server = Running(page_html=lambda: cls.page())
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cls.cdp.call("Page.enable", {}, cls.sid)

    @classmethod
    def page(cls):
        if cls.html is None:
            cls.html = page_html(**cls.source)
        return cls.html

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def at(self, width):
        self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.probe)", self.sid)), "the test bundle ran")
        self.assertEqual(self.cdp.js("window.innerWidth", self.sid), width)

    def probe(self, id, at, fx, fy, sections=SECTIONS):
        expr = f"T.probe({json.dumps(sections)}, {json.dumps(id)}, {json.dumps(at)}, {fx}, {fy})"
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), got)
        return json.loads(got)

    def grid_width(self):
        return self.cdp.js("document.querySelector('.secs').getBoundingClientRect().width", self.sid)

    def problems(self, width):
        """What is wrong with half width pairs at this width; empty when the page does what row 1214 says."""
        self.at(width)
        bad = []
        self.probe("a", "b", 0.5, 0.5)
        full = self.grid_width()
        wide = width > 900
        # 1. the middle of a section on its own, left and right
        for side, fx in (("left", 0.25), ("right", 0.75)):
            p = self.probe("a", "b", fx, 0.5)
            if wide:
                if p["columns"] != 2 or p["target"] != {"beside": "b", "side": side}:
                    bad.append(f"{width}: the {side} half of a lone section is offered")
                elif not p["after"]:
                    bad.append(f"{width}: dropping on the {side} half is refused")
                else:
                    a, b = p["after"]["a"], p["after"]["b"]
                    pair = (a, b) if side == "left" else (b, a)
                    if abs(pair[0]["width"] - (pair[1]["width"] - REACH)) > GAP_TOL:
                        bad.append(f"{width}: the two halves are not the same width")
                    if not (pair[0]["width"] < full / 2 + GAP_TOL and pair[1]["width"] < full / 2 + REACH + GAP_TOL):
                        bad.append(f"{width}: the pair did not shrink both to half")
                    if not (pair[0]["left"] < pair[1]["left"] and abs(pair[0]["top"] - pair[1]["top"]) < GAP_TOL):
                        bad.append(f"{width}: the halves are not side by side, {side} first as offered")
            else:
                if p["columns"] != 1 or "beside" in (p["target"] or {}):
                    bad.append(f"{width}: only full width places are offered, columns 1")
        # 2. over a pair: only above or below, wherever the pointer is across it
        for fx in (0.1, 0.5, 0.9):
            for fy in (0.1, 0.5, 0.9):
                for over in ("c", "d"):
                    t = self.probe("a", over, fx, fy)["target"]
                    if t is None or "beside" in t:
                        bad.append(f"{width}: over a pair only above or below is offered")
        # 3. the pair at the start: side by side at 1400, stacked at 900
        start = self.probe("a", "b", 0.5, 0.5)["before"]
        same_row = abs(start["c"]["top"] - start["d"]["top"]) < GAP_TOL
        if wide and not (same_row and abs(start["c"]["width"] - (start["d"]["width"] - REACH)) < GAP_TOL and start["c"]["width"] < full / 2 + GAP_TOL):
            bad.append(f"{width}: an existing pair is two halves across")
        if not wide and (same_row or start["c"]["width"] < full - GAP_TOL or start["d"]["width"] < full - GAP_TOL):
            bad.append(f"{width}: an existing pair stacks, each full width")
        # 4. whatever is dropped, wherever: never three across, and at 900 no new pair
        pairs_at_start = 1
        for moving in ("a", "e"):
            for over in "abcdef":
                for fy in (0.05, 0.5, 0.95):
                    for fx in (0.25, 0.75):
                        p = self.probe(moving, over, fx, fy)
                        if not p["after"]:
                            continue
                        tops = {}
                        for r in p["after"].values():
                            tops[round(r["top"])] = tops.get(round(r["top"]), 0) + 1
                        if max(tops.values()) > (2 if wide else 1):
                            bad.append(f"{width}: a row holds {max(tops.values())} across")
                        if not wide and sum(len(r) == 2 for r in p["rows"]) > pairs_at_start:
                            bad.append(f"{width}: a drop made a new pair")
        return sorted(set(bad))


class RealLayout(Browser):
    def test_at_1400_a_lone_section_takes_half_a_pair_shrinks_both_and_a_pair_offers_only_above_or_below(self):
        self.assertEqual(self.problems(1400), [])

    def test_at_900_only_full_width_places_are_offered_and_no_pair_is_made(self):
        self.assertEqual(self.problems(900), [])

    def test_the_media_query_drag_reads_is_the_one_shell_css_stacks_at(self):
        self.assertIn("@media (max-width: 900px) { .secs { grid-template-columns: minmax(0, 1fr); }", SHELL)
        self.assertIn('const STACKED = "(max-width: 900px)";', DRAG)
        self.assertIn("const columns = window.matchMedia(STACKED).matches ? 1 : 2;", DRAG)


class Mutants(unittest.TestCase):
    """One thing changed at a time; the checks must then find a problem at 1400, at 900, or both."""

    def run_mutant(self, name, width, **source):
        class M(Browser):
            pass
        M.source = source
        M.__name__ = name
        M.setUpClass()
        try:
            m = M("problems")
            return m.problems(width)
        finally:
            M.tearDownClass()

    def test_each_mutant_is_found(self):
        def swap(text, old, new):
            assert text.count(old) == 1, old
            return text.replace(old, new)
        cases = [
            ("drag reads a window that is too narrow", 900, dict(drag=swap(DRAG, '"(max-width: 900px)"', '"(max-width: 600px)"'))),
            ("drag always offers two columns", 900, dict(drag=swap(DRAG, "matches ? 1 : 2", "matches ? 2 : 2"))),
            ("the grid never stacks", 900, dict(shell=swap(SHELL, "@media (max-width: 900px) { .secs { grid-template-columns: minmax(0, 1fr); } .slot-left, .slot-right { grid-column: 1; } }", ""))),
            ("the left half runs the whole row", 1400, dict(shell=swap(SHELL, ".slot-left { grid-column: 1; }", ".slot-left { grid-column: 1 / -1; }"))),
            ("a pair is offered a half", 1400, dict(placement=swap(PLACEMENT, "columns === 2 && others.length === 1", "columns === 2"))),
            ("the half is never offered", 1400, dict(placement=swap(PLACEMENT, "columns === 2 && others.length === 1", "false"))),
            ("the left half is the right", 1400, dict(placement=swap(PLACEMENT, 'point.x < r.left + (r.right - r.left) / 2 ? "left" : "right"', 'point.x < r.left + (r.right - r.left) / 2 ? "right" : "left"'))),
        ]
        for name, width, source in cases:
            with self.subTest(name):
                self.assertNotEqual(self.run_mutant(name, width, **source), [], f"mutant not found: {name}")


if __name__ == "__main__":
    unittest.main()
