"""Row 1467: on the Dashboard, opening a work item's peek does not move the page, and a click on another work item's row with the peek open shows
that item in the same peek (no close and open). Real mouse clicks in headless Chrome, 1400 and 900 px.
Run: CLARK_CHROME=/usr/local/bin/creaite-chrome python3 dev/run_tests.py test_peek_switch_1467
Demo project: the Dashboard's work item rows are li.wl-row[data-id] in View.
"""
import json
import tempfile
import time
from pathlib import Path
import unittest

from _paths import ROOT

import test_peek_ruled_1077 as base  # noqa: E402
import test_peek_body_1180 as bodytests  # noqa: E402
import test_peek_latest  # noqa: E402
import test_publish as tp  # noqa: E402
from test_peek_latest import OVERDUE  # noqa: E402
from test_server import chrome, wait  # noqa: E402

# the Dashboard draws a section's rows as a table (tr) or as a list (li.wl-row); the one that is shown is the one a person clicks
VIS = "(id => [...document.querySelectorAll('#report tr[data-id], #report li.wl-row[data-id]')].find(e => e.dataset.id === id && e.offsetParent !== null))"
ROWS = "[...new Set([...document.querySelectorAll('#report tr[data-id], #report li.wl-row[data-id]')].filter(e => e.offsetParent !== null).map(r => r.dataset.id))]"
PVIS = VIS.replace("#report tr[data-id], #report li.wl-row[data-id]", "tr[data-id], li.wl-row[data-id]")      # a published file has no #report
PROWS = ROWS.replace("#report tr[data-id], #report li.wl-row[data-id]", "tr[data-id], li.wl-row[data-id]")
SPOT = ("(id => { const r = " + VIS + "(id); if (!r) return null; const b = r.getBoundingClientRect();"
        " return { top: Math.round(b.top * 100) / 100, y: Math.round(scrollY * 100) / 100, x: Math.round(scrollX * 100) / 100 }; })")
STATE = ("(() => { const p = document.querySelector('#peek'); return { id: p && p.dataset.peek, title: p ? (p.querySelector('.pk-title') || {}).value || (p.querySelector('.pk-title') || {}).textContent || '' : null,"
         " tag: window.__peek1467 === p }; })()")


class Switch(base.Peeks):
    def ready(self, cdp, width):
        sid = self.dashboard_in_view(cdp, width, self.store, self.code)
        self.assertTrue(wait(lambda: len(cdp.js(ROWS, sid)) >= 2), "the Dashboard lists work items")
        return sid

    def press(self, cdp, sid, ref):
        """A real mouse click on the middle of the row's title."""
        x, y = cdp.js(f"(() => {{ const r = {VIS}({json.dumps(ref)}), t = r.querySelector('.wil-c-title, .wl-title') || r, b = t.getBoundingClientRect(); return [b.left + Math.min(b.width / 2, 120), b.top + b.height / 2]; }})()", sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": x, "y": y, "button": "left", "buttons": 1, "clickCount": 1}, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": x, "y": y, "button": "left", "buttons": 0, "clickCount": 1}, sid)

    def place(self, cdp, sid, ref):
        """Scroll so that the row is about a third down the window (a person has scrolled to it)."""
        cdp.js(f"(() => {{ const r = {VIS}({json.dumps(ref)}); window.scrollTo(0, scrollY + r.getBoundingClientRect().top - 300); }})()", sid)
        wait(lambda: True)
        return cdp.js(f"({SPOT})({json.dumps(ref)})", sid)

    def test_opening_the_peek_does_not_move_the_page_or_the_row(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.ready(cdp, width)
                ref = cdp.js(ROWS, sid)[len(cdp.js(ROWS, sid)) // 2]
                before = self.place(cdp, sid, ref)
                self.press(cdp, sid, ref)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .pk-fields')", sid)), "the peek opened")
                for _ in range(8):      # the layout settles after the peek's slide: look again until 0.8 s have gone
                    time.sleep(0.1)
                    after = cdp.js(f"({SPOT})({json.dumps(ref)})", sid)
                    self.assertEqual(after, before, "the page and the clicked row stay where they were")

    def test_a_click_on_another_row_switches_the_open_peek(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.ready(cdp, width)
                ids = cdp.js(ROWS, sid)
                a, b = ids[-2], ids[-1]
                self.place(cdp, sid, a)
                self.press(cdp, sid, a)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek)(document.querySelector('#peek'))", sid) == a))
                cdp.js("window.__peek1467 = document.querySelector('#peek'); window.__closed1467 = 0; new MutationObserver(() => { if (!document.querySelector('#peek')) window.__closed1467++; }).observe(document.body, { childList: true, subtree: true })", sid)
                before = cdp.js(f"({SPOT})({json.dumps(b)})", sid)
                self.press(cdp, sid, b)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek)(document.querySelector('#peek'))", sid) == b), "the peek shows the other item")
                got = cdp.js(f"({{ same: window.__peek1467 === document.querySelector('#peek'), closed: window.__closed1467, spot: ({SPOT})({json.dumps(b)}) }})", sid)
                self.assertTrue(got["same"], "the same peek element: never closed and reopened")
                self.assertEqual(got["closed"], 0)
                self.assertEqual(got["spot"], before, "the page did not move")

    def test_work_items_page_and_milestones_page_switch_the_peek_too(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.live(cdp, width, self.store, f"#work&p={self.code}")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 1))
                ids = cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)", sid)
                self.open_peek(cdp, sid, ids[0], "item")
                cdp.js("window.__peek1467 = document.querySelector('#peek')", sid)
                cdp.js(f"document.querySelector('#work tbody tr[data-id={ids[1]}] .wil-c-title, #work tbody tr[data-id={ids[1]}] td:nth-child(2)').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').dataset.peek", sid) == ids[1]))
                self.assertTrue(cdp.js("window.__peek1467 === document.querySelector('#peek')", sid), "the same peek element")
            with self.subTest(page="milestones", width=width), chrome() as cdp:
                sid = self.live(cdp, width, self.store, f"#milestones&p={self.code}")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msl-row[data-ms], .mv-mk').length", sid) > 1))
                ms = cdp.js("[...new Set([...document.querySelectorAll('.msl-row[data-ms]')].filter(e => e.offsetParent).map(e => e.dataset.ms))]", sid)
                if len(ms) < 2:
                    print("SKIPPED milestones list", width); continue
                self.open_peek(cdp, sid, ms[0], "milestone")
                cdp.js("window.__peek1467 = document.querySelector('#peek')", sid)
                cdp.js(f"document.querySelector('.msl-row[data-ms={ms[1]}] .msl-cells').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').dataset.peek", sid) == ms[1]))

    def test_a_click_on_empty_page_and_esc_still_close_and_up_down_still_step(self):
        with chrome() as cdp:
            sid = self.ready(cdp, 1400)
            ids = cdp.js(ROWS, sid)
            self.open_peek(cdp, sid, ids[0], "item")
            cdp.js("document.querySelector('#peek').focus && document.querySelector('#peek [data-pk-close]').focus()", sid)
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "ArrowDown", "code": "ArrowDown", "windowsVirtualKeyCode": 40}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek') && document.querySelector('#peek').dataset.peek", sid) != ids[0]), "Down steps to another item")
            x, y = cdp.js("(() => { const h = document.querySelector('#report h1, header, .topbar') || document.body; const b = h.getBoundingClientRect(); return [Math.max(b.left + 4, 4), 4]; })()", sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mousePressed", "x": 3, "y": 3, "button": "left", "clickCount": 1}, sid)
            cdp.call("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": 3, "y": 3, "button": "left", "clickCount": 1}, sid)
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)), "a click on empty page closes the peek")
            self.open_peek(cdp, sid, ids[0], "item")
            cdp.js("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))", sid)
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)), "Esc closes it")


