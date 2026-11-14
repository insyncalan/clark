"""Item 1179, 'Draft with AI': a quiet text button beside Latest update on every peek, and the AI menu on a right-click of selected text.
Written first: every test fails until the button, the menu and the store change are built.
Run: python3 dev/run_tests.py test_draft_with_ai_1179

Hooks the build must give (named here so the build and the test agree):
  [data-pk-ai]        the button (class pk-ai) in the .pk-lab row of [data-pk-latest], aria-label 'Draft with AI', text 'Draft with AI'
  [data-ai-menu]      the AI menu (role=menu, class pk-ai-menu), opened by the button, by a right-click on a non-empty selection
                      in the Latest update editor, and by Shift+F10 / the Menu key there; items are role=menuitem
  the AiCard mounts inside [data-pk-latest] (so the editor's focusout check does not close the editor under it)
Part 1 is the store (risks, issues and milestones take a latest update; a decision does not). Part 2 is the source. Part 3 is the page in a
real browser at 1400 and 900 px in Edit on the fictional demo project.
"""
import json
import re
import unittest

from _paths import ROOT

from clark import changes  # noqa: E402
from test_peek import key  # noqa: E402
import test_peek_latest  # noqa: E402
from test_peek_latest import OVERDUE, Server  # noqa: E402
from test_server import chrome, wait  # noqa: E402
from test_work_filters import click  # noqa: E402

SRC = ROOT / "src/clark/page/src"
RISK, ISSUE, MILESTONE = "TUL-007", "TUL-010", "TUL-M-001"        # demo data
ALL_FOUR = (("action", OVERDUE), ("risk", RISK), ("issue", ISSUE), ("milestone", MILESTONE))
BUTTON, MENU = "[data-pk-latest] [data-pk-ai]", "[data-ai-menu]"


class Store(Server):
    def test_a_risk_an_issue_and_a_milestone_take_a_latest_update_and_undo_it(self):
        data = self.store.data_for(self.code)
        for kind, ref in (("raid", RISK), ("raid", ISSUE), ("milestones", MILESTONE)):
            code, body = self.send("Checked with the owner.", kind, ref)
            self.assertEqual((code, body["ok"], body["undoable"]), (200, True, True), (kind, ref, body))
            code, undone = self.undo({"project": self.code, "apply_id": body["apply_id"]})
            self.assertEqual(code, 200, undone)

    def test_a_decision_still_has_no_latest_update(self):
        ref = self.store.data_for(self.code)["decisions"][0]["id"]
        code, body = self.send("Anything", "decisions", ref)
        self.assertEqual((code, body["ok"]), (400, False))


class Source(unittest.TestCase):
    def read(self, rel):
        return (SRC / rel).read_text(encoding="utf-8")

    def test_the_button_is_in_the_label_row_with_the_words_and_the_sparkle(self):
        src = self.read("edit/PeekLatest.jsx")
        self.assertRegex(src, r"data-pk-ai")
        self.assertIn('aria-label="Draft with AI"', src)
        self.assertIn("Draft with AI", src)
        self.assertIn('name="sparkle"', src)

    def test_the_latest_update_is_no_longer_for_actions_only(self):
        self.assertNotRegex(self.read("edit/PeekLatest.jsx"), r"action\s*\?", "no 'action ? :' guard is left in PeekLatest")
        peek = self.read("components/Peek.jsx")
        latest = next(l for l in peek.splitlines() if "tools.PeekLatest" in l and "const" in l)
        self.assertNotIn("forItem", latest, "the Latest update line is not gated on the item-only flag (a milestone gets it too)")
        self.assertIn("MilestonePeek", peek + self.read("edit/MilestonePeek.jsx"))
        self.assertNotRegex(self.read("edit/PeekLatest.jsx"), r"kind\s*!==?\s*.(risk|issue|milestone).", "no per-kind exclusion is left")

    def test_the_menu_is_the_current_place_menu_and_the_editor_takes_an_ai_prop(self):
        menu = self.read("edit/AiMenu.jsx")
        self.assertIn('menu("current")', menu)
        self.assertIn('role="menu"', menu)
        rich = self.read("edit/RichText.jsx")
        self.assertRegex(rich, r"addEventListener\(\s*.contextmenu.")
        self.assertRegex(rich, r"props\.current\.ai\b")
        self.assertRegex(rich, r"F10")
        self.assertRegex(self.read("edit/RichField.jsx"), r"\bai\s*=\s*\{")

    def test_the_ai_card_is_mounted_and_its_old_header_is_fixed(self):
        self.assertIn("AiCard", self.read("edit/PeekLatest.jsx"))
        self.assertNotIn("not wired to any editor yet", self.read("edit/AiCard.jsx"))

    def test_the_light_look_uses_the_sun_and_the_sparkle_means_ai(self):
        icons = self.read("menuIcons.js")
        self.assertRegex(icons, r"lookLight:\s*\"sun\"")

    def test_the_button_has_its_style_and_a_24px_target(self):
        css = "".join(p.read_text(encoding="utf-8") for p in (SRC / "edit").glob("*.css"))
        self.assertIn(".pk-ai", css)
        rule = re.search(r"\.pk-ai\s*\{([^}]*)\}", css)
        self.assertTrue(rule, "a .pk-ai rule")
        self.assertRegex(rule.group(1), r"min-height:\s*24px")
        self.assertIn("--brand-blue-tint", css)
        self.assertIn(".pk-ai-menu", css)

    def test_comments_carry_no_hash_digits(self):
        """comms/ is gitignored (the NEW-WORDS.md entry is the lead's to log), so nothing here reads it."""
        for rel in ("edit/PeekLatest.jsx", "edit/AiMenu.jsx", "edit/AiCard.jsx", "edit/RichText.jsx"):
            self.assertNotRegex(self.read(rel), r"#\d{2,}", rel + ": write 'item 1179', not a hash and digits")


