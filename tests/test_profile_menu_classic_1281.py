"""Row 1281, Classic theme only (Cards, frozen, keeps its menu as it is): the profile menu has no Export to Word, Appearance is one pill line
(System | Light | Dark, a group of three menuitemradio, arrows choose, visible focus, light and dark, 1400 and 900), and the Help line carries
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
ORDER = [WHO] + ITEMS[:5] + ["System"] + ITEMS[5:]      # the keys reach the pill as one stop, its chosen radio (System by default)
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

    def active(self, p):
        return p.js("document.activeElement.textContent.replace('✓', '')")

    def chosen(self, p):
        return p.js("[...document.querySelectorAll('#profile-menu .pr')].filter(function(e){return e.getAttribute('aria-checked')==='true'}).map(function(e){return e.textContent}).join()")

    def version_in(self, p):
        p.until("!!document.querySelector('#profile-menu [data-kind=help] .hver')", "the version arrived")

    # Export to Word
    def test_C_export_to_word_is_not_in_the_menu_and_stays_in_settings_data(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.assertNotIn("Export to Word", self.menu(p))
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu [data-kind=word-export]').length"), 0)
            self.assertEqual(self.menu(p), [WHO] + ITEMS[:5] + ITEMS[5:])
        src = ROOT / "src" / "clark" / "page" / "src" / "edit" / "Data.jsx"
        self.assertIn("data-word-export", src.read_text(encoding="utf-8"), "Settings > Data still has its Export to Word button")

    # The pill
    def test_C_the_pill_is_one_line_group_of_three_radios_with_the_mockup_values(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                self.open_menu(p)
                self.assertEqual(p.js("[...document.querySelectorAll('#profile-menu .pr')].map(function(e){return e.getAttribute('role')+':'+e.textContent}).join()"),
                                 "menuitemradio:System,menuitemradio:Light,menuitemradio:Dark")
                self.assertEqual(p.js("document.querySelector('#profile-menu .ap').getAttribute('role')"), "group")
                self.assertEqual(p.js("new Set([...document.querySelectorAll('#profile-menu .pr')].map(function(e){return Math.round(e.getBoundingClientRect().top)})).size"), 1, "one line")
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu [data-kind^=look-] .ck, #profile-menu [data-kind^=look-] svg').length"), 0, "no tick, no icon")
                got = p.js("(function(){var q=function(s){return getComputedStyle(document.querySelector('#profile-menu '+s))};"
                           "var w=[...document.querySelectorAll('#profile-menu .pr')].map(function(e){return Math.round(e.getBoundingClientRect().width)});"
                           "return {lab:q('.ap .lab').fontSize,r:q('.ptrack').borderRadius,pad:q('.ptrack').padding,gap:q('.ptrack').columnGap,cell:q('.pr').padding,fs:q('.pr').fontSize,"
                           "rad:q('.pr').borderRadius,on:q('.pr[aria-checked=true]').fontWeight,eq:Math.max.apply(null,w)-Math.min.apply(null,w)<=1?1:w.join()}})()")
                self.assertEqual(got, {"lab": "13px", "r": "999px", "pad": "3px", "gap": "2px", "cell": "6px 4px", "fs": "14px", "rad": "999px", "on": "600", "eq": 1})

    def test_C_the_chosen_cell_is_a_raised_surface_pill_with_accent_text_in_light_and_dark(self):
        for w in WIDTHS:
            with self.subTest(width=w), chrome() as cdp:
                p = self.page(cdp)
                p.width(w, 700)
                for kind in ("light", "dark"):
                    self.open_menu(p)
                    p.js("document.querySelector('#profile-menu [data-kind=look-%s]').click()" % kind)
                    p.until("(document.documentElement.dataset.theme || 'light') === '%s'" % kind, kind)
                    self.open_menu(p)
                    got = p.js("(function(){var tok=function(n,prop){var t=document.createElement('i');t.style[prop]='var('+n+')';document.body.appendChild(t);var v=getComputedStyle(t)[prop];t.remove();return v};"
                               "var on=getComputedStyle(document.querySelector('#profile-menu .pr[aria-checked=true]')),tr=getComputedStyle(document.querySelector('#profile-menu .ptrack'));"
                               "return {bg:on.backgroundColor===tok('--surface','backgroundColor'),fg:on.color,track:tr.backgroundColor,ap:getComputedStyle(document.querySelector('#profile-menu .ap')).padding,"
                               "shadow:on.boxShadow!=='none'}})()")
                    # the ticket's values (1281 AP3, AP4, AP5): track #eceff6 (dark #1c3040), chosen text #4f35c9 (dark #a99bff), label block padding 8px 20px 6px; the ticket values win (ruling 22-11)
                    want = {"light": ("rgb(236, 239, 246)", "rgb(79, 53, 201)"), "dark": ("rgb(28, 48, 64)", "rgb(169, 155, 255)")}[kind]
                    self.assertEqual(got, {"bg": True, "fg": want[1], "track": want[0], "ap": "8px 20px 6px", "shadow": True}, kind)

    def test_C_the_keys_reach_the_pill_as_one_stop_and_left_right_choose(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.assertEqual(p.js("[...document.querySelectorAll('#profile-menu .pr')].map(function(e){return e.tabIndex}).join()"), "0,-1,-1")
            self.assertEqual(self.active(p), WHO)
            for want in ORDER[1:]:
                p.key("ArrowDown", vk=40)
                self.assertEqual(self.active(p), want)
            p.key("ArrowDown", vk=40)
            self.assertEqual(self.active(p), WHO, "it wraps")
            p.key("End", vk=35)
            self.assertTrue(self.active(p).startswith("Help"))
            p.key("Home", vk=36)
            self.assertEqual(self.active(p), WHO)
            for _ in range(6):
                p.key("ArrowDown", vk=40)
                if self.active(p) == "System":
                    break
            for key, vk, want in (("ArrowRight", 39, "Light"), ("ArrowRight", 39, "Dark"), ("ArrowRight", 39, "System"), ("ArrowLeft", 37, "Dark")):
                p.key(key, vk=vk)
                self.assertEqual((self.active(p), self.chosen(p)), (want, want), key)
            self.assertTrue(p.js("!!document.querySelector('#profile-menu')"), "choosing by arrow leaves the menu open")
            self.assertEqual(p.js("document.documentElement.dataset.theme"), "dark")
            self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), "dark", "the same storage as before")
            self.assertEqual(p.js("document.activeElement.matches(':focus-visible')"), True, "the focus ring shows")
            self.assertNotEqual(p.js("getComputedStyle(document.activeElement).outlineStyle"), "none")
            p.key("Home", vk=36)
            self.assertEqual(self.active(p), WHO, "Home from the pill goes to the first line")

    def test_C_a_click_chooses_and_closes_the_menu(self):
        with chrome() as cdp:
            p = self.page(cdp)
            for kind, theme_ in (("dark", "dark"), ("light", None), ("system", None)):
                self.open_menu(p)
                p.js("document.querySelector('#profile-menu [data-kind=look-%s]').click()" % kind)
                p.until("!document.querySelector('#profile-menu')", "a click closes the menu")
                self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), kind)
                if theme_:
                    self.assertEqual(p.js("document.documentElement.dataset.theme"), theme_)

    # The version
    def test_C_the_help_line_carries_clark_ver_from_health_at_its_right_end(self):
        for w in WIDTHS:
            with self.subTest(width=w), mock.patch.object(sv, "VERSION", VER), chrome() as cdp:      # a version no source file holds
                p = self.page(cdp)
                p.width(w, 700)
                self.open_menu(p)
                self.version_in(p)
                self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=help] .hver').textContent"), "clark ver. " + VER)
                self.assertEqual(p.js("getComputedStyle(document.querySelector('#profile-menu .hver')).fontSize"), "12px")
                self.assertEqual(p.js("(function(){var h=document.querySelector('#profile-menu [data-kind=help]'),v=h.querySelector('.hver'),a=h.getBoundingClientRect(),b=v.getBoundingClientRect();"
                                      "var t=document.createElement('i');t.style.color='var(--text-muted)';h.appendChild(t);var c=getComputedStyle(t).color===getComputedStyle(v).color;t.remove();"
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

    def test_C_the_cards_menu_has_no_pill_no_version_and_keeps_export_to_word(self):
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
