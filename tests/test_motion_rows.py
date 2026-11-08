"""Row 938-5 / 970 (motion): rows added to or removed from the Work items list fade. Run: python3 dev/run_tests.py test_motion_rows

An added row rises 4 px and fades in (m-rise, --dur-state, --ease-enter); a deleted row stays drawn where it was, inert and aria-hidden with no id,
and fades out (m-out, --dur-instant, --ease-exit), then leaves. The first draw, a filter, a sort and Group by never animate. Under reduced
motion nothing animates and the row is gone at once. Edit build only: the rules are in edit.css, not in the published page.
"""
import json
import unittest
from _editor_checks import for_url

from _paths import ROOT
import _testpage as testpage

from _real_server import real_server
from test_server import chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

EDIT = (ROOT / "src/clark/page/src/edit/edit.css").read_text(encoding="utf-8")
CSS = (ROOT / "src/clark/page/shell.css").read_text(encoding="utf-8")
PUBLISHED = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8") if (ROOT / "src/clark/page/page-view.html").exists() else ""
IDS = "[...document.querySelectorAll('#work tbody tr[data-id]')].map(r => r.dataset.id)"
# Drop the first row from the data (a delete), or put it back (an add); the page reads its data this way after a change.
DROP = """(() => { const d = window.clarkPage; let gone = null;
  d.changeData(x => { const o = {...x}; for (const k of ['actions', 'raid', 'decisions']) { if (!gone && o[k] && o[k].length) { gone = o[k][0]; window.__gone = [k, gone]; o[k] = o[k].slice(1); } } return o; });
  return gone.id; })()"""
BACK = """(() => { const [k, r] = window.__gone; window.clarkPage.changeData(x => ({...x, [k]: [r, ...x[k]]})); return r.id; })()"""
# What the first row (by id) is doing: animation name, leaving flags.
LEFT = """(() => { const t = document.querySelector('#work tbody tr.leaving'); return t ? JSON.stringify({name: getComputedStyle(t).animationName, dur: getComputedStyle(t).animationDuration,
  id: t.hasAttribute('data-id'), role: t.getAttribute('role'), hidden: t.getAttribute('aria-hidden'), inert: t.inert}) : null; })()"""
ENTER = """(() => { const t = document.querySelector('#work tbody tr.entering'); return t ? JSON.stringify({name: getComputedStyle(t).animationName, dur: getComputedStyle(t).animationDuration}) : null; })()"""
QUIET = "document.getAnimations().length === 0"


