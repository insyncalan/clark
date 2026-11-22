"""Item 1352 (ask clark, new chat): the heading card and the status line as the prototype draws them, in the Classic theme (prototype 2.0).

Run: python3 dev/run_tests.py test_ask_first_run_classic_1352
Real browser, the real page with fictional demo data, at 1400 and 900 px. Every number below was measured in the prototype's own
panel (mock-up folder 1292-ask-clark-prototype, ask.js line 203 and 207, app.css lines 559, 590, 597-599) at 1400 and 900 px: the
same at both. The Cards theme keeps what it had: its card has no frame (it is still a block with one line under it).
Only the design and the format are compared; the prototype's own words are not pinned here beyond the ticket's wording.
"""
import unittest

import _testpage as testpage
from _real_server import real_server
from clark import page, theme as themes
from test_ask_panel import Stub
from test_report_editor import Base
from test_server import chrome

# What the prototype measures (computed styles), by selector. Colours are the Theme's tokens, so a Brand reaches them: not compared.
PROTO_CARD = {"borderTopWidth": "1px", "borderTopStyle": "solid", "borderTopLeftRadius": "12px", "paddingTop": "14px", "paddingLeft": "16px",
              "paddingRight": "16px", "paddingBottom": "14px", "fontSize": "14px"}
PROTO_H3 = {"fontSize": "15px", "marginBottom": "6px", "marginTop": "0px"}
PROTO_UL = {"paddingLeft": "18px", "marginBottom": "8px", "listStyleType": "disc"}
PROTO_LI = {"marginTop": "5px", "marginBottom": "5px", "fontSize": "14px"}
PROTO_TIP = {"fontSize": "13px", "marginTop": "0px", "marginBottom": "0px"}
PROTO_KBD = {"fontSize": "12px", "borderTopWidth": "1px", "borderTopLeftRadius": "4px", "paddingLeft": "5px", "paddingRight": "5px"}
PROTO_STATUS = {"fontSize": "13px", "paddingTop": "9px", "paddingLeft": "20px", "paddingRight": "20px"}
PROTO_LINK = {"fontSize": "14px", "textDecorationLine": "none"}
PROTO_STATUS_LINK = {"fontSize": "13px", "textDecorationLine": "none"}

READ = """(function (sel, keys) {
  var e = document.querySelector(sel); if (!e) return null;
  var c = getComputedStyle(e), o = {}; keys.forEach(function (k) { o[k] = c[k]; });
  var r = e.getBoundingClientRect(); o.w = Math.round(r.width); o.h = Math.round(r.height); o.left = Math.round(r.left); return o;
})"""
KEYS = ["borderTopWidth", "borderTopStyle", "borderTopLeftRadius", "paddingTop", "paddingLeft", "paddingRight", "paddingBottom", "fontSize",
        "marginTop", "marginBottom", "listStyleType", "textDecorationLine"]
CONTRAST = """(function (sel, bgSel) {
  function rgb(s) { var m = s.match(/[\\d.]+/g).map(Number); return m; }
  function lum(c) { return [0, 1, 2].reduce(function (a, i) { var v = c[i] / 255; v = v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); return a + v * [.2126, .7152, .0722][i]; }, 0); }
  var fg = rgb(getComputedStyle(document.querySelector(sel)).color), bg = rgb(getComputedStyle(document.querySelector(bgSel)).backgroundColor);
  var a = lum(fg), b = lum(bg); return (Math.max(a, b) + .05) / (Math.min(a, b) + .05);
})"""


class Classic(Base):
    THEME = "prototype-2.0"

    def setUp(self):
        super().setUp()
        self.stub = Stub()
        self.s.close()                                      # the page this class serves carries the Theme (or none, for Cards)
        theme = self.THEME
        css = themes.css(theme) if theme else None
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css) if css else testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        self.s.httpd.ask = self.stub

    def read(self, p, sel):
        return p.js(f"({READ})({sel!r}, {KEYS!r})")

    def at(self, p, width):
        p.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)


