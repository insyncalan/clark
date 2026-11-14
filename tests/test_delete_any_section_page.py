"""Row 906 on the page: Delete section is in the grip menu of every section type; deleting shows the toast with Undo, Undo and Cmd/Ctrl+Z
bring the section back, a reload keeps it gone, and Add a section offers a deleted built-in again (one of each, and not while it is there).

Run: python3 dev/run_tests.py test_delete_any_section_page
The real page and a real server over the fictional demo report (the harness of tests/test_report_editor.py), in headless Chrome at
1400 px and 900 px. The browser parts are required: they fail, never skip, without Chrome (set CLARK_CHROME to its path).
"""
import time
import unittest

from test_report_editor import Base, IDS, TITLES  # noqa: E402
from test_server import chrome  # noqa: E402

WIDTHS = (1400, 900)
CTRL = 2


class DeleteAnySection(Base):
    def at(self, cdp, p, width):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1400, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.until(f"window.innerWidth === {width}", "resized")
        time.sleep(.2)

    def acts(self, p, ref):
        p.js(f"document.querySelector('[data-id=\"{ref}\"] [data-options]').click()")
        p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .menu')", "the menu opened")
        p.until("!!document.activeElement && !!document.activeElement.closest('.menu')", "focus moved into the menu (the key goes to it)")
        got = p.js(f"[...document.querySelectorAll('[data-id=\"{ref}\"] .menu-item')].map(b => b.dataset.act)")
        p.key("Escape", code="Escape", vk=27)
        p.until(f"!document.querySelector('[data-id=\"{ref}\"] .menu')", "the menu closed")
        return got

    def test_every_section_type_offers_delete_section_at_1400_and_900(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                for ref in IDS:
                    got = self.acts(p, ref)
                    self.assertEqual(got[-1:], ["delete"], f"{ref} at {w}: Delete section is the last item")

    def test_delete_each_built_in_undo_cmd_z_reload_and_add_it_again(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            for w in WIDTHS:
                self.at(cdp, p, w)
                for ref in ("ABC-S-004", "ABC-S-008"):                      # Milestones, Risks and issues
                    p.menu(ref, "delete")
                    p.order_is([i for i in IDS if i != ref], f"{ref} deleted at {w}")
                    self.assertNotIn(ref, self.ids_in_store())
                    p.toast_is("Section deleted.")      # the toast from the last Ctrl+Z may still be up
                    p.js("document.querySelector('[data-undo]').click()")      # Undo
                    p.order_is(IDS, f"Undo at {w}")
                    p.menu(ref, "delete")
                    p.order_is([i for i in IDS if i != ref], "deleted again")
                    p.js("document.body.focus()")
                    p.key("z", CTRL, "KeyZ", 90)                                # Cmd/Ctrl+Z
                    p.order_is(IDS, f"Ctrl+Z at {w}")
            p.menu("ABC-S-004", "delete")
            p.order_is([i for i in IDS if i != "ABC-S-004"], "deleted")
            p.reload()
            p.edit()
            p.order_is([i for i in IDS if i != "ABC-S-004"], "a reload keeps it gone")
            self.assertNotIn("Milestones", p.titles())
            for w in WIDTHS:
                self.at(cdp, p, w)
                p.menu("ABC-S-003", "add")
                p.until("!!document.querySelector('[data-template=built-in-milestones]')", "Add a section offers Milestones again")
                self.assertIsNone(p.js("document.querySelector('[data-template=built-in-raid]')"), "a built-in that is there is not offered")
                p.js("document.querySelector('[data-template=built-in-milestones] input').click()")
                p.js("document.querySelector('button[data-place]').click()")
                p.until("document.querySelectorAll('.secs > .sec').length === 11", "added")
                self.assertEqual(p.titles().count("Milestones"), 1)
                p.menu(p.ids()[3], "delete")                                    # ready for the next width
                p.until("document.querySelectorAll('.secs > .sec').length === 10", "deleted again")


if __name__ == "__main__":
    unittest.main()
