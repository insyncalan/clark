"""Row 1005, a second hostile pass: inputs the first hostile tests did not reach.

Run: python3 dev/run_tests.py test_b4_hostile_1005
plainLine and a next-line character; the Movement form's Who agreed it / Reason / Source (the Tab order through the three, a real click on
Move straight after typing, a pasted script and onerror, a line break kept out of what is sent, 10,000 characters, emoji and right-to-left
words); a RAID card's Own words (the 400 and 401 boundary counted in emoji, saving twice quickly, Undo after a save, a paste with a script,
10,000 characters, U+2028 and U+0085, right-to-left words, Escape after an over-long try). 1400 and 900 wide, light and dark. Made-up data only.
"""
import html
import json
import re
import time
import unittest

from _demo import USER
from test_report_editor import Base as PageBase
from test_server import chrome, wait
import test_movement_page as tmp
import test_p1005b_eye as eye
import test_plain_line_hostile as plh

COMBOS = ((1400, "light"), (900, "dark"))
TOO_LONG = eye.TOO_LONG
NEL, LS, PS = "\u0085", " ", " "


def look(p, width, theme):
    p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
    p.js(f"document.documentElement.dataset.theme = '{theme}'")


class Logic(unittest.TestCase):
    pl = plh.PlainLine.pl
    setUpClass = classmethod(plh.PlainLine.setUpClass.__func__)
    tearDownClass = classmethod(plh.PlainLine.tearDownClass.__func__)
    def test_a_next_line_character_is_not_left_inside_one_line(self):
        for s in ("<p>a%sb</p>" % NEL, "a%sb" % NEL, "<p>a</p><p>%sb</p>" % NEL):
            got = self.pl(s)
            self.assertNotIn(NEL, got, repr(s))
            self.assertNotIn("\n", got)

    def test_line_and_paragraph_separators_are_spaces(self):
        self.assertEqual(self.pl("<p>a%sb%sc</p>" % (LS, PS)), "a b c")

    def test_ten_thousand_characters_keep_every_one(self):
        self.assertEqual(len(self.pl("<p>" + "x" * 10000 + "</p>")), 10000)

    def test_whitespace_only_in_every_flavour_is_nothing(self):
        self.assertEqual(self.pl("<p>  %s\t%s</p>" % (LS, "　")), "")
        self.assertEqual(self.pl("<p>%s</p>" % NEL), "")


# Row 1270: the RAID cards Edit has no Own words editor (ticket 1270 line 26: no own words anywhere in Edit or View; raid-cards.html approved 18-11 14:27); the hostile tests for what Edit has now are in test_raid_cards_hostile_1270.py.


