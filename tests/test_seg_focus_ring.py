"""#952: the chosen half of a segmented group (.seg) keeps a focus ring of at least 3:1 on its aqua fill, in light and in dark.

Run: python3 dev/run_tests.py test_seg_focus_ring
The real page and a real server over the fictional demo data, at 1400 and 900 px, light and dark, on Settings (Appearance), Work items, Milestones and
Use cases. Each chosen half is focused from the keyboard's point of view (:focus-visible) and its ring is measured: the ring's colour against both ends of
the fill (the --pill-bg gradient) is at least 3:1, and the ring is drawn inside the half (a negative offset at least as big as its width) so the fill is
on both sides of it. The View | Edit pill keeps its own outset ring and the two-icon switch keeps the blue ring on its tint. Chrome is required.
"""
import json
import re
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
VIEWS = {"settings": "#settings", "work": "#work&p=TUL&f=mode:all", "milestones": "#milestones&p=TUL", "usecases": "#usecases&p=TUL"}
# every chosen half of a group of words (not the icon pair, not the View | Edit pill), focused, and what its ring and its fill are
MEASURE = r"""(() => {
  const out = [];
  const root = getComputedStyle(document.documentElement);
  for (const b of document.querySelectorAll('.seg:not(.icons):not(.modes) button[aria-pressed="true"], .seg:not(.icons):not(.modes) button[aria-checked="true"], .cal-sc button[aria-current="true"]')) {
    if (!b.getClientRects().length) continue;
    b.focus({ preventScroll: true });
    const cs = getComputedStyle(b);
    out.push({ group: (b.closest('.seg').getAttribute('aria-label') || '?'), text: b.textContent.trim(), visible: b.matches(':focus-visible'), color: cs.outlineColor, style: cs.outlineStyle,
               width: parseFloat(cs.outlineWidth), offset: parseFloat(cs.outlineOffset), bg: cs.backgroundImage, fill: cs.backgroundColor });
  }
  const mode = document.querySelector('.rbar .modes.seg .mode[aria-pressed="true"]');
  let pill = null;
  if (mode) { mode.focus({ preventScroll: true }); const cs = getComputedStyle(mode); pill = { visible: mode.matches(':focus-visible'), color: cs.outlineColor, offset: parseFloat(cs.outlineOffset) }; }
  return JSON.stringify({ halves: out, pill, brand: root.getPropertyValue('--brand-blue').trim() });
})()"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def rgb(text):
    return [int(float(x)) for x in re.findall(r"[\d.]+", text)[:3]]


def lum(c):
    out = []
    for v in c:
        v /= 255
        out.append(v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4)
    return 0.2126 * out[0] + 0.7152 * out[1] + 0.0722 * out[2]


def ratio(a, b):
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def fill_colours(bg_image, bg_color):
    """Every colour the half's fill is made of: the stops of its gradient, and the plain colour under it."""
    stops = [rgb(m) for m in re.findall(r"rgba?\([^)]*\)", bg_image)]
    return stops + [rgb(bg_color)]


class SegFocusRing(unittest.TestCase):
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

    def measure(self, cdp, view, width, theme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{VIEWS[view]}"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        cdp.js("(document.querySelector('[data-mode=edit]') || {click() {}}).click()", sid)
        if view == "milestones":        # the Timeline | Calendar switch: the calendar has its own scale group (Day / Week / ...), aqua on the chosen scale
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-msvb=cal]')", sid)), "the calendar switch is on the page")
            cdp.js("document.querySelector('[data-msvb=cal]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.cal-sc')", sid)), "the calendar drew")
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.seg:not(.icons):not(.modes) button[aria-pressed=\"true\"], .seg:not(.icons):not(.modes) button[aria-checked=\"true\"], .cal-sc button[aria-current=\"true\"]')", sid)),
                        f"{view}: a chosen half is on the page")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
        for kind in ("keyDown", "keyUp"):       # a key, so the page is in keyboard mode and a focused button matches :focus-visible
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
        return json.loads(cdp.js(MEASURE, sid))

    def test_the_ring_on_every_chosen_half_reaches_3_to_1_on_its_fill_at_both_widths_in_both_looks(self):
        seen = set()
        with chrome() as cdp:
            for view in VIEWS:
                for width in (1400, 900):
                    for theme in ("light", "dark"):
                        got = self.measure(cdp, view, width, theme)
                        where = f"{view}, {width} px, {theme}"
                        self.assertTrue(got["halves"], where + ": no chosen half was measured")
                        for h in got["halves"]:
                            label = f"{where}: {h['group']} / {h['text']}"
                            seen.add(h["group"])
                            self.assertTrue(h["visible"], label + " shows its keyboard focus ring")
                            self.assertEqual(h["style"], "solid", label)
                            self.assertGreaterEqual(h["width"], 2, label + ": the ring is at least 2 px")
                            self.assertLessEqual(h["offset"], -h["width"], label + ": the ring is inside the half, so the fill is on both sides of it")
                            ring = rgb(h["color"])
                            for fill in fill_colours(h["bg"], h["fill"]):
                                self.assertGreaterEqual(ratio(ring, fill), 3.0, f"{label}: ring {ring} on fill {fill} is {ratio(ring, fill):.2f}:1")
                        if got["pill"]:
                            self.assertEqual(got["pill"]["offset"], 1, where + ": the View | Edit pill keeps its own outset ring")
        self.assertTrue({"Appearance", "Type", "Milestones view", "Calendar scale", "Layout"} <= seen, f"the groups measured: {sorted(seen)}")


if __name__ == "__main__":
    unittest.main()
