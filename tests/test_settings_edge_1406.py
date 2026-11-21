"""Row 1406 in the Classic Theme: the Settings card controls (field, search box, button, choice) have a 1px border in the prototype's line colour,
read from the real Settings pages as Chrome computes it at 1400 then 900, light and dark; Cards keeps the control-edge token (the control).
Run: python3 dev/run_tests.py test_settings_edge_1406
Fails, never skips, without Chrome."""
import re
import shutil
import tempfile
import unittest

from _paths import ROOT

from clark import page
from test_server import Running, chrome, wait
from test_settings_sidebar_1401 import ratio
from test_settings_look_1200 import PAGE_READY, STUB, rgb
from test_work_items import FIXED_DATE, load_demo, page_target

NAME = "prototype-2.0"
WIDTHS = (1400, 900)
LIGHT_LINE = "#D9E0EF"
CARDS_SEARCH = {"light": "#C4CEE3", "dark": "#2B5868"}     # the Cards Settings search box edge on main (measured below on this page)
DARK_LINE = "#2B3850"     # the Classic dark value of the same grey-200 token
PROBE = """(() => { const q = (s) => document.querySelector(s), g = (s) => { const e = q(s); return e ? [getComputedStyle(e).borderTopColor, getComputedStyle(e).borderTopWidth] : null; };
  if (!q('.frame:not(#gantt-setting) .set-reset')) { const f = q('#ess-name') && q('#ess-name').closest('.frame'); if (f) f.insertAdjacentHTML('beforeend', '<button type="button" class="set-reset">Reset</button>'); }  /* the real Reset button (SettingRow.jsx) shows only after a change; add its markup to a real non-Gantt card */
  const inv = {}; for (const [k, sel] of [['name', '#ess-name'], ['rowtext', '.set-row-ctl input[type="text"]']]) { const e = q(sel); if (e) { e.setAttribute('aria-invalid', 'true'); inv[k] = getComputedStyle(e).borderTopColor; e.removeAttribute('aria-invalid'); } }
  const redp = document.createElement('i'); redp.style.borderTopColor = 'var(--status-red-text)'; redp.style.borderTopStyle = 'solid'; document.body.appendChild(redp); const red = getComputedStyle(redp).borderTopColor; redp.remove();
  const b = q('.seg button + button');
  const ground = (s) => { let e = q(s); while (e) { const c = getComputedStyle(e).backgroundColor; if (c !== 'rgba(0, 0, 0, 0)' && c !== 'transparent') return c; e = e.parentElement; } return null; };
  return {ground: ground('#safety-copy-box') || ground('#ess-name') || ground('.seg'),
          edges: {box: g('#safety-copy-box'), save: g('[data-copy-save]'), choice: g('.seg'), name: g('#ess-name'), paste: g('#client-folder-paste'), use: g('[data-copy-suggestion]'), search: g('.set-search input'), reset: g('.frame:not(#gantt-setting) .set-reset'), rowtext: g('.set-row-ctl input[type="text"]'), gantt: g('#gantt-name')},
          invalid: inv, red: red,
          divider: b ? getComputedStyle(b).borderLeftColor : null}; })()"""


