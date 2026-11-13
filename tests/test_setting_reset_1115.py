"""Row 1115, S4: a changed dot and a Reset button on each setting row whose setting is not at its default, and one list of defaults
(src/clark/page/src/edit/settingsDefaults.json). Run: python3 dev/run_tests.py test_setting_reset_1115

The source checks need no browser: every row that offers Reset has an entry with a written reason, and the defaults match the code's own.
The page checks mount the Settings cards on the Gantt test page (tests/fixtures/gantt_tab_demo.jsx) at 1400 and 900 px: a row at its
default shows neither dot nor Reset; a changed row shows both; Reset sends the default as one change with Undo, and the row goes quiet.
Chrome is required for the page checks: they fail, never skip, without it."""
import json
import re
import unittest

import test_gantt_tab as T
from _demo import USER, DemoStore
from clark import changes

DEFAULTS = json.loads(T.read("edit", "settingsDefaults.json"))
ROWS = ("review-days", "gantt-editor", "gantt-client", "gantt-name")


class Source(unittest.TestCase):
    def test_every_row_that_offers_reset_has_a_default_and_a_reason(self):
        used = set()
        for f in ("ReviewDays.jsx", "GanttSetting.jsx"):
            used |= set(re.findall(r'defaultOf\("([a-z-]+)"\)', T.read("edit", f)))
        self.assertEqual(used, set(ROWS), "the cards ask for exactly these defaults")
        for id in used:
            self.assertIn(id, DEFAULTS, id + " has an entry")
            self.assertGreater(len(DEFAULTS[id]["why"].split()), 5, id + " has a written reason")
        self.assertEqual(set(DEFAULTS), used, "no entry is left without a row")

    def test_the_defaults_are_the_ones_the_code_uses(self):
        self.assertEqual(DEFAULTS["review-days"]["value"], int(re.search(r"REVIEW_DAYS = (\d+)", T.read("filters.js")).group(1)))
        self.assertEqual(DEFAULTS["gantt-name"]["value"], re.search(r'DEFAULT_NAME = "([^"]+)"', T.read("gantt", "ganttTab.js")).group(1))
        self.assertEqual((DEFAULTS["gantt-editor"]["value"], DEFAULTS["gantt-client"]["value"]), (False, False))

    def test_reset_is_drawn_only_for_a_changed_row(self):
        s = T.read("edit", "SettingRow.jsx")
        self.assertIn("changed && onReset", s)


