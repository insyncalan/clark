"""#193: the single-key shortcuts switch is on by default, is remembered in the browser, and is read live. The letter keys
themselves are checked in the page's own browser tests. Run: python3 dev/run_tests.py test_single_keys"""
import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

import _paths  # noqa: F401
from _clean_html import wait_for
from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402
from test_server import chrome  # noqa: E402
from test_report_editor import Base  # noqa: E402

STORE = ROOT / "src" / "clark" / "page" / "src" / "stores"


class Store:
    """stores/keyPrefs.js bundled alone as `KP`, in a Chrome tab."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        out = tmp / "kp.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=KP", "--target=es2020", "--tsconfig-raw={}",
                            *build_page.preact_flags(), str(STORE / "keyPrefs.js"), f"--outfile={out}"],
                           cwd=STORE, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        (tmp / "page.html").write_text("<!doctype html><meta charset=utf-8><body><script src=kp.js></script></body>", encoding="utf-8")
        self.chrome = chrome()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof KP === 'object'", self.sid) is True, 60), "the script did not load"
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        return self.cdp.js(expr, self.sid)

    def reload(self):
        self.cdp.call("Page.reload", {}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof KP === 'object'", self.sid) is True, 60), "the script did not reload"


class Switch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = Store().__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.page.__exit__(None, None, None)

    def setUp(self):
        self.page.ev("localStorage.removeItem('clark.single-keys')")
        self.page.reload()                          # the switch is read when the page starts: each test starts it fresh

    def test_on_by_default(self):
        self.assertIs(self.page.ev("KP.singleKeys.value"), True)

    def test_off_is_remembered_and_read_live(self):
        self.page.ev("KP.setSingleKeys(false)")
        self.assertIs(self.page.ev("KP.singleKeys.value"), False)
        self.assertEqual(self.page.ev("localStorage.getItem('clark.single-keys')"), "off")

    def test_back_on_is_remembered(self):
        self.page.ev("KP.setSingleKeys(false)")
        self.page.ev("KP.setSingleKeys(true)")
        self.assertEqual(self.page.ev("localStorage.getItem('clark.single-keys')"), "on")


CTRL, META = 2, 4                                   # Input.dispatchKeyEvent modifiers
EDIT = "document.querySelector('#report').dataset.mode === 'edit'"
VIEW = "document.querySelector('#report').dataset.mode === 'view'"
TITLES = "[...document.querySelectorAll('.mode')].map(b => b.title + '|' + b.getAttribute('aria-keyshortcuts'))"


class PageKeys(Base):
    """The real page, with fictional demo data: V and E on, off, and back on, at both widths, light and dark."""

    def letter(self, p, key, modifiers=0):
        p.key(key, modifiers, code="Key" + key.upper(), vk=ord(key.upper()))

    def settings_box(self, p):
        p.js("clarkPage.show('settings')")
        p.until("!!document.querySelector('fieldset.keys input[type=checkbox]')", "Settings has the switch")

    def flip(self, p, on):
        """Use the real checkbox in Settings, then return to the Dashboard in View."""
        self.settings_box(p)
        p.js("document.querySelector('fieldset.keys input[type=checkbox]').click()")
        self.assertEqual(p.js("document.querySelector('fieldset.keys input[type=checkbox]').checked"), on)
        p.js("clarkPage.show('dashboard')")
        p.until("!!document.querySelector('#report')", "back on the Dashboard")
        p.js("document.activeElement.blur()")

    def test_letters_work_when_on_do_nothing_when_off_and_work_again_with_no_reload(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("window.marker = 'same page'")
            for scheme in ("light", "dark"):
                cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    p.until(f"window.innerWidth === {w}", "resized")
                    where = f"{scheme} {w}"
                    p.js("document.activeElement.blur()")
                    self.assertEqual(p.js(TITLES), ["View (V)|V", "Edit (E)|E"], where)
                    for key, test in (("e", EDIT), ("v", VIEW), ("E", EDIT), ("V", VIEW)):
                        self.letter(p, key)
                        p.until(test, f"{where}: {key} does its job when on")
                    self.flip(p, False)
                    self.assertEqual(p.js(TITLES), ["View|null", "Edit|null"], f"{where}: no letter in the tooltips when off")
                    for key in ("e", "E", "v", "V"):
                        self.letter(p, key)
                    time.sleep(0.3)
                    self.assertTrue(p.js(VIEW), f"{where}: E does nothing when off")
                    p.js("document.querySelector('.mode[data-mode=edit]').click()")
                    p.until(EDIT, f"{where}: the button still works when off")
                    p.js("document.activeElement.blur()")
                    for key in ("v", "V"):
                        self.letter(p, key)
                    time.sleep(0.3)
                    self.assertTrue(p.js(EDIT), f"{where}: V does nothing when off")
                    p.view()
                    self.flip(p, True)                                                # read live: no reload
                    self.assertEqual(p.js(TITLES), ["View (V)|V", "Edit (E)|E"], f"{where}: the letter is back")
                    self.letter(p, "e")
                    p.until(EDIT, f"{where}: E works again, no reload")
                    p.view()
            self.assertEqual(p.js("window.marker"), "same page", "no reload at any point")
            self.assertEqual(self.sent, [], "the keys ask the server for nothing")

    def test_arrows_enter_esc_space_and_ctrl_or_cmd_combinations_are_untouched(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.flip(p, False)
            for mod in (CTRL, META, CTRL | META):                                  # a held Cmd or Ctrl never reaches V or E, on or off
                self.letter(p, "e", mod)
            self.assertTrue(p.js(VIEW))
            # Esc and the question mark: Help opens and closes; Space is not taken from a button
            p.key("?", code="Slash", vk=191)
            p.until("!!document.querySelector('#help')", "? still opens Help when off")
            p.key("/", code="Slash", vk=191)
            time.sleep(0.2)
            self.assertNotEqual(p.js("document.activeElement.id"), "hpQ", "'/' does not go to the search box when off")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('#help') && !!document.querySelector('#report')", "Esc still closes Help when off")
            # the arrows in a menu, and Enter on a milestone
            p.edit()
            p.js("document.querySelector('[data-options]').click()")
            p.until("!!document.querySelector('.menu')", "a section's menu opened")
            p.js("document.querySelector('.menu [role=menuitem]').focus()")
            first = p.js("document.activeElement.textContent")
            p.key("ArrowDown", code="ArrowDown", vk=40)
            self.assertNotEqual(p.js("document.activeElement.textContent"), first, "the arrow moves through the menu when off")
            p.key("ArrowUp", code="ArrowUp", vk=38)
            self.assertEqual(p.js("document.activeElement.textContent"), first, "and back up")
            p.key("Escape", code="Escape", vk=27)
            p.until("!document.querySelector('.menu')", "Esc closes the menu when off")
            p.view()
            p.js("clarkPage.show('milestones')")
            p.until("!!document.querySelector('.msl-cells[role=button]')", "the milestones list")
            p.js("document.querySelector('.msl-cells[role=button]').focus()")
            p.key("Enter", code="Enter", vk=13)
            p.until("!!clarkPage.peek()", "Enter opens the peek when off")
            p.js("clarkPage.closePeek()")                                           # the peek has no Esc of its own yet
            p.until("!clarkPage.peek()", "the peek closed")
            # Space on a button, Mod+Enter keeps an edit
            p.js("clarkPage.show('dashboard')")
            p.until("!!document.querySelector('#report')", "the Dashboard")
            p.edit()
            p.js("var t = document.querySelector('[data-title]'); t.focus(); window.title0 = t.textContent")
            p.type(" more")
            p.key("Enter", CTRL, code="Enter", vk=13)
            p.until("document.activeElement !== document.querySelector('[data-title]')", "Ctrl+Enter keeps the edit and leaves the title when off")
            p.view()
            p.js("document.querySelector('.mode[data-mode=edit]').focus()")
            p.key(" ", code="Space", vk=32)
            p.until(EDIT, "Space presses a focused button when off")

    def test_help_says_which_keys_the_switch_covers(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.key("?", code="Slash", vk=191)
            p.until("!!document.querySelector('#help')", "Help opened")
            p.js("document.querySelector('#hpTab-reference').click()")
            p.until("document.querySelectorAll('#hp-ref-keys .hp-keys tbody tr').length > 0", "the key table drew")
            rows = p.js("[...document.querySelectorAll('#hp-ref-keys .hp-keys tbody tr')].map(r => r.textContent)")
            hit = [r for r in rows if "Single-key shortcuts" in r]
            self.assertEqual(len(hit), 2, "the V row and the E row each say it")
            self.assertFalse([r for r in rows if r.startswith("?") and "Single-key" in r], "? is not a letter key: it is not covered")
            self.assertTrue(any(r.startswith("V") for r in hit) and any(r.startswith("E") for r in hit))
            self.assertTrue(all("Settings › Personal" in r for r in hit))

    def test_the_setting_survives_a_reload(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.flip(p, False)
            self.assertEqual(p.js("localStorage.getItem('clark.single-keys')"), "off")
            p.reload()
            p.js("document.activeElement.blur()")
            self.assertEqual(p.js(TITLES), ["View|null", "Edit|null"], "still off after a reload")
            self.letter(p, "e")
            time.sleep(0.3)
            self.assertTrue(p.js(VIEW), "E does nothing after a reload")
            self.settings_box(p)
            self.assertIs(p.js("document.querySelector('fieldset.keys input[type=checkbox]').checked"), False, "Settings shows it off")


if __name__ == "__main__":
    unittest.main()
