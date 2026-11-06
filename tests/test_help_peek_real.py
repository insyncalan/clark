"""#645 integration: the Help peek with the REAL context text (contextText in helpLogic.js, helpContent.json "context"), no stand-in.

Run: python3 dev/run_tests.py test_help_peek_real
test_help_peek.py proves each of the owner's rules with a made-up text; this file proves the same rules hold with the text that ships, for every
screen in LIVE_SCREENS, and that the Settings card lines are drawn. The layout and colours at 1400 and 900 px, light and dark, are checked on
every screen. Set CLARK_SHOT_DIR to a folder to also save the Settings peek (1400 px) as a picture.
"""
import base64
import json
import os
import re
import unittest
from pathlib import Path

import test_help_peek as base
from test_server import chrome

GONE, KEY = base.GONE, base.KEY
SRC = Path(__file__).resolve().parent.parent / "src" / "clark" / "page" / "src" / "help"
CONTEXT = json.loads((SRC / "helpContent.json").read_text(encoding="utf-8"))["context"]
LIVE_SCREENS = json.loads(re.search(r"LIVE_SCREENS = (\[.*?\]);", (SRC / "helpStore.js").read_text(encoding="utf-8")).group(1))
BY = {c["page"]: c for c in CONTEXT}
TAB = {"ref": "reference", "howto": "howto"}


def goto(p, screen):
    p.js("window.clarkPage.show(%s)" % json.dumps("dashboard" if screen.startswith("dashboard") else screen))
    p.until("!!document.querySelector('#main')", "the screen")
    if screen == "dashboard+edit":
        p.edit()
    p.js("document.activeElement && document.activeElement.blur()")


