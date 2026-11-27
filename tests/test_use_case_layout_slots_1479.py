"""Row 1479: the one layout of a use case's page (UseCaseLayout.jsx): the parts that show only when there is something to show.

Run: python3 dev/run_tests.py test_use_case_layout_slots_1479
A real page (the editor's component read only, and the published file's), the same use case, its data changed before it is drawn:
no reference means no "Open all" link; no owner means no Owner row; the file's work items say the client message (the editor's say the title);
a milestone that is Done shows the date it was done, one that is not shows its planned date, never an empty or odd date; a very long and an
odd owner and title are drawn as text, never as markup, and the page does not scroll sideways.
"""
import json
import unittest

from _paths import SRC  # noqa: F401
from test_server import chrome, wait  # noqa: E402,F401      (named here, so the runner sees a browser test by its text)
from test_uc_published_same_1479 import ENTRY, UC, FIXED_DATE, page_target, need_chrome, tearDownModule
import test_uc_published_same_1479 as _test_uc_published_same_1479

ENTRY2 = ENTRY + """
import { UCEDIT } from "./edit/UseCasesEdit.jsx";
// the editor's page WITH the edit parts (ed), read only (ro true: a published file) or not; the use case linked directly to the first milestone
window.clarkMountEd = (id, ro) => {
  let host = document.getElementById("uc-test");
  if (!host) { host = document.createElement("main"); host.id = "uc-test"; document.getElementById("main").style.display = "none"; document.getElementById("main").after(host); }
  data.value = { ...data.value, uc_milestones: [{ use_case: id, milestone: data.value.milestones[0].id }] };
  fromFile.value = ro;
  render(<UseCaseDetail id={id} ed={UCEDIT} />, host);
};
window.clarkPatch = (src) => { data.value = new Function("d", "return (" + src + ")")(data.value); };
"""


