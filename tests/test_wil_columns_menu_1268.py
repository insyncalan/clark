"""Row 1268: the Work items list's Columns menu (a right click on a column heading) ticks each column with aria-checked: "true" for a
column the list shows and "false" for one it does not, and the tick follows a press."""
import json
import time
import unittest

import test_tpl_workitems as base
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome, wait


class ColumnsMenu(base.InThePage):
    # Row 1549: macOS shard 1/6 (run 45155082524) failed "the menu opened" on a load flake (passed alone in 4.6 s). Menu.jsx closes a menu on ANY scroll or resize, so a scroll
    # or layout shift after the right-click is the suspected cause (not proven). So the right-click waits until the page rests, and a menu that still does not open fails
    # with the state printed. There is no retry: a re-sent right-click would hide the flake.
    LOOK = ("(() => { const h = document.querySelector(%s), r = h ? h.getBoundingClientRect() : null;"
            " return { scrollY: Math.round(scrollY * 100) / 100, scrollX: Math.round(scrollX * 100) / 100, w: innerWidth, h: innerHeight,"
            " head: r ? [r.left, r.top, r.width, r.height].map(v => Math.round(v * 100) / 100) : null,"
            " expanded: h ? h.getAttribute('aria-expanded') : null, menu: !!document.querySelector('.cols-menu') }; })()")

    def look(self, p, head):
        return p.js(self.LOOK % json.dumps(head))

    def settle(self, p, head, seconds=10):
        """True once the heading exists and its rect, the window scroll and the window size are the same on two looks 150 ms apart; False at the limit."""
        def at_rest():
            a = self.look(p, head)
            time.sleep(0.15)
            b = self.look(p, head)
            return a["head"] is not None and all(a[k] == b[k] for k in ("scrollY", "scrollX", "w", "h", "head"))
        return wait(at_rest, seconds)

    def right_click(self, p, head, what="the menu opened"):
        """Wait for the page to rest, send ONE right-click on the heading, and wait for the menu; where it does not open, fail with the state."""
        rested = self.settle(p, head)
        p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent(new MouseEvent('contextmenu', {{bubbles: true, cancelable: true}}))")
        opened = wait(lambda: p.js("!!document.querySelector('.cols-menu')"), 10)
        self.assertTrue(opened, f"{what}: page at rest before the click: {rested}; state now: {self.look(p, head)}")
    def checked(self, p):
        return p.js("Object.fromEntries([...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map(b => [b.dataset.colName, b.getAttribute('aria-checked')]))")

    def test_aria_checked_is_true_for_a_shown_column_and_false_for_a_hidden_one_and_follows_a_press(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
            p.until(f"!!document.querySelector({json.dumps(head)})", "the list drew in Edit")
            self.right_click(p, head, "the menu opened")
            got = self.checked(p)
            self.assertEqual(got["ID"], "true")
            self.assertEqual(got["Owner"], "true")
            for off in ("Type", "Due", "Status", "Priority", "Workstream", "Milestone"):
                self.assertEqual(got[off], "false", off)
            p.js("document.querySelector('.cols-menu [data-col-name=Due]').click()")
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-due')", "Due was added")
            self.right_click(p, head, "the menu opened again")
            self.assertEqual(self.checked(p)["Due"], "true", "a column the press added is ticked")

    def test_the_list_scroll_box_contains_vertical_overscroll_only_so_the_swipe_still_works(self):
        """Row 1268: the Work items list's scroll box (.wil-scroll) keeps the page from scrolling under it (vertical containment) and leaves the
        horizontal overscroll alone, because Chrome's two-finger swipe for Back and Forward is off under overscroll-behavior-x none or contain."""
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            box = f"[data-id=\"{ref}\"] [data-wil-scroll]"
            p.until(f"!!document.querySelector({json.dumps(box)})", "the scroll box drew")
            got = p.js(f"(() => {{ const c = getComputedStyle(document.querySelector({json.dumps(box)})); return [c.overscrollBehaviorX, c.overscrollBehaviorY]; }})()")
            self.assertEqual(got, ["auto", "contain"])

    def open_menu(self, p, ref):
        head = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table th.wil-c-owner"
        p.until(f"!!document.querySelector({json.dumps(head)})", "the list drew in Edit")
        return head

    def test_every_column_line_carries_an_icon_named_by_columnIcon(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        want = {"Type": "table", "ID": "table", "Owner": "user", "Due": "cal", "Status": "half", "Priority": "table", "Workstream": "board", "Milestone": "flag"}
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = self.open_menu(p, ref)
            self.right_click(p, head, "the menu opened")
            got = p.js("Object.fromEntries([...document.querySelectorAll('.cols-menu [role=menuitemcheckbox]')].map(b => [b.dataset.colName, [...b.querySelectorAll(':scope > svg.mi')].map(i => i.getAttribute('data-icn'))]))")
            self.assertEqual(got, {k: [v] for k, v in want.items()}, "each column line has one icon, named as columnIcon names it")
            self.assertEqual(got["Owner"], ["user"])

    def test_plain_f10_does_not_open_the_menu_and_shift_f10_does_and_the_menu_is_named_columns(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            head = self.open_menu(p, ref)
            key = "new KeyboardEvent('keydown', {key: 'F10', shiftKey: %s, bubbles: true, cancelable: true})"
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent({key % 'false'})")
            self.assertFalse(p.js("!!document.querySelector('.cols-menu')"), "F10 alone is not the menu key")
            p.js(f"document.querySelector({json.dumps(head)}).dispatchEvent({key % 'true'})")
            p.until("!!document.querySelector('.cols-menu')", "Shift+F10 opened the menu")
            self.assertEqual(p.js("document.querySelector('.cols-menu').getAttribute('aria-label')"), "Columns")
            self.assertEqual(p.js("[...document.querySelectorAll('.cols-menu .ck')].every(e => e.getAttribute('aria-hidden') === 'true')"), True, "the tick glyph is hidden from readers")

    def test_headings_are_column_headers_and_rows_show_a_pointer_in_edit(self):
        ref = self.add({"mode": "all", "columns": ["id", "owner"], "owner": ["Pat Demo", "Lee Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.edit()
            self.open_menu(p, ref)
            sel = f"[data-id=\"{ref}\"] [data-wil-edit] .wil-table"
            self.assertEqual(p.js(f"[...document.querySelectorAll({json.dumps(sel + ' th')})].every(t => t.getAttribute('scope') === 'col')"), True)
            p.until(f"!!document.querySelector({json.dumps(sel + ' tbody tr')})", "a row drew")
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector({json.dumps(sel + ' tbody tr')})).cursor"), "pointer")


for _name in [n for n in dir(base.InThePage) if n.startswith("test_")]:
    setattr(ColumnsMenu, _name, None)       # the helpers of the list's page tests are reused; their tests are run by test_tpl_workitems


if __name__ == "__main__":
    unittest.main()
