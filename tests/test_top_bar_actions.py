"""The Dashboard top bar's search and ask buttons (#664), in a real browser against the real page. Chrome is required: these tests fail, never skip, without it.

Run: python3 dev/run_tests.py test_top_bar_actions
Covers: both buttons are there with their exact aria-labels and titles, in the order search, ask, ?, avatar; a click on search opens the
palette and a click on ask opens the ask panel; the ask button is not there while asking is off; no item of the bar overlaps another or
runs past the window at 1400, 901, 900 and 800 px.
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
            self.assertEqual(got[:7], ["Go to or do", "Go to or do (Ctrl or Cmd + K)", "", "ask clark", "ask clark (/)", "ask clark /", True])
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

    def test_the_ask_button_is_not_there_while_asking_is_off(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400, asking=False)
            p.js("new Promise(r => setTimeout(r, 800))")
            self.assertEqual(p.js("[!!document.querySelector('#pal-btn'), !!document.querySelector('#ask-btn')]"), [True, False])

    def test_the_bar_has_no_overlap_and_nothing_past_the_window(self):
        for width in (1400, 901, 900, 800):
            with self.subTest(width=width), chrome() as cdp:
                p = self.at(cdp, width)
                got = p.js(f"(function(){{var r=[...{ITEMS}].map(e => [e.className || e.id, e.getBoundingClientRect()]), bad=[];"
                           "for (var i=0;i<r.length;i++){ if (r[i][1].right > document.documentElement.clientWidth + 0.5) bad.push('past ' + r[i][0]);"
                           "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].top < r[j][1].bottom - 0.5 && r[j][1].top < r[i][1].bottom - 0.5 && r[i][1].width && r[j][1].width) bad.push(r[i][0] + ' over ' + r[j][0]);}"
                           "return bad;})()")
                self.assertEqual(got, [], f"at {width} px")
                words = p.js("getComputedStyle(document.querySelector('.tb-ask-w')).display")
                self.assertEqual(words == "none", width <= 1100)

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
                               "for (var j=i+1;j<r.length;j++) if (r[i][1].left < r[j][1].right - 0.5 && r[j][1].left < r[i][1].right - 0.5 && r[i][1].top < r[j][1].bottom - 0.5 && r[j][1].top < r[i][1].bottom - 0.5 && r[i][1].width && r[j][1].width) bad.push(r[i][0] + ' over ' + r[j][0]); }"
                               "return bad.concat(document.documentElement.scrollWidth > document.documentElement.clientWidth ? ['sideways scroll'] : []);})()")
                    self.assertEqual(got, [], f"at {width} px, {theme}, long name")
                    self.assertTrue(p.js("!!document.querySelector('#ask-btn') && !!document.querySelector('#pal-btn')"), "both buttons are there")


if __name__ == "__main__":
    unittest.main()
