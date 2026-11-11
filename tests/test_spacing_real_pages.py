"""Spacing (item 1025): the real Work items page and the real Help page follow the density. Run: python3 dev/run_tests.py test_spacing_real_pages

Not synthetic elements: the page is drawn, the real Work items table and the real Help screen are on it, and the spacing tokens their own
rows, headings, tabs and sections use are read from the computed style in Compact and in Comfortable, at 1400 and 900 px. Comfortable must
be looser for each, and the type size must not move. Chrome is required: the browser tests fail, never skip, without it.
"""
import unittest

from test_help_panel import full_help_from_menu
from test_publish_dialog import Base
from test_server import chrome

WORK = """(() => { try { const cs = (e) => getComputedStyle(e); const td = document.querySelector('#work table.items tbody td'); const th = document.querySelector('#work table.items th');
  if (!td || !th) return 'no real table on the page'; return {row: parseFloat(cs(td).paddingTop), head: parseFloat(cs(th).paddingTop), size: cs(td).fontSize}; } catch (e) { return String(e); } })()"""
HELP = """(() => { try { const cs = (e) => getComputedStyle(e); const sec = document.querySelector('#help .hp-sec'); const tabs = document.querySelector('#help .hp-tabs');
  if (!sec || !tabs) return 'no real Help sections on the page'; return {sec: parseFloat(cs(sec).marginTop), tabs: parseFloat(cs(tabs).marginBottom), size: cs(sec).fontSize}; } catch (e) { return String(e); } })()"""


class RealPages(Base):
    def read(self, probe, ready):
        got = {}
        for word in ("compact", "comfortable"):
            self.p.js(f"document.documentElement.dataset.density = {word!r}")
            self.p.until(ready, "the page is there")
            got[word] = self.p.js(probe)
            self.assertIsInstance(got[word], dict, got[word])
        return got

    def test_the_real_work_items_page_is_looser_in_comfortable_at_1400_and_900(self):
        with chrome() as cdp:
            self.p = self.page(cdp, "#work&p=PUB")
            self.p.until("!!document.querySelector('#work table.items tbody td')", "Work items drew its table")
            for w in (1400, 900):
                with self.subTest(width=w):
                    self.p.width(w)
                    got = self.read(WORK, "!!document.querySelector('#work table.items tbody td')")
                    c, f = got["compact"], got["comfortable"]
                    self.assertGreater(f["row"], c["row"], "table rows take more room")
                    self.assertGreater(f["head"], c["head"], "column headings take more room")
                    self.assertEqual(f["size"], c["size"], "type size does not change with the density")

    def test_the_real_help_page_is_looser_in_comfortable_at_1400_and_900(self):
        with chrome() as cdp:
            self.p = self.page(cdp)
            full_help_from_menu(self.p)
            for w in (1400, 900):
                with self.subTest(width=w):
                    self.p.width(w)
                    got = self.read(HELP, "!!document.querySelector('#help .hp-sec')")
                    c, f = got["compact"], got["comfortable"]
                    self.assertGreater(f["sec"], c["sec"], "Help sections sit further apart")
                    self.assertGreater(f["tabs"], c["tabs"], "Help tabs sit further from the text")
                    self.assertEqual(f["size"], c["size"], "type size does not change with the density")


if __name__ == "__main__":
    unittest.main()
