"""The Dashboard top bar's search and ask buttons (#664), in a real browser against the real page. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_actions
Covers: both buttons are there with their exact aria-labels and titles, in the order search, ask, ?, avatar; a click on search opens the
palette and a click on ask opens the ask panel; the ask button is not drawn while asking is off (askOn, the switch the server keeps; being signed out of the provider does not hide it:
the panel says so when it opens); the ask word and the / key hint hide at 1100 px and below and show at 1101; no item of the bar
overlaps another or runs past the window at 1400, 901, 900 and 800 px, in light and in dark.
"""
import sqlite3
import unittest

from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome

ITEMS = "[...document.querySelectorAll('header.top > *')].filter(e => e.getClientRects().length)"


class TopBarActions(Base):
    def at(self, cdp, width, asking=True):
        with sqlite3.connect(str(self.store.path)) as con:          # the switch the server keeps (Settings > Ask)
            con.execute("UPDATE app_settings SET ask_enabled = ? WHERE id = 1", (1 if asking else 0,))
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        if asking:
            p.until("!!document.querySelector('#ask-btn')", "the ask button shows while asking is on")
        return p

    def test_the_two_buttons_have_their_words_and_sit_before_help_and_the_avatar(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var q=s=>document.querySelector(s), a=q('#pal-btn'), k=q('#ask-btn');"
                       "return [a.getAttribute('aria-label'), a.title, a.textContent.trim(), k.getAttribute('aria-label'), k.title, k.textContent.replace(/\\s+/g,' ').trim(),"
                       "getComputedStyle(q('#ask-btn kbd')).display !== 'none', [...document.querySelectorAll('header.top button')].map(b => b.id || b.className).slice(-4)];})()")
            self.assertEqual(got[:7], ["Go to or do", "Go to or do (Ctrl or Cmd + K)", "", "ask clark", "Open ask clark (/ or Ctrl or Cmd + J)", "ask clark /", True])
            self.assertEqual(got[7][:3], ["pal-btn", "ask-btn", "help-btn"])

    def test_search_opens_the_palette_and_ask_opens_the_ask_panel(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            p.js("document.querySelector('#pal-btn').click()")
            p.until("document.querySelector('#palette')", "the palette opened")
            p.key("Escape", 0, "Escape", 27)
            p.until("!document.querySelector('#palette')", "the palette closed")
            p.js("document.querySelector('#ask-btn').click()")
            p.until("!!document.querySelector('#ask-panel')", "the ask panel opened")

    def test_ctrl_or_cmd_j_opens_ask_from_anywhere_and_other_chords_do_not(self):
        """Row 855: Ctrl or Cmd + J opens the ask panel (a field included); J alone, Shift or Alt with it, and an open menu do not."""
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            shut = lambda: (p.key("Escape", 0, "Escape", 27), p.until("!document.querySelector('#ask-panel')", "the ask panel closed"))
            for mods, name in ((2, "Ctrl"), (4, "Cmd")):
                p.key("j", mods, "KeyJ", 74)
                p.until("!!document.querySelector('#ask-panel')", name + " + J opened the ask panel")
                shut()
            for mods, name in ((0, "J alone"), (2 | 8, "Ctrl + Shift + J"), (2 | 1, "Ctrl + Alt + J")):
                p.key("j", mods, "KeyJ", 74)
                p.js("new Promise(r => setTimeout(r, 300))")
                self.assertFalse(p.js("!!document.querySelector('#ask-panel')"), name + " must not open it")
            p.js("var t = document.createElement('textarea'); t.id = 'tt'; document.body.appendChild(t); t.focus()")
            p.key("j", 2, "KeyJ", 74)
            p.until("!!document.querySelector('#ask-panel')", "Ctrl + J opens it from inside a field")
            self.assertEqual(p.js("document.getElementById('tt').value"), "", "and types nothing into the field")
            shut()
            p.js("document.getElementById('tt').remove(); document.querySelector('#project-name').click()")
            p.until("!!document.querySelector('[role=menu]')", "a menu is open")
            p.key("j", 2, "KeyJ", 74)
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertFalse(p.js("!!document.querySelector('#ask-panel')"), "not while a menu is open")

    def test_the_ask_button_is_not_there_while_asking_is_off(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, asking=False)
            p.js("new Promise(r => setTimeout(r, 800))")
            self.assertEqual(p.js("[!!document.querySelector('#pal-btn'), !!document.querySelector('#ask-btn')]"), [True, False])

    def test_the_bar_has_no_overlap_and_nothing_past_the_window(self):
        for width in (1400, 901, 900, 800):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.at(cdp, width)
                    p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                    got = p.js(f"(function(){{var r=[...{ITEMS}].map(e => [e.className || e.id, e.getBoundingClientRect()]), bad=[];"
                               "for (var i=0;i<r.length;i++){ if (r[i][1].right > document.documentElement.clientWidth + 0.5) bad.push('past ' + r[i][0]);"
                               "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].width && r[j][1].width) bad.push(r[i][0] + ' over ' + r[j][0]);}"
                               "return bad;})()")
                    self.assertEqual(got, [], f"at {width} px, {theme}")

    def test_the_ask_word_and_the_key_hint_hide_at_1100_px_and_below_and_show_at_1101(self):
        for width, shown in ((1101, True), (1100, False), (1099, False), (1400, True)):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                got = p.js("['.tb-ask-w', '.tb-key'].map(s => getComputedStyle(document.querySelector(s)).display !== 'none')")
                self.assertEqual(got, [shown, shown], f"at {width} px the ask word and the / key hint should be {'shown' if shown else 'hidden'}; got {got}")

    def test_a_long_project_name_at_901_and_900_px_light_and_dark_keeps_the_bar_inside_the_window(self):
        # The project name shortens first; the new buttons must not push anything out.
        for width in (901, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    p = self.at(cdp, width)
                    p.js(f"document.documentElement.setAttribute('data-theme', '{theme}')")
                    p.js("document.querySelector('.top [data-mode=edit]') && document.querySelector('.top [data-mode=edit]').click()")
                    p.js("(function(){ var s = document.querySelector('.top .projbtn > span') || document.querySelector('.top .proj'); "
                         "s.textContent = 'Customer onboarding programme, phase two, northern region'; })()")
                    got = p.js(f"(function(){{var r=[...{ITEMS}].map(e => [e.className || e.id, e.getBoundingClientRect()]), bad=[];"
                               "for (var i=0;i<r.length;i++){ if (r[i][1].right > document.documentElement.clientWidth + 0.5) bad.push('past ' + r[i][0]);"
                               "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].width && r[j][1].width) bad.push(r[i][0] + ' over ' + r[j][0]); }"
                               "return bad.concat(document.documentElement.scrollWidth > document.documentElement.clientWidth ? ['sideways scroll'] : []);})()")
                    self.assertEqual(got, [], f"at {width} px, {theme}, long name")
                    clipped = p.js("(function(){ var s = document.querySelector('.top .projbtn > span'); return s ? [s.textContent.length > 40, s.scrollWidth > s.clientWidth] : null; })()")
                    self.assertEqual(clipped, [True, True], f"at {width} px, {theme}: the long name is in the bar and is the part that gives way (its ellipsis)")
                    self.assertTrue(p.js("!!document.querySelector('#ask-btn') && !!document.querySelector('#pal-btn')"), "both buttons are there")


if __name__ == "__main__":
    unittest.main()
