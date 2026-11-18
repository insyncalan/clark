"""Item 1180, the peek's body (Layout A of the approved mockup): the Latest update above Details, Cmd/Ctrl+Enter saves with its hint, Details is a
collapsible line, the history tabs (All, Activity, Updates, Source) and the footer. Written first: every test fails until the body is built.
Run: python3 dev/run_tests.py test_peek_body_1180

The page is a real browser at 1400 and 900 px in Edit, on the fictional demo project (TUL-A-002 is an action with a source-less history of
its own changes). The hooks the build must give (named here so the build and the test agree):
  [data-pk-latest]            the Latest update block (exists today); [data-pk-hint] the Cmd/Ctrl+Enter hint under its box
  [data-pk-details]           the Details toggle button (aria-expanded, aria-controls); [data-pk-details-rows] the open rows;
                              [data-pk-details-sum] the one summary line shown while closed
  [data-pk-htabs] with [data-pk-htab=all|activity|updates|source] (role=tab, aria-selected), each text ending in its count
  [data-pk-hrow=activity|update|source] the history rows; [data-pk-open-source] the 'Open source' link
  [data-pk-foot] holding a <kbd>//</kbd> and the input [data-pk-ask]
  [data-pk-unsaved] the bar for an unsaved update, with [data-pk-save-close], [data-pk-discard], [data-pk-keep]
"""
import json
import re
import time
import unittest

from _paths import ROOT

import test_peek_latest  # noqa: E402
from test_peek_latest import OVERDUE  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

PEEK = ROOT / "src/clark/page/src/components/Peek.jsx"


