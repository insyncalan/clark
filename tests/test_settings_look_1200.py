"""Item 1200, the Settings page look, pinned to the numbers measured on the approved mock-up, in real Chrome at 1400 and 900 px only.
Run: python3 dev/run_tests.py test_settings_look_1200

What is asserted at each width: the control-edge token is #7A859F and a field, a button and a choice are edged with it; the card heading is 20 px,
a setting's label 15 px semibold, a group label 13 px capitals, a help line 13 px in the muted colour; the empty name, backup-folder and pasted-folder
boxes show their examples; in Backups the path is a line of text with a short Use button beside it (not inside it); the side menu has soft
rows with a violet marker on the card you are reading, at both widths.
No setting, behaviour or Gantt card is changed here: the older Settings suites keep covering those. Chrome is required: this test fails, never skips, without it.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from _paths import SRC  # noqa: F401

from clark import page, server as sv  # noqa: E402
from test_backup_copy_focus import STUB as COPY_STUB  # noqa: E402
from test_server import CHROME, Running, chrome, wait  # noqa: E402
from test_work_items import FIXED_DATE, load_demo, page_target  # noqa: E402

WIDTHS = (1400, 900)
EDGE = "rgb(122, 133, 159)"
OLD_EDGE = "rgb(196, 206, 227)"       # the grey-300 edge the Gantt card had before item 1200
PATH = "/Users/demo/OneDrive-DemoOrg/clark backups"
# the stand-in listing offers one OneDrive folder, so the Use line is drawn
STUB = COPY_STUB.replace("/tmp/OneDrive", PATH)
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")

LOOK = """(() => {
  const q = (s) => document.querySelector(s), cs = (e, p) => getComputedStyle(e, p || null);
  const rect = (e) => { const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, t: r.top, b: r.bottom, w: r.width, h: r.height}; };
  const edge = (s) => { const e = q(s); return e ? [cs(e).borderTopColor, cs(e).borderTopWidth] : null; };
  const type = (s) => { const e = q(s); return e ? {size: cs(e).fontSize, weight: cs(e).fontWeight, upper: cs(e).textTransform, color: cs(e).color} : null; };
  const chips = [...document.querySelectorAll('.set-nav .set-chip')];
  const cur = q('.set-chip[aria-current]'), nav = q('.set-nav');
  const sug = (s) => { const b = q(s); if (!b) return null; const box = b.parentElement, path = box.querySelector('.copy-sug-path');
    return {text: b.textContent, name: b.getAttribute('aria-label'), btn: rect(b), path: rect(path), pathText: path.textContent, inside: b.contains(path)}; };
  return {
    token: cs(document.documentElement).getPropertyValue('--control-edge').trim(),
    muted: cs(document.documentElement).getPropertyValue('--text-muted').trim(),
    gantt: !q('#gantt-name') ? null : {name: edge('#gantt-name'), namePlaceholder: (q('#gantt-name') || {}).placeholder, reset: edge('#gantt-setting .set-reset'), intro: type('#gantt-setting > h2 + p'), button: type('#gantt-setting .set-reset')},
    sizes: {intro: type('#safety > h2 + p, #local-folder > h2 + p'), save: type('[data-copy-save]'), seg: type('.seg button'), chip: type('.set-nav .set-chip')},
    edges: {box: edge('#safety-copy-box'), save: edge('[data-copy-save]'), choice: edge('.seg'), name: edge('#ess-name'), paste: edge('#client-folder-paste'), use: edge('[data-copy-suggestion]')},
    heading: type('#safety-h'), label: type('.set-row-text label'), group: type('#local-folder h3'), help: type('.set-row-text small'),
    placeholders: {name: (q('#ess-name') || {}).placeholder, essCopy: (q('#ess-safety-copy-box') || {}).placeholder, copy: (q('#safety-copy-box') || {}).placeholder, paste: (q('#client-folder-paste') || {}).placeholder},
    use: sug('[data-copy-suggestion]'), essUse: sug('[data-ess-copy-suggestion]'),
    menu: {count: chips.length, minHeight: Math.min(...chips.map(c => rect(c).h)), tops: [...new Set(chips.map(c => Math.round(rect(c).t)))].length,
           radius: cs(chips[1]).borderTopLeftRadius, border: cs(chips[1]).borderTopWidth, curMarker: cur ? cs(cur, '::before').width : null, curMarkerShown: cur ? cs(cur, '::before').display : null,
           curBg: cur ? cs(cur).backgroundColor : null, curWeight: cur ? cs(cur).fontWeight : null, otherBg: cs(chips.find(c => c !== cur) || chips[0]).backgroundColor,
           navDir: cs(nav).flexDirection, pageScroll: document.documentElement.scrollWidth - innerWidth}
  };
})()"""


# The Settings pages that hold what is measured, each with what shows it is drawn (the first is the page the address opens).
PAGE_READY = [("profile", "!!document.querySelector('#ess-name') && !!document.querySelector('[data-ess-copy-suggestion]') && !!document.querySelector('#ess-safety-copy-box')"),
              ("appearance", "!!document.querySelector('.seg')"),
              ("backups", "!!document.querySelector('[data-copy-suggestion]') && !!document.querySelector('#safety-copy-box') && !!document.querySelector('#safety-h')"),
              ("folder", "!!document.querySelector('#client-folder-paste') && !!document.querySelector('#local-folder h3')"),
              ("reports", "!!document.querySelector('#gantt-name') && !!document.querySelector('#gantt-setting .set-reset')")]


def merge(into, more):
    """What a page read adds to what the pages before it read: a value another page did not have, key by key."""
    for k, v in more.items():
        if isinstance(v, dict) and isinstance(into.get(k), dict):
            merge(into[k], v)
        elif v is not None and (k not in into or into[k] is None):
            into[k] = v


def tearDownModule():
    shutil.rmtree(EMPTY_BRANDING, ignore_errors=True)


def rgb(hexa):
    h = hexa.lstrip("#")
    return "rgb(%d, %d, %d)" % tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


class SettingsLook(unittest.TestCase):
    def setUp(self):
        assert Path(CHROME).is_file(), f"Google Chrome is needed for the required browser tests ({CHROME}); set CLARK_CHROME"
        self.store, self.folder, _ = load_demo()
        self.addCleanup(shutil.rmtree, str(self.folder), True)
        self.addCleanup(self.store.close)
        self.s = Running(data_for=self.data_for, projects=lambda archived=False: [{"code": "TUL", "name": "Tulip"}],
                         page_html=lambda: page.page_html(EMPTY_BRANDING))
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def data_for(self, code, archived=None):
        d = self.store.data_for(code)
        d["project"]["gantt_tab_name"] = "Delivery plan"      # a renamed Gantt tab, so its Reset button is drawn
        return d

    def look(self, cdp, width, scheme="light"):
        sid = page_target(cdp)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.enable", {}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
        cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": STUB}, sid)
        # row 1024: one Settings page at a time, so each page that holds something measured is opened in turn and what it holds is read there
        got = {}
        for n, (slug, ready) in enumerate(PAGE_READY):
            if n == 0:
                cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#settings&p=TUL&s={slug}"}, sid)
            else:
                cdp.js(f"location.hash = '#settings&p=TUL&s={slug}'", sid)
            self.assertTrue(wait(lambda: cdp.js(ready + " && !!document.querySelector('.set-chip[aria-current]') && document.querySelector('.set-cards').getAttribute('data-page') === " + json.dumps(slug), sid)),
                            f"Settings, its {slug} page and its menu are drawn")
            if n == 0:
                cdp.js(f"document.documentElement.dataset.theme = {json.dumps(scheme)}", sid)
            merge(got, cdp.js(LOOK, sid))
        return got

    def test_the_look_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                k = self.look(cdp, w)
                self.assertEqual(k["token"].lower(), "#7a859f", f"the control-edge token at {w}")
                for name, got in k["edges"].items():
                    self.assertEqual(got, [EDGE, "1px"], f"{name} is edged with the control-edge token at {w}")
                self.assertEqual(k["heading"]["size"], "20px", f"card heading size at {w}")
                self.assertEqual((k["label"]["size"], k["label"]["weight"]), ("15px", "600"), f"setting label size and weight at {w}")
                self.assertEqual((k["group"]["size"], k["group"]["upper"]), ("13px", "uppercase"), f"group label size and capitals at {w}")
                self.assertEqual(k["help"]["size"], "13px", f"help line size at {w}")
                self.assertEqual(k["help"]["color"], rgb(k["muted"]), f"help line is in the muted colour at {w}")
                self.assertEqual(k["placeholders"], {"name": "Your full name", "essCopy": "/Users/you/OneDrive/clark backups", "copy": "/Users/you/OneDrive/clark backups",
                                                     "paste": "/Users/you/OneDrive/Client/Reports"}, f"the examples in the empty boxes at {w}")

    def test_the_gantt_card_keeps_its_old_edge_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                g = self.look(cdp, w)["gantt"]
                self.assertEqual(g["name"], [OLD_EDGE, "1px"], f"the Gantt tab name box keeps the old edge at {w}")
                self.assertEqual(g["reset"], [OLD_EDGE, "1px"], f"the Gantt Reset button keeps the old edge at {w}")
                self.assertNotEqual(g["name"][0], EDGE, f"the Gantt card does not take the new token at {w}")
                self.assertEqual(g["namePlaceholder"], "Gantt", f"the empty Gantt tab name box shows the example Gantt at {w}")
                self.assertEqual(g["intro"]["size"], "14px", f"the Gantt intro line keeps its old 14 px at {w}")

    def test_the_type_of_intro_buttons_choices_and_menu_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                z = self.look(cdp, w)["sizes"]
                for what in ("intro", "save", "seg", "chip"):
                    self.assertEqual(z[what]["size"], "15px", f"{what} is 15 px at {w}")

    def test_the_dark_control_edge_is_7aa3ae_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                k = self.look(cdp, w, "dark")
                self.assertEqual(k["token"].lower(), "#7aa3ae", f"the dark control-edge token at {w}")
                for name, got in k["edges"].items():
                    self.assertEqual(got, [rgb("#7AA3AE"), "1px"], f"{name} is edged with the dark token at {w}")

    def test_the_backups_path_is_beside_a_short_use_button_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                k = self.look(cdp, w)
                for which in ("use", "essUse"):
                    u = k[which]
                    self.assertEqual(u["text"], "Use", f"{which}: the button says only Use at {w}")
                    self.assertEqual(u["name"], "Use " + PATH, f"{which}: its name for a screen reader still has the path at {w}")
                    self.assertEqual(u["pathText"], PATH, f"{which}: the path is drawn as a line of text at {w}")
                    self.assertFalse(u["inside"], f"{which}: the path is not inside the button at {w}")
                    self.assertLessEqual(u["btn"]["w"], 80, f"{which}: the button is short at {w}: {u['btn']}")
                    self.assertGreaterEqual(u["btn"]["l"], u["path"]["r"] - 1, f"{which}: the button is at the right of the path at {w}: {u}")
                    self.assertLess(abs((u["btn"]["t"] + u["btn"]["b"]) / 2 - (u["path"]["t"] + u["path"]["b"]) / 2), 12, f"{which}: same line as the path at {w}: {u}")

    def test_the_side_menu_at_1400_and_900(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                m = self.look(cdp, w)["menu"]
                self.assertEqual(m["minHeight"], 32, f"every menu row is exactly 32 px at {w}")      # row 1280: tighter rows (was 36), so a group reads as a block
                self.assertEqual(m["border"], "0px", f"soft rows: no outline at {w}")
                self.assertEqual(m["curWeight"], "600", f"the marked row is semibold at {w}")
                self.assertNotEqual(m["curBg"], m["otherBg"], f"the marked row has a tint the others have not at {w}")
                self.assertLessEqual(m["pageScroll"], 0, f"the page does not scroll sideways at {w}")
                self.assertEqual(m["radius"], "10px", f"rows are rounded 10 px at {w}")
                self.assertEqual((m["curMarker"], m["curMarkerShown"]), ("3px", "block"), f"the violet marker is 3 px wide at {w}")
                self.assertEqual(m["navDir"], "column", f"a list down the left at {w}")
                self.assertGreater(m["tops"], 1, f"one row each at {w}")


if __name__ == "__main__":
    unittest.main()
