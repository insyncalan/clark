import json
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait
import _dbg1549


class EditKillers(base.InThePage):
    def head(self, ref, col="owner"):
        return f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-{col}"

    def applies(self):
        return self.demo.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def drawn(self, p, ref, col="owner"):
        p.until(f"!!document.querySelector({json.dumps(self.head(ref, col))})", "the list drew in Edit")

    def test_the_last_shown_column_cannot_be_taken_off_and_nothing_is_saved(self):
        ref = self.add({"mode": "all", "columns": ["owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.drawn(p, ref)
            _dbg1549.arm(p.js, self.id().split('.')[-1], '.cols-menu', p)
            p.js(f"(() => {{ const ev = new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}); const r = document.querySelector({json.dumps(self.head(ref))}).dispatchEvent(ev); window.__dbg.dispatch = {{ret: r, defaultPrevented: ev.defaultPrevented, type: ev.type, key: ev.key}}; return r; }})()")
            p.until("!!document.querySelector('.cols-menu')", "the menu opened")
            before = self.applies()
            p.js("document.querySelector('.cols-menu [data-col-name=Owner]').click()")
            p.until("!!document.querySelector('.toast-text') && document.querySelector('.toast-text').textContent === 'Choose at least one column to show.'", "the refusal was said")
            self.assertEqual(self.applies(), before)
            self.assertEqual(json.loads(self.demo.store.read("report_sections", ref=ref)["body"])["columns"], ["owner"])

    def test_the_context_menu_key_on_a_heading_opens_the_columns_menu(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.drawn(p, ref)
            _dbg1549.arm(p.js, self.id().split('.')[-1], '.cols-menu', p)
            p.js(f"(() => {{ const ev = new KeyboardEvent('keydown', {{key: 'ContextMenu', bubbles: true, cancelable: true}}); const r = document.querySelector({json.dumps(self.head(ref))}).dispatchEvent(ev); window.__dbg.dispatch = {{ret: r, defaultPrevented: ev.defaultPrevented, type: ev.type, key: ev.key}}; return r; }})()")
            p.until("!!document.querySelector('.cols-menu')", "the menu key opened the menu")

    def test_a_right_click_on_a_heading_keeps_the_browsers_own_menu_away(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.drawn(p, ref)
            _dbg1549.arm(p.js, self.id().split('.')[-1], '.cols-menu', p)
            sent = p.js(f"(() => {{ const ev = new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}); const r = document.querySelector({json.dumps(self.head(ref))}).dispatchEvent(ev); window.__dbg.dispatch = {{ret: r, defaultPrevented: ev.defaultPrevented, type: ev.type, key: ev.key}}; return r; }})()")
            _dbg1549.last.dump()
            self.assertEqual(sent, False, "the right click was cancelled")

    def test_each_list_keeps_its_own_column_widths(self):
        a = self.add({"mode": "all", "columns": ["owner", "due"], "owner": ["Pat Demo", "Lee Demo"]}, title="First")
        b = self.add({"mode": "all", "columns": ["owner", "due"], "owner": ["Pat Demo", "Lee Demo"]}, title="Second", after=a)
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.drawn(p, a)
            self.drawn(p, b)
            w = lambda r: p.js(f"document.querySelector({json.dumps(self.head(r))}).style.width")
            p.js(f"document.querySelector({json.dumps(self.head(a))}).dispatchEvent(new KeyboardEvent('keydown', {{key: 'ArrowRight', altKey: true, bubbles: true}}))")
            self.assertTrue(wait(lambda: w(a) != ""), "the first list's Owner width was set")
            self.assertEqual(w(b), "", "the second list's Owner width was not")

    def test_the_count_line_says_one_work_item_in_the_singular(self):
        ref = self.add({"mode": "all", "kinds": ["risk"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            sel = f"[data-id=\"{ref}\"] [data-wil-say=count]"
            p.until(f"!!document.querySelector({json.dumps(sel)})", "the count drew")
            self.assertEqual(p.js(f"document.querySelector({json.dumps(sel)}).textContent.split('.')[0]"), "1 work item listed now")

    def test_the_columns_menu_ticks_a_shown_column_with_a_check_and_leaves_a_hidden_one_blank(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.drawn(p, ref)
            _dbg1549.arm(p.js, self.id().split('.')[-1], '.cols-menu', p)
            p.js(f"(() => {{ const ev = new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}); const r = document.querySelector({json.dumps(self.head(ref))}).dispatchEvent(ev); window.__dbg.dispatch = {{ret: r, defaultPrevented: ev.defaultPrevented, type: ev.type, key: ev.key}}; return r; }})()")
            p.until("!!document.querySelector('.cols-menu')", "the menu opened")
            got = p.js("Object.fromEntries([...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map(b => [b.dataset.colName, b.querySelector('.ck').textContent]))")
            self.assertEqual(got["Owner"], "✓")
            self.assertEqual(got["Due"], "")


for _name in [n for n in dir(base.InThePage) if n.startswith("test_")]:
    setattr(EditKillers, _name, None)


if __name__ == "__main__":
    unittest.main()