class Reset(unittest.TestCase):
    setUpClass = classmethod(T.Tab.setUpClass.__func__)
    tearDownClass = classmethod(T.Tab.tearDownClass.__func__)
    load, js, go = T.Tab.load, T.Tab.js, T.Tab.go

    def row(self, id):
        return self.js("(() => { const r = document.getElementById('%s').closest('.set-row');"
                       " return {dot: !!r.querySelector('.set-dot'), reset: !!r.querySelector('.set-reset'),"
                       " resetBeforeControl: !!r.querySelector('.set-reset') && !!(r.querySelector('.set-reset').compareDocumentPosition(document.getElementById('%s')) & 4)}; })()" % (id, id))

    def test_rows_at_their_default_show_neither_dot_nor_reset(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                self.load(edit=True, width=w)
                self.go("location.hash = '#settings&p=DEMO'")
                for id in ROWS:
                    self.assertEqual((self.row(id)["dot"], self.row(id)["reset"]), (False, False), id)

    def test_a_changed_row_shows_a_dot_and_reset_and_reset_puts_the_default_back_with_undo(self):
        changed = {"review_after_days": 30, "show_gantt_editor": 1, "show_gantt_client": 1, "gantt_tab_name": "Plan"}
        for w in (1400, 900):
            with self.subTest(width=w):
                self.load(changed, edit=True, width=w)
                self.go("location.hash = '#settings&p=DEMO'")
                for id in ROWS:
                    r = self.row(id)
                    self.assertTrue(r["dot"] and r["reset"] and r["resetBeforeControl"], id)
                self.assertEqual(self.js("document.querySelector('.set-dot').getAttribute('aria-label')"), "Changed from the default")
                for i, id in enumerate(ROWS):
                    self.go("document.getElementById('%s').closest('.set-row').querySelector('.set-reset').click()" % id)
                    self.assertEqual((self.row(id)["dot"], self.row(id)["reset"]), (False, False), id + " is quiet after Reset")
                sent = json.loads(self.js("JSON.stringify(G.sent.map(s => s.changes))"))
                self.assertEqual(sent, [{"review_after_days": 14}, {"show_gantt_editor": 0}, {"show_gantt_client": 0}, {"gantt_tab_name": "Gantt"}])
                self.assertIn("Undo", self.js("document.body.innerText"), "each Reset is a change with Undo")

    def test_the_dot_and_reset_fit_inside_the_row_at_1400_and_900(self):
        for w in (1400, 900):
            with self.subTest(width=w):
                self.load({"gantt_tab_name": "A tab name that is nearly thirty"}, edit=True, width=w)
                self.go("location.hash = '#settings&p=DEMO'")
                ok = self.js("(() => { const r = document.getElementById('gantt-name').closest('.set-row'), b = r.getBoundingClientRect();"
                             " return [...r.querySelectorAll('.set-reset, input, .set-dot')].every(e => { const k = e.getBoundingClientRect(); return k.left >= b.left - 1 && k.right <= b.right + 1; })"
                             " && document.documentElement.scrollWidth <= innerWidth; })()")
                self.assertTrue(ok)

    def focused(self):
        return self.js("document.activeElement && (document.activeElement.id || document.activeElement.tagName)")

    def test_after_reset_and_after_undo_the_focus_is_on_the_rows_own_control(self):
        changed = {"review_after_days": 30, "show_gantt_editor": 1, "show_gantt_client": 1, "gantt_tab_name": "Plan"}
        for w in (1400, 900):
            for id in ROWS:
                with self.subTest(width=w, row=id):
                    self.load(changed, edit=True, width=w)
                    self.go("location.hash = '#settings&p=DEMO'")
                    self.go("document.getElementById('%s').closest('.set-row').querySelector('.set-reset').focus()" % id)
                    self.go("document.activeElement.click()")
                    self.assertEqual(self.focused(), id, "after Reset")
                    self.go("document.querySelector('[data-undo]').focus(); document.querySelector('[data-undo]').click()")
                    self.assertEqual(self.js("G.undone.length"), 1, "the toast's Undo was used")
                    self.assertEqual(self.focused(), id, "after Undo")
                    self.assertTrue(self.row(id)["reset"], "the row is changed again after Undo")

    def test_reset_clears_the_typed_value_and_the_refusal_line(self):
        for w in (1400, 900):
            for id, bad, typed in (("review-days", "data-review-days-bad", "0"), ("gantt-name", "data-gantt-name-bad", "")):
                with self.subTest(width=w, row=id):
                    self.load({"review_after_days": 30, "gantt_tab_name": "Plan"}, edit=True, width=w)
                    self.go("location.hash = '#settings&p=DEMO'")
                    self.go("var b = document.getElementById('%s'); b.focus(); b.value = %s; b.dispatchEvent(new Event('input', {bubbles: true}))" % (id, json.dumps(typed)))
                    self.go("document.getElementById('%s').blur()" % id)
                    self.assertTrue(self.js("document.querySelector('[%s]').textContent.length > 0" % bad), "the refusal line is shown")
                    self.go("document.getElementById('%s').closest('.set-row').querySelector('.set-reset').click()" % id)
                    self.assertEqual(self.js("document.querySelector('[%s]').textContent" % bad), "", "the refusal line is gone")
                    self.assertEqual(self.js("document.getElementById('%s').value" % id), "14" if id == "review-days" else "Gantt")
                    self.assertIsNone(self.js("document.getElementById('%s').getAttribute('aria-invalid')" % id))

    def test_reset_drops_a_half_typed_value(self):
        self.load({"gantt_tab_name": "Plan"}, edit=True)
        self.go("location.hash = '#settings&p=DEMO'")
        self.go("var b = document.getElementById('gantt-name'); b.value = 'Half'; b.dispatchEvent(new Event('input', {bubbles: true}))")
        self.go("document.getElementById('gantt-name').closest('.set-row').querySelector('.set-reset').click()")
        self.assertEqual(self.js("document.getElementById('gantt-name').value"), "Gantt")


class StoreUndo(unittest.TestCase):
    """The four Resets are ordinary project changes: each one is a step, and its Undo puts the changed value back."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.path = self.demo.store.path
        self.change = changes.make_change(self.path, [], USER)
        self.undo = changes.make_undo(self.path, [], USER)

    def value(self, field):
        return self.demo.store.con.execute("SELECT %s FROM projects WHERE code = 'ABC'" % field).fetchone()[0]

    def test_each_reset_has_one_undo_that_puts_the_changed_value_back(self):
        cases = (("review_after_days", 30, 14), ("show_gantt_editor", 1, 0), ("show_gantt_client", 1, 0), ("gantt_tab_name", "Plan", "Gantt"))
        for field, was, default in cases:
            with self.subTest(field=field):
                self.assertEqual(self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {field: was}})[0], 200)
                status, got = self.change({"project": "ABC", "kind": "projects", "op": "update", "changes": {field: default}, "place": "menu"})
                self.assertEqual((status, got.get("ok")), (200, True), got)
                self.assertEqual(self.value(field), default, "Reset sends the default")
                self.assertTrue(got.get("apply_id"), "Reset is one step")
                status, back = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
                self.assertEqual((status, back.get("ok")), (200, True), back)
                self.assertEqual(self.value(field), was, "Undo puts the changed value back")


if __name__ == "__main__":
    unittest.main()
