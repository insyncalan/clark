"""Row 1299 AP11: the STORE behind the project cards follows the Settings tab's project, in a real browser at 1400 and 900 px, light and dark. Run: python3 dev/run_tests.py test_settings_tabs_cards_1299

What is asserted (Classic), on the store only (no card is drawn from it yet; the switch stays a test hook, so the page's cards are not proven to follow the tab): with the tab on a project other than the open one (T, here ABC; the open one O is PUB) the store reads T's data (GET /api/data?project=ABC) and hands it out (settingsProjectData); a change made for T goes to T's code, the toast and its Undo name T, T's data is read again, and O's data and the top bar are not touched. A tab that is the open
project reads nothing again. A failed read of T's data hands out no values (never O's); a failed read AFTER T's data was held drops it, and the page says the change was saved but could not be refreshed. Chrome is required: these tests fail, never skip, without it.
"""
import copy
import unittest

from test_server import chrome
from test_settings_tabs_1299 import Rigged, TABS

TWO = [{"code": "PUB", "name": "Harbour Bridge Programme"}, {"code": "ABC", "name": "Second Programme"}]


class Cards(Rigged):
    """PUB is the real plant project; ABC is a fake one the rig serves: data_for answers from `abc`, change and undo record the request and edit `abc`."""
    listed = TWO
    switch = True
    fail_abc = False

    def setUp(self):
        super().setUp()
        rig = self.rig
        real = rig.httpd.data_for
        self.abc = copy.deepcopy(real("PUB"))
        self.abc["project"].update({"code": "ABC", "name": "Second Programme", "review_after_days": 30, "brand": "generic", "publish_client": "/Clients/Second", "publish_local": None})
        self.reads, self.sent, self.undone, self.fail_abc = [], [], [], False
        self.old_abc = []

        def data_for(code, archived="hide"):
            self.reads.append(code)
            if code == "ABC":
                return None if self.fail_abc else copy.deepcopy(self.abc)
            return real(code, archived=archived) if archived != "hide" else real(code)

        def change(req):
            self.sent.append(req)
            if req.get("project") != "ABC":
                return real_change(req)
            self.old_abc.append(copy.deepcopy(self.abc["project"]))
            self.abc["project"].update(req.get("changes") or {})
            return 200, {"ok": True, "apply_id": 900 + len(self.old_abc), "ref": "ABC", "sections": [], "project": {}}

        def undo(req):
            self.undone.append(req)
            if req.get("project") != "ABC":
                return real_undo(req)
            self.abc["project"] = self.old_abc.pop()
            return 200, {"ok": True, "sections": [], "project": {}}

        real_change, real_undo = rig.httpd.change, rig.httpd.undo
        rig.httpd.data_for, rig.httpd.change, rig.httpd.undo = data_for, change, undo

    w, mode = 1400, "light"

    def settings(self, p, slug):
        self.open_settings(p, self.w, self.mode, slug=slug)
        p.until(f"{TABS}.length === 2", "the tabs drew")

    def choose_abc(self, p):
        p.js(f"{TABS}[1].click()")
        p.until(f"{TABS}[1].getAttribute('aria-current') === 'page' && clarkPage.settingsProjectData() && clarkPage.settingsProjectData().project.code === 'ABC'", "ABC's data was read")


class StoreTests:
    def test_a_tab_reads_its_projects_data_and_the_open_project_stays(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.settings(p, "reports")
            open_code = p.js("clarkPage.project()")
            before_reads = self.reads.count("PUB")
            self.choose_abc(p)
            self.assertEqual(self.reads.count("ABC"), 1, "T's data was read once")
            self.assertEqual(self.reads.count("PUB"), before_reads, "the open project was not read again")
            self.assertEqual(p.js("clarkPage.settingsProjectData().project.review_after_days"), 30, "the store hands out T's data")
            self.assertEqual(p.js("[clarkPage.project(), clarkPage.data().project.code]"), [open_code, "PUB"], "the open project and its data are untouched")

    def test_switching_back_to_the_open_project_reads_nothing_again(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.settings(p, "reports")
            self.choose_abc(p)
            n = len(self.reads)
            p.js(f"{TABS}[0].click()")
            p.until(f"{TABS}[0].getAttribute('aria-current') === 'page'", "the open project's tab is marked")
            self.assertEqual(p.js("clarkPage.settingsProjectData().project.code"), "PUB", "the open project's data again")
            self.assertEqual(len(self.reads), n, "nothing was read")

    def test_a_change_for_the_tab_project_goes_to_its_code_and_reads_its_data_again(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.settings(p, "reports")
            self.choose_abc(p)
            was = p.js("clarkPage.data().project.review_after_days")
            p.js("clarkPage.changeFor('ABC', {kind: 'projects', op: 'update', changes: {review_after_days: 21}, place: 'menu'}, 'Not reviewed after: 21 days.')")
            p.until("clarkPage.settingsProjectData().project.review_after_days === 21", "T's data was read again")
            self.assertEqual([r["project"] for r in self.sent], ["ABC"], "the change names T")
            self.assertEqual(p.js("clarkPage.data().project.review_after_days"), was, "O's data is as it was")
            self.assertEqual(p.js("clarkPage.toast().code"), "ABC", "the toast and its Undo name T")

    def test_tab_read_failure_shows_no_values_not_the_open_projects(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.settings(p, "reports")
            self.fail_abc = True
            p.js(f"{TABS}[1].click()")
            p.until("clarkPage.settingsRead() === 'failed'", "the read failed")
            self.assertIsNone(p.js("clarkPage.settingsProjectData()"), "no data, not the open project's")

    def test_a_failed_re_read_after_a_change_drops_the_held_data_and_says_so(self):
        with chrome() as cdp:
            p = self.page(cdp)
            self.settings(p, "reports")
            self.choose_abc(p)
            self.fail_abc = True
            p.js("clarkPage.changeFor('ABC', {kind: 'projects', op: 'update', changes: {review_after_days: 21}, place: 'menu'}, 'Not reviewed after: 21 days.')")
            p.until("clarkPage.settingsRead() === 'failed'", "the re-read failed")
            self.assertIsNone(p.js("clarkPage.settingsProjectData()"), "T's old values are gone, and O's are not shown in their place")
            p.until("!!clarkPage.toast() && clarkPage.toast().kind === 'problem'", "the page says the re-read failed")
            self.assertEqual(p.js("clarkPage.toast().text"), "The change was saved, but the page could not be refreshed. Reload the page to see it.")


class TabStore(StoreTests, Cards):
    pass


for _w in (1400, 900):
    for _m in ("light", "dark"):
        if (_w, _m) != (1400, "light"):
            globals()[f"TabStore{_w}{_m.title()}"] = type(f"TabStore{_w}{_m.title()}", (StoreTests, Cards), {"w": _w, "mode": _m})


if __name__ == "__main__":
    unittest.main()
