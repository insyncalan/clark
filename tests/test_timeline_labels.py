"""The milestone timeline: no line is drawn through a milestone's name or date.

Run: python3 dev/run_tests.py test_timeline_labels
The real page and a real server over the fictional demo data, at 1400 and 900 px, light and dark. The Today line (and the month
lines) used to be drawn over a label that sat across them ("Staff training complete" was struck through). A label now paints above
the Today line, on the strip's own colour. The Today line is moved onto the middle of each label in turn, so the test does not depend
on what day it is, and the element at the middle of the label must be the label. The browser parts are required: they fail, never
skip, without Chrome (set CLARK_CHROME to its path).
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401  (puts src/ on the path)

from clark import page, server as sv  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")

# For each label: put the Today line on its middle and name the element drawn there (a label, or something else).
PROBE = r"""(() => {
  const today = document.querySelector('.mv-today'); if (!today) return JSON.stringify({ error: 'no Today line' });
  const out = [];
  for (const lab of document.querySelectorAll('.mv-strip .mv-lab')) {
    const strip = lab.closest('.mv-strip'), r = lab.getBoundingClientRect(), s = strip.getBoundingClientRect();
    today.style.left = Math.round(r.left - s.left + r.width / 2 - 1) + 'px';
    const cx = r.left + r.width / 2, cy = r.top + r.height / 2;
    lab.scrollIntoView({ block: 'nearest', inline: 'center' });
    const r2 = lab.getBoundingClientRect(), at = document.elementFromPoint(r2.left + r2.width / 2, r2.top + r2.height / 2);
    const wrap = lab.closest('.mv-wrap'), tops = new Set([...document.querySelectorAll('.mv-strip .mv-lab')].map(l => Math.round(l.getBoundingClientRect().top - s.top)));
    out.push({ lab: lab.dataset.lab, on: at ? (at.closest('.mv-lab') === lab ? 'label' : (at.className || at.tagName)) : 'nothing',
      why: { scrollTop: wrap.scrollTop, offsetHeight: wrap.offsetHeight, clientHeight: wrap.clientHeight, stripHeight: Math.round(s.height), labTop: lab.offsetTop, labHeight: lab.offsetHeight, distinctTops: tops.size, rect: [Math.round(r2.left), Math.round(r2.top), Math.round(r2.width), Math.round(r2.height)] } });
  }
  return JSON.stringify({ labels: out });
})()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


CLEAR = r"""(() => {
  const wrap = document.querySelector('.mv-wrap'), w = wrap.getBoundingClientRect();
  let low = 0; for (const l of document.querySelectorAll('.mv-strip .mv-lab')) low = Math.max(low, l.getBoundingClientRect().bottom);
  return JSON.stringify({ scrolls: wrap.scrollWidth > wrap.clientWidth, clear: Math.round((w.bottom - low) * 10) / 10, wrapH: wrap.offsetHeight, clientH: wrap.clientHeight });
})()"""


class Labels(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.s = Running(data_for=self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived=None):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code)
        finally:
            st.close()

    def test_the_today_line_never_runs_over_a_milestones_name_or_date(self):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#milestones&p=TUL"}, sid)
                    self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-strip .mv-lab').length", sid) > 1), "the timeline drew")
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
                    got = json.loads(cdp.js(PROBE, sid))
                    where = f"{width} px, {theme}"
                    self.assertNotIn("error", got, where)
                    self.assertGreater(len(got["labels"]), 1, where)
                    for item in got["labels"]:
                        self.assertEqual(item["on"], "label", f"{where}: the Today line is drawn over the label {item['lab']} ({item['on']}); geometry {item['why']}")


    def test_the_last_lane_keeps_clear_of_an_overlay_scrollbar(self):
        """macOS draws its scrollbar over the bottom of a box that scrolls sideways while it scrolls: no label may sit under it
        (the Today-line probe then reads the box, not the label). Scrollbars are hidden here as on the Mac (no room taken)."""
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setScrollbarsHidden", {"hidden": True}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#milestones&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-strip .mv-lab').length", sid) > 1), "the timeline drew")
            got = json.loads(cdp.js(CLEAR, sid))
            self.assertTrue(got["scrolls"], "the fixture's line scrolls sideways")
            self.assertGreaterEqual(got["clear"], 16, f"the last label ends {got['clear']} px above the box's bottom edge, inside where an overlay scrollbar is drawn: {got}")

    def test_every_label_has_a_24_px_hit_box(self):
        """The labels are one line (about 18 px of text box); the padded box that takes the click is at least 24 px high."""
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#milestones&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.mv-strip .mv-lab').length", sid) > 1), "the timeline drew")
            got = json.loads(cdp.js("JSON.stringify([...document.querySelectorAll('.mv-strip .mv-lab')].map(l => l.getBoundingClientRect().height))", sid))
            self.assertTrue(got and min(got) >= 24, f"a label's hit box is {min(got)} px high, under 24: {got}")


if __name__ == "__main__":
    unittest.main()
