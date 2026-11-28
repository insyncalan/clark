"""Row 1366 slice (a): the status line under each saved folder, in a real browser at 1400 and 900, in the project card (own and for-all folders)
and the All projects card, against the real folder service and the real background reader (Classic).

Run: python3 dev/run_tests.py test_ask_index_page_1366
Chrome is required. Every file is made in the test from made-up text.
"""
import os
import shutil
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from _editor_checks import for_project
from test_ask_settings import make_db, service
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask_folders, ask_index, ask_picture, page, platform as pl, theme

WIDTHS = (1400, 900)


class Fixture(unittest.TestCase):
    CLASSIC = True

    def setUp(self):
        for patch in (mock.patch.object(pl, "system", return_value=pl.MAC),
                      mock.patch.object(ask_picture, "_READER", None)):      # on a Mac ask_index registers the real reader at import: no picture here may start it
            patch.start()
            self.addCleanup(patch.stop)
        html = page.page_html(tempfile.mkdtemp())
        if self.CLASSIC:
            html = page.layer_theme(html, theme.css("prototype-2.0"))      # the status-line rules are Classic-only
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: html)
        self.addCleanup(self.s.close)
        self.d = Path(os.path.realpath(tempfile.mkdtemp(prefix="clark-test-")))
        self.addCleanup(shutil.rmtree, self.d, True)
        self.home = self.d / "home"
        self.data = self.d / "data"
        self.shared, self.own = self.d / "shared", self.d / "own"
        for p in (self.home, self.shared, self.own, self.data):
            p.mkdir(parents=True)
        (self.own / "a.txt").write_text("alpha river", encoding="utf-8")
        (self.own / "b.bin").write_bytes(b"x")
        (self.shared / "c.md").write_text("beta lake", encoding="utf-8")
        db = make_db(self.data)
        self.s.httpd.app_settings = service(db)
        self.gate = threading.Event()
        self.gate.set()
        real = ask_index.refresh

        def held(data, code, folders, home=None, stop=None, progress=None):
            def hold(f, d, t):
                progress(f, d, t)
                self.gate.wait(10)
            return real(data, code, folders, home, stop=stop, progress=hold)
        self.ix = ask_index.Indexer(self.data, self.home, refresh_fn=held)
        self.addCleanup(self.ix.shutdown)
        self.s.httpd.ask_folders = self.svc = ask_folders.AskFolders(db, [], data_dir=self.data, home=self.home, by_user=lambda: "tester", indexer=self.ix)

    def show(self, cdp, tab):
        self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
        js = lambda e: cdp.js(e, self.sid)          # noqa: E731
        self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab]')"), 20))
        if tab == "all":
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all-folders')"), 10))
        return js

    def until(self, js, expr, what):
        self.assertTrue(wait(lambda: js(expr), 20), f"{what}: {expr}")

    LOOK = ("(() => { const e = document.querySelector(%r); const c = getComputedStyle(e); const li = e.closest('li'); "
            "const r = li.querySelector('[data-ask-remove],[data-ask-all-remove],[data-ask-change-shared]').getBoundingClientRect(); "
            "return {size: c.fontSize, weight: c.fontWeight, color: c.color, mt: c.marginTop, role: e.getAttribute('role'), live: e.getAttribute('aria-live'), "
            "below: e.getBoundingClientRect().top >= r.bottom - 1, text: e.innerText}; })()")


