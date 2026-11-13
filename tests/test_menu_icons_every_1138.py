"""Row 1138 (extends 1074): every drop-down menu shows an icon beside each line's words, the same icon for the same action.

Run: python3 dev/run_tests.py test_menu_icons_every_1138
Part 1 reads the shared map (page/src/menuIcons.js ACTION_ICON) in node. Part 2 reads the source: each menu takes its icons from the
map. Part 3 drives the real page (the harness of tests/test_report_editor.py) in headless Chrome at 1400 and 900: the section menu and
the profile menu, with the words as they were.
"""
import json
import re
import shutil
import subprocess
import time
import unittest

from _paths import ROOT

from test_report_editor import Base, IDS  # noqa: E402
from test_server import chrome  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
WIDTHS = (1400, 900)


def run_js(body):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    code = f'import * as M from "{(SRC / "menuIcons.js").as_uri()}"; {body}'
    done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


class Map(unittest.TestCase):
    def test_every_icon_in_the_map_is_in_the_existing_set(self):
        icons = (SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        for action, name in run_js("console.log(JSON.stringify(M.ACTION_ICON))").items():
            self.assertRegex(icons, rf'(?m)^\s*"?{re.escape(name)}"?:', action)

    def test_move_up_and_move_down_differ_and_delete_is_the_bin(self):
        m = run_js("console.log(JSON.stringify(M.ACTION_ICON))")
        self.assertNotEqual(m["up"], m["down"])
        self.assertEqual(m["delete"], "trash")
        self.assertEqual(m["exportExcel"], m["exportWord"])
        self.assertEqual(run_js("console.log(JSON.stringify(M.actionIcon('nonsense') ?? null))"), None)


class Source(unittest.TestCase):
    def test_each_menu_takes_its_icons_from_the_map(self):
        for rel in ("edit/Gutter.jsx", "edit/ProfileMenu.jsx", "edit/RowMenu.jsx", "components/ClientMenu.jsx",
                    "gantt/components/GanttTable.jsx", "gantt/components/GanttChart.jsx"):
            self.assertIn("actionIcon", (SRC / rel).read_text(encoding="utf-8"), rel)

    def test_the_row_menu_no_longer_names_its_own_icons_for_shared_actions(self):
        text = (SRC / "edit" / "RowMenu.jsx").read_text(encoding="utf-8")
        for bad in ('icon: "trash"', 'icon: "archive"', 'icon: "ext"'):
            self.assertNotIn(bad, text)


class Page(Base):
    def at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        time.sleep(.2)

    def test_the_section_menu_gives_each_line_its_icon_and_keeps_its_words(self):
        want = {"add": "plus", "up": "chevup", "down": "chevdown", "beside": "board", "full": "arrows-out", "hide": "eyeoff",
                "show": "eye", "delete": "trash", "settings": "gear"}
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                for ref in IDS:
                    p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-options]').click()")
                    p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .menu')", "the menu opened")
                    p.until("!!document.activeElement && !!document.activeElement.closest('.menu')", "focus moved into the menu")
                    got = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .menu-item')].map(b => {{ const s = b.querySelector('svg.i'); "
                               "const r = s ? s.getBoundingClientRect() : {width: 0}; const t = b.querySelector('.mi-t'); "
                               "return {act: b.dataset.act, icn: s ? s.dataset.icn : '', w: r.width, text: t ? t.textContent.trim() : '', all: b.textContent.trim()}; })")
                    p.key("Escape", code="Escape", vk=27)
                    p.until(f"!document.querySelector('[data-id=\"{ref}\"] .menu')", "closed")
                    self.assertTrue(got)
                    for g in got:
                        self.assertEqual(g["icn"], want[g["act"]], f"{ref} {g['act']} at {w}")
                        self.assertGreaterEqual(g["w"], 15, f"{ref} {g['act']} at {w}: the icon is drawn")
                        self.assertTrue(g["text"] and g["text"] == g["all"], f"{ref} {g['act']}: the words are plain")

    def test_the_profile_menu_gives_each_command_its_icon(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                p.js("document.querySelector('#profile-btn').click()")
                p.until("!!document.querySelector('#profile-menu [role=menuitem]')", "the profile menu opened")
                got = p.js("[...document.querySelectorAll('#profile-menu [role=menuitem]:not(.who-link)')].map(b => { const s = b.querySelector('svg.i'); "
                           "return {id: b.dataset.kind, icn: s ? s.dataset.icn : ''}; })")
                p.key("Escape", code="Escape", vk=27)
                ids = {g["id"]: g["icn"] for g in got}
                self.assertEqual(ids.get("publish"), "ul", w)
                self.assertEqual(ids.get("export"), "dl", w)
                self.assertEqual(ids.get("word-export"), "dl", w)
                self.assertEqual(ids.get("settings"), "gear", w)
                self.assertEqual(ids.get("help"), "info", w)


if __name__ == "__main__":
    unittest.main()
