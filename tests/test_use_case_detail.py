"""#157: one use case on its own page (src/clark/page/src/components/UseCaseDetail.jsx), Edit only.

Run: python3 dev/run_tests.py test_use_case_detail
Part 1 is the read behind the history (clark/use_cases_read.py): the lines a use case's history gives the page. Part 2 builds the
page from a copy of the source whose entry also mounts the component by itself (the route and the list are another part's work),
starts a real server whose change and undo are the real clark.changes over a real demo store (fictional data, built at a fixed date)
and drives it at 1400 and 900 px, light and dark: what the detail shows, each save being one change with one Undo, the eye, Archive
and Restore, no Delete anywhere, Esc and the crumb, no sideways scroll, targets of 24 px, text contrast. The published file never has
the component. The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import __main__ as launcher, changes, page, server as sv, use_cases_read  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_inline_edits import EMPTY_BRANDING, KEYS, click, key, need_chrome  # noqa: E402,F401
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
UC = "TUL-U-001"                     # demo: "Flag", on the dashboard, two linked work items, one linked milestone
ENTRY = """import { render } from "preact";
import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";
import { UseCaseDetail } from "./components/UseCaseDetail.jsx";

boot(EDIT);
if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", startApp); else startApp();
window.clarkMountUc = (id) => {
  let host = document.getElementById("uc-test");
  if (!host) {
    host = document.createElement("main");
    host.id = "uc-test";
    document.getElementById("main").style.display = "none";
    document.getElementById("main").after(host);
  }
  render(<UseCaseDetail id={id} />, host);
};
"""


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


# ---- part 1: the read behind the history ----
def event(**kw):
    base = {"table": "use_cases", "ref": "ABC-U-001", "field": "status", "before": "On track", "after": "Flag", "op": "update",
            "route": "dashboard", "by_user": "Demo User", "at": "2026-10-28 09:12:00.000", "is_undo": False}
    return {**base, **kw}


class HistoryRead(unittest.TestCase):
    def test_lines_are_the_fields_the_page_can_change_and_the_step_that_made_it(self):
        events = [event(field="archived", before="0", after="1"), event(field="updated_at"), event(field="sort_order", op="insert", before=None, after="0"),
                  event(field="standing", before="<p>old</p>", after="<p>new</p>"), event(field="id", op="insert", before=None, after="ABC-U-001"),
                  event(ref="ABC-U-002"), event(table="actions"), event(field="source", before="a", after="b")]
        got = use_cases_read.history_lines(events, "ABC-U-001")
        self.assertEqual([(g["field"], g["made"]) for g in got], [("archived", False), ("standing", False), ("id", True)])
        self.assertEqual((got[0]["before"], got[0]["after"], got[0]["who"], got[0]["how"]), ("0", "1", "Demo User", "dashboard"))
        self.assertEqual((got[1]["before"], got[1]["after"]), (None, None), "the standing text itself is never in the history lines")

    def test_an_undo_is_marked_and_a_long_value_is_cut_and_the_list_is_capped(self):
        got = use_cases_read.history_lines([event(is_undo=True, route="undo", before="x" * 500)], "ABC-U-001")[0]
        self.assertTrue(got["undo"])
        self.assertEqual(len(got["before"]), use_cases_read.SHORT)
        many = use_cases_read.history_lines([event() for _ in range(100)], "ABC-U-001")
        self.assertEqual(len(many), use_cases_read.HISTORY_MAX)

    def test_without_a_history_reader_a_use_case_has_no_history_key_and_a_failing_one_leaves_it_empty(self):
        with DemoStore() as store:
            read = use_cases_read.make_read(store.data_for, lambda code: set())
            self.assertNotIn("history", read("ABC")[0])

            def broken(refs):
                raise OSError("no")
            self.assertEqual(use_cases_read.make_read(store.data_for, lambda code: set(), broken)("ABC")[0]["history"], [])

    def test_the_real_reader_gives_the_lines_newest_first_and_the_launcher_reads_them_on_its_own_connection(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        demo.update("use_cases", demo.use_case, {"status": "Flag"})
        demo.update("use_cases", demo.use_case, {"client_visible": 0})
        out = use_cases_read.make_read(demo.store.data_for, lambda code: set(), launcher.use_case_history(demo.store))("ABC")[0]["history"]
        self.assertEqual([(h["field"], h["after"]) for h in out], [("client_visible", "0"), ("status", "Flag"), ("id", None)])
        self.assertTrue(all(h["who"] == USER for h in out))


# ---- part 2: the real page ----
CONTRAST = """(() => {
  const rgb = (c) => { const m = /rgba?\\(([^)]+)\\)/.exec(c); if (!m) return null; const p = m[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 }; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); };
  const back = (el) => { let base = { r: 255, g: 255, b: 255 }; const chain = []; for (let e = el; e; e = e.parentElement) chain.push(e);
    for (const e of chain.reverse()) { const c = rgb(getComputedStyle(e).backgroundColor); if (c && c.a > 0) base = c.a >= 1 ? c : { r: c.r * c.a + base.r * (1 - c.a), g: c.g * c.a + base.g * (1 - c.a), b: c.b * c.a + base.b * (1 - c.a) }; } return base; };
  const bad = [], seen = new Set();
  for (const el of document.querySelectorAll('[data-ucd] *')) {
    const own = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim()) || (el.tagName === 'TEXTAREA' && el.value.trim());
    if (!own || seen.has(el)) continue;
    const st = getComputedStyle(el); if (st.visibility === 'hidden' || st.display === 'none') continue;
    const fg = rgb(st.color), bg = back(el); if (!fg) continue;
    const a = lum(fg), b = lum(bg), ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
    if (ratio < 4.5) bad.push([el.className || el.tagName, st.color, ratio.toFixed(2)]);
    if (parseFloat(st.fontSize) < 13) bad.push([el.className || el.tagName, 'size', st.fontSize]);
  }
  return bad;
})()"""


class Detail(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = tempfile.mkdtemp(prefix="clark-ucd-")
        cls.src = Path(cls.tmp) / "src"
        shutil.copytree(PAGE_SRC, cls.src, ignore=shutil.ignore_patterns("shown"))
        (cls.src / "main.jsx").write_text(ENTRY, encoding="utf-8")
        with mock.patch.object(build_page, "SRC", cls.src):
            cls.built = build_page.build()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.sent = []
        real_change, real_undo = changes.make_change(self.path, [], USER), changes.make_undo(self.path, [], USER)

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return real(req)
            return call
        self.s = Running(data_for=self.read, projects=lambda: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: self.built,
                         change=seam(real_change, "change"), undo=seam(real_undo, "undo"))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def row(self, ref=UC):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.read("use_cases", ref=ref)
        finally:
            st.close()

    def steps(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.con.execute("SELECT count(*) FROM applies").fetchone()[0]
        finally:
            st.close()

    def open_detail(self, cdp, width=1400, scheme="light", edit=True, uc=UC):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#dashboard&p=TUL"}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.sec').length > 0", sid)), "the page drew")
        if edit:
            cdp.js("document.querySelector('[data-mode=edit]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#report').dataset.mode === 'edit'", sid)), "Edit")
        cdp.js(f"window.clarkMountUc({json.dumps(uc)})", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ucd]') && !/Loading the use case/.test(document.querySelector('[data-ucd]').innerText)", sid)))
        self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('ucd-h')", "the heading took the focus")
        return sid

    def until(self, cdp, sid, expr, what, seconds=20):
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), what)

    def toast(self, cdp, sid):
        return cdp.js("(document.querySelector('.toast-text') || {}).textContent || ''", sid)

    def undo(self, cdp, sid):
        before = self.steps()
        click(cdp, sid, "[data-undo]")
        self.until(cdp, sid, "/Undone/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the undo said so")
        self.assertEqual(self.steps(), before + 1, "an undo is one step")

    # ---- what it shows ----
    def test_the_detail_shows_everything_at_1400_and_900_px_light_and_dark(self):
        data = self.read("TUL")
        u = next(x for x in data["use_cases"] if x["id"] == UC)
        linked = sorted(r["id"] for k in ("actions", "raid", "decisions") for r in data[k] if r.get("use_case") == UC)
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme)
                    js = lambda e: cdp.js(e, sid)  # noqa: E731
                    self.until(cdp, sid, "!!document.querySelector('[data-history] li')", "the history was read")
                    self.assertEqual(js("document.querySelector('.ucd-crumb').textContent"), "Use cases › UC 1.1")
                    self.assertEqual(js("document.querySelector('.ucd-crumb a').getAttribute('href')"), "#usecases&p=TUL")
                    self.assertEqual(js("document.querySelector('[data-ucd-field=title]').value"), u["title"])
                    self.assertEqual(js("document.querySelector('[data-ucd-field=headline]').value"), u["headline"])
                    self.assertEqual(js("document.querySelector('[data-ucd] [data-word]').textContent"), "Flag", "the status is a word, not only a colour")
                    self.assertRegex(js("document.querySelector('.ucd-sub').textContent"), r"^Flag2 of 2 work items open · 1 milestone$")
                    self.assertEqual(js("document.querySelector('[data-eye]').textContent"), "On the dashboard")
                    self.assertEqual(js("document.querySelector('[data-eye-toggle]').textContent"), "Take off the dashboard")
                    self.assertEqual(js("[...document.querySelectorAll('#ucd-status')].length"), 1)
                    self.assertEqual(js("document.querySelector('[data-rich=standing]').textContent"), re.sub(r"<[^>]+>", "", u["standing"]))
                    self.assertEqual(sorted(js("[...document.querySelectorAll('[data-item]')].map(b => b.dataset.item)")), linked)
                    self.assertTrue(js("[...document.querySelectorAll('[data-item]')].every(b => b.querySelector('.pill') && b.querySelector('.ucd-x').textContent)"), "each row has a status pill and an owner or due")
                    self.assertEqual(js("[...document.querySelectorAll('[data-ucd] [data-ms]')].map(e => e.dataset.ms)"), ["TUL-M-005"])
                    self.assertIn("added the use case", js("document.querySelector('[data-history]').textContent"))
                    self.assertEqual(js("document.querySelector('[data-archive]').textContent"), "Archive this use case (it can be restored; nothing is deleted)")
                    self.assertFalse(js("/\\bdelete\\b/i.test(document.querySelector('[data-ucd]').innerText + [...document.querySelectorAll('[data-ucd] [aria-label],[data-ucd] [title]')].map(e => (e.getAttribute('aria-label') || '') + (e.title || '')).join(' '))"), "no Delete anywhere")
                    self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    columns = js("getComputedStyle(document.querySelector('.ucd-grid')).gridTemplateColumns.split(' ').length")
                    self.assertEqual(columns, 2 if width == 1400 else 1, "two columns at 1400 px, one at 900 px")
                    small = js("[...document.querySelectorAll('[data-ucd] button, [data-ucd] a, [data-ucd] textarea, [data-ucd] [role=button]')].filter(e => { const b = e.getBoundingClientRect(); return b.width && (b.height < 24 || b.width < 24); }).map(e => e.className + ':' + e.textContent.slice(0, 20))")
                    self.assertEqual(small, [], "every control is at least 24 px")
                    self.assertEqual(js(CONTRAST), [], "text is 13 px or more and has a contrast of 4.5:1")

    def test_in_view_nothing_changes_and_the_text_is_plain(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] textarea, [data-ucd] [data-rich], [data-eye-toggle], [data-archive], #ucd-status').length", sid), 0)
            self.assertIn("Flag", cdp.js("document.querySelector('[data-ucd] [data-word]').textContent", sid))
            self.assertTrue(cdp.js("document.querySelector('[data-ucd-field=title]').textContent.length > 0", sid))

    # ---- saving ----
    def test_the_standing_text_is_one_change_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before, was = self.steps(), self.row()["standing"]
            cdp.js("document.querySelector('[data-rich=standing]').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('.ProseMirror')", "the one editor opened")
            self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('ProseMirror')", "the editor has focus")
            cdp.js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Added by the test. '); true", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 4 if cdp.js("/Mac/.test(navigator.platform)", sid) else 2}, sid)
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertEqual(self.steps(), before + 1, "one save is one step")
            self.assertIn("Added by the test.", self.row()["standing"])
            self.assertEqual(self.sent[-1][1]["kind"], "use_cases")
            self.assertEqual((self.sent[-1][1]["op"], list(self.sent[-1][1]["changes"])), ("update", ["standing"]))
            self.until(cdp, sid, "document.querySelector('[data-rich=standing]') && document.querySelector('[data-rich=standing]').textContent.includes('Added by the test.')", "the page shows what was saved")
            self.until(cdp, sid, "[...document.querySelectorAll('[data-history] li')].some(l => /edited where it stands/.test(l.textContent))", "the history says so")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["standing"], was)
            self.until(cdp, sid, "!document.querySelector('[data-rich=standing]').textContent.includes('Added by the test.')", "Undo draws it as it was")

    def test_the_title_and_the_headline_are_one_change_each_with_one_undo_and_a_blank_title_is_refused(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            was = self.row()

            def type_into(field, text):
                cdp.js(f"(() => {{ const t = document.querySelector('[data-ucd-field={field}]'); t.focus(); t.select(); }})()", sid)
                cdp.call("Input.insertText", {"text": text}, sid)
                key(cdp, sid, "Enter")
            before = self.steps()
            type_into("title", "A new name")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertEqual((self.row()["title"], self.steps(), self.toast(cdp, sid)), ("A new name", before + 1, "Name changed."))
            self.until(cdp, sid, "document.querySelector('[data-ucd-field=title]').value === 'A new name'", "the page shows it")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["title"], was["title"])
            self.until(cdp, sid, f"document.querySelector('[data-ucd-field=title]').value === {json.dumps(was['title'])}", "Undo draws the old name")
            before = self.steps()
            type_into("headline", "One new line")
            self.until(cdp, sid, "/Headline changed/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the headline saved")
            self.assertEqual((self.row()["headline"], self.steps()), ("One new line", before + 1))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["headline"], was["headline"])
            n, before = len(self.sent), self.steps()
            cdp.js("(() => { const t = document.querySelector('[data-ucd-field=title]'); t.focus(); t.select(); })()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Delete", "code": "Delete", "windowsVirtualKeyCode": 46}, sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "/needs a name/.test((document.querySelector('.toast-text') || {}).textContent || '')", "a blank name is refused in plain words")
            self.assertEqual((len(self.sent), self.steps(), self.row()["title"]), (n, before, was["title"]), "nothing was sent")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd-field=title]').value", sid), was["title"])
            # Esc puts the text back and does not leave the page
            cdp.js("(() => { const t = document.querySelector('[data-ucd-field=headline]'); t.focus(); t.select(); })()", sid)
            cdp.call("Input.insertText", {"text": "Thrown away"}, sid)
            key(cdp, sid, "Escape")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd-field=headline]').value", sid), was["headline"])
            self.assertEqual((len(self.sent), cdp.js("location.hash", sid)), (n, "#dashboard&p=TUL"), "Esc in a field only puts the text back")

    def test_the_status_menu_offers_three_words_and_a_pick_is_one_change_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "#ucd-status")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[role=menu] [role=menuitemradio]')].map(b => b.textContent.replace('✓', ''))", sid), ["On track", "Flag", "High risk"])
            self.assertEqual(cdp.js("document.querySelector('[role=menu] [aria-checked=true]').textContent.replace('✓', '')", sid), "Flag")
            click(cdp, sid, "[role=menu] [data-kind='High risk']")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector('[data-ucd] [data-word]').textContent === 'High risk'", "the word changed")
            self.assertEqual((self.row()["status"], self.steps(), self.toast(cdp, sid)), ("High risk", before + 1, "Status changed to High risk."))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["status"], "Flag")
            self.until(cdp, sid, "document.querySelector('[data-ucd] [data-word]').textContent === 'Flag'", "Undo draws the old word")

    def test_the_eye_is_said_in_words_and_toggles_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "[data-eye-toggle]")
            self.until(cdp, sid, "document.querySelector('[data-eye]').textContent === 'Not on the dashboard'", "the words changed")
            self.assertEqual((self.row()["client_visible"], self.steps()), (0, before + 1))
            self.assertEqual(cdp.js("document.querySelector('[data-eye-toggle]').textContent", sid), "Put on the dashboard")
            self.assertEqual(cdp.js("document.querySelector('[data-dash]').textContent", sid), "Not on the dashboard")
            self.assertEqual(self.sent[-1][1]["changes"], {"client_visible": 0})
            self.undo(cdp, sid)
            self.assertEqual(self.row()["client_visible"], 1)
            self.until(cdp, sid, "document.querySelector('[data-eye]').textContent === 'On the dashboard'", "Undo put it back")

    # ---- archive ----
    def test_archive_makes_it_read_only_with_restore_and_one_undo_and_nothing_is_deleted(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "[data-archive]")
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "Restore is offered")
            self.assertEqual((self.row()["archived"], self.steps()), (1, before + 1), "Archive is one step and the row is still there")
            self.assertEqual(self.sent[-1][1], {"project": "TUL", "kind": "use_cases", "op": "archive", "id": UC, "place": "cell"})
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] textarea, [data-ucd] [data-rich], [data-eye-toggle], [data-archive], #ucd-status').length", sid), 0, "read-only")
            self.assertIn("Archived", cdp.js("document.querySelector('.ucd-sub').textContent", sid))
            self.assertIn("read-only", cdp.js("document.querySelector('[data-archived-note]').textContent", sid))
            self.assertFalse(cdp.js("/\\bdelete\\b/i.test(document.querySelector('[data-ucd]').innerText)", sid), "no Delete")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd-field=title]').textContent.length > 0", sid), True, "it still shows its text")
            self.until(cdp, sid, "document.querySelectorAll('[data-item]').length === 2", "its work items are still listed")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["archived"], 0)
            self.until(cdp, sid, "!!document.querySelector('[data-archive]') && !document.querySelector('[data-restore]')", "Undo brings it back, editable")
            # archive again, then Restore: one step, one Undo of that
            click(cdp, sid, "[data-archive]")
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "archived again")
            before = self.steps()
            click(cdp, sid, "[data-restore]")
            self.until(cdp, sid, "!!document.querySelector('[data-archive]')", "Restore made it editable again")
            self.assertEqual((self.row()["archived"], self.steps()), (0, before + 1))
            self.assertEqual(self.toast(cdp, sid), "Use case restored.")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["archived"], 1)
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "Undo of Restore archives it again")

    def test_an_archived_use_case_opens_read_only_with_restore(self):
        with self.store.step("dashboard", USER) as st:
            st.archive("use_cases", UC)
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "the archived use case was found and Restore is offered")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-word]').textContent", sid), "Flag")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] textarea, [data-archive]').length", sid), 0)
            self.assertEqual(cdp.js("document.querySelector('[data-dash]').textContent", sid), "Archived")

    def test_a_use_case_that_is_not_there_says_so_and_leads_back(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, uc="TUL-U-099")
            self.until(cdp, sid, "!!document.querySelector('[data-missing]')", "it says there is no such use case")
            self.assertEqual(cdp.js("document.querySelector('[data-missing] a').getAttribute('href')", sid), "#usecases&p=TUL")

    # ---- leaving ----
    def test_esc_and_the_crumb_return_to_the_list(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            self.until(cdp, sid, "document.activeElement === document.querySelector('.ucd-h')", "the page's heading has the focus on arrival")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "location.hash === '#usecases&p=TUL'", "Esc leaves for the list")
            cdp.js("history.replaceState(null, '', '#dashboard&p=TUL'); dispatchEvent(new HashChangeEvent('hashchange'))", sid)
            click(cdp, sid, "[data-uc-back]")
            self.until(cdp, sid, "location.hash === '#usecases&p=TUL'", "the crumb leaves for the list")
            # Esc with a menu open closes the menu and stays
            cdp.js("history.replaceState(null, '', '#dashboard&p=TUL'); dispatchEvent(new HashChangeEvent('hashchange'))", sid)
            click(cdp, sid, "#ucd-status")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "menu")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[role=menu]')", "Esc closed the menu")
            self.assertEqual(cdp.js("location.hash", sid), "#dashboard&p=TUL", "and stayed on the page")

    # ---- the published file ----
    def test_the_published_file_has_none_of_the_component(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("ucd-", "UseCaseDetail", "data-ucd", "use-cases?project", "archived=only", "Archive this use case"):
            self.assertNotIn(word, view, word)

    def test_the_built_pages_are_current(self):
        self.assertEqual(build_page.main(["--check"]), 0)

    def test_no_name_or_date_in_the_component_source(self):
        text = (PAGE_SRC / "components" / "UseCaseDetail.jsx").read_text(encoding="utf-8")
        self.assertNotRegex(text, r"\b(19|20)\d\d-\d\d-\d\d\b")
        self.assertNotIn("contenteditable", text.replace("isContentEditable", "").lower(), "the one editor and the plain text boxes only")


if __name__ == "__main__":
    unittest.main()
