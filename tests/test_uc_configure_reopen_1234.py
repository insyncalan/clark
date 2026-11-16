"""Row 1234: close the Configure box (Done or Esc) while a save is still being stored, open it again at once and change something else:
the earlier change is not lost. The save is held at the page's own fetch until the test lets it go, so the order is exact.
Run: ~/ag/slot.sh with, inside tests/: PYTHONPATH=../src:../vendor:. python3 -m unittest test_uc_configure_reopen_1234
"""
import json

from test_glance_page import Setup, tearDownModule  # noqa: F401
from test_server import chrome

from _uc_view import put_view

HOLD = """(() => { window.__posts = 0; window.__open = null; const gate = new Promise((r) => { window.__open = r; }); const f = window.fetch;
  window.fetch = async (u, o) => { const post = String(u).includes('/api/section-body') && o && o.method === 'POST'; if (post) { window.__posts++; await gate; } return f(u, o); }; })()"""
DONE = "document.querySelector('#ucCfg [data-cancel]').click()"
ESC = "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', bubbles: true}))"


class Reopen(Setup):
    def stored(self):
        row = next(r for r in self.store.read("report_sections", "ABC") if r["type"] == "usecases")
        return json.loads(row["body"]) if row["body"] else None

    def run_close(self, closer):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                put_view(self, None)
                p = self.show(cdp, width)
                p.js("document.querySelector('[data-mode=edit]').click()")
                p.until("!!document.querySelector('[data-uc-configure]')", "Edit")
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgN')", "panel")
                p.js(HOLD)
                p.js("(s => { s.value = '1'; s.dispatchEvent(new Event('change', {bubbles: true})); })(document.querySelector('#ucCfgN'))")
                p.until("window.__posts === 1", "the first save is out")
                p.js(closer)
                p.until("!document.querySelector('#ucCfg')", "closed")
                p.js("document.querySelector('[data-uc-configure]').click()")
                p.until("!!document.querySelector('#ucCfgS')", "panel again")
                p.js("document.querySelector('#ucCfgS').click()")
                p.js("window.__open()")      # the saves are one after the other: the second goes out once the first is stored
                p.until("window.__posts === 2 && document.querySelector('#ucCfgS').checked", "second change stored and drawn")
                self.assertEqual(p.js("document.querySelector('#ucCfgN').value"), "1", "the first change is still drawn")
                self.assertEqual(self.stored(), {"n": 1, "scroll": True, "tracker": "top"}, "both changes are stored")

    def test_done_then_reopen_while_a_save_is_pending_keeps_both(self):
        self.run_close(DONE)

    def test_escape_then_reopen_while_a_save_is_pending_keeps_both(self):
        self.run_close(ESC)