class Page(Fixture):
    def test_the_line_in_the_project_card_for_an_own_and_a_shared_folder_at_both_widths(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "document.querySelectorAll('.ask-folder-line').length === 2", "two lines")
            self.until(js, "[...document.querySelectorAll('.ask-folder-line')].every(e => e.innerText.startsWith('100% indexed'))", "indexed")
            self.assertEqual(js("document.querySelector('#ask-folders-shared .ask-folder-line').innerText"), "100% indexed")
            self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').innerText"), "100% indexed. 1 file could not be read (why)")
            muted = js("getComputedStyle(document.querySelector('.ask-folders')).color && (() => { const p = document.createElement('p'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); const c = getComputedStyle(p).color; p.remove(); return c; })()")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
                for q in ("#ask-folders-shared .ask-folder-line", "#ask-folders .ask-folder-line"):
                    look = js(self.LOOK % q)
                    self.assertEqual((look["size"], look["weight"], look["mt"], look["role"], look["live"], look["below"]), ("13px", "400", "2px", None, None, True), (w, q, look))
                    self.assertEqual(look["color"], muted, (w, q))

    def test_status_line_tokens_light_and_dark(self):
        """Row 1366 AP10: the line is 13px (--size-caption), weight 400, --text-muted, margin-top 2px, in light and dark, at both widths, with no bar, spinner or graphic."""
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        probe = ("(() => { const p = document.createElement('p'); p.style.color = 'var(--text-muted)'; document.body.appendChild(p); "
                 "const c = getComputedStyle(p).color; p.remove(); return c; })()")
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "!!document.querySelector('#ask-folders .ask-folder-line') && document.querySelector('#ask-folders .ask-folder-line').innerText.startsWith('100% indexed')", "indexed")
            seen = set()
            for mode in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = {mode!r}")
                muted = js(probe)
                seen.add(muted)
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {mode} {w}")
                    look = js(self.LOOK % "#ask-folders .ask-folder-line")
                    self.assertEqual((look["size"], look["weight"], look["mt"], look["below"]), ("13px", "400", "2px", True), (mode, w, look))
                    self.assertEqual(look["color"], muted, (mode, w))
                    self.assertFalse(js("!!document.querySelector('#ask-folders li progress, #ask-folders li [role=progressbar], #ask-folders li svg, #ask-folders li canvas')"), (mode, w))
            self.assertEqual(len(seen), 2, "light and dark muted colours differ, so the pin is not vacuous")

    def test_note_is_one_size_smaller_than_the_folder_name_and_the_row_is_no_taller_when_it_fits(self):
        """Row 1371 AP6: the note is 13px under a 14px folder name (one size smaller) and sits on one line; a row whose note fits is the same height at 1400 and 900, in light and dark."""
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        probe = ("(() => { const out = {}; for (const [k, sel] of [['shared', '#ask-folders-shared'], ['own', '#ask-folders']]) { const li = document.querySelector(sel + ' li'); "
                 "const n = li.querySelector('.folder-now'); const l = li.querySelector('.ask-folder-line'); const ln = parseFloat(getComputedStyle(l).lineHeight); "
                 "const row = li.getBoundingClientRect().height; const noteH = l.getBoundingClientRect().height; l.style.display = 'none'; const bare = li.getBoundingClientRect().height; l.style.display = ''; "
                 "out[k] = {name: parseFloat(getComputedStyle(n).fontSize), note: parseFloat(getComputedStyle(l).fontSize), lines: Math.round(noteH / ln), row: row, bare: bare, noteH: noteH, ln: ln, "
                 "gap: parseFloat(getComputedStyle(li).rowGap), mt: parseFloat(getComputedStyle(l).marginTop)}; } return out; })()")
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "[...document.querySelectorAll('.ask-folder-line')].length === 2 && [...document.querySelectorAll('.ask-folder-line')].every(e => e.innerText.startsWith('100% indexed'))", "indexed")
            rows = {}
            for mode in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = {mode!r}")
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {mode} {w}")
                    got = js(probe)
                    for which, m in got.items():
                        self.assertEqual((m["name"], m["note"], m["name"] - m["note"]), (14, 13, 1), (mode, w, which, m))      # one size smaller than the folder name
                        self.assertEqual(m["lines"], 1, (mode, w, which, m))      # one line
                        self.assertEqual((m["mt"], m["ln"]), (2, 1.5 * m["note"]), (mode, w, which, m))      # the note's own 2px top margin, and a line 1.5 times its 13px text: not a taller line
                        self.assertEqual(m["row"] - m["bare"], m["gap"] + m["mt"] + m["noteH"], (mode, w, which, m))      # the note adds its row gap, its 2px margin and its own height to the row, nothing more
                        if which == "shared":
                            self.assertEqual(m["noteH"], m["ln"], (mode, w, which, m))      # text only: the note is exactly one line high
                        else:
                            self.assertLessEqual(m["noteH"], 24, (mode, w, which, m))      # this note holds the 24px (why) button: no higher than the button
                        rows.setdefault(which, set()).add(m["row"])
            self.assertEqual({k: len(v) for k, v in rows.items()}, {"shared": 1, "own": 1}, rows)      # the row does not grow with the width or the theme while the note fits


    def test_a_picture_the_computer_cannot_read_has_its_line_and_reason_at_both_widths(self):
        (self.own / "p.png").write_bytes(b"x")
        (self.own / "q.jpg").write_bytes(b"x")
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        line = "100% indexed. 3 files could not be read (why)"
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "!!document.querySelector('#ask-folders .ask-folder-line') && document.querySelector('#ask-folders .ask-folder-line').innerText.startsWith('100% indexed')", "indexed")
            self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').innerText"), line)
            js("document.querySelector('#ask-folders .ask-left-btn').click()")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {w}")
                rows = js("[...document.querySelectorAll('#ask-folders .ask-left-list li')].map(e => e.innerText.replace(/\\s+/g, ' '))")
                self.assertIn("p.png is a picture and this computer cannot read pictures", rows, w)
                self.assertIn("q.jpg is a picture and this computer cannot read pictures", rows, w)
                self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').innerText"), line)

    def test_the_live_region_says_the_start_then_100_percent_indexed_at_the_default_width(self):
        """No window resize here, so this runs while the 900 px cases are paused: the region speaks at the start and when done."""
        self.gate.clear()
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        with chrome() as cdp:
            js = self.show(cdp, "all")
            LIVE = "document.querySelector('#ask-all-folder-list .ask-folder-live').textContent"
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexing… 0%'", "reading")
            self.until(js, LIVE + " === 'Indexing started'", "said at the start")
            self.gate.set()
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexed for 1 of 1 projects'", "indexed (row 1371: the All projects tab counts projects)")
            self.until(js, LIVE + " === '100% indexed'", "said when done")

    def test_the_line_in_the_all_projects_card_reads_reading_then_indexed_and_goes_with_its_folder(self):
        self.gate.clear()
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "!!document.querySelector('#ask-all-folder-list .ask-folder-line')", "list")
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexing… 0%'", "reading")
            LIVE = "(() => { const e = document.querySelector('#ask-all-folder-list .ask-folder-live'); return [e.getAttribute('role'), e.getAttribute('aria-live'), e.textContent]; })()"
            self.assertEqual(js(LIVE), ["status", "polite", "Indexing started"])      # row 1371: the line is quiet; this region speaks
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                look = js(self.LOOK % "#ask-all-folder-list .ask-folder-line")
                self.assertEqual((look["size"], look["weight"], look["mt"], look["role"], look["live"], look["below"]), ("13px", "400", "2px", None, None, True), (w, look))
            self.gate.set()
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexed for 1 of 1 projects'", "indexed (asked again within 2 s polls)")
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-live').textContent === '100% indexed'", "said at 100%")
            js("document.querySelector('[data-ask-all-remove]').click()")
            self.until(js, "!!document.querySelector('#ask-all-folders-none')", "removed with its line")
            self.assertFalse(js("!!document.querySelector('#ask-all-folders .ask-folder-line')"))


