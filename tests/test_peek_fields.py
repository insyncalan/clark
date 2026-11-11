"""The peek's inline fields (row 829): the title, the client wording and the Workstream, Milestone and Use case choices of a work item,
changed in place in the peek, each one request and one Undo. Run: python3 dev/run_tests.py test_peek_fields

The server already takes these fields (clark/changes.py CHANGE_KINDS), so every test here is the page: 1400 and 900 px, light and dark,
and the source rule that a published file carries none of it.
"""
import json
import unittest

from _paths import ROOT

from test_peek import key  # noqa: E402
import test_peek_latest as _tl  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

ACTION = "TUL-A-001"
SRC = ROOT / "src/clark/page/src"


class Fields(unittest.TestCase):
    """The page loader of test_peek_latest, borrowed (not inherited, so its own tests are not run twice)."""
    HOLD = _tl.Browser.HOLD
    fresh = _tl.Browser.fresh
    load = _tl.Browser.load
    action = _tl.Browser.action
    toast = _tl.Browser.toast
    _inside_now = _tl.Browser.inside

    def calm(self, cdp, sid):
        """Wait until the peek (it slides in) and everything in it has stopped moving: a box measured, or a button clicked, mid-slide is
        somewhere else a moment later (a slow runner draws the slide late)."""
        self.assertTrue(wait(lambda: cdp.js("(p => !p || p.getAnimations({subtree: true}).every(a => a.playState !== 'running'))(document.querySelector('#peek'))", sid)),
                        "the peek has stopped moving")

    def inside(self, cdp, sid, selector):
        """Whether the box fits the peek, asked once the peek has settled and for as long as it takes to hold (the answer is still read last)."""
        self.calm(cdp, sid)
        wait(lambda: self._inside_now(cdp, sid, selector))
        return self._inside_now(cdp, sid, selector)

    def setUp(self):
        self.fresh()

    def widths(self):
        return [(w, dark) for w in (1400, 900) for dark in (False, True)]

    def title(self, cdp, sid):
        return cdp.js("(t => t ? t.textContent : '')(document.querySelector('#peek [data-pk-title-in]'))", sid)

    def type_title(self, cdp, sid, text):
        cdp.js("document.querySelector('#peek [data-pk-title-in]').focus()", sid)
        cdp.js(f"document.querySelector('#peek [data-pk-title-in]').textContent = {json.dumps(text)}", sid)


class Title(Fields):
    def test_the_title_is_changed_in_place_with_enter_and_undone_in_one_step(self):
        was = self.action(ACTION)["description"]
        for width, dark in self.widths():
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                sent, sid = self.load(cdp, width, ACTION, dark=dark)
                self.assertEqual(self.title(cdp, sid), was)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-title-in]"), "the title box fits the peek")
                self.type_title(cdp, sid, "A new title for this action")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: len(sent) == 1))
                self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", ACTION, {"description": "A new title for this action"}))
                self.assertTrue(wait(lambda: self.title(cdp, sid) == "A new title for this action"))
                self.assertTrue(wait(lambda: f"Title of {ACTION} changed." in self.toast(cdp, sid)))
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.title(cdp, sid) == was), "one Undo puts the old title back")

    def test_escape_puts_the_title_back_and_an_empty_title_is_put_back_in_words(self):
        was = self.action(ACTION)["description"]
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ACTION)
            self.type_title(cdp, sid, "Typed and abandoned")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == was))
            self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "Esc leaves the peek open")
            self.type_title(cdp, sid, "   ")
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: self.title(cdp, sid) == was))
            self.assertTrue(wait(lambda: "A title can't be blank" in self.toast(cdp, sid)))
            self.assertEqual(sent, [], "nothing was sent")

    def test_a_click_away_saves_the_title(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ACTION)
            self.type_title(cdp, sid, "Saved by clicking away")
            click(cdp, sid, "#peek [data-pk-close]")
            self.assertTrue(wait(lambda: len(sent) == 1 and sent[0]["changes"] == {"description": "Saved by clicking away"}))

    def test_the_title_is_plain_in_a_published_file_and_in_view(self):
        peek = (SRC / "components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && forItem && tools.PeekTitle", peek)
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        self.assertNotIn("data-pk-title-in", view)


