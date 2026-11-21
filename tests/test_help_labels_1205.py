"""Row 1205, the sentences that need no new word: Help is checked against the real page.

Run: python3 dev/run_tests.py test_help_labels_1205
Three sentences change and each is read from the Help file and then tested on the page at 1400 and 900 px (fictional demo data, real server):
the Legend sits at the right of the bar above the milestone rows, not under them; Accept all and Reject all set the choice on each change
and a change that starts on Reject stays on Reject under Accept all; the Appearance choices are
System, Light and Dark. Chrome is required: the page tests fail, never skip, without it.
"""
import json
import shutil
import tempfile
import unittest

from _paths import SRC

from clark import page
from test_import_box_keys import ImportBox as _Box, page_html as import_page_html
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

HELP = SRC / "clark" / "page" / "src" / "help" / "helpContent.json"
WIDTHS = (1400, 900)


def every_string(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from every_string(v)
    elif isinstance(node, list):
        for v in node:
            yield from every_string(v)


TEXT = "\n".join(every_string(json.loads(HELP.read_text(encoding="utf-8"))))


class HelpSaysIt(unittest.TestCase):
    def test_the_sentences_say_what_the_page_does_and_the_old_ones_are_gone(self):
        for new in ("**Legend**, at the right of the bar above the milestones, explains every mark",
                    "Under that bar, the list shows each milestone",
                    "**Accept all** sets every change to **Accept** except the ones that start on **Reject**, and **Reject all** sets every change to **Reject**.",
                    "How the Dashboard sections look, System, Light or Dark and the single-key slash commands."):
            self.assertEqual(TEXT.count(new), 1, new)
        for old in ("at the right under the milestones", "Under the Legend, the list", "set every change at once",
                    "How the Dashboard sections look, Light or Dark"):
            self.assertNotIn(old, TEXT, old)


def milestones_steps():
    entries = [e for e in every_dict(json.loads(HELP.read_text(encoding="utf-8"))) if e.get("t") == "Read the timeline and calendar"]
    assert len(entries) == 1, entries
    return entries[0]["s"]


def every_dict(node):
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from every_dict(v)
    elif isinstance(node, list):
        for v in node:
            yield from every_dict(v)


class LegendLinesStay(unittest.TestCase):
    def test_both_legend_sentences_are_in_the_milestones_entry_word_for_word(self):
        steps = milestones_steps()
        legend = "**Legend**, at the right of the bar above the milestones, explains every mark when you point at it or tab to it."
        under = "Under that bar, the list shows each milestone with its date, state and progress."
        self.assertEqual(steps.count(legend), 1, "the Legend line is one step, word for word")
        mine = [s for s in steps if s.startswith(under)]
        self.assertEqual(len(mine), 1, "the list line starts as it should")
        self.assertEqual(steps.index(legend) + 1, steps.index(mine[0]), "the list line follows the Legend line")


class OnThePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.projects = cls.store.read("projects")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self):
        s = Running(data_for=self.store.data_for, projects=lambda archived=False: self.projects, page_html=lambda: page.page_html(tempfile.mkdtemp()))
        self.addCleanup(s.close)
        return s.port

    def visit(self, cdp, width, hash_, ready):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.serve()}/{hash_}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(f"!!document.querySelector('{ready}')", sid)), f"{ready} drew")
        return sid

    def test_the_legend_is_at_the_right_of_the_bar_above_the_rows_with_the_hide_button(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, "#milestones&p=MOSS", ".msl-det")
                got = cdp.js("""(() => {
                  const l = document.querySelector('.mlg-b').getBoundingClientRect(), h = document.querySelector('.msl-det').getBoundingClientRect(),
                        r = document.querySelector('.msl-row').getBoundingClientRect();
                  return {right: l.left > h.left, above: l.bottom <= r.top + 1, sameBar: document.querySelector('.msl-det').parentElement.contains(document.querySelector('.mlg-b'))};
                })()""", sid)
                self.assertEqual(got, {"right": True, "above": True, "sameBar": True}, "the Legend is right of Hide milestone details, in its bar, above the first row")

    def test_appearance_offers_system_light_and_dark(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.visit(cdp, width, "#settings&p=MOSS", ".set-chip")
                cdp.js("[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === 'Appearance').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#personal [data-appearance] .seg button')", sid)), "Personal drew")
                self.assertEqual(cdp.js("[...document.querySelectorAll('#personal [data-appearance] .seg button')].map(b => b.textContent)", sid),
                                 ["System", "Light", "Dark"])


class AcceptAllRejectAll(_Box):
    """The real Import box on a bare page; one change starts on Reject (it clashes with a later change in clark)."""

    def rows(self):
        return self.js("[...document.querySelectorAll('.st-act')].map(g => g.querySelector('input:checked').value)")

    def test_accept_all_keeps_a_change_that_starts_on_reject_and_reject_all_sets_every_change_to_reject(self):
        its = [{"n": 1, "kind": "new", "table": "actions", "text": "Row 1", "default": True},
               {"n": 2, "kind": "changed", "table": "actions", "text": "Row 2", "default": True},
               {"n": 3, "kind": "changed", "table": "actions", "text": "Row 3", "default": False}]
        for width in WIDTHS:
            with self.subTest(width=width):
                self.cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, self.sid)
                self.to_plan(its)
                self.until("document.querySelectorAll('.st-act').length === 3", "the three changes drew")
                self.assertEqual(self.rows(), ["1", "1", "0"], "the clash starts on Reject")
                self.js("document.querySelector('[name=st3][value=\"1\"]').click()")
                self.until("document.querySelector('[name=st3][value=\"1\"]').checked", "the clash was set to Accept by hand")
                self.click("#import-reject-all")
                self.until("document.querySelector('#import-go').disabled", "Reject all took every change")
                self.assertEqual(self.rows(), ["0", "0", "0"])
                self.click("#import-accept-all")
                self.until("!document.querySelector('#import-go').disabled", "Accept all took the changes")
                self.assertEqual(self.rows(), ["1", "1", "0"], "Accept all leaves the one that starts on Reject on Reject")


for _n in [n for n in dir(_Box) if n.startswith("test_") and n not in vars(AcceptAllRejectAll)]:
    setattr(AcceptAllRejectAll, _n, None)       # only this class's own test runs, not the Import box tests it borrows the page from
del _Box


if __name__ == "__main__":
    unittest.main()
