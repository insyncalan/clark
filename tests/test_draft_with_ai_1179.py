"""Row 1179: the quiet "Draft with AI" button beside Latest update on every peek (Action, Risk, Issue, Milestone) and the AI menu on a right-click over
selected text in the Latest update editor. The page runs for real in headless Chrome at 1400 and 900 px, light and dark; only the three /api/ai/ routes
are answered by a script in the page (the page's own client, aiClient.js, makes the calls), so the flow does not depend on a signed-in provider.
Run: python3 dev/run_tests.py test_draft_with_ai_1179
"""
import json
import unittest

from _paths import ROOT
from _demo import USER, DemoStore  # noqa: F401
from test_movement_page import GO_LIVE, Base
import test_milestone_peek_828 as _test_milestone_peek_828
import test_peek_latest
from test_server import chrome, wait
from test_work_filters import click

SRC = ROOT / "src" / "clark" / "page" / "src"
B = "#peek [data-pk-ai]"
SUGGESTED = "Suggested words"
OPTIONS = ["rewrite", "shorter", "longer", "executive", "format", "summary", "custom"]       # the server's list for the place current, less Format notes (one line of text)
# The three /api/ai/ routes, answered in the page: ready, one suggestion, stop. Every call is kept in window.__ai.
STUB = """(() => { const real = window.fetch.bind(window); window.__ai = [];
  const ok = (o) => Promise.resolve(new Response(JSON.stringify(o), {status: 200, headers: {'Content-Type': 'application/json'}}));
  window.fetch = (url, opts) => { const u = String(url); if (!u.startsWith('/api/ai/')) return real(url, opts); window.__ai.push([u, opts && opts.body ? JSON.parse(opts.body) : null]);
    if (u === '/api/ai/status') return ok({ok: true, state: 'ready', line: ''});
    if (u === '/api/ai/suggest') return ok({ok: true, html: '<p>Suggested words</p>', notes: [], changes: []});
    return ok({ok: true}); }; })()"""


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


class Source(unittest.TestCase):
    def test_the_bubble_last_button_uses_the_existing_words_and_the_style_menu_ticks(self):    # row 1288
        rt = read("edit/RichText.jsx")
        self.assertIn("data-rt-bubble-ai", rt)
        self.assertIn("{classic ? ASK_AI : DRAFT_WITH_AI}</button>", rt, "Classic's bubble ends with the ruled Ask AI...; Cards keeps the words of DraftAi.jsx")
        self.assertIn('ASK_AI = "Ask AI\\u2026"', rt, "the ellipsis character, not three dots")
        bubble = [l for l in rt.splitlines() if "data-rt-bubble-ai" in l][0]
        self.assertNotIn("Ask AI", bubble, "the bubble button reads Draft with AI here (the Classic Ask AI... is row 1288 part a1); the '/' menu has its own Ask AI line")
        self.assertIn("checked: current ?", rt, "the Text style menu ticks the current line")

    def test_the_button_is_in_every_peek_and_the_menu_is_the_places_menu(self):
        latest, ms, shared = read("edit/PeekLatest.jsx"), read("edit/MilestonePeek.jsx"), read("edit/DraftAi.jsx")
        self.assertIn("<LatestBox", ms, "row 1184: the milestone's Latest update is the work item peek's box (PeekLatest.jsx LatestBox)")
        self.assertIn("<DraftButton", latest)
        self.assertIn("<DraftPanel", latest)
        self.assertIn("ai={place}", latest, "the right-click menu is on in the Latest update editor")
        self.assertIn('keyForField("latest_update")', latest, "the place comes from aiPlaces.js, by the field")
        self.assertIn('export const DRAFT_WITH_AI = "Draft with AI"', shared)
        self.assertIn("aria-label={DRAFT_WITH_AI}", shared)
        self.assertIn('role="menu" aria-label={DRAFT_WITH_AI}', shared, "the menu is named with the same words as the button")
        self.assertIn('<Icon name="sparkle"', shared)
        self.assertIn("<AiCard", shared)
        self.assertIn("menu(place)", shared)
        self.assertIn("ai={ai}", read("edit/RichField.jsx"))
        self.assertIn("onContextMenu={onContext}", read("edit/RichText.jsx"))
        self.assertNotIn("not wired to any editor yet", read("edit/AiCard.jsx"))

    def test_the_place_is_current_for_the_latest_update_of_every_kind(self):
        self.assertIn('"peek.latest_update": "current"', read("logic/aiPlaces.js"))
        self.assertIn('latest_update: "peek.latest_update"', read("logic/aiPlaces.js"))

    def test_the_light_look_uses_the_sun_and_no_other_look_or_menu_icon_changed(self):
        icons = read("menuIcons.js")
        self.assertIn('lookLight: "sun"', icons)
        self.assertIn('lookDark: "eyeoff"', icons)
        self.assertIn("sun:", read("components/Icon.jsx"))

    def test_the_words_box_keeps_its_picture_sparkle(self):
        self.assertIn('<Icon name="sparkle" />', read("edit/SneakPeek.jsx"))

    def test_the_button_rule_is_24px_and_the_draft_email_names_stay_apart(self):
        css = read("edit/edit.css")
        rule = css.split(".pk-ai {", 1)[1].split("}", 1)[0]
        self.assertIn("min-height: 24px", rule)
        self.assertIn("var(--brand-blue)", rule)
        self.assertIn("var(--brand-blue-tint)", css.split(".pk-ai:hover", 1)[1].split("}", 1)[0])
        self.assertIn("font-size: var(--size-caption); font-weight: 600", rule)
        self.assertNotIn("draft-email", read("edit/DraftAi.jsx").lower().replace("not the draft email feature", ""))


