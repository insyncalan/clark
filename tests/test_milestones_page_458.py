"""#458: the Milestones page where the build gave less than the prototype: the head (project, title, one sentence), Add milestone, and
Movement's Add a recovery action, Escalate to steering and Internal note. The owner's ruling stays: the published list shows five rows
and "Show all N".

Run: python3 dev/run_tests.py test_milestones_page_458
Without a browser: the published page carries the head and none of the owner's parts; the requests the page makes are ones clark takes
(a linked action, a steering decision, a new milestone, the note), each with one Undo; the five-row ruling is pinned in the page's source.
With headless Chrome (fails, never skips, without it): the head's sentence from the page's own rules; the head, the button and the
Movement parts in the real server at 1400 and 900 px, light and dark; the published file at five rows, "Show all N", and nothing internal.
Laptop only.
"""
import json
import re
import shutil
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from _demo import USER, DemoStore
from _paths import SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

from clark import changes, page, publish  # noqa: E402
from test_milestones_page import CASES, EMPTY_BRANDING, MODULE, TODAY  # noqa: E402
from test_movement_page import GO_LIVE, INTERNAL, PILOT, Base, in_days  # noqa: E402
from test_server import Running, chrome, wait  # noqa: E402
from test_work_items import bundled, page_target  # noqa: E402

PAGE_SRC = SRC / "clark" / "page" / "src"
OWNERS_WORDS = ("Add milestone", "Internal note", "Add a recovery action", "Escalate to steering", "Saves when you leave the box",
                "New milestone", "Steering decision on", "Note saved")
NEW_STRINGS = ("Add milestone", "New milestone", "Milestone added. Undo.", "Add a recovery action", "Escalate to steering", "Recover %s",
               "Steering decision on %s", "%s added and linked to %s. Undo.", "%s added for %s. Undo.", "Internal note",
               "What is going on, what you are waiting for", "Saves when you leave the box. Never published.", "Note saved. Undo.",
               "The note couldn't be saved, and nothing was changed. Reload the page and try again.", "Hold recorded in the note. Undo.",
               "%s is %s behind its agreed date.", "%s is not behind its agreed date.",
               "There is no open workstream to put the action in. Open or add a workstream first, then try again.")


def js_words():
    text = (PAGE_SRC / "edit" / "movementWords.js").read_text(encoding="utf-8")
    return {m.group(1): json.loads(m.group(2)) for m in re.finditer(r'^export const (\w+) = ("(?:[^"\\]|\\.)*");$', text, re.M)}


