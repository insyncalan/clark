"""#130 point 6, #912: the crowded Milestones page (ten milestones within two weeks of each other), in the app and in the published file.

Run: python3 dev/run_tests.py test_milestones_crowded
These tests were the end of tests/test_milestones_page.py, unchanged; they are 18 Chrome launches and are a file of their own so that file
and this one each stay short on a hosted runner. Every label's box is measured; no two overlap and the Today label stays clear of every
label, mark and month name, in four font variants at 1400, 900 and 390 px.
"""
import json
import shutil
import tempfile
import time
import unittest
from _editor_checks import for_url
from pathlib import Path

from _demo import USER, DemoStore
from clark import page, publish
from test_milestones_page import EMPTY_BRANDING, MODULE, TODAY
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

# #130 point 6: every label's box is measured; no two overlap and the Today label stays clear of every label, mark and month name.
CROWDED = [("Design sign-off for the whole regional programme", "2026-10-26", "2026-11-09"), ("Vendor contract signed", "2026-10-27", None),
           ("Data migration rehearsal one", "2026-10-28", "2026-11-20"), ("Go-live readiness review", "2026-10-29", None),
           ("Training for every team lead complete", "2026-10-30", "2026-12-04"), ("Security test passed", "2026-11-02", None),
           ("Pilot users onboarded", "2026-11-03", "2026-11-17"), ("Cutover plan approved by the board", "2026-11-04", None),
           ("Hypercare starts", "2026-11-05", None), ("Old system switched off", "2026-11-06", "2026-11-08")]
BOXES = """(() => {
  const EPS = 1;                                        // one pixel of tolerance for sub-pixel differences between fonts and systems
  const box = (e) => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, n: e.dataset.lab || e.className}; };
  const hit = (a, b) => a.l < b.r - EPS && b.l < a.r - EPS && a.t < b.b - EPS && b.t < a.b - EPS;
  const labs = [...document.querySelectorAll('.mv-lab')].map(box);
  const today = box(document.querySelector('.mv-today b'));
  const text = (e) => { const g = document.createRange(); g.selectNodeContents(e); const r = g.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, n: 'month ' + e.textContent}; };
  const others = [...document.querySelectorAll('.mv-mk')].map(box).concat([...document.querySelectorAll('.mv-month')].map(text));
  const pairs = [];
  for (let i = 0; i < labs.length; i++) for (let j = i + 1; j < labs.length; j++) if (hit(labs[i], labs[j])) pairs.push([labs[i].n, labs[j].n]);
  const lanes = {};
  for (const e of document.querySelectorAll('.mv-lab')) (lanes[e.style.top] = lanes[e.style.top] || []).push(box(e));
  const laneClash = Object.values(lanes).flatMap((l) => l.flatMap((a, i) => l.slice(i + 1).filter((b) => a.l < b.r - EPS && b.l < a.r - EPS).map((b) => [a.n, b.n])));
  const wrap = document.querySelector('.mv-wrap'), strip = document.querySelector('.mv-strip').getBoundingClientRect();
  const lowest = Math.max(...labs.map((l) => l.b));
  return {count: labs.length, pairs, laneClash, lowest: lowest - strip.top, stripHeight: strip.height, fits: wrap.scrollHeight <= wrap.clientHeight + EPS, bar: wrap.offsetHeight - wrap.clientHeight - 2,
           todayHits: labs.concat(others).filter((o) => hit(today, o)).map((o) => o.n),
          inside: labs.every((l) => l.l >= document.querySelector('.mv-strip').getBoundingClientRect().left - 1)};
})()"""


def add_crowded(store, project):
    with store.step("dashboard", USER) as step:
        for name, base, fc in CROWDED:
            step.create("milestones", {"project": project, "name": name, "baseline_date": base, "forecast_date": fc,
                                       "client_visible": 1, "source": "demo"})


