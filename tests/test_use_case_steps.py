"""Use cases: the next steps and the owner's circle (prototype parity, views.js and usecases.js).

Run: python3 dev/run_tests.py test_use_case_steps
Part 1 runs the page's own rules (logic/useCaseSteps.js, edit/itemEdit.js) in headless Chrome. Part 2 drives the committed page on a real
server over a fictional store: the summary's steps are the open work items of ANY type, said in the client wording; in Edit a step's owner
and words change in place, one step with one Undo. Part 3 opens a published file from file:// and checks that a client sees the client
wording only (a step with none is left out, and its own words are nowhere in what is drawn) and the owner's circle on the Use Cases tab.
Laptop widths only: 1400 and 900 px, light and dark. Every planted due date is in 2020 or 2099, so no clock is fixed.
"""
import contextlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _paths import SRC
from test_glance_page import LONG, Setup, plant  # noqa: F401
from test_report_editor import EMPTY_BRANDING, Pg, tearDownModule  # noqa: F401
from test_server import chrome, wait  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402

from clark import publish  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
WORDS = "We will send you the supplier file by Friday."
RISK_WORDS = "One supplier may be late."
NO_WORDS = "ZQ-no-wording step"
INTERNAL = "Chase the supplier file"                  # the action's own title (the plant's): internal, never in a client's file when it has no wording


class Rules(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)
        for module, name in (("logic/useCaseSteps.js", "S"), ("edit/itemEdit.js", "E")):
            res = cls.cdp.call("Runtime.evaluate", {"expression": bundled(PAGE_SRC / module, name) + "; true", "returnByValue": True}, cls.sid)
            assert "exceptionDetails" not in res, res

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def js(self, expr):
        res = self.cdp.call("Runtime.evaluate", {"expression": expr, "returnByValue": True}, self.sid)
        self.assertNotIn("exceptionDetails", res, res)
        return res["result"]["value"]

    def test_a_client_sees_the_wording_and_a_step_with_none_is_left_out(self):
        got = self.js("""(() => { const open = [{id: 'A1', title: 'Own title one', kind: 'action'}, {id: 'R1', title: 'Own title two', kind: 'risk'}, {id: 'D1', title: 'Own title three', kind: 'decision'}];
          const wording = {A1: 'Wording one', D1: 'Wording three'};
          return {client: S.stepsFrom(open, wording, {client: true}).map(r => [r.id, r.said]), editor: S.stepsFrom(open, wording).map(r => [r.id, r.said])}; })()""")
        self.assertEqual(got["client"], [["A1", "Wording one"], ["D1", "Wording three"]], "the risk has no wording, so a client's list leaves it out")
        self.assertEqual(got["editor"], [["A1", "Wording one"], ["R1", "Own title two"], ["D1", "Wording three"]],
                         "the editor sees the wording when there is some, the title when there is not; every type is a step")

    def test_wording_is_read_from_actions_risks_and_decisions_and_blanks_are_none(self):
        got = self.js("""S.wordingById({actions: [{id: 'A1', client_message: '  Say  this \\n now '}, {id: 'A2', client_message: '   '}, {id: 'A3'}],
          raid: [{id: 'R1', client_message: 'Risk words'}], decisions: [{id: 'D1', client_message: null}, {id: 'D2', client_message: 'Decision words'}]})""")
        self.assertEqual(got, {"A1": "Say this now", "R1": "Risk words", "D2": "Decision words"})

    def test_the_circle_has_the_first_letters_of_up_to_two_words(self):
        self.assertEqual(self.js("['Pat Demo', 'sam rivers lee', 'Dana', '', null, 'TBC'].map(S.avatarOf)"), ["PD", "SR", "D", "?", "?", "?"])

    def test_a_steps_title_is_changed_in_the_column_its_kind_saves_it_in(self):
        got = self.js("""[E.changeFor({id: 'A1', kind: 'action', title: 'Old'}, 'title', '  New   words ', '2026-10-28'),
          E.changeFor({id: 'R1', kind: 'risk', title: 'Old'}, 'title', 'New', '2026-10-28'),
          E.changeFor({id: 'D1', kind: 'decision', title: 'Old'}, 'title', 'New', '2026-10-28'),
          E.changeFor({id: 'A1', kind: 'action', title: 'Same'}, 'title', ' Same ', '2026-10-28')].map(r => r && r.changes)""")
        self.assertEqual(got, [{"description": "New words"}, {"description": "New"}, {"decision": "New"}, None])

    def test_a_title_that_cannot_be_kept_is_said_in_plain_words_and_sends_nothing(self):
        got = self.js("""['', '   ', 'a\\u200bb', 'x'.repeat(201)].map(v => E.changeFor({id: 'A1', kind: 'action', title: 'Old'}, 'title', v, '2026-10-28').error)""")
        self.assertIn("needs some words", got[0])
        self.assertEqual(got[0], got[1])
        self.assertIn("hidden character", got[2])
        self.assertIn("200 characters", got[3])