class NoBrowser(unittest.TestCase):
    def test_the_published_page_has_the_head_and_none_of_the_owners_parts(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        served = page.PAGE.read_text(encoding="utf-8")
        for text in ("ms-summary", "head-sub", "to come", "achieved"):
            self.assertIn(text, view, text)
        for text in OWNERS_WORDS:
            self.assertNotIn(text, view, f"{text!r} is in the published page")
            self.assertIn(text, served, f"{text!r} is not in the served page")
        for text in ("sendNewRow", "mvNote", "mv-recover", "mv-escalate", "addMs"):
            self.assertNotIn(text, view, text)

    def test_the_published_build_takes_none_of_the_new_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            meta = Path(tmp) / "meta.json"
            done = esbuild.run(["--bundle", "--format=iife", "--tsconfig-raw={}", *build_page.preact_flags(), build_page.ENTRY_VIEW,
                                f"--outfile={Path(tmp) / 'p.js'}", f"--metafile={meta}"], cwd=build_page.SRC, capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
            inputs = list(json.loads(meta.read_text(encoding="utf-8"))["inputs"])
        for name in inputs:
            self.assertFalse(name.endswith(("MsAdd.jsx", "newRows.js", "api.js", "stores/changes.js")), name)
            self.assertNotRegex(name, r"(?i)movement", name)

    def test_the_styles_of_the_owners_note_are_in_the_served_page_only(self):
        self.assertIn(".mvm-note", build_page.page_css(build_page.ENTRY))
        self.assertNotIn(".mvm-note", build_page.page_css(build_page.ENTRY_VIEW))
        self.assertIn(".head-sub", build_page.page_css(build_page.ENTRY_VIEW))

    def test_the_owners_ruling_the_list_stays_five_rows_and_show_all(self):
        logic = MODULE.read_text(encoding="utf-8")
        self.assertIn("export const RAIL = 5;", logic)
        self.assertIn('`Show all ${n} milestones`', logic)
        self.assertIn('"Show the first 5"', logic)
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        self.assertIn("Show all ", view)
        self.assertIn("Show the first 5", view)

    def test_every_new_string_is_in_the_words_file_and_is_plain(self):
        words = set(js_words().values())
        for text in NEW_STRINGS:
            self.assertIn(text, words, text)
            self.assertFalse(re.match(r"(?i)clark\b", text), text)
            self.assertNotRegex(text, r"\d{4}-\d\d-\d\d", text)
        self.assertIn("Add milestone", words)


class Requests(unittest.TestCase):
    """The requests the page sends, through the real change and undo routes of clark/changes.py."""

    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.s = self.demo.store
        self.change = changes.make_change(self.s.path, [], USER)
        self.undo = changes.make_undo(self.s.path, [], USER)
        self.m = self.demo.milestone

    def send(self, kind, values):
        status, got = self.change({"project": "ABC", "kind": kind, "op": "new", "values": values, "place": "report"})
        self.assertEqual((status, got.get("ok")), (200, True), got)
        return got

    def test_a_recovery_action_is_high_due_in_a_week_and_linked_and_one_undo_takes_it_away(self):
        due = (date.today() + timedelta(days=7)).isoformat()
        got = self.send("actions", {"description": "Recover pilot live", "priority": "High", "due_date": due, "milestone": self.m})
        row = self.s.read("actions", ref=got["ref"])
        self.assertEqual((row["description"], row["priority"], row["due_date"], row["milestone"]), ("Recover pilot live", "High", due, self.m))
        self.assertRegex(got["ref"], r"^ABC-A-\d{3}$")
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual((status, undone["ok"], undone["skipped"]), (200, True, []))
        self.assertIsNone(self.s.read("actions", ref=got["ref"]))

    def test_the_explanation_line_is_kept_on_the_new_row_and_never_said_back_or_shown_to_ask_clark(self):
        due = (date.today() + timedelta(days=7)).isoformat()
        got = self.send("actions", {"description": "Recover pilot live", "priority": "High", "due_date": due, "milestone": self.m,
                                    "latest_update": "Pilot live is 3 days behind its agreed date."})
        self.assertEqual(self.s.read("actions", ref=got["ref"])["latest_update"], "Pilot live is 3 days behind its agreed date.")
        done = self.send("decisions", {"decision": "Steering decision on pilot live", "needed_by": due, "reasoning": "Pilot live is 3 days behind its agreed date."})
        self.assertEqual(self.s.read("decisions", ref=done["ref"])["reasoning"], "Pilot live is 3 days behind its agreed date.")
        for reply in (got, done):
            self.assertNotIn("behind its agreed date", json.dumps(reply), "the reply does not say the line back")
        self.assertNotIn("latest_update", changes.ASK_SHOWN["actions"])
        self.assertNotIn("reasoning", changes.ASK_SHOWN["decisions"])
        for table, field in (("actions", "latest_update"), ("decisions", "reasoning")):
            self.assertNotIn(field, changes.ASK_FIELDS[table][changes.NEW])
            self.assertNotIn(field, changes.CHANGE_KINDS[table][changes.UPDATE])
        status, bad = self.change({"project": "ABC", "kind": "decisions", "op": "new", "place": "report",
                                   "values": {"decision": "x", "reasoning": "a\u202eb"}})
        self.assertEqual((status, bad["ok"]), (400, False), "the line is held to the plain-text rule")

    def test_a_steering_decision_is_pending_and_needed_in_a_week(self):
        needed = (date.today() + timedelta(days=7)).isoformat()
        got = self.send("decisions", {"decision": "Steering decision on pilot live", "needed_by": needed})
        row = self.s.read("decisions", ref=got["ref"])
        self.assertEqual((row["status"], row["needed_by"], row["decision"]), ("Pending", needed, "Steering decision on pilot live"))
        self.assertRegex(got["ref"], r"^ABC-D-\d{3}$")
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True))
        self.assertIsNone(self.s.read("decisions", ref=got["ref"]))

    def test_a_new_milestone_is_planned_thirty_days_out_and_one_undo_takes_it_away(self):
        agreed = (date.today() + timedelta(days=30)).isoformat()
        got = self.send("milestones", {"name": "New milestone", "baseline_date": agreed, "workstream": "Build"})
        row = self.s.read("milestones", ref=got["ref"])
        self.assertEqual((row["name"], row["baseline_date"], row["status"], row["workstream"]), ("New milestone", agreed, "Planned", "Build"))
        status, undone = self.undo({"project": "ABC", "apply_id": got["apply_id"]})
        self.assertEqual((status, undone["ok"]), (200, True))
        self.assertIsNone(self.s.read("milestones", ref=got["ref"]))


