"""Row 1286 AP4 (ruling 23-11): the icons of Group by, Add and Move to draw the mock-up tones; every other menu keeps production's.

Run: python3 dev/run_tests.py test_menu_icon_tones_1286
Classic only (the Classic theme layered on the shell's styles). A probe icon of each tone (red, amber, green, blue, grey and the neutral, an icon with no
tone class) is put in each of the three menus' boxes and in two other menus' boxes, at 1400 and 900, light and dark, and its COMPUTED colour is read:
the three menus draw red #a3301f / #ff9b8a, green #006b5e / #4fd1bd, blue #2f4bb8 / #9db0ff (light / dark), amber and grey as production; the others keep
the production colour of the same icon outside any menu. Cards (no theme) draws no menu differently. The real open menus are read in test_menus_one_look_1286.
"""
import json
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import build_page  # noqa: E402
from clark import theme  # noqa: E402
from test_server import chrome, wait  # noqa: E402

NAME = "prototype-2.0"
RULES = "".join((ROOT / "src" / "clark" / "themes" / NAME / f).read_text(encoding="utf-8") for f in ("rules.css", "rules-2.css"))
THREE = {"group-by": '<div id="viewMenuList" class="ddmenu">', "add": '<div class="ddmenu" aria-label="Add a work item">', "move": '<div class="ddmenu" aria-label="Move item to">'}
OTHERS = {"columns": '<div class="ddmenu cols-menu" aria-label="Columns">', "row": '<div class="ddmenu" aria-label="Row actions">'}
TONES = ("ic-r", "ic-a", "ic-g", "ic-b", "ic-n", "")
MOCK = {"light": {"ic-r": "rgb(163, 48, 31)", "ic-a": "rgb(138, 90, 0)", "ic-g": "rgb(0, 107, 94)", "ic-b": "rgb(47, 75, 184)", "ic-n": "rgb(71, 85, 119)"},
        "dark": {"ic-r": "rgb(255, 155, 138)", "ic-g": "rgb(79, 209, 189)", "ic-b": "rgb(157, 176, 255)"}}
READ = """(() => { const o = {}; for (const el of document.querySelectorAll('[data-probe]')) o[el.dataset.probe] = getComputedStyle(el).color; return o; })()"""


def body():
    out = ['<i data-probe="outside/%s" class="%s"></i>' % (t or "none", t) for t in TONES]
    for kind, boxes in (("three", THREE), ("other", OTHERS)):
        for name, open_tag in boxes.items():
            out.append(open_tag + "".join('<i data-probe="%s/%s" class="%s"></i>' % (name, t or "none", t) for t in TONES) + "</div>")
    return "".join(out)


class Tones(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        path = Path(self.tmp.name) / "page.html"
        path.write_text(f'<!doctype html><meta charset=utf-8><style>{build_page.page_css()}</style><style>{theme.css(NAME)}</style><body>{body()}</body>', encoding="utf-8")
        self.url = path.as_uri()

    def test_computed_icon_tones_light_and_dark_at_1400_and_900(self):
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.navigate", {"url": self.url}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('[data-probe]').length", sid) == len(TONES) * 6), "the probe page loaded")
            for width in (1400, 900):
                for th in ("light", "dark"):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.js(f"document.documentElement.dataset.theme = {json.dumps(th)}", sid)
                    self.assertTrue(wait(lambda: cdp.js(f"innerWidth === {width} && document.documentElement.dataset.theme === {json.dumps(th)}", sid)))
                    got = cdp.js(READ, sid)
                    where = f"at {width} {th}"
                    prod = {t: got["outside/%s" % (t or "none")] for t in TONES}
                    self.assertGreaterEqual(len(set(prod.values())), 5, where)
                    for name in list(THREE) + list(OTHERS):
                        for t in TONES:
                            c = got["%s/%s" % (name, t or "none")]
                            if name in THREE and t in MOCK[th]:
                                self.assertEqual(c, MOCK[th][t], f"{name} {t or 'neutral'} {where}: the mock-up tone")
                            else:
                                self.assertEqual(c, prod[t], f"{name} {t or 'neutral'} {where}: production's colour")
                    for t in ("ic-r", "ic-g", "ic-b"):      # another menu keeps production, which is not the mock-up tone
                        self.assertNotEqual(got["columns/%s" % t], MOCK[th][t], f"{t} in Columns {where}")
                        self.assertNotEqual(got["row/%s" % t], MOCK[th][t], f"{t} in a row menu {where}")


class Static(unittest.TestCase):
    def test_the_rule_is_scoped_and_in_the_classic_theme_only(self):
        for tone, tok in (("ic-r", "--status-red-text"), ("ic-g", "--status-green-text"), ("ic-b", "--tone-blue-text")):
            self.assertIn(f'[aria-label$=" to"]) .{tone} {{ color: var({tok}); }}', RULES)
        self.assertNotRegex(RULES, r"[^}]*\.ic-[an]\s*\{[^}]*--(status|tone)")


if __name__ == "__main__":
    unittest.main()
