"""Row 1535 step 5 (AP16, AP17): Settings › Backups (the foot of its card) says "Your preferences are kept with your data" and has "Reset all preferences", in a real browser at
1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_preferences_settings_1535. Chrome is required: these tests fail, never skip, without it.

What is asserted: the line and the button are on the Backups page; the page never scrolls sideways; the first press asks (Cancel appears, nothing is sent), Cancel
puts it back and sends nothing, the second press sends one reset and takes the kept `clark.` keys out of the browser (a reader's key and a key outside `clark.` stay).
The folder's half of "only preferences" (the database and settings.json are not touched) is test_preferences_1535.DataFolder1535.test_reset_all_preferences_only.
"""
import json
import unittest

from test_appearance import scheme
from test_publish_dialog import Base
from test_server import chrome

WIDTHS = (1400, 900)
MODES = ("light", "dark")
LINE = "Your preferences are kept with your data"
BUTTON = "Reset all preferences"


class Kept(Base):
    def open_backups(self, p, w, mode):
        p.width(w)
        scheme(p, mode)
        p.js("location.hash = '#settings&p=PUB&s=backups'")
        p.until("!!document.getElementById('preferences-kept') && !!document.getElementById('preferences-reset')", "the preferences card drew")
        p.settled("Settings finished drawing and scrolling")

    def test_settings_shows_kept_line(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_backups(p, w, mode)
                    self.assertEqual(p.js("document.getElementById('preferences-kept').textContent"), LINE)
                    self.assertEqual(p.js("document.getElementById('preferences-reset').textContent"), BUTTON)
                    self.assertTrue(p.js("!!document.getElementById('preferences').closest('#safety')"), "it is in the Backups card")
                    box = p.js("(function(){ var r = document.getElementById('preferences-reset').getBoundingClientRect(); return [r.left, r.right, r.width, r.height, window.innerWidth]; })()")
                    self.assertTrue(0 <= box[0] and box[1] <= box[4] and box[2] > 0 and box[3] >= 24, box)
                    self.assertLessEqual(p.js("document.documentElement.scrollWidth"), w, "no sideways scroll")

    def test_reset_button_asks_then_resets(self):
        for w in WIDTHS:
            for mode in MODES:
                with self.subTest(width=w, mode=mode), chrome() as cdp:
                    p = self.page(cdp)
                    self.open_backups(p, w, mode)
                    p.js("""(function(){ localStorage.setItem('clark.peekWidth', '480'); localStorage.setItem('clark.reader.name', 'Pat'); localStorage.setItem('other.key', 'x');
                      sessionStorage.setItem('seen', '[]'); var real = window.fetch.bind(window);
                      window.fetch = function(u, o){ if (String(u).indexOf('/api/preferences') === 0) { var s = JSON.parse(sessionStorage.getItem('seen')); s.push(o.body); sessionStorage.setItem('seen', JSON.stringify(s));
                        return Promise.resolve({ ok: true }); } return real(u, o); }; })()""")
                    seen = lambda: json.loads(p.js("sessionStorage.getItem('seen')"))
                    p.js("document.getElementById('preferences-reset').click()")
                    p.until("!!document.getElementById('preferences-cancel')", "the question's Cancel is there")
                    self.assertEqual(seen(), [], "the first press sends nothing")
                    p.js("document.getElementById('preferences-cancel').click()")
                    p.until("!document.getElementById('preferences-cancel')", "Cancel put it back")
                    self.assertEqual((seen(), p.js("localStorage.getItem('clark.peekWidth')")), ([], "480"))
                    p.js("document.getElementById('preferences-reset').click()")
                    p.until("!!document.getElementById('preferences-cancel')", "asking again")
                    p.js("document.getElementById('preferences-reset').click()")
                    p.until("sessionStorage.getItem('seen') !== '[]'", "the reset was sent")
                    self.assertEqual([json.loads(b) for b in seen()], [{"reset": True}])
                    p.until("localStorage.getItem('clark.peekWidth') === null", "the kept key was taken out of the browser")
                    self.assertEqual(p.js("[localStorage.getItem('clark.reader.name'), localStorage.getItem('other.key')]"), ["Pat", "x"])


if __name__ == "__main__":
    unittest.main()