class Published(unittest.TestCase):
    def test_a_published_report_switches_the_peek_without_closing_it(self):
        _plant, _pub, text = tp.made()
        folder = Path(tempfile.mkdtemp(prefix="clark-1467-"))
        self.addCleanup(lambda: __import__("shutil").rmtree(str(folder), ignore_errors=True))
        path = folder / "report.html"
        path.write_text(text, encoding="utf-8")
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = tp.opened(cdp, path.as_uri() + "#work&p=PUB", width)
                self.assertTrue(wait(lambda: len(cdp.js(PROWS, sid)) >= 2), "the report lists work items")
                ids = cdp.js(PROWS, sid)
                cdp.js(f"({PVIS})({json.dumps(ids[0])}).click()", sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek)(document.querySelector('#peek'))", sid) == ids[0]))
                cdp.js("window.__peek1467 = document.querySelector('#peek')", sid)
                x, y = cdp.js(f"(() => {{ const b = ({PVIS})({json.dumps(ids[1])}).getBoundingClientRect(); return [b.left + 40, b.top + b.height / 2]; }})()", sid)
                for kind, extra in (("mouseMoved", {}), ("mousePressed", {"button": "left", "buttons": 1, "clickCount": 1}), ("mouseReleased", {"button": "left", "clickCount": 1})):
                    cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, **extra}, sid)
                self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek)(document.querySelector('#peek'))", sid) == ids[1]), "the peek shows the other item")
                self.assertTrue(cdp.js("window.__peek1467 === document.querySelector('#peek')", sid), "the same peek element")


class Unsaved(test_peek_latest.Browser):
    press = bodytests.Body.press      # the settled real mouse press (not the whole Body class: it would bring its tests)
    """Rule 3: with an unsaved Latest update, a click on another row asks first (the unsaved bar), as Close does."""
    def test_another_row_asks_first_keep_stays_and_discard_switches(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            ids = cdp.js("[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)", sid)
            other = next(i for i in ids if i != OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Not yet saved")
            self.press(cdp, sid, f"#work tbody tr[data-id={other}] .wil-c-title, #work tbody tr[data-id={other}] td:nth-child(2)")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "the bar asks")
            self.assertEqual(cdp.js("document.querySelector('#peek').dataset.peek", sid), OVERDUE, "the peek still shows the first item")
            self.assertEqual(sent, [], "nothing is saved while it asks")
            self.press(cdp, sid, "[data-pk-keep]")
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)))
            self.assertIn("Not yet saved", cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent", sid), "Keep editing keeps A with its changes")
            self.press(cdp, sid, f"#work tbody tr[data-id={other}] .wil-c-title, #work tbody tr[data-id={other}] td:nth-child(2)")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-discard]')", sid)))
            self.press(cdp, sid, "[data-pk-discard]")
            self.assertTrue(wait(lambda: cdp.js("(p => !!p && p.dataset.peek)(document.querySelector('#peek'))", sid) == other), "Discard switches to the clicked item")
            self.assertEqual(sent, [], "Discard stores nothing")


for _name in dir(test_peek_latest.Browser):      # only the loader and helpers of that class are wanted here, not its own tests
    if _name.startswith("test_"):
        setattr(Unsaved, _name, None)


class Source(unittest.TestCase):
    def test_the_outside_rule_keeps_the_dashboard_table_rows(self):
        src = (ROOT / "src/clark/page/src/peek/outside.js").read_text(encoding="utf-8")
        self.assertIn(".wil-table tr[data-id]", src)
        self.assertIn("preventScroll: true", (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
