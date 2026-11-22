"""Row 1317 in the Classic Theme, on the REAL Settings page (the committed page from the real server, demo database, fictional data), as Chrome computes
it at 1400 and 900 px, light and dark; the same elements under Cards as the control. Listed in issue 1317 (Classic re-audit, 18-11): the sidebar is a
grey panel with sentence-case group names and a tinted bar for the open page, the Settings cards have radius 14 and no shadow, the Projects table header is
bold and sentence case without the divider line, and Add project is a filled blue button with its plus and its word always visible.

Run: python3 dev/run_tests.py test_theme_classic_1317
Fails, never skips, without Chrome. Sizes are by eye (+/-2 px): the prototype files are not on the box that built this."""
import hashlib
import re
import shutil
import tempfile
import time
import unittest

from _editor_checks import for_url

from clark import page
from test_server import Running, chrome, wait
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
# The Cards page, page_html(branding=NO_BRAND, theme=None), without its <script> blocks, taken from origin/main (3496323b) before this row and equal on main d6f756eec; rules.css is read only when a Theme is named.
# The script is left out on purpose: the shared JS bundle moves the whole-page sha without a Cards look change; the markup and CSS pins stay (the style md5 in test_ms_cards_1315 and test_work_items_mockup_1195).
CARDS_SHA256 = "bbd5f8b4139b78174b4cf9c5bcd4e75657e00645009f5790869c1e68a4b068a2"
SIZES = (1400, 900)
PROBE = """(() => { const q = (s) => document.querySelector(s), g = (e, p) => getComputedStyle(e)[p];
  const tok = (v, p) => { const i = document.createElement('i'); i.style[p || 'color'] = v; document.body.appendChild(i); const r = getComputedStyle(i)[p || 'color']; i.remove(); return r; };
  const bar = q('.set-bar'), cur = q('.set-chip[aria-current]'), name = q('.set-group-name'), card = q('.set-cards .frame'), th = q('#projects-table th');
  const mc = q('#projects-table tr[data-project="MOSS"] td.num'), rg = document.createRange(); rg.selectNodeContents(mc);
  const lines = new Set([...rg.getClientRects()].map((r) => Math.round(r.top))).size, mtr = mc.parentElement;
  const broken = []; document.querySelectorAll('#projects-table tbody td:not(.acts)').forEach((td) => { const w = document.createTreeWalker(td, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { const re = /\\S+/g; let m; while ((m = re.exec(n.data))) { const r = document.createRange(); r.setStart(n, m.index); r.setEnd(n, m.index + m[0].length);
      if (new Set([...r.getClientRects()].map((x) => Math.round(x.top))).size > 1) broken.push(m[0]); } } });
  const btn = q('#npBtn'), w = btn.querySelector('.w'), wr = w.getBoundingClientRect(), br = btn.getBoundingClientRect();
  return { barBg: g(bar, 'backgroundColor'), grey100: tok('var(--grey-100)', 'backgroundColor'), grey50: tok('var(--grey-50)', 'backgroundColor'), barPos: g(bar, 'position'), barPad: ['paddingTop', 'paddingRight', 'paddingBottom', 'paddingLeft'].map((k) => g(bar, k)).join(' '),
    barRadius: g(bar, 'borderTopLeftRadius'), groupCase: g(name, 'textTransform'), groupTrack: g(name, 'letterSpacing'), curRadius: ['borderTopLeftRadius', 'borderTopRightRadius', 'borderBottomRightRadius', 'borderBottomLeftRadius'].map((k) => g(cur, k)).join(' '),
    marker: (() => { const m = getComputedStyle(cur, '::before'), r = cur.getBoundingClientRect(); return [m.content, m.position, m.left, m.top, m.bottom, m.width, m.borderTopLeftRadius, Math.round(r.height)].join('|'); })(),
    cardRadius: g(card, 'borderTopLeftRadius'), cardShadow: g(card, 'boxShadow'),
    thCase: g(th, 'textTransform'), thTrack: g(th, 'letterSpacing'), thWeight: g(th, 'fontWeight'), thBorderTop: g(th, 'borderTopWidth'),
    btnBg: g(btn, 'backgroundColor'), btnColor: g(btn, 'color'), brand: tok('var(--brand-blue)', 'backgroundColor'), onBrand: tok('var(--text-on-brand)'),
    wMax: g(w, 'maxWidth'), wOpacity: g(w, 'opacity'), wWidth: Math.round(wr.width), btnW: Math.round(br.width), btnH: Math.round(br.height), word: w.textContent.trim(),
    icons: btn.querySelectorAll('svg, .i').length, iconW: Math.round((btn.querySelector('svg, .i') || {getBoundingClientRect: () => ({width: 0})}).getBoundingClientRect().width),
    codeText: mc.textContent.trim(), codeLines: lines, codeW: Math.round(mc.getBoundingClientRect().width), rowH: Math.round(mtr.getBoundingClientRect().height),
    brokenWords: broken, codeWs: g(mc, 'whiteSpace'), codeWrap: g(mc, 'overflowWrap'),
    groupSize: g(name, 'fontSize'), groupWeight: g(name, 'fontWeight'), chipH: Math.round(q('.set-chip:not([aria-current])').getBoundingClientRect().height),
    tint: tok('color-mix(in srgb, var(--grey-500) 15%, var(--grey-100))', 'backgroundColor') }; })()"""