class Wording(Fields):
    BOX = "#peek [data-ce]"

    def words(self, cdp, sid):
        return cdp.js(f"(t => t ? t.textContent : null)(document.querySelector({json.dumps(self.BOX)}))", sid)

    def type_words(self, cdp, sid, text):
        cdp.js(f"document.querySelector({json.dumps(self.BOX)}).focus()", sid)
        cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent = {json.dumps(text)}", sid)

    def test_the_client_wording_is_changed_in_place_and_undone_in_one_step(self):
        was = (self.action(ACTION).get("client_message") or "").strip()
        for width, dark in self.widths():
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                sent, sid = self.load(cdp, width, ACTION, dark=dark)
                self.assertEqual(cdp.js("document.querySelector('#peek [data-ce]').closest('.pk-row').querySelector('dt').textContent", sid), "Client wording")
                self.assertEqual(self.words(cdp, sid), was)
                self.assertTrue(self.inside(cdp, sid, BOX_PK), "the box fits the peek")
                self.type_words(cdp, sid, "Plain words a client can read")
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: len(sent) == 1))
                self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", ACTION, {"client_message": "Plain words a client can read"}))
                self.assertTrue(wait(lambda: f"Wording of {ACTION} changed." in self.toast(cdp, sid)))
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.words(cdp, sid) == was), "one Undo puts the old words back")

    def test_escape_and_an_empty_text_put_the_old_words_back(self):
        was = (self.action(ACTION).get("client_message") or "").strip()
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ACTION)
            self.type_words(cdp, sid, "Typed and abandoned")
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: self.words(cdp, sid) == was))
            self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "Esc leaves the peek open")
            self.type_words(cdp, sid, "x" * 201)
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: "200 characters at most" in self.toast(cdp, sid)))
            self.assertEqual((sent, self.words(cdp, sid)), ([], was))

    def test_the_wording_box_is_edit_only(self):
        peek = (SRC / "components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && tools.PeekWording", peek)
        self.assertNotIn("pk-ce", (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8"))


class Picks(Fields):
    def shown(self, cdp, sid, field):
        return cdp.js(f"(b => b ? b.textContent : null)(document.querySelector('#peek [data-pk-pick={field}]'))", sid)

    def test_workstream_milestone_and_use_case_are_chosen_in_the_peek_each_with_one_undo(self):
        a = self.action(ACTION)
        other_ws = next(w["name"] for w in self.data["workstreams"] if w["name"] != a["workstream"] and w["status"] != "Closed" and not w.get("archived"))
        other_ms = next(m for m in self.data["milestones"] if m["id"] != a["milestone"] and not m.get("archived"))
        other_uc = next(u for u in self.data["use_cases"] if u["id"] != a["use_case"] and not u.get("archived"))
        cases = [("workstream", other_ws, other_ws, "Workstream"), ("milestone", other_ms["id"], other_ms["name"], "Milestone"),
                 ("use_case", other_uc["id"], f"Use case {other_uc['ref']}", "Use case")]
        for width, dark in self.widths():
            for field, value, words, name in cases:
                with self.subTest(width=width, dark=dark, field=field), chrome() as cdp:
                    sent, sid = self.load(cdp, width, ACTION, dark=dark)
                    was = self.shown(cdp, sid, field)
                    self.assertTrue(self.inside(cdp, sid, f"[data-pk-pick={field}]"), "the button fits the peek")
                    click(cdp, sid, f"#peek [data-pk-pick={field}]")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu] [role=menuitemradio]')", sid)))
                    self.assertTrue(cdp.js("document.querySelector('[role=menu]').contains(document.activeElement)", sid), "the focus is in the list")
                    cdp.js("[...document.querySelectorAll('[role=menu] [data-value]')].find(b => b.dataset.value === " + json.dumps(value) + ").click()", sid)     # by script: a long list may reach below the window
                    self.assertTrue(wait(lambda: len(sent) == 1))
                    self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", ACTION, {field: value}))
                    self.assertTrue(wait(lambda: self.shown(cdp, sid, field) == words))
                    self.assertTrue(wait(lambda: (f"{ACTION}: use case changed to {other_uc['ref']}." if field == "use_case" else f"{name} of {ACTION} changed to {words}.") in self.toast(cdp, sid)))
                    if field == "use_case":
                        self.assertNotIn("Use case of", self.toast(cdp, sid))
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)))
                    cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                    self.assertTrue(wait(lambda: self.shown(cdp, sid, field) == was), "one Undo puts it back")

    def test_none_clears_a_choice_and_escape_leaves_it_as_it_was(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ACTION)
            was = self.shown(cdp, sid, "milestone")
            click(cdp, sid, "#peek [data-pk-pick=milestone]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            key(cdp, sid, "Escape")
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[role=menu]')", sid)))
            self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "Esc leaves the peek open")
            self.assertEqual((sent, self.shown(cdp, sid, "milestone")), ([], was))
            click(cdp, sid, "#peek [data-pk-pick=milestone]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            cdp.js("document.querySelector(\"[role=menu] [data-value='']\").click()", sid)
            self.assertTrue(wait(lambda: len(sent) == 1 and sent[0]["changes"] == {"milestone": None}))
            self.assertTrue(wait(lambda: self.shown(cdp, sid, "milestone") == "No milestone"))

    def test_the_none_choice_of_a_use_case_says_cleared(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ACTION)
            click(cdp, sid, "#peek [data-pk-pick=use_case]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menu]')", sid)))
            cdp.js("document.querySelector(\"[role=menu] [data-value='']\").click()", sid)
            self.assertTrue(wait(lambda: f"Use case of {ACTION} cleared." in self.toast(cdp, sid)))
            self.assertTrue(wait(lambda: sent and sent[0]["changes"] == {"use_case": None}))

    def test_a_decision_has_a_use_case_choice_and_no_workstream_or_milestone_choice(self):
        ref = self.data["decisions"][0]["id"]
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, ref)
            self.assertEqual(cdp.js("[...document.querySelectorAll('#peek [data-pk-pick]')].map(b => b.dataset.pkPick)", sid), ["use_case"])

    def test_the_choices_are_edit_only(self):
        peek = (SRC / "components/Peek.jsx").read_text(encoding="utf-8")
        self.assertIn("editing && tools.PeekPick", peek)
        self.assertNotIn("data-pk-pick", (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8"))


class Duplicate(Fields):
    def test_duplicate_in_the_peek_adds_a_copy_opens_it_and_one_undo_takes_it_back(self):
        a = self.action(ACTION)
        before = len(self.data["actions"])
        for width, dark in self.widths():
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                sent, sid = self.load(cdp, width, ACTION, dark=dark)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-dup]"), "the button fits the peek")
                self.calm(cdp, sid)
                click(cdp, sid, "#peek [data-pk-dup]")
                self.assertTrue(wait(lambda: len(sent) == 1))
                self.assertEqual((sent[0]["kind"], sent[0]["op"], sent[0]["copy_of"]), ("actions", "new", ACTION))
                self.assertEqual(sent[0]["values"], {"description": a["description"] + " (copy)"})
                self.assertTrue(wait(lambda: f"a copy of {ACTION}." in self.toast(cdp, sid)))
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('#peek').dataset.peek", sid) != ACTION), "the copy opens in the peek")
                self.assertTrue(wait(lambda: len(self.store.data_for(self.code)["actions"]) == before + 1))
                self.assertEqual(len(self.store.data_for(self.code)["actions"]), before + 1)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)))
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: len(self.store.data_for(self.code)["actions"]) == before), "one Undo takes the copy back")

    def test_the_button_is_edit_only(self):
        self.assertIn("editing && forItem && tools.PeekDuplicate", (SRC / "components/Peek.jsx").read_text(encoding="utf-8"))
        self.assertNotIn("data-pk-dup", (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8"))


class Archive(Fields):
    def row(self, ref):
        return next(a for a in self.store.read("actions", self.code) if a["id"] == ref)

    def test_archive_in_the_peek_hides_the_item_closes_the_peek_and_one_undo_brings_it_back(self):
        for width, dark in self.widths():
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                sent, sid = self.load(cdp, width, ACTION, dark=dark)
                self.assertTrue(self.inside(cdp, sid, "[data-pk-archive]"), "the button fits the peek")
                self.calm(cdp, sid)
                click(cdp, sid, "#peek [data-pk-archive]")
                self.assertTrue(wait(lambda: len(sent) == 1))
                self.assertEqual((sent[0]["kind"], sent[0]["op"], sent[0]["id"]), ("actions", "archive", ACTION))
                self.assertTrue(wait(lambda: f"{ACTION} archived. It is out of the lists and the published page." in self.toast(cdp, sid)))
                self.assertTrue(wait(lambda: self.row(ACTION)["archived"] == 1))
                self.assertEqual(self.row(ACTION)["archived"], 1)
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)), "the peek closes with the item")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.toast [data-undo]')", sid)))
                self.assertTrue(wait(lambda: cdp.js("document.activeElement === document.querySelector('.toast [data-undo]')", sid)), "the focus is on Undo")
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.row(ACTION)["archived"] == 0), "one Undo brings it back")

    def test_the_button_is_edit_only(self):
        self.assertIn("editing && forItem && tools.PeekArchive", (SRC / "components/Peek.jsx").read_text(encoding="utf-8"))
        self.assertNotIn("data-pk-archive", (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8"))


BOX_PK = "#peek [data-ce]"


if __name__ == "__main__":
    unittest.main()