class Head(unittest.TestCase):
    """The head's sentence from the page's own rules (logic/milestones.js headLine), in Chrome."""

    @classmethod
    def setUpClass(cls):
        script = (bundled(MODULE, "MS") + ";\n(" + """(c) => ({
            all: MS.headLine(MS.milestoneRows(c.cases, c.today, false)),
            none: MS.headLine([]),
            cancelled: MS.headLine(MS.milestoneRows(c.cases.filter((x) => x.status === 'Cancelled'), c.today, false)),
            client: MS.headLine(MS.milestoneRows(c.cases, c.today, true)),
        })""" + ")(" + json.dumps({"cases": CASES, "today": TODAY}) + ")")
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            assert "exceptionDetails" not in res, res
            cls.js = res["result"]["value"]

    def test_the_last_milestone_how_many_are_achieved_and_how_many_are_to_come(self):
        live = [c for c in CASES if not c["archived"] and c["status"] != "Cancelled"]
        got = self.js["all"]
        self.assertEqual(got["achieved"] + got["toCome"], len(live))
        self.assertEqual(got["achieved"], sum(1 for c in live if c["status"] == "Done"))
        self.assertTrue(got["name"] and got["date"])

    def test_no_milestones_and_only_cancelled_ones_give_no_sentence(self):
        self.assertIsNone(self.js["none"])
        self.assertIsNone(self.js["cancelled"])

    def test_a_published_file_counts_what_the_file_holds(self):
        live = [c for c in CASES if not c["archived"] and c["status"] != "Cancelled"]
        self.assertLessEqual(self.js["client"]["achieved"] + self.js["client"]["toCome"], len(live))


SEE = """(() => {
  const px = (c) => { const k = document.createElement('canvas').getContext('2d', {willReadFrequently: true}); k.clearRect(0, 0, 1, 1); k.fillStyle = c; k.fillRect(0, 0, 1, 1); return [...k.getImageData(0, 0, 1, 1).data]; };
  const lum = (c) => { const f = (v) => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); };
  const back = (e) => { for (; e; e = e.parentElement) { const c = px(getComputedStyle(e).backgroundColor); if (c[3] === 255) return c; } return [255, 255, 255, 255]; };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const q = (s) => document.querySelector(s), r = (e) => e.getBoundingClientRect();
  const sub = q('#ms-summary'), h1 = q('#milestones h1'), add = q('#addMs'), crumbs = q('#milestones .crumbs');
  return {crumbs: crumbs.textContent, title: h1.textContent, summary: sub.textContent, tag: [crumbs.tagName, h1.tagName, sub.tagName],
          order: r(crumbs).bottom <= r(h1).top + 1 && r(h1).bottom <= r(sub).top + 1,
          ratio: ratio(px(getComputedStyle(sub).color), back(sub)), size: parseFloat(getComputedStyle(sub).fontSize),
          add: add && {w: r(add).width, h: r(add).height, name: add.getAttribute('aria-label'), onScreen: r(add).right <= window.innerWidth && r(add).left >= 0,
                       apart: r(add).left >= r(sub).right - 1 || r(add).top >= r(sub).bottom - 1 || r(add).bottom <= r(h1).top + 1},
          noScroll: document.documentElement.scrollWidth <= window.innerWidth,
          note: q('#mvNote') && {w: r(q('#mvNote')).width, h: r(q('#mvNote')).height, onScreen: r(q('#mvNote')).right <= window.innerWidth && r(q('#mvNote')).left >= 0},
          buttons: [...document.querySelectorAll('.mvm-actions .btn')].map((b) => ({id: b.id, onScreen: r(b).right <= window.innerWidth && r(b).left >= 0, h: r(b).height}))};
})()"""


