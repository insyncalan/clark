"""The eye on each row of the Milestones list (Edit only): leave a milestone out of the published page, or put it back.

Run: python3 dev/run_tests.py -j 1 test_milestones_eye
The page runs from the real server over a real store (fictional data) in headless Chrome (required: it fails, never skips,
without Chrome). The eye sends the page's one change, kind report_hidden, through the real change and undo routes, so what the
page draws after a press is what clark saved. It is the same list on the Dashboard and on the Milestones page. View and a published
file have no eye and no mark, and a published file does not hold a left-out milestone at all. Laptop widths only: 1400 and 900 px,
light and dark.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER, DemoStore

from clark import changes, page, publish, server as sv
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")        # so a brand on this laptop never changes a test
LEFT_OUT = "Left out of the published page"
NAMES = {"ABC-M-001": "Pilot live", "ABC-M-002": "Training done", "ABC-M-003": "Handover"}

# What a person sees on each row: the eye's name and state, its size and place, the words that mark a left-out row and, for the
# eye's icon, how it reads against what is behind it (colours go through a canvas so any colour syntax is read as plain sRGB).
SEE = """((root) => {
  const px = (c) => { const k = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); k.clearRect(0, 0, 1, 1); k.fillStyle = c; k.fillRect(0, 0, 1, 1); return [...k.getImageData(0, 0, 1, 1).data]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const back = (e) => { for (; e; e = e.parentElement) { const c = px(getComputedStyle(e).backgroundColor); if (c[3] === 255) return c; } return [255, 255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const box = root.querySelector('.msv');
  if (!box) return null;
  const rows = [...box.querySelectorAll('.msl-row')].map((r) => {
    const eye = r.querySelector('button[data-ms-eye]'), cells = r.querySelector('.msl-cells'), tag = r.querySelector('.tag.hid');
    const rr = r.getBoundingClientRect(), out = {id: r.dataset.ms, hasEye: !!eye, tag: tag ? tag.textContent.trim() : null,
                                                  tagShown: !!tag && tag.getBoundingClientRect().width > 0, listItem: r.tagName === 'LI'};
    if (eye) {
      const er = eye.getBoundingClientRect(), cr = cells.getBoundingClientRect();
      Object.assign(out, {name: eye.getAttribute('aria-label'), pressed: eye.classList.contains('is-left') ? 'true' : 'false', ariaPressed: eye.getAttribute('aria-pressed'), tag2: eye.tagName, type: eye.type,
                          w: er.width, h: er.height, inside: er.left >= rr.left - 1 && er.right <= rr.right + 1 && er.top >= rr.top - 1 && er.bottom <= rr.bottom + 1,
                          apart: er.left >= cr.right - 1, tabStop: eye.tabIndex >= 0, inCells: cells.contains(eye), icon: eye.querySelector('svg').getAttribute('data-icn'),
                          ink: ratio(px(getComputedStyle(eye).color), back(eye))});
    }
    return out;
  });
  return {place: box.dataset.place, rows, noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1};
})(document.querySelector('%s'))"""


def eye_name(left, name):
    return f"{'Include in' if left else 'Leave out of'} the published page: {name}"


class Editor(unittest.TestCase):
    """The page clark serves, with Edit, over project ABC with three milestones."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            st.create("milestones", {"project": "ABC", "name": NAMES["ABC-M-002"], "baseline_date": "2030-04-01", "source": "demo"})
            st.create("milestones", {"project": "ABC", "name": NAMES["ABC-M-003"], "baseline_date": "2030-05-01", "source": "demo"})
        self.sent = []
        real_change = changes.make_change(self.store.path, [], USER)
        real_undo = changes.make_undo(self.store.path, [], USER)

        def seam(real, which):
            def call(req):
                self.sent.append((which, req))
                return real(req)
            return call
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING),
                         change=seam(real_change, "change"), undo=seam(real_undo, "undo"))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    # ---- helpers ----
    def visit(self, cdp, hash_="#dashboard&p=ABC", width=1400, theme=None, edit=True):
        self.cdp = cdp
        self.sid = page_target(cdp)
        cdp.call("Page.enable", {}, self.sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, self.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, self.sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{hash_}"}, self.sid)
        self.until("!!document.querySelector('.msv .msl-row')", "the list drew its rows")
        if edit:
            self.js("document.querySelector('[data-mode=edit]').click()")
            self.until("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed') === 'true'", "Edit is on")
        if theme:
            self.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        return self.sid

    def js(self, expr):
        return self.cdp.js(expr, self.sid)

    def until(self, expr, what, seconds=10):
        self.assertTrue(wait(lambda: self.js(expr), seconds), what)

    def key(self, key, code, vk, text=""):
        for kind in ("keyDown", "keyUp"):
            args = {"type": kind, "key": key, "code": code, "windowsVirtualKeyCode": vk}
            if text and kind == "keyDown":
                args["text"] = text
            self.cdp.call("Input.dispatchKeyEvent", args, self.sid)

    def seen(self, root):
        return {r["id"]: r for r in self.js(SEE % root)["rows"]}

    def left_out(self):
        return self.store.data_for("ABC")["report_hidden"]

    def eye(self, ident, place):
        return f".msv[data-place{'=page' if place == 'page' else '^=sec-'}] .msl-row[data-ms='{ident}'] button[data-ms-eye]"

    def press(self, ident, place="dash"):
        self.js(f"document.querySelector({json.dumps(self.eye(ident, place))}).click()")

    def sent_changes(self):
        return [r for w, r in self.sent if w == "change"]

    # ---- every row has the eye ----
    def check_every_row(self, seen, label):
        self.assertEqual(sorted(seen), sorted(NAMES), label)
        for ident, r in seen.items():
            self.assertTrue(r["hasEye"], f"{label} {ident}: a button on the row")
            self.assertEqual((r["tag2"], r["type"]), ("BUTTON", "button"), f"{label} {ident}: a real button")
            self.assertEqual(r["name"], eye_name(False, NAMES[ident]), f"{label} {ident}: it names what it does and the milestone")
            self.assertEqual(r["pressed"], "false", f"{label} {ident}: not marked until the milestone is left out")
            self.assertIsNone(r["ariaPressed"], f"{label} {ident}: the name changes, so there is no aria-pressed to say it twice")
            self.assertGreaterEqual(min(r["w"], r["h"]), 24, f"{label} {ident}: a target of 24 px at least")
            self.assertTrue(r["inside"] and r["apart"], f"{label} {ident}: inside its row, beside the cells")
            self.assertFalse(r["inCells"], f"{label} {ident}: not a control inside another control")
            self.assertTrue(r["tabStop"] and r["listItem"], f"{label} {ident}: a tab stop of its own, in a list item")
            self.assertGreaterEqual(r["ink"], 3, f"{label} {ident}: the icon reads against the row at 3:1")
            self.assertIsNone(r["tag"], f"{label} {ident}: nothing is left out yet")

    def test_the_dashboard_block_and_the_milestones_page_have_an_eye_on_every_row_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme):
                    with chrome() as cdp:
                        self.visit(cdp, width=width, theme=theme)
                        got = self.js(SEE % ".secs")
                        self.assertTrue(got["place"].startswith("sec-"), "this is the Dashboard's own block")
                        self.check_every_row({r["id"]: r for r in got["rows"]}, f"{width}/{theme} dashboard")
                        self.assertTrue(got["noScroll"])
                    with chrome() as cdp:
                        self.visit(cdp, "#milestones&p=ABC", width=width, theme=theme)
                        got = self.js(SEE % ".frame")
                        self.assertEqual(got["place"], "page")
                        self.check_every_row({r["id"]: r for r in got["rows"]}, f"{width}/{theme} page")
                        self.assertTrue(got["noScroll"])

    def test_a_left_out_row_says_so_in_words_and_shows_the_eye_pressed_at_both_widths_in_both_themes(self):
        self.store_hide("ABC-M-002")
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    self.visit(cdp, width=width, theme=theme)
                    got = self.js(SEE % ".secs")
                    by = {r["id"]: r for r in got["rows"]}
                    r = by["ABC-M-002"]
                    self.assertEqual((r["tag"], r["tagShown"]), (LEFT_OUT, True), "the words, not colour alone")
                    self.assertEqual((r["pressed"], r["icon"], r["name"]), ("true", "eyeoff", eye_name(True, "Training done")))
                    self.assertIsNone(r["ariaPressed"], "the name says it; aria-pressed would say it twice")
                    self.assertGreaterEqual(r["ink"], 3)
                    for other in ("ABC-M-001", "ABC-M-003"):
                        self.assertEqual((by[other]["tag"], by[other]["pressed"], by[other]["icon"]), (None, "false", "eye"), other)
                    self.assertTrue(got["noScroll"])
                    self.assertTrue(r["inside"] and r["apart"])

    def store_hide(self, ident):
        status, body = changes.make_change(self.store.path, [], USER)({"project": "ABC", "kind": "report_hidden", "op": "new", "id": ident})
        self.assertEqual(status, 200, body)

    # ---- the press: one change, one Undo, drawn at once ----
    def test_a_press_sends_one_change_and_one_undo_puts_it_back_on_the_dashboard(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.press("ABC-M-002")
            self.until(f"!!document.querySelector(\"[data-ms='ABC-M-002'] .tag.hid\")", "the row says it is left out")
            self.assertEqual(self.sent_changes(), [{"project": "ABC", "kind": "report_hidden", "op": "new", "id": "ABC-M-002", "place": "report"}])
            self.assertEqual(self.left_out(), ["ABC-M-002"])
            now = self.seen(".secs")["ABC-M-002"]
            self.assertEqual((now["tag"], now["pressed"], now["name"]), (LEFT_OUT, "true", eye_name(True, "Training done")))
            self.assertEqual(self.js("document.querySelector('.toast .toast-text').textContent"), "Training done left out of the published page.")
            self.assertEqual(self.js("document.querySelectorAll('.toast [data-undo]').length"), 1, "one Undo")
            self.js("document.querySelector('.toast [data-undo]').click()")
            self.until("!document.querySelector(\"[data-ms='ABC-M-002'] .tag.hid\")", "Undo put it back at once")
            self.assertEqual(self.left_out(), [])
            back = self.seen(".secs")["ABC-M-002"]
            self.assertEqual((back["tag"], back["pressed"], back["name"]), (None, "false", eye_name(False, "Training done")))
            self.assertEqual([w for w, _ in self.sent], ["change", "undo"], "one change and one undo, nothing more")

    def test_pressing_again_includes_it_and_that_has_its_own_undo(self):
        self.store_hide("ABC-M-003")
        with chrome() as cdp:
            self.visit(cdp, "#milestones&p=ABC")
            self.press("ABC-M-003", "page")
            self.until("!document.querySelector(\"[data-ms='ABC-M-003'] .tag.hid\")", "the row is included again")
            self.assertEqual(self.sent_changes(), [{"project": "ABC", "kind": "report_hidden", "op": "delete", "id": "ABC-M-003", "place": "report"}])
            self.assertEqual(self.left_out(), [])
            self.assertEqual(self.js("document.querySelector('.toast .toast-text').textContent"), "Handover included in the published page.")
            self.js("document.querySelector('.toast [data-undo]').click()")
            self.until("!!document.querySelector(\"[data-ms='ABC-M-003'] .tag.hid\")", "Undo left it out again")
            self.assertEqual(self.left_out(), ["ABC-M-003"])

    def test_the_state_is_there_again_after_a_reload(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.press("ABC-M-001")
            self.until("!!document.querySelector(\"[data-ms='ABC-M-001'] .tag.hid\")", "left out")
            self.visit(cdp)                                    # a fresh load of the page
            seen = self.seen(".secs")
            self.assertEqual([k for k, r in seen.items() if r["tag"] == LEFT_OUT], ["ABC-M-001"])
            self.assertEqual(seen["ABC-M-001"]["pressed"], "true")

    def test_the_dashboard_and_the_milestones_page_agree(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.press("ABC-M-002")
            self.until("!!document.querySelector(\"[data-ms='ABC-M-002'] .tag.hid\")", "left out")
            self.js("location.hash = '#milestones&p=ABC'")
            self.until("!!document.querySelector('.msv[data-place=page] .msl-row')", "the Milestones page drew")
            page_rows = self.seen(".frame")
            self.assertEqual([k for k, r in page_rows.items() if r["tag"] == LEFT_OUT], ["ABC-M-002"])
            self.assertEqual(page_rows["ABC-M-002"]["pressed"], "true")

    # ---- the keyboard ----
    def test_the_eye_is_a_tab_stop_after_its_row_and_enter_and_space_work_it(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.js("document.querySelector(\".msl-row[data-ms='ABC-M-002'] .msl-cells\").focus()")
            self.key("Tab", "Tab", 9)
            self.assertEqual(self.js("document.activeElement.dataset.msEye"), "ABC-M-002", "Tab from a row reaches its own eye")
            self.key("Enter", "Enter", 13, "\r")
            self.until("!!document.querySelector(\"[data-ms='ABC-M-002'] .tag.hid\")", "Enter left it out")
            self.assertEqual(self.js("document.activeElement.dataset.msEye"), "ABC-M-002", "focus stays on the eye")
            self.key(" ", "Space", 32, " ")
            self.until("!document.querySelector(\"[data-ms='ABC-M-002'] .tag.hid\")", "Space put it back")
            self.assertEqual(self.js("document.activeElement.dataset.msEye"), "ABC-M-002", "focus stays on the eye")
            self.assertEqual([r["op"] for r in self.sent_changes()], ["new", "delete"])

    def test_a_double_press_is_one_change(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.js(f"(() => {{ const b = document.querySelector({json.dumps(self.eye('ABC-M-001', 'dash'))}); b.click(); b.click(); }})()")
            self.until("!!document.querySelector(\"[data-ms='ABC-M-001'] .tag.hid\")", "left out")
            self.assertEqual(len(self.sent_changes()), 1, "the second press while the first was on its way was ignored")
            self.assertEqual(self.js("document.querySelectorAll('.toast.problem').length"), 0)

    def test_a_refused_change_says_why_and_draws_nothing_new(self):
        with chrome() as cdp:
            self.visit(cdp)
            self.store_hide("ABC-M-002")                       # hidden behind the page's back: the page still shows it as shown
            self.press("ABC-M-002")
            self.until("!!document.querySelector('.toast.problem, .toast.note')", "a plain line says it could not be done")
            self.assertEqual(self.left_out(), ["ABC-M-002"])

    # ---- View and the published file ----
    def test_view_has_no_eye_and_no_mark_even_for_a_left_out_milestone(self):
        self.store_hide("ABC-M-002")
        with chrome() as cdp:
            self.visit(cdp, edit=False)
            got = self.js(SEE % ".secs")
            self.assertTrue(got["rows"])
            self.assertTrue(all(not r["hasEye"] and r["tag"] is None for r in got["rows"]), got["rows"])
            self.assertEqual(self.js("document.querySelectorAll('[data-ms-eye]').length"), 0)
            self.js("document.querySelector('[data-mode=edit]').click()")
            self.until("!!document.querySelector('button[data-ms-eye]')", "the eye comes with Edit")
            self.js("document.querySelector('[data-mode=view]').click()")
            self.until("!document.querySelector('button[data-ms-eye]')", "and goes with it")
            self.assertEqual(self.js("document.querySelectorAll('.msl-row .tag.hid').length"), 0)

    def test_the_published_file_has_no_eye_no_mark_and_not_the_left_out_milestone(self):
        self.store_hide("ABC-M-002")
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        body = Path(done["path"]).read_text(encoding="utf-8")
        self.assertNotIn("ABC-M-002", body, "a left-out milestone is not in the file at all")
        self.assertNotIn("Training done", body)
        self.assertNotIn("data-ms-eye", body)
        self.assertNotIn("ms-eye", body, "the file holds none of the eye's code or style")
        block = re.search(r'<script type="application/json" id="clark-data">[^<]*</script>', body)
        self.assertIsNotNone(block, "the file's data block")
        self.assertNotIn("report_hidden", block.group(0), "the file's data holds no list of left-out rows")    # the page's own code may name it; the data must not
        with chrome() as cdp:
            self.cdp = cdp
            self.sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": "file://" + str(done["path"])}, self.sid)
            self.until("document.documentElement.dataset.ready === '1'", "the file drew")
            self.until("!!document.querySelector('.tab')", "the file's tabs")
            self.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()")
            self.until("!!document.querySelector('.msv .msl-row')", "the file's Milestones page drew its rows")
            got = self.js(SEE % "body")
            self.assertEqual(sorted(r["id"] for r in got["rows"]), ["ABC-M-001", "ABC-M-003"])
            self.assertTrue(all(not r["hasEye"] and r["tag"] is None for r in got["rows"]))
            self.assertEqual(self.js("document.querySelectorAll('button[data-ms-eye], .tag.hid').length"), 0)


if __name__ == "__main__":
    unittest.main()
