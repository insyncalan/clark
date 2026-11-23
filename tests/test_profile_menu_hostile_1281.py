"""Row 1281 (PR 2037), hostile pass on the NEW logic only: stores/version.js (loadVersion), Menu.jsx (groupedItems row flag, pillRadio keys,
the aside span) and ProfileMenu.jsx (Classic-only items, pill, version on the Help line). Fictional data only.

Run: python3 dev/run_tests.py test_profile_menu_hostile_1281
"""
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, "tests")
import _testpage as testpage
from test_publish_dialog import Base
from test_publish_route import Rig
from test_server import chrome
from clark import page, server as sv, theme

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src" / "clark" / "page" / "src"


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


def node_run(body):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    done = subprocess.run([node, "--input-type=module"], input=body, capture_output=True, text=True, timeout=60)
    if done.returncode:
        raise AssertionError(done.stderr)
    return json.loads(done.stdout)


def func_source(name):
    """The source text of one top-level function of Menu.jsx (up to its closing brace at column 0)."""
    text = (SRC / "components" / "Menu.jsx").read_text(encoding="utf-8")
    m = re.search(r"^(export )?function %s\(.*?^}\n" % name, text, re.S | re.M)
    assert m, name
    return m.group(0).replace("export ", "", 1)


def version_src():
    return (SRC / "stores" / "version.js").read_text(encoding="utf-8").replace('import { signal } from "@preact/signals";', "const signal = (v) => ({ value: v });")


class VersionStore(unittest.TestCase):
    """stores/version.js with a stubbed fetch: every odd /health answer leaves version "" or a clean string, never throws."""

    def one(self, case):
        body = version_src() + """
const c = %s;
globalThis.fetch = async () => { if (c.kind === "throw") throw new Error("x"); if (c.kind === "undef") return undefined;
  return { ok: c.ok !== false, json: async () => { if (c.kind === "badjson") throw new SyntaxError("bad"); return c.body === "HUGE" ? { version: "v".repeat(2000000) } : c.body; } }; };
let err = null;
try { await loadVersion(); } catch (e) { err = String(e); }
const v = version.value;
console.log(JSON.stringify([err, typeof v, v.length > 100 ? "long:" + v.length : v]));
""" % json.dumps(case)
        return node_run(body)

    def test_each_odd_health_answer(self):
        cases = [
            ({"kind": "ok", "body": None}, ""), ({"kind": "ok", "body": []}, ""), ({"kind": "ok", "body": "1.2.3"}, ""), ({"kind": "ok", "body": 7}, ""),
            ({"kind": "ok", "body": {"version": None}}, ""), ({"kind": "ok", "body": {"version": ["1"]}}, ""), ({"kind": "ok", "body": {"version": {"a": 1}}}, ""),
            ({"kind": "ok", "body": {"version": True}}, ""), ({"kind": "ok", "body": {"version": "1\u00002"}}, "1\u00002"),
            ({"kind": "ok", "body": {"version": "<img src=x onerror=alert(1)>"}}, "<img src=x onerror=alert(1)>"),
            ({"kind": "ok", "body": {"version": "‮1.2"}}, "‮1.2"), ({"kind": "ok", "body": {"version": "\U0001f600" * 5}}, "\U0001f600" * 5),
            ({"kind": "badjson"}, ""), ({"kind": "throw"}, ""), ({"kind": "undef"}, ""),
        ]
        for case, want in cases:
            with self.subTest(case=str(case)[:60]):
                got = self.one(case)
                self.assertIsNone(got[0], "never throws out of loadVersion")
                self.assertEqual(got[2], want)

    def test_a_failed_http_status_with_a_version_body_is_not_shown(self):
        """/health answered 500 or 404 with a JSON body that carries a version string (a proxy or error page): r.ok is checked."""
        got = self.one({"kind": "ok", "ok": False, "body": {"version": "evil-proxy-9.9"}})
        self.assertEqual(got[2], "", "a non-2xx answer must not show a version")

    def test_health_is_read_without_a_cache_and_a_bad_body_is_asked_again(self):
        got = node_run(version_src() + """
const seen = [], out = [];
const step = async (f) => { globalThis.fetch = async (u, o) => { seen.push([u, o && o.cache]); return f(); }; await loadVersion(); out.push(version.value); };
await step(() => ({ json: async () => ({}) }));
await step(() => ({ json: async () => ({ version: "8.1" }) }));
await step(() => ({ json: async () => ({ version: "9.9" }) }));
console.log(JSON.stringify([out, seen]));""")
        self.assertEqual(got, [["", "8.1", "8.1"], [["/health", "no-store"], ["/health", "no-store"]]])

    def test_a_null_json_body_is_asked_again(self):
        got = node_run(version_src() + """
let n = 0; globalThis.fetch = async () => { n++; return { json: async () => (n === 1 ? null : { version: "1.0" }) }; };
await loadVersion(); const a = version.value; await loadVersion(); console.log(JSON.stringify([a, version.value, n]));""")
        self.assertEqual(got, ["", "1.0", 2])

    def test_huge_version_string_is_kept_whole_and_does_not_throw(self):
        self.assertEqual(self.one({"kind": "ok", "body": "HUGE"}), [None, "string", "long:2000000"])

    def test_concurrent_calls_fetch_once(self):
        got = node_run(version_src() + """
let n = 0; globalThis.fetch = async () => { n++; await new Promise((r) => setTimeout(r, 20)); return { json: async () => ({ version: "2.0" }) }; };
await Promise.all(Array.from({ length: 50 }, () => loadVersion()));
console.log(JSON.stringify([n, version.value]));""")
        self.assertEqual(got, [1, "2.0"])

    def test_failure_with_calls_in_flight_does_not_loop(self):
        got = node_run(version_src() + """
let n = 0; globalThis.fetch = async () => { n++; await new Promise((r) => setTimeout(r, 10)); throw new Error("down"); };
await Promise.all([loadVersion(), loadVersion(), loadVersion()]);
const a = n; await loadVersion(); console.log(JSON.stringify([a, n, version.value]));""")
        self.assertEqual(got, [1, 2, ""], "one fetch for the burst, one more for the later call, nothing stored")



