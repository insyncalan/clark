"""Published file, Work items / Milestones / Use cases tabs: the small line above each title is the same plain project name,
and the Use cases tab shows each use case's headline in its row as the Dashboard row does.

Run: python3 dev/run_tests.py test_published_tabs_eyebrow
Headless Chrome (required). 1400 and 900 px, light and dark.
"""
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER, DemoStore
from clark import publish
from test_published_work_no_add import EMPTY_BRANDING, TODAY, VARIANTS, open_page
from test_server import chrome, wait
from test_work_filters import need_chrome

SETTLED = "document.getAnimations().length === 0"
EYEBROW = """(() => { const c = document.querySelector('%s .crumbs');
  if (!c) return null; const s = getComputedStyle(c);
  return [s.textTransform, s.letterSpacing, s.fontWeight, s.fontSize, s.fontFamily, s.color, c.textContent]; })()"""
HEADS = """(() => [...document.querySelectorAll('#usecases-file .ucp')].map(d => {
  const h = d.querySelector('summary .ucp-headline'); return [d.querySelector('.ucp-title').textContent, h ? h.textContent : null]; }))()"""
TABS = (("Work items", "#work"), ("Milestones", "#milestones"), ("Use cases", "#usecases-file"))


class PublishedTabs(unittest.TestCase):
    def setUp(self):
        need_chrome()

    def test_one_eyebrow_style_and_the_headline_on_the_use_cases_tab(self):
        demo = DemoStore()
        HEAD = "Matching is on track for the next close"
        with demo.store.step("dashboard", USER) as st:
            st.update("use_cases", demo.use_case, {"headline": HEAD})
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(demo.close)
        self.addCleanup(shutil.rmtree, folder, True)
        path = Path(publish.publish(demo.store, "ABC", folder, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = open_page(cdp, path.as_uri(), width, scheme)
                self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.tab')", sid)))
                seen = []
                for tab, sel in TABS:
                    cdp.js("[...document.querySelectorAll('.tab')].find(t => t.textContent.includes('%s')).click()" % tab, sid)
                    self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('%s .crumbs')" % sel, sid)), tab + " drew")
                    self.assertTrue(wait(lambda: cdp.js(SETTLED, sid)), "motion finished")
                    seen.append(cdp.js(EYEBROW % sel, sid))
                self.assertEqual(seen[0][0], "none", "plain, not capitals")
                self.assertEqual(seen[0], seen[1])
                self.assertEqual(seen[0], seen[2])
                heads = cdp.js(HEADS, sid)
                self.assertTrue(heads, "the tab lists use cases")
                self.assertIn(["Invoice matching", HEAD], heads, "the headline is in the use case's row")


if __name__ == "__main__":
    unittest.main()
