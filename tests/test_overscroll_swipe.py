"""item 1136: the two-finger swipe on a Mac mouse or trackpad (Chrome's swipe to go Back and Forward) works on clark's pages.

Run: python3 dev/run_tests.py test_overscroll_swipe
Chrome turns that swipe off when `overscroll-behavior-x` is none or contain on html, body or the scroller under the pointer.
The real swipe cannot be made in headless Chrome, so this guards the cause: on Work items in List and Board, and on the full
screen board, at 1400 and 900 px, no element that scrolls sideways (or html, body, main) has a horizontal containment, and the
board scroller still contains vertical overscroll. A source check covers shell.css and every other style sheet of the page.
"""
import re
import unittest

from _paths import SRC
from test_server import chrome, wait  # noqa: E402,F401  (chrome: the runner tells a browser file by this import)
from test_work_board_page import Base, shared, setUpModule, tearDownModule  # noqa: E402,F401
from test_work_filters import click  # noqa: E402

WALK = ("(() => { const out = []; const els = [document.documentElement, document.body, document.querySelector('main'),"
        " ...document.querySelectorAll('.boardbox'), ...document.querySelectorAll('*')];"
        " for (const e of new Set(els)) { if (!e) continue; const c = getComputedStyle(e);"
        " const sideways = /auto|scroll/.test(c.overflowX) || e === document.documentElement || e === document.body || e.tagName === 'MAIN' || e.classList.contains('boardbox');"
        " if (sideways) out.push([e.tagName.toLowerCase() + (e.className && typeof e.className === 'string' ? '.' + e.className.split(' ')[0] : ''), c.overscrollBehaviorX, c.overscrollBehaviorY]); }"
        " return out; })()")


class Swipe(Base):
    def check(self, cdp, sid, where, board_box=True):
        got = cdp.js(WALK, sid)
        self.assertTrue(got, where)
        for name, x, _y in got:
            self.assertNotIn(x, ("none", "contain"), f"{where}: {name} stops the browser's swipe (overscroll-behavior-x {x})")
        if board_box:
            box = [g for g in got if g[0].endswith(".boardbox") or g[0] == "main"]
            self.assertTrue(any(y == "contain" for _n, _x, y in box), f"{where}: the board scroller keeps vertical containment")

    def test_no_scroller_stops_the_swipe_on_work_items(self):
        for width in (1400, 900):
            with self.subTest(width=width), shared.page() as cdp:
                sid = self.visit(cdp, width=width)
                self.check(cdp, sid, f"List at {width}", board_box=False)
                self.board(cdp, sid, "status")
                self.until(cdp, sid, "!!document.querySelector('.boardbox')", "the board scroller")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('.boardbox')).overscrollBehaviorY", sid), "contain")
                self.check(cdp, sid, f"Board at {width}")
                click(cdp, sid, "#board-full")
                self.until(cdp, sid, "document.body.classList.contains('board-full')", "full screen")
                self.assertEqual(cdp.js("getComputedStyle(document.querySelector('main')).overscrollBehaviorY", sid), "contain")
                self.check(cdp, sid, f"Full screen board at {width}")


class Source(unittest.TestCase):
    def test_no_style_sets_horizontal_overscroll_to_none_or_contain(self):
        files = list((SRC / "clark").rglob("*.css")) + list((SRC / "clark" / "page").rglob("*.js*"))
        self.assertTrue(any(f.name == "shell.css" for f in files))
        bad = []
        for f in files:
            text = f.read_text(encoding="utf-8", errors="replace")
            for m in re.finditer(r"overscroll-behavior(-x)?\s*:\s*([^;}]*)", text):
                value = m.group(2).split()
                # the shorthand's first value is x; `-x` takes one value
                if value and value[0] in ("none", "contain"):
                    bad.append(f"{f.name}: {m.group(0)}")
        self.assertEqual(bad, [])
        self.assertIn("overscroll-behavior-y: contain", (SRC / "clark" / "page" / "shell.css").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