class Real(base.Base):
    page, q = base.Peek.page, base.Peek.q              # the peek tests' own helpers, none of their tests

    def setUp(self):
        super().setUp()
        self.stub = base.Stub()
        self.s.httpd.ask = self.stub

    def real(self, cdp):
        return self.page(cdp, text=False)              # no useText call: contextText answers

    def test_every_live_screen_has_context_text(self):
        self.assertEqual(sorted(BY), sorted(LIVE_SCREENS))
        # Measured on the merged tree (v10-integration): 5 screens, 20 sentences (4, 4, 4, 5, 3), 9 Settings cards. A floor, never lowered without a reason.
        self.assertGreaterEqual(len(BY), 5)
        self.assertGreaterEqual(sum(len(c["s"]) for c in CONTEXT), 20)
        self.assertGreaterEqual(len(BY["settings"]["cards"]), 9)

    def test_each_screen_opens_with_its_real_text_and_closes_by_every_rule(self):
        with chrome() as cdp:
            p = self.real(cdp)
            for screen in LIVE_SCREENS:
                c = BY[screen]
                goto(p, screen)
                self.q(p)
                p.until("!!document.querySelector('#help-peek')", f"{screen}: opened on ?")
                self.assertEqual(p.js("document.querySelector('#help')"), None, f"{screen}: not the full Help")
                self.assertEqual(p.js("document.querySelector('#help-peek h2').textContent"), c["title"], screen)
                lines = p.js("[...document.querySelectorAll('#help-peek .hpk-line')].map(e => e.textContent)")
                self.assertEqual(len(lines), len(c["s"]), f"{screen}: every sentence is drawn")
                self.assertTrue(all(l.strip() for l in lines), screen)
                self.assertFalse([l for l in lines if re.search(r"[<>*{}]|&[a-z]+;", l)], f"{screen}: plain text, no markup showing")
                cards = p.js("[...document.querySelectorAll('#help-peek .hpk-cards li')].map(e => [e.querySelector('b') ? e.querySelector('b').textContent : '', e.textContent])")
                want = c.get("cards", [])
                self.assertEqual([x[0] for x in cards], [k["title"] for k in want], f"{screen}: the card names (name || title)")
                for (name, text), k in zip(cards, want):
                    self.assertGreater(len(text), len(name) + 5, f"{screen}: the line of card {k['card']} is drawn")
                self.assertEqual(p.js("document.querySelector('#help-peek [data-hpk-full]').textContent"), "Open full Help")
                self.q(p)
                p.until(GONE, f"{screen}: a second ? closed it")
                self.q(p)
                p.until("!!document.querySelector('#help-peek')", f"{screen}: reopened")
                p.key("Escape", code="Escape", vk=27)
                p.until(GONE, f"{screen}: Esc closed it")
                self.q(p)
                p.until("!!document.querySelector('#help-peek')", f"{screen}: reopened")
                p.mouse("mousePressed", 300, 700)
                p.mouse("mouseReleased", 300, 700)
                p.until(GONE, f"{screen}: a click outside closed it")
                p.js("document.querySelector('#help-btn').click()")
                p.until("!!document.querySelector('#help-peek')", f"{screen}: the button opened it")
                p.js("document.querySelector('#help-btn').click()")
                p.until(GONE, f"{screen}: the button closed it")

    def test_the_foot_link_opens_the_full_help_on_the_entry_named(self):
        with chrome() as cdp:
            p = self.real(cdp)
            for screen in LIVE_SCREENS:
                full = BY[screen]["full"]
                goto(p, screen)
                self.q(p)
                p.until("!!document.querySelector('#help-peek')", f"{screen}: opened")
                p.js("document.querySelector('#help-peek [data-hpk-full]').click()")
                p.until("!!document.querySelector('#help')", f"{screen}: the full Help")
                self.assertEqual(p.js("document.querySelector('#help-peek')"), None, f"{screen}: the peek closed")
                self.assertEqual(p.js("document.querySelector('#hpTab-%s').getAttribute('aria-selected')" % TAB[full.split("-")[0]]), "true", f"{screen}: on the tab of {full}")
                p.until("!!document.querySelector('[id$=\"%s\"]')" % full, f"{screen}: {full} is drawn (a shown entry, never a held one)")
                p.js("document.querySelector('#hpBack').click()")
                p.until("!document.querySelector('#help') && !!document.querySelector('#main')", f"{screen}: Back")

    def test_row_896_the_peek_lists_the_how_to_articles_of_the_open_page(self):
        """Row 896: the profile menu's Help and the ? key open the same peek; under the how-to tab's own word it lists the how-to articles whose
        go page is the open one, each opening its article; at 1400 and 900 px, light and dark."""
        content = json.loads((SRC / "helpContent.json").read_text(encoding="utf-8"))
        word = dict(content["tabs"])["howto"]
        held = json.loads((SRC / "helpLater.json").read_text(encoding="utf-8")).get("howto", {})      # held articles are not shown
        want = {s: [t["t"] for t in content["howto"]["tasks"] if t["id"] not in held and t.get("go") and t["go"].split("#")[0] == s] for s in LIVE_SCREENS}
        self.assertTrue(want["work"] and want["dashboard+edit"], "the data has articles for Work items and the Edit dashboard")
        arts = "[...document.querySelectorAll('#help-peek [data-hpk-art]')].map(e => e.textContent)"
        with chrome() as cdp:
            p = self.real(cdp)
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    for screen in LIVE_SCREENS:
                        goto(p, screen)
                        if screen == "dashboard" and p.js("document.querySelector('#report').dataset.mode") == "edit":
                            p.view()                                  # the Dashboard in View, not left in Edit by the last pass
                        self.q(p)
                        p.until("!!document.querySelector('#help-peek')", f"{scheme} {w} {screen}: opened on ?")
                        by_key = p.js(arts)
                        self.assertEqual(by_key, want[screen], f"{scheme} {w} {screen}: the open page's articles")
                        if want[screen]:
                            self.assertEqual(p.js("document.querySelector('#help-peek .hpk-sub').textContent"), word, f"{screen}: under the how-to tab's word")
                        self.q(p)
                        p.until(GONE, f"{screen}: closed")
                        p.js("document.querySelector('#profile-btn').click()")
                        p.until("!!document.querySelector('#profile-menu')", "menu")
                        p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]')].find(e => e.textContent === 'Help').click()")
                        p.until("!!document.querySelector('#help-peek')", f"{scheme} {w} {screen}: the menu's Help opened the peek")
                        self.assertEqual(p.js("document.querySelector('#help')"), None)
                        self.assertEqual(p.js(arts), want[screen], f"{screen}: the same articles from the menu")
                        p.key("Escape", code="Escape", vk=27)
                        p.until(GONE, f"{screen}: Esc closed it")
            goto(p, "work")
            self.q(p)
            p.until("!!document.querySelector('#help-peek [data-hpk-art]')", "an article link")
            place = p.js("document.querySelector('#help-peek [data-hpk-art]').dataset.hpkArt")
            p.js("document.querySelector('#help-peek [data-hpk-art]').click()")
            p.until("!!document.querySelector('#help')", "the full Help")
            p.until("!!document.querySelector('[id$=\"%s\"]')" % place, "the article is drawn")
            self.assertEqual(p.js("document.querySelector('#help-peek')"), None)

    def test_leaving_the_page_closes_it_with_the_real_text(self):
        with chrome() as cdp:
            p = self.real(cdp)
            goto(p, "work")
            self.q(p)
            p.until("!!document.querySelector('#help-peek')", "opened on Work items")
            p.js("window.clarkPage.show('milestones')")
            p.until(GONE, "leaving the page closed it")

    def test_it_fits_and_reads_at_both_widths_in_both_themes_on_every_screen(self):
        shots = os.environ.get("CLARK_SHOT_DIR")
        with chrome() as cdp:
            p = self.real(cdp)
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    for screen in LIVE_SCREENS:
                        goto(p, screen)
                        self.q(p)
                        p.until("!!document.querySelector('#help-peek')", f"{scheme} {w} {screen}: open")
                        p.until("(function(){var r=document.querySelector('#help-peek').getBoundingClientRect(); return r.right <= innerWidth + 1})()", f"{scheme} {w} {screen}: slid in")
                        got = p.js("""(function(){var e=document.querySelector('#help-peek'),r=e.getBoundingClientRect(),cs=getComputedStyle(e);
                          var f=document.querySelector('#help-peek [data-hpk-full]').getBoundingClientRect();
                          return {l:r.left,r:r.right,t:r.top,b:r.bottom,sw:e.scrollWidth,cw:e.clientWidth,fb:f.bottom,fr:f.right,bg:cs.backgroundColor,fg:cs.color,
                                  page:document.documentElement.scrollWidth<=innerWidth}})()""")
                        where = f"{scheme} {w} {screen}: {got}"
                        self.assertTrue(got["page"], f"{where}: no sideways scroll")
                        self.assertTrue(got["l"] >= 0 and got["r"] <= w + 1 and got["t"] >= 0 and got["b"] <= 901, f"{where}: in view")
                        self.assertLessEqual(got["sw"], got["cw"] + 1, f"{where}: nothing sideways inside")
                        self.assertTrue(got["fb"] <= 901 and got["fr"] <= w, f"{where}: the foot link is in view")
                        self.assertNotEqual(got["bg"], got["fg"], f"{where}: text differs from its ground")
                        if shots and screen == "settings" and w == 1400:
                            Path(shots, f"peek-settings-{w}-{scheme}.png").write_bytes(base64.b64decode(cdp.call("Page.captureScreenshot", {"format": "png"}, p.sid)["data"]))
                        self.q(p)
                        p.until(GONE, f"{where}: closed")


if __name__ == "__main__":
    unittest.main()