class MenuPure(unittest.TestCase):
    """groupedItems, cut out of Menu.jsx and run with plain objects."""

    def grouped(self, items, menu_id="m"):
        body = func_source("groupedItems") + "\nconsole.log(JSON.stringify(groupedItems(%s, %s)));" % (json.dumps(items), json.dumps(menu_id))
        return node_run(body)

    def test_row_flag_is_a_boolean_for_any_odd_value(self):
        for v in (True, 1, "x", {}, [], 0, "", None, False):
            with self.subTest(row=repr(v)):
                out = self.grouped([{"id": "l", "lab": "A", "row": v}, {"id": "a", "checked": False}])
                self.assertIs(out[0]["row"], bool(v) or v in ({}, []))

    def test_label_without_radios_is_not_a_group(self):
        out = self.grouped([{"id": "l", "lab": "A", "row": True}, {"id": "x", "name": "n"}])
        self.assertTrue(all("item" in n for n in out))
        self.assertEqual(self.grouped([]), [])
        self.assertEqual(self.grouped([{"id": "l", "lab": "A", "row": True}]), [{"item": {"id": "l", "lab": "A", "row": True}}])

    def test_two_labels_in_a_row_and_radios_after_a_separator(self):
        out = self.grouped([{"id": "l1", "lab": "A", "row": True}, {"id": "l2", "lab": "B"}, {"id": "a", "checked": True}, {"id": "s", "sep": True}, {"id": "b", "checked": False}])
        self.assertEqual([("group" if "group" in n else "item") for n in out], ["item", "group", "item", "item"])
        self.assertIs(out[1]["row"], False, "the row flag belongs to the label that opens the group")

    def test_many_radios_and_odd_ids(self):
        items = [{"id": "l\u0000<>‮", "lab": "\U0001f600", "row": True}] + [{"id": "r%d" % i, "checked": i % 2 == 0} for i in range(5000)]
        out = self.grouped(items, "m\u0000")
        self.assertEqual(len(out), 1)
        self.assertEqual(len(out[0]["items"]), 5000)
        self.assertEqual(out[0]["labelId"], "m\u0000-l\u0000<>‮")

    def test_checked_null_counts_as_a_radio_and_undefined_does_not(self):
        out = self.grouped([{"id": "l", "lab": "A", "row": True}, {"id": "a", "checked": None}, {"id": "b"}])
        self.assertEqual(len(out[0]["items"]), 1)