class Crowded(unittest.TestCase):
    """A project with ten milestones within two weeks of each other, in the app and in the published file."""

    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        add_crowded(cls.store, "TUL")
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    # Other fonts, so the layout is shown not to depend on one system's metrics: a wide one, a narrow one, and a classic
    # (space-taking) sideways scrollbar as Linux draws it. Each is a style put in before the page's own script runs.
    FONTS = {
        "default": "",
        "wide": ".mv-lab, .mv-month, .mv-today { font-family: 'Courier New', 'DejaVu Sans Mono', monospace !important; letter-spacing: 0.08em !important; }",
        "narrow": ".mv-lab, .mv-month, .mv-today { font-family: 'Arial Narrow', 'DejaVu Sans Condensed', sans-serif !important; letter-spacing: -0.06em !important; }",
        "scrollbar": ".mv-wrap::-webkit-scrollbar { height: 15px; background: #ddd; } .mv-wrap::-webkit-scrollbar-thumb { background: #999; }",
    }
    VARIANTS = [("default", 1400), ("default", 900), ("default", 390), ("wide", 1400), ("wide", 900), ("narrow", 1400), ("narrow", 390), ("scrollbar", 1400), ("scrollbar", 390)]

    def style_for(self, font):
        css = self.FONTS[font]       # a constructed style sheet: the page's content-security rule would drop an inline <style>
        return "" if not css else "(() => { const sheet = new CSSStyleSheet(); sheet.replaceSync(%s); document.adoptedStyleSheets = [...document.adoptedStyleSheets, sheet]; })();" % json.dumps(css)

    def check(self, cdp, sid, where):
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) >= len(CROWDED)), where)
        time.sleep(0.4)                       # the labels are measured, then laid out again
        got = cdp.js(BOXES, sid)
        self.assertGreaterEqual(got["count"], len(CROWDED) + 1, where)       # row 1020: one label a milestone (a slipped one carries '+N days' on it), no separate expected-date label
        if "scrollbar font" in where:
            self.assertGreaterEqual(got["bar"], 10, f"{where}: this variant really draws a scrollbar that takes room inside the box")
        self.assertEqual(got["pairs"], [], f"{where}: no two labels overlap")
        self.assertEqual(got["laneClash"], [], f"{where}: no two labels in one lane overlap")
        self.assertTrue(got["fits"], f"{where}: the box is tall enough for the lanes actually used (lowest label {got['lowest']}, strip {got['stripHeight']})")
        self.assertEqual(got["todayHits"], [], f"{where}: the Today label is clear of every label, mark and month name")
        self.assertTrue(got["inside"], where)

    def test_in_the_app_at_1400_900_and_390_px(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        for font, width in self.VARIANTS:
            with self.subTest(font=font, width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for(font)}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600}, sid)
                cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#milestones&p=TUL")}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
                self.check(cdp, sid, f"app {font} font {width}px")

    def test_many_lanes_in_a_wider_font_still_fit_the_box(self):
        """A wider font than this machine's (forced here) needs more lanes than the 900 px box limit: the box grows to the measured lanes."""
        extra = [(f"Extra milestone number {n} with a long name", f"2026-11-{10 + n % 3:02d}", f"2026-11-{20 + n % 5:02d}") for n in range(40)]       # row 1020: a label is one line now, so more of them make the lanes the old 900 px limit could not hold
        store, folder, _ = load_demo()               # its own store: the shared one keeps ten milestones for the other tests
        self.addCleanup(shutil.rmtree, str(folder), True)
        self.addCleanup(store.close)
        add_crowded(store, "TUL")
        with store.step("dashboard", USER) as step:
            for name, base, fc in extra:
                step.create("milestones", {"project": "TUL", "name": name, "baseline_date": base, "forecast_date": fc, "client_visible": 1, "source": "demo"})
        s = Running(data_for=store.data_for, projects=lambda archived=False: store.read("projects"), page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        self.FONTS["wider"] = ".mv-lab, .mv-month, .mv-today { font-family: 'Courier New', 'DejaVu Sans Mono', monospace !important; letter-spacing: 0.2em !important; }"
        self.addCleanup(self.FONTS.pop, "wider", None)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for("wider")}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#milestones&p=TUL")}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-lab').length", sid) >= len(CROWDED) + len(extra)))
            time.sleep(0.4)
            got = cdp.js(BOXES, sid)
            self.assertGreater(got["lowest"], 880, "this check really needs more lanes than the old 900 px limit allowed")
            self.assertTrue(got["fits"], f"the box is tall enough for the lanes actually used (lowest label {got['lowest']}, strip {got['stripHeight']})")
            self.assertEqual(got["laneClash"], [])

    def test_in_the_published_file_at_1400_900_and_390_px(self):
        demo = DemoStore()
        add_crowded(demo.store, "ABC")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for font, width in self.VARIANTS:
            with self.subTest(font=font, width=width), chrome() as cdp:
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE + ";" + self.style_for(font)}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": width < 600}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.mv-wrap')", sid)))
                self.check(cdp, sid, f"published {font} font {width}px")

    def test_label_lines_use_each_labels_own_width(self):
        text = MODULE.read_text(encoding="utf-8")
        self.assertIn("labelLines(xs, width, gap = 0)", text)


if __name__ == "__main__":
    unittest.main()