class Pane(unittest.TestCase):
    """Action, Risk and Issue peeks (the work-items page in Edit)."""
    load, open_box, type_in, save_key, toast, fresh, refused = (test_peek_latest.Browser.load, test_peek_latest.Browser.open_box, test_peek_latest.Browser.type_in,
                                                                test_peek_latest.Browser.save_key, test_peek_latest.Browser.toast, test_peek_latest.Browser.fresh,
                                                                test_peek_latest.Browser.refused)
    HOLD, SHOWN, BOX = test_peek_latest.Browser.HOLD, test_peek_latest.Browser.SHOWN, test_peek_latest.Browser.BOX
    REFS = (("TUL-A-001", "actions"), ("TUL-007", "raid"), ("TUL-010", "raid"))

    def setUp(self):
        self.fresh()

    def opened(self, cdp, width, ref, dark=False):
        sent, sid = self.load(cdp, width, ref, edit=True, dark=dark)
        cdp.js(STUB, sid)
        return sent, sid

    def test_the_button_is_beside_latest_update_on_every_work_item_peek_and_opens_the_flow(self):
        for ref, table in self.REFS:
            for width in (1400, 900):
                with self.subTest(item=ref, width=width), chrome() as cdp:
                    sent, sid = self.opened(cdp, width, ref)
                    self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(B)})", sid)), "the button is on the peek")
                    self.assertTrue(cdp.js(f"!!document.querySelector('#peek [data-pk-latest] .pk-lab').contains(document.querySelector({json.dumps(B)}))", sid), "in the Latest update heading row")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(B)}).getAttribute('aria-label')", sid), "Draft with AI")
                    self.assertEqual(cdp.js(f"document.querySelector({json.dumps(B)}).textContent.trim()", sid), "Draft with AI")
                    self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(B)} + ' svg, ' + {json.dumps(B)} + ' .ic')", sid) or cdp.js(f"!!document.querySelector({json.dumps(B)}).querySelector('svg')", sid), "the sparkle icon")
                    self.assertGreaterEqual(cdp.js(f"document.querySelector({json.dumps(B)}).getBoundingClientRect().height", sid), 24)
                    self.assertFalse(cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid))
                    cdp.js(f"document.querySelector({json.dumps(B)}).click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid)), "the menu opens")
                    self.assertEqual(cdp.js("document.querySelector('#peek [data-ai-menu]').getAttribute('aria-label')", sid), "Draft with AI")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#peek [data-ai-option]')].map(e => e.dataset.aiOption)", sid), OPTIONS)
                    cdp.js("document.querySelector('#peek [data-ai-option=shorter]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("(c => !!c && c.dataset.state === 'ready')(document.querySelector('#peek .aic'))", sid)), "the card says the suggestion is ready")
                    ask = cdp.js("window.__ai.filter(a => a[0] === '/api/ai/suggest').map(a => a[1])", sid)
                    self.assertEqual([(a["option"], a["place"]) for a in ask], [("shorter", "current")])
                    self.assertEqual(len(sent), 0, "nothing is written before Accept")
                    cdp.js("[...document.querySelectorAll('#peek .aic button')].find(b => b.textContent === 'Accept').click()", sid)
                    self.assertTrue(wait(lambda: len(sent) == 1), "Accept is one change")
                    self.assertEqual((sent[0]["kind"], sent[0]["id"], sent[0]["changes"]), (table, ref, {"latest_update": f"<p>{SUGGESTED}</p>"}))
                    self.assertTrue(wait(lambda: cdp.js(f"document.activeElement === document.querySelector({json.dumps(B)})", sid)), "focus is back on the button")

    def click_when_there(self, cdp, sid, selector):
        """Waits for the real element, then clicks it: a single read right after load or a close finds nothing on a slow runner."""
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector({json.dumps(selector)})", sid)), f"{selector} is on the page")
        cdp.js(f"document.querySelector({json.dumps(selector)}).click()", sid)

    def test_esc_closes_the_menu_and_the_card_and_gives_the_focus_back_to_the_button(self):
        with chrome() as cdp:
            _, sid = self.opened(cdp, 1400, "TUL-A-001")
            key = lambda: [cdp.call("Input.dispatchKeyEvent", {"type": t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid) for t in ("keyDown", "keyUp")]
            self.click_when_there(cdp, sid, B)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid)))
            self.assertTrue(wait(lambda: cdp.js("document.activeElement.dataset.aiOption === 'rewrite'", sid)), "the first option has the focus")
            key()
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid)), "Esc closes the menu")
            self.assertTrue(wait(lambda: cdp.js(f"document.activeElement === document.querySelector({json.dumps(B)})", sid)), "focus is back on the button")
            self.click_when_there(cdp, sid, B)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid)))
            self.click_when_there(cdp, sid, "#peek [data-ai-option=rewrite]")
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .aic') && document.querySelector('#peek .aic').contains(document.activeElement)", sid)), "the focus is in the card")
            key()
            self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek .aic')", sid)), "Esc closes the card")
            self.assertTrue(wait(lambda: cdp.js(f"document.activeElement === document.querySelector({json.dumps(B)})", sid)))

    def test_the_button_and_the_menu_are_drawn_in_light_and_dark_at_both_widths(self):
        for width in (1400, 900):
            for dark in (False, True):
                with self.subTest(width=width, dark=dark), chrome() as cdp:
                    _, sid = self.opened(cdp, width, "TUL-A-001", dark=dark)
                    cdp.js(f"document.querySelector({json.dumps(B)}).click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-ai-menu]')", sid)))
                    look = cdp.js(f"(() => {{ const b = getComputedStyle(document.querySelector({json.dumps(B)})), m = getComputedStyle(document.querySelector('#peek [data-ai-menu]')); return [b.color, b.backgroundColor, m.backgroundColor, m.color, document.documentElement.dataset.theme || '']; }})()", sid)
                    self.assertNotEqual(look[0], look[1], "the words are not the colour of their ground")
                    self.assertNotEqual(look[2], "rgba(0, 0, 0, 0)", "the menu has a ground")
                    self.assertNotEqual(look[2], look[3])
                    self.assertEqual(look[4] == "dark", dark)
                    self.assertGreaterEqual(cdp.js("document.querySelector('#peek [data-ai-option=rewrite]').getBoundingClientRect().height", sid), 24)

    def select_all(self, cdp, sid, text):
        self.open_box(cdp, sid)
        cdp.js(f"(e => {{ e.cxed.editor.commands.setContent('<p>{text}</p>'); e.cxed.editor.commands.selectAll(); }})(document.querySelector({json.dumps(self.BOX)})); true", sid)

    def right_click(self, cdp, sid):
        return cdp.js(f"(e => {{ const ev = new MouseEvent('contextmenu', {{bubbles: true, cancelable: true, clientX: 300, clientY: 300}}); e.dispatchEvent(ev); return ev.defaultPrevented; }})(document.querySelector({json.dumps(self.BOX)}))", sid)

    def test_a_right_click_on_selected_text_opens_the_menu_esc_closes_it_and_accept_replaces_the_selection(self):
        for ref, _ in (self.REFS[0], self.REFS[1]):
            for width in (1400, 900):
                with self.subTest(item=ref, width=width), chrome() as cdp:
                    sent, sid = self.opened(cdp, width, ref)
                    self.select_all(cdp, sid, "alpha beta gamma")
                    # Row 1587 diagnostic only: every focus move from here on, with the time, so a macOS log says who took the focus from the menu.
                    cdp.js("(() => { window.__fl = []; const t0 = performance.now(), d = (n) => n && n.tagName ? n.tagName + (n.dataset && n.dataset.aiOption ? '[' + n.dataset.aiOption + ']' : '') + (n.className ? '.' + String(n.className).split(' ')[0] : '') : String(n); for (const k of ['focusin', 'focusout']) document.addEventListener(k, (e) => window.__fl.push(k + ' ' + d(e.target) + ' to ' + d(e.relatedTarget) + ' @' + Math.round(performance.now() - t0)), true); })(); true", sid)
                    self.assertTrue(self.right_click(cdp, sid), "the browser's own menu is held back")
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-rt-ai] [data-ai-menu]')", sid)), "the AI menu opens over the selection")
                    self.assertEqual(cdp.js("[...document.querySelectorAll('#peek [data-rt-ai] [data-ai-option]')].map(e => e.dataset.aiOption)", sid), OPTIONS)
                    in_menu = wait(lambda: cdp.js("document.querySelector('#peek [data-rt-ai]').contains(document.activeElement)", sid))
                    seen = "" if in_menu else cdp.js("(a => JSON.stringify({tag: a && a.tagName, cls: a && a.className, data: a && {...a.dataset}, hasFocus: document.hasFocus(), menuButton: !!document.querySelector('#peek [data-rt-ai] button'), moves: window.__fl}))(document.activeElement)", sid)
                    self.assertTrue(in_menu, "the focus is in the menu; seen: " + str(seen))
                    for t in ("keyDown", "keyUp"):
                        cdp.call("Input.dispatchKeyEvent", {"type": t, "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27}, sid)
                    self.assertTrue(wait(lambda: not cdp.js("!!document.querySelector('#peek [data-rt-ai]')", sid)), "Esc closes the menu")
                    self.assertTrue(wait(lambda: cdp.js("document.activeElement.classList.contains('ProseMirror')", sid)), "focus is back in the editor")
                    self.assertTrue(cdp.js(f"!!document.querySelector({json.dumps(self.BOX)})", sid), "the editor stays open")
                    self.assertEqual(len(sent), 0)
                    self.assertTrue(self.right_click(cdp, sid))
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-rt-ai] [data-ai-menu]')", sid)))
                    cdp.js("document.querySelector('#peek [data-rt-ai] [data-ai-option=shorter]').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js("(c => !!c && c.dataset.state === 'ready')(document.querySelector('#peek [data-rt-ai] .aic'))", sid)))
                    ask = cdp.js("window.__ai.filter(a => a[0] === '/api/ai/suggest').map(a => a[1])", sid)
                    self.assertEqual([(a["option"], a["place"], a["text"]) for a in ask], [("shorter", "current", "alpha beta gamma")], "only the selected words are sent")
                    cdp.js("[...document.querySelectorAll('#peek [data-rt-ai] .aic button')].find(b => b.textContent === 'Accept').click()", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"document.querySelector({json.dumps(self.BOX)}).textContent", sid) == SUGGESTED), "the selection is replaced")
                    self.assertEqual(len(sent), 0, "nothing is saved until the box is saved as usual")
                    self.save_key(cdp, sid)
                    self.assertTrue(wait(lambda: len(sent) == 1))
                    self.assertEqual(sent[0]["changes"], {"latest_update": f"<p>{SUGGESTED}</p>"})

    def test_shift_f10_opens_the_same_menu_on_a_selection(self):
        with chrome() as cdp:
            _, sid = self.opened(cdp, 1400, "TUL-A-001")
            self.select_all(cdp, sid, "alpha beta gamma")
            cdp.js(f"document.querySelector({json.dumps(self.BOX)}).dispatchEvent(new KeyboardEvent('keydown', {{key: 'F10', shiftKey: true, bubbles: true, cancelable: true}}))", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-rt-ai] [data-ai-menu]')", sid)))

    def test_the_bubble_ends_with_draft_with_ai_and_opens_the_same_menu_as_the_right_click(self):    # row 1288, bubble
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                _, sid = self.opened(cdp, width, "TUL-A-001")
                self.select_all(cdp, sid, "alpha beta gamma")
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek .rt-bubble [data-rt-bubble-ai]')", sid)), "the bubble has the line")
                self.assertEqual(cdp.js("(b => b[b.length - 1].textContent)([...document.querySelectorAll('#peek .rt-bubble button')])", sid), "Draft with AI", "it is last")
                cdp.js("document.querySelector('#peek .rt-bubble [data-rt-bubble-ai]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#peek [data-rt-ai] [data-ai-menu]')", sid)))
                self.assertEqual(cdp.js("[...document.querySelectorAll('#peek [data-rt-ai] [data-ai-option]')].map(e => e.dataset.aiOption)", sid), OPTIONS, "the right-click menu's lines")

    def test_the_style_menu_ticks_the_current_line(self):    # row 1288, style menu
        with chrome() as cdp:
            _, sid = self.opened(cdp, 1400, "TUL-A-001")
            self.open_box(cdp, sid)
            cdp.js("document.querySelector('#peek .rt-style').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[role=menuitemradio][aria-checked=true]')", sid)))
            self.assertEqual(cdp.js("[...document.querySelectorAll('[role=menuitemradio][aria-checked=true]')].map(b => b.textContent.replace('✓','').trim())", sid), ["Text"])

    def test_no_selection_leaves_the_browsers_own_menu(self):
        with chrome() as cdp:
            _, sid = self.opened(cdp, 1400, "TUL-A-001")
            self.open_box(cdp, sid)
            cdp.js(f"(e => {{ e.cxed.editor.commands.setContent('<p>alpha beta gamma</p>'); e.cxed.editor.commands.setTextSelection(3); }})(document.querySelector({json.dumps(self.BOX)})); true", sid)
            self.assertFalse(self.right_click(cdp, sid), "not held back: the browser shows its own menu")
            self.assertFalse(cdp.js("!!document.querySelector('#peek [data-rt-ai], #peek [data-ai-menu]')", sid))
            cdp.js(f"document.querySelector({json.dumps(self.BOX)}).dispatchEvent(new KeyboardEvent('keydown', {{key: 'F10', shiftKey: true, bubbles: true, cancelable: true}}))", sid)
            self.assertFalse(cdp.js("!!document.querySelector('#peek [data-rt-ai]')", sid), "nor does Shift+F10 without a selection")