class Summary(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.a_open, {"client_message": WORDS})
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Supplier may be late", "raised": "2026-10-01", "source": "demo",
                                           "impact": "High", "likelihood": "High", "owner": "Lee Demo", "use_case": self.demo.use_case,
                                           "client_message": RISK_WORDS})

    def open_first(self, p):
        p.js("document.querySelector('.ucrow .ucbar').click()")
        p.until("!!document.querySelector('.ucdetail')", "the row opened")

    def test_the_steps_are_the_open_items_of_any_type_in_the_client_wording(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    bar = p.js("document.querySelector('.ucrow .ucbar .ucsteps').textContent")
                    self.assertEqual(bar, "4 next steps", "three actions and the risk")
                    self.open_first(p)
                    steps = p.js("[...document.querySelectorAll('.ucdetail [data-step]')].map(e => e.dataset.step + '|' + e.textContent)")
                    self.assertEqual(len(steps), 4)
                    text = " ".join(steps)
                    self.assertIn(f"Pat Demo: {WORDS}", text, "the action is said in its client wording")
                    self.assertNotIn(INTERNAL, " ".join(s for s in steps if s.startswith(self.a_open)), "not its own title")
                    self.assertIn(f"Lee Demo: {RISK_WORDS}", text, "a risk is a next step too")
                    self.assertIn("Sam Demo: ZQ-sensitive step", text, "with no wording, the editor sees the title")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_a_step_with_the_eye_off_the_page_still_counts_for_the_editor_but_a_closed_one_does_not(self):
        with self.store.step("dashboard", USER) as st:
            st.update("raid", self.risk, {"status": "Closed"})
        with chrome() as cdp:
            p = self.show(cdp)
            self.assertEqual(p.js("document.querySelector('.ucrow .ucbar .ucsteps').textContent"), "3 next steps")

    def edit_step(self, p, step, field, text, key="Enter"):
        sel = f"[data-step='{step}'] [data-step-field={field}]"
        p.js(f"document.querySelector(\"{sel}\").focus()")
        p.js(f"document.querySelector(\"{sel}\").textContent = {json.dumps(text)}")
        p.js(f"document.querySelector(\"{sel}\").dispatchEvent(new KeyboardEvent('keydown', {{key: {json.dumps(key)}, bubbles: true, cancelable: true}}))")

    def test_in_edit_the_owner_and_the_words_change_in_place_one_step_with_one_undo(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.show(cdp, width, dark)
                    p.edit()
                    self.open_first(p)
                    old = self.store.read("actions", ref=self.a_open)
                    self.assertEqual(p.js(f"document.querySelector(\"[data-step='{self.a_open}'] [data-step-field=title]\").textContent"), INTERNAL,
                                     "Edit shows the item's own title, to change it")
                    self.assertEqual(p.js(f"document.querySelector(\"[data-step='{self.a_open}'] [data-step-field=owner]\").getAttribute('contenteditable')"), "plaintext-only")
                    self.edit_step(p, self.a_open, "title", "Chase the supplier file again")
                    p.until("!!document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.includes('changed')", "saved")
                    row = self.store.read("actions", ref=self.a_open)
                    self.assertEqual(row["description"], "Chase the supplier file again")
                    self.assertEqual(row["owner"], old["owner"], "only the words changed")
                    self.undo(p)
                    self.assertEqual(self.store.read("actions", ref=self.a_open)["description"], old["description"], "one Undo puts the words back")
                    self.edit_step(p, self.a_open, "owner", "Lee Demo")
                    p.until("!!document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.includes('Owner')", "owner saved")
                    self.assertEqual(self.store.read("actions", ref=self.a_open)["owner"], "Lee Demo")
                    self.undo(p)
                    self.assertEqual(self.store.read("actions", ref=self.a_open)["owner"], old["owner"])

    def test_esc_and_a_blank_leave_the_text_as_it_was_and_send_nothing(self):
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.open_first(p)
            before = self.store.read("actions", ref=self.a_open)
            self.edit_step(p, self.a_open, "title", "Typed over", key="Escape")
            p.until(f"document.querySelector(\"[data-step='{self.a_open}'] [data-step-field=title]\").textContent === {json.dumps(INTERNAL)}", "Esc put the text back")
            self.edit_step(p, self.a_open, "owner", "   ")
            p.until("!!document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent.includes('blank')", "the refusal is said")
            self.assertEqual(p.js(f"document.querySelector(\"[data-step='{self.a_open}'] [data-step-field=owner]\").textContent"), "Pat Demo")
            self.assertEqual(self.store.read("actions", ref=self.a_open), before)

    def test_view_has_nothing_to_type_into(self):
        with chrome() as cdp:
            p = self.show(cdp)
            self.open_first(p)
            self.assertEqual(p.js("document.querySelectorAll('.ucdetail [data-step-field], .ucdetail [contenteditable]').length"), 0)


class Published(Setup):
    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            st.update("actions", self.a_open, {"client_message": WORDS})
            st.update("actions", self.a_later, {"client_message": "We will plan the second wave next quarter."})
            st.create("raid", {"project": "ABC", "type": "Risk", "description": "ZQ-risk-own-title", "raised": "2026-10-01", "source": "demo",
                               "impact": "High", "likelihood": "High", "owner": "Lee Demo", "use_case": self.demo.use_case, "client_message": RISK_WORDS})
        self.demo.action(description=NO_WORDS, owner="Kim Demo", due_date=LONG, use_case=self.demo.use_case)      # kept in the file (a client may see it), but it has no client wording
        out = tempfile.mkdtemp(prefix="clark-steps-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        self.path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)["path"])

    def draw(self, cdp, width=1400, dark=False):
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": self.path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        if dark:
            p.js("document.documentElement.dataset.theme = 'dark'")
        return p

    def test_the_dashboard_says_the_client_wording_and_leaves_out_a_step_with_none(self):
        for width, dark in ((1400, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.draw(cdp, width, dark)
                p.until("!!document.querySelector('.ucrow .ucbar')", "the summary drew")
                self.assertEqual(p.js("document.querySelector('.ucrow .ucbar .ucsteps').textContent"), "2 next steps", "the action and the risk have wording; the open action with none is left out")
                p.js("document.querySelector('.ucrow .ucbar').click()")
                p.until("!!document.querySelector('.ucdetail')", "the row opened")
                text = p.js("document.querySelector('.ucdetail').innerText")
                self.assertIn(f"Pat Demo: {WORDS}", text)
                self.assertIn(f"Lee Demo: {RISK_WORDS}", text)
                for internal in (INTERNAL, "ZQ-risk-own-title", NO_WORDS):
                    self.assertNotIn(internal, text, "an item's own title is not what a client reads")
                self.assertEqual(p.js("document.querySelectorAll('.ucdetail [data-step-field], .ucdetail [contenteditable]').length"), 0)
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_the_tab_has_the_circle_and_the_wording_and_nothing_internal(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    p = self.draw(cdp, width, dark)
                    p.js("document.querySelector('[data-view=usecases]').click()")
                    p.until("document.querySelector('h1').textContent === 'Use Cases'", "the tab opened")
                    p.js("document.querySelector('.ucp summary').click()")
                    steps = p.js("[...document.querySelectorAll('.ucp[open] .ucp-steps li')].map(li => ({av: li.querySelector('.av').textContent, text: li.querySelector('.ucp-sm').textContent}))")
                    self.assertEqual(len(steps), 1, "only the action with client wording is a step on the tab (the tab holds actions, as the prototype's does)")
                    self.assertEqual(steps[0]["av"], "PD", "the owner's first letters")
                    self.assertTrue(steps[0]["text"].startswith(f"Pat Demo: {WORDS}"), steps)
                    body = p.js("document.querySelector('.ucp[open] .ucp-body').innerText")
                    self.assertIn("NEXT STEPS · 1", body.upper())
                    for internal in (INTERNAL, NO_WORDS, "ZQ-sensitive step", "ZQ-client-off step"):
                        self.assertNotIn(internal, body)
                    box = p.js("(() => { const a = document.querySelector('.ucp[open] .ucp-steps .av').getBoundingClientRect(); return [a.width, a.height, getComputedStyle(document.querySelector('.ucp[open] .ucp-steps .av')).borderRadius]; })()")
                    self.assertEqual(box[0], box[1], "the circle is round")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")

    def test_a_step_with_no_wording_is_in_no_drawn_text_of_the_tab(self):
        with chrome() as cdp:
            p = self.draw(cdp)
            p.js("document.querySelector('[data-view=usecases]').click()")
            p.until("document.querySelector('h1').textContent === 'Use Cases'", "the tab opened")
            p.js("document.querySelectorAll('.ucp').forEach(d => d.open = true)")
            text = p.js("document.querySelector('#usecases-file').innerText")
            self.assertIn("We will plan the second wave next quarter.", text, "the second use case's step has wording")
            self.assertNotIn("Plan the second wave", text)


if __name__ == "__main__":
    unittest.main()