class Browser(test_peek_latest.Browser):
    """Same loader as the Latest update tests; the peek of another kind is opened over the first."""

    def open_kind(self, cdp, width, kind, ref):
        sent, sid = self.load(cdp, width, OVERDUE)
        if ref != OVERDUE:
            cdp.js(f"clarkPage.openPeek({json.dumps(ref)}, {json.dumps(kind)})", sid)
            self.assertTrue(wait(lambda: cdp.js("(document.querySelector('#peek') || {dataset: {}}).dataset.peek", sid) == ref))
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(BUTTON)})", sid)), f"the button is on the {kind} peek")
        return sent, sid

    def select_all(self, cdp, sid):
        cdp.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.selectAll(); true", sid)

    def right_click(self, cdp, sid):
        r = cdp.js("(r => [r.left + 20, r.top + 8])(document.querySelector('#peek .ProseMirror').getBoundingClientRect())", sid)
        for kind in ("mousePressed", "mouseReleased"):
            cdp.call("Input.dispatchMouseEvent", {"type": kind, "x": r[0], "y": r[1], "button": "right", "clickCount": 1}, sid)

    def menu_open(self, cdp, sid):
        return cdp.js(f"!!document.querySelector({json.dumps(MENU)})", sid)

    def test_the_button_shows_on_all_four_peeks_with_its_label_and_a_24px_target(self):
        for width in (1400, 900):
            for kind, ref in ALL_FOUR:
                with self.subTest(width=width, kind=kind), chrome() as cdp:
                    sent, sid = self.open_kind(cdp, width, kind, ref)
                    info = cdp.js(f"(b => ({{label: b.getAttribute('aria-label'), text: b.textContent.trim(), h: b.getBoundingClientRect().height,"
                                  f" icon: !!b.querySelector('svg'), tag: b.tagName, row: !!b.closest('.pk-lab')}}))(document.querySelector({json.dumps(BUTTON)}))", sid)
                    self.assertEqual((info["label"], info["text"], info["tag"]), ("Draft with AI", "Draft with AI", "BUTTON"))
                    self.assertTrue(info["icon"] and info["row"], info)
                    self.assertGreaterEqual(info["h"], 24, "the 24px target")
                    self.assertTrue(cdp.js(f"!!document.querySelector('[data-pk-latest] [data-rich=latest_update], [data-pk-latest] .ProseMirror')", sid), "the field is there too")

    def test_the_button_opens_the_menu_and_esc_closes_it_with_the_focus_back(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.open_kind(cdp, width, "action", OVERDUE)
                click(cdp, sid, BUTTON)
                self.assertTrue(wait(lambda: self.menu_open(cdp, sid)), "the menu opens")
                self.assertEqual(cdp.js(f"document.querySelector({json.dumps(MENU)}).getAttribute('role')", sid), "menu")
                self.assertGreater(cdp.js(f"document.querySelectorAll({json.dumps(MENU)} + ' [role=menuitem]').length", sid), 0)
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: not self.menu_open(cdp, sid)), "Esc closes it")
                self.assertTrue(cdp.js("!!document.querySelector('#peek')", sid), "and the peek stays")

    def test_a_right_click_on_selected_text_opens_the_menu_and_esc_returns_to_the_editor(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.open_kind(cdp, width, "action", OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Venue confirmed.")
                self.select_all(cdp, sid)
                self.right_click(cdp, sid)
                self.assertTrue(wait(lambda: self.menu_open(cdp, sid)), "the AI menu opens on the selection")
                self.assertEqual(sent, [], "opening the menu saves nothing")
                key(cdp, sid, "Escape")
                self.assertTrue(wait(lambda: not self.menu_open(cdp, sid)))
                self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('ProseMirror')", sid)), "the focus is back in the editor")

    def test_with_no_selection_the_right_click_is_the_browsers_own(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                sent, sid = self.open_kind(cdp, width, "action", OVERDUE)
                self.open_box(cdp, sid)
                self.type_in(cdp, sid, "Venue confirmed.")
                cdp.js("(e => { e.cxed.editor.commands.setTextSelection(1); window.__cm = null; document.addEventListener('contextmenu', ev => { window.__cm = ev.defaultPrevented; }); })(document.querySelector('#peek .ProseMirror')); true", sid)
                self.right_click(cdp, sid)
                self.assertTrue(wait(lambda: cdp.js("window.__cm !== null", sid)), "the event arrived")
                self.assertFalse(self.menu_open(cdp, sid), "no AI menu")
                self.assertFalse(cdp.js("window.__cm", sid), "preventDefault was not called, so the browser's menu shows")

    def stub_ai(self, cdp, sid, html="<p>Better words.</p>"):
        """The page's fetch answers the AI routes: status ready, and one suggestion. Everything else goes to the real server."""
        cdp.js("(html => { const real = window.fetch; window.__ai = []; window.fetch = (u, o) => { const path = String(u);"
               " if (path.startsWith('/api/ai/status')) return Promise.resolve(new Response(JSON.stringify({ok: true, state: 'ready', line: ''}), {status: 200}));"
               " if (path.startsWith('/api/ai/suggest')) { window.__ai.push(JSON.parse(o.body)); return Promise.resolve(new Response(JSON.stringify({ok: true, html, notes: [], changes: []}), {status: 200})); }"
               " return real(u, o); }; })(" + json.dumps(html) + "); true", sid)

    def pick_first_option(self, cdp, sid):
        click(cdp, sid, BUTTON)
        self.assertTrue(wait(lambda: self.menu_open(cdp, sid)))
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ai-menu] [data-ai-option]')", sid)))
        click(cdp, sid, "[data-ai-menu] [data-ai-option]")

    def card_state(self, cdp, sid):
        return cdp.js("(c => c ? c.dataset.state : null)(document.querySelector('[data-pk-latest] [data-ai-card] .aic'))", sid)

    def editor_text(self, cdp, sid):
        return cdp.js("document.querySelector('#peek .ProseMirror').textContent", sid)

    def test_accept_writes_the_suggestion_into_the_editor_and_a_save_sends_it(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.stub_ai(cdp, sid)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Venue confirmed.")
            self.pick_first_option(cdp, sid)
            self.assertTrue(wait(lambda: self.card_state(cdp, sid) == "ready"), "the card reaches Suggestion ready (a status the page asked for)")
            self.assertEqual(cdp.js("window.__ai[0].place", sid), "current", "asked for the current-update place")
            self.assertIn("Venue confirmed.", cdp.js("window.__ai[0].text", sid), "the field's words went to the provider")
            self.assertIn("Venue confirmed.", self.editor_text(cdp, sid), "nothing changes before Accept")
            self.assertEqual(sent, [])
            click(cdp, sid, "[data-ai-card] .again")
            self.assertTrue(wait(lambda: "Better words." in self.editor_text(cdp, sid)), "Accept wrote it through the editor")
            self.assertNotIn("Venue confirmed.", self.editor_text(cdp, sid))
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('[data-ai-card] .aic')", sid)), "the card is gone")
            self.save_key(cdp, sid)
            self.assertTrue(wait(lambda: len(sent) == 1), "one save")
            self.assertIn("Better words.", sent[0]["changes"]["latest_update"])

    def test_discard_leaves_the_text_as_it_was(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.stub_ai(cdp, sid)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Venue confirmed.")
            self.pick_first_option(cdp, sid)
            self.assertTrue(wait(lambda: self.card_state(cdp, sid) == "ready"))
            cdp.js("[...document.querySelectorAll('[data-ai-card] .aic-btn')].find(b => !b.classList.contains('again')).click(); true", sid)
            self.assertTrue(wait(lambda: self.card_state(cdp, sid) is None), "the card closes")
            self.assertIn("Venue confirmed.", self.editor_text(cdp, sid))
            self.assertNotIn("Better", self.editor_text(cdp, sid))
            self.assertEqual(sent, [])

    def test_accept_on_a_selection_replaces_only_the_selection(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.stub_ai(cdp, sid, "<p>X</p>")
            self.open_box(cdp, sid)
            cdp.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.setContent('<p>Alpha beta gamma</p>'); true", sid)
            cdp.js("document.querySelector('#peek .ProseMirror').cxed.editor.commands.setTextSelection({from: 7, to: 11}); true", sid)     # 'beta'
            self.right_click(cdp, sid)
            self.assertTrue(wait(lambda: self.menu_open(cdp, sid)))
            click(cdp, sid, "[data-ai-menu] [data-ai-option]")
            self.assertTrue(wait(lambda: self.card_state(cdp, sid) == "ready"))
            self.assertEqual(cdp.js("window.__ai[0].text", sid), "beta", "only the selected words are sent")
            click(cdp, sid, "[data-ai-card] .again")
            self.assertTrue(wait(lambda: "X" in self.editor_text(cdp, sid)))
            t = self.editor_text(cdp, sid)
            self.assertTrue(t.startswith("Alpha") and t.endswith("gamma") and "beta" not in t, t)

    def test_with_ai_off_the_card_says_so_and_changes_nothing(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            cdp.js("(real => { window.__ai = []; window.fetch = (u, o) => String(u).startsWith('/api/ai/') ? (window.__ai.push(String(u)), Promise.resolve(new Response(JSON.stringify({ok: true, state: 'off', line: ''}), {status: 200}))) : real(u, o); })(window.fetch); true", sid)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Venue confirmed.")
            self.pick_first_option(cdp, sid)
            self.assertTrue(wait(lambda: self.card_state(cdp, sid) == "off"), "the off card")
            self.assertFalse(cdp.js("window.__ai.some(u => u.startsWith('/api/ai/suggest'))", sid), "nothing is sent to a provider when AI is off")
            self.assertFalse(cdp.js("!!document.querySelector('[data-ai-card] .again')", sid), "no Accept on an off card")
            self.assertIn("Venue confirmed.", self.editor_text(cdp, sid))
            self.assertEqual(sent, [])

    def test_tab_from_the_open_editor_to_the_button_keeps_the_editor_and_saves_nothing(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Half typed.")
            cdp.js("document.querySelector('[data-pk-latest] [data-pk-ai]').focus(); true", sid)      # what Shift+Tab from the editor does
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.hasAttribute('data-pk-ai')", sid)))
            cdp.call("Runtime.evaluate", {"expression": "new Promise(r => setTimeout(r, 300))", "awaitPromise": True}, sid)
            self.assertTrue(cdp.js("!!document.querySelector('#peek .ProseMirror')", sid), "the editor is still open")
            self.assertEqual(sent, [], "focus on the button is not a save")
            self.assertIn("Half typed.", self.editor_text(cdp, sid))

    def test_shift_f10_on_a_selection_opens_the_menu(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Venue confirmed.")
            self.select_all(cdp, sid)
            for kind in ("keyDown", "keyUp"):
                cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": "F10", "code": "F10", "windowsVirtualKeyCode": 121, "modifiers": 8}, sid)
            self.assertTrue(wait(lambda: self.menu_open(cdp, sid)), "Shift+F10 opens it")

    def test_opening_the_menu_does_not_close_the_editor_or_lose_the_text(self):
        with chrome() as cdp:
            sent, sid = self.open_kind(cdp, 1400, "action", OVERDUE)
            self.open_box(cdp, sid)
            self.type_in(cdp, sid, "Kept words.")
            click(cdp, sid, BUTTON)
            self.assertTrue(wait(lambda: self.menu_open(cdp, sid)))
            self.assertTrue(cdp.js("!!document.querySelector('#peek .ProseMirror')", sid), "the editor stays open under the menu")
            self.assertIn("Kept words.", cdp.js("document.querySelector('#peek .ProseMirror').textContent", sid))
            self.assertEqual(sent, [], "nothing saved by opening it")


if __name__ == "__main__":
    unittest.main()
