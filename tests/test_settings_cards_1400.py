"""Row 1400 in the Classic Theme, on the REAL Settings pages (committed page, real server, demo database), as Chrome computes it at 1400 and 900 px, light and dark:
the card sub-heading (15 px, 600, heading colour, sentence case, heading face), the field and row labels (15 px, 600), the spacing cards (1 px border in the grey-500 tone, radius 14)
and the Update rows' label (15 px, 600). Cards is the control and keeps what it had. Values are the ticket's (measured on the prototype by the audit).

Run: python3 dev/run_tests.py test_settings_cards_1400
Fails, never skips, without Chrome."""
import shutil
import tempfile
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
SIZES = (1400, 900)
PAGES = {"folder": (".set-cards .setting > h3, .set-cards .setting-part > h3", "folder"), "profile": (".set-cards .fld > label", "profile"),
         "essentials": (".set-cards .set-row-text label", "profile"), "appearance": (".secpick input:not(:checked) + .secpick-card", "appearance"), "version": (".upd-rows .upd-l", "version")}
PROBE = """function(sel) { const e = document.querySelector(sel); if (!e) return null; const g = (p) => getComputedStyle(e)[p];
  const tok = (v, p) => { const i = document.createElement('i'); i.style[p] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p]; i.remove(); return r; };
  return { size: g('fontSize'), weight: g('fontWeight'), color: g('color'), case: g('textTransform'), track: g('letterSpacing'), family: g('fontFamily'),
    border: g('borderTopWidth') + ' ' + g('borderTopColor'), radius: g('borderTopLeftRadius'), grey500: tok('var(--grey-500)', 'borderTopColor'), heading: tok('var(--heading)', 'color'),
    head: tok('var(--font-head)', 'fontFamily') }; }"""


class Real(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, cls.ids = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}
        cls.data = {c: cls.store.data_for(c) for c in cls.names}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def serve(self, theme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s

    def look(self, cdp, port, width, scheme, slug, sel):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL&s={slug}")}, sid)
        if slug == "version":      # the demo server has no update status, so the card shows no rows: add the rows' markup (Update.jsx) to the real card
            self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#update')", sid)), 30), "timed out waiting for the update card")
            cdp.js("if (!document.querySelector('.upd-rows')) document.querySelector('#update').insertAdjacentHTML('beforeend', '<div class=\"upd-rows\"><p class=\"upd-l\">Installed</p><div class=\"upd-c\"><p>Version</p></div></div>')", sid)
        self.assertTrue(wait(lambda: bool(cdp.js(f"!!document.querySelector({sel!r})", sid)), 30), f"timed out waiting for {sel} on the {slug} page")
        return cdp.js(f"({PROBE})({sel!r})", sid)

    def each(self, theme):
        s = self.serve(theme)
        for scheme in ("light", "dark"):
            for width in SIZES:
                for key, (sel, slug) in PAGES.items():
                    with chrome() as cdp:
                        yield f"{theme or 'cards'} {scheme} {width} {key}", key, self.look(cdp, s.port, width, scheme, slug, sel)

    def test_classic_sub_heading_labels_spacing_cards_and_update_rows(self):
        for tag, slug, c in self.each(NAME):
            if slug == "folder":
                self.assertEqual((c["size"], c["weight"], c["case"], c["track"]), ("15px", "600", "none", "normal"), tag + ": card sub-heading 15 px, 600, sentence case")
                self.assertEqual(c["color"], c["heading"], tag + ": sub-heading in the heading colour")
                self.assertEqual(c["family"], c["head"], tag + ": sub-heading in the heading face")
            elif slug in ("profile", "essentials", "version"):
                self.assertEqual((c["size"], c["weight"]), ("15px", "600"), tag + ": label 15 px, 600")
            else:
                self.assertEqual(c["border"].split(" ", 1)[0], "1px", tag)
                self.assertEqual(c["radius"], "14px", tag + ": spacing card radius 14")
                self.assertEqual(c["border"].split(" ", 1)[1], c["grey500"], tag + ": spacing card border in the grey-500 tone")

    def test_cards_keeps_its_own_look(self):
        for tag, slug, c in self.each(None):
            if slug == "folder":
                self.assertEqual((c["size"], c["case"]), ("13px", "uppercase"), tag + ": Cards sub-heading unchanged")
            elif slug == "version":
                self.assertEqual((c["size"], c["weight"]), ("14px", "400"), tag)
            elif slug == "appearance":
                self.assertNotEqual(c["border"].split(" ", 1)[1], c["grey500"], tag + ": Cards spacing card border unchanged")


if __name__ == "__main__":
    unittest.main()
