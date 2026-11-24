"""Item 1352 (ask clark, new chat): the heading card and the status line as the prototype draws them, in the Classic theme (prototype 2.0).

Run: python3 dev/run_tests.py test_ask_first_run_classic_1352
Real browser, the real page with fictional demo data, at 1400 and 900 px. Every number below was measured in the prototype's own
panel (mock-up folder 1292-ask-clark-prototype, ask.js line 203 and 207, app.css lines 559, 590, 597-599) at 1400 and 900 px: the
same at both. The Cards theme keeps what it had: its card has no frame (it is still a block with one line under it).
Only the design and the format are compared; the prototype's own words are not pinned here beyond the ticket's wording.
"""
import threading
import time
import unittest

import _testpage as testpage
from _new_page import reload_to_new_page
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
            self.assertEqual(p.js(f"{li}.length"), 5)
            self.assertEqual(p.js(f"{li}[3].textContent"), "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question.")
            self.assertEqual(p.js(f"{li}[4].textContent"), "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out.")
            self.assertEqual(p.js("document.querySelector('#ask-first-run li a').textContent"), "What will be sent? (Settings)")
            self.assertEqual(p.js("document.querySelector('#ask-first-run p.ask-first-tip').textContent"), "Tip: press the sparkle on a work item, a section or a use case to ask about just that. Type / in the box for slash commands.")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Ready. Reading this project's report data. Standing instructions on")
            self.assertEqual(p.js("document.querySelector('#ask-instr').textContent"), "Standing instructions on")


class ClassicProviderNamed(Classic):
    def test_the_passages_bullet_names_the_provider_in_use(self):
        """Row 1537 AP6: the passages sentence names ChatGPT when that is the provider; the Mac sentence is the same for every provider."""
        self.stub.provider = "ChatGPT"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            li = "document.querySelectorAll('#ask-first-run li')"
            self.assertEqual(p.js(f"{li}[3].textContent"), "Passages from the folders you list go to ChatGPT, which OpenAI runs, only when they contain words from your question.")
            self.assertEqual(p.js(f"{li}[4].textContent"), "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out.")


class FoldersSaid:
    """What the server's folders route says for the open project: nothing set, or its own folders, or only folders for all projects."""

    def __init__(self, own=(), shared=(), status=200, ok=True, gate=None):
        self.own, self.shared, self.status, self.ok, self.gate = list(own), list(shared), status, ok, gate

    def read(self, code):
        if self.gate is not None:
            self.gate.wait(30)
        return self.status, {"ok": self.ok, "folders": self.own, "shared": self.shared}


BULLET = "document.querySelectorAll('#ask-first-run li')[0].textContent"
PLAIN = "I read this project's work items, milestones and use cases. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings."
NAMED = "I read this project's work items, milestones and use cases and the folders you named. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings."


class ClassicFolders(Classic):
    def bullet(self, folders):
        self.s.httpd.ask_folders = folders
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            p.until(f"{BULLET} === {(NAMED if folders.own or folders.shared else PLAIN)!r}", "the bullet settles on what the folders say")
            return p.js(BULLET)

    def test_bullet_one_names_the_folders_only_when_the_project_has_some(self):
        self.assertEqual(self.bullet(FoldersSaid(own=["/home/x/notes"])), NAMED)

    def test_bullet_one_names_the_folders_when_only_folders_for_all_projects_are_set(self):
        self.assertEqual(self.bullet(FoldersSaid(shared=["/home/x/all"])), NAMED)

    def test_bullet_one_is_the_plain_line_when_the_project_has_no_folders(self):
        self.assertEqual(self.bullet(FoldersSaid()), PLAIN)


