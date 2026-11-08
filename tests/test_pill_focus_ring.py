"""#996: the chosen (aqua) half of the View | Edit pill shows a dark keyboard ring, at least 3:1 on its aqua fill, in light and in dark, at 1400 and 900 px.

Run: python3 dev/run_tests.py test_pill_focus_ring
Same measured-contrast method as test_seg_focus_ring (#952): the real page and a real server over the fictional demo data, the chosen half focused from the
keyboard's point of view (:focus-visible); the dark inner ring (an inset box-shadow in --pill-fg) is measured against both ends of the fill and the plain
colour under it. The outset ring the pill already had stays (offset 1), and the half that is not chosen keeps no inner ring. Chrome is required.
"""
import json
import re
import unittest

from test_seg_focus_ring import SegFocusRing as _Base, fill_colours, ratio, rgb, tearDownModule  # noqa: F401
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, page_target  # noqa: E402

MEASURE = r"""(() => {
  const modes = document.querySelector('.rbar .modes.seg');
  const on = modes.querySelector('.mode[aria-pressed="true"]');
  const off = modes.querySelector('.mode[aria-pressed="false"]');
  const read = (b) => { b.focus({ preventScroll: true }); const cs = getComputedStyle(b); return { visible: b.matches(':focus-visible'), shadow: cs.boxShadow, offset: parseFloat(cs.outlineOffset), bg: cs.backgroundImage, fill: cs.backgroundColor }; };
  const a = read(on);
  const th = getComputedStyle(modes, '::before');
  a.thumb = th.content !== 'none' ? { bg: th.backgroundImage, fill: th.backgroundColor } : null;
  const b = off ? read(off) : null;
  return JSON.stringify({ on: a, off: b, text: on.textContent.trim() });
})()"""


def solid_fills(bg_image, bg_color):
    """The gradient's stops, and the plain colour under it unless that is fully see-through."""
    out = [rgb(m) for m in re.findall(r"rgba?\([^)]*\)", bg_image)]
    nums = re.findall(r"[\d.]+", bg_color)
    if not (len(nums) == 4 and float(nums[3]) == 0):
        out.append(rgb(bg_color))
    return out


class PillFocusRing(unittest.TestCase):
    setUp = _Base.setUp      # the same real server over the demo data
    read = _Base.read

    def measure_pill(self, cdp, width, theme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-reduced-motion", "value": "reduce"}]}, sid)      # pinned: no transition is mid-way when the ring is measured
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#dashboard&p=TUL"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
        cdp.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-mode=edit]')", sid)), "the Edit half is on the page")
        cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelector('.rbar .modes.seg .mode[data-mode=edit]').getAttribute('aria-pressed') === 'true'", sid)), "the Edit half is the chosen one")
        self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "the page's motion has finished before anything is measured")
        for kind in ("keyDown", "keyUp"):
            cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
        return json.loads(cdp.js(MEASURE, sid))

    def test_the_chosen_half_of_the_pill_has_a_dark_ring_3_to_1_on_its_aqua_at_both_widths_in_both_looks(self):
        with chrome() as cdp:
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    got = self.measure_pill(cdp, width, theme)
                    where = f"{width} px, {theme}, {got['text']}"
                    self.assertEqual(got["text"], "Edit", where + ": the half measured is the Edit half")
                    on = got["on"]
                    self.assertTrue(on["visible"], where + ": shows its keyboard focus")
                    self.assertEqual(on["offset"], 1, where + ": the pill keeps its outset ring")
                    m = re.match(r"(rgba?\([^)]*\))\s+0px 0px 0px (\d+)px inset$", on["shadow"].strip())
                    self.assertTrue(m, f"{where}: an inset inner ring, not {on['shadow']!r}")
                    self.assertGreaterEqual(int(m.group(2)), 2, where + ": the inner ring is at least 2 px")
                    ring = rgb(m.group(1))
                    # the aqua is on the half, or on the thumb under it when the half itself is see-through (a see-through colour is no fill)
                    fills = solid_fills(on["bg"], on["fill"]) + (solid_fills(on["thumb"]["bg"], on["thumb"]["fill"]) if on["thumb"] else [])
                    self.assertTrue(fills, where + ": the aqua fill was found")
                    for fill in fills:
                        self.assertGreaterEqual(ratio(ring, fill), 3.0, f"{where}: ring {ring} on fill {fill} is {ratio(ring, fill):.2f}:1")
                    if got["off"]:
                        self.assertEqual(got["off"]["shadow"], "none", where + ": the half that is not chosen has no inner ring")


class PillRuleIsEditOnly(unittest.TestCase):
    """The pill is Edit's: its inner ring is in edit.css, so the published page (shell.css only) is byte-for-byte without it."""
    RULE = '.rbar .seg .mode[aria-pressed="true"]:focus-visible'

    def test_the_rule_is_in_edit_css_and_the_published_css_and_shell_css_do_not_have_it(self):
        import sys
        from pathlib import Path
        root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(root / "dev" / "tools"))
        import build_page
        page = root / "src" / "clark" / "page"
        self.assertIn(self.RULE, (page / "src" / "edit" / "edit.css").read_text(encoding="utf-8"))
        self.assertNotIn(".rbar .seg .mode", (page / "shell.css").read_text(encoding="utf-8").replace(".rbar .modes.seg.glide .mode", ""))
        self.assertNotIn(self.RULE, build_page.page_css(build_page.ENTRY_VIEW), "the published page's css")
        self.assertNotIn("inset 0 0 0 2px var(--pill-fg)", build_page.page_css(build_page.ENTRY_VIEW))
        self.assertIn(self.RULE, build_page.page_css(build_page.ENTRY), "the served page's css")


if __name__ == "__main__":
    unittest.main()
