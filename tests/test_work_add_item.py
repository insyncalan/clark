"""Gap list B-8: the Add menu on Work items makes the item, opens it in the item panel and says "<ID> added" with Undo.

Run: python3 dev/run_tests.py test_work_add_item
The browser tests start headless Chrome through the harness against a real server whose change and undo are the real
clark.changes over a real store in a temporary folder (fictional data), at 1400 and 900 px. Chrome is required: these tests
fail, never skip, without it. Before this change every pick said it was coming later and nothing reached the store.
"""
import unittest

from clark import changes, publish
from test_report_editor import Base, Pg
from test_server import chrome

SIZES = (1400, 900)
KINDS = (("action", "actions", "description", "New action"), ("risk", "raid", "description", "New risk"),
         ("issue", "raid", "description", "New issue"), ("decision", "decisions", "decision", "New decision"))


class AddMenu(Base):
    def setUp(self):
        super().setUp()
        self.first = self.demo.action(workstream="Build", owner="Sam Example")

    def work(self, cdp, width):
        p = Pg.at(self, cdp, self.s.port, "#work&p=ABC&f=mode:all")
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until("document.querySelectorAll('#work tbody tr[data-id]').length >= 1", "the rows drew")
        p.js("window.clarkPage.closePeek(); document.querySelector('[data-mode=view]').click()")      # the same tab is reused: start in View
        p.until("document.querySelector('[data-mode=view]').getAttribute('aria-pressed') === 'true' && !window.clarkPage.peek()", "View, no panel open")
        return p

    def pick(self, p, kind):
        p.js("document.querySelector('#newBtn').click()")
        p.until("!!document.querySelector('#newBtnMenu')", "the Add menu opened")
        p.js(f"document.querySelector('#newBtnMenu [data-kind={kind}]').click()")

    def items(self, table):
        return {r["id"]: r for r in self.store.read(table, "ABC")}

    def test_each_pick_makes_the_item_opens_it_and_undo_removes_it(self):
        with chrome() as cdp:
            for width in SIZES:
                for kind, table, title_field, title in KINDS:
                    with self.subTest(width=width, kind=kind):
                        p = self.work(cdp, width)
                        before = self.items(table)
                        self.assertEqual(p.js("document.querySelector('[data-mode=view]').getAttribute('aria-pressed')"), "true", "the page opens in View")
                        self.pick(p, kind)
                        p.saved()
                        self.assertEqual(p.js("document.querySelector('[data-mode=edit]').getAttribute('aria-pressed')"), "true", "a pick in View turns the page to Edit")
                        made = [r for k, r in self.items(table).items() if k not in before]
                        self.assertEqual(len(made), 1, "one item was made")
                        row = made[0]
                        self.assertEqual((row["project"], row[title_field], row["source"], row["archived"]),
                                         ("ABC", title, changes.NEW_SOURCE, 0))
                        if table == "raid":
                            self.assertEqual(row["type"], kind.capitalize())
                        self.assertEqual(row["client_visible"], 1, "client-visible to start with, as every work item is (D-3); the eye hides it")
                        self.assertEqual(p.toast(), f"{row['id']} added")
                        p.until(f"(window.clarkPage.peek() || {{}}).id === '{row['id']}'", "the new item opened in its panel")
                        p.until(f"!!document.querySelector('#work tr[data-id=\"{row['id']}\"]')", "the new row is in the table")
                        p.js("document.querySelector('[data-undo]').click()")
                        p.until(f"(document.querySelector('.toast-text') || {{}}).textContent === '{row['id']} removed.'", "the Undo said what it removed")
                        self.assertEqual(set(self.items(table)), set(before), "Undo removed exactly what was made")
                        p.until(f"!document.querySelector('#work tr[data-id=\"{row['id']}\"]')", "the row left the table")
                        self.assertEqual(p.js("document.documentElement.scrollWidth <= window.innerWidth"), True)

    def test_the_request_names_only_the_new_rows_own_fields(self):
        with chrome() as cdp:
            p = self.work(cdp, 1400)
            for kind, table, _, _ in KINDS:
                self.sent.clear()
                self.pick(p, kind)
                p.saved()
                req = next(r for which, r in self.sent if which == "change")
                self.assertEqual((req["kind"], req["op"], req["project"], req["place"]), (table, "new", "ABC", "menu"))
                self.assertLessEqual(set(req["values"]), set(changes.CHANGE_KINDS[table][changes.NEW]))
                self.assertNotIn("client_visible", req["values"])
                p.clear_toast()

    def test_a_refusal_says_why_adds_nothing_and_opens_nothing(self):
        self.failure = lambda req: (400, {"ok": False, "code": "refused", "message": changes.PROJECT_NOT_ACTIVE})
        with chrome() as cdp:
            p = self.work(cdp, 1400)
            before = self.items("actions")
            self.pick(p, "action")
            p.until("!!document.querySelector('.toast')", "the page said what happened")
            self.assertEqual(p.toast(), changes.PROJECT_NOT_ACTIVE)
            self.assertFalse(p.js("!!document.querySelector('[data-undo]')"), "no Undo for nothing")
            self.assertEqual(p.js("(window.clarkPage.peek() || {}).id || ''"), "")
            self.assertEqual(set(self.items("actions")), set(before))

    def test_what_publish_selects_follows_the_eye_and_the_undo_of_an_added_item(self):
        def ids():
            return [r["id"] for r in publish.select(publish.read_inputs(self.store, "ABC", "2026-10-29"))["data"]["actions"]]
        with chrome() as cdp:
            p = self.work(cdp, 1400)
            before = set(self.items("actions"))
            self.pick(p, "action")
            p.saved()
            ref = next(k for k in self.items("actions") if k not in before)
            step = p.js("document.querySelector('[data-undo]') && true")
            self.assertTrue(step)
            self.assertIn(ref, ids(), "client-visible to start with (D-3), so it is published unless hidden")
            status, hid = self.real_change({"project": "ABC", "kind": "report_hidden", "op": "new", "id": ref, "place": "report"})
            self.assertEqual(status, 200)
            self.assertNotIn(ref, ids(), "hidden with the eye: never in the published file")
            self.assertEqual(self.real_undo({"project": "ABC", "apply_id": hid["apply_id"]})[0], 200)
            self.assertIn(ref, ids())
            p.js("document.querySelector('[data-undo]').click()")
            p.until(f"(document.querySelector('.toast-text') || {{}}).textContent === '{ref} removed.'", "the add was undone")
            self.assertNotIn(ref, ids(), "an undone add is never published")

if __name__ == "__main__":
    unittest.main()
