"""#157: one use case on its own page (src/clark/page/src/components/UseCaseDetail.jsx); live, with no Edit mode (row 825).

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
import time
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore
from _real_server import real_server
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402

from clark import __main__ as launcher, page, server as sv, use_cases_read  # noqa: E402
from clark.store import open_store  # noqa: E402
from test_inline_edits import EMPTY_BRANDING, KEYS, click, key, need_chrome  # noqa: E402,F401
from test_undo_key import press_z  # noqa: E402
from test_server import chrome, wait, wait_toast  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
UC = "TUL-U-001"                     # demo: "Flag", on the dashboard, two linked work items, one linked milestone
ENTRY = """import { render } from "preact";
import { boot } from "./boot.jsx";
import { EDIT } from "./edit/index.js";
import { startApp } from "./app.js";
import { UseCaseDetail } from "./components/UseCaseDetail.jsx";
import { UCEDIT } from "./edit/UseCasesEdit.jsx";

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
  render(<UseCaseDetail id={id} ed={UCEDIT} />, host);
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

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return real(req)
            return call
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: self.built,
                             seam=seam)
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            d = st.data_for(code, archived=archived)
        finally:
            st.close()
        if getattr(self, "blank", False):                      # #659: the use case with nothing written, to see the prompts
            for x in d["use_cases"]:
                x["headline"], x["standing"] = "", ""
        return d

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
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#{'dashboard' if edit else 'usecases'}&p=TUL"}, sid)    # row 825: off the Dashboard the page is live and the change toast (with Undo) is drawn without Edit
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.sec').length > 0" if edit else "!!document.querySelector('#usecases')", sid)), "the page drew")
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
        return wait_toast(lambda: cdp.js("(document.querySelector('.toast-text') || {}).textContent || ''", sid))

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
                    self.assertEqual(js("document.querySelector('[data-ucd] [data-ucd-field=title]').value"), u["title"])
                    self.assertEqual(js("document.querySelector('[data-ucd] [data-ucd-field=headline]').value"), u["headline"])
                    self.assertEqual(js("document.querySelector('[data-ucd] [data-word]').textContent"), "Flag", "the status is a word, not only a colour")
                    self.assertRegex(js("document.querySelector('.ucd-sub').textContent"), r"^FlagCommitted2 of 2 work items open · 1 milestone$")
                    self.assertEqual(js("document.querySelector('.ucd-eye[data-eye]').title"), "On the dashboard")
                    self.assertEqual(js("document.querySelector('.ucd-eye[data-eye]').textContent.trim()"), "On the dashboard", "item 1010: the eye carries its words, one control")
                    self.assertEqual(js("document.querySelectorAll('[data-dash]').length"), 0, "item 1010: no second Dashboard row while the control is there")
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

    def test_the_crumb_is_tracked_capitals_and_its_link_is_not_underlined(self):
        # row 777: the same small capitals line as the other pages' crumbs; the link is indigo, underlined only on hover.
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme)
                    js = lambda e: cdp.js(e, sid)  # noqa: E731
                    self.assertEqual(js("getComputedStyle(document.querySelector('.ucd-crumb')).textTransform"), "uppercase")
                    self.assertEqual(js("getComputedStyle(document.querySelector('.ucd-crumb')).letterSpacing === 'normal'"), False)
                    self.assertIn("none", js("getComputedStyle(document.querySelector('.ucd-crumb a')).textDecorationLine"))
                    self.assertEqual(js("document.querySelector('.ucd-crumb').textContent"), "Use cases › UC 1.1", "the words are unchanged")

    def test_the_empty_where_it_stands_card_says_what_to_write_and_the_longer_prompt_fits(self):
        """#659: the owner's words, in the headline box (a placeholder, so the box keeps a plain name for a screen reader) and in the
        text box; the longer one wraps inside its card at 1400 and 900 px, light and dark. Screenshots go to CLARK_SHOTS when it is set."""
        import base64
        import os
        self.blank = True
        head, body = "Today's position, in one line", "What is done, what is happening now, and what is next. Add anything that is blocked or at risk."
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme)
                    js = lambda e: cdp.js(e, sid)  # noqa: E731
                    self.assertEqual(js("document.querySelector('[data-ucd-field=headline]').getAttribute('placeholder')"), head)
                    self.assertEqual(js("document.querySelector('[data-ucd-field=headline]').value"), "")
                    self.assertEqual(js("document.querySelector('[data-ucd-field=headline]').getAttribute('aria-label')"), "Headline for 1.1")
                    self.assertEqual(js("document.querySelector('[data-rich=standing]').textContent"), body)
                    self.assertEqual(js("document.querySelector('[data-rich=standing]').getAttribute('aria-label')"), "Edit where UC 1.1 stands")
                    self.assertEqual(js("document.querySelector('#ucd-h-std span').textContent"), "Where it stands")
                    self.assertTrue(js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                    self.assertTrue(js("(() => { const v = document.querySelector('[data-rich=standing]'), c = v.closest('.ucd-card'), p = v.querySelector('p'); "
                                       "const a = p.getBoundingClientRect(), b = c.getBoundingClientRect(); "
                                       "return p.scrollWidth <= p.clientWidth + 1 && a.left >= b.left && a.right <= b.right + 1; })()"), "the longer prompt stays inside its card")
                    self.assertEqual(js(CONTRAST), [], "text is 13 px or more and has a contrast of 4.5:1")
                    shots = os.environ.get("CLARK_SHOTS")
                    if shots:
                        js("document.querySelector('#ucd-h-std').scrollIntoView({block: 'center'})")
                        png = cdp.call("Page.captureScreenshot", {"format": "png"}, sid)["data"]
                        Path(shots, f"659-{width}-{scheme}.png").write_bytes(base64.b64decode(png))

    def test_every_control_is_there_with_no_edit_mode_at_1400_and_900_px_light_and_dark_row_825(self):
        """Row 825: the use case page has no View|Edit switch; the name, headline, status, eye, commitment, Where it stands and Archive are live."""
        for width in (1400, 915):          # 915 px of window is 900 px of page on this box (15 px scrollbar)
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width=width, scheme=scheme, edit=False)
                    self.assertNotEqual(cdp.js("document.querySelector('#report').dataset.mode", sid), "edit", "the page is not in Edit")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] textarea').length", sid), 2, "name and headline are boxes")
                    for sel in ("#ucd-status", "[data-ucd] [data-eye]", "[data-ucd] [data-archive]", "[data-ucd] [data-rich]", "[data-ucd] [data-uc-commit] button"):
                        self.assertEqual(cdp.js(f"document.querySelectorAll({json.dumps(sel)}).length", sid), 1, sel)

    def test_each_control_saves_as_one_change_with_one_undo_with_no_edit_mode_row_825(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            was = self.row()
            before = self.steps()
            cdp.js("(() => { const t = document.querySelector('[data-ucd] [data-ucd-field=title]'); t.focus(); t.select(); })()", sid)
            cdp.call("Input.insertText", {"text": "Named in View"}, sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertEqual((self.row()["title"], self.steps(), self.toast(cdp, sid)), ("Named in View", before + 1, "Name changed."))
            self.undo(cdp, sid)
            before = self.steps()
            click(cdp, sid, "#ucd-status")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the menu opened")
            click(cdp, sid, "[role=menu] [data-kind='High risk']")
            self.until(cdp, sid, "document.querySelector('[data-ucd] [data-word]').textContent === 'High risk'", "the status changed")
            self.assertEqual((self.row()["status"], self.steps()), ("High risk", before + 1))
            self.undo(cdp, sid)
            before = self.steps()
            click(cdp, sid, "[data-ucd] [data-eye]")
            self.until(cdp, sid, "document.querySelector('[data-ucd] [data-eye]').title === 'Not on the dashboard'", "the eye switched")
            self.assertEqual((self.row()["client_visible"], self.steps()), (0, before + 1))
            self.undo(cdp, sid)
            before = self.steps()
            cdp.js("document.querySelector('.ucd-sub [data-uc-commit] button').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[role=menu][aria-label=Commitment]')", "the commitment menu opened")
            cdp.js("[...document.querySelectorAll('[role=menu][aria-label=Commitment] [role^=menuitem]')].find(e => e.textContent.includes('Planned 2027')).click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the commitment saved")
            self.assertEqual((self.row()["commitment"], self.steps()), ("Planned 2027", before + 1))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["commitment"], was["commitment"])
            before = self.steps()
            click(cdp, sid, "[data-ucd] [data-archive]")
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "Restore is offered with no Edit mode")
            self.assertEqual((self.row()["archived"], self.steps()), (1, before + 1))
            self.assertNotIn("Switch to Edit", cdp.js("document.querySelector('[data-archived-note]').textContent", sid))
            click(cdp, sid, "[data-restore]")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-archive]')", "Restore worked with no Edit mode")
            self.assertEqual(self.row()["archived"], 0)

    def test_the_standing_text_saves_with_no_edit_mode_row_825(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            before = self.steps()
            cdp.js("document.querySelector('[data-rich=standing]').click()", sid)
            self.until(cdp, sid, "document.activeElement && document.activeElement.classList.contains('ProseMirror')", "the editor has focus")
            cdp.js("document.querySelector('.ProseMirror').cxed.editor.commands.insertContent('Written in View. '); true", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, "modifiers": 4 if cdp.js("/Mac/.test(navigator.platform)", sid) else 2}, sid)
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertIn("Written in View.", self.row()["standing"])
            self.assertEqual(self.steps(), before + 1)

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

    def test_the_commitment_is_one_change_with_one_undo_and_the_history_says_it_in_words(self):
        """#709: the chip in the detail is a menu in Edit; a choice is one change, one Undo, and a History line from the old word to the new."""
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            was = self.row()["commitment"]
            self.assertEqual(was, "Committed", "the demo's first TUL use case")
            self.assertEqual(cdp.js("document.querySelector('.ucd-sub [data-uc-commit] button').getAttribute('aria-label')", sid), "Commitment: Committed. Change")
            before = self.steps()
            cdp.js("document.querySelector('.ucd-sub [data-uc-commit] button').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[role=menu][aria-label=Commitment]')", "the menu opened")
            cdp.js("[...document.querySelectorAll('[role=menu][aria-label=Commitment] [role^=menuitem]')].find(e => e.textContent.includes('Planned 2027')).click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertEqual(self.steps(), before + 1, "one choice is one step")
            self.assertEqual(self.row()["commitment"], "Planned 2027")
            self.assertEqual((self.sent[-1][1]["op"], self.sent[-1][1]["changes"]), ("update", {"commitment": "Planned 2027"}))
            self.until(cdp, sid, "[...document.querySelectorAll('[data-history] li')].some(l => /changed the Commitment from Committed to Planned 2027/.test(l.textContent))", "the history says so")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["commitment"], was)
            cdp.js("document.querySelector('.ucd-sub [data-uc-commit] button').click()", sid)
            self.until(cdp, sid, "!!document.querySelector('[role=menu][aria-label=Commitment]')", "the menu opened again")
            cdp.js("[...document.querySelectorAll('[role=menu][aria-label=Commitment] [role^=menuitem]')].find(e => e.textContent.includes('No flag')).click()", sid)
            self.until(cdp, sid, "[...document.querySelectorAll('[data-history] li')].some(l => /changed the Commitment from Committed to no flag/.test(l.textContent))", "a clear reads as no flag")
            self.assertIsNone(self.row()["commitment"])
            self.until(cdp, sid, "document.querySelector('.ucd-sub [data-uc-commit] button').textContent === 'Set commitment'", "the quiet Set commitment affordance")

    def test_the_commitment_menu_is_headed_commitment(self):
        """row 791: the open commitment menu starts with the one word Commitment (a heading, not a command), over the three words and No flag;
        at 1400 and 900 px, light and dark. Screenshots go to CLARK_SHOTS when it is set."""
        import base64
        import os
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme)
                    js = lambda e: cdp.js(e, sid)  # noqa: E731
                    js("document.querySelector('.ucd-sub [data-uc-commit] button').click()")
                    self.until(cdp, sid, "!!document.querySelector('[role=menu][aria-label=Commitment]')", "the menu opened")
                    menu = "document.querySelector('[role=menu][aria-label=Commitment]')"
                    self.assertEqual(js(f"[...{menu}.querySelectorAll('.lab')].map(e => e.textContent.trim())"), ["Commitment"])
                    self.assertEqual(js(f"{menu}.firstElementChild.querySelector('.lab') !== null || {menu}.firstElementChild.classList.contains('lab')"), True, "the heading is first")
                    self.assertEqual(js(f"[...{menu}.querySelectorAll('[role=menuitemradio]')].map(e => e.textContent.replace('\u2713', '').trim())"),
                                     ["Planned 2026", "Committed", "Planned 2027", "No flag"], "the heading is not a pickable row")
                    self.assertEqual(js(f"{menu}.querySelector('[aria-checked=true]').textContent.replace('\u2713', '').trim()"), "Committed")
                    shots = os.environ.get("CLARK_SHOTS")
                    if shots:
                        png = cdp.call("Page.captureScreenshot", {"format": "png"}, sid)["data"]
                        Path(shots, f"791-commitment-menu-{width}-{scheme}.png").write_bytes(base64.b64decode(png))

    def test_the_title_and_the_headline_are_one_change_each_with_one_undo_and_a_blank_title_is_refused(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            was = self.row()

            def type_into(field, text):
                cdp.js(f"(() => {{ const t = document.querySelector('[data-ucd] [data-ucd-field={field}]'); t.focus(); t.select(); }})()", sid)
                cdp.call("Input.insertText", {"text": text}, sid)
                key(cdp, sid, "Enter")
            before = self.steps()
            type_into("title", "A new name")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]')", "the toast offers Undo")
            self.assertEqual((self.row()["title"], self.steps(), self.toast(cdp, sid)), ("A new name", before + 1, "Name changed."))
            self.until(cdp, sid, "document.querySelector('[data-ucd] [data-ucd-field=title]').value === 'A new name'", "the page shows it")
            self.undo(cdp, sid)
            self.assertEqual(self.row()["title"], was["title"])
            self.until(cdp, sid, f"document.querySelector('[data-ucd] [data-ucd-field=title]').value === {json.dumps(was['title'])}", "Undo draws the old name")
            before = self.steps()
            type_into("headline", "One new line")
            self.until(cdp, sid, "/Headline changed/.test((document.querySelector('.toast-text') || {}).textContent || '')", "the headline saved")
            self.assertEqual((self.row()["headline"], self.steps()), ("One new line", before + 1))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["headline"], was["headline"])
            n, before = len(self.sent), self.steps()
            cdp.js("(() => { const t = document.querySelector('[data-ucd] [data-ucd-field=title]'); t.focus(); t.select(); })()", sid)
            cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Delete", "code": "Delete", "windowsVirtualKeyCode": 46}, sid)
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "/needs a name/.test((document.querySelector('.toast-text') || {}).textContent || '')", "a blank name is refused in plain words")
            self.assertEqual((len(self.sent), self.steps(), self.row()["title"]), (n, before, was["title"]), "nothing was sent")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-ucd-field=title]').value", sid), was["title"])
            # Esc puts the text back and does not leave the page
            cdp.js("(() => { const t = document.querySelector('[data-ucd] [data-ucd-field=headline]'); t.focus(); t.select(); })()", sid)
            cdp.call("Input.insertText", {"text": "Thrown away"}, sid)
            key(cdp, sid, "Escape")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-ucd-field=headline]').value", sid), was["headline"])
            self.assertEqual((len(self.sent), cdp.js("location.hash", sid)), (n, "#dashboard&p=TUL"), "Esc in a field only puts the text back")

    def test_the_status_menu_offers_four_words_and_a_pick_is_one_change_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "#ucd-status")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the menu opened")
            self.assertEqual(cdp.js("[...document.querySelectorAll('[role=menu] [role=menuitemradio]')].map(b => b.textContent.replace('✓', ''))", sid), ["On track", "Flag", "High risk", "Done"])
            self.assertEqual(cdp.js("document.querySelector('[role=menu] [aria-checked=true]').textContent.replace('✓', '')", sid), "Flag")
            click(cdp, sid, "[role=menu] [data-kind='High risk']")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector('[data-ucd] [data-word]').textContent === 'High risk'", "the word changed")
            self.assertEqual((self.row()["status"], self.steps(), self.toast(cdp, sid)), ("High risk", before + 1, "Status changed to High risk."))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["status"], "Flag")
            self.until(cdp, sid, "document.querySelector('[data-ucd] [data-word]').textContent === 'Flag'", "Undo draws the old word")

    def slash(self, cdp, sid):
        common = {"key": "/", "code": "Slash", "windowsVirtualKeyCode": 191}
        cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", **common, "text": "/"}, sid)
        cdp.call("Input.dispatchKeyEvent", {"type": "keyUp", **common}, sid)

    def test_two_slashes_open_the_words_box_and_enter_is_one_change_with_one_undo(self):
        """Sneak peek on a use case: status, commitment and headline in words; Done asks first; Esc closes the box; View has no box."""
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before, was = self.steps(), self.row()
            self.slash(cdp, sid)
            self.assertFalse(cdp.js("!!document.querySelector('[data-sneak]')", sid), "one slash opens nothing")
            self.slash(cdp, sid)
            self.until(cdp, sid, "!!document.querySelector('.sn-in')", "the words box opened")

            def type_words(text):
                cdp.js(f"(() => {{ const i = document.querySelector('.sn-in'); i.value = {json.dumps(text)}; i.dispatchEvent(new Event('input', {{bubbles: true}})); }})()", sid)
            type_words("done")
            self.until(cdp, sid, "!!document.querySelector('[data-sneak-confirm]')", "Done asks first")
            key(cdp, sid, "Enter")
            self.assertEqual(self.row()["status"], was["status"], "Enter alone does not apply a Done")
            self.assertTrue(cdp.js("!!document.querySelector('[data-sneak-confirm-btn]') && !!document.querySelector('.sn-chips')", sid), "row 776: the OK line, its link and the chips stay")
            cdp.js("document.querySelector('[data-sneak-not-now]').click()", sid)
            self.until(cdp, sid, "!document.querySelector('[data-sneak]')", "Not now closed the box")
            self.assertEqual(self.row()["status"], was["status"], "Not now leaves the status alone")
            self.slash(cdp, sid)
            self.slash(cdp, sid)
            self.until(cdp, sid, "!!document.querySelector('.sn-in')", "the box opened again")
            type_words("done")
            self.until(cdp, sid, "!!document.querySelector('[data-sneak-confirm]')", "Done asks first, again")
            type_words("high risk, planned 2026, headline: Vendor is late")
            self.until(cdp, sid, "document.querySelectorAll('.sn-list li').length === 3", "three lines")
            key(cdp, sid, "Enter")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector('[data-ucd] [data-word]').textContent === 'High risk'", "applied")
            row = self.row()
            self.assertEqual((row["status"], row["commitment"], row["headline"], self.steps()), ("High risk", "Planned 2026", "Vendor is late", before + 1))
            self.assertFalse(cdp.js("!!document.querySelector('[data-sneak]')", sid), "Enter closes the box")
            self.undo(cdp, sid)
            row = self.row()
            self.assertEqual((row["status"], row["commitment"], row["headline"]), (was["status"], was["commitment"], was["headline"]))
            cdp.js("document.querySelector('.ucd-h').focus()", sid)      # row 1015: the heading has focus when the box opens
            self.slash(cdp, sid)
            self.slash(cdp, sid)
            self.until(cdp, sid, "!!document.querySelector('.sn-in')", "the box opened again")
            self.until(cdp, sid, "document.activeElement.className === 'sn-in'", "the box took focus")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('[data-sneak]')", "Esc closed the box")
            self.assertTrue(cdp.js("!!document.querySelector('[data-ucd]')", sid), "and stayed on the use case")
            self.until(cdp, sid, "document.activeElement.classList.contains('ucd-h')", "focus went back to the heading that had it (row 1015: no sparkle to return to)")

    def test_two_slashes_open_the_words_box_on_a_use_case_page_with_no_edit_mode(self):
        """Row 825: a use case's own page has no View, so the words box opens from two slashes without Edit."""
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            self.slash(cdp, sid)
            self.slash(cdp, sid)
            self.until(cdp, sid, "!!document.querySelector('.sn-in')", "the words box opened with no Edit mode")

    def test_two_slashes_open_no_words_box_on_an_archived_use_case(self):
        """An archived use case is read-only: no words box, in either way of opening the page."""
        with self.store.step("dashboard", USER) as st:
            st.archive("use_cases", UC)
        for edit in (True, False):
            with self.subTest(edit=edit), chrome() as cdp:
                sid = self.open_detail(cdp, edit=edit)
                self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "the archived use case is drawn")
                self.slash(cdp, sid)
                self.slash(cdp, sid)
                self.assertFalse(wait(lambda: cdp.js("!!document.querySelector('[data-sneak],[data-sneak-open]')", sid), 1.4), "no words box on an archived use case")

    def test_done_in_the_status_menu_saves_and_shows_its_word_in_grey(self):
        """#412: choosing Done in Edit saves it (one change, one Undo) and the page shows the word Done with the grey dot."""
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "#ucd-status")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the menu opened")
            click(cdp, sid, "[role=menu] [data-kind='Done']")
            self.until(cdp, sid, "!!document.querySelector('[data-undo]') && document.querySelector('[data-ucd] [data-word]').textContent === 'Done'", "the word changed")
            self.assertEqual((self.row()["status"], self.steps(), self.toast(cdp, sid)), ("Done", before + 1, "Status changed to Done."))
            self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-word]').className", sid).split()[-1], "rag-n")
            self.assertEqual(cdp.js("getComputedStyle(document.querySelector('[data-ucd] [data-word] .ragdot')).backgroundColor", sid),
                             cdp.js("(() => { const i = document.createElement('i'); i.style.color = 'var(--status-grey)'; document.body.append(i); "
                                    "const c = getComputedStyle(i).color; i.remove(); return c; })()", sid))
            self.undo(cdp, sid)
            self.assertEqual(self.row()["status"], "Flag")

    def test_the_eye_is_one_button_with_its_words_and_toggles_with_one_undo(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, ".ucd-eye[data-eye]")
            self.until(cdp, sid, "document.querySelector('.ucd-eye[data-eye]').title === 'Not on the dashboard'", "the tooltip changed")
            self.assertEqual((self.row()["client_visible"], self.steps()), (0, before + 1))
            self.assertEqual(cdp.js("document.querySelector('.ucd-eye[data-eye]').getAttribute('aria-label')", sid), "Not on the dashboard")
            self.assertEqual(cdp.js("document.querySelector('.ucd-eye[data-eye]').textContent.trim()", sid), "Not on the dashboard")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-dash]').length", sid), 0)
            self.assertEqual(self.sent[-1][1]["changes"], {"client_visible": 0})
            self.undo(cdp, sid)
            self.assertEqual(self.row()["client_visible"], 1)
            self.until(cdp, sid, "document.querySelector('.ucd-eye[data-eye]').title === 'On the dashboard'", "Undo put it back")

    def test_change_status_has_room_between_its_words_and_chevron_and_the_controls_are_as_tall(self):
        """Row 791."""
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width=width, scheme=scheme)
                    got = cdp.js("""(() => { const b = document.querySelector('#ucd-status'), t = b.querySelector('span').getBoundingClientRect(), c = b.querySelector('svg').getBoundingClientRect();
                        const e = document.querySelector('.ucd-eye[data-eye]').getBoundingClientRect(), r = b.getBoundingClientRect();
                        return { gap: c.left - t.right, eye: e.height, btn: r.height }; })()""", sid)
                    self.assertGreaterEqual(got["gap"], 4, got)
                    self.assertGreaterEqual(got["eye"], got["btn"] - 1, got)

    def test_the_eye_and_its_words_are_one_button_that_works_from_the_keyboard_and_never_meets_the_commitment_chip(self):
        """Issue 753."""
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width=width, scheme=scheme)
                    got = cdp.js("""(() => { const e = document.querySelector('.ucd-eye[data-eye]'), b = e.getBoundingClientRect();
                        const others = [...document.querySelectorAll('.ucd-sub [data-uc-commit], .ucd-sub .cchip, #ucd-status, .ucd-acts .btn')];
                        return { tag: e.tagName, words: e.innerText.trim(), svg: e.querySelectorAll('svg').length, title: e.title, label: e.getAttribute('aria-label'),
                          head: document.querySelector('[data-ucd]').innerText.toLowerCase().includes('home dashboard'), n: others.length,
                          inside: b.left >= 0 && b.right <= innerWidth, side: Math.min(b.width, b.height),
                          clash: others.some(x => { const c = x.getBoundingClientRect(); return b.left < c.right && c.left < b.right && b.top < c.bottom && c.top < b.bottom; }) }; })()""", sid)
                    self.assertEqual((got["tag"], got["words"], got["svg"], got["head"]), ("BUTTON", "On the dashboard", 1, False), got)
                    self.assertEqual((got["title"], got["label"]), ("On the dashboard", "On the dashboard"))
                    self.assertTrue(got["inside"] and not got["clash"] and got["n"] >= 2, got)
                    self.assertGreaterEqual(got["side"], 24)
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            for key, code, vk in (("Enter", "Enter", 13), (" ", "Space", 32)):
                cdp.js("document.querySelector('.ucd-eye[data-eye]').focus()", sid)
                was = self.row()["client_visible"]
                for kind in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk,
                                                         **({"text": "\r" if key == "Enter" else " "} if kind == "keyDown" else {})}, sid)
                self.until(cdp, sid, f"document.querySelector('.ucd-eye[data-eye]').title === '{'Not on the dashboard' if was else 'On the dashboard'}'", f"{code} toggled it")
                self.assertEqual(self.row()["client_visible"], 0 if was else 1)
            cdp.js("document.querySelector('.ucd-eye[data-eye]').focus()", sid)
            self.assertNotEqual(cdp.js("getComputedStyle(document.querySelector('.ucd-eye[data-eye]')).outlineStyle", sid), "none")

    # ---- archive ----
    def test_archive_makes_it_read_only_with_restore_and_one_undo_and_nothing_is_deleted(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp)
            before = self.steps()
            click(cdp, sid, "[data-archive]")
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "Restore is offered")
            self.assertEqual((self.row()["archived"], self.steps()), (1, before + 1), "Archive is one step and the row is still there")
            self.assertEqual(self.sent[-1][1], {"project": "TUL", "kind": "use_cases", "op": "archive", "id": UC, "place": "cell"})
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] textarea, [data-ucd] [data-rich], [data-archive], #ucd-status').length", sid), 0, "read-only")
            self.assertIn("Archived", cdp.js("document.querySelector('.ucd-sub').textContent", sid))
            self.assertIn("read-only", cdp.js("document.querySelector('[data-archived-note]').textContent", sid))
            self.assertFalse(cdp.js("/\\bdelete\\b/i.test(document.querySelector('[data-ucd]').innerText)", sid), "no Delete")
            self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-ucd-field=title]').textContent.length > 0", sid), True, "it still shows its text")
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
            self.until(cdp, sid, "((document.querySelector('.toast-text') || {}).textContent || '') === 'Use case restored.'", "the toast says it was restored")
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

    # ---- the peek beside the page (rows 859 and 860) ----
    def peek_round(self, cdp, sid, opener, shown):
        """Open the peek from `opener` (a selector) with the mouse or Enter, check it, close it with Esc, and check the page stayed and the focus came back."""
        hash_before = cdp.js("location.hash", sid)
        self.until(cdp, sid, f"!!document.querySelector({json.dumps(opener)})", "the opener is drawn")
        for how in ("click", "enter"):
            if how == "click":
                click(cdp, sid, opener)
            else:
                cdp.js(f"document.querySelector({json.dumps(opener)}).focus()", sid)
                key(cdp, sid, "Enter")
            self.until(cdp, sid, f"!!document.querySelector('#peek[data-peek={shown}]')", f"{how}: the peek shows {shown}")
            self.assertTrue(cdp.js("!!document.querySelector('[data-ucd]') && !!document.querySelector('[data-ucd]').offsetParent", sid), "the use case page stays")
            self.assertNotRegex(cdp.js("location.hash", sid), r"^#work", "and the address did not leave for Work items")
            self.assertTrue(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), "no sideways scroll")
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "!document.querySelector('#peek')", f"{how}: Esc closed the peek")
            self.assertEqual(cdp.js("location.hash", sid), hash_before, "Esc closed the peek and did not leave the page")
            self.assertTrue(cdp.js("!!document.querySelector('[data-ucd]')", sid), "the page is still there")
            self.until(cdp, sid, f"document.activeElement === document.querySelector({json.dumps(opener)})", f"{how}: the focus is back on the opener")

    def test_the_work_items_card_is_one_line_per_item_with_one_tinted_chip_row_1081(self):
        """Row 1081: ID, title, one tinted status chip, then Owner and Due in muted text, on ONE line at 1400 and 900, light and dark.
        The chip takes the colours of row 1021 (Open green, Made and Closed blue, grey when withdrawn or cancelled), not the old pill's."""
        probe = ("(() => { const out = {}; for (const t of ['red', 'amber', 'green', 'blue', 'grey']) { const e = document.createElement('i'); e.style.cssText = 'color:var(--tone-' + t + '-text);background:var(--tone-' + t + '-tint)'; document.body.appendChild(e); "
                 "const c = getComputedStyle(e); out[t] = [c.color, c.backgroundColor]; e.remove(); } return out; })()")
        rows = ("[...document.querySelectorAll('[data-item]')].map(b => { const q = (s) => b.querySelector(s), r = (e) => e.getBoundingClientRect(), chip = q('.pill'), c = getComputedStyle(chip), x = q('.ucd-x');"
                " return {id: b.dataset.item, h: r(b).height, chips: b.querySelectorAll('.pill').length, word: chip.textContent.trim(), cls: chip.className, fg: c.color, bg: c.backgroundColor,"
                " one: r(q('.ucd-id')).top < r(chip).bottom && r(x).top < r(chip).bottom && r(chip).top < r(q('.ucd-id')).bottom + 8 && Math.abs(r(x).top - r(q('.ucd-id')).top) < 12,"
                " muted: getComputedStyle(x).color === getComputedStyle(q('.ucd-id')).color, ordered: r(q('.ucd-id')).left < r(q('.ucd-t')).left && r(q('.ucd-t')).left < r(chip).left && r(chip).left < r(x).left}; })")
        want = {"Open": "green", "Pending": "green", "Made": "blue", "Closed": "blue", "Overdue": "red", "Due soon": "amber"}
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme, edit=False)
                    tones = cdp.js(probe, sid)
                    found = cdp.js(rows, sid)
                    self.assertTrue(found, "the card lists its items")
                    for r in found:
                        self.assertEqual(r["chips"], 1, r["id"])
                        self.assertTrue(r["one"], f"{r['id']}: the id, title, chip and owner and due sit on one line at {width}")
                        self.assertTrue(r["ordered"], f"{r['id']}: id, title, chip, then owner and due")
                        self.assertTrue(r["muted"], f"{r['id']}: owner and due are muted like the id")
                        self.assertLess(r["h"], 48, r["id"])
                        if r["word"] in want:
                            self.assertEqual([r["fg"], r["bg"]], tones[want[r["word"]]], f"{r['id']} {r['word']} takes its row 1021 tone")

    def _uc_items(self):
        data = self.read("TUL")
        return [(k, r) for k in ("actions", "raid", "decisions") for r in data[k] if r.get("use_case") == UC]

    def test_hostile_a_huge_unbroken_unicode_title_keeps_one_line_and_no_sideways_scroll_row_1081(self):
        """Hostile row 1081: a 600-character title with no spaces, RTL and emoji must not wrap the row to many lines or push the page sideways."""
        kind, row = next((k, r) for k, r in self._uc_items() if k == "actions")
        with self.store.step("dashboard", USER) as st:
            st.update(kind, row["id"], {"description": ("\u202e\u05e9\u05dc\u05d5\u05dd\U0001F525" + "W" * 600)})
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width, scheme, edit=False)
                    m = cdp.js("(() => { const b = document.querySelector('[data-item=' + JSON.stringify(%s) + ']'); const r = b.getBoundingClientRect();"
                               " return {h: r.height, sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth}; })()" % json.dumps(row["id"]), sid)
                    self.assertLessEqual(m["sw"], m["cw"], "no sideways scroll")
                    self.assertLess(m["h"], 48, "ONE line per item: a long title is cut, it does not make the row many lines tall")

    def test_hostile_markup_in_a_title_is_text_and_a_closed_item_takes_the_blue_tone_row_1081(self):
        """Hostile row 1081: <img onerror> in a title shows as text, never an element; a Closed item has the blue chip, in both schemes."""
        items = self._uc_items()
        with self.store.step("dashboard", USER) as st:
            for k, r in items:
                if k == "actions":
                    st.update(k, r["id"], {"description": "<img src=x onerror=window.__pwn=1><b>bold</b>", "status": "Closed"})
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.open_detail(cdp, 1400, scheme, edit=False)
                self.assertFalse(cdp.js("!!window.__pwn || !!document.querySelector('.ucd-item img, .ucd-item b')", sid), "markup in a title is text")
                blue = cdp.js("(() => { const e = document.createElement('i'); e.style.cssText = 'color:var(--tone-blue-text);background:var(--tone-blue-tint)'; document.body.appendChild(e); const c = getComputedStyle(e); return [c.color, c.backgroundColor]; })()", sid)
                for b in cdp.js("[...document.querySelectorAll('[data-item]')].map(b => { const c = getComputedStyle(b.querySelector('.pill')); return {id: b.dataset.item, word: b.querySelector('.pill').textContent.trim(), fg: c.color, bg: c.backgroundColor}; })", sid):
                    if b["word"] == "Closed":
                        self.assertEqual([b["fg"], b["bg"]], blue, f"{b['id']} Closed is blue")

    def test_hostile_an_archived_work_item_is_not_listed_and_enter_opens_the_peek_row_1081(self):
        """Hostile row 1081: an archived work item is not on the card; only this use case's items are; Enter on a row opens the peek."""
        items = self._uc_items()
        kind, row = items[0]
        with self.store.step("dashboard", USER) as st:
            st.archive(kind, row["id"])
        with chrome() as cdp:
            sid = self.open_detail(cdp, 1400, "light", edit=False)
            ids = cdp.js("[...document.querySelectorAll('[data-item]')].map(b => b.dataset.item)", sid)
            self.assertNotIn(row["id"], ids, "an archived item is not on the card")
            self.assertTrue(set(ids) <= {r["id"] for _k, r in items}, "only this use case's items")
            if ids:
                cdp.js("document.querySelector('[data-item]').focus()", sid)
                key(cdp, sid, "Enter")
                self.until(cdp, sid, "!!document.querySelector('.peek, [data-peek], [data-sneak-open]')", "Enter opens the peek")

    def test_every_chip_tone_red_amber_green_blue_grey_is_painted_on_the_card_row_1081(self):
        """Row 1081 (mutation gap): the demo's two items only show amber and one other tone, so a wrong red, green or grey chip passed. Seed each state and read the colours."""
        probe = ("(() => { const out = {}; for (const t of ['red', 'amber', 'green', 'blue', 'grey']) { const e = document.createElement('i'); e.style.cssText = 'color:var(--tone-' + t + '-text);background:var(--tone-' + t + '-tint)'; document.body.appendChild(e); "
                 "const c = getComputedStyle(e); out[t] = [c.color, c.backgroundColor]; e.remove(); } return out; })()")
        chips = "[...document.querySelectorAll('[data-item]')].map(b => { const c = getComputedStyle(b.querySelector('.pill')); return {id: b.dataset.item, word: b.querySelector('.pill').textContent.trim(), fg: c.color, bg: c.backgroundColor, dot: getComputedStyle(b.querySelector('.pill'), '::before').backgroundColor}; })"
        cases = [({"status": "Open", "due_date": "2020-01-01"}, "Overdue", "red"), ({"status": "Open", "due_date": "2030-01-01"}, "Open", "green"),
                 ({"status": "Open", "due_date": "2026-11-02"}, "Due soon", "amber"), ({"status": "Closed", "due_date": "2030-01-01"}, "Closed", "blue"),
                 ({"status": "Cancelled", "due_date": "2030-01-01"}, "Cancelled", "grey")]
        for change, word, tone in cases:
            with self.subTest(word=word):
                with self.store.step("dashboard", USER) as st:
                    st.update("actions", "TUL-A-001", change)
                for scheme in ("light", "dark"):
                    with chrome() as cdp:
                        sid = self.open_detail(cdp, 1400, scheme, edit=False)
                        tones = cdp.js(probe, sid)
                        got = next(c for c in cdp.js(chips, sid) if c["id"] == "TUL-A-001")
                        self.assertEqual(got["word"], word)
                        self.assertEqual([got["fg"], got["bg"]], tones[tone], f"{word} chip is {tone} in {scheme}")
                        self.assertEqual(got["dot"], tones[tone][0], f"{word} dot is {tone} in {scheme}")

    def test_the_card_row_cuts_long_text_with_dots_and_never_overlaps_the_id_row_1081(self):
        """Row 1081 (mutation gap): id, title and owner/due are single-line cells that end in dots; the id never runs into the title; the owner and due cell is not wider than 260px."""
        with self.store.step("dashboard", USER) as st:
            st.update("actions", "TUL-A-001", {"description": "T" * 400 + " end", "owner": "Somebody With An Extremely Long Name " * 8})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_detail(cdp, width, "light", edit=False)
                m = cdp.js("(() => { const b = document.querySelector('[data-item=\"TUL-A-001\"]'), q = (s) => b.querySelector(s), r = (e) => e.getBoundingClientRect(), g = (e, p) => getComputedStyle(e)[p];"
                           " return {ws: [g(q('.ucd-id'), 'whiteSpace'), g(q('.ucd-t'), 'whiteSpace'), g(q('.ucd-x'), 'whiteSpace')], to: [g(q('.ucd-t'), 'textOverflow'), g(q('.ucd-x'), 'textOverflow')],"
                           " idw: r(q('.ucd-id')).width, idRight: r(q('.ucd-id')).right, tLeft: r(q('.ucd-t')).left, xw: r(q('.ucd-x')).width, h: r(b).height}; })()", sid)
                self.assertEqual(m["ws"], ["nowrap", "nowrap", "nowrap"], "id, title and owner stay on one line")
                self.assertEqual(m["to"], ["ellipsis", "ellipsis"], "a long title or owner ends in dots")
                self.assertLessEqual(m["idRight"], m["tLeft"], "the id does not run into the title")
                self.assertGreaterEqual(m["idw"], 100, "the id column is wide enough for a full id")
                self.assertLessEqual(m["xw"], 261, "the owner and due cell is capped at 260px")
                self.assertLess(m["h"], 48)

    def test_a_work_item_row_opens_its_peek_beside_the_page_row_859(self):
        data = self.read("TUL")
        item = sorted(r["id"] for k in ("actions", "raid", "decisions") for r in data[k] if r.get("use_case") == UC)[0]
        for edit in (False, True):
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    with self.subTest(edit=edit, width=width, scheme=scheme), chrome() as cdp:
                        sid = self.open_detail(cdp, width, scheme, edit=edit)
                        self.assertEqual(cdp.js(f"document.querySelector('[data-item={item}]').title", sid), "", "the row no longer promises the Work items page")
                        self.peek_round(cdp, sid, f"[data-item={item}]", item)

    def test_a_linked_milestone_opens_its_peek_and_shows_its_state_row_860(self):
        ms = "TUL-M-005"
        words = ["Achieved", "On track", "At risk", "Slipped", "Overdue", "Forecast", "Cancelled"]       # the Milestones page's own state words
        for edit in (False, True):
            for width in (1400, 900):
                for scheme in ("light", "dark"):
                    with self.subTest(edit=edit, width=width, scheme=scheme), chrome() as cdp:
                        sid = self.open_detail(cdp, width, scheme, edit=edit)
                        row = f"[data-ucd] [data-ms={ms}]"
                        self.assertIn(cdp.js(f"document.querySelector('{row} [data-ms-state]').textContent.trim()", sid), words, "the row says the state in a word")
                        self.assertTrue(cdp.js(f"!!document.querySelector('{row} [data-ms-state] svg')", sid), "with the Milestones page's mark")
                        self.assertRegex(cdp.js(f"document.querySelector('{row}').textContent", sid), r"\d", "and the date")
                        self.assertEqual(cdp.js(f"document.querySelector('{row} [data-ms-open]').tagName", sid), "BUTTON", "the name is a control")
                        self.peek_round(cdp, sid, f"{row} [data-ms-open]", ms)

    # ---- row 1141: ONE "Add a milestone" (a direct link); the next-step-creating one and the work-item Remove are gone ----
    def ms_ids(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('[data-ucd] [data-ms]')].map(e => e.dataset.ms).sort()", sid)

    def direct(self):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return [l["milestone"] for l in st.data_for("TUL")["uc_milestones"] if l["use_case"] == UC]
        finally:
            st.close()

    def test_one_add_a_milestone_button_and_no_remove_on_a_work_item_milestone_row_1141(self):
        for width in (1400, 915):          # 915 px of window is 900 px of page on this box (15 px scrollbar)
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.open_detail(cdp, width=width, scheme=scheme, edit=False)
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms-link]').length", sid), 1, "one Add a milestone control")
                    self.assertEqual(cdp.js("document.querySelector('[data-ucd] [data-ms-link] button').textContent.trim()", sid), "Add a milestone")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms-add], [data-ucd] [data-ms-remove]').length", sid), 0, "the old Add and Remove are gone")
                    self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms] [data-ms-unlink]').length", sid), 0, "a milestone only through work items is not offered a removal")
                    self.assertEqual(self.ms_ids(cdp, sid), ["TUL-M-005"], "the work item's milestone still shows")
                    for w, h in cdp.js("[...document.querySelectorAll('[data-ucd] [data-ms-link] button')].map(e => { const b = e.getBoundingClientRect(); return [b.width, b.height]; })", sid):
                        self.assertGreaterEqual(min(w, h), 24, "a control is at least 24 px")
                    self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - document.documentElement.clientWidth", sid), 0, "no sideways scroll")

    def test_add_a_milestone_links_it_directly_in_one_change_with_one_undo_row_1141(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            before = self.steps()
            actions_before = len(self.read("TUL")["actions"])
            click(cdp, sid, "[data-ucd] [data-ms-link] button")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "the menu of milestones opened")
            self.assertEqual(cdp.js("document.querySelectorAll('[role=menu] [role^=menuitem]').length", sid), 6, "every milestone it has no direct link to")
            click(cdp, sid, "[role=menu] [data-kind='TUL-M-002']")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-ms=TUL-M-002]')", "the milestone is listed")
            self.assertEqual(self.steps(), before + 1, "one step")
            self.assertEqual(self.direct(), ["TUL-M-002"])
            self.assertEqual(len(self.read("TUL")["actions"]), actions_before, "no next step is made")
            self.assertIn("Pilot office live", self.toast(cdp, sid))
            self.undo(cdp, sid)
            self.until(cdp, sid, "!document.querySelector('[data-ucd] [data-ms=TUL-M-002]')", "the undo took it away")
            self.assertEqual(self.direct(), [])

    def test_unlink_ends_only_the_direct_link_and_leaves_the_work_items_row_1141(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            click(cdp, sid, "[data-ucd] [data-ms-link] button")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "menu")
            click(cdp, sid, "[role=menu] [data-kind='TUL-M-005']")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-ms=TUL-M-005][data-how=both]')", "now both")
            linked = [r["id"] for k in ("actions", "raid") for r in self.read("TUL")[k] if r.get("use_case") == UC and r.get("milestone") == "TUL-M-005"]
            click(cdp, sid, "[data-ucd] [data-ms=TUL-M-005] [data-ms-unlink]")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-ms=TUL-M-005][data-how=work]')", "back to through work items only")
            self.assertEqual(self.direct(), [])
            self.assertEqual([r["id"] for k in ("actions", "raid") for r in self.read("TUL")[k] if r.get("use_case") == UC and r.get("milestone") == "TUL-M-005"], linked, "the work items are not touched")

    def test_no_milestone_controls_when_archived_or_in_the_file_row_1141(self):
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            click(cdp, sid, "[data-ucd] [data-archive]")
            self.until(cdp, sid, "!!document.querySelector('[data-restore]')", "archived")
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] [data-ms-link], [data-ucd] [data-ms-unlink]').length", sid), 0)
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        for word in ("data-ms-link", "data-ms-unlink", "data-ms-add", "data-ms-remove"):
            self.assertNotIn(word, view, word)

    def sql(self, q, args=()):
        st = open_store(self.path, onedrive_roots=[])
        try:
            st.con.execute(q, args)
            st.con.commit()
        finally:
            st.close()

    def test_hostile_milestone_name_is_text_only_in_the_menu_and_the_row_row_1141(self):
        evil = "<img src=x onerror=window.__pwn=1>\u202e\U0001F600 " + "W" * 600
        self.sql("UPDATE milestones SET name = ? WHERE id = 'TUL-M-002'", (evil,))
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            click(cdp, sid, "[data-ucd] [data-ms-link] button")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "menu")
            self.assertEqual(cdp.js("document.querySelectorAll('[role=menu] img').length", sid), 0, "the name is text in the menu")
            click(cdp, sid, "[role=menu] [data-kind='TUL-M-002']")
            self.until(cdp, sid, "!!document.querySelector('[data-ucd] [data-ms=TUL-M-002]')", "listed; toast: " + self.toast(cdp, sid))
            self.assertEqual(cdp.js("document.querySelectorAll('[data-ucd] img').length + (window.__pwn ? 1 : 0)", sid), 0, "nothing ran")
            self.assertLessEqual(cdp.js("document.documentElement.scrollWidth - document.documentElement.clientWidth", sid), 0, "a huge name causes no sideways scroll")
        self.assertEqual(self.direct(), ["TUL-M-002"])

    def test_an_archived_milestone_is_neither_listed_nor_offered_row_1141(self):
        self.sql("UPDATE milestones SET archived = 1 WHERE id IN ('TUL-M-005', 'TUL-M-003')")
        with chrome() as cdp:
            sid = self.open_detail(cdp, edit=False)
            self.assertEqual(self.ms_ids(cdp, sid), [])
            click(cdp, sid, "[data-ucd] [data-ms-link] button")
            self.until(cdp, sid, "!!document.querySelector('[role=menu]')", "menu")
            ids = cdp.js("[...document.querySelectorAll('[role=menu] [data-kind]')].map(e => e.dataset.kind)", sid)
            self.assertNotIn("TUL-M-003", ids)
            self.assertNotIn("TUL-M-005", ids)

    def test_the_old_next_step_adder_is_gone_from_the_source_row_1141(self):
        text = (PAGE_SRC / "edit" / "UseCasesEdit.jsx").read_text(encoding="utf-8") + (PAGE_SRC / "components" / "UseCaseDetail.jsx").read_text(encoding="utf-8")
        for word in ("MilestoneAdd", "MilestoneRemove", "data-ms-add", "data-ms-remove", "Link a milestone"):
            self.assertNotIn(word, text, word)

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