class SettingsEdge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.store, cls.folder, _ = load_demo()
        cls.names = {p["code"]: p["name"] for p in cls.store.read("projects")}

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(str(cls.folder), ignore_errors=True)

    def read(self, theme, width, scheme):
        def data_for(code, archived=None):
            d = self.store.data_for(code)
            d["project"]["gantt_tab_name"] = "Delivery plan"
            return d
        brand = tempfile.mkdtemp(prefix="clark-no-brand-")
        self.addCleanup(shutil.rmtree, brand, True)
        s = Running(data_for=data_for, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}], page_html=lambda: page.page_html(brand, theme=theme))
        self.addCleanup(s.close)
        got = {"edges": {}, "ground": None}
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB}, sid)
            for n, (slug, ready) in enumerate(PAGE_READY):
                if n == 0:
                    cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{s.port}/#settings&p=TUL&s={slug}"}, sid)
                else:
                    cdp.js(f"location.hash = '#settings&p=TUL&s={slug}'", sid)
                self.assertTrue(wait(lambda: cdp.js(ready + " && !!document.querySelector('.set-chip[aria-current]')", sid)), f"Settings {slug} drawn")
                if n == 0:
                    cdp.js(f"document.documentElement.dataset.theme = '{scheme}'", sid)
                    cdp.js("document.querySelectorAll('*').forEach((e) => { e.style.transition = 'none'; })", sid)
                r = cdp.js(PROBE, sid)
                for k, v in r["edges"].items():
                    if v is not None and k not in got["edges"]:
                        got["edges"][k] = v
                if r["ground"] and not got["ground"]:
                    got["ground"] = r["ground"]
                got.setdefault("invalid", {})
                for k, v in (r.get("invalid") or {}).items():
                    got["invalid"].setdefault(k, v)
                got["red"] = r["red"]
                if r["divider"] and "divider" not in got:
                    got["divider"] = r["divider"]
        return got

    def test_classic_controls_take_the_line_colour(self):
        for scheme, line in (("light", LIGHT_LINE), ("dark", DARK_LINE)):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w):
                    got = self.read(NAME, w, scheme)
                    for name in ("box", "save", "choice", "name", "paste", "use", "search", "reset", "rowtext"):
                        self.assertEqual(got["edges"][name], [rgb(line), "1px"], f"{name} edge, Classic {scheme} {w}")
                    self.assertEqual(got["divider"], rgb(line), f"choice divider, Classic {scheme} {w}")
                    self.assertEqual(got["edges"]["gantt"][0], "rgb(196, 206, 227)" if scheme == "light" else "rgb(43, 88, 104)", f"the Gantt card keeps its edge, Classic {scheme} {w}")

    def test_a_field_marked_invalid_keeps_its_red_border(self):
        """The line colour is for a valid field only: with aria-invalid set, the Settings field and the row text input keep the red error border of shell.css."""
        for scheme in ("light", "dark"):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w):
                    got = self.read(NAME, w, scheme)
                    self.assertEqual(sorted(got["invalid"]), ["name", "rowtext"], f"both fields probed, Classic {scheme} {w}")
                    for name, colour in got["invalid"].items():
                        self.assertNotEqual(colour, got["edges"][name][0], f"{name} invalid border is not the line colour, Classic {scheme} {w}")
                        self.assertEqual(colour, got["red"], f"{name} invalid border is the error red, Classic {scheme} {w}")

    def test_reset_markup_matches_the_real_page_source(self):
        src = (ROOT / "src" / "clark" / "page" / "src" / "edit" / "SettingRow.jsx").read_text(encoding="utf-8")
        self.assertIn('<button type="button" class="set-reset"', src)

    def test_the_measured_line_against_its_ground(self):
        """Measured from the computed border and the card ground Chrome draws, 1400 and 900: the Classic line is 1.32:1 on white in light and 1.46:1 in dark,
        both under the non-text 3:1 (the named exemption); the old Cards edge, 7A859F, is 3.70:1 on white."""
        for scheme, want in (("light", 1.32), ("dark", 1.46)):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w):
                    got = self.read(NAME, w, scheme)
                    r = ratio(got["edges"]["name"][0], got["ground"])
                    print(f"1406 border {scheme} {w}: {got['edges']['name'][0]} on {got['ground']} = {r:.2f}:1")
                    self.assertAlmostEqual(r, want, places=2, msg=f"Classic {scheme} {w} border ratio")
                    self.assertLess(r, 3.0, "the exemption is real: under 3:1")

    def test_cards_keeps_the_control_edge(self):
        for scheme, edge in (("light", "#7A859F"), ("dark", "#7AA3AE")):
            for w in WIDTHS:
                with self.subTest(scheme=scheme, width=w):
                    got = self.read(None, w, scheme)
                    for name in ("box", "save", "choice", "name", "paste", "use"):
                        self.assertEqual(got["edges"][name], [rgb(edge), "1px"], f"{name} edge, Cards {scheme} {w}")
                    self.assertEqual(got["edges"]["search"], [rgb(CARDS_SEARCH[scheme]), "1px"], f"search box edge unchanged, Cards {scheme} {w}")

    def test_the_exemption_is_one_rule_naming_the_settings_controls(self):
        """The ONE named exemption (ticket 1406, the 18-11 ruling, do not redesign for contrast): the Settings card controls' border in Classic is the grey-200 line
        colour, which is under 3:1 on white; no other control, icon or text is exempt, and the Classic rule file holds no colour literal for it."""
        rules = (ROOT / "src" / "clark" / "themes" / NAME / "rules.css").read_text(encoding="utf-8")
        hits = re.findall(r"^[^/\n][^\n]*border-color: var\(--grey-200\); \}$", rules, re.M)
        self.assertEqual(len([h for h in hits if ".set-cards .frame" in h]), 1, "one rule sets the exempt border")
        self.assertNotIn(".btn.pri", rules.split("/* Row 1406")[1].split("/* Row 1400")[0], "primary buttons are not exempt")


if __name__ == "__main__":
    unittest.main()
