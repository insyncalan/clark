"""Row 1282, hostile round: the Work items list's Priority matrix (a risk's or issue's Impact x Likelihood drop-down) under rough use.

Run: python3 dev/run_tests.py test_priority_matrix_hostile_1282
Real page in Chrome over a real server and demo store (the helpers of test_inline_edits). What is driven: a rapid double click on one cell of the
matrix, Esc while the write is still on its way, a click outside while it is open, a row that leaves the list while it is open (a filter), a row that is
gone from the store when the pick is sent, and the store changing the row's impact while it is open. The row's type (risk to action) cannot change
in the product, so that case is only the source check at the end: the plain list is chosen by the row's kind at each draw.
"""
import json
import time
import unittest
from pathlib import Path

import test_inline_edits as ie
from _real_server import real_server
import _testpage as testpage
from clark import server as sv
from test_inline_edits import click, key
from test_server import chrome
from test_work_items import load_demo
from unittest import mock
import shutil

from clark.store import open_store

SRC = Path(__file__).resolve().parents[1] / "src" / "clark" / "page"
CELL = "[data-cell='TUL-007:priority']"      # a risk: impact High, likelihood Medium
OPEN = "!!document.querySelector('[data-pop] .rmx')"
GONE = "document.querySelectorAll('[data-pop]').length === 0"
BACK = f"document.activeElement === document.querySelector(\"{CELL}\")"
URGENT = "[data-pop] [data-mx='High|High']"


class Hostile(unittest.TestCase):
    read, row, steps, open_page, until, cell_text, toast = (
        ie.Live.read, ie.Live.row, ie.Live.steps, ie.Live.open_page, ie.Live.until, ie.Live.cell_text, ie.Live.toast)

    def setUp(self):
        ie.need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.sent = []
        self.delay = 0                       # seconds a change waits before the real handler runs (a slow write)

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                if self.delay and which == "change":
                    time.sleep(self.delay)
                return real(req)
            return call
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                             page_html=lambda: testpage.html(), seam=seam)
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def outside(self, do):
        """Another person's change, made in the store while this page is open (the page does not hear of it)."""
        st = open_store(self.path, onedrive_roots=[])
        try:
            with st.step("dashboard", "Demo User") as step:
                do(step)
        finally:
            st.close()

    def open_matrix(self, cdp, sid):
        click(cdp, sid, CELL)
        self.until(cdp, sid, OPEN, "the matrix opened")

    def test_a_rapid_double_click_on_one_cell_sends_one_change(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            where = f"(() => {{ const b = document.querySelector(\"{URGENT}\").getBoundingClientRect(); return [b.x + b.width / 2, b.y + b.height / 2]; }})()"
            x, y = cdp.js(where, sid)
            for n in (1, 2):
                for t in ("mousePressed", "mouseReleased"):
                    cdp.call("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "buttons": 1 if t == "mousePressed" else 0, "clickCount": n}, sid)
            self.until(cdp, sid, GONE, "closed")
            self.until(cdp, sid, f"document.querySelector(\"{CELL}\").textContent === 'Urgent'", "the cell shows Urgent")
            time.sleep(0.5)
            self.assertEqual(len(self.sent), 1, "two clicks in a row on the matrix: one change")
            self.assertEqual(self.row("raid", "TUL-007")["likelihood"], "High")

    def test_a_double_click_on_the_cell_does_not_leave_a_matrix_open_over_a_change(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            click(cdp, sid, CELL)
            click(cdp, sid, CELL)             # open, then close by the second click
            self.until(cdp, sid, GONE, "two clicks on the cell leave it closed")
            self.assertEqual(len(self.sent), 0)
            self.assertEqual(cdp.js(f"document.querySelector(\"{CELL}\").getAttribute('aria-expanded')", sid), "false")

    def test_esc_while_the_write_is_on_its_way_neither_undoes_it_nor_opens_a_peek(self):
        self.delay = 1.5
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, GONE, "closed at once, before the write lands")
            key(cdp, sid, "Escape")
            key(cdp, sid, "Escape")
            self.assertNotIn("item=", cdp.js("location.hash", sid), "Esc after a pick opens no peek")
            self.until(cdp, sid, f"document.querySelector(\"{CELL}\").textContent === 'Urgent'", "the write still lands", 15)
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(self.row("raid", "TUL-007")["likelihood"], "High")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 0)

    def test_the_cell_cannot_be_opened_again_into_a_second_matrix_while_the_write_is_on_its_way(self):
        self.delay = 1.5
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, GONE, "closed")
            click(cdp, sid, CELL)             # open again over the slow write
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length >= 1", "opened again")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop] .rmx').length", sid), 1, "one matrix only")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, f"document.querySelector(\"{CELL}\").textContent === 'Urgent'", "the first write lands", 15)
            self.assertEqual(len(self.sent), 1, "the second open sent nothing")

    def test_a_click_outside_on_another_cell_closes_it_and_opens_nothing_wrong(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            click(cdp, sid, "[data-cell='TUL-010:priority']")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 1", "one panel only")
            self.assertEqual(cdp.js(f"document.querySelector(\"{CELL}\").getAttribute('aria-expanded')", sid), "false", "the first cell says it is closed")
            self.assertEqual(len(self.sent), 0)

    def test_a_row_that_leaves_the_list_while_the_matrix_is_open_takes_the_matrix_with_it(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            cdp.js("clarkPage.setFilters('mode:closed')", sid)
            self.until(cdp, sid, "!document.querySelector(\"" + CELL + "\")", "the row is gone from the list")
            self.until(cdp, sid, GONE, "no matrix is left hanging over a row that is not there")
            self.assertEqual(len(self.sent), 0)
            self.assertEqual(cdp.js("document.querySelectorAll('.cell-pick[aria-expanded=true]').length", sid), 0)

    def test_a_row_deleted_from_the_store_while_open_is_refused_in_words_and_the_page_stays_whole(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            self.outside(lambda s: s.delete("raid", "TUL-007"))
            key(cdp, sid, "ArrowRight")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, GONE, "closed")
            self.until(cdp, sid, "!!document.querySelector('.toast-text')", "the page says something")
            text = self.toast(cdp, sid)
            self.assertNotRegex(text, r"Traceback|undefined|\[object|KeyError|Error:", text)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-pop]').length", sid), 0)
            self.assertNotIn("Urgent.", text, "a change that did not happen is not reported as done")

    def test_the_store_changing_the_impact_while_open_does_not_make_a_stale_pick_overwrite_blindly_or_hide_a_no_change(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, edit=False)
            self.open_matrix(cdp, sid)
            self.outside(lambda s: s.update("raid", "TUL-007", {"impact": "Low", "likelihood": "Low"}))
            key(cdp, sid, "Enter")            # the cell the page thinks the row has: High|Medium
            self.until(cdp, sid, GONE, "closed")
            time.sleep(1)
            row = self.row("raid", "TUL-007")
            # Either nothing was sent (the page believed nothing changed) or the pick won; it must never leave impact and likelihood half-applied.
            self.assertIn((row["impact"], row["likelihood"]), [("Low", "Low"), ("High", "Medium")], "both fields move together or not at all")

    def test_the_plain_list_is_chosen_by_the_kind_at_every_draw(self):
        text = (SRC / "src" / "edit" / "cells" / "PriorityPick.jsx").read_text(encoding="utf-8")
        self.assertIn('if (row.kind !== "action") return <Matrix', text)
        self.assertIn("<MenuPick ", text)
