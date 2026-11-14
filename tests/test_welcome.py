"""#174: the first-run welcome (src/clark/page/src/edit/Welcome.jsx), in a real browser at 1400 and 900 px, in Light and in Dark.
Run: python3 dev/run_tests.py test_welcome

The first time clark is opened with no name in Settings › Profile › About you, a card asks for it. What is asserted: its words; it
fits the window; it takes the focus into the Name box when the page has none (row 857, which reverses the
earlier never-takes-focus rule) and keeps Tab inside it; Save keeps the name through clark (settings.json, the same route as About you) and the
menu shows it at once; a refusal says why and keeps the card; Not now (or Esc) closes it and saves nothing; once answered or
dismissed it is never shown again, over a reload; a name already in Settings means it is never shown. The tests set
window.__clarkWelcome before the page loads, which the browser tests' copy (main-test.jsx, testhook.js) needs to show it at all.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import unittest

from _new_page import reload_to_new_page
from test_publish_dialog import Base, Pg
from test_server import chrome, wait

WIDTHS = (1400, 900)
HEAD = "Welcome to clark"
ASK = "What is your name? It goes on each change you make, at the top of your menu, and on what you publish."
LINE = "Not now leaves it empty: your changes show this computer's login name. You can add it later in Settings › Profile."
CARD = "document.querySelector('[data-welcome]')"


class Welcome(Base):
    def saved(self):
        f = self.rig.data_dir / "settings.json"
        return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

    def load(self, cdp, look="light", width=1400):
        """The page with the welcome let through (and the Appearance chosen) before any of its script runs."""
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument",
                 {"source": f"window.__clarkWelcome = true; try {{ localStorage.setItem('clark.appearance', {json.dumps(look)}); }} catch (e) {{}}"}, sid)
        p = Pg(self, cdp, sid)
        p.width(width)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.rig.httpd.server_port}/#dashboard&p=PUB"}, sid)
        p.until("!!document.querySelector('#profile-btn')", "the page drew")
        return p

    def reload(self, p):
        reload_to_new_page(p.js, "!!document.querySelector('#profile-btn')", "the page is up again")

    def no_card_for_good(self, p):
        """No card, now or once the profile read has had time to answer (the menu's top line is drawn from that same read)."""
        p.js("document.querySelector('#profile-btn').click()")
        p.until("!!document.querySelector('#profile-menu .who, #profile-menu .who-link')", "the menu drew its top line")
        p.js("document.querySelector('#profile-menu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
        self.assertFalse(p.js(f"!!{CARD}"), "the welcome is not shown")

    def type_name(self, p, text):
        p.js(f"(() => {{ const el = document.querySelector('#welcome-name'); el.value = {json.dumps(text)}; "
             "el.dispatchEvent(new Event('input', {bubbles: true})); })()")

    def test_C_the_card_its_words_and_its_look_at_both_widths_in_light_and_dark(self):
        for look in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(look=look, width=w), chrome() as cdp:
                    p = self.load(cdp, look, w)
                    p.until(f"!!{CARD}", "the welcome is shown")
                    self.assertEqual(p.js(f"{CARD}.querySelector('h2').textContent"), HEAD)
                    self.assertEqual(p.js("document.querySelector('#welcome-ask').textContent"), ASK)
                    self.assertEqual(p.js("document.querySelector('label[for=welcome-name]').textContent"), "Your name")
                    self.assertEqual(p.js("document.querySelector('#welcome-line').textContent"), LINE)
                    self.assertEqual(p.js(f"[...{CARD}.querySelectorAll('button')].map(b => b.textContent)"), ["Save", "Not now"])
                    self.assertEqual(p.js(f"[{CARD}.getAttribute('role'), {CARD}.getAttribute('aria-modal')]"), ["dialog", "false"])
                    # row 857 reverses the earlier 'never takes the focus': the Name box has it, so the keyboard works at once
                    # the focus is set after the card draws (an effect): a slow Mac may not have run it yet, so wait, and say where the focus was if it never comes
                    named = "document.activeElement === document.querySelector('#welcome-name')"
                    self.assertTrue(wait(lambda: p.js(named), 10), "the Name box has the focus; the focus was on: " + str(p.js("(document.activeElement && (document.activeElement.tagName + '#' + document.activeElement.id + '.' + document.activeElement.className)) || 'nothing'")))
                    box = p.js(f"(() => {{ const r = {CARD}.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }})()")
                    self.assertGreaterEqual(box[0], 0)
                    self.assertGreaterEqual(box[1], 0)
                    self.assertLessEqual(box[2], w)
                    self.assertLessEqual(box[3], 900)
                    self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w, "no sideways scroll")
                    self.assertEqual(p.js("document.documentElement.dataset.theme || 'light'"), look)
                    # the card is drawn in the page's own colours: dark on light, or light on dark
                    bg, fg = p.js(f"(() => {{ const s = getComputedStyle({CARD}); const l = (c) => {{ const m = c.match(/\\d+(\\.\\d+)?/g).map(Number); "
                                  "return (m[0] * 299 + m[1] * 587 + m[2] * 114) / 1000; }; return [l(s.backgroundColor), l(s.color)]; })()")
                    if look == "dark":
                        self.assertLess(bg, 90)
                        self.assertGreater(fg, 160)
                    else:
                        self.assertGreater(bg, 200)
                        self.assertLess(fg, 100)
                    self.assertEqual(self.saved(), {}, "showing it saves nothing")

    def test_C_save_keeps_the_name_through_clark_and_it_is_never_asked_again(self):
        with chrome() as cdp:
            p = self.load(cdp)
            p.until(f"!!{CARD}", "the welcome is shown")
            self.type_name(p, "  Jane Doe ")
            p.js("document.querySelector('[data-welcome-save]').click()")
            p.until(f"!{CARD}", "the card closed")
            self.assertEqual(self.saved().get("profile_name"), "Jane Doe")
            self.assertEqual(p.js("localStorage.getItem('clark.welcome')"), "done")
            p.js("document.querySelector('#profile-btn').click()")
            p.until("(document.querySelector('#profile-menu .who b') || {}).textContent === 'Jane Doe'", "the menu shows the name at once")
            p.js("document.querySelector('#profile-menu').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            self.reload(p)
            self.no_card_for_good(p)

    def test_C_a_name_saved_in_settings_and_then_emptied_does_not_bring_it_back(self):
        with chrome() as cdp:
            p = self.load(cdp)
            p.until(f"!!{CARD}", "the welcome is shown")
            self.type_name(p, "Sam Lee")
            p.js("document.querySelector('[data-welcome-save]').click()")
            p.until(f"!{CARD}", "the card closed")
            (self.rig.data_dir / "settings.json").write_text(json.dumps({**self.saved(), "profile_name": ""}), encoding="utf-8")
            self.reload(p)
            self.no_card_for_good(p)

    def test_C_not_now_closes_it_saves_nothing_and_it_stays_closed(self):
        with chrome() as cdp:
            p = self.load(cdp, "dark", 900)
            p.until(f"!!{CARD}", "the welcome is shown")
            self.type_name(p, "Jane Doe")
            p.js("document.querySelector('[data-welcome-skip]').click()")
            p.until(f"!{CARD}", "the card closed")
            self.assertEqual(self.saved(), {}, "Not now saves nothing, even with a name typed")
            self.reload(p)
            self.no_card_for_good(p)

    def test_C_row_857_the_keyboard_works_at_once_tab_stays_inside_and_esc_closes(self):
        act = "(() => { const e = document.activeElement; return e.id || (e.hasAttribute('data-welcome-save') ? 'save' : e.hasAttribute('data-welcome-skip') ? 'skip' : e.tagName); })()"
        for look in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(look=look, width=w), chrome() as cdp:
                    p = self.load(cdp, look, w)
                    p.until(f"!!{CARD}", "the welcome is shown", 30)
                    p.until("document.activeElement && document.activeElement.id === 'welcome-name'", "the focus is in the Name box", 10)
                    p.until("document.getAnimations().length === 0", "the card has settled", 10)
                    p.cdp.call("Input.insertText", {"text": "Jo"}, p.sid)      # typing straight away lands in the Name box
                    self.assertEqual(p.js("document.querySelector('#welcome-name').value"), "Jo")
                    seen = []
                    for _ in range(4):                  # Tab goes round Name, Save, Not now and back, never out of the card
                        p.key("Tab", "Tab", 9)
                        seen.append(p.js(act))
                    self.assertEqual(seen, ["save", "skip", "welcome-name", "save"])
                    p.js("document.querySelector('#welcome-name').focus()")      # Shift+Tab from the Name box wraps to Not now
                    p.cdp.call("Input.dispatchKeyEvent", {"type": "keyDown", "key": "Tab", "code": "Tab", "windowsVirtualKeyCode": 9, "modifiers": 8}, p.sid)
                    self.assertEqual(p.js(act), "skip")
                    p.key("Escape", "Escape", 27)
                    p.until(f"!{CARD}", "Esc closed it")
                    self.assertEqual(self.saved(), {})

    def test_C_row_857_it_does_not_take_the_focus_from_something_already_being_typed_in(self):
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.enable", {}, sid)
            # an input is focused as soon as the page starts, and every answer from clark is held back a second, so the card
            # opens after that: it must leave the focus where it is
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": "window.__clarkWelcome = true; "
                     "const f = window.fetch; window.fetch = (...a) => new Promise((ok) => setTimeout(ok, 1500)).then(() => f(...a)); "
                     "document.addEventListener('DOMContentLoaded', () => { const i = document.createElement('input'); i.id = 'other'; "
                     "document.body.appendChild(i); i.focus(); });"}, sid)
            p = Pg(self, cdp, sid)
            p.width(1400)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.rig.httpd.server_port}/#dashboard&p=PUB"}, sid)
            p.until(f"!!{CARD}", "the welcome is shown", 30)
            self.assertEqual(p.js("document.activeElement.id"), "other", "the focus stayed where the person was")

    def test_C_esc_in_the_card_is_not_now(self):
        with chrome() as cdp:
            p = self.load(cdp)
            p.until(f"!!{CARD}", "the welcome is shown")
            p.js("document.querySelector('#welcome-name').dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))")
            p.until(f"!{CARD}", "the card closed")
            self.assertEqual(self.saved(), {})
            self.assertEqual(p.js("localStorage.getItem('clark.welcome')"), "done")

    def test_C_an_empty_name_or_a_refusal_says_why_and_keeps_the_card(self):
        with chrome() as cdp:
            p = self.load(cdp, "light", 900)
            p.until(f"!!{CARD}", "the welcome is shown")
            self.type_name(p, "   ")
            p.js("document.querySelector('[data-welcome-save]').click()")
            p.until(f"{CARD}.querySelector('.fld-bad').textContent === 'Type your name, or choose Not now.'", "it says what to do")
            self.type_name(p, "J" * 61)
            p.js("document.querySelector('[data-welcome-save]').click()")
            p.until(f"/too long.*Nothing was saved\\./.test({CARD}.querySelector('.fld-bad').textContent)", "clark's own refusal is shown")
            self.assertEqual(p.js("document.querySelector('#welcome-name').getAttribute('aria-invalid')"), "true")
            self.assertEqual(self.saved(), {}, "a refusal writes nothing")
            self.assertTrue(p.js(f"!!{CARD}"), "the card stays so the name can be mended")
            self.assertIsNone(p.js("localStorage.getItem('clark.welcome')"))

    def test_C_a_name_already_in_settings_means_it_is_never_shown(self):
        (self.rig.data_dir / "settings.json").write_text(json.dumps({"profile_name": "Jane Doe"}), encoding="utf-8")
        with chrome() as cdp:
            p = self.load(cdp)
            self.no_card_for_good(p)


if __name__ == "__main__":
    unittest.main()
