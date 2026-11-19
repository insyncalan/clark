"""Row 1316c: the Use cases Next steps count in the Classic look, as Chrome computes it, at 1400 and 900 px, light and dark; the same elements under Cards.

Run: python3 dev/run_tests.py test_theme_classic_usecases_next
Sizes are by eye from the issue table (the prototype files are not on this box).
Rebrand only (CSS in the Classic Theme folder): each item of the issue is one computed fact under Classic and the installed value of the same
element under Cards, which a Theme layer must not touch. The real page over a real server and the demo data (fictional), as test_use_cases_page_e2e.
"""
import re
import shutil
import unittest
from unittest import mock

from _real_server import real_server
from clark import __main__ as launcher, page, server as sv, use_cases_read
from clark.store import open_store
from test_inline_edits import EMPTY_BRANDING, need_chrome, tearDownModule  # noqa: F401
from test_server import chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
LIST = "#usecases&p=TUL"

# the facts of each item, read in the page: [what, selector, property] (a pseudo-element is "selector::before")
PROBE = """(() => {
  const g = (sel, prop, pseudo) => { const e = document.querySelector(sel); return e ? getComputedStyle(e, pseudo || null)[prop] : null; };
  return {
    text: [...document.querySelectorAll('#usecases .ucsteps')].map((e) => e.textContent.trim()).filter(Boolean),
    font: [g('#usecases .ucsteps .ucn-b', 'fontSize'), g('#usecases .ucsteps', 'fontSize')],
    box: ['minHeight', 'paddingLeft', 'paddingRight', 'marginRight'].map((k) => g('#usecases .ucsteps .ucn-b', k)),
    type: ['fontWeight', 'lineHeight'].map((k) => [g('#usecases .ucsteps .ucn-b', k), g('#usecases .ucsteps', k)]),
    color: [g('#usecases .ucsteps .ucn-b', 'color'), g('#usecases .ucsteps', 'color')],
    badge: [g('#usecases .ucsteps .ucn-b', 'backgroundColor'), g('#usecases .ucsteps .ucn-b', 'borderTopLeftRadius'), g('#usecases .ucsteps .ucn-b', 'minWidth')],
    scroll: document.documentElement.scrollWidth,
  };
})()"""


def contrast(fg, bg):
    def lum(css):
        v = [int(x) for x in re.findall(r"\d+", css)[:3]]
        a = [x / 255 / 12.92 if x / 255 <= 0.03928 else ((x / 255 + 0.055) / 1.055) ** 2.4 for x in v]
        return 0.2126 * a[0] + 0.7152 * a[1] + 0.0722 * a[2]
    hi, lo = sorted((lum(fg), lum(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


READY_CLASSIC = "document.querySelectorAll('#usecases tr.ucr[data-uc]').length > 0 && !!document.querySelector('#usecases .meta2 .cm')"      # row 1325: Classic draws the table
READY_CARDS = "document.querySelectorAll('#usecases .ucl-row[data-uc]').length > 0 && !!document.querySelector('#usecases .ucl-st .cchip')"      # Cards: the list as it was


class Computed(unittest.TestCase):
    def setUp(self):
        need_chrome()
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.path = self.folder / "clark.db"
        self.theme = None
        self.s = real_server(self.path, self.read, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                             page_html=lambda: page.page_html(EMPTY_BRANDING, theme=self.theme))
        self.s.httpd.use_cases = use_cases_read.make_read(self.read, lambda code: set(), launcher.use_case_history(mock.Mock(path=self.path)))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def read(self, code, archived="hide"):
        st = open_store(self.path, onedrive_roots=[])
        try:
            return st.data_for(code, archived=archived)
        finally:
            st.close()

    def facts(self, cdp, width, scheme, theme):
        self.theme = theme
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/{LIST}"}, sid)
        self.assertTrue(wait(lambda: cdp.js(READY_CLASSIC if theme is not None else READY_CARDS, sid), 20), "the list drew")
        self.assertEqual(cdp.js("!!document.getElementById('theme')", sid), theme is not None)
        self.assertEqual(cdp.js("window.innerWidth", sid), width)
        return cdp.js(PROBE, sid)

    def both(self, width, scheme):
        with chrome() as cdp:
            classic = self.facts(cdp, width, scheme, NAME)
        with chrome() as cdp:
            cards = self.facts(cdp, width, scheme, None)
        return classic, cards

    def test_each_item_under_classic_and_the_same_element_unchanged_under_cards(self):
        for width in (1400, 900):
            for scheme in ("light", "dark"):
                with self.subTest(width=width, scheme=scheme):
                    c, k = self.both(width, scheme)
                    tag = f"{scheme} {width}"
                    self.check(c, k, width, tag)

    def check(self, c, k, width, tag):
        # Next steps: the count is text, not a round badge; Cards keeps the badge
        self.assertEqual(c["badge"], ["rgba(0, 0, 0, 0)", "0px", "0px"], tag)
        self.assertEqual(k["badge"][1:], ["12px", "24px"], tag)
        self.assertEqual(c["box"], ["0px"] * 4, tag)
        self.assertEqual(k["box"][3], "4px", tag)
        for got, parent in c["type"]:
            self.assertEqual(got, parent, tag)
        self.assertEqual(c["font"][0], c["font"][1], tag)
        self.assertEqual(c["color"][0], c["color"][1], tag)
        self.assertEqual(c["text"], k["text"], tag)
        self.assertTrue(c["text"], tag)
        self.assertEqual((c["scroll"], k["scroll"]), (width, width), tag)

    def test_cards_page_is_the_page_with_no_theme_layer(self):
        plain = page.page_html(EMPTY_BRANDING)
        self.assertEqual(page.page_html(EMPTY_BRANDING, theme=None), plain)
        self.assertEqual(page.page_html(EMPTY_BRANDING, theme="no-such-theme"), plain)
        self.assertNotIn('id="theme"', plain)
        self.assertNotIn("Row 1316c", plain)
        classic = page.page_html(EMPTY_BRANDING, theme=NAME)
        self.assertIn("#usecases .ucsteps .ucn-b", classic)
        self.assertEqual(classic.replace(classic[classic.index('\n<style id="theme">'):classic.index("</style>", classic.index('<style id="theme">')) + 8], ""), plain)


if __name__ == "__main__":
    unittest.main()
