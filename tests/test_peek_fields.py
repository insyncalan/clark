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
    inside = _tl.Browser.inside

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


BOX_PK = "#peek [data-ce]"


if __name__ == "__main__":
    unittest.main()
