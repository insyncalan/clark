"""Row 811: the peek's "Needed from the client" switch (Edit only), with its sub-line, under the Raised / Last reviewed line and above
Latest update. One request and one Undo; the row carries the flag so the `is:needed` filter word finds it; View, a published file and a
decision's peek have none. Looked at in the page at 1400 and 900 px, light and dark.

Run: python3 dev/run_tests.py test_peek_client_action
"""
import unittest

from _paths import ROOT
from test_peek_latest import Browser as _Harness, OVERDUE
from test_server import chrome, wait
from test_work_filters import click

SUB = "Lists it under “Needs from you” when the report has that section"      # row 1066: the published page adds no section the editor lacks
LABEL = "Needed from the client"


class Page(unittest.TestCase):
    setUp = _Harness.setUp
    fresh = _Harness.fresh
    load = _Harness.load
    look = _Harness.look
    want = _Harness.want
    inside = _Harness.inside
    toast = _Harness.toast
    LOOK = _Harness.LOOK
    HOLD = _Harness.HOLD

    def flag(self, table, ref):
        return next(r for r in self.store.data_for(self.code)[table] if r["id"] == ref)["client_action"]

    def state(self, cdp, sid):
        return cdp.js("(b => b ? b.getAttribute('aria-checked') : null)(document.querySelector('#peek [data-pk-needed] [role=switch]'))", sid)

    def test_the_source_hands_it_to_edit_only_and_the_row_carries_the_flag(self):
        peek = (ROOT / "src/clark/page/src/components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && forItem && tools.PeekNeeded", peek)
        self.assertLess(peek.index("<Needed "), peek.index("<Latest "), "above Latest update")
        items = (ROOT / "src/clark/page/src/workItems.js").read_text(encoding="utf-8")
        self.assertIn("client_action: !!r.client_action", items)
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("data-pk-needed", view)

    def test_the_switch_sits_between_the_review_line_and_latest_update_and_flips_with_one_request_and_one_undo(self):
        for width, dark in ((1400, False), (900, False), (1400, True), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, dark=dark)
                self.assertEqual(self.state(cdp, sid), "false", "off to start")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-needed] [role=switch]').getAttribute('aria-label')", sid), LABEL)
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-needed]').textContent", sid), LABEL + SUB)
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-needed] small').textContent", sid), SUB)
                order = cdp.js("(() => { const p = document.querySelector('#peek'), n = p.querySelector('[data-pk-needed]'), l = p.querySelector('[data-pk-latest]'),"
                               " f = p.querySelector('.pk-fields'); const a = f.compareDocumentPosition(n), b = n.compareDocumentPosition(l);"
                               " return [!!(a & Node.DOCUMENT_POSITION_FOLLOWING), !!(b & Node.DOCUMENT_POSITION_FOLLOWING)]; })()", sid)
                self.assertEqual(order, [True, True], "after the fields, before Latest update")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-needed]"), "fits the peek")
                self.assertTrue(cdp.js("(() => { const r = document.querySelector('#peek [data-pk-needed] [role=switch]').getBoundingClientRect(); return r.width >= 44 && r.height >= 24; })()", sid))
                for sel in ("[data-pk-needed] span", "[data-pk-needed] small"):
                    seen = self.look(cdp, sid, "#peek " + sel)
                    self.assertTrue(seen["shown"], sel)
                    self.assertGreaterEqual(seen["ratio"], 4.5, seen)
                if dark:
                    self.assertEqual(cdp.js("document.documentElement.dataset.theme", sid), "dark")
                    self.assertEqual(self.want(cdp, sid, "--surface"), [14, 45, 56])
                click(cdp, sid, "#peek [data-pk-needed] [role=switch]")
                self.assertTrue(wait(lambda: self.state(cdp, sid) == "true"), "on once clark has saved it")
                self.assertEqual(len(sent), 1, "one switch is one request")
                self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", OVERDUE, {"client_action": 1}))
                self.assertEqual(self.flag("actions", OVERDUE), 1)
                if dark:
                    blue = self.want(cdp, sid, "--brand-blue")
                    self.assertTrue(wait(lambda: self.look(cdp, sid, "#peek [data-pk-needed] [role=switch]")["bg"] == blue), "the on switch is the brand blue")
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.state(cdp, sid) == "false"), "one Undo puts it back")
                self.assertEqual(self.flag("actions", OVERDUE), 0)
                click(cdp, sid, "#peek [data-pk-needed] [role=switch]")
                self.assertTrue(wait(lambda: self.state(cdp, sid) == "true"))
                click(cdp, sid, "#peek [data-pk-needed] [role=switch]")
                self.assertTrue(wait(lambda: self.state(cdp, sid) == "false"), "and it switches off")
                self.assertEqual(sent[-1]["changes"], {"client_action": 0})

    def test_a_risk_has_it_and_a_decision_has_none(self):
        risk, decision = self.data["raid"][0]["id"], self.data["decisions"][0]["id"]
        probe = "!!document.querySelector('#peek [data-pk-needed]')"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, risk)
                self.assertTrue(cdp.js(probe, sid))
                click(cdp, sid, "#peek [data-pk-needed] [role=switch]")
                self.assertTrue(wait(lambda: self.state(cdp, sid) == "true"))
                self.assertEqual((sent[0]["kind"], sent[0]["changes"]), ("raid", {"client_action": 1}))
            with self.subTest(width=width, item="decision"), chrome() as cdp:
                sent, sid = self.load(cdp, width, decision)
                self.assertFalse(cdp.js(probe, sid))
            with self.subTest(width=width, item="work items in view"), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, edit=False)
                self.assertTrue(cdp.js(probe, sid), "row 824: Work items is editable in View, so its peek has the switch (a published file has none: the source test above)")


if __name__ == "__main__":
    unittest.main()
