"""Row 1005, a second hostile pass: inputs the first hostile tests did not reach.

Run: python3 dev/run_tests.py test_b4_hostile_1005
plainLine and a next-line character; the Movement form's Who agreed it / Reason / Source (the Tab order through the three, a real click on
Move straight after typing, a pasted script and onerror, a line break kept out of what is sent, 10,000 characters, emoji and right-to-left
words); a RAID card's Own words (the 400 and 401 boundary counted in emoji, saving twice quickly, Undo after a save, a paste with a script,
10,000 characters, U+2028 and U+0085, right-to-left words, Escape after an over-long try). 1400 and 900 wide, light and dark. Made-up data only.
"""
import json
import time
import unittest

from _demo import USER
from test_report_editor import Base as PageBase
from test_server import chrome
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


class Raid(PageBase):
    seed, stored, wait_for, open_editor, typed = (eye.Raid.__dict__[k] for k in ("seed", "stored", "wait_for", "open_editor", "typed"))

    def edit_open(self, p, view, box):
        p.js(f"document.querySelector({json.dumps(view)}).click()")
        p.until(f"!!document.querySelector({json.dumps(box)})", "opened")

    def changes(self):
        return len([s for s in self.sent if s[0] == "change"])

    def each(self, own="Old words"):
        for width, theme in COMBOS:
            self.seed(own)
            with chrome() as cdp:
                p, view, box = self.open_editor(cdp)
                look(p, width, theme)
                yield p, view, box
            # report_sections rows are never deleted (Step.delete refuses them); seed() makes the next combo's section

    def test_400_emoji_save_and_401_emoji_do_not(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "\U0001F680" * 401)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.until(f"!!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')", "401 emoji say too long")
            self.assertEqual(self.stored(), "Old words")
            self.typed(p, box, "\U0001F680" * 400)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored() == "\U0001F680" * 400), "400 emoji (800 UTF-16 units) are saved, or the server refused them")

    def test_cmd_enter_twice_and_a_blur_after_it_save_once(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "Twice")
            n = self.changes()
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored() == "Twice"))
            time.sleep(0.6)
            self.assertEqual(self.changes(), n + 1, "one save, not two")
            self.assertFalse(p.js(f"!!document.querySelector({json.dumps(box)})"), "closed")

    def test_undo_after_a_save_puts_the_old_words_back_and_the_view_shows_them(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "New words")
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored() == "New words"))
            p.until("!!document.querySelector('.toast [data-undo]')", "an Undo is offered")
            p.js("document.querySelector('.toast [data-undo]').click()")
            self.assertTrue(self.wait_for(lambda: self.stored() == "Old words"), "Undo restores the old words")
            p.until(f"document.querySelector({json.dumps(view)}).textContent.indexOf('Old words') >= 0", "the card shows the old words")

    def test_a_paste_with_a_script_and_an_onerror_is_kept_as_text_only(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            eye.paste(p, box, "<p>Hi</p><img src=x onerror=\"window.__pwn=1\"><script>window.__pwn=2</script><p onclick=\"window.__pwn=3\">there</p>", "Hi there")
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: "Hi" in self.stored()))
            time.sleep(0.5)
            got = self.stored()
            self.assertNotIn("<", got)
            self.assertNotIn("onerror", got)
            self.assertFalse(p.js("!!window.__pwn"))
            self.assertEqual(p.js(f"document.querySelectorAll('[data-id={json.dumps(self.sec)}] img, [data-id={json.dumps(self.sec)}] script').length"), 0)

    def test_ten_thousand_characters_pasted_are_refused_in_words_and_the_page_holds(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            eye.paste(p, box, "<p>" + "word " * 2000 + "</p>", "word " * 2000)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.until(f"!!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')", "a message")
            self.assertEqual(self.stored(), "Old words")
            self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"))

    def test_line_separators_and_next_line_never_reach_the_store(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "a%sb%sc%sd" % (LS, NEL, PS))
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored().startswith("a")), "saved")
            got = self.stored()
            for ch in (LS, NEL, PS, "\n"):
                self.assertNotIn(ch, got, repr(got))

    def test_a_next_line_character_between_words_is_a_space_not_nothing(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "one%stwo" % NEL)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored().startswith("one")))
            self.assertEqual(self.stored(), "one two")

    def test_right_to_left_and_emoji_words_come_back_as_typed(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            words = "\u0645\u0631\u062d\u0628\u0627 \u05e9\u05dc\u05d5\u05dd \U0001F468 \U0001F680 ok"
            self.typed(p, box, words)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            self.assertTrue(self.wait_for(lambda: self.stored() == words), repr(self.stored()))

    def test_a_joined_emoji_or_a_direction_mark_is_refused_and_the_editor_says_so_in_the_editor(self):
        """The store refuses hidden characters. The refusal must not leave the editor open with only a toast that is gone in seconds."""
        for p, view, box in self.each():
            for words in ("\U0001F468\u200d\U0001F469 ok", "abc\u200fdef"):
                self.edit_open(p, view, box) if not p.js(f"!!document.querySelector({json.dumps(box)})") else None
                self.typed(p, box, words)
                p.key("Enter", modifiers=2, code="Enter", vk=13)
                time.sleep(1.0)
                self.assertEqual(self.stored(), "Old words")
                if p.js(f"!!document.querySelector({json.dumps(box)})"):
                    self.assertTrue(p.js(f"!!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')"), "open with no message in the editor for " + repr(words))

    def test_escape_after_an_over_long_try_keeps_the_old_words(self):
        for p, view, box in self.each():
            self.edit_open(p, view, box)
            self.typed(p, box, "z" * 401)
            p.key("Enter", modifiers=2, code="Enter", vk=13)
            p.until(f"!!document.querySelector('[data-id={json.dumps(self.sec)}] .rt-problem')", "message")
            p.key("Escape", code="Escape", vk=27)
            p.until(f"!document.querySelector({json.dumps(box)})", "closed")
            self.assertEqual(self.stored(), "Old words")
            self.assertIn("Old words", p.js(f"document.querySelector({json.dumps(view)}).textContent"))


class Movement(tmp.Base):
    def form(self, cdp, width, theme):
        p = self.visit(cdp, width=width, theme=theme)
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
            p.js("document.querySelector(%s).blur()" % json.dumps(self.box(k)))
            p.until("!document.querySelector(%s)" % json.dumps(self.box(k)), "closed " + k)

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
                p.js("document.querySelector(%s).focus()" % json.dumps(self.box("who")))
                p.key("Tab", code="Tab", vk=9)
                time.sleep(0.5)
                self.assertFalse(p.js("!!document.querySelector(%s)" % json.dumps(self.box("who"))), "closed on Tab")
                self.assertIn("Pat Example", p.js("document.getElementById('mv-who').textContent"), "kept")
                self.assertTrue(p.js("!!document.querySelector('.mvm-form')"), "form stays")

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
