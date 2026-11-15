"""Item 1174a: the Dashboard leaves a stored 'Needs from you' section out (item 1158), in Edit and in View, and the minimap too.

Run: cd tests && PYTHONPATH=../src:../vendor:. python3 -m unittest test_dashboard_needs_filter
Stored sections are [text, needs, text]. The page draws the two text sections only: no needs section on the page, two entries in
the minimap, in Edit and in View, at 1400 and 900 px. The filter is the first line of `all` in
src/clark/page/src/components/Dashboard.jsx; with it removed the needs section would be drawn and listed (3 sections, 3 entries).
The stored section stays stored.
"""
import unittest

from test_report_editor import Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

IDS = ["ABC-S-701", "ABC-S-702", "ABC-S-703"]
TYPES = ["text", "needs", "text"]
TITLES = ["First words", "Needs from you", "Last words"]
NEEDS_BODY = '{"v": 1, "rows": [{"what": "Typed row", "kind": "decision", "from": "", "by": "", "hidden": 0}]}'


class NeedsFilter(Base):
    def setUp(self):
        super().setUp()
        con = self.store.con
        con.execute("DELETE FROM report_sections WHERE project = 'ABC'")
        for n, (i, t, title) in enumerate(zip(IDS, TYPES, TITLES), 1):
            body = NEEDS_BODY if t == "needs" else f"<p>Words in section {n}</p>"
            con.execute("INSERT INTO report_sections (project, id, type, title, body, sort_order) VALUES ('ABC', ?, ?, ?, ?, ?)",
                        (i, t, title, body, n * 1000))
        con.commit()

    def show(self, cdp, width):
        p = Pg.at(self, cdp, self.s.port)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.ready()
        p.until("document.querySelectorAll('.secs > .sec').length > 0", "the sections drew")
        return p

    def check(self, p, mode):
        self.assertEqual(p.js("document.querySelector('#report').dataset.mode"), mode)
        self.assertEqual(p.ids(), [IDS[0], IDS[2]], f"{mode}: the two text sections, no needs section")
        self.assertEqual(p.js("document.querySelectorAll('[data-id=\"%s\"]').length" % IDS[1]), 0, f"{mode}: the needs section is not on the page")
        self.assertEqual(p.js("document.querySelectorAll('.toc-card button[data-id]').length"), 2, f"{mode}: two minimap entries")
        self.assertEqual(p.js("document.querySelectorAll('.toc-lines i[data-tl]').length"), 2, f"{mode}: two lines on the minimap")
        self.assertEqual(p.js("[...document.querySelectorAll('.toc-card button[data-id]')].map(e => e.dataset.id)"), [IDS[0], IDS[2]])

    def test_a_stored_needs_section_is_not_drawn_or_listed_in_edit_or_view(self):
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.view()
                self.check(p, "view")
                p.edit()
                p.until("document.querySelectorAll('.secs > .sec').length > 0", "Edit drew")
                self.check(p, "edit")
                self.assertEqual([r["id"] for r in self.store.read("report_sections", "ABC") if r["type"] == "needs"], [IDS[1]],
                                 "the needs section stays stored")


if __name__ == "__main__":
    unittest.main()
