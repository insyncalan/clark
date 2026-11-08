"""The page's table of refusals (stores/report.js CHANGE_KNOWN and ALLOWED) kept equal to the words clark sends.

Run: python3 dev/run_tests.py test_change_known_parity
- a refusal the change route sends is a key the page knows, spelt the same (a Made decision refused as Pending);
- the page's own copy of a refusal (logic/board.js) is the server's, word for word;
- no key in the table is a leftover: each one has a live sender somewhere in src/;
- the status-level words (ALLOWED) hold the server's stale and not-allowed sentences.
"""
import re
import unittest
from pathlib import Path

from _paths import SRC

from clark import changes, page, server  # noqa: E402

PAGE_SRC = Path(page.PAGE).parent / "src"
REPORT = (PAGE_SRC / "stores" / "report.js").read_text(encoding="utf-8")
STR = r'"((?:[^"\\]|\\.)*)"'

# Sentences that are not keys of CHANGE_KNOWN on purpose, and the surface that shows each one as it is.
EXEMPT = {
    changes.PASTE_NONE: "People card, Paste from Excel (readPeople): shown raw",
    changes.PASTE_MANY: "People card, Paste from Excel (readPeople): shown raw",
    changes.PASTE_BAD_ROW: "People card, Paste from Excel (readPeople): shown raw",
    changes.ASK_OFF: "ask clark's Apply (AskChange.jsx): shown raw",
    changes.ASK_NOT_YET: "ask clark's Apply (AskChange.jsx): shown raw",
    changes.ASK_CHANGED: "ask clark's Apply (AskChange.jsx): shown raw",
}


def block(start, end):
    return REPORT[REPORT.index(start):REPORT.index(end)]


def change_keys():
    text = block("const CHANGE_KNOWN = {", "export const sayings")
    return [m.group(1).replace('\\"', '"') for m in re.finditer(r"^\s*" + STR + r":", text, re.M)]


def sender_text():
    """Every .py and page source under src/ except the table itself."""
    out = []
    root = Path(SRC)
    for p in list(root.rglob("*.py")) + [q for q in PAGE_SRC.rglob("*") if q.suffix in (".js", ".jsx")]:
        if "dist" in p.parts or p == PAGE_SRC / "stores" / "report.js":
            continue
        out.append(p.read_text(encoding="utf-8"))
    return "\n".join(out)


class Parity(unittest.TestCase):
    def test_a_made_decision_refused_as_pending_is_a_key_spelt_as_the_route_sends_it(self):
        self.assertIn(changes.MADE_STAYS, change_keys())

    def test_the_three_wordings_of_that_refusal_agree(self):
        board = (PAGE_SRC / "logic" / "board.js").read_text(encoding="utf-8")
        m = re.search(r"madeStays:\s*" + STR, board)
        self.assertTrue(m)
        self.assertEqual(m.group(1), changes.MADE_STAYS)

    def test_the_date_refusals_the_route_sends_are_keys(self):
        keys = change_keys()
        self.assertIn(changes.NOT_A_DATE, keys)
        self.assertIn(changes.DOC_NOT_A_DATE, keys)

    def test_the_stale_and_not_allowed_sentences_are_in_the_403_words(self):
        row = block("  403: {", "  404: {")
        for said in (server.STALE_PAGE, server.MESSAGES["not_allowed"], server.MESSAGES["stale"]):
            self.assertIn(said, row.replace("\\", "") + self.constants())

    def constants(self):
        return REPORT[:REPORT.index("const ALLOWED")]

    def test_the_400_and_404_words_hold_the_servers(self):
        for code, name in ((400, "bad_project_code"), (404, "project_not_found")):
            row = block("  %d: {" % code, "  %d: {" % {400: 403, 404: 500}[code])
            self.assertIn(server.MESSAGES[name], row + self.constants(), name)


class NoLeftovers(unittest.TestCase):
    def test_every_key_has_a_live_sender(self):
        senders = sender_text()
        # a key with a number in it is built from a limit (an f-string), so it cannot be found as written
        dead = [k for k in change_keys() if not re.search(r"\d", k) and k not in senders]
        self.assertEqual(dead, [], "keys no string in src/ sends")

    def test_the_exempt_sentences_are_not_keys_and_are_still_sent(self):
        keys = change_keys()
        for said in EXEMPT:
            self.assertNotIn(said, keys)
            self.assertTrue(said)


if __name__ == "__main__":
    unittest.main()
