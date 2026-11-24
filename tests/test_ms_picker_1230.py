"""Row 1230, picker PR: the Add a milestone box is a table with an On the page filter; Where it is has two values; no Show all link.

Run: python3 dev/run_tests.py -j 1 test_ms_picker_1230   (headless Chrome; fails, never skips, without it)
Fictional data over a real store; "today" is 2026-10-28. Widths 1400 and 900 only; no keyboard walk-through.
"""
import tempfile
import unittest
from unittest import mock

from _demo import USER, DemoStore

from clark import changes, page, server as sv
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, page_target

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
HEADS = ["Milestone", "State", "Agreed", "Expected or achieved", "Progress", "Where it is", "ID"]
EYE, NOT_ON = "Taken off with the eye", "Not on the page"

READ = """(() => {
  const box = document.querySelector('form.ms-pk');
  if (!box) return null;
  const r = box.getBoundingClientRect(), vis = (e) => !!e && e.getBoundingClientRect().width > 0;
  const rows = [...box.querySelectorAll('tbody tr')].map((tr) => [...tr.children].slice(1).map((c) => c.textContent.trim()));
  return {w: Math.round(r.width), h: Math.round(r.height), heads: [...box.querySelectorAll('thead th')].slice(1).map((t) => t.textContent.trim()), rows,
          why: [...box.querySelectorAll('tbody .why')].map((e) => e.textContent.trim()), foot: box.querySelector('.pk-count').textContent.trim(),
          add: box.querySelector('[type=submit]').textContent.trim(), noScroll: document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
          inside: r.left >= 0 && r.right <= document.documentElement.clientWidth, panel: vis(box.querySelector('.fpan')), badge: (box.querySelector('.ficon i') || {}).textContent || null,
          showAll: !!document.querySelector('.msl-all, [data-msall]')};
})()"""