class MotionRows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.code = next(iter(cls.ids))

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        import shutil
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def load(self, cdp, width, scheme, motion, hash_=None):
        projects = self.store.read("projects")
        s = real_server(self.store.path, self.store.data_for, who="Demo User", projects=lambda archived=False: projects,
                        page_html=lambda: testpage.html())
        self.addCleanup(s.close)
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme},
                                                              {"name": "prefers-reduced-motion", "value": motion}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/{hash_ or '#work&p=' + self.code + '&f=mode:all'}")}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) > 2))
        self.assertTrue(wait(lambda: cdp.js(QUIET, sid), 15))
        return sid

    def test_a_deleted_row_fades_in_place_then_leaves_and_an_added_row_rises(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                    sid = self.load(cdp, width, scheme, "no-preference")
                    self.assertIsNone(cdp.js(ENTER, sid), "the first draw animates nothing")
                    before = cdp.js(IDS, sid)
                    gone = cdp.js(DROP, sid)
                    got = json.loads(cdp.js(LEFT, sid))
                    self.assertEqual(got, {"name": "m-out", "dur": "0.12s", "id": False, "role": "presentation", "hidden": "true", "inert": True})
                    self.assertNotIn(gone, cdp.js(IDS, sid), "the fading copy carries no id")
                    self.assertTrue(wait(lambda: cdp.js(QUIET + " && !document.querySelector('#work tr.leaving')", sid), 15), "gone after the fade")
                    self.assertEqual(cdp.js(IDS, sid), [i for i in before if i != gone])
                    cdp.js(BACK, sid)
                    got = json.loads(cdp.js(ENTER, sid))
                    self.assertEqual(got, {"name": "m-rise", "dur": "0.22s"})
                    self.assertTrue(wait(lambda: cdp.js(QUIET, sid), 15))
                    self.assertEqual(sorted(cdp.js(IDS, sid)), sorted(before))

    def test_a_filter_or_a_group_change_animates_no_row(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            n = cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid)
            cdp.js(f"location.hash = '#work&p={self.code}&f=mode:open'", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work tbody tr[data-id]').length", sid) < n), "the filter changed the rows")
            self.assertIsNone(cdp.js(ENTER, sid))
            self.assertIsNone(cdp.js(LEFT, sid))
            self.assertEqual(cdp.js("document.getAnimations().filter(a => a.effect.target.closest('tbody tr')).length", sid), 0, "no row animates")

    def test_changing_the_view_to_one_flat_list_animates_no_row(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            self.assertTrue(cdp.js("!!document.querySelector('#work tr.grp')", sid), "grouped to begin with")
            cdp.js("document.querySelector('#viewMenu').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('.ddmenu [data-kind=\"group:nothing\"]')", sid)))
            cdp.js("document.querySelector('.ddmenu [data-kind=\"group:nothing\"]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!document.querySelector('#work tr.grp')", sid)), "now one flat list")
            self.assertIsNone(cdp.js(ENTER, sid))
            self.assertIsNone(cdp.js(LEFT, sid))
            self.assertEqual(cdp.js("document.getAnimations().filter(a => a.effect.target.closest('tbody tr')).length", sid), 0)

    def test_a_re_sort_by_an_edit_animates_no_row(self):
        # An edit that moves a row to another place (its due date) is a re-sort, not an add or a delete: nothing fades.
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "no-preference")
            before = cdp.js(IDS, sid)
            cdp.js("""window.clarkPage.changeData(x => { const o = {...x}; for (const k of ['actions', 'raid', 'decisions']) { if (o[k] && o[k].length) {
              o[k] = o[k].map((r, i) => i === 0 ? {...r, due_date: '2099-12-31', needed_by: '2099-12-31', date: '2099-12-31'} : r); break; } } return o; })""", sid)
            self.assertTrue(wait(lambda: cdp.js(IDS, sid) != before), "the rows were re-sorted")
            self.assertEqual(sorted(cdp.js(IDS, sid)), sorted(before))
            self.assertIsNone(cdp.js(ENTER, sid))
            self.assertIsNone(cdp.js(LEFT, sid))
            self.assertEqual(cdp.js("document.getAnimations().filter(a => a.effect.target.closest('tbody tr')).length", sid), 0)

    def test_under_reduced_motion_no_row_animates_and_a_deleted_row_is_gone_at_once(self):
        with chrome() as cdp:
            sid = self.load(cdp, 1400, "light", "reduce")
            before = cdp.js(IDS, sid)
            gone = cdp.js(DROP, sid)
            self.assertIsNone(cdp.js(LEFT, sid))
            self.assertEqual(cdp.js(IDS, sid), [i for i in before if i != gone])
            cdp.js(BACK, sid)
            self.assertIsNone(cdp.js(ENTER, sid))
            self.assertTrue(cdp.js(QUIET, sid))

    def test_the_rules_are_edit_only_and_use_existing_tokens(self):
        i = EDIT.index("row 970:")
        block = EDIT[i:i + 900]
        self.assertIn("prefers-reduced-motion: no-preference", block)
        self.assertIn('[data-motion="reduce"]) table.items tr.entering { animation: m-rise var(--dur-state) var(--ease-enter) 1; }', block)
        self.assertIn('[data-motion="reduce"]) table.items tr.leaving { pointer-events: none; animation: m-out var(--dur-instant) var(--ease-exit) forwards; }', block)
        for text in (CSS, PUBLISHED):
            self.assertNotIn("tr.entering", text)
            self.assertNotIn("tr.leaving", text)


if __name__ == "__main__":
    unittest.main()