class FiveStates(Fixture):
    """Row 1371 AP10 to AP15: the five states the server reports, drawn under a folder in the project card and the All projects card,
    at 1400 and 900, light and dark. The server's answer is set here; the page reads it and does not invent it."""

    def serve(self, state, **more):
        path = str(self.own)
        self.svc.change({"project": "ABC", "action": "add", "path": path})
        self.assertTrue(self.ix.wait_idle(10))
        self.ix.status_for = lambda code, folders: {path: {"state": state, "line": "server text, not shown", **more}}
        self.svc.reindex = mock.Mock()
        return path

    def check(self, cdp, js, sel, text, link=None, again=None):
        for mode in ("light", "dark"):
            js(f"document.documentElement.dataset.theme = {mode!r}")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, f"document.querySelector({sel!r}).innerText === {text!r}", f"{mode} {w}")
                self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll {mode} {w}")
        names = js(f"[...document.querySelectorAll({sel!r} + ' button')].map(b => b.innerText)")
        self.assertEqual(names, [link] if link else [])
        if link:
            js(f"document.querySelector({sel!r} + ' button').click()")
            self.assertTrue(wait(lambda: self.svc.reindex.call_count == 1, 10), "one press calls reindex")
            self.assertEqual(self.svc.reindex.call_count, 1)

    def run_state(self, state, text, link=None, tab="project", **more):
        self.serve(state, **more)
        with chrome() as cdp:
            js = self.show(cdp, tab)
            self.check(cdp, js, "#ask-folders .ask-folder-line", text, link)

    def test_a_folder_not_started_says_waiting_to_index(self):
        self.run_state("waiting", "Waiting to index")

    def test_a_change_found_says_updating_n_files_changed(self):
        self.run_state("updating", "Updating\u2026 1 file changed", changed=1)

    def test_a_paused_folder_says_it_carries_on_when_clark_is_open(self):
        self.run_state("paused", "Indexing paused. It carries on when clark is open")

    def test_failed_says_could_not_index_and_try_again_starts_the_read(self):
        self.run_state("failed", "Could not index this folder. Try again", "Try again")

    def test_cleared_says_not_indexed_and_index_again_starts_the_read(self):
        self.run_state("cleared", "Not indexed. Index again", "Index again")

    def test_three_files_changed_is_plural(self):
        self.run_state("updating", "Updating\u2026 3 files changed", changed=3)

    def test_the_all_projects_tab_says_indexed_for_n_of_n_projects(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.assertTrue(self.ix.wait_idle(10))
        path = str(self.shared)
        self.svc.indexed_counts = lambda folders: {path: [3, 3]}
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.check(cdp, js, "#ask-all-folder-list .ask-folder-line", "Indexed for 3 of 3 projects")
            self.assertEqual(js("document.querySelector('#ask-all-folder-list .ask-folder-live').textContent"), "100% indexed")
            self.assertNotIn("100% indexed", js("document.querySelector('#ask-all-folder-list .ask-folder-line').innerText"))
        self.svc.indexed_counts = lambda folders: {path: [2, 3]}
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.until(js, "document.querySelector('#ask-all-folder-list .ask-folder-line').innerText === 'Indexed for 2 of 3 projects'", "2 of 3")
            self.assertNotIn("100% indexed", js("document.querySelector('#ask-all-folder-list .ask-folder-line').innerText"))

    def test_a_project_tab_keeps_100_percent_indexed_for_its_own_and_an_all_projects_folder(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        self.svc.indexed_counts = lambda folders: {str(self.shared): [3, 3]}
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, "document.querySelectorAll('.ask-folder-line').length === 2", "two lines")
            self.until(js, "[...document.querySelectorAll('.ask-folder-line')].every(e => e.innerText.startsWith('100% indexed'))", "100% indexed")
            self.assertFalse(js("[...document.querySelectorAll('.ask-folder-line')].some(e => e.innerText.includes('Indexed for'))"))

    def test_the_all_projects_tab_failed_link_asks_for_the_read_again(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.assertTrue(self.ix.wait_idle(10))
        path = str(self.shared)
        self.ix.status_for = lambda code, folders: {path: {"state": "failed", "line": "x"}}
        self.svc.reindex = mock.Mock()
        with chrome() as cdp:
            js = self.show(cdp, "all")
            self.check(cdp, js, "#ask-all-folder-list .ask-folder-line", "Could not index this folder. Try again", "Try again")

    def test_the_note_wraps_inside_a_narrow_row_and_does_not_overflow(self):
        """Row 1371 AP6, the last clause: a note that does not fit its row wraps onto more lines. The row is a wrapping flex line (shell.css .ask-folders li)
        and the note is a full-width flex item with normal white space (rules.css .ask-folder-line), so the row itself is narrowed to 180px here,
        at 1400 and 900, in light and dark, with the longest note of the five states: the note is two lines or more, stays inside the row, and the page does not scroll sideways."""
        text = "Indexing paused. It carries on when clark is open"
        self.serve("paused")
        probe = ("(() => { const l = document.querySelector('#ask-folders .ask-folder-line'); const li = l.closest('li'); const ln = parseFloat(getComputedStyle(l).lineHeight); "
                 "li.style.width = ''; const wide = l.getBoundingClientRect().height; li.style.boxSizing = 'border-box'; li.style.width = '180px'; "
                 "const n = l.getBoundingClientRect(); const r = li.getBoundingClientRect(); "
                 "const out = {ln: ln, wide: wide, h: n.height, right: n.right, left: n.left, rowW: r.width, rowLeft: r.left, rowRight: r.right, sw: l.scrollWidth, cw: l.clientWidth, "
                 "space: getComputedStyle(l).whiteSpace, page: document.documentElement.scrollWidth, win: window.innerWidth, text: l.innerText}; "
                 "li.style.width = ''; li.style.boxSizing = ''; return out; })()")
        with chrome() as cdp:
            js = self.show(cdp, "project")
            self.until(js, f"!!document.querySelector('#ask-folders .ask-folder-line') && document.querySelector('#ask-folders .ask-folder-line').innerText === {text!r}", "paused")
            for mode in ("light", "dark"):
                js(f"document.documentElement.dataset.theme = {mode!r}")
                for w in WIDTHS:
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                    self.until(js, "document.documentElement.scrollWidth <= window.innerWidth", f"no sideways scroll at {mode} {w}")
                    m = js(probe)
                    where = (mode, w, m)
                    self.assertEqual((m["text"], m["rowW"]), (text, 180), where)      # the longest note, in a row made 180px wide
                    self.assertEqual(m["wide"], m["ln"], f"the note is one line while its row is wide: {where}")
                    self.assertGreaterEqual(m["h"], 2 * m["ln"] - 1, f"the note wraps onto two lines or more in a narrow row: {where}")
                    self.assertLessEqual(m["sw"], m["cw"], f"the note's text does not overflow the note: {where}")
                    self.assertGreaterEqual(m["left"], m["rowLeft"] - 0.5, f"the note starts inside its row: {where}")
                    self.assertLessEqual(m["right"], m["rowRight"] + 0.5, f"the note ends inside its row: {where}")
                    self.assertLessEqual(m["page"], m["win"], f"no sideways scroll with the narrow row: {where}")


class Wired(unittest.TestCase):
    """Row 1371: the page draws the line with indexNote.js's words (its announce and its "(why)"), and the line itself is not a live region."""
    SRC = (Path(__file__).resolve().parent.parent / "src/clark/page/src/edit/AskSettings.jsx").read_text(encoding="utf-8")

    def test_the_card_uses_the_note_words_and_a_quiet_line(self):
        self.assertIn('import { announce, LINKS, note, projectsNote } from "./indexNote.js";', self.SRC)
        self.assertIn(">{LINKS.why}</button>", self.SRC)
        self.assertIn('<div class="ask-folder-live" role="status" aria-live="polite">{said.current}</div>', self.SRC)
        self.assertIn('<div class="ask-folder-line">{n.text}', self.SRC)
        self.assertNotIn("Show the files left out", self.SRC)


class CardsPage(Fixture):
    """The status line and the left-out list are the Classic theme's: the Cards page is as it was (no line, no button), in every card."""
    CLASSIC = False

    def test_cards_has_no_status_line_and_no_left_out_button_in_any_card(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})
        self.assertTrue(self.ix.wait_idle(10))
        self.assertTrue(ask_index.status(self.data, "ABC", [str(self.own)])["type"], "the folder has a file left out, so Classic would show the button")
        with chrome() as cdp:
            for tab in ("project", "all"):
                js = self.show(cdp, tab)
                self.until(js, "document.querySelectorAll('.folder-now').length >= 1", f"the folders are listed ({tab})")
                self.assertEqual(js("document.querySelectorAll('.ask-folder-line, .ask-left-out, .ask-left-btn').length"), 0, tab)


if __name__ == "__main__":
    unittest.main()