class Body(test_peek_latest.Browser):
    """The same loader as the Latest update tests (demo data, today fixed at 28-10-2026, Edit mode); only the tests differ."""

    def q(self, cdp, sid, expr):
        return cdp.js(expr, sid)

    def top(self, cdp, sid, selector):
        return cdp.js(f"(e => e ? e.getBoundingClientRect().top : null)(document.querySelector({json.dumps(selector)}))", sid)

    def expanded(self, cdp, sid):
        return cdp.js("document.querySelector('[data-pk-details]').getAttribute('aria-expanded')", sid)

    def tab(self, cdp, sid, name):
        return cdp.js(f"(t => t ? [t.textContent.trim(), t.getAttribute('aria-selected')] : null)(document.querySelector('[data-pk-htab={name}]'))", sid)

    def tabs(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('[data-pk-htabs] [data-pk-htab]')].map(t => t.dataset.pkHtab)", sid)

    def until(self, cdp, sid, what, expr, seconds=15):
        """Wait for a page expression to be true; fails naming `what` was not reached (never hangs: wait() has a limit)."""
        self.assertTrue(wait(lambda: cdp.js(expr, sid), seconds), f"not reached within {seconds} s: {what}")

    def press(self, cdp, sid, selector, seconds=15):
        """A real mouse press on `selector`, sent only when its centre is settled: the same rect on two looks 50 ms apart (PeekUnsavedBar scrolls
        the body after it paints) and the topmost element at that point is the target, so it is clear of the sticky toolbar."""
        sel = json.dumps(selector)
        probe = (f"(e => {{ if (!e) return null; const r = e.getBoundingClientRect(), x = r.x + r.width / 2, y = r.y + r.height / 2, t = document.elementFromPoint(x, y);"
                 f" return {{x, y, box: [r.x, r.y, r.width, r.height], top: !!t && e.contains(t)}}; }})(document.querySelector({sel}))")
        seen = []

        def settled():
            a = cdp.js(probe, sid)
            time.sleep(0.05)                      # about three frames
            b = cdp.js(probe, sid)
            seen.append(b)
            return bool(a and b) and a["box"] == b["box"] and a["top"] and b["top"]
        self.assertTrue(wait(settled, seconds), f"not reached within {seconds} s: {selector} at rest and clear of the toolbar (last look: {seen[-1] if seen else None})")
        r = seen[-1]
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": r["x"], "y": r["y"]}, sid)
        for kind in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": r["x"], "y": r["y"], "button": "left", "clickCount": 1}, sid)

    def test_the_latest_update_sits_above_details_and_both_above_the_history(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                latest, details, hist = (self.top(cdp, sid, s) for s in ("[data-pk-latest]", "[data-pk-details]", "[data-pk-htabs]"))
                self.assertTrue(None not in (latest, details, hist), (latest, details, hist))
                self.assertLess(latest, details, "the Latest update comes before Details")
                self.assertLess(details, hist, "Details comes before the history")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-details]") and self.inside(cdp, sid, "[data-pk-htabs]"), "both fit the peek")

    def test_the_footer_in_the_box_names_the_save_key_and_is_shown_before_the_box_opens(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.until(cdp, sid, "the footer [data-pk-hint] shown with the box closed (row 1257)", "!!document.querySelector('[data-pk-hint]')")
                self.open_box(cdp, sid)
                hint = cdp.js("(document.querySelector('[data-pk-hint]') || {textContent: ''}).textContent", sid)
                self.assertRegex(hint, r"⌘ Enter to save", "the footer names the key")
                self.assertGreater(self.top(cdp, sid, "[data-pk-hint]"), self.top(cdp, sid, self.BOX), "the footer sits under the text")

    def test_ctrl_or_cmd_enter_saves_once_and_a_plain_enter_makes_a_new_line(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "First line")
                for kind in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "Enter", "code": "Enter", "windowsVirtualKeyCode": 13, **({"text": "\r"} if kind == "keyDown" else {})}, sid)
                self.type_in(cdp, sid, "Second line")
                self.assertEqual(sent, [], "a plain Enter saves nothing")
                self.assertGreaterEqual(cdp.js(f"document.querySelector({json.dumps(self.BOX)}).querySelectorAll('p').length", sid), 2, "a plain Enter is a new line")
                self.save_key(cdp, sid)
                self.assertTrue(wait(lambda: len(sent) == 1), "the key saves, once")
                self.assertIn("First line", sent[0]["changes"]["latest_update"])
                self.assertIn("Second line", sent[0]["changes"]["latest_update"])
                self.assertTrue(wait(lambda: "Second line" in cdp.js(f"(document.querySelector({json.dumps(self.SHOWN)}) || {{textContent: ''}}).textContent", sid)))

    def test_closing_with_an_unsaved_update_asks_and_each_answer_does_what_it_says(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Not yet saved")
                cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "the bar appears")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays open under it")
                bar = cdp.js("document.querySelector('[data-pk-unsaved]').textContent", sid)
                for words in ("You have an unsaved update.", "Save and close", "Discard", "Keep editing"):
                    self.assertIn(words, bar)
                self.assertEqual(sent, [], "nothing is sent while it asks")
                cdp.js("document.querySelector('[data-pk-keep]').click()", sid)           # Keep editing: bar gone, text and peek stay
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)))
                self.assertIn("Not yet saved", cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent", sid))
                cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)))
                cdp.js("document.querySelector('[data-pk-discard]').click()", sid)         # Discard: closes, nothing sent
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)))
                self.assertEqual(sent, [])

    def test_the_mouse_on_the_bar_keeps_the_editor_so_discard_stores_nothing_and_keep_editing_stays(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Not yet saved")

                self.press(cdp, sid, "#peek [data-pk-close]")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "the mouse on Close shows the bar")
                self.assertEqual(sent, [], "Close with the mouse saved nothing")
                self.press(cdp, sid, "[data-pk-keep]")
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)))
                self.assertIn("Not yet saved", cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent", sid), "the editor is open with the text")
                self.until(cdp, sid, "the focus back in the editor after Keep editing", "document.activeElement.classList.contains('ProseMirror')")
                self.assertEqual(sent, [], "Keep editing saved nothing")
                self.press(cdp, sid, "#peek [data-pk-close]")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-discard]')", sid)))
                self.press(cdp, sid, "[data-pk-discard]")
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)))
                self.assertEqual(sent, [], "Discard with the mouse stores nothing")

    def test_esc_with_an_unsaved_update_shows_the_bar_and_does_not_close(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Not yet saved")
                # Esc aimed at the page (not the editor, which keeps Esc for itself): the peek asks, like its Close button
                cdp.js("document.body.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true, cancelable: true}))", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "Esc shows the bar")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays open under it")
                bar = cdp.js("document.querySelector('[data-pk-unsaved]').textContent", sid)
                for words in ("Save and close", "Discard", "Keep editing"):
                    self.assertIn(words, bar)
                self.assertEqual(sent, [], "nothing is sent while it asks")

    def test_save_and_close_saves_one_change_and_then_closes(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Saved on the way out")
                cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-save-close]')", sid)))
                cdp.js("document.querySelector('[data-pk-save-close]').click()", sid)
                self.assertTrue(wait(lambda: len(sent) == 1), "one request")
                self.assertIn("Saved on the way out", sent[0]["changes"]["latest_update"])
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)), "then the peek closes")
                self.assertTrue(wait(lambda: "saved" in self.toast(cdp, sid).lower()), "the toast says it is saved")

    def test_save_and_close_with_a_refused_save_keeps_the_peek_and_the_text(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE, refuse=True)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Refused on the way out")
                cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-save-close]')", sid)))
                cdp.js("document.querySelector('[data-pk-save-close]').click()", sid)
                self.assertTrue(wait(lambda: len(sent) >= 1), "the save was tried")
                self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid)), "the bar steps aside")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "the peek stays open")
                self.assertIn("Refused on the way out", cdp.js(f"(document.querySelector({json.dumps(self.BOX)}) || {{textContent: ''}}).textContent", sid), "the editor keeps the text")

    def test_a_peek_with_nothing_unsaved_closes_without_asking(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            cdp.js("document.querySelector('#peek [data-pk-close]').click()", sid)
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek')", sid)))
            self.assertFalse(cdp.js("!!document.querySelector('[data-pk-unsaved]')", sid))

    def test_details_is_a_collapsible_line_with_a_summary_when_closed(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                btn = "[data-pk-details]"
                self.assertEqual(cdp.js(f"document.querySelector({json.dumps(btn)}).tagName", sid), "BUTTON", "a real button: Tab and Enter work")
                self.assertIn("Details", cdp.js(f"document.querySelector({json.dumps(btn)}).textContent", sid))
                self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(btn)} + ' svg, ' + {json.dumps(btn)} + ' [data-icon]')", sid) or cdp.js(f"!!document.querySelector({json.dumps(btn)}).querySelector('svg')", sid), "the chevron")
                if self.expanded(cdp, sid) == "true":                                    # start from closed
                    click(cdp, sid, btn)
                    self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "false"))
                self.assertTrue(cdp.js("(s => !!s && s.textContent.trim().length > 0)(document.querySelector('[data-pk-details-sum]'))", sid), "closed: one summary line")
                self.assertFalse(cdp.js("!!document.querySelector('[data-pk-details-rows]')", sid), "closed: no rows")
                summary = cdp.js("document.querySelector('[data-pk-details-sum]').textContent", sid)
                self.assertIn("Raised", summary, "the summary names Raised")
                self.assertRegex(summary, r"Client (visible|not visible)|Client-visible|Not client-visible")
                click(cdp, sid, btn)
                self.assertTrue(wait(lambda: self.expanded(cdp, sid) == "true"))
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-details-rows]')", sid)), "open: the rows")
                self.assertFalse(cdp.js("!!document.querySelector('[data-pk-details-sum]')", sid), "open: the summary gives way to the rows")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-details-rows]"))

    def test_details_opens_and_closes_from_the_keyboard(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 1400, OVERDUE)
            cdp.js("document.querySelector('[data-pk-details]').focus()", sid)
            before = self.expanded(cdp, sid)
            from test_peek import key
            key(cdp, sid, "Enter")
            self.assertTrue(wait(lambda: self.expanded(cdp, sid) != before), "Enter toggles it")
            self.assertTrue(cdp.js("document.activeElement.hasAttribute('data-pk-details')", sid), "the focus stays on the line")

    def test_the_history_has_four_tabs_in_order_each_with_a_count_and_one_selected(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.assertEqual(self.tabs(cdp, sid), ["all", "activity", "updates", "source"])
                self.assertEqual(cdp.js("document.querySelector('[data-pk-htabs]').getAttribute('role')", sid), "tablist")
                self.until(cdp, sid, "the history read arrived (the activity list is no longer aria-busy)", "(a => !!a && a.getAttribute('aria-busy') === 'false')(document.querySelector('[data-activity]'))")
                for name, word in (("all", "All"), ("activity", "Activity"), ("updates", "Updates"), ("source", "Source")):
                    text, _ = self.tab(cdp, sid, name)
                    self.assertRegex(text, rf"^{word}\s*\d+$", f"{word} ends in its count")
                self.assertEqual([self.tab(cdp, sid, n)[1] for n in ("all", "activity", "updates", "source")], ["true", "false", "false", "false"], "All is first")
                counts = {n: int(re.search(r"\d+$", self.tab(cdp, sid, n)[0]).group()) for n in ("all", "activity", "updates", "source")}
                self.assertEqual(counts["all"], counts["activity"] + counts["updates"] + counts["source"], "All is the sum of the others")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-htabs]"), "four tabs fit the peek")

    def test_a_tab_shows_only_its_own_rows_with_its_own_icon_and_arrow_keys_move_between_tabs(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "A line for the history")
                self.save_key(cdp, sid)
                self.assertTrue(wait(lambda: len(sent) == 1))
                kinds = lambda: cdp.js("[...new Set([...document.querySelectorAll('[data-pk-hrow]')].map(r => r.dataset.pkHrow))].sort()", sid)
                self.assertTrue(wait(lambda: "update" in kinds()), "the saved update is in All")
                click(cdp, sid, "[data-pk-htab=updates]")
                self.assertTrue(wait(lambda: self.tab(cdp, sid, "updates")[1] == "true"))
                self.assertEqual(kinds(), ["update"], "Updates shows update rows only")
                self.assertIn("A line for the history", cdp.js("document.querySelector('[data-pk-hrow=update]').textContent", sid))
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-hrow=update] svg')", sid), "each update row carries its icon")
                click(cdp, sid, "[data-pk-htab=activity]")
                self.assertTrue(wait(lambda: self.tab(cdp, sid, "activity")[1] == "true"))
                self.assertNotIn("update", kinds())
                self.assertTrue(cdp.js("[...document.querySelectorAll('[data-pk-hrow=activity]')].every(r => !!r.querySelector('svg'))", sid), "activity rows carry the clock")
                cdp.js("document.querySelector('[data-pk-htab=activity]').focus()", sid)
                from test_peek import key
                key(cdp, sid, "ArrowRight")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.pkHtab", sid) == "updates"), "ArrowRight moves along the tabs")
                click(cdp, sid, "[data-pk-htab=all]")
                self.assertTrue(wait(lambda: self.tab(cdp, sid, "all")[1] == "true"))
                self.assertGreaterEqual(len(kinds()), 1)

    def test_the_source_tab_reads_as_one_sentence_with_open_source_and_the_path_as_hover_text(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, "TUL-A-001")
                wait(lambda: not re.search(r"0$", self.tab(cdp, sid, "source")[0]))      # the counts arrive with the history read
                text, _ = self.tab(cdp, sid, "source")
                if re.search(r"0$", text):
                    self.skipTest("the demo item has no source")
                click(cdp, sid, "[data-pk-htab=source]")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-pk-hrow=source]')", sid)))
                row = cdp.js("(r => ({text: r.textContent.trim(), title: r.getAttribute('title') || (r.querySelector('[title]') || {}).title || ''}))(document.querySelector('[data-pk-hrow=source]'))", sid)
                self.assertIn(" · ", row["text"], "the source is one sentence with the middle dots")
                self.assertIn("Open source", row["text"])
                self.assertTrue(row["title"], "the full file path is the hover text")
                self.assertTrue(cdp.js("!!document.querySelector('[data-pk-open-source]')", sid))

    def test_the_footer_has_the_key_tag_and_the_ask_input_and_the_slash_key_types_in_it(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.load(cdp, width, OVERDUE)
                self.assertEqual(cdp.js("(k => k ? k.textContent.trim() : null)(document.querySelector('[data-pk-foot] kbd'))", sid), "//")
                self.assertEqual(cdp.js("document.querySelector('[data-pk-foot] [data-pk-ask]').getAttribute('placeholder')", sid), "ask clark to update")
                self.assertTrue(self.inside(cdp, sid, "[data-pk-foot]"))
                cdp.js("[document.querySelector('#peek'), document.querySelector('#peek [data-pk-body]')].forEach(s => { if (s) s.scrollTop = s.scrollHeight; })", sid)
                self.assertGreater(self.top(cdp, sid, "[data-pk-foot]"), self.top(cdp, sid, "[data-pk-htabs]"), "the footer is below the history")
                self.assertFalse(cdp.js("document.activeElement.hasAttribute('data-pk-ask')", sid))
                cdp.js("document.querySelector('#peek [data-pk-close]').focus()", sid)
                from test_peek import key
                key(cdp, sid, "/")
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-ask')", sid)), "pressing / puts the cursor in the input")

    def test_the_footer_stays_in_view_while_the_body_scrolls(self):
        with chrome() as cdp:
            sent, sid = self.load(cdp, 900, OVERDUE)
            cdp.js("(s => { if (s) s.scrollTop = s.scrollHeight; })(document.querySelector('#peek [data-pk-body]') || document.querySelector('#peek .pk-body'))", sid)
            inview = cdp.js("(e => { const r = e.getBoundingClientRect(); return r.top >= 0 && r.bottom <= innerHeight + 1; })(document.querySelector('[data-pk-foot]'))", sid)
            self.assertTrue(inview, "the footer is always on screen")

    def test_the_footer_keeps_the_words_the_live_peek_has_and_the_old_split_is_gone(self):
        src = PEEK.read_text(encoding="utf-8")
        self.assertIn("data-pk-htabs", (PEEK.parent.parent / "edit/PeekActivity.jsx").read_text(encoding="utf-8"))
        self.assertIn("data-pk-details", (PEEK.parent / "PeekDetails.jsx").read_text(encoding="utf-8"))
        self.assertIn("data-pk-foot", (PEEK.parent.parent / "edit/PeekFooter.jsx").read_text(encoding="utf-8"))
        self.assertNotRegex(src, r'data-pk-tab=["\']?details', "the old Details and Activity tab pair is replaced")


if __name__ == "__main__":
    unittest.main()
