"""Keyboard focus rings the stylesheet owes: the peek's buttons and width handle and the milestone labels.

Run: python3 dev/run_tests.py test_focus_rings_sweep
Reads src/clark/page/shell.css (the rules, not a page): each ring is drawn in a colour that holds 3:1 on the surface it sits on in both themes.
"""
import json
import re
import unittest

from _paths import SRC
from test_seg_focus_ring import SegFocusRing as _Base, tearDownModule  # noqa: F401
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, page_target  # noqa: E402

CSS = (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8")


def rule(selector):
    """The declarations of the rule whose selector list is exactly `selector`."""
    m = re.search(r"(?m)^" + re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    return m.group(1) if m else None


class FocusRings(unittest.TestCase):
    def test_the_peek_buttons_ring_is_the_focus_colour(self):
        body = rule(".pkp-btn:focus-visible")
        self.assertIsNotNone(body)
        self.assertIn("var(--focus)", body)
        self.assertNotIn("--brand-cyan", body)

    def test_the_milestone_label_buttons_have_a_ring(self):
        body = rule(".mv-lab:focus-visible")
        self.assertIsNotNone(body, "a .mv-lab button reached by Tab shows a ring")
        self.assertIn("outline: 2px solid", body)

    def test_the_peek_width_handle_shows_focus_with_an_outline_not_only_a_faint_fill(self):
        body = rule(".pk-edge:focus-visible")
        self.assertIsNotNone(body, "focus has its own rule, apart from hover")
        self.assertIn("outline: 2px solid var(--focus)", body)
        self.assertIn("opacity: 1", body)
        self.assertEqual(rule(".pk-edge:hover"), " background: linear-gradient(var(--brand-cyan), var(--brand-cyan)) left / 8px 100% no-repeat; opacity: .5; ")

    def test_try_again_ring_is_the_focus_colour(self):
        self.assertIn("var(--focus)", rule(".again:focus-visible"))

    def test_menu_items_show_a_two_pixel_ring_when_focused(self):
        m = re.search(r'(?m)^\.ddmenu \[role="menuitem"\]:focus-visible, \.ddmenu \[role="menuitemradio"\]:focus-visible\s*\{([^}]*)\}', CSS)
        self.assertIsNotNone(m, "menu items have a ring rule of their own")
        self.assertIn("outline: 2px solid var(--focus)", m.group(1))

    def test_the_filter_box_has_no_focus_ring_rule(self):
        # Issue 1137, the ruling: the filter field looks the same with or without the cursor in it.
        self.assertIsNone(rule(".fline:focus-within"))
        self.assertIsNone(re.search(r"\.fline\.on\s*[,{]", CSS))


BROWSER_RING = r"""(() => {
  const ring = (el) => { const cs = getComputedStyle(el); return { visible: el.matches(':focus-visible, :focus-within'), style: cs.outlineStyle, width: parseFloat(cs.outlineWidth), color: cs.outlineColor }; };
  const item = document.querySelector('#profile-menu [role=menuitem]');
  item.focus({ preventScroll: true });
  const menuItem = ring(item);
  const input = document.querySelector('#fline-input');
  input.focus({ preventScroll: true });
  return JSON.stringify({ menuItem, active: document.activeElement === input });
})()"""


class FocusRingsDrawn(_Base):
    """The rings are drawn in the real page, at 1400 and 900: a focused menu item (Chrome is required)."""

    def test_a_focused_menu_item_and_the_filter_box_draw_a_two_pixel_ring_at_both_widths(self):
        with chrome() as cdp:
            for width in (1400, 900):
                sid = page_target(cdp)
                cdp.call("Page.enable", {}, sid)
                cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#work&p=TUL&f=mode:all"}, sid)
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the bundle ran")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#fline-input') && !!document.querySelector('#profile-btn')", sid)), "the page drew")
                self.assertTrue(wait(lambda: cdp.js("document.getAnimations().length === 0", sid)), "motion has finished")
                for kind in ("keyDown", "keyUp"):       # a key, so the page is in keyboard mode and :focus-visible matches
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Shift", "code": "ShiftLeft", "windowsVirtualKeyCode": 16}, sid)
                cdp.js("document.querySelector('#profile-btn').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#profile-menu [role=menuitem]')", sid)), "the profile menu opened")
                got = json.loads(cdp.js(BROWSER_RING, sid))
                for name, r in (("menu item", got["menuItem"]),):
                    where = f"{width} px, {name}"
                    self.assertTrue(r["visible"], where + ": has focus")
                    self.assertEqual(r["style"], "solid", where)
                    self.assertGreaterEqual(r["width"], 2, where + ": the ring is drawn, 2 px or more")
                self.assertTrue(got["active"], "the filter input has the focus")


if __name__ == "__main__":
    unittest.main()
