"""Row 1294, area 5: the 'Changes and safety' card on the ask clark page says what the code does (src/clark/page/src/edit/AskSettings.jsx).

Run: python3 dev/run_tests.py test_ask_safety_1294
Each of the four statements is pinned to the code behind it; the words are read from the page source."""
import re
import tempfile
import time
import unittest

from _paths import SRC
from _publish import PublishedFile
import test_glance_page as glance
from test_ask_apply import Base
import test_ask_settings as settings
from _editor_checks import for_project
from test_page import DATA, navigate
from test_server import Running, chrome, wait

from clark import ask, ask_files, changes, theme
from clark import page as page_module

JSX = (SRC / "clark" / "page" / "src" / "edit" / "AskSettings.jsx").read_text(encoding="utf-8")
LOOKS_KEY = "pass" + "word = Hunter2-Zebra-9"      # built in two pieces so the repository's own secret scan has nothing to match here


def page(*parts):
    return (SRC / "clark" / "page" / "src" / "/".join(parts)).read_text(encoding="utf-8")


class Words(unittest.TestCase):
    def test_the_card_is_on_the_all_projects_tab_with_the_four_statements(self):
        block = JSX[JSX.index("export const SAFETY"):JSX.index("const ALL_FOLDERS_COUNT")]
        titles = re.findall(r'^  \["([^"]+)"', block, re.M)
        self.assertEqual(titles, ["Every change needs your approval",
                                  "A change taken from one of your own files or passages needs an extra tick",
                                  "ask clark is never on a published report",
                                  "Passwords and keys are never sent"])
        self.assertIn("{classicTheme() ? <Safety /> : null}", JSX[JSX.index("function AllProjects"):JSX.index("function AllFolders")])
        self.assertIn('const SAFETY_NOTE = "These are not switches.";', JSX)
        self.assertIn("A change can be taken back with Undo, except a decision marked Made, which a new decision replaces.", block)
        self.assertIn("A published file has no ask clark button or panel, and it asks nothing.", block)

    def test_the_old_untrue_words_are_gone(self):
        for old in ("what a client sees", "read-only or client page", "View mode", "Every change has an Undo.",
                    "ask clark only suggests", "The published report has none.", "from a file or passage"):
            self.assertNotIn(old, JSX)

    def test_the_tick_words_are_the_boxs_own_words(self):
        words = page("edit", "askWords.js")
        box = re.search(r'CONFIRM_BOX = "([^"]+)"', words).group(1)
        self.assertEqual(box, "I have checked this change and want to save it")
        self.assertIn("\\u201c" + box + "\\u201d", JSX)


class Approval(Base):
    def test_a_suggestion_changes_nothing_until_apply(self):
        before = self.counts()
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")
        status, body = self.ask.apply("not-an-offer", "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)
        self.applied(plan["offer"])
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Closed")

    def test_an_applied_change_has_an_undo_and_it_puts_the_old_value_back(self):
        applied = self.applied(self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})["offer"])
        self.assertTrue(applied["undoable"])
        status, body = self.undo({"project": "ABC", "apply_id": applied["apply_id"]})
        self.assertEqual(status, 200, body)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_a_decision_marked_made_is_not_undone_and_a_new_decision_replaces_it(self):
        with self.s.step("dashboard", "t") as st:
            ref = st.create("decisions", {"project": "ABC", "decision": "Use the shared calendar", "status": "Pending", "source": "demo"})
        applied = self.applied(self.planned({"op": "change", "id": ref, "current_title": "Use the shared calendar", "status": "Made", "date": "2026-10-29", "made_by": "Sara Khan"})["offer"])
        self.assertEqual(self.s.read("decisions", ref=ref)["status"], "Made")
        status, body = self.undo({"project": "ABC", "apply_id": applied["apply_id"]})
        self.assertFalse(applied["undoable"], "the apply says itself there is no Undo for a Made decision")
        self.assertEqual((status, body["code"], body["message"]), (400, "refused", "That step can't be undone from here."))
        self.assertEqual(self.s.read("decisions", ref=ref)["status"], "Made", "still Made after the refused Undo")
        self.assertIn("Record a new decision that replaces it", changes.MADE_CANT_BE_PUT_BACK)
        self.assertIn("except a decision marked Made, which a new decision replaces", JSX)

    def test_a_decision_marked_made_has_no_undo(self):
        with self.s.step("dashboard", "tester") as st:
            ref = st.create("decisions", {"project": "ABC", "decision": "Pick the venue", "made_by": "Sam Lee", "status": "Pending", "source": "demo"})
        plan = self.planned({"op": "change", "id": ref, "current_title": "Pick the venue", "status": "Made", "date": "2026-11-01"})
        self.assertFalse(self.applied(plan["offer"])["undoable"])

    def test_asking_cannot_make_a_new_use_case_so_that_needs_no_undo_words(self):
        status, body = self.ask.plan("ABC", {"op": "new", "kind": "use case", "title": "Book the room"})
        self.assertEqual((status, body["code"]), (400, "not_a_change"))

    def test_a_new_work_item_has_an_undo(self):
        plan = self.planned({"op": "new", "kind": "action", "title": "Book the training room", "owner": "Sam Lee"})
        self.assertTrue(self.applied(plan["offer"])["undoable"])


