"""#72 slice 1: the page's AI menu table (src/clark/page/src/logic/aiMenu.js) against the server's menu, and its plain words.

Run: python3 dev/run_tests.py test_ai_menu_page
The page's copy only decides what to draw; src/clark/ai_menu.py (the server's menu()) is the authority. The parity test bundles
aiMenu.js alone with the pinned esbuild, runs it in headless Chrome and compares menu(place) with ai_menu.menu(place) for all five
places. The server module is read as it is on this tree (never a copy), so if it breaks or its menu changes, this test fails.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _clean_html import wait_for
from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import esbuild  # noqa: E402
from test_server import chrome  # noqa: E402

from clark import ai_menu, draft_email  # noqa: E402     # the real server module, never a copy: if it breaks, this test must fail, not pass on a frozen file

LOGIC = ROOT / "src" / "clark" / "page" / "src" / "logic"
PLACES = ["current", "notes", "plain", "email", "client_message"]
# Words a person should never meet in a line of the menu or the card.
JARGON = re.compile(r"\b(json|api|http|html|markdown|token|route|provider|payload|exception|error|traceback|undefined|null|nan|"
                    r"timeout|stack|endpoint|prompt|llm|regex)\b|!", re.I)
# A date written out or in numbers, and a name (a capital in the middle of a line).
DATE = re.compile(r"\b\d{1,4}[-/.]\d{1,2}[-/.]\d{1,4}\b|\b\d{1,2}(st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|"
                  r"\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b|\b20\d\d\b", re.I)
NAME = re.compile(r"(?<=[a-z,] )(?!(?:Claude|Settings)\b)[A-Z][a-z]+")      # a capital in the middle of a line, apart from the two words the card uses


class Page:
    """aiMenu.js bundled alone as `AM`, in a Chrome tab."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        out = tmp / "am.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AM", "--target=es2020", "--tsconfig-raw={}",
                            str(LOGIC / "aiMenu.js"), f"--outfile={out}"], cwd=LOGIC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        (tmp / "page.html").write_text("<!doctype html><meta charset=utf-8><body><script src=am.js></script></body>", encoding="utf-8")
        self.chrome = chrome()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof AM === 'object'", self.sid) is True, 60), "the script did not load"
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        return self.cdp.js(expr, self.sid)


