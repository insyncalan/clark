"""Row 1371 part 2: the states under a source folder in a real browser at 1400 and 900 (Classic), and the Cards page unchanged.
The folder service is real; the index worker is a stand-in that says the state under test.

Run: python3 dev/run_tests.py test_ask_index_states_page_1371
Chrome is required. Every file is made in the test from made-up text.
"""
import unittest

from test_ask_index_page_1366 import Fixture, WIDTHS
from test_server import chrome, wait

from clark import ask_folders

D = "…"
STATES = [
    ("waiting", "Waiting to index"),
    ("paused", "Indexing paused. It carries on when clark is open"),
    ("updating", f"Updating{D} 1 file changed"),
    ("updating", f"Updating{D} 3 files changed"),
    ("failed", "Could not index this folder. Try again"),
    ("cleared", "Not indexed. Index again"),
]


class Stand:
    """What the worker says: one state and its line for every folder; again() is recorded."""
    def __init__(self, state, line):
        self.state, self.line, self.asked = state, line, 0

    def status_for(self, code, folders):
        return {str(f): {"state": self.state, "line": self.line} for f in folders}

    def again(self, code, folders):
        self.asked += 1
        return True

    def start(self, code, folders):
        return True


class Base(Fixture):
    def stand(self, state, line):
        self.ix2 = Stand(state, line)
        self.svc.indexer = self.ix2
        self.svc.change({"project": "ABC", "action": "add", "path": str(self.own)})


class States(Base):
    def test_each_state_reads_its_words_at_both_widths(self):
        for state, line in STATES:
            with self.subTest(line=line):
                self.stand(state, line)
                with chrome() as cdp:
                    js = self.show(cdp, "project")
                    want = line
                    self.until(js, "!!document.querySelector('#ask-folders .ask-folder-line')", "the line")
                    for w in WIDTHS:
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                        self.until(js, f"document.querySelector('#ask-folders .ask-folder-line').innerText === {want!r}", f"{line} at {w}")
                        self.assertEqual(js("document.documentElement.scrollWidth <= window.innerWidth"), True, w)
                        self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').getBoundingClientRect().height < 40"), True, w)

    def test_try_again_and_index_again_are_buttons_that_ask_for_a_new_read(self):
        for state, line, word in (("failed", "Could not index this folder. Try again", "Try again"), ("cleared", "Not indexed. Index again", "Index again")):
            with self.subTest(word=word):
                self.stand(state, line)
                self.svc.reindex_again = lambda code, me=self: (200, {"ok": True, "started": bool(me.ix2.again(code, []))})
                with chrome() as cdp:
                    js = self.show(cdp, "project")
                    self.until(js, "!!document.querySelector('#ask-folders [data-ask-index-again]')", "the link")
                    self.assertEqual(js("document.querySelector('#ask-folders [data-ask-index-again]').innerText"), word)
                    self.assertEqual(js("document.querySelector('#ask-folders .ask-folder-line').innerText"), line)
                    js("document.querySelector('#ask-folders [data-ask-index-again]').click()")
                    self.assertTrue(wait(lambda: self.ix2.asked == 1, 10))
                    self.assertEqual(self.ix2.asked, 1)

    def test_the_all_projects_card_says_indexed_for_n_of_n_projects(self):
        ask_folders.AskFolders.change_all(self.svc, {"scope": "all", "action": "add", "path": str(self.shared)})
        self.stand("done", "100% indexed")
        self.svc.projects_indexed = lambda folders: {f: {"done": 3, "all": 3, "line": "Indexed for 3 of 3 projects"} for f in folders}
        with chrome() as cdp:
            js = self.show(cdp, "all")
            for w in WIDTHS:
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.until(js, "document.querySelector('#ask-all-folders .ask-folder-line') && document.querySelector('#ask-all-folders .ask-folder-line').innerText === 'Indexed for 3 of 3 projects'", f"the count at {w}")


class CardsStates(Base):
    CLASSIC = False

    def test_cards_shows_no_state_line_in_any_state(self):
        for state, line in STATES:
            self.stand(state, line)
            with chrome() as cdp:
                js = self.show(cdp, "project")
                self.until(js, "document.querySelectorAll('.folder-now').length >= 1", "listed")
                self.assertEqual(js("document.querySelectorAll('.ask-folder-line, [data-ask-index-again]').length"), 0, line)


if __name__ == "__main__":
    unittest.main()