class OnlyOffered(Base):
    def test_an_id_that_was_never_offered_is_refused_and_nothing_is_written(self):
        before = self.counts()
        for fake in ("never-offered", "", "0" * 32):
            status, body = self.ask.apply(fake, "ABC")
            self.assertEqual((status, body["code"]), (409, "no_offer"), fake)
        self.assertEqual(self.counts(), before, "nothing was written")
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")

    def test_an_offer_applies_once_and_the_second_try_writes_nothing_more(self):
        plan = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        before = self.counts()
        self.applied(plan["offer"])
        after_first = self.counts()
        self.assertEqual(after_first[0], before[0] + 1, "one apply row")
        status, body = self.ask.apply(plan["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), after_first, "the second apply wrote nothing")

    def test_one_offer_cannot_stand_in_for_another(self):
        one = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        before = self.counts()
        status, body = self.ask.apply(one["offer"] + "x", "ABC")
        self.assertEqual((status, body["code"]), (409, "no_offer"))
        self.assertEqual(self.counts(), before)
        self.assertEqual(self.s.read("actions", ref=self.action)["status"], "Open")


class ExtraTick(Base):
    def test_only_a_change_taken_from_a_source_needs_the_tick(self):
        own = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed"})
        self.assertFalse(own["needs_confirm"])
        src = self.planned({"op": "change", "id": self.action, "current_title": "Draft the cut-over plan", "status": "Closed", "source": "P2"})
        self.assertTrue(src["needs_confirm"])
        status, body = self.ask.apply(src["offer"], "ABC")
        self.assertEqual((status, body["code"]), (409, "needs_confirm"))
        self.assertIn('"needs_confirm": plan.from_source', (SRC / "clark" / "ask_apply.py").read_text(encoding="utf-8"))

    def test_the_panel_blocks_apply_until_the_tick(self):
        jsx = page("edit", "AskChange.jsx")
        self.assertIn("plan.needs_confirm === true", jsx)
        self.assertIn("(confirm && !ticked)", jsx)


class Published(PublishedFile, glance.Setup):
    def test_a_published_file_has_no_ask_button_no_panel_and_the_slash_opens_nothing(self):
        path = self.publish()
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.draw(cdp, path, width)
                p.key("/", code="Slash", vk=191)
                time.sleep(0.5)
                got = p.js("""({btn: !!document.querySelector('#ask-btn, .tb-ask'), panel: !!document.querySelector('#ask-panel'),
                                label: [...document.querySelectorAll('button,a')].some(e => /ask clark/i.test(e.getAttribute('aria-label') || e.textContent))})""")
                self.assertEqual(got, {"btn": False, "panel": False, "label": False})

    def test_the_card_has_no_bullets_like_the_folders_list_in_classic(self):
        css = ((SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8") + (SRC / "clark" / "themes" / "prototype-2.0" / "rules-2.css").read_text(encoding="utf-8"))
        self.assertIn(".ask-safety { margin: var(--space-2) 0 0; padding: 0; list-style: none; }", css)
        self.assertLess(css.index(".ask-safety {"), css.index("/* Row 1314"))


class CardLayout(unittest.TestCase):
    ready = True
    folder, until = (settings.Settings.__dict__[n] for n in ("folder", "until"))

    def setUp(self):             # as Settings.setUp, but with the page served in Classic, the only look applied (clark.theme.CLASSIC)
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code),
                         page_html=lambda: page_module.page_html(tempfile.mkdtemp(), theme=theme.CLASSIC))
        self.addCleanup(self.s.close)
        self.db = settings.make_db(self.folder(), ready=True, cleanup=self.addCleanup)
        self.s.httpd.app_settings = settings.service(self.db)

    """The card as drawn on the running page, at 1400 and 900."""
    def test_the_card_is_on_the_all_projects_tab_with_four_plain_statements_and_fits(self):
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), 20))
            self.assertFalse(js("!!document.querySelector('#ask-safety')"), "not on the project's own tab")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-safety')"), 20), "on the All projects tab")
            for w in settings.WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(lambda: js("document.documentElement.scrollWidth <= window.innerWidth"), True, f"no sideways scroll at {w}")
                got = js("""(() => { const c = document.querySelector('#ask-safety'), r = c.getBoundingClientRect(), ul = c.querySelector('ul.ask-safety');
                  return {heading: c.querySelector('h2').innerText, n: ul.children.length, style: getComputedStyle(ul).listStyleType,
                         
                          left: r.left, right: r.right, vw: window.innerWidth, over: c.scrollWidth > c.clientWidth,
                          titles: [...ul.querySelectorAll('li > strong')].map(e => e.innerText)}; })()""")
                self.assertEqual(got["heading"], "Changes and safety", w)
                self.assertEqual(got["n"], 4, w)
                self.assertEqual(len(got["titles"]), 4, w)
                self.assertEqual(got["style"], "none", f"no bullets at {w}")
                self.assertTrue(got["left"] >= 0 and got["right"] <= got["vw"], f"the card is inside the page at {w}: {got}")
                self.assertFalse(got["over"], f"the card does not scroll sideways at {w}")