def strings(value):
    """Every string in a JSON-like value."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for v in value.values():
            yield from strings(v)
    elif isinstance(value, (list, tuple)):
        for v in value:
            yield from strings(v)


class Menu(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = Page().__enter__()
        cls.menus = {p: cls.page.ev(f"AM.menu({json.dumps(p)})") for p in PLACES}
        cls.words = cls.page.ev("AM.WORDS")
        cls.options = cls.page.ev("AM.OPTIONS")

    @classmethod
    def tearDownClass(cls):
        cls.page.__exit__(None, None, None)

    def test_same_as_the_servers_menu_for_all_five_places(self):
        for place in PLACES:
            with self.subTest(place=place):
                self.assertEqual(self.menus[place], ai_menu.menu(place))

    def test_same_names_lines_and_places_as_the_server(self):
        self.assertEqual({k: list(v) for k, v in self.options.items()}, {k: [v[0], v[1]] for k, v in ai_menu.OPTIONS.items()})
        self.assertEqual(self.page.ev("AM.PLACES"), ai_menu.PLACES)
        self.assertEqual(self.page.ev("AM.MAKE_INTO"), ai_menu.MAKE_INTO)

    def test_an_unknown_place_is_refused_by_both(self):
        self.assertIsNone(self.page.ev("AM.menu('nowhere')"))
        with self.assertRaises(Exception):
            ai_menu.menu("nowhere")

    def test_shape_without_the_server(self):
        for p in PLACES:
            m = self.menus[p]
            self.assertEqual(m["place"], p)
            self.assertEqual(m["ask"]["id"], "custom")
            rich = p in ("current", "notes")
            self.assertEqual(bool(m["make_into"]), rich, p)
            self.assertEqual(m["format_notes"] is not None, rich, p)
            ids = [i["id"] for g in m["groups"] for i in g["items"]]
            self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual([i["id"] for g in self.menus["email"]["groups"] for i in g["items"]],
                         ["rewrite", "shorter", "longer", "formal", "warmer"])
        self.assertIn("checklist", [i["id"] for g in self.menus["notes"]["groups"] for i in g["items"]])
        self.assertNotIn("checklist", [i["id"] for g in self.menus["current"]["groups"] for i in g["items"]])
        self.assertIsNone(self.page.ev("AM.menu('nowhere')"))
        self.assertIsNone(self.page.ev("AM.menu('__proto__')"))

    def test_every_menu_option_has_a_name_and_a_line(self):
        for p in PLACES:
            for g in self.menus[p]["groups"]:
                for i in g["items"]:
                    self.assertTrue(i["name"] and i["line"], i)

    def test_parity_fails_if_a_place_is_missing_from_the_page_table(self):
        self.assertEqual(sorted(self.page.ev("Object.keys(AM.PLACES)")), sorted(PLACES))
        self.assertEqual(sorted(ai_menu.PLACES), sorted(PLACES))
        self.assertEqual(self.page.ev("AM.GROUPS"), {k: [[a, list(b)] for a, b in v] for k, v in ai_menu.GROUPS.items()})
        self.assertEqual(self.page.ev("AM.WORDS.notSignedIn"), "Connect Claude in Settings to use this.")

    def test_plain_words(self):
        everything = list(strings(self.menus)) + list(strings(self.words)) + list(strings(self.options)) \
            + list(strings(self.page.ev("AM.MAKE_INTO")))
        self.assertGreater(len(everything), 40)
        for line in everything:
            with self.subTest(line=line):
                self.assertFalse(re.match(r"\s*clark\b", line, re.I), "starts with the product name")
                self.assertIsNone(JARGON.search(line), "jargon")
                self.assertIsNone(DATE.search(line), "a date")
                self.assertIsNone(NAME.search(line), "a person's name")

    def test_the_word_check_catches_what_it_should(self):
        for bad in ("Clark made this", "The JSON came back", "Wait for 12-03-2026", "Sent by Priya", "Done on Monday 5 March"):
            self.assertTrue(re.match(r"\s*clark\b", bad, re.I) or JARGON.search(bad) or DATE.search(bad) or NAME.search(bad), bad)
        card = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "AiCard.jsx").read_text(encoding="utf-8")
        for line in re.findall(r'aria-label=\{`([^`$]*)', card):             # the card's own fixed words
            self.assertIsNone(JARGON.search(line), line)

    def test_the_card_names_the_shown_option(self):
        self.assertEqual(self.page.ev("AM.optionName('shorter')"), "Shorter")
        self.assertEqual(self.page.ev("AM.optionName('custom', '  make   it   kinder ')"), "make it kinder")
        self.assertEqual(self.page.ev("AM.optionName('custom', '')"), "Ask…")
        self.assertLessEqual(len(self.page.ev("AM.optionName('custom', 'x '.repeat(100))")), 60)


class EmailPlace(unittest.TestCase):
    """The email place is offered only when the Draft email route says the address is on one of the user's own domains."""

    @classmethod
    def setUpClass(cls):
        cls.page = Page().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.page.__exit__(None, None, None)

    def test_offered_only_when_the_address_is_known_to_be_inside(self):
        self.assertTrue(self.page.ev("AM.placeOffered('email', false)"))
        self.assertFalse(self.page.ev("AM.placeOffered('email', true)"))

    def test_not_knowing_counts_as_outside(self):
        for unknown in ("undefined", "null", "'no'", "0", "''"):
            self.assertFalse(self.page.ev(f"AM.placeOffered('email', {unknown})"), unknown)
        self.assertIsNone(self.page.ev("AM.menuFor('email')"))

    def test_every_other_place_is_offered_whatever_the_address(self):
        for place in PLACES:
            if place != "email":
                for outside in ("true", "false", "undefined"):
                    self.assertTrue(self.page.ev(f"AM.placeOffered('{place}', {outside})"), (place, outside))
                    self.assertEqual(self.page.ev(f"AM.menuFor('{place}', {outside})"), ai_menu.menu(place))

    def test_the_menu_is_the_servers_menu_when_offered_and_none_when_not(self):
        self.assertEqual(self.page.ev("AM.menuFor('email', false)"), ai_menu.menu("email"))
        self.assertIsNone(self.page.ev("AM.menuFor('email', true)"))
        self.assertIsNone(self.page.ev("AM.menuFor('nowhere', false)"))

    def test_the_page_and_the_server_agree_for_every_case(self):
        own = ["example.test"]
        for address in ("sam@example.test", "dana@partner.test", "", "sam@mail.example.test"):
            outside = draft_email.is_outside(address, own)
            for place in PLACES:
                self.assertEqual(self.page.ev(f"AM.placeOffered({json.dumps(place)}, {json.dumps(outside)})"),
                                 ai_menu.place_offered(place, address, own), (place, address))


if __name__ == "__main__":
    unittest.main()
