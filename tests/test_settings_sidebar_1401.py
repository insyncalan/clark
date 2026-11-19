"""Row 1401 in the Classic Theme: the Settings sidebar chip text size, the open page's colours and marker, and the group spacing, as Chrome computes them on the
REAL Settings page (demo database, fictional data) at 1400 and 900 px, light and dark; the same elements under Cards as the control.
Values from the issue table (prototype at 1400): chip text 15 px; open page text 5B47D8 and fill ECE9FB (light) with a 3 px bar inset 7 px top and bottom;
group margin 12 px and 4 px between the pages of a group. At 900 the list is packed on purpose (item 1177), so the spacing is checked at 1400 only
and the 900 pass checks the text size, colours and marker.

Run: python3 dev/run_tests.py test_settings_sidebar_1401"""
import shutil
import tempfile
import time
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const tok = (v, p) => { const i = document.createElement('i'); i.style[p || 'color'] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p || 'color']; i.remove(); return r; };
  const chip = q('.set-chip:not([aria-current])'), cur = q('.set-chip[aria-current]'), grp = [...document.querySelectorAll('.set-group')].filter((e) => e.previousElementSibling)[0];
  const pl = q('.set-nav .plain'), lis = pl ? [...pl.children] : [];
  const gap = lis.length > 1 ? Math.round(lis[1].getBoundingClientRect().top - lis[0].getBoundingClientRect().bottom) : -1;
  const b = getComputedStyle(cur, '::before');
  return { chipSize: g(chip, 'fontSize'), curColor: g(cur, 'color'), curBg: g(cur, 'backgroundColor'), barW: b.width, barTop: b.top, barBottom: b.bottom,
    groupMargin: grp ? g(grp, 'marginTop') : 'none', gap: gap,
    fgLight: tok('#5B47D8'), bgLight: tok('#ECE9FB', 'backgroundColor'), fgDark: tok('var(--status-blue-text)'), bgDark: tok('var(--brand-blue-tint)', 'backgroundColor'),
    oldFg: tok('#4A37C2'), oldBg: tok('#ECE9FF', 'backgroundColor') }; })()"""


class RealSettings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def look(self, theme, width, scheme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{s.port}/#settings&p=TUL")}, sid)
            self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('.set-chip[aria-current]') && !!document.querySelector('.set-nav .plain')", sid)), 30),
                            "timed out waiting for the real Settings page")
            time.sleep(0.3)
            return cdp.js(PROBE, sid)

    def test_classic_sidebar(self):
        for scheme in ("light", "dark"):
            for width in (1400, 900):
                c = self.look(NAME, width, scheme)
                tag = f"classic {scheme} {width}"
                self.assertEqual(c["chipSize"], "15px", tag + ": chip text 15 px")
                self.assertEqual((c["barW"], c["barTop"], c["barBottom"]), ("3px", "7px", "7px"), tag + ": 3 px bar inset 7 px top and bottom")
                if scheme == "light":
                    self.assertEqual((c["curColor"], c["curBg"]), (c["fgLight"], c["bgLight"]), tag + ": open page text 5B47D8 on fill ECE9FB")
                else:
                    self.assertEqual((c["curColor"], c["curBg"]), (c["fgDark"], c["bgDark"]), tag + ": dark keeps its tokens")
                if width == 1400:
                    self.assertEqual(c["groupMargin"], "12px", tag + ": 12 px above a group")
                    self.assertEqual(c["gap"], 4, tag + ": 4 px between the pages of a group")

    def test_cards_unchanged(self):
        c = self.look(None, 1400, "light")
        # Measured: Cards' chip is 15px (brand --size-body: 15px in src/clark/brand/tokens.css). The ticket's "built 14px" is the prototype Theme's --size-body, which Cards does not load.
        self.assertEqual(c["chipSize"], "15px")
        self.assertEqual(c["curColor"], c["oldFg"])
        self.assertEqual(c["curBg"], c["oldBg"])
        self.assertEqual(c["barTop"], "4px")
        self.assertEqual(c["groupMargin"], "24px")
        self.assertEqual(c["gap"], 0)


if __name__ == "__main__":
    unittest.main()
