"""Row 1350: the ask box placeholder, the two slash hints and the quick bar's project order are Classic only; Cards keeps what main showed before.

Run: python3 dev/run_tests.py test_classic_gate_1350
Classic is the page with the <style id="theme"> layer (classicTheme() in components/Contents.jsx); the tests add that element to the running page for the
Classic half and leave it out for the Cards half. Logic runs in node (askSlash.js, askWords.js); the page parts are headless Chrome at 1400 and 900.
"""
import unittest

import test_palette as tp
from test_ask_slash import ROWS, SlashPanel, json, run_node
from test_palette import Base as PalBase
from test_server import chrome

CARDS_PLACEHOLDER = "Ask a question about this project"
CLASSIC_PLACEHOLDER = "Ask a question or give an instruction... (type / for shortcuts)"
CARDS_HINTS = {"summary": "Summarise this week", "overdue": "What is overdue"}
CLASSIC_HINTS = {"summary": "Summarise this week into a draft", "overdue": "What is overdue?"}
LAYER = "(function(){var s=document.createElement('style'); s.id='theme'; document.head.appendChild(s);})()"
HINTS = "JSON.stringify(Array.from(document.querySelectorAll('#ask-slash [role=option]')).map(function(o){return [o.getAttribute('data-name'), o.querySelector('span').textContent]}))"


def runs(kinds):
    return [k for i, k in enumerate(kinds) if i == 0 or k != kinds[i - 1]]


class Logic(unittest.TestCase):
    def hints(self, classic):
        return dict(run_node(f"AS.slashMatches('/', {classic}).map(c=>[c.name, c.hint])"))

    def test_cards_hints_are_the_old_words_and_the_default_is_cards(self):
        got = self.hints("false")
        self.assertEqual({k: got[k] for k in CARDS_HINTS}, CARDS_HINTS)
        self.assertEqual(dict(run_node("AS.slashMatches('/').map(c=>[c.name, c.hint])")), got, "no second argument means Cards")

    def test_classic_hints_are_the_new_words_and_only_those_two_differ(self):
        cards, classic = self.hints("false"), self.hints("true")
        self.assertEqual({k: classic[k] for k in CLASSIC_HINTS}, CLASSIC_HINTS)
        self.assertEqual({k: v for k, v in cards.items() if classic[k] != v}, CARDS_HINTS)
        self.assertEqual(list(cards), list(classic))

    def test_the_questions_a_command_sends_are_the_same_in_both(self):
        self.assertEqual(run_node("AS.slashMatches('/', true).map(c=>[c.ask, c.act])"), run_node("AS.slashMatches('/', false).map(c=>[c.ask, c.act])"))


class Panel(SlashPanel):
    def look(self, cdp, classic, width):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        if classic:
            p.js(LAYER)
        p.key("/", code="Slash", vk=191)
        p.until("!!document.querySelector('#ask-panel')", "the panel opened")
        p.until("document.querySelector('#ask-panel').getAnimations().length === 0", "the panel has risen")
        p.until("!document.querySelector('#ask-send').disabled", "ready")
        p.js("document.querySelector('#ask-box').focus()")
        return p

    def test_cards_keeps_the_old_placeholder_and_hints_at_both_widths(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.look(cdp, False, w)
                self.assertEqual(p.js("[document.querySelector('#ask-box').placeholder, document.querySelector('#ask-box').getAttribute('aria-label')]"), [CARDS_PLACEHOLDER] * 2, f"at {w} px")
                p.type("/")
                p.until("!!document.querySelector('#ask-slash')", "the menu opened")
                got = dict(json.loads(p.js(HINTS)))
                self.assertEqual({k: got[k] for k in CARDS_HINTS}, CARDS_HINTS, f"at {w} px")

    def test_classic_shows_the_new_placeholder_and_hints_at_both_widths(self):
        for w in (1400, 900):
            with chrome() as cdp:
                p = self.look(cdp, True, w)
                self.assertEqual(p.js("[document.querySelector('#ask-box').placeholder, document.querySelector('#ask-box').getAttribute('aria-label')]"), [CLASSIC_PLACEHOLDER] * 2, f"at {w} px")
                p.type("/")
                p.until("!!document.querySelector('#ask-slash')", "the menu opened")
                got = dict(json.loads(p.js(HINTS)))
                self.assertEqual({k: got[k] for k in CLASSIC_HINTS}, CLASSIC_HINTS, f"at {w} px")
                self.assertEqual(len(json.loads(p.js(ROWS))), 8)


class Order(PalBase):
    def setUp(self):
        tp.DATA["DEF"] = tp.project("DEF", "Pilot supplier programme")
        tp.LIST[1] = {"code": "DEF", "name": "Pilot supplier programme"}
        self.addCleanup(lambda: (tp.DATA.__setitem__("DEF", tp.project("DEF", "Second Programme")), tp.LIST.__setitem__(1, {"code": "DEF", "name": "Second Programme"})))
        super().setUp()

    def kinds(self, p, q):
        p.find(q)
        return runs([r[0] for r in p.rows(True)])

    def test_cards_lists_the_data_before_the_project_as_main_did_and_classic_the_project_first(self):
        with chrome() as cdp:
            for classic in (False, True):
                p = self.visit(cdp)
                if classic:
                    p.js(LAYER)
                for w in (1400, 900):
                    p.width(w)
                    p.show()
                    got = [k for k in self.kinds(p, "supplier") if k in ("Project", "Risk", "ask clark")]
                    self.assertEqual(got, ["Project", "Risk", "ask clark"] if classic else ["Risk", "Project", "ask clark"], f"classic={classic} at {w} px")
                    p.key("Escape", 0, "Escape", 27)
                    p.show()
                    got = self.kinds(p, "work")
                    self.assertEqual(got[:2], ["Command", "Page"] if classic else ["Page", "Command"], f"classic={classic} at {w} px: {got}")
                    p.key("Escape", 0, "Escape", 27)
                    p.show()
                    self.assertEqual(runs([r[0] for r in p.rows(True)]), ["Page", "Action", "Project", "Command"], f"classic={classic} at {w} px: empty bar")
                    p.key("Escape", 0, "Escape", 27)


if __name__ == "__main__":
    unittest.main()
