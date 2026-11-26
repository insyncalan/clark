"""Row 1281, Classic theme only (Cards, frozen, keeps its menu as it is): the profile menu has no Export to Word, has no Appearance (row 1627,
the owner 25-11: the pill line System | Light | Dark of row 1281 is gone; Settings keeps it), and the Help line carries
"clark ver. X" at its right end, X read from /health (never written in the page). Same storage as before. Export to Word stays in Settings > Data.

Run: python3 dev/run_tests.py test_profile_menu_classic_1281
"""
import json
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, "tests")
import _testpage as testpage
from test_publish_dialog import Base, WIDTHS
from test_publish_route import Rig
from test_server import chrome
from clark import page, server as sv, theme

ROOT = Path(__file__).resolve().parent.parent
ITEMS = ["Preview the page in a new tab", "Export to Excel", "Publish…", "Published reports", "Settings", "Help"]
WHO = "Add your name in Settings"
VER = "9.8.7"


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class Classic(Base):
    def setUp(self):
        self.rig = Rig(self, saved=True, page_html=classic_html)

    def open_menu(self, p):
        p.js("document.querySelector('#profile-btn').focus()")
        p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                "return !!document.querySelector('#profile-menu'); })()", "the menu opened")

    def menu(self, p):
        return p.js("[].map.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return e.textContent.replace(/ ?clark ver\\. .*$/, '')})")

    def version_in(self, p):
        p.until("!!document.querySelector('#profile-menu [data-kind=help] .hver')", "the version arrived")

    # Export to Word
    def test_profile_menu_no_word_1281(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.assertNotIn("Export to Word", self.menu(p))
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu [data-kind=word-export]').length"), 0)
            self.assertEqual(self.menu(p), [WHO] + ITEMS[:5] + ITEMS[5:])
        src = ROOT / "src" / "clark" / "page" / "src" / "edit" / "Data.jsx"
        self.assertIn("data-word-export", src.read_text(encoding="utf-8"), "Settings > Data still has its Export to Word button")

    # Row 1627 (the owner 25-11): the Appearance pill left the Classic menu (it was this row's AP3-AP6); Cards keeps its group (frozen, the owner 19-11)
    def test_classic_menu_has_no_appearance_and_one_separator_1627(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for w, near in ((1400, 0), (900, 1)):      # item 1177: at 900 'Go to or do' is an entry too (asking is off here)
                p.width(w)
                self.open_menu(p)
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu .ap, #profile-menu .pr, #profile-menu [role=group], #profile-menu [role=menuitemradio], #profile-menu [data-kind^=look-]').length"), 0)
                self.assertEqual(p.js("[].map.call(document.querySelector('#profile-menu').children, function(e){return e.getAttribute('role')}).join()"),
                                 ",".join(["menuitem"] * (1 + near + 5) + ["separator", "menuitem"]), "the actions and Settings, one separator, Help")
                self.assertEqual(self.menu(p)[near + 1:], ITEMS)
                p.key("Escape", vk=27)
                p.until("!document.querySelector('#profile-menu')", "closed")

    # The version
    def test_help_line_version_1281(self):
        for w in WIDTHS:
            with self.subTest(width=w), mock.patch.object(sv, "VERSION", VER), chrome() as cdp:      # a version no source file holds
                p = self.page(cdp)
                p.width(w, 700)
                self.open_menu(p)
                self.version_in(p)
                self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=help] .hver').textContent"), "clark ver. " + VER)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#profile-menu .hver')).fontSize"), "12px")
                self.assertEqual(p.js("(function(){var h=document.querySelector('#profile-menu [data-kind=help]'),v=h.querySelector('.hver'),a=h.getBoundingClientRect(),b=v.getBoundingClientRect();"
                                      "var t=document.createElement('i');t.remove();var c=getComputedStyle(v).color===(document.documentElement.dataset.theme==='dark'?'rgb(159, 176, 189)':'rgb(74, 85, 120)');"
                                      "return c && b.right>a.right-40 && Math.abs((b.top+b.bottom)/2-(a.top+a.bottom)/2)<4})()"), True, "muted, right-aligned, on the Help line")

    def test_C_no_version_means_no_text(self):
        for bad in ("", 123):
            with self.subTest(version=bad), mock.patch.object(sv, "VERSION", bad), chrome() as cdp:
                p = self.page(cdp)
                self.open_menu(p)
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu .hver').length"), 0)
                self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=help]').textContent"), "Help")

    def test_C_a_long_version_neither_wraps_nor_overflows(self):
        for w in (900,):
            with self.subTest(width=w), mock.patch.object(sv, "VERSION", "13.0.0-rc.1+dev.20261119.0123456789abcdef0123456789abcdef"), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 800)
                self.open_menu(p)
                self.version_in(p)
                got = p.js("(function(){var m=document.querySelector('#profile-menu'),h=m.querySelector('[data-kind=help]'),v=h.querySelector('.hver'),a=h.getBoundingClientRect(),b=v.getBoundingClientRect();"
                           "return {inside:b.right<=a.right+0.5&&b.left>=a.left,fits:m.scrollWidth<=m.clientWidth,one:b.height<30,ell:getComputedStyle(v).textOverflow}})()")
                self.assertEqual(got, {"inside": True, "fits": True, "one": True, "ell": "ellipsis"})

    def test_C_the_version_is_read_from_health_without_a_cache_and_asked_again_after_a_failure(self):
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        src = (ROOT / "src" / "clark" / "page" / "src" / "stores" / "version.js").read_text(encoding="utf-8")
        src = src.replace('import { signal } from "@preact/signals";', "const signal = (v) => ({ value: v });")
        body = src + """
const out = [], seen = [];
let calls = 0;
const step = async (f) => { calls++; globalThis.fetch = async (u, o) => { seen.push([u, o && o.cache]); return f(); }; await loadVersion(); out.push([calls, version.value]); };
await step(() => { throw new Error("down"); });
await step(() => ({ json: async () => ({ version: 5 }) }));
await step(() => ({ json: async () => ({}) }));
await step(() => ({ json: async () => ({ version: "1.2.3" }) }));
let fetched = 0; globalThis.fetch = async () => { fetched++; return { json: async () => ({ version: "9" }) }; };
await loadVersion();
out.push(["after", version.value, fetched], seen.every((s) => s[0] === "/health" && s[1] === "no-store"));
console.log(JSON.stringify(out));
"""
        done = subprocess.run([node, "--input-type=module", "-e", body], capture_output=True, text=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(json.loads(done.stdout), [[1, ""], [2, ""], [3, ""], [4, "1.2.3"], ["after", "1.2.3", 0], True])


class CardsStaysAsItWas(Base):
    """The default page is Cards: its menu keeps three rows with a tick, Export to Word, no pill and no version."""
    def setUp(self):
        self.rig = Rig(self, saved=True)

    def test_profile_menu_cards_unchanged_1281(self):
        with mock.patch.object(sv, "VERSION", VER), chrome() as cdp:
            p = self.page(cdp)
            self.assertFalse(p.js("!!document.getElementById('theme')"))
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu')", "the menu opened")
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu .ap, #profile-menu .pr, #profile-menu .hver').length"), 0)
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu [data-kind=word-export]').length"), 1)
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu [role=menuitemradio]').length"), 3)
            self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=help]').textContent"), "Help")


if __name__ == "__main__":
    unittest.main()