class Hostile(Base):
    def setUp(self):
        self.rig = Rig(self, saved=True, page_html=classic_html)

    def open_menu(self, p):
        p.js("document.querySelector('#profile-btn').focus()")
        p.until("(() => { if (document.querySelector('#profile-menu')) return true; "
                "if (Date.now() - (window.__menuTried || 0) > 1000) { window.__menuTried = Date.now(); document.querySelector('#profile-btn').click(); } "
                "return !!document.querySelector('#profile-menu'); })()", "the menu opened")

    def active(self, p):
        return p.js("document.activeElement.textContent.replace('✓', '')")

    def chosen(self, p):
        return p.js("[...document.querySelectorAll('#profile-menu .pr')].filter(function(e){return e.getAttribute('aria-checked')==='true'}).map(function(e){return e.textContent}).join()")

    def to_pill(self, p):
        for _ in range(8):
            if p.js("document.activeElement.classList.contains('pr')"):
                return
            p.key("ArrowDown", vk=40)
        self.fail("the keys never reached the pill")

    def test_hostile_version_texts_are_text_only(self):
        for bad in ("<img src=x onerror=window.__x=1>", "1.2\u0000.3", "‮3.2.1", "a" * 3000, "\U0001f600́" * 40, "&amp;<b>x</b>"):
            with self.subTest(version=bad[:20]), mock.patch.object(sv, "VERSION", bad), chrome() as cdp:
                p = self.page(cdp)
                p.width(320, 700)
                self.open_menu(p)
                p.until("!!document.querySelector('#profile-menu .hver')", "the version arrived")
                self.assertEqual(p.js("document.querySelectorAll('#profile-menu img, #profile-menu b + b, #profile-menu .hver b').length"), 0, "no markup from the version")
                self.assertIsNone(p.js("window.__x || null"))
                self.assertTrue(p.js("(function(){var m=document.querySelector('#profile-menu'); return m.scrollWidth<=m.clientWidth+1 && m.getBoundingClientRect().right<=innerWidth+1})()"),
                                "the menu stays inside a 320 px window")

    def test_non_string_health_versions_show_nothing(self):
        for bad in (None, ["1"], {"a": 1}, 1.5, True):
            with self.subTest(version=str(bad)), mock.patch.object(sv, "VERSION", bad), chrome() as cdp:
                p = self.page(cdp)
                self.open_menu(p)
                p.js("new Promise(r => setTimeout(r, 400))")
                self.assertEqual(p.js("document.querySelector('#profile-menu [data-kind=help]').textContent"), "Help")

    def test_health_is_asked_once_however_often_the_menu_opens(self):
        with mock.patch.object(sv, "VERSION", "4.5.6"), chrome() as cdp:
            p = self.page(cdp)
            for _ in range(4):
                self.open_menu(p)
                p.key("Escape", vk=27)
                p.until("!document.querySelector('#profile-menu')", "closed")
            n = p.js("performance.getEntriesByType('resource').filter(function(e){return e.name.endsWith('/health')}).length")
            self.assertEqual(n, 1)

    def test_key_mashing_in_the_pill_keeps_one_choice_one_stop_and_the_same_storage(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.to_pill(p)
            order = ["System", "Light", "Dark"]
            for i in range(1, 31):
                p.key("ArrowRight", vk=39)
                self.assertEqual((self.active(p), self.chosen(p)), (order[i % 3], order[i % 3]))
            for _ in range(7):
                p.key("ArrowLeft", vk=37)
            self.assertEqual((self.chosen(p), self.active(p)), ("Dark", "Dark"), "30 rights then 7 lefts wrap to Dark")
            self.assertEqual(p.js("[...document.querySelectorAll('#profile-menu .pr')].filter(function(e){return e.tabIndex===0}).length"), 1, "exactly one tab stop")
            self.assertEqual(p.js("document.querySelector('#profile-menu .pr[tabindex=\"0\"]').getAttribute('aria-checked')"), "true", "the stop is the chosen radio")
            self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), self.chosen(p).lower())

    def test_home_and_end_in_the_pill_choose_the_ends_and_keep_the_menu_and_page_still(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.to_pill(p)
            y = p.js("scrollY")
            for key, vk, want in (("End", 35, "Dark"), ("Home", 36, "System"), ("End", 35, "Dark"), ("End", 35, "Dark"), ("Home", 36, "System")):
                p.key(key, vk=vk)
                self.assertEqual((self.active(p), self.chosen(p)), (want, want), key)
            self.assertTrue(p.js("!!document.querySelector('#profile-menu')"), "the menu stays open")
            self.assertEqual(p.js("scrollY"), y, "the page did not scroll")

    def test_classic_menu_entries_and_pill_markup_exact(self):
        with mock.patch.object(sv, "VERSION", "6.5.4"), chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.until("!!document.querySelector('#profile-menu .hver')", "version")
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return e.getAttribute('data-kind')}).join()"),
                             "who,preview,export,publish,published,settings,help")
            self.assertEqual(p.js("document.querySelector('#profile-menu .hver').textContent"), "clark ver. 6.5.4")
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#profile-menu .pr'), function(e){return e.getAttribute('role')}).join()"), "menuitemradio,menuitemradio,menuitemradio")
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu .pr svg, #profile-menu .pr .mi').length"), 0)
            self.assertEqual(p.js("(function(){var g=document.querySelector('#profile-menu .ap'),l=document.getElementById(g.getAttribute('aria-labelledby'));return l&&l.textContent})()"), "Appearance")

    def test_a_click_on_a_pill_radio_chooses_it_and_closes_the_menu(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelector('#profile-menu .pr[data-kind=look-light]').click()")
            p.until("!document.querySelector('#profile-menu')", "closed")
            self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), "light")

    def test_pill_up_down_leave_and_return_to_the_chosen_radio(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            p.js("document.querySelector('#profile-menu [data-kind=look-dark]').click()")
            p.until("!document.querySelector('#profile-menu')", "closed")
            self.open_menu(p)
            self.to_pill(p)
            self.assertEqual(self.active(p), "Dark", "the keys stop on the chosen radio, not the first")
            p.key("ArrowDown", vk=40)
            p.key("ArrowUp", vk=38)
            self.assertEqual(self.active(p), "Dark")
            self.assertEqual(p.js("localStorage.getItem('clark.appearance')"), "dark", "Up and Down alone choose nothing")

    def test_escape_in_the_pill_closes_and_hands_focus_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.to_pill(p)
            p.key("ArrowRight", vk=39)
            p.key("Escape", vk=27)
            p.until("!document.querySelector('#profile-menu')", "closed")
            self.assertEqual(p.js("document.activeElement.id"), "profile-btn")

    def test_stray_keys_do_not_choose_a_radio(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_menu(p)
            self.to_pill(p)
            for k, vk in (("a", 65), ("x", 88), ("PageDown", 34), ("ArrowUp", 38)):
                p.key(k, vk=vk)
            self.assertIsNone(p.js("localStorage.getItem('clark.appearance')"))


    def test_word_export_hook_twice_without_error(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.assertEqual(p.js("typeof window.clarkPage.openWordExport"), "function")
            p.js("window.__errs = []; addEventListener('error', function(e){window.__errs.push(String(e.message))}); window.clarkPage.openWordExport(); window.clarkPage.openWordExport(); 1")
            p.js("new Promise(r => setTimeout(r, 300))")
            self.assertEqual(p.js("window.__errs"), [])
            self.assertEqual(p.js("document.querySelectorAll('#word-export-dialog').length"), 1, "the box is open, once")

    def test_modified_arrows_are_not_taken_by_the_pill(self):
        """Alt+Left is the browser's Back, Ctrl+Home the page's top: a pill that chooses on them takes keys that are not its own."""
        for name, key, vk, mod in (("alt-left", "ArrowLeft", 37, 1), ("ctrl-right", "ArrowRight", 39, 2), ("meta-left", "ArrowLeft", 37, 4), ("ctrl-home", "Home", 36, 2), ("ctrl-end", "End", 35, 2)):
            with self.subTest(key=name), chrome() as cdp:
                p = self.page(cdp)
                self.open_menu(p)
                self.to_pill(p)
                for kind in ("keyDown", "keyUp"):
                    cdp.call("Input.dispatchKeyEvent", {"type": kind, "key": key, "code": key, "windowsVirtualKeyCode": vk, "modifiers": mod}, p.sid)
                self.assertIsNone(p.js("localStorage.getItem('clark.appearance')"), name + " chose a radio")


class CardsHostile(Base):
    def setUp(self):
        self.rig = Rig(self, saved=True)

    def test_cards_never_asks_health_for_a_version_or_draws_a_pill(self):
        with mock.patch.object(sv, "VERSION", "<b>1</b>"), chrome() as cdp:
            p = self.page(cdp)
            p.js("document.querySelector('#profile-btn').click()")
            p.until("!!document.querySelector('#profile-menu')", "open")
            p.js("new Promise(r => setTimeout(r, 400))")
            self.assertEqual(p.js("document.querySelectorAll('#profile-menu .hver, #profile-menu .ap, #profile-menu .pr').length"), 0)
            self.assertEqual(p.js("[].map.call(document.querySelectorAll('#profile-menu [role=menuitem]'), function(e){return e.getAttribute('data-kind')}).join()"),
                             "who,publish,preview,export,word-export,published,settings,help")
            n = p.js("(performance.getEntriesByType('resource') || []).filter(function(e){return e.name.endsWith('/health')}).length")
            self.assertEqual(n, 0, "Cards does not read /health for the menu")


if __name__ == "__main__":
    unittest.main()
