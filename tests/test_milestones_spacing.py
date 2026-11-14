"""Row 1083: the milestones list is less cramped. Each row has 14 px above and below its text, and a light 1 px line (the rail's
grey, --grey-200, so dark follows the token) runs under every row but the last, starting at the text so the rail and its dots stay unbroken.
The words stay: "Show all N milestones" / "Show the first 5". The rows keep their amber changed tint and the .out look.

Run: python3 dev/run_tests.py test_milestones_spacing
Without a browser: the rules are in shell.css and, because shell.css is inlined into the published page (rule 6), in the built view page.
With headless Chrome (fails, never skips, without it): the live page (demo database, fixed CLARK_NOW) and a published file of the same
demo project, each at 1400 and 900 px, light and dark: the computed padding, the line on every row but the last and on none after the last,
the line's left edge at the text (right of the rail), the rail and the dots as before, "Show the first 5" after "Show all", and nothing
scrolling sideways. Laptop widths only.
"""
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC

from clark import page, publish
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test
PAD = 14                                                     # 14 px in both densities (item 1083), so the default Compact has it too
PADS = {"comfortable": 14, "compact": 14}
CODE = "MOSS"                                                        # the demo project with more than five milestones
WIDTHS = (1400, 900)

# For each list row: the cells' padding, the line under it (the row's ::after, read as computed style), the rail, the dot and whether
# the next row starts where this one ends. Colours are read as the browser gives them, and --grey-200 is probed the same way.
LOOK = r"""(() => {
  const probe = (v) => { const e = document.createElement('i'); e.style.borderColor = `var(${v})`; e.style.borderStyle = 'solid'; document.body.appendChild(e); const c = getComputedStyle(e).borderTopColor; e.remove(); return c; };
  const rows = [...document.querySelectorAll('.msl-row')];
  const out = rows.map((row, i) => {
    const cells = row.querySelector('.msl-cells'), cs = getComputedStyle(cells), rs = getComputedStyle(row), after = getComputedStyle(row, '::after');
    const rb = row.getBoundingClientRect(), n = row.querySelector('.node'), nb = n.getBoundingClientRect(), ns = getComputedStyle(n);
    const next = rows[i + 1] ? rows[i + 1].getBoundingClientRect() : null;
    const drawn = after.content !== 'none' && after.display !== 'none';
    return {padTop: parseFloat(cs.paddingTop), padBottom: parseFloat(cs.paddingBottom), padLeft: parseFloat(cs.paddingLeft), h: rb.height,
      line: drawn ? {h: parseFloat(after.height), left: parseFloat(after.left), right: parseFloat(after.right), bottom: parseFloat(after.bottom),
                     pos: after.position, colour: after.backgroundColor} : null,
      rail: {w: parseFloat(rs.borderLeftWidth), style: rs.borderLeftStyle, colour: rs.borderLeftColor},
      dot: {w: nb.width, h: nb.height, ring: parseFloat(ns.borderTopWidth), round: ns.borderTopLeftRadius,
            onRail: Math.abs((nb.left + nb.width / 2) - rb.left) <= 8, mid: Math.abs((nb.top + nb.height / 2) - (rb.top + rb.height / 2)) <= 2},
      touchesNext: next ? Math.abs(next.top - rb.bottom) <= 1 : null};
  });
  const all = document.querySelector('.msl-all'), box = document.querySelector('.msl-box');
  return {rows: out, grey200: probe('--grey-200'), all: all ? all.textContent.trim() : null,
          pageScroll: document.documentElement.scrollWidth > window.innerWidth, listScroll: box.scrollWidth > box.clientWidth + 1};
})()"""


def show_all(cdp, sid):
    """Press "Show all N milestones" so every row is on the page and the button reads "Show the first 5"."""
    if cdp.js("!!document.querySelector('.msl-all')", sid) and cdp.js("document.querySelector('.msl-all').textContent", sid).startswith("Show all"):
        cdp.js("document.querySelector('.msl-all').click()", sid)
        wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length", sid) > 5)


def open_at(cdp, width, scheme):
    sid = page_target(cdp)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
    cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    return sid


