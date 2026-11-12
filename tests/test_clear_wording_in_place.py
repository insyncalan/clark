"""Row 893: in Edit, clearing a report row's wording box and pressing Enter clears the wording (no refusal). The change request carries
client_message '', the toast is the existing 'Wording of <ID> changed.', the row stays in its section and shows the item's title
(its fallback, row 851), and one Undo puts the old words back. 1400 and 900, light and dark. All rows are fictional.

Run: python3 dev/run_tests.py test_clear_wording_in_place
"""
import json
import sys
import unittest

from _demo import USER, DemoStore
from _paths import TOOLS

sys.path.insert(0, str(TOOLS))
from test_item_rows import edit_server, fill, id_of  # noqa: E402
from test_report_editor import Pg  # noqa: E402
from test_server import chrome, wait  # noqa: E402

CASES = (("raid", "Supplier delivery may slip", "Supplier may deliver late"),
         ("actions", "Cut-over plan to be agreed", "Agree the cut-over plan"),
         ("decisions", "Hosting region to be chosen", "Choose the hosting region"))
SPY = ("(function(){var f=window.fetch; window.__sent=[]; window.fetch=function(u,o){try{if(o&&o.body){window.__sent.push(String(o.body));}}catch(e){}"
       " return f.apply(this,arguments);};})()")


class ClearWordingInPlace(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        fill(self.store)
        self.s = edit_server(self, self.store)

    def test_a_blank_wording_clears_it_the_row_shows_its_title_and_undo_puts_the_words_back(self):
        with chrome() as cdp:
            p = Pg.at(self, cdp, self.s.port)
            p.ready()
            p.edit()
            for theme in ("light", "dark"):
                p.js("document.documentElement.setAttribute('data-theme', %r)" % theme)
                for w in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": w, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                    for table, words, title in CASES:
                        where = f"{theme} {w} {table}"
                        ident = id_of(self.store, words) if any(r["client_message"] == words for r in self.store.read(table, "ABC")) else None
                        self.assertTrue(ident, where)
                        row = f"[data-type={table}] .wl-row[data-id={ident!r}]"
                        box = f"document.querySelector({row!r} + ' [data-rich=client_message]')"
                        p.js(SPY)
                        p.js(f"{box}.click()")                              # item 1005: the one editor opens in its place
                        p.until("document.activeElement.classList.contains('ProseMirror')", f"{where}: the editor opens")
                        p.js("(() => { const e = document.activeElement.cxed.editor; e.commands.selectAll(); e.commands.deleteSelection(); })()")
                        p.key("Enter", code="Enter", vk=13)
                        p.toast_is(f"Wording of {ident} changed.")
                        self.assertTrue(wait(lambda: any('"client_message": ""' in b or '"client_message":""' in b for b in p.js("window.__sent"))), f"{where}: the request carries client_message ''")
                        p.until(f"{box}.textContent.trim() === {json.dumps(title)}", f"{where}: the row stays in its section and shows the item's title")
                        self.assertEqual(p.js(f"document.querySelectorAll({row!r}).length"), 1, where)
                        stored = next(r for r in self.store.read(table, "ABC") if r["id"] == ident)
                        self.assertEqual(stored["client_message"], "", where)
                        p.js("document.querySelector('.toast [data-undo]').click()")
                        p.until(f"{box}.textContent.trim() === {json.dumps(words)}", f"{where}: one Undo puts the old words back")
                        self.assertEqual(next(r for r in self.store.read(table, "ABC") if r["id"] == ident)["client_message"], words, where)


if __name__ == "__main__":
    unittest.main()
