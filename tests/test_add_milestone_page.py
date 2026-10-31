"""C-M3: 'Add milestone' (+) on the Milestones page (prototype parity), in a real browser against the real routes.

Run: python3 dev/run_tests.py test_add_milestone_page
Without a browser: the control and its words are in the served page and in nothing a published file is made from. With headless Chrome
(the #33 harness; fails, never skips, without it): in Edit one press adds a milestone through the change route (kind milestones, op new),
agreed 30 days from today (the local date), with one Undo and one line in the history; focus goes to the new row with its name selected;
View has no control. The milestone peek (#42) is not on the page yet, so the row, not a peek, takes focus.
"""
import tempfile
import unittest
from datetime import date, timedelta
from unittest import mock

from _demo import USER, DemoStore
from _paths import SRC

from clark import changes, page, server as sv  # noqa: E402
from test_server import Running, chrome  # noqa: E402
from test_report_editor import Pg  # noqa: E402

EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
PAGE_SRC = SRC / "clark" / "page" / "src"


class NoBrowser(unittest.TestCase):
    def test_the_control_is_in_the_served_page_and_not_in_the_published_one(self):
        view = page.VIEW_PAGE.read_text(encoding="utf-8")
        served = page.PAGE.read_text(encoding="utf-8")
        for text in ("Add milestone", "New milestone", "ms-add"):
            self.assertIn(text, served, text)
            self.assertNotIn(text, view, text)

    def test_it_goes_through_the_one_writer(self):
        api = (PAGE_SRC / "api.js").read_text(encoding="utf-8")
        self.assertIn('kind: "milestones", op: "new"', api)
        self.assertIn(changes.NEW, changes.CHANGE_KINDS["milestones"])


class Base(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.store = self.demo.store
        self.real_change = changes.make_change(self.store.path, [], USER)
        self.real_undo = changes.make_undo(self.store.path, [], USER)
        self.sent = []

        def change(req):
            self.sent.append(req)
            return self.real_change(req)
        self.s = Running(data_for=self.store.data_for, page_html=lambda: page.page_html(EMPTY_BRANDING), change=change, undo=self.real_undo)
        self.addCleanup(self.s.close)
        quiet = mock.patch.object(sv.LOG, "disabled", True)
        quiet.start()
        self.addCleanup(quiet.stop)

    def rows(self):
        return self.store.data_for("ABC")["milestones"]

    def visit(self, cdp):
        p = Pg.at(self, cdp, self.s.port, "#milestones&p=ABC")
        p.until("!!document.querySelector('#milestones')", "Milestones drew")
        return p


class InBrowser(Base):
    def test_view_has_no_add_and_edit_has_a_named_button(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("!!document.querySelector('#addMs')"), False, "View has no Add milestone")
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('#addMs')", "Edit draws it")
            self.assertEqual(p.js("document.querySelector('#addMs').getAttribute('aria-label')"), "Add milestone")
            self.assertEqual(p.js("document.querySelector('#addMs').tagName"), "BUTTON", "reachable and pressable by keyboard")
            p.js("document.querySelector('[data-mode=view]').click()")
            p.until("!document.querySelector('#addMs')", "View removes it")

    def test_add_creates_one_milestone_30_days_out_focuses_its_name_and_one_undo_takes_it_back(self):
        before = [r["name"] for r in self.rows()]
        with chrome() as cdp:
            p = self.visit(cdp)
            p.js("document.querySelector('[data-mode=edit]').click()")
            p.until("!!document.querySelector('#addMs')", "Edit draws it")
            p.js("document.querySelector('#addMs').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Milestone added.'", "the toast")
            self.assertEqual((self.sent[-1]["kind"], self.sent[-1]["op"]), ("milestones", "new"))
            new = [r for r in self.rows() if r["name"] == "New milestone"]
            self.assertEqual(len(new), 1)
            row = new[0]
            self.assertEqual(row["baseline_date"], (date.today() + timedelta(days=30)).isoformat(), "30 days from the local date")
            logged = list(self.store.con.execute("SELECT DISTINCT apply_id FROM change_log WHERE new_value = 'New milestone'"))
            self.assertEqual(len(logged), 1, "one history step")
            p.until("!!document.activeElement && !!document.activeElement.closest('.msl-row') && document.activeElement.closest('.msl-row').dataset.ms === %r"
                    % row["id"], "focus is on the new row")
            self.assertEqual(p.js("window.getSelection().toString()"), "New milestone", "its name is selected")
            p.js("document.querySelector('.toast [data-undo]').click()")
            p.until("(document.querySelector('.toast .toast-text') || {}).textContent === 'Undone.'", "Undone")
            self.assertEqual([r["name"] for r in self.rows()], before, "one Undo removes it")
            p.until("!document.querySelector('.msl-row[data-ms=\"%s\"]')" % row["id"], "the list follows")


if __name__ == "__main__":
    unittest.main()