class Slots(_test_uc_published_same_1479.SamePage):
    """Reuses the build and the server of the same-page test; its own AP1, AP3, AP4 and AP6 tests are switched off here."""
    test_published_and_editor_pages_have_the_same_cards_in_the_same_order = None
    test_details_shows_owner_and_not_last_change = None
    test_no_history_card = None
    test_reference_is_not_doubled_on_either_page = None

    @classmethod
    def setUpClass(cls):
        import tempfile, shutil
        from unittest import mock
        from test_uc_published_same_1479 import build_page
        from pathlib import Path
        need_chrome()
        cls.tmp = tempfile.mkdtemp(prefix="clark-uc1479s-")
        cls.src = Path(cls.tmp) / "src"
        shutil.copytree(SRC / "clark" / "page" / "src", cls.src, ignore=shutil.ignore_patterns("shown"))
        (cls.src / "main.jsx").write_text(ENTRY2, encoding="utf-8")
        with mock.patch.object(build_page, "SRC", cls.src):
            cls.built = build_page.build()

    def look(self, which, patch, ref="UC 1.1", owner="ZQ Owner Name", expr="1", width=1400, mount=None):
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.enable", {}, sid)
            cdp.call("Page.addScriptToEvaluateOnNewDocument", {"source": FIXED_DATE}, sid)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.s.port}/#usecases&p=TUL"}, sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#usecases')", sid)), "the page drew")
            cdp.js(f"window.clarkPatch({json.dumps(patch)})", sid)
            cdp.js(mount or f"window.clarkMountOne({json.dumps(UC)}, {json.dumps(which)}, {json.dumps(ref)}, {json.dumps(owner)}, false)", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('[data-ucd],[data-ucf]')", sid)))
            self.assertTrue(wait(lambda: cdp.js("!/Loading the use case/.test(document.querySelector('[data-ucd],[data-ucf]').innerText)", sid)))
            return cdp.js(expr, sid)

    def test_no_reference_means_no_open_all_link(self):
        for which in ("editor", "file"):
            self.assertEqual(self.look(which, "d", ref="", expr="document.querySelectorAll('[data-open-all]').length"), 0, which)
            self.assertEqual(self.look(which, "d", ref="UC 1.1", expr="document.querySelectorAll('[data-open-all]').length"), 1, which)

    def test_no_owner_means_no_owner_row(self):
        for which in ("editor", "file"):
            for owner in ("", None):
                got = self.look(which, "d", owner=owner, expr="[document.querySelectorAll('[data-uc-owner]').length, [...document.querySelectorAll('dt')].map((e) => e.textContent)]")
                self.assertEqual(got[0], 0, f"{which} {owner!r}")
                self.assertNotIn("Owner", got[1], f"{which} {owner!r}")
        got = self.look("file", "d", expr="[document.querySelectorAll('[data-uc-owner]').length, [...document.querySelectorAll('dt')].map((e) => e.textContent)]")
        self.assertEqual(got[0], 1)
        self.assertEqual(got[1][0], "Owner")

    def test_the_file_says_the_client_message_and_the_editor_the_title(self):
        patch = "({ ...d, actions: d.actions.map((r) => ({ ...r, client_message: 'ZQ-CM ' + r.id })), raid: d.raid.map((r) => ({ ...r, client_message: 'ZQ-CM ' + r.id })), decisions: d.decisions.map((r) => ({ ...r, client_message: 'ZQ-CM ' + r.id })) })"
        expr = "[...document.querySelectorAll('[data-item]')].map((b) => [b.querySelector('[class$=-t]').textContent, b.querySelector('[class$=-t]').getAttribute('title')])"
        file_rows = self.look("file", patch, expr=expr)
        self.assertTrue(file_rows)
        for text, title in file_rows:
            self.assertTrue(text.startswith("ZQ-CM "), text)
            self.assertEqual(title, text)
        ed_rows = self.look("editor", patch, expr=expr)
        self.assertTrue(ed_rows)
        for text, title in ed_rows:
            self.assertFalse(text.startswith("ZQ-CM "), text)
            self.assertIsNone(title, "the editor's page sets no title attribute on the row")

    def test_a_milestone_shows_the_date_it_was_done_only_when_it_is_done(self):
        def when(status):
            patch = ("({ ...d, milestones: d.milestones.map((m) => ({ ...m, status: %s, actual_date: '2026-03-02', baseline_date: '2026-01-05', forecast_date: '2026-02-09' })) })" % json.dumps(status))
            return self.look("file", patch, expr="[...document.querySelectorAll('[data-ms]')].map((li) => li.querySelector('.num').textContent)")
        done, open_ = when("Done"), when("In progress")
        self.assertTrue(done and open_)
        self.assertEqual(len(set(done)), 1)
        self.assertEqual(len(set(open_)), 1)
        self.assertNotEqual(done[0], open_[0], "Done reads the date it was done; not Done reads the planned date")
        self.assertEqual(done[0], "02-03-2026")
        self.assertEqual(open_[0], "05-01-2026")

    def test_the_unlink_control_is_for_the_editing_page_only(self):
        expr = "[document.querySelectorAll('[data-ms] [data-ms-unlink]').length, [...document.querySelectorAll('[data-ms]')].filter((li) => li.dataset.how !== 'work').length]"
        editing = self.look("editor", "d", mount=f"window.clarkMountEd({json.dumps(UC)}, false)", expr=expr)
        self.assertEqual(editing, [1, 1], "the control to unlink a directly linked milestone is on the editing page")
        read_only = self.look("editor", "d", mount=f"window.clarkMountEd({json.dumps(UC)}, true)", expr=expr)
        self.assertEqual(read_only, [0, 1], "a read only page has the same milestone and no control, even given the edit parts")

    def test_the_how_line_is_under_the_name_in_a_file(self):
        expr = "(() => { const li = document.querySelector('[data-ucf] [data-ms]'); const a = li.querySelector('[data-ms-open]').getBoundingClientRect(), h = li.querySelector('[data-ms-how]').getBoundingClientRect(); return [h.top >= a.bottom - 1, h.left <= a.left + 2]; })()"
        self.assertEqual(self.look("file", "d", expr=expr, width=1400), [True, True], "how a milestone is reached is on its own line under its name")
        self.assertEqual(self.look("file", "d", expr=expr, width=600), [True, True])

    def test_odd_owner_and_title_are_text_not_markup(self):
        hostile = "<img src=x onerror=window.ZQ=1>" + "é中\"'" + "W" * 3000
        patch = "({ ...d, use_cases: d.use_cases.map((u) => ({ ...u, title: %s })) })" % json.dumps(hostile)
        for which in ("editor", "file"):
            got = self.look(which, patch, owner=hostile, expr="[document.querySelectorAll('[data-ucd] img, [data-ucf] img').length, !!window.ZQ, document.documentElement.scrollWidth <= window.innerWidth, document.querySelector('[data-uc-owner]').textContent.length]")
            self.assertEqual(got[0:3], [0, False, True], which)
            self.assertEqual(got[3], len(hostile), which)


if __name__ == "__main__":
    unittest.main()