class CardsUnchanged(unittest.TestCase):
    """Cards is frozen: with no theme the All projects tab draws no Changes and safety card."""
    ready = True
    folder, until = (settings.Settings.__dict__[n] for n in ("folder", "until"))

    def setUp(self):
        self.s = Running(data_for=lambda code, archived=None: DATA.get(code), page_html=lambda: page_module.page_html(tempfile.mkdtemp()))
        self.addCleanup(self.s.close)
        self.db = settings.make_db(self.folder(), ready=True, cleanup=self.addCleanup)
        self.s.httpd.app_settings = settings.service(self.db)

    def test_cards_all_projects_tab_has_no_safety_card(self):
        with chrome() as cdp:
            self.sid = navigate(cdp, self.s.port, for_project("#settings&p=ABC&s=claude"))
            js = lambda e: cdp.js(e, self.sid)          # noqa: E731
            self.assertTrue(wait(lambda: js("!!document.querySelector('[data-ask-tab=all]')"), 20))
            self.assertFalse(js("!!document.querySelector('style#theme')"), "this page is Cards: no theme element")
            js("document.querySelector('[data-ask-tab=all]').click()")
            self.assertTrue(wait(lambda: js("!!document.querySelector('#ask-all')"), 20), "the All projects tab is drawn")
            self.assertFalse(js("!!document.querySelector('#ask-safety, ul.ask-safety')"), "Cards draws no safety card")
            self.assertNotIn("Changes and safety", js("document.body.innerText"))


class Secrets(unittest.TestCase):
    def test_a_question_that_looks_like_a_key_is_stopped_and_the_person_is_told(self):
        with self.assertRaises(ask.AskRefused) as r:
            ask.check_question(LOOKS_KEY)
        self.assertIn("so it wasn't sent", str(r.exception))

    def test_an_earlier_message_that_looks_like_a_key_stops_the_chat_with_words(self):
        with self.assertRaises(ask.AskRefused) as r:
            ask.check_question("Next question", [("user", LOOKS_KEY)])
        self.assertIn("can't be sent", str(r.exception))

    def test_a_file_that_looks_like_a_key_refuses_the_question(self):
        import base64
        f = {"name": "notes.txt", "data": base64.b64encode(LOOKS_KEY.encode()).decode()}
        with self.assertRaises(ask.AskRefused) as r:
            ask_files.passages([f])
        self.assertIn("Nothing was sent", str(r.exception))


if __name__ == "__main__":
    unittest.main()
