"""#1292 slice 2 (the first-run card of ask clark): three plain lines in an empty chat, the old "A question sends" line stays gone.

Run: python3 dev/run_tests.py test_ask_first_run_1292
Headless Chrome through the shared harness, with the same stub for the server's `ask` as test_ask_panel.
"""
import re
import time
import unittest

from _paths import ROOT
from test_ask_panel import NEVER, Panel
from test_server import chrome

CSS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "edit.css").read_text(encoding="utf-8")
JSX = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AskPanel.jsx").read_text(encoding="utf-8")
WORDS = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "askWords.js").read_text(encoding="utf-8")
CARD = "document.querySelector('#ask-first-run')"
LINE = "document.querySelectorAll('#ask-first-run p')"


class FirstRun(Panel):
    def test_an_empty_chat_shows_the_card_with_three_lines(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.assertEqual(p.js(f"{CARD}.getAttribute('aria-label')"), "About ask clark")
            self.assertEqual(p.js(f"{LINE}.length"), 3)
            self.assertEqual(p.js(f"{LINE}[0].textContent.trim()"), "It reads what is in this project. Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.")
            self.assertEqual(p.js(f"{LINE}[1].textContent.trim()"), "It can suggest changes. Nothing is saved until you press Apply, and every change can be undone.")
            self.assertEqual(p.js(f"{LINE}[2].textContent.trim()"), "Your question goes to Claude, which Anthropic runs.")
            self.assertEqual(p.js("document.querySelector('#ask-panel').textContent.indexOf('A question sends')"), -1, "rule 9: the old line stays gone")
            self.assertEqual(p.js("document.querySelector('#ask-panel').textContent.indexOf('Show details')"), -1)

    def test_the_card_goes_when_a_question_is_asked_and_comes_back_with_a_new_chat(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            self.ask(p, "When is go-live?")
            p.until("document.querySelectorAll('.ask-turn').length === 2", "answered")
            self.assertEqual(p.js(CARD), None)
            p.js("document.querySelector('#ask-new').click()")
            p.until(f"!!{CARD}", "a new chat is empty again")

    def test_the_card_is_not_shown_while_history_is_open(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            p.js("document.querySelector('#ask-history').click()")
            p.until("!!document.querySelector('#ask-hist')", "history open")
            self.assertEqual(p.js(CARD), None)

    def test_the_card_is_not_shown_while_checking(self):
        self.stub.status_hold.clear()
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("document.querySelector('#ask-status').textContent !== ''", "checking")
            self.assertEqual(p.js(CARD), None, "nothing is said about where a question goes before the server has answered")
            self.stub.status_hold.set()
            p.until(f"!!{CARD}", "the card once the server has answered")

    def test_the_card_is_not_shown_when_signed_out(self):
        self.stub.connected = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-signed-out')", "signed out")
            self.assertEqual(p.js(CARD), None)

    def test_the_card_is_not_shown_when_the_status_check_fails(self):
        """A check that failed says nothing about where a question goes, so the card (which says it) stays away."""
        def failed(*_):
            self.stub.calls.append(("status", None))     # the replaced method no longer records the ask, so the test does
            return 200, {"ok": False}
        self.stub.status = failed
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            deadline = time.time() + 10
            while self.stub.count("status") < 1 and time.time() < deadline:
                time.sleep(0.1)
            time.sleep(0.8)
            self.assertEqual(self.stub.count("status"), 1, "the check was asked")
            self.assertEqual(p.js(CARD), None)

    def test_with_asking_off_the_card_still_reads(self):
        self.stub.enabled = False
        with chrome() as cdp:
            p = self.opened(cdp, ready=False)
            p.until("!!document.querySelector('#ask-off')", "off")
            self.assertEqual(p.js(f"{LINE}.length"), 3)

    def test_the_provider_in_use_is_named(self):
        self.stub.provider = "ChatGPT"
        with chrome() as cdp:
            p = self.opened(cdp)
            text = p.js(f"{CARD}.textContent")
            self.assertIn("Your question goes to ChatGPT, which OpenAI runs.", text)
            self.assertNotIn("Anthropic", text)
            self.assertNotIn("Claude", text)

    def test_the_link_opens_the_asking_card_in_settings_and_closes_the_panel(self):
        with chrome() as cdp:
            p = self.opened(cdp)
            link = "document.querySelector('#ask-first-run a[data-ask-first-settings]')"
            self.assertEqual(p.js(f"{link}.textContent"), "Open the Asking card in Settings")
            p.js(f"{link}.click()")
            p.until("document.querySelector('#ask-panel') === null && location.hash.indexOf('settings') === 1", "went to Settings")

    def test_the_card_fits_at_1400_and_900_px_in_light_and_dark(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                for theme in ("light", "dark"):
                    p.js(f"document.documentElement.dataset.theme = '{theme}'")
                    p.key("/", code="Slash", vk=191)
                    p.until("!!document.querySelector('#ask-panel')", f"opened at {width} {theme}")
                    p.until("!document.querySelector('#ask-send').disabled", "ready")
                    p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "risen")
                    p.until(f"!!{CARD}", "the card")
                    inside = f"(function(){{var c={CARD}.getBoundingClientRect(),a=document.querySelector('#ask-panel').getBoundingClientRect();return c.left>=a.left&&c.right<=a.right&&{CARD}.scrollWidth<={CARD}.clientWidth+1}})()"
                    self.assertTrue(p.js(inside), f"inside the panel at {width} {theme}")
                    self.assertTrue(p.js("document.documentElement.scrollWidth <= document.documentElement.clientWidth"), "no sideways scroll")
                    p.key("Escape", code="Escape", vk=27)
                    p.until("document.querySelector('#ask-panel') === null", "closed")


class Words(unittest.TestCase):
    def test_the_first_run_sentences_are_plain_and_complete(self):
        said = dict(re.findall(r'export const (FIRST_RUN_[A-Z_]+) = "((?:[^"\\]|\\.)*)"', WORDS))
        self.assertEqual(sorted(said), ["FIRST_RUN_CHANGES", "FIRST_RUN_LABEL", "FIRST_RUN_LINK", "FIRST_RUN_READS", "FIRST_RUN_SENT"])
        for name, text in said.items():
            self.assertIsNone(NEVER.search(text), f"{name}: {text}")
            self.assertFalse(text.lower().startswith("clark"), name)
            if name not in ("FIRST_RUN_LABEL", "FIRST_RUN_LINK"):
                self.assertRegex(text, r"\.$", name)
        self.assertIn("Mail, Teams, calendars and SharePoint are used only if you turn that connector on in Settings.", said["FIRST_RUN_READS"])
        self.assertNotIn("never reads", said["FIRST_RUN_READS"])
        self.assertIn("Nothing is saved until you press Apply", said["FIRST_RUN_CHANGES"])
        self.assertIn("Claude, which Anthropic runs", said["FIRST_RUN_SENT"], "written for Claude; named() swaps the provider")


class Sweep(unittest.TestCase):
    """Killers for the survivors of the diff-only sweep of the added lines (JS and CSS)."""

    def rule(self, selector):
        m = re.search(r"^" + re.escape(selector) + r" \{ ([^}]*)\}", CSS, re.M)
        self.assertIsNotNone(m, selector + " is one rule with the house spacing")
        return m.group(1)

    def test_the_card_css_keeps_it_inside_the_panel_and_the_link_a_target(self):
        card = self.rule(".ask-first-run")
        for part in ("flex: none", "overflow-wrap: anywhere", "border-bottom: 1px solid var(--grey-200)", "color: var(--text-muted)"):
            self.assertIn(part, card)
        self.assertIn("margin: 0 0 6px", self.rule(".ask-first-run p"))
        link = self.rule(".ask-first-link a")
        for part in ("min-height: 24px", "display: inline-flex", "text-decoration: underline", "color: var(--link, var(--brand-blue))"):
            self.assertIn(part, link)

    def test_the_off_line_link_rule_is_untouched_by_the_card(self):
        self.assertEqual(self.rule(".ask-off a"), "display: inline-flex; align-items: center; min-height: 24px; color: inherit; font-weight: var(--weight-medium); text-decoration: underline; ")

    def test_the_card_shows_only_for_ready_or_off_and_sits_above_the_log(self):
        m = re.search(r"\{(!showHist && !list\.length && \(state === \"ready\" \|\| state === \"off\"\)) \? \(\s*<section class=\"ask-first-run\"", JSX)
        self.assertIsNotNone(m, "the card's guard names history, an empty list, and exactly the two states")
        self.assertLess(JSX.index('id="ask-first-run"'), JSX.index('id="ask-log"'))
        self.assertIn('href="#settings&s=claude" data-ask-first-settings onClick={toSettings}', JSX)


if __name__ == "__main__":
    unittest.main()
