"""Row 1268, slice s2: a Work items list row opens the peek. In a published file the peek is read only (no control, only the client's
fields); in Edit it is the editable peek (test_tpl_workitems covers Edit's click and Enter). Fictional data only.

Run: python3 dev/run_tests.py test_wil_peek_1268   (headless Chrome; fails, never skips, without it)
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from clark import changes, publish
from test_tpl_workitems import TODAY, plant
from test_report_editor import EMPTY_BRANDING, Base as PageBase, Pg, tearDownModule  # noqa: F401
from test_server import chrome

CONTROLS = "button:not([data-pk-details]), input, textarea, select, [role=textbox], [role=combobox]"
PEEK_ID = "((document.querySelector('#peek') || {dataset: {}}).dataset.peek || '')"
OWNERS = ["Pat Demo", "Lee Demo", "Sam Demo", "Kim Demo"]


class FilePeek(PageBase):
    def setUp(self):
        super().setUp()
        plant(self)
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.NEW, "values": {"type": "workitems", "title": "Due soon"}, "after": None})
        self.ref = got["ref"]
        status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": changes.UPDATE, "id": self.ref,
                                        "changes": {"body": json.dumps({"mode": "all", "columns": ["id", "owner", "due"], "owner": OWNERS})}})
        self.assertEqual(status, 200, got)

    def test_a_row_of_the_published_file_opens_the_read_only_peek_by_click_and_by_keyboard(self):
        out = tempfile.mkdtemp(prefix="clark-1268-peek-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now=TODAY, branding=EMPTY_BRANDING)["path"])
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
                sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
                cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
                p = Pg(self, cdp, sid)
                p.until(f"!!document.querySelector('[data-id=\"{self.ref}\"] .wil-table tbody tr')", "the list drew")
                row = f"[data-id=\"{self.ref}\"] .wil-table tbody tr[data-id=\"{self.a_due}\"]"
                if width == 900:
                    row = f"[data-id=\"{self.ref}\"] .wil-lines li[data-id=\"{self.a_due}\"]"
                p.js(f"document.querySelector({row!r}).click()")
                p.until(f"{PEEK_ID} === {self.a_due!r}", "the row opened its own item")
                self.assertEqual(p.js(f"[...document.querySelectorAll('#peek .pk-body')].reduce((n, b) => n + b.querySelectorAll({CONTROLS!r}).length, 0)"), 0, "read only: no control in the body")
                self.assertEqual(p.js("document.querySelectorAll('#peek [role=textbox], #peek [contenteditable=true]').length"), 0)
                p.js("location.hash = ''")
                p.until(f"{PEEK_ID} === ''", "the peek closed")
                p.js(f"document.querySelector({row!r}).dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', bubbles: true, cancelable: true}}))")
                p.until(f"{PEEK_ID} === {self.a_due!r}", "Enter opened it")


if __name__ == "__main__":
    unittest.main()
