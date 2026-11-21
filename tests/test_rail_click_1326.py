"""Row 1326: a click on a Contents entry marks THAT entry, not the next section the 30% line lands on, and the mark stays until the reader scrolls
by hand. Classic's left column and the Cards minimap share the rule (logic/minimap.js clickLock). Chrome is required. Fictional data only.

Run: python3 dev/run_tests.py test_rail_click_1326
"""
import time
import unittest

import test_classic_contents_1318 as c18
import test_report_editor as tre
from test_inline_67 import size
from test_server import chrome

ON = "(document.querySelector('.cnt li a.on, #toc-card button.on') || {dataset: {}}).dataset"
ENTRIES = "[...document.querySelectorAll('.cnt li a, #toc-card button[data-id]')].map(b => b.dataset.entry || b.dataset.id)"
CLICK = "(function(i){var b=[...document.querySelectorAll('.cnt li a, #toc-card button[data-id]')][i]; b.click();})"


def settle(p):
    last = [None]
    for _ in range(60):
        y = p.js("window.scrollY")
        if y == last[0]:
            return y
        last[0] = y
        time.sleep(0.15)
    return last[0]


class ClickMarksClicked(tre.Base):
    def setUp(self):
        super().setUp()
        self.demo.action(description="Fictional open action", due_date="2030-01-05", owner="Sara Khan")
        self.s.close()
        self.s = tre.real_server(self.store.path, self.store.data_for, page_html=c18.classic_html, seam=self.seam)
        self.addCleanup(self.s.close)

    at = c18.Classic.at

    def every_entry(self, width):
        with chrome() as cdp:
            p = self.at(cdp, width)
            ids = p.js(ENTRIES)
            self.assertGreaterEqual(len(ids), 3)
            order = list(range(len(ids))) + list(range(len(ids) - 1, -1, -1))     # down the list, then back up
            for i in order:
                p.js(f"{CLICK}({i})")
                settle(p)
                self.assertEqual(p.js(f"{ON}.entry || {ON}.id"), ids[i], f"entry {i} of {len(ids)} is marked after its click at {width}")

    def test_each_click_marks_its_own_entry_at_1400(self):
        self.every_entry(1400)

    def test_each_click_marks_its_own_entry_at_900(self):
        self.every_entry(900)

    def held(self, p, ids, fire):
        """Click the last entry, then run `fire` (the reader's input, or none) and a scroll to the top that is not the reader's."""
        p.js(f"{CLICK}({len(ids) - 1})")
        settle(p)
        p.js(fire)
        p.js("window.scrollTo(0, 0)")
        time.sleep(0.4)
        return p.js(f"{ON}.entry")

    def lets_go(self, fire):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            ids = p.js(ENTRIES)
            self.assertGreaterEqual(len(ids), 3)
            self.assertEqual(self.held(p, ids, ""), ids[-1], "no input of the reader: the mark stays on the clicked entry")
            p.js(f"{CLICK}({len(ids) - 1})")
            settle(p)
            p.js(fire)
            p.js("window.scrollTo(0, 0)")
            p.until(f"{ON}.entry === {ids[0]!r}", "the first entry is marked again after the reader's input and a scroll to the top")

    def test_a_wheel_scroll_by_the_reader_lets_the_rule_back_in(self):
        self.lets_go("window.dispatchEvent(new WheelEvent('wheel', {deltaY: 10}))")

    def test_a_touch_move_lets_the_rule_back_in(self):
        self.lets_go("window.dispatchEvent(new Event('touchmove'))")

    def test_a_scrolling_key_lets_the_rule_back_in(self):
        self.lets_go("window.dispatchEvent(new KeyboardEvent('keydown', {key: 'PageDown'}))")

    def test_a_press_on_the_scrollbar_lets_the_rule_back_in(self):
        for kind in ("pointerdown", "mousedown"):
            self.lets_go(f"window.dispatchEvent(new MouseEvent('{kind}', {{clientX: document.documentElement.clientWidth + 5, clientY: 50, bubbles: true}}))")

    def test_a_press_inside_the_page_or_a_non_scrolling_key_does_not_let_go(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            ids = p.js(ENTRIES)
            fire = ("window.dispatchEvent(new MouseEvent('pointerdown', {clientX: 100, clientY: 100, bubbles: true}));"
                    "window.dispatchEvent(new KeyboardEvent('keydown', {key: 'a'}))")
            self.assertEqual(self.held(p, ids, fire), ids[-1])

    def test_a_change_of_the_entries_after_a_click_keeps_the_mark(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.edit()
            ids = p.js(ENTRIES)
            gone = "ABC-S-004"
            self.assertIn(gone, ids)
            keep = [i for i in ids if i != gone][-1]
            p.js(f"{CLICK}({ids.index(keep)})")
            settle(p)
            self.assertEqual(p.js(f"{ON}.entry"), keep)
            p.menu(gone, "hide")
            p.until(f"!!document.querySelector('[data-id=\"{gone}\"].is-hidden')", "the section is hidden")
            p.until(f"!document.querySelector('.cnt li a[data-entry=\"{gone}\"]')", "the entry list was re-read")
            time.sleep(0.4)
            self.assertEqual(p.js(f"{ON}.entry"), keep, "the clicked entry is still marked after the entries changed")


class CardsMinimap(tre.Base):
    def test_cards_minimap_does_not_lock_the_clicked_entry(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
            p.js("window.scrollTo(0, 0)")
            ids = p.js(ENTRIES)
            self.assertGreaterEqual(len(ids), 3)
            p.js(f"{CLICK}({len(ids) - 1})")
            settle(p)
            p.js("window.scrollTo(0, 0)")
            p.until(f"{ON}.id === {ids[0]!r}", "Cards: the rule alone marks the first entry at the top (no lock)")
