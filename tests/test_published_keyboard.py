"""Published (view-only) file, keyboard: Tab reaches the skip link first, then every tab, each stop shows a ring, and Esc closes an open peek.

Run: python3 dev/run_tests.py test_published_keyboard
Headless Chrome (required). 1400 and 900 px.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import publish
from test_published_work_no_add import EMPTY_BRANDING, TODAY, open_page
from test_server import chrome, wait
from test_work_filters import need_chrome

WIDTHS = (1400, 900)
STOP = """(() => { const e = document.activeElement; if (!e || e === document.body) return null;
  const s = getComputedStyle(e), r = e.getBoundingClientRect(), c = s.outlineColor;
  const drawn = s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0 && !/rgba?\\(.*,\\s*0\\)$/.test(c);
  return {name: e.tagName + '.' + String(e.className && e.className.baseVal === undefined ? e.className : '') + ':' + (e.getAttribute('aria-label') || e.textContent || '').trim().slice(0, 24),
    ring: drawn || (s.boxShadow !== 'none'), on: r.width > 0 && r.height > 0 && r.right > 0 && r.bottom > 0 && r.left < innerWidth && r.top < innerHeight}; })()"""


def key(cdp, sid, name, code, vk, shift=False):
    for kind in ("keyDown", "keyUp"):
        cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": name, "code": code, "windowsVirtualKeyCode": vk, "modifiers": 8 if shift else 0, **({"text": "\r"} if name == "Enter" and kind == "keyDown" else {})}, sid)


def tab(cdp, sid, shift=False):
    key(cdp, sid, "Tab", "Tab", 9, shift)


class PublishedKeyboard(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.demo.action(description="Draft the cut-over plan", due_date="2026-11-30", status="Open", owner="Example Owner", client_message="Draft the cut-over plan", client_action=1)
        self.demo.action(description="Sign off the test plan", due_date="2026-12-05", status="Open", owner="Example Owner", client_message="Sign off the test plan", client_action=1)
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        self.path = Path(publish.publish(self.demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])

    def walk(self, cdp, sid, limit=80):
        """Tab from the top of the page until focus leaves it; each stop's name, whether it draws a ring and whether it is on screen."""
        cdp.js("window.scrollTo(0, 0); document.activeElement.blur()", sid)
        stops = []
        for _ in range(limit):
            tab(cdp, sid)
            st = cdp.js(STOP, sid)
            if st is None:
                break
            stops.append(st)
        return stops

    def test_tab_goes_skip_link_then_the_chosen_tab_and_every_stop_shows_a_ring(self):
        for width in WIDTHS:
            for scheme in ("light", "dark"):
                for name in ("Dashboard", "Work items", "Milestones", "Use cases"):
                    with self.subTest(width=width, scheme=scheme, tab=name), chrome() as cdp:
                        sid = open_page(cdp, self.path.as_uri(), width, scheme)
                        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                        cdp.js("[...document.querySelectorAll('.tab')].find(t => t.textContent.includes('%s')).click()" % name, sid)
                        wait(lambda: cdp.js("document.getAnimations().length === 0", sid))
                        stops = self.walk(cdp, sid)
                        names = [s["name"] for s in stops]
                        self.assertTrue(names[0].startswith("A.skip:Skip to content"), names[:2])
                        # The tabs are one tab stop (roving tabindex, hunt 16): Tab reaches the chosen tab only, and the arrow keys move between tabs.
                        others = {"Dashboard", "Work items", "Milestones", "Use cases"} - {name}
                        self.assertEqual(names[1].split(":")[1], name, "Tab goes from the skip link to the chosen tab")
                        self.assertEqual([n for n in names[2:] if n.startswith("BUTTON.tab") and n.split(":")[1] in others], [], "the other tabs are not tab stops")
                        self.assertEqual([s["name"] for s in stops if not s["ring"]], [], "every stop shows a ring")
                        self.assertEqual([s["name"] for s in stops if not s["on"]], [], "every stop is on screen when reached")


    def test_esc_closes_a_peek_opened_from_the_keyboard_and_a_menu(self):
        shown = "[...document.querySelectorAll('aside.peek, .ddmenu.on')].length"
        cases = (("Work items", "#work tr[data-id]"), ("Milestones", ".mv-mk"), ("Milestones", ".msl-cells"), ("Dashboard", ".cm-badge"))
        for width in WIDTHS:
            for name, sel in cases:
                with self.subTest(width=width, tab=name, opener=sel), chrome() as cdp:
                    sid = open_page(cdp, self.path.as_uri(), width, "light")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                    cdp.js("[...document.querySelectorAll('.tab')].find(t => t.textContent.includes('%s')).click()" % name, sid)
                    wait(lambda: cdp.js("document.getAnimations().length === 0", sid))
                    cdp.js("document.querySelector('%s').focus()" % sel, sid)
                    key(cdp, sid, "Enter", "Enter", 13)
                    self.assertTrue(wait(lambda: cdp.js(shown, sid) == 1, 5), "Enter opened it")
                    key(cdp, sid, "Escape", "Escape", 27)
                    self.assertTrue(wait(lambda: cdp.js(shown, sid) == 0, 5), "Esc closed it")


if __name__ == "__main__":
    unittest.main()