class Page(Base):
    def test_the_head_is_the_project_the_title_and_one_sentence_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit(cdp, width, theme)
                    p.until("!!document.querySelector('#ms-summary')", "the head drew")
                    self.assertEqual(p.js("!!document.querySelector('#addMs')"), False, "View has no Add milestone")
                    p.js("document.querySelector('[data-mode=edit]').click()")
                    p.until("!!document.querySelector('#addMs')", "Edit draws the button")
                    seen = p.js(SEE)
                    self.assertEqual(seen["crumbs"], "Example Programme")
                    self.assertEqual(seen["title"], "Milestones")
                    self.assertEqual(seen["tag"], ["P", "H1", "P"])
                    self.assertRegex(seen["summary"], r"^.+ is agreed for \d\d-\d\d-\d{4}( and now expected \d\d-\d\d-\d{4})?\. \d+ achieved, \d+ to come\.$")
                    self.assertIn("0 achieved, 2 to come.", seen["summary"])
                    self.assertTrue(seen["order"], "the project, then the title, then the sentence")
                    self.assertGreaterEqual(seen["ratio"], 4.5)
                    self.assertGreaterEqual(seen["size"], 13)
                    self.assertTrue(seen["add"] and seen["add"]["onScreen"] and seen["add"]["apart"], "the Add milestone button sits clear of the head")
                    self.assertEqual(seen["add"]["name"], "Add milestone")
                    self.assertGreaterEqual(min(seen["add"]["w"], seen["add"]["h"]), 24)
                    self.assertTrue(seen["noScroll"], "no page-wide scroll")

    def test_view_has_no_add_milestone_and_sends_no_request_and_going_back_to_view_takes_it_away(self):
        before = {r["id"] for r in self.store.read("milestones")}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.until("!!document.querySelector('#ms-summary')", "the head drew")
            self.assertEqual(p.js("!!document.querySelector('#addMs')"), False, "View has no Add milestone")
            self.assertEqual(self.sent, [], "View sends no request")
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('#addMs')", "Edit draws the button")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("!document.querySelector('#addMs')", "View takes it away again")
            self.assertEqual(self.sent, [], "still no request")
        self.assertEqual({r["id"] for r in self.store.read("milestones")}, before)

    def test_add_milestone_adds_one_thirty_days_out_opens_it_and_one_undo_takes_it_away(self):
        iso, _ = in_days(30)
        before = {r["id"] for r in self.store.read("milestones")}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('#addMs')", "the button is there")
            p.js("document.querySelector('#addMs').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Milestone added. Undo.'", "the toast")
            new = [r for r in self.store.read("milestones") if r["id"] not in before]
            self.assertEqual(len(new), 1)
            self.assertEqual((new[0]["name"], new[0]["baseline_date"], new[0]["workstream"]), ("New milestone", iso, "Build"))
            self.assertEqual(self.sent[-1][1]["place"], "report")
            p.until("!!document.querySelector('#peek') && document.querySelector('#peek').dataset.peek === %s" % json.dumps(new[0]["id"]), "it opens in the peek")
            self.assertIn("New milestone", p.js("document.querySelector('#ms-summary').textContent") + p.js("document.querySelector('#peek').textContent"))
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertIsNone(self.store.read("milestones", ref=new[0]["id"]))

    def test_movement_adds_a_linked_recovery_action_and_a_steering_decision_and_opens_each(self):
        iso, _ = in_days(7)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            self.assertEqual(p.js("[...document.querySelectorAll('.mvm-actions .btn')].map(b => b.textContent)"),
                             ["Hold: keep the forecast, agreed date unchanged", "Move the agreed date", "Add a recovery action", "Escalate to steering"])
            p.js("document.querySelector('#mv-recover').click()")
            p.until("/added and linked to Go live\\. Undo\\.$/.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "the action's toast")
            text = self.toast(p)
            action = self.store.read("actions", ref=text.split(" ")[0])
            self.assertEqual((action["description"], action["priority"], action["due_date"], action["milestone"]), ("Recover go live", "High", iso, GO_LIVE))
            self.assertRegex(action["latest_update"], r"^Go live is \d+ days? behind its agreed date\.$")
            self.assertEqual(action["workstream"], "Build", "the first open workstream (Go live has none of its own)")
            p.until("!!document.querySelector('#peek') && document.querySelector('#peek').dataset.peek === %s" % json.dumps(action["id"]), "the action opens in the peek")
            p.js("document.querySelector('[data-pk-close]').click()")
            p.until("!document.querySelector('#peek')", "the peek closed")
            p.js("document.querySelector('#mv-escalate').click()")
            p.until("/added for Go live\\. Undo\\.$/.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "the decision's toast")
            decision = self.store.read("decisions", ref=self.toast(p).split(" ")[0])
            self.assertEqual((decision["decision"], decision["needed_by"], decision["status"]), ("Steering decision on go live", iso, "Pending"))
            self.assertRegex(decision["reasoning"], r"^Go live is \d+ days? behind its agreed date\.$")
            p.until("!!document.querySelector('#peek') && document.querySelector('#peek').dataset.peek === %s" % json.dumps(decision["id"]), "the decision opens in the peek")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertIsNone(self.store.read("decisions", ref=decision["id"]))

    def test_the_internal_note_saves_when_the_box_is_left_undoes_and_follows_the_row(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            self.assertEqual(p.js("document.querySelector('#mvNote').previousElementSibling.textContent"), "Internal note")
            self.assertEqual(p.js("document.querySelector('#mvNote').placeholder"), "What is going on, what you are waiting for")
            self.assertEqual(p.js("document.querySelector('#mvNote-help').textContent"), "Saves when you leave the box. Never published.")
            self.assertEqual(p.js("document.querySelector('#mvNote').value"), INTERNAL, "the box shows the note the milestone holds")
            before = len(self.sent)
            p.js("document.querySelector('#mvNote').focus(); document.querySelector('#mvNote').blur()")
            self.assertEqual(len(self.sent), before, "leaving the box with no change sends nothing")
            p.js("(() => { const t = document.querySelector('#mvNote'); t.focus(); t.value = 'Waiting for the vendor\\nChase on Friday'; t.dispatchEvent(new Event('input', {bubbles: true})); let n = 0; t.addEventListener('blur', () => n++); t.blur(); if (!n) t.dispatchEvent(new FocusEvent('blur')); })()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Note saved. Undo.'", "the toast")
            self.assertEqual(self.row(GO_LIVE)["internal_note"], "Waiting for the vendor\nChase on Friday")
            self.assertEqual(self.sent[-1][1]["place"], "movement")
            p.until("document.querySelector('#mvNote').value === 'Waiting for the vendor\\nChase on Friday'", "the box keeps what was saved")
            self.assertNotIn("Waiting for the vendor", p.js("document.querySelector('.mvm-list') ? document.querySelector('.mvm-list').textContent : ''"),
                             "What changed never says what the note says")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertEqual(self.row(GO_LIVE)["internal_note"], INTERNAL)
            p.until("document.querySelector('#mvNote').value === %s" % json.dumps(INTERNAL), "the box follows the Undo")
            p.js("document.querySelector('.mvm-row[data-id=\"%s\"]').click()" % PILOT)
            p.until("document.querySelector('#mv-card-h').textContent === 'Pilot live'", "the card follows the row")
            self.assertEqual(p.js("document.querySelector('#mvNote').value"), "", "another milestone, its own note")

    def test_the_movement_buttons_fit_at_both_widths_in_both_themes(self):
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.visit(cdp, width, theme)
                    self.open_movement(p)
                    seen = p.js(SEE)
                    self.assertEqual([b["id"] for b in seen["buttons"]], ["mv-hold", "mv-move", "mv-recover", "mv-escalate"])
                    for b in seen["buttons"]:
                        self.assertTrue(b["onScreen"], b["id"])
                        self.assertGreaterEqual(b["h"], 24, b["id"])
                    self.assertTrue(seen["note"] and seen["note"]["onScreen"], "the note box is on screen")
                    self.assertGreaterEqual(seen["note"]["w"], 200, "the note box is wide enough to write in")
                    self.assertGreaterEqual(seen["note"]["h"], 24)
                    self.assertTrue(seen["noScroll"])

    def test_a_recovery_action_goes_in_an_open_workstream_and_says_so_when_there_is_none(self):
        with self.store.step("dashboard", USER) as st:
            st.create("workstreams", {"project": "ABC", "name": "Run", "source": "demo"})
            st.update("milestones", GO_LIVE, {"workstream": "Build"})
        with self.store.step("dashboard", USER) as st:
            for w in self.store.read("workstreams"):
                if w["name"] == "Build":
                    st.update("workstreams", w["id"], {"status": "Closed"})
        before = {r["id"] for r in self.store.read("actions")}
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-recover').click()")
            p.until("/added and linked to Go live\\. Undo\\.$/.test((document.querySelector('.toast .toast-text') || {}).textContent || '')", "the action's toast")
            new = [r for r in self.store.read("actions") if r["id"] not in before]
            self.assertEqual([(r["workstream"], r["milestone"]) for r in new], [("Run", GO_LIVE)], "Build is closed, so the first open one")
        with self.store.step("dashboard", USER) as st:
            for w in self.store.read("workstreams"):
                st.update("workstreams", w["id"], {"status": "Closed"})
        before = {r["id"] for r in self.store.read("actions")}
        with chrome() as cdp:
            p = self.visit(cdp)
            self.open_movement(p)
            p.js("document.querySelector('#mv-recover').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === %s" % json.dumps(js_words()["NO_WORKSTREAM"]), "the plain refusal")
        self.assertEqual({r["id"] for r in self.store.read("actions")}, before, "nothing was added")


class Published(unittest.TestCase):
    def test_the_file_has_the_head_five_rows_and_show_all_and_nothing_of_the_owner(self):
        demo = DemoStore()
        self.addCleanup(demo.close)
        with demo.store.step("dashboard", USER) as step:
            for n in range(1, 8):
                step.create("milestones", {"project": "ABC", "name": f"Extra {n}", "baseline_date": f"2027-0{n}-10", "client_visible": 1,
                                           "internal_note": INTERNAL, "source": "demo"})
            step.update("milestones", demo.milestone, {"client_visible": 1})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)
        text = Path(done["path"]).read_text(encoding="utf-8")
        for never in (INTERNAL, "internal_note", *OWNERS_WORDS[:7], "/api/change"):
            self.assertNotIn(never, text, never)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
            cdp.js("[...document.querySelectorAll('.tab')].find(t => /Milestones/.test(t.textContent)).click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#ms-summary')", sid)), "the head drew")
            self.assertEqual(cdp.js("document.querySelector('#milestones .crumbs').textContent", sid), "Example Programme")
            self.assertRegex(cdp.js("document.querySelector('#ms-summary').textContent", sid), r"^.+ is agreed for \d\d-\d\d-\d{4}.* \d+ achieved, 8 to come\.$")
            self.assertEqual(cdp.js("!!document.querySelector('#addMs')", sid), False, "a file has no Add milestone")
            self.assertEqual(cdp.js("document.querySelectorAll('.msl-row').length", sid), 5, "the owner's ruling: five rows")
            self.assertEqual(cdp.js("document.querySelector('.msl-all').textContent", sid), "Show all 8 milestones")
            cdp.js("document.querySelector('.msl-all').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('.msl-row').length === 8", sid)), "Show all lists every milestone")
            self.assertEqual(cdp.js("document.querySelector('.msl-all').textContent", sid), "Show the first 5")
            self.assertEqual(cdp.js("document.querySelectorAll('textarea, #mvNote, #mv-recover, #mv-escalate').length", sid), 0)


if __name__ == "__main__":
    unittest.main()