class MilestonePane(Base):
    visit_peek, click, undo, until_store, saved, toast_text = (_test_milestone_peek_828.Fields.visit_peek, _test_milestone_peek_828.Fields.click, _test_milestone_peek_828.Fields.undo, _test_milestone_peek_828.Fields.until_store, _test_milestone_peek_828.Fields.saved, _test_milestone_peek_828.Fields.toast_text)
    cur = GO_LIVE

    def test_the_milestone_peek_has_the_button_the_menu_and_the_right_click(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                p.js(STUB)
                p.until(f"!!document.querySelector({json.dumps(B)})", "the button is on the milestone peek")
                self.assertEqual(p.js(f"document.querySelector({json.dumps(B)}).getAttribute('aria-label')"), "Draft with AI")
                self.assertTrue(p.js(f"document.querySelector('#peek [data-pk-latest]').contains(document.querySelector({json.dumps(B)}))"), "in the Latest update box")
                before = len(self.sent)
                p.js(f"document.querySelector({json.dumps(B)}).click()")
                p.until("!!document.querySelector('#peek [data-ai-menu]')", "the menu opens")
                p.js("document.querySelector('#peek [data-ai-option=rewrite]').click()")
                p.until("(c => !!c && c.dataset.state === 'ready')(document.querySelector('#peek .aic'))", "the card is ready")
                self.assertEqual(len(self.sent), before, "nothing is written before Accept")
                p.js("[...document.querySelectorAll('#peek .aic button')].find(b => b.textContent === 'Accept').click()")
                self.saved(p, "latest_update", f"<p>{SUGGESTED}</p>")
                self.click(p, "#peek [data-rich=latest_update]")
                p.until("!!document.querySelector('#peek .ProseMirror') && document.activeElement.classList.contains('ProseMirror')", "the editor opened")
                p.js("(e => { e.cxed.editor.commands.setContent('<p>alpha beta</p>'); e.cxed.editor.commands.selectAll(); })(document.querySelector('#peek .ProseMirror')); true")
                self.assertTrue(p.js("(e => { const ev = new MouseEvent('contextmenu', {bubbles: true, cancelable: true, clientX: 300, clientY: 300}); e.dispatchEvent(ev); return ev.defaultPrevented; })(document.querySelector('#peek .ProseMirror'))"))
                p.until("!!document.querySelector('#peek [data-rt-ai] [data-ai-menu]')", "the AI menu opens over the selection")


if __name__ == "__main__":
    unittest.main()