class Spacing(unittest.TestCase):
    """The same checks on the live page and on a published file (shell.css is inlined into both)."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def check(self, got, where, pad=PAD):
        rows = got["rows"]
        self.assertGreater(len(rows), 5, f"{where}: every milestone is on the page")
        self.assertEqual(got["all"], "Show the first 5", f"{where}: the words after Show all")
        self.assertFalse(got["pageScroll"], f"{where}: no sideways scroll on the page")
        self.assertFalse(got["listScroll"], f"{where}: nothing scrolls inside the list")
        for i, r in enumerate(rows):
            last = i == len(rows) - 1
            self.assertEqual((r["padTop"], r["padBottom"]), (pad, pad), f"{where}: row {i} has {pad} px above and below")
            # The rail and its dot are as they were: a 2 px grey-200 line down the left, a 12 px ring on it half way down the row.
            self.assertEqual((r["rail"]["w"], r["rail"]["style"], r["rail"]["colour"]), (2, "solid", got["grey200"]), f"{where}: row {i} rail")
            self.assertEqual((r["dot"]["w"], r["dot"]["h"], r["dot"]["ring"], r["dot"]["round"]), (12, 12, 2, "50%"), f"{where}: row {i} dot")
            self.assertTrue(r["dot"]["onRail"] and r["dot"]["mid"], f"{where}: row {i} dot sits on the rail half way down")
            if last:
                self.assertIsNone(r["line"], f"{where}: no line under the last row")
                self.assertIsNone(r["touchesNext"], where)
                continue
            line = r["line"]
            self.assertIsNotNone(line, f"{where}: a line under row {i}")
            self.assertEqual((line["pos"], line["h"], line["bottom"], line["right"]), ("absolute", 1, 0, 0), f"{where}: row {i} line is 1 px along the row's foot")
            self.assertEqual(line["left"], r["padLeft"], f"{where}: row {i} line starts at the text")
            self.assertGreater(line["left"], 0, f"{where}: row {i} line stays off the rail")
            self.assertEqual(line["colour"], got["grey200"], f"{where}: row {i} line is the rail's grey")
            self.assertEqual(line["colour"], r["rail"]["colour"], f"{where}: row {i} line and rail are one colour")
            self.assertTrue(r["touchesNext"], f"{where}: row {i + 1} starts where row {i} ends, so the line sits between them")

    def test_the_live_page_at_1400_and_900_light_and_dark(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        greys = {}
        for width in WIDTHS:
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = open_at(cdp, width, scheme)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#milestones&p={CODE}"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)), "the list drew")
                    show_all(cdp, sid)
                    for dens, pad in PADS.items():
                        cdp.js(f"document.documentElement.dataset.density = '{dens}'", sid)
                        got = cdp.js(LOOK, sid)
                        self.check(got, f"live {dens} {scheme} {width}px", pad)
                    greys[scheme] = got["grey200"]
        self.assertNotEqual(greys["light"], greys["dark"], "the line's grey follows the theme's token")

    def test_the_published_file_at_1400_and_900_light_and_dark(self):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(self.store, CODE, folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width in WIDTHS:
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = open_at(cdp, width, scheme)
                    cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                    cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.msl-row')", sid)))
                    show_all(cdp, sid)
                    for dens, pad in PADS.items():
                        cdp.js(f"document.documentElement.dataset.density = '{dens}'", sid)
                        self.check(cdp.js(LOOK, sid), f"published {dens} {scheme} {width}px", pad)


class Stylesheet(unittest.TestCase):
    """The rules in shell.css, and the same rules in the built view page the published file is made from (rule 6)."""

    def rules(self, css):
        cells = re.search(r"\n\.msl-cells \{([^}]*)\}", css)
        line = re.search(r"\.msl-row:not\(:last-child\)::after \{([^}]*)\}", css)
        return cells.group(1) if cells else None, line.group(1) if line else None

    def check(self, css, where):
        cells, line = self.rules(css)
        self.assertIsNotNone(cells, f"{where}: the .msl-cells rule")
        self.assertIn("padding: var(--d-msl-y) var(--space-2) var(--d-msl-y) 22px", cells, f"{where}: the spacing token above and below the text")
        self.assertRegex(css, r'html\[data-density="comfortable"\] \{[^}]*--d-msl-y: %dpx' % PAD, f"{where}: Comfortable has {PAD} px above and below")
        self.assertRegex(css, r":root \{[^}]*--d-msl-y: %dpx" % PAD, f"{where}: Compact has {PAD} px above and below")
        self.assertIsNotNone(line, f"{where}: a line under every row but the last")
        for part in ("content: \"\"", "position: absolute", "left: 22px", "right: 0", "bottom: 0", "height: 1px", "background: var(--grey-200)"):
            self.assertIn(part, line, f"{where}: the line rule has {part}")

    def test_shell_css_has_the_padding_and_the_line(self):
        self.check((SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8"), "shell.css")

    def test_the_built_view_page_carries_the_same_rules(self):
        self.check(page.page_html(view=True), "page-view.html")


if __name__ == "__main__":
    unittest.main()