class ClassicFoldersWaiting(Classic):
    def test_bullet_one_is_the_plain_line_until_the_folders_answer_comes_and_then_names_them(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.s.httpd.ask_folders = FoldersSaid(own=["/home/x/notes"], gate=gate)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            self.assertEqual(p.js(BULLET), PLAIN, "the answer has not come: no folders are claimed")
            gate.set()
            p.until(f"{BULLET} === {NAMED!r}", "the bullet names the folders once the answer is in")


class FoldersByProject:
    """The folders route for two projects: ABC has some, any other has none. A project answers only when its event in `gates` is set
    (a project with no event answers at once), so the test can look at the page while an answer is still out."""

    def __init__(self, gates):
        self.asked, self.gates = [], gates

    def read(self, code):
        self.asked.append(code)
        if code in self.gates:
            self.gates[code].wait(30)
        return 200, {"ok": True, "folders": ["/home/x/notes"] if code == "ABC" else [], "shared": []}


class ClassicFoldersProjectSwitch(Classic):
    def test_switching_to_a_project_without_folders_goes_back_to_the_plain_line_even_with_the_panel_open(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.s.httpd.ask_folders = said = FoldersByProject({"ZZZ": gate})
        with self.store.step("dashboard", "tester") as st:
            st.create("projects", {"code": "ZZZ", "name": "Second Programme", "health": "On track"})
        with chrome() as cdp:
            p = self.visit(cdp)
            # The page reloads for another project when served over http; this keeps it in place (as a project switch inside one page does),
            # so what the open panel does with the new project is what is seen.
            p.js("URLSearchParams.prototype.get = function (k) { return k === 'project' ? (location.hash.match(/p=([A-Z]+)/) || [])[1] || '' : null; }")
            for width in (1400, 900):
                self.at(p, width)
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-first-run')", f"card at {width}")
                p.until(f"{BULLET} === {NAMED!r}", f"project ABC names its folders at {width}")
                gate.clear()
                said.asked.clear()
                p.js("location.hash = '#dashboard&p=ZZZ'")
                p.until(f"{BULLET} === {PLAIN!r}", f"the plain line comes back at once on the switch, before ZZZ answers, at {width}")
                for _ in range(100):
                    if "ZZZ" in said.asked:
                        break
                    time.sleep(0.1)
                self.assertEqual(said.asked.count("ZZZ"), 1, "ZZZ's folders were asked for")
                gate.set()
                p.until(f"{BULLET} === {PLAIN!r}", f"ZZZ has none, so it stays plain at {width}")
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until(f"{BULLET} === {NAMED!r}", f"back on ABC the folders are named again at {width}")
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")


    def test_an_answer_for_the_old_project_that_comes_late_is_not_taken_for_the_new_one(self):
        gate = threading.Event()
        self.addCleanup(gate.set)
        self.s.httpd.ask_folders = said = FoldersByProject({"ABC": gate})
        with self.store.step("dashboard", "tester") as st:
            st.create("projects", {"code": "ZZZ", "name": "Second Programme", "health": "On track"})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("URLSearchParams.prototype.get = function (k) { return k === 'project' ? (location.hash.match(/p=([A-Z]+)/) || [])[1] || '' : null; }")
            for width in (1400, 900):
                self.at(p, width)
                gate.clear()
                p.key("/", code="Slash", vk=191)
                p.until("!!document.querySelector('#ask-first-run')", f"card at {width}")
                p.js("location.hash = '#dashboard&p=ZZZ'")
                for _ in range(100):
                    if "ZZZ" in said.asked:
                        break
                    time.sleep(0.1)
                self.assertIn("ZZZ", said.asked)
                p.until(f"{BULLET} === {PLAIN!r}", f"ZZZ has none: plain at {width}")
                gate.set()                                   # ABC's answer (it has folders) arrives now, after the switch
                time.sleep(1)
                self.assertEqual(p.js(BULLET), PLAIN, f"the old project's late answer does not name folders for the new one at {width}")
                p.js("location.hash = '#dashboard&p=ABC'")
                p.until(f"{BULLET} === {NAMED!r}", "back on ABC")
                p.key("Escape", code="Escape", vk=27)
                p.until("document.querySelector('#ask-panel') === null", "closed")


class ClassicFoldersRefused(Classic):
    def plain_after(self, folders):
        self.s.httpd.ask_folders = folders
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim().length > 0"), True)
            self.assertEqual(p.js(BULLET), PLAIN)

    def test_bullet_one_stays_plain_when_the_folders_answer_is_not_ok(self):
        self.plain_after(FoldersSaid(own=["/home/x/notes"], ok=False))

    def test_bullet_one_stays_plain_when_the_folders_answer_is_not_a_200(self):
        self.plain_after(FoldersSaid(own=["/home/x/notes"], status=500))


class ClassicStates(Classic):
    def test_the_off_state_says_ready_in_the_status_line_and_shows_the_card(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-off') && !!document.querySelector('#ask-first-run')", "off panel")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Ready. Reading this project's report data.")

    def test_the_working_state_says_working_in_the_status_line(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Summarise the risks")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Working. You can close this: it carries on.")
            self.stub.hold.set()

    def ask_one(self, p, text):
        p.until("!!document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready")
        p.js("document.querySelector('#ask-box').focus()")
        p.type(text)
        p.js("document.querySelector('#ask-send').click()")

    def test_pin_a_closing_the_panel_while_a_question_is_out_and_opening_it_again_shows_the_answer(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            self.ask_one(p, "Summarise the risks")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            p.key("Escape", code="Escape", vk=27)
            p.until("document.querySelector('#ask-panel') === null", "the panel is closed")
            self.stub.hold.set()
            p.until("document.querySelector('#ask-btn').getAttribute('aria-label') === 'ask clark, 1 answer ready'", "the answer landed while closed")
            p.js("document.querySelector('#ask-btn').click()")
            p.until("!!document.querySelector('#ask-panel')", "the panel is open again")
            p.until("document.body.textContent.indexOf('The pilot goes live in March.') >= 0", "the answer is shown")
            self.assertEqual(self.stub.count("stop"), 0)

    def test_pin_b_page_side_after_a_reload_a_new_question_that_the_server_calls_busy_is_shown_the_busy_words(self):
        # Page side only: the stub answers "busy" itself, as the real ask_claude does while a run holds its lock (ask_claude.py BUSY);
        # this pins that the reloaded page shows those words. That the server refuses the second run is not tested here.
        self.stub.hold.clear()
        run = {"on": False}
        real_ask = self.stub.ask

        def ask(body):
            if run["on"]:
                self.stub.calls.append(("ask", body))
                return 200, {"ok": False, "code": "busy", "message": "Another question is being answered. Wait for it, or press Stop."}
            run["on"] = True
            try:
                return real_ask(body)
            finally:
                run["on"] = False
        self.stub.ask = ask
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            self.ask_one(p, "First question")
            p.until("!!document.querySelector('#ask-stop')", "the first question is out")
            reload_to_new_page(p.js, what="the page reloaded")
            p.key("/", code="Slash", vk=191)
            self.ask_one(p, "Second question")
            p.until("document.body.textContent.indexOf('Another question is being answered.') >= 0", "the second question is told to wait")
            self.stub.hold.set()


class CardsKeepsItsOwn(Classic):
    THEME = None

    def test_cards_status_line_says_working_while_a_question_is_out(self):
        self.stub.hold.clear()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-box') && !document.querySelector('#ask-send').disabled", "ready")
            p.js("document.querySelector('#ask-box').focus()")
            p.type("Summarise the risks")
            p.js("document.querySelector('#ask-send').click()")
            p.until("!!document.querySelector('#ask-stop')", "the question is out")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Working")
            self.stub.hold.set()

    def test_the_cards_theme_has_no_frame_on_the_card(self):
        """The rules above are the Classic theme's: Cards draws the card with the rules it had (a block with one line under it, no radius)."""
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            card = self.read(p, "#ask-first-run")
            self.assertEqual((card["borderTopWidth"], card["borderTopLeftRadius"]), ("0px", "0px"))

    def test_cards_keeps_its_line_even_when_the_project_has_folders(self):
        self.s.httpd.ask_folders = FoldersSaid(own=["/home/x/notes"])
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("/", code="Slash", vk=191)
            p.until("!!document.querySelector('#ask-first-run')", "card")
            self.assertEqual(p.js("document.querySelector('#ask-first-run p').textContent"), "It reads what is in this project. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.")

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
                "Your question goes to Claude, which Anthropic runs.",
                "Passages from the folders you list go to Claude, which Anthropic runs, only when they contain words from your question.",
                "On a Mac, text in PNG and JPG pictures is read on this Mac and never sent out."])
            self.assertEqual(p.js(f"{card}.querySelector('.ask-first-link a').textContent"), "Open the Asking card in Settings")
            self.assertEqual(p.js("document.querySelector('#ask-status').textContent.trim()"), "Answering with Sonnet. Standing instructions on.")


if __name__ == "__main__":
    unittest.main()
