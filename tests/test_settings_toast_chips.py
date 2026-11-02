"""#440 (rows 5, 14, 15): the profile toast with Undo, the sticky chip row and the marked chip on Settings.
Run: python3 dev/run_tests.py test_settings_toast_chips

Logic (no browser, node): the words after a save ("Name saved", "Email saved", both, or nothing) and which card is being read.
Browser (Chrome required: these fail, never skip, without it), at 1400 and 900 px, light and dark: saving a name shows "Name saved" with
Undo and Undo saves the old name again (read from clark's own file); likewise the email; saving what is already kept says nothing; the
chip row is sticky (it stays under the top bar after a scroll), the first chip is marked at the top, a click marks its chip, and a scroll
to a card marks that card's chip. Alias, Phone and Organisation are not here: they need new fields (guarded) and have no ruling.
"""
import json
import subprocess
import unittest

from _paths import ROOT
from test_about_you import AboutYou as _AboutYou, WIDTHS
from test_appearance import scheme
from test_server import chrome

LOGIC = ROOT / "src" / "clark" / "page" / "src" / "logic"


def node(module, expr):
    code = f"import('file://{LOGIC / module}').then(m => console.log(JSON.stringify({expr})))"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


class Logic(unittest.TestCase):
    def test_the_words_after_a_save(self):
        e = "m.savedWords({name: 'A', email: ''}, {name: 'B', email: ''})"
        self.assertEqual(node("profileToast.js", e), "Name saved")
        self.assertEqual(node("profileToast.js", "m.savedWords({name: 'A', email: ''}, {name: 'A', email: 'a@b.test'})"), "Email saved")
        self.assertEqual(node("profileToast.js", "m.savedWords({name: 'A', email: ''}, {name: 'B', email: 'a@b.test'})"), "Name and email saved")
        self.assertIsNone(node("profileToast.js", "m.savedWords({name: 'A', email: 'x'}, {name: 'A', email: 'x'})"), "nothing changed says nothing")
        self.assertEqual(node("profileToast.js", "m.savedWords({name: 'A', email: ''}, {name: '', email: ''})"), "Name saved", "emptying a name is a save")

    def test_the_card_being_read(self):
        f = "settingsSpy.js"
        self.assertEqual(node(f, "m.currentIndex([300, 900, 1500], 120)"), 0, "none has reached the edge: the first")
        self.assertEqual(node(f, "m.currentIndex([-400, 100, 900], 120)"), 1)
        self.assertEqual(node(f, "m.currentIndex([-900, -400, 100], 120)"), 2)
        self.assertEqual(node(f, "m.currentIndex([-900, -400, 120], 120)"), 2, "exactly at the edge counts")
        self.assertEqual(node(f, "m.currentIndex([], 120)"), 0)


class Browser(_AboutYou):
    def open_about(self, p, w, mode="light"):
        p.width(w)
        scheme(p, mode)
        p.js("location.hash = '#settings&p=PUB'")
        p.until("!!document.querySelector('#about-name') && !!document.querySelector('.set-nav .set-chip')", "Settings drew")

    def toast(self, p):
        return p.js("(() => { const t = document.querySelector('.toast'); return t ? t.querySelector('.toast-text').textContent : null; })()")

    def test_C_name_saved_toast_with_undo_puts_the_old_name_back(self):
        for w in WIDTHS:
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_about(p, w, mode)
                    self.type_into(p, "name", "Sam Lee")
                    p.until("document.querySelector('.toast .toast-text') && document.querySelector('.toast .toast-text').textContent === 'Name saved'", "Name saved shown")
                    self.assertEqual(self.saved().get("profile_name"), "Sam Lee")
                    p.js("document.querySelector('.toast [data-undo]').click()")
                    p.until("document.querySelector('#about-name').value === ''", "the box has the old name")
                    self.assertEqual(self.saved().get("profile_name", ""), "", "Undo saved the old name")
                    self.assertIsNone(self.toast(p), "the toast went")

    def test_C_email_saved_toast_with_undo_and_a_repeat_save_says_nothing(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.open_about(p, 1400)
            self.type_into(p, "name", "Sam Lee")
            p.until("!!document.querySelector('.toast .toast-text')", "first toast")
            p.js("document.querySelector('.toast [data-dismiss]').click()")
            self.type_into(p, "email", "sam@example.test")
            p.until("document.querySelector('.toast .toast-text') && document.querySelector('.toast .toast-text').textContent === 'Email saved'", "Email saved shown")
            p.js("document.querySelector('.toast [data-dismiss]').click()")
            self.type_into(p, "email", "sam@example.test")           # the same again
            self.handled(p, "Sam Lee", "sam@example.test")
            self.assertIsNone(self.toast(p), "a save that changes nothing says nothing")
            self.type_into(p, "email", "x@example.test")
            p.until("document.querySelector('.toast .toast-text') && document.querySelector('.toast .toast-text').textContent === 'Email saved'", "Email saved again")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("document.querySelector('#about-email').value === 'sam@example.test'", "the email is back")
            self.assertEqual(self.saved().get("profile_email"), "sam@example.test")
            self.assertEqual(self.saved().get("profile_name"), "Sam Lee", "the name was not touched")

    def test_C_the_chip_row_is_sticky_and_the_current_chip_is_marked(self):
        for w in WIDTHS:
            for mode in ("light", "dark"):
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_about(p, w, mode)
                    self.assertEqual(p.js("getComputedStyle(document.querySelector('.set-bar')).position"), "sticky")
                    marked = "[...document.querySelectorAll('.set-nav .set-chip[aria-current]')].map(b => b.textContent)"
                    p.until(f"{marked}.length === 1", "one chip is marked")
                    self.assertEqual(p.js(marked), ["Publishing"], "at the top the first chip is marked")
                    self.assertEqual(p.js("document.querySelector('.set-chip[aria-current]').getAttribute('aria-current')"), "location")
                    p.js("[...document.querySelectorAll('.set-nav .set-chip')].find(b => b.textContent === 'Personal').click()")
                    p.until(f"{marked}[0] === 'Personal'", "a click marks its chip")
                    p.js("window.scrollTo(0, 0)")
                    p.js("document.getElementById('safety-h').closest('section').scrollIntoView({block: 'start'})")
                    p.until("true", "settle")
                    p.js("window.scrollBy(0, 1)")
                    p.js("window.dispatchEvent(new Event('scroll'))")
                    # the click's hold lasts about a second; wait it out, then a scroll names the card in view
                    import time
                    time.sleep(1.4)
                    p.js("window.scrollBy(0, -1); window.scrollBy(0, 1)")
                    p.until(f"{marked}.length === 1 && {marked}[0] !== 'Personal'", "scrolling to Backups moves the mark")
                    top = p.js("document.querySelector('.set-bar').getBoundingClientRect().top")
                    top_bar = p.js("document.querySelector('.top').getBoundingClientRect().height")
                    self.assertAlmostEqual(top, top_bar, delta=2, msg="after a scroll the row is still under the top bar")


for _n in [n for n in dir(_AboutYou) if n.startswith("test_")]:
    setattr(Browser, _n, None)                       # only the helpers of About you's tests are borrowed, not its tests


if __name__ == "__main__":
    unittest.main()