class Picker(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        with self.store.step("dashboard", USER) as st:
            for i in range(1, 9):
                st.create("milestones", {"project": "ABC", "name": f"T{i}", "baseline_date": f"2030-0{i}-01", "source": "demo"})
            st.update("milestones", "ABC-M-005", {"client_visible": 0})
        self.hide("ABC-M-003", "ABC-M-004")
        self.sent = []
        real = changes.make_change(self.store.path, [], USER)

        def seam(req):
            self.sent.append(req)
            return real(req)
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING), change=seam,
                         undo=changes.make_undo(self.store.path, [], USER))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def hide(self, *ids):
        for i in ids:
            status, body = changes.make_change(self.store.path, [], USER)({"project": "ABC", "kind": "report_hidden", "op": "new", "id": i})
            self.assertEqual(status, 200, body)

    def open(self, cdp, width):
        self.cdp = cdp
        self.sid = page_target(cdp)
        cdp.call("Page.enable", {}, self.sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, self.sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, self.sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#dashboard&p=ABC"}, self.sid)
        self.until("!!document.querySelector('.msv .msl-row')", "the list drew")
        self.js("document.querySelector('[data-mode=edit]').click()")
        self.until("!!document.querySelector('.secs [data-ms-back]')", "the add line is there")
        self.until("document.getAnimations().length === 0", "animations ended")
        return self.sid

    def js(self, e):
        return self.cdp.js(e, self.sid)

    def until(self, e, what):
        self.assertTrue(wait(lambda: self.js(e), 10), what)

    def launch(self):
        self.js("document.querySelector('.secs [data-ms-back]').click()")
        self.until("!!document.querySelector('form.ms-pk tbody tr')", "the table drew")
        self.until("document.getAnimations().length === 0", "animations ended")
        return self.js(READ)

    def test_a_table_with_seven_columns_and_two_where_it_is_values_at_both_widths(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.open(cdp, width)
                self.assertEqual(self.js("document.querySelector('.secs [data-ms-back]').textContent.trim()"), "+ Add a milestone from your project record (3)")
                got = self.launch()
                self.assertEqual(got["heads"], HEADS)
                self.assertEqual(sorted(set(got["why"])), sorted([EYE, NOT_ON]), "two values, no others")
                self.assertEqual([r[0] for r in got["rows"]], ["T2", "T3", "T4"])
                self.assertEqual([r[-1] for r in got["rows"]], ["ABC-M-003", "ABC-M-004", "ABC-M-005"], "the ID column")
                self.assertEqual(got["why"], [EYE, EYE, NOT_ON])
                self.assertEqual(got["foot"], "None selected")
                self.assertTrue(got["noScroll"] and got["inside"], "no sideways scroll")
                self.assertEqual(got["w"], 1080 if width == 1400 else got["w"], "1080 wide when there is room")
                self.assertLessEqual(got["w"], width)
                self.assertGreaterEqual(got["h"], 650 - 1, "650 tall at least")

    def test_the_on_the_page_filter_has_two_values_with_counts_and_narrows_the_table(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                self.open(cdp, width)
                self.launch()
                self.js("document.querySelector('form.ms-pk [data-pkp]').click()")
                self.until("!!document.querySelector('form.ms-pk .fpan')", "the panel opened")
                self.js("[...document.querySelectorAll('form.ms-pk .frow')].find((b) => b.textContent.startsWith('On the page')).click()")
                self.assertEqual(self.js("[...document.querySelectorAll('form.ms-pk .fopts label')].map((l) => l.textContent.trim())"), [NOT_ON + "1", EYE + "2"])
                self.js("document.querySelector(\"form.ms-pk [data-pkv='%s']\").click()" % NOT_ON)
                self.until("document.querySelectorAll('form.ms-pk tbody tr').length === 1", "the table narrowed")
                self.assertEqual(self.js("document.querySelector('form.ms-pk .fres span').textContent"), "Result: 1 of 3 shown")
                self.js("document.querySelector('form.ms-pk [data-pkd]').click()")
                got = self.js(READ)
                self.assertFalse(got["panel"], "Done closed the panel only")
                self.assertEqual(got["badge"], "1")
                self.assertEqual([r[0] for r in got["rows"]], ["T4"])

    def test_the_header_tick_and_add_bring_them_back_in_one_change(self):
        with chrome() as cdp:
            self.open(cdp, 1400)
            self.launch()
            self.js("document.querySelector('form.ms-pk [data-pksa]').click()")
            self.until("document.querySelector('form.ms-pk .pk-count').textContent === '3 selected'", "all three ticked")
            self.assertEqual(self.js("document.querySelector('form.ms-pk [type=submit]').textContent.trim()"), "Add 3")
            self.js("document.querySelector('form.ms-pk [type=submit]').click()")
            self.until("!document.querySelector('form.ms-pk')", "the box closed")
            self.assertEqual(self.sent[-1], {"project": "ABC", "kind": "report_hidden", "op": "pick", "ids": ["ABC-M-003", "ABC-M-004", "ABC-M-005"], "place": "report"})
            self.until("!!document.querySelector('.toast .toast-text')", "the toast")
            self.assertEqual(self.js("document.querySelector('.toast .toast-text').textContent"), "3 milestones added to the page.")
            self.assertEqual(self.js("document.querySelectorAll('.toast [data-undo]').length"), 1, "one Undo")
    def test_row_click_header_states_is_not_and_the_empty_progress(self):
        with chrome() as cdp:
            self.open(cdp, 1400)
            got = self.launch()
            self.assertEqual([r[4] for r in got["rows"]], ["—", "—", "—"], "no percent is a dash")
            self.assertEqual(self.js("document.querySelector('form.ms-pk [type=submit]').disabled"), True, "Add is off with nothing ticked")
            state = "(() => { const b = document.querySelector('form.ms-pk'); const h = b.querySelector('[data-pksa]'); return [b.querySelector('.pk-count').textContent.trim(), h.checked, h.indeterminate, b.querySelector('[type=submit]').disabled]; })()"
            self.js("document.querySelector('form.ms-pk tbody tr td.nm').click()")
            self.until("document.querySelector('form.ms-pk .pk-count').textContent === '1 selected'", "a click on the row ticked it")
            self.assertEqual(self.js(state), ["1 selected", False, True, False], "some ticked: header is mixed, not checked, Add is on")
            self.js("document.querySelector('form.ms-pk tbody tr input[type=checkbox]').click()")
            self.until("document.querySelector('form.ms-pk .pk-count').textContent === 'None selected'", "the tick itself toggled once, not twice")
            self.js("document.querySelector('form.ms-pk [data-pksa]').click()")
            self.until("document.querySelector('form.ms-pk .pk-count').textContent === '3 selected'", "header ticked all")
            self.assertEqual(self.js(state), ["3 selected", True, False, False])
            self.js("document.querySelector('form.ms-pk [data-pkp]').click()")
            self.until("!!document.querySelector('form.ms-pk .fpan')", "the panel opened")
            self.js("[...document.querySelectorAll('form.ms-pk .frow')].find((b) => b.textContent.startsWith('On the page')).click()")
            self.js("document.querySelector('form.ms-pk [data-pkn=\"1\"]').click()")
            self.js("document.querySelector(\"form.ms-pk [data-pkv='%s']\").click()" % NOT_ON)
            self.until("document.querySelectorAll('form.ms-pk tbody tr').length === 2", "is not hides the Not on the page row")
            self.assertEqual([self.js("document.querySelector('form.ms-pk [data-pkn=\"1\"]').getAttribute('aria-pressed')")], ["true"])
            self.js("document.querySelector('form.ms-pk [data-pksa]').click()")
            self.until("document.querySelector('form.ms-pk .pk-count').textContent === '1 selected'", "header untick drops only the shown rows")
            self.js("[...document.querySelectorAll('form.ms-pk .frow')].find((b) => b.textContent.startsWith('Status')).click()")
            self.assertEqual(self.js("[...document.querySelectorAll('form.ms-pk .fopts input')].filter((i) => i.disabled).length"), 6, "values with no rows are off")
            self.js("document.querySelector('form.ms-pk [data-pkp]').click()")
            self.until("!document.querySelector('form.ms-pk .fpan')", "the filter button closes the panel when open")

    def test_no_show_all_link_with_more_than_five_rows(self):
        for edit in (False, True):
            with self.subTest(edit=edit), chrome() as cdp:
                self.open(cdp, 1400)
                if not edit:
                    self.js("document.querySelector('[data-mode=view]').click()")
                self.until("document.querySelectorAll('.secs .msl-row').length >= 6", "all six on the page are listed")
                self.assertFalse(self.js("!!document.querySelector('.msl-all, [data-msall]')"))
                self.assertNotIn("Show all", self.js("document.querySelector('.secs .msv').textContent"))

    def test_esc_closes_with_no_change(self):
        with chrome() as cdp:
            self.open(cdp, 1400)
            self.launch()
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, self.sid)
            self.until("!document.querySelector('form.ms-pk')", "Esc closed it")
            self.assertEqual([r for r in self.sent if r.get("op") == "pick"], [])


if __name__ == "__main__":
    unittest.main()