class Movement(tmp.Base):
    def form(self, cdp, width, theme):
        p = self.visit(cdp, width=width, theme=theme)
        # A hosted Mac runner does not always give the page the keyboard focus: a Tab then reached the editor but the focus never left it, and a blur()
        # of a page that never had the focus does not fire. Ask for the page to be focused, as test_appearance does.
        p.cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        p.cdp.call("Page.bringToFront", {}, p.sid)
        self.open_movement(p)
        p.js("document.querySelector('#mv-move').click()")
        p.until("!!document.querySelector('.mvm-form')", "form %s %s" % (width, theme))
        p.until("document.activeElement.id === 'mv-to'", "focus")
        return p

    def box(self, k):
        return ".mvm-f[data-f=%s] .ProseMirror" % k

    def set_to(self, p):
        _, text = tmp.in_days(30)
        p.js("(function(){var e = document.getElementById('mv-to'); e.value = %s; e.dispatchEvent(new Event('input', {bubbles: true}));})()" % json.dumps(text))

    def put(self, p, k, html, close=True):
        p.js("document.getElementById('mv-%s').click()" % k)
        p.until("!!document.querySelector(%s)" % json.dumps(self.box(k)), "editor " + k)
        p.js("document.querySelector(%s).cxed.editor.commands.setContent(%s)" % (json.dumps(self.box(k)), json.dumps(html)))
        if close:
            # A slow Mac can drop the focus or the blur: focus the box, blur it again until it closes (a closed box needs no more).
            sel = json.dumps(self.box(k))
            def blur_once():
                p.js("(function(){var e = document.querySelector(%s); if (e) { e.focus(); e.blur(); }})()" % sel)
                return not p.js("!!document.querySelector(%s)" % sel)
            p.t.assertTrue(wait(blur_once, 30), "closed " + k)

    def rebaseline(self):
        for which, req in reversed(self.sent):
            if isinstance(req, dict) and req.get("rebaseline"):
                return req["rebaseline"]
        return None

    def test_tab_goes_who_then_reason_then_source_in_the_form(self):
        for width, theme in COMBOS:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                seen = []
                p.js("document.getElementById('mv-who').focus()")
                for _ in range(2):
                    p.key("Tab", code="Tab", vk=9)
                    time.sleep(0.2)
                    seen.append(p.js("document.activeElement.id || document.activeElement.className"))
                self.assertEqual(seen, ["mv-reason", "mv-source"], seen)
                p.key("Tab", code="Tab", vk=9, modifiers=8)
                time.sleep(0.2)
                self.assertEqual(p.js("document.activeElement.id || document.activeElement.className"), "mv-reason", "Shift+Tab goes back")

    def test_tab_from_inside_an_open_editor_saves_it_and_lands_on_the_next_field(self):
        for width, theme in COMBOS:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                self.put(p, "who", "<p>Pat Example</p>", close=False)
                sel = json.dumps(self.box("who"))
                p.js("document.querySelector(%s).focus()" % sel)
                p.js("window.__k = []; addEventListener('keydown', (e) => { window.__k.push([Math.round(performance.now()), e.key, e.target.className || e.target.id || e.target.tagName]); (window.__ke = window.__ke || []).push(e); }, true); window.__t0 = Math.round(performance.now())")
                # The leave handler skips a focusout while the page has no focus, and a Tab with the focus elsewhere never leaves the box: wait for the page to have the focus
                # and the caret to be in the open editor before the key, so a failure below is the key's and not the setup's. (Tab sent with the editing command insertTab
                # is swallowed as a tab character and never moves the focus, so the key stays a plain key.)
                p.t.assertTrue(wait(lambda: p.js("document.hasFocus() && !!document.querySelector(%s) && document.querySelector(%s).contains(document.activeElement)" % (sel, sel)), 15), "page focused with the caret in the open editor")
                p.key("Tab", code="Tab", vk=9)
                # The editor closes when its leave handler has run; on a slow Mac that was after the old fixed half second. Wait for it, and say what the page was doing if it never does.
                gone = None
                end = time.monotonic() + 10
                while time.monotonic() < end:
                    gone = not p.js("!!document.querySelector(%s)" % sel)
                    if gone:
                        break
                    time.sleep(0.05)
                seen = "" if gone else " | " + json.dumps(p.js("({focus: document.hasFocus(), open: !!document.querySelector(%s), active: document.activeElement ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) : null, keys: window.__k, tabDefaultPrevented: (window.__ke || []).filter(e => e.key === 'Tab').map(e => e.defaultPrevented), activeDesc: document.activeElement ? [document.activeElement.tagName, document.activeElement.id, document.activeElement.className] : null, since: Math.round(performance.now()) - window.__t0})" % sel))
                self.assertTrue(gone, "closed on Tab" + seen)
                self.assertIn("Pat Example", p.js("document.getElementById('mv-who').textContent"), "kept")
                self.assertTrue(p.js("!!document.querySelector('.mvm-form')"), "form stays")
                self.assertTrue(wait(lambda: p.js("document.activeElement && document.activeElement.id === 'mv-reason'"), 10), "the next field has the focus; got " + json.dumps(p.js("document.activeElement ? (document.activeElement.id || document.activeElement.className || document.activeElement.tagName) : null")))

    def test_a_real_click_on_move_right_after_typing_sends_what_was_typed(self, width=1400, theme="light"):
        if True:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                self.set_to(p)
                self.put(p, "reason", "<p>Because</p>")
                self.put(p, "source", "<p>Call</p>")
                self.put(p, "who", "<p>Still typing</p>", close=False)
                p.js("document.querySelector(%s).focus()" % json.dumps(self.box("who")))
                time.sleep(0.3)
                x, y, _ = p.box("#mv-go")
                p.mouse("mouseMoved", x, y)
                p.mouse("mousePressed", x, y, buttons=1)
                p.mouse("mouseReleased", x, y)
                p.until("!document.querySelector('.mvm-form') || !!document.querySelector('.mvm-problems p')", "sent or refused")
                rb = self.rebaseline()
                self.assertIsNotNone(rb, "a move was sent; the form said: " + str(p.js("[...document.querySelectorAll('.mvm-problems p')].map(e => e.textContent)")))
                self.assertEqual(rb["agreed_with"], "Still typing")

    def test_hostile_words_are_sent_as_one_plain_line(self, width=1400, theme="light"):
        if True:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                self.set_to(p)
                self.put(p, "who", "<p>a%sb%sc%sd</p>" % (LS, NEL, PS))
                self.put(p, "reason", "<p>مرحبا \U0001F680 &lt;img src=x onerror=1&gt;</p>")
                self.put(p, "source", "<p>s</p>")
                p.js("document.querySelector('#mv-go').click()")
                p.until("!document.querySelector('.mvm-form') || !!document.querySelector('.mvm-problems p')", "sent or refused")
                rb = self.rebaseline()
                self.assertIsNotNone(rb, str(p.js("[...document.querySelectorAll('.mvm-problems p')].map(e => e.textContent)")))
                for k in ("agreed_with", "reason", "source"):
                    for ch in (LS, NEL, PS, "\n"):
                        self.assertNotIn(ch, rb[k], (k, repr(rb[k])))
                self.assertIn("\U0001F680", rb["reason"])

    def test_a_pasted_script_and_onerror_in_who_never_runs_or_is_kept_as_markup(self):
        for width, theme in COMBOS:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                p.js("document.getElementById('mv-who').click()")
                p.until("!!document.querySelector(%s)" % json.dumps(self.box("who")), "open")
                eye.paste(p, self.box("who"), "<p>Pat</p><img src=x onerror=\"window.__pwn=1\"><script>window.__pwn=2</script>", "Pat")
                p.js("document.querySelector(%s).blur()" % json.dumps(self.box("who")))
                p.until("!document.querySelector(%s)" % json.dumps(self.box("who")), "closed")
                self.assertFalse(p.js("!!window.__pwn"))
                self.assertEqual(p.js("document.querySelectorAll('.mvm-form img, .mvm-form script').length"), 0)
                self.assertEqual(p.js("document.getElementById('mv-who').textContent.trim()"), "Pat")

    def test_ten_thousand_characters_in_who_are_refused_in_the_form_not_lost(self):
        for width, theme in COMBOS:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                self.set_to(p)
                self.put(p, "who", "<p>" + "w" * 10000 + "</p>")
                self.put(p, "reason", "<p>r</p>")
                self.put(p, "source", "<p>s</p>")
                p.js("document.querySelector('#mv-go').click()")
                p.until("!!document.querySelector('.mvm-problems p')", "refused")
                self.assertTrue(p.js("!!document.querySelector('.mvm-form')"))
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_hostile_words_are_sent_as_one_plain_line_at_900_in_the_dark(self):
        self.test_hostile_words_are_sent_as_one_plain_line(900, "dark")

    def test_only_spaces_and_breaks_in_who_count_as_not_given(self):
        for width, theme in COMBOS:
            with chrome() as cdp:
                p = self.form(cdp, width, theme)
                self.set_to(p)
                self.put(p, "who", "<p>  %s</p><p>%s</p>" % (LS, NEL))
                self.put(p, "reason", "<p>r</p>")
                self.put(p, "source", "<p>s</p>")
                p.js("document.querySelector('#mv-go').click()")
                p.until("!!document.querySelector('.mvm-problems p')", "refused")
                self.assertTrue(p.js("!!document.querySelector('.mvm-form')"))
                self.assertIsNone(self.rebaseline())


if __name__ == "__main__":
    unittest.main()
