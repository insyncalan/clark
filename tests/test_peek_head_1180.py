"""Item 1180, the peek's head: the item's ID in a small outlined tag and the project name once under the toolbar, and a title that is edited in
place (a textarea in the title's own font). Run: python3 dev/run_tests.py test_peek_head_1180

Hooks the build must carry: [data-pk-id] (the tag, text is the ID), [data-pk-project] (the project name), and on the title box
textarea[data-pk-title-in] inside h2.pk-title. The title is drawn as text until it is clicked, or reached by Tab and opened with Enter or Space.
Enter commits, Esc cancels, leaving the box commits, a blank or an unchanged title changes nothing, and a change is one request, one
Undo, one Activity line ("You changed Title: old to new") and the toast "Title changed".
Widths 1400 and 900 only.
"""
import json
import unittest

from _paths import ROOT

from clark import activity_read  # noqa: E402
from test_peek import key  # noqa: E402
import test_peek_latest as _tl  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

ACTION = "TUL-A-001"
BOX = "#peek textarea[data-pk-title-in]"
WIDTHS = (1400, 900)


class Head(unittest.TestCase):
    HOLD = _tl.Browser.HOLD
    fresh = _tl.Browser.fresh
    action = _tl.Browser.action
    toast = _tl.Browser.toast

    def setUp(self):
        self.fresh()
        self.live = []

    def load(self, cdp, width, item=ACTION):
        """The loader of test_peek_latest, with the Activity reader switched on (the server it builds is caught as it is made)."""
        made = []
        real = _tl.Running

        def catch(*a, **k):
            s = real(*a, **k)
            made.append(s)
            return s
        _tl.Running = catch
        try:
            sent, sid = _tl.Browser.load(self, cdp, width, item)
        finally:
            _tl.Running = real
        made[-1].httpd.activity = activity_read.make_read(self.store.path, self.store.data_for)
        return sent, sid

    def calm(self, cdp, sid):
        self.assertTrue(wait(lambda: cdp.js("(p => !p || p.getAnimations({subtree: true}).every(a => a.playState !== 'running'))(document.querySelector('#peek'))", sid)),
                        "the peek has stopped moving")

    def value(self, cdp, sid):
        return cdp.js("(t => t ? t.value : null)(document.querySelector('#peek textarea[data-pk-title-in]'))", sid)

    def shown(self, cdp, sid):
        """The title as a reader of the page gets it, in the box or out of it."""
        return cdp.js("(h => { const t = h.querySelector('textarea'); return (t ? t.value : h.textContent).trim(); })(document.querySelector('#peek h2.pk-title'))", sid)

    def focused_box(self, cdp, sid):
        return cdp.js("(a => !!a && a.tagName === 'TEXTAREA' && a.hasAttribute('data-pk-title-in') && !a.readOnly)(document.activeElement)", sid)

    def open_by_click(self, cdp, sid):
        self.calm(cdp, sid)
        click(cdp, sid, "#peek h2.pk-title")
        self.assertTrue(wait(lambda: self.focused_box(cdp, sid)), "a click on the title opens the box with the focus in it")

    def type_title(self, cdp, sid, text):
        """What a person does: take the whole text and type over it."""
        cdp.js("document.querySelector('#peek textarea[data-pk-title-in]').select()", sid)
        cdp.call("Input.insertText", {"text": text}, sid)
        self.assertTrue(wait(lambda: self.value(cdp, sid) == text), "the typed text is in the box")

    def undo_buttons(self, cdp, sid):
        return cdp.js("document.querySelectorAll('.toast [data-undo]').length", sid)

    # ---- the ID tag and the project line

    def test_the_id_is_in_an_outlined_tag_and_the_project_said_once_between_the_toolbar_and_the_title(self):
        project = next(p for p in self.store.read("projects") if p["code"] == self.code)
        name = project.get("name") or project.get("title")
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-id]').length", sid), 1, "one ID tag")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-id]').textContent.trim()", sid), ACTION)
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-project]').length", sid), 1, "the project once")
                self.assertEqual(cdp.js("document.querySelector('#peek [data-pk-project]').textContent.trim()", sid), name)
                outlined = cdp.js("(c => { const s = getComputedStyle(c); return parseFloat(s.borderTopWidth) > 0 && s.borderTopStyle !== 'none' && "
                                  "(s.backgroundColor === 'rgba(0, 0, 0, 0)' || s.backgroundColor === 'transparent'); })(document.querySelector('#peek [data-pk-id]'))", sid)
                self.assertTrue(outlined, "the tag is an outline, not a filled chip")
                order = cdp.js("(() => { const q = (s) => document.querySelector(s), f = Node.DOCUMENT_POSITION_FOLLOWING;"
                               " return [q('#peek .pk-bar').compareDocumentPosition(q('#peek [data-pk-id]')) & f, q('#peek [data-pk-id]').compareDocumentPosition(q('#peek [data-pk-project]')) & f,"
                               " q('#peek [data-pk-project]').compareDocumentPosition(q('#peek h2.pk-title')) & f].map(Boolean); })()", sid)
                self.assertEqual(order, [True, True, True], "toolbar, then the ID, then the project, then the title")
                self.assertFalse(cdp.js("document.querySelector('#peek .pk-bar').textContent.includes(" + json.dumps(ACTION) + ")", sid), "the toolbar no longer carries the ID")
                self.assertFalse(cdp.js("[...document.querySelectorAll('#peek dt')].some(d => /^(Type|Project)$/.test(d.textContent.trim()))", sid),
                                 "the Type and Project rows are not repeated in the details")
                self.assertTrue(cdp.js("(r => r.left >= 0 && r.right <= innerWidth)(document.querySelector('#peek [data-pk-project]').getBoundingClientRect())", sid))

    # ---- opening the title

    def test_a_click_opens_the_title_in_a_box_of_the_same_font_and_size_with_a_brand_ring(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.load(cdp, width)
                self.calm(cdp, sid)
                probe = ("(h => { const e = h.querySelector('textarea') || h, s = getComputedStyle(e), r = h.getBoundingClientRect();"
                         " return {size: s.fontSize, weight: s.fontWeight, family: s.fontFamily, height: Math.round(r.height), width: Math.round(r.width)}; })"
                         "(document.querySelector('#peek h2.pk-title'))")
                before = cdp.js(probe, sid)
                self.open_by_click(cdp, sid)
                after = cdp.js(probe, sid)
                self.assertEqual((after["size"], after["weight"], after["family"]), (before["size"], before["weight"], before["family"]), "the same font")
                self.assertNotIn("mono", after["family"].lower())
                self.assertLessEqual(abs(after["height"] - before["height"]), 2, "the title does not change height when it opens")
                self.assertLessEqual(abs(after["width"] - before["width"]), 2, "the title does not change width when it opens")
                self.assertEqual(self.value(cdp, sid), self.action(ACTION)["description"])
                ring = cdp.js("(s => ({outline: s.outlineStyle + ' ' + s.outlineWidth, shadow: s.boxShadow}))(getComputedStyle(document.querySelector('#peek textarea[data-pk-title-in]')))", sid)
                self.assertTrue(ring["outline"].split()[0] not in ("none",) or ring["shadow"] != "none", "the focused box carries a visible ring")
                self.assertTrue(cdp.js("(r => r.left >= document.querySelector('#peek').getBoundingClientRect().left - 1 && r.right <= document.querySelector('#peek').getBoundingClientRect().right + 1)"
                                       "(document.querySelector('#peek textarea[data-pk-title-in]').getBoundingClientRect())", sid), "the box fits the peek")

    def test_tab_reaches_the_title_and_enter_or_space_opens_it_for_keys_alone(self):
        for opener in ("Enter", " "):
            for width in WIDTHS:
                with self.subTest(opener=repr(opener), width=width), chrome() as cdp:
                    sent, sid = self.load(cdp, width)
                    self.calm(cdp, sid)
                    cdp.js("document.querySelector('#peek [data-pk-close]').focus()", sid)
                    reached = False
                    for _ in range(25):
                        key(cdp, sid, "Tab")
                        if cdp.js("!!document.activeElement && !!document.activeElement.closest('h2.pk-title')", sid):
                            reached = True
                            break
                    self.assertTrue(reached, "Tab reaches the title")
                    self.assertEqual(cdp.js("document.activeElement.tagName === 'TEXTAREA' && !document.activeElement.hasAttribute('data-pk-title-in')", sid), False)
                    key(cdp, sid, opener)
                    self.assertTrue(wait(lambda: self.focused_box(cdp, sid)), "the key opens the box with the focus in it")
                    self.assertEqual(sent, [], "opening is not a change")
                    self.assertEqual(self.value(cdp, sid), self.action(ACTION)["description"], "the key did not type into the title")

    # ---- committing and cancelling

    def test_enter_commits_with_one_request_one_undo_one_activity_line_and_the_toast(self):
        was = self.action(ACTION)["description"]
        new = "Confirm the pilot go-live checklist"
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width)
                self.open_by_click(cdp, sid)
                self.type_title(cdp, sid, new)
                key(cdp, sid, "Enter")
                self.assertTrue(wait(lambda: len(sent) == 1), "one change is one request")
                self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), ("actions", ACTION, {"description": new}))
                self.assertEqual(self.value(cdp, sid) if self.value(cdp, sid) is not None else new, new, "Enter makes no new line")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == new))
                self.assertNotIn("\n", self.shown(cdp, sid))
                self.assertTrue(wait(lambda: self.toast(cdp, sid).strip().startswith("Title changed")), "the toast says Title changed")
                self.assertTrue(wait(lambda: self.undo_buttons(cdp, sid) == 1), "the toast carries one Undo")
                self.assertTrue(wait(lambda: cdp.js("!!document.activeElement && document.activeElement.closest('#peek') !== null", sid)), "focus stays in the peek")
                # the Activity line
                click(cdp, sid, "[data-pk-tab=activity]")
                self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-activity-row]').length", sid) > 0))
                first = cdp.js("document.querySelector('[data-activity-row]').textContent", sid)
                self.assertIn("You changed Title", first)
                self.assertIn(was, first)
                self.assertIn(new, first)
                self.assertEqual(cdp.js("[...document.querySelectorAll('[data-activity-row]')].filter(r => r.textContent.includes('You changed Title')).length", sid), 1, "one line")
                # one Undo puts it all back
                cdp.js("document.querySelector('.toast [data-undo]').click()", sid)
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == was), "one Undo puts the old title back")
                self.assertEqual(len(sent), 1, "Undo is not a second change request")

    def test_escape_cancels_and_leaves_the_peek_open(self):
        was = self.action(ACTION)["description"]
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width)
                self.open_by_click(cdp, sid)
                self.type_title(cdp, sid, "Typed and abandoned")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == was), "the old title is back")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "Esc cancelled the edit only; the peek stays")
                self.assertTrue(wait(lambda: cdp.js("!!document.activeElement && document.activeElement.closest('#peek') !== null", sid)), "focus stays in the peek")
                self.assertEqual(sent, [])
                self.assertEqual(self.toast(cdp, sid).strip(), "")

    def test_leaving_the_box_commits(self):
        new = "Saved by leaving the box"
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width)
                self.open_by_click(cdp, sid)
                self.type_title(cdp, sid, new)
                click(cdp, sid, "#peek [data-pk-id]")
                self.assertTrue(wait(lambda: len(sent) == 1 and sent[0]["changes"] == {"description": new}), "blur is a commit")
                self.assertTrue(wait(lambda: self.shown(cdp, sid) == new))
                self.assertTrue(wait(lambda: self.toast(cdp, sid).strip().startswith("Title changed")))
                self.assertEqual(len(sent), 1, "one request, not one for the blur and one for something else")

    def test_a_blank_or_an_unchanged_title_changes_nothing(self):
        was = self.action(ACTION)["description"]
        for how in ("Enter", "blur"):
            for case in ("blank", "unchanged", "spaces around"):
                with self.subTest(how=how, case=case), chrome() as cdp:
                    sent, sid = self.load(cdp, 1400)
                    self.open_by_click(cdp, sid)
                    if case == "blank":
                        self.type_title(cdp, sid, " ")
                    elif case == "spaces around":
                        self.type_title(cdp, sid, "  " + was + "  ")
                    if how == "Enter":
                        key(cdp, sid, "Enter")
                    else:
                        click(cdp, sid, "#peek [data-pk-id]")
                    wait(lambda: False, 1)           # give a wrong request time to leave
                    self.assertEqual(sent, [], "nothing was sent")
                    self.assertEqual(self.undo_buttons(cdp, sid), 0, "no Undo to offer")
                    self.assertNotIn("Title changed", self.toast(cdp, sid))
                    self.assertTrue(wait(lambda: self.shown(cdp, sid) == was or self.value(cdp, sid) is not None), "the title reads as before")
                    self.assertEqual(self.action(ACTION)["description"], was)

    def test_the_title_is_plain_in_view(self):
        """A reader without Edit gets the heading and no box, and a click on it opens nothing."""
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = _tl.Browser.load(self, cdp, width, ACTION, edit=False)
                self.calm(cdp, sid)
                self.assertEqual(cdp.js("document.querySelectorAll('#peek textarea').length", sid), 0)
                self.assertEqual(cdp.js("document.querySelectorAll('#peek [data-pk-id]').length", sid), 1, "the ID tag is in View too")
                click(cdp, sid, "#peek h2.pk-title")
                self.assertEqual(cdp.js("document.querySelectorAll('#peek textarea').length", sid), 0)
                self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