class ClassicLook(Classic):
    def check(self, got, want, what):
        self.assertIsNotNone(got, what + " is on the page")
        for k, v in want.items():
            self.assertEqual(got[k], v, f"{what} {k}")

    def test_the_card_and_the_status_line_measure_what_the_prototype_measures_at_1400_and_900(self):
        self.stub.standing = True
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                self.at(p, width)
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-panel')", f"opened at {width}")
                p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
                p.until("!document.querySelector('#ask-send').disabled && !!document.querySelector('#ask-first-run') && !!document.querySelector('#ask-instr')", "ready")
                card = self.read(p, "#ask-first-run")
                self.check(card, PROTO_CARD, f"{width} card")
                panel = p.js("(function () { var e = document.querySelector('#ask-panel'), r = e.getBoundingClientRect(); return [Math.round(r.left + e.clientLeft), e.clientWidth]; })()")
                self.assertEqual((card["left"] - panel[0], card["w"]), (20, panel[1] - 40), f"{width}: the card is 20 px in from each side of the panel, as the prototype's is")
                self.check(self.read(p, "#ask-first-run h3"), PROTO_H3, f"{width} heading")
                self.check(self.read(p, "#ask-first-run ul"), PROTO_UL, f"{width} list")
                self.check(self.read(p, "#ask-first-run li"), PROTO_LI, f"{width} bullet")
                self.check(self.read(p, "#ask-first-run p.ask-first-tip"), PROTO_TIP, f"{width} tip")
                self.check(self.read(p, "#ask-first-run kbd"), PROTO_KBD, f"{width} key")
                link = self.read(p, "#ask-first-run li a")
                self.check(link, PROTO_LINK, f"{width} link")
                self.assertGreaterEqual(link["h"], 24, f"{width}: the link is a target of 24 px or more")
                self.check(self.read(p, "#ask-status"), PROTO_STATUS, f"{width} status line")
                self.check(self.read(p, "#ask-instr"), PROTO_STATUS_LINK, f"{width} standing-instructions link")
                self.assertTrue(p.js("(function () { var c = document.querySelector('#ask-first-run'); return c.scrollWidth <= c.clientWidth && document.documentElement.scrollWidth <= document.documentElement.clientWidth; })()"),
                                f"{width}: nothing runs outside the card or the page")
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")

    def test_the_text_of_the_card_reads_4_5_to_1_in_light_and_dark(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                self.at(p, width)
                for scheme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{scheme}'")
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-first-run')", f"card at {width} {scheme}")
                    p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
                    for sel in ("#ask-first-run li", "#ask-first-run h3", "#ask-first-run p.ask-first-tip", "#ask-first-run li a"):
                        ratio = p.js(f"({CONTRAST})({sel!r}, '#ask-first-run')")
                        self.assertGreaterEqual(ratio, 4.5, f"{sel} at {width} {scheme}: {ratio:.2f}")
                    p.key("Escape", code="Escape", vk=27)
                    p.until("document.querySelector('#ask-panel') === null", "closed")


class ClassicWords(Classic):
    def test_the_card_and_the_status_line_say_the_tickets_words(self):
        self.stub.standing, self.stub.model = True, "Sonnet"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run') && !!document.querySelector('#ask-instr')", "card")
            self.assertEqual(p.js("document.querySelector('#ask-first-run h3').textContent"), "Ask about this project")
            li = "document.querySelectorAll('#ask-first-run li')"
            self.assertEqual(p.js(f"{li}[0].textContent"), "I read this project's work items, milestones and use cases. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.")
            self.assertEqual(p.js(f"{li}[1].textContent"), "I can suggest changes. Nothing is saved until you press Apply, and every change can be undone.")
            self.assertEqual(p.js(f"{li}[2].textContent"), "Your question and what it needs go to Claude. What will be sent? (Settings)")
            self.assertEqual(p.js("document.querySelector('#ask-first-run li a').textContent"), "What will be sent? (Settings)")
            self.assertEqual(p.js("document.querySelector('#ask-first-run p.ask-first-tip').textContent"), "Tip: press the sparkle on a work item, a section or a use case to ask about just that. Type / in the box for shortcuts.")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Ready. Reading this project's report data. Standing instructions on")
            self.assertEqual(p.js("document.querySelector('#ask-instr').textContent"), "Standing instructions on")


class CardsKeepsItsOwn(Classic):
    THEME = None

    def test_the_cards_theme_has_no_frame_on_the_card(self):
        """The rules above are the Classic theme's: Cards draws the card with the rules it had (a block with one line under it, no radius)."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            card = self.read(p, "#ask-first-run")
            self.assertEqual((card["borderTopWidth"], card["borderTopLeftRadius"]), ("0px", "0px"))

    def test_cards_is_as_on_main_the_three_plain_lines_and_the_model_in_the_status_line(self):
        self.stub.standing, self.stub.model = True, "Sonnet"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run') && !!document.querySelector('#ask-instr')", "card")
            card = "document.querySelector('#ask-first-run')"
            self.assertEqual(p.js(f"{card}.querySelectorAll('h3, ul, li, kbd, .ask-first-tip').length"), 0, "no new markup")
            self.assertEqual(p.js(f"[...{card}.querySelectorAll('p')].map(e => e.textContent)"), [
                "It reads what is in this project. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.",
                "It can suggest changes. Nothing is saved until you press Apply, and every change can be undone.",
                "Your question goes to Claude, which Anthropic runs."])
            self.assertEqual(p.js(f"{card}.querySelector('.ask-first-link a').textContent"), "Open the Asking card in Settings")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Answering with Sonnet. Standing instructions on.")


if __name__ == "__main__":
    unittest.main()