HOVER = """(() => { const c = [...document.querySelectorAll('.set-chip:not([aria-current])')][0]; const r = c.getBoundingClientRect(); return [Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2)]; })()"""
HOVERED = "getComputedStyle([...document.querySelectorAll('.set-chip:not([aria-current])')][0]).backgroundColor"


def width_is_wide(tag):
    return tag.endswith("1400")


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

    def serve(self, theme):
        s = Running(data_for=lambda code, **kw: self.data.get(code), projects=lambda archived=False: [{"code": c, "name": n} for c, n in sorted(self.names.items())],
                    page_html=lambda: page.page_html(tempfile.mkdtemp(), theme=theme))
        self.addCleanup(s.close)
        return s

    def look(self, cdp, port, width, scheme):
        sid = page_target(cdp)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Page.navigate", {"url": "about:blank"}, sid)
        cdp.call("Page.navigate", {"url": for_url(f"http://127.0.0.1:{port}/#settings&p=TUL")}, sid)
        self.assertTrue(wait(lambda: bool(cdp.js("!!document.querySelector('#projects-table tbody tr') && !!document.querySelector('#npBtn') && !!document.querySelector('.set-bar')", sid)), 30),
                        "timed out waiting for the real Settings page")
        cdp.js("document.querySelectorAll('.set-chip, #npBtn, #npBtn .w').forEach((e) => { e.style.transition = 'none'; })", sid)
        got = cdp.js(PROBE, sid)
        x, y = cdp.js(HOVER, sid)
        cdp.call("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": x, "y": y}, sid)
        time.sleep(0.3)
        got["chipHover"] = cdp.js(HOVERED, sid)
        return got

    def each(self, theme):
        s = self.serve(theme)
        for scheme in ("light", "dark"):
            for width in SIZES:
                with chrome() as cdp:
                    yield f"{theme or 'cards'} {scheme} {width}", self.look(cdp, s.port, width, scheme)

    def test_classic_settings_sidebar_cards_table_and_add_project(self):
        for tag, c in self.each(NAME):
            self.assertEqual(c["barBg"], c["grey50"], tag + ": the sidebar is the soft grey panel (row 1356)")
            self.assertEqual(c["barRadius"], "10px", tag + ": the panel radius is 10 (row 1356)")
            self.assertEqual(c["barPos"], "sticky", tag + ": the real bar is still sticky")
            self.assertEqual(c["barPad"], "8px 4px 8px 4px" if width_is_wide(tag) else "4px 4px 8px 4px", tag + ": the panel padding is 8px 4px (row 1356; at 900 the top is 4px, item 1177)")
            self.assertEqual(c["groupCase"], "none", tag + ": group names in sentence case")
            self.assertEqual(c["groupTrack"], "normal", tag)
            self.assertEqual(c["curRadius"], "10px 10px 10px 10px", tag + ": the open page chip has radius 10 on all four corners (ruling 20-11, prototype settings.css:34)")
            head, h = c["marker"].rsplit("|", 1)      # row 1299: at 900 the longer page names (Projects overview) can wrap the open chip, so only the wide chip is pinned at 36
            self.assertEqual(head, '""|absolute|0px|7px|7px|3px|3px', tag + ": the 3px marker is inside the chip, 7px from top and bottom, radius 3 (prototype settings.css:37)")
            self.assertTrue(int(h) == 36 if width_is_wide(tag) else int(h) >= 36, tag + ": the open chip is 36px high (wide) or at least that (900)")
            self.assertEqual((c["barRadius"], c["groupSize"], c["groupWeight"]), ("10px", "14px", "600"), tag + ": panel radius 10, group name 14px 600")
            if width_is_wide(tag):
                self.assertEqual(c["chipH"], 36, tag + ": sidebar row 36px high")
            self.assertNotEqual(c["chipHover"], c["tint"], tag + ": no hover tint on a sidebar chip (not in the list)")
            self.assertEqual((c["cardRadius"], c["cardShadow"]), ("14px", "none"), tag + ": Settings cards radius 14, no shadow")
            self.assertEqual((c["thCase"], c["thTrack"], c["thWeight"], c["thBorderTop"]), ("none", "normal", "700", "0px"), tag + ": bold sentence-case header, no divider")
            self.assertEqual((c["btnBg"], c["btnColor"]), (("rgb(6, 47, 58)" if "light" in tag else c["brand"]), c["onBrand"]), tag + ": Add project is a filled button (navy in light since row 1402, blue in dark)")
            self.assertEqual(c["icons"], 1, tag + ": one plus, as an svg or .i")
            self.assertGreater(c["iconW"], 0, tag)
            self.assertEqual(c["wOpacity"], "1", tag + ": the word is visible without a hover")
            self.assertNotEqual(c["wMax"], "0px", tag)
            self.assertGreater(c["wWidth"], 30, tag)
            self.assertEqual(c["word"], "Add project", tag)
            self.assertGreater(c["btnW"], c["btnH"] * 2, tag + ": a wide button with its word, not a round +")

    def test_classic_projects_code_cell_stays_on_one_line(self):
        for tag, c in self.each(NAME):
            self.assertEqual(c["codeText"], "MOSS", tag)
            self.assertEqual(c["codeLines"], 1, tag + f": the Code cell MOSS is one line, not broken (cell {c['codeW']} px, row {c['rowH']} px)")
            self.assertEqual((c["codeWs"], c["codeWrap"]), ("nowrap", "normal"), tag)

    def test_classic_projects_table_never_breaks_a_word_in_the_middle(self):
        for tag, c in self.each(NAME):
            self.assertEqual(c["brokenWords"], [], tag + ": a word in a Projects cell is broken mid-word (the narrower table must wrap at spaces, as main does)")

    def test_cards_keeps_its_own_settings_look(self):
        for tag, c in self.each(None):
            self.assertEqual(c["groupCase"], "uppercase", tag)
            self.assertEqual(c["thCase"], "uppercase", tag)
            self.assertEqual(c["wMax"], "0px", tag + ": the word grows in on hover under Cards")
            self.assertNotEqual(c["barBg"], c["grey100"], tag)
            self.assertNotEqual(c["thBorderTop"], "0px", tag + ": Cards keeps the divider")
            self.assertNotEqual(c["btnBg"], c["brand"], tag + ": Cards keeps the dashed Add")
            self.assertEqual((c["codeWs"], c["codeWrap"]), ("normal", "anywhere"), tag + ": Cards Code cell unchanged")

    def test_the_cards_page_is_byte_for_byte_what_it_was(self):
        html = page.page_html(branding=page.NO_BRAND, theme=None)
        markup = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.S)
        self.assertEqual(hashlib.sha256(markup.encode("utf-8")).hexdigest(), CARDS_SHA256)
        classic = page.page_html(branding=page.NO_BRAND, theme="prototype-2.0")
        self.assertIn(".projects #npBtn.newb", classic)
        self.assertNotIn(".projects #npBtn.newb", html)


if __name__ == "__main__":
    unittest.main()
