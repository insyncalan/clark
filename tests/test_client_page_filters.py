"""#69 (page): the published page's Work items filters, search and Group by, driven in headless Chrome.

Run: python3 dev/run_tests.py test_client_page_filters
A page is published from the test plant (fictional, with extra rows and one row that is not the client's) and opened from disk, with
no server. Every control is clicked: the type switch, Open / Closed / All, Filter by (a second filter opens in one click), the chips,
Clear all, search and Group by. Nothing may move when a control is clicked. The choices are remembered in the page's own key and
come back after a reload; the editor's key is never written. Desktop only: 1400 and 900 px, light and dark.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_server import chrome, wait
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

TODAY = "2026-10-28"
EMPTY_BRANDING = tempfile.mkdtemp(prefix="clark-no-brand-")
VARIANTS = [(w, s) for w in (1400, 900) for s in ("light", "dark")]
INTERNAL = "ZQ-INTERNAL-ONLY-ROW"
HIDDEN_OWNER = "Hidden Owner"            # the row that is not the client's has an owner and a workstream of its own
HIDDEN_WS = "Hidden Workstream"
CLOSED = ["PUB-A-104", "PUB-D-001", "PUB-D-003"]


def plant():
    p = fx.load()
    base = p["data"]["actions"][0]
    more = [("101", "Ana Lopez", "Delivery", "High", "2026-10-20", "Open", "Order the pumps"),
            ("102", "Bo Chen", "Build", "Low", "2026-11-02", "Delayed", "Book the crane"),
            ("103", "Ana Lopez", "Build", "Urgent", "2026-12-20", "Open", "Sign off the drawings"),
            ("104", "Cy Dunn", "Delivery", "Medium", "2026-10-01", "Closed", "Close the old contract")]
    for n, owner, ws, pri, due, status, text in more:
        row = dict(base, id=f"PUB-A-{n}", description=text, owner=owner, workstream=ws, priority=pri, due_date=due, status=status,
                   latest_update=f"Note {n}", client_message="", milestone=None, use_case=None,
                   closed="2026-10-02" if status == "Closed" else None)
        p["data"]["actions"].append(row)
    p["data"]["actions"].append(dict(base, id="PUB-A-199", description=INTERNAL, client_visible=0, client_message="",
                                    owner=HIDDEN_OWNER, workstream=HIDDEN_WS))
    return p


def open_page(cdp, url, width, scheme):
    sid = page_target(cdp)
    cdp.call("Page.enable", {}, sid)
    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
    cdp.call("Page.navigate", {"url": url}, sid)
    return sid


class ClientPageFilters(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-cpf-"))
        db = fx.build_db(cls.tmp / "c.db", plant())
        cls.store = open_store(db, onedrive_roots=[])
        out = cls.tmp / "out"
        out.mkdir()
        cls.path = Path(publish.publish(cls.store, "PUB", out, by_user="Demo User", now=TODAY, branding=EMPTY_BRANDING)["path"])
        cls.html = cls.path.read_text(encoding="utf-8")

    @classmethod
    def tearDownClass(cls):
        cls.store.close()
        shutil.rmtree(cls.tmp, True)

    # -- helpers
    def go(self, cdp, width, scheme):
        sid = open_page(cdp, self.path.as_uri() + "#work", width, scheme)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work-list')", sid)), "the Work items tab drew")
        return sid

    def count(self, cdp, sid):
        return cdp.js("document.querySelectorAll('#work-list tr[data-id]').length", sid)

    def ids(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].map(r => r.dataset.id)", sid)

    def spots(self, cdp, sid):
        return cdp.js("""[...document.querySelectorAll('.wbar button, .fbar .fbtn, #q, #group-by')].map(e => { const r = e.getBoundingClientRect();
            return [e.id || e.dataset.type || e.dataset.show || e.dataset.fb, Math.round(r.left + window.scrollX), Math.round(r.top + window.scrollY)]; })""", sid)

    def click(self, cdp, sid, sel):
        self.assertTrue(cdp.js(f"(() => {{ const e = document.querySelector({json.dumps(sel)}); if (!e) return false; e.click(); return true; }})()", sid), sel)

    def settle(self, cdp, sid, cond="true"):
        self.assertTrue(wait(lambda: cdp.js(cond, sid)), cond)

    def tick(self, cdp, sid, field, value):
        self.click(cdp, sid, f'[data-fb="{field}"]')
        self.settle(cdp, sid, f"!!document.querySelector('#fbox-{field}')")
        self.assertTrue(cdp.js(f"(() => {{ const i = [...document.querySelectorAll('#fbox-{field} input[type=checkbox]')].find(x => x.value === {json.dumps(value)}); if (!i) return false; i.click(); return true; }})()", sid), value)

    # -- what the file holds
    def test_only_the_clients_rows_are_in_the_file(self):
        self.assertNotIn(INTERNAL, self.html)
        self.assertNotIn("PUB-A-199", self.html)

    def test_the_owner_and_workstream_options_leave_out_a_hidden_row(self):
        self.assertNotIn(HIDDEN_OWNER, self.html)
        self.assertNotIn(HIDDEN_WS, self.html)
        with chrome() as cdp:
            sid = self.go(cdp, 1400, "light")
            self.click(cdp, sid, "[data-show=all]")
            for field, shown in (("owner", "Ana Lopez"), ("workstream", "Build")):
                self.click(cdp, sid, f'[data-fb="{field}"]')
                self.settle(cdp, sid, f"!!document.querySelector('#fbox-{field}')")
                values = cdp.js(f"[...document.querySelectorAll('#fbox-{field} input[type=checkbox]')].map(i => i.value)", sid)
                self.assertIn(shown, values, f"the {field} options list the client's own rows")
                self.assertFalse([v for v in values if "Hidden" in v], f"a hidden row's {field} is not an option: {values}")
                self.assertNotIn("Hidden", cdp.js(f"document.querySelector('#fbox-{field}').textContent", sid))
                self.click(cdp, sid, f'[data-fb="{field}"]')

    def test_each_control_works(self):
        for width, scheme in VARIANTS:
            with self.subTest(width=width, scheme=scheme), chrome() as cdp:
                sid = self.go(cdp, width, scheme)
                open_ids = self.ids(cdp, sid)
                self.assertNotIn("PUB-A-104", open_ids, "a closed row is not in Open")
                self.assertNotIn("PUB-A-199", open_ids)
                # no Client filter, no Freshness, the seven the client gets, a search box and Group by
                fb = cdp.js("[...document.querySelectorAll('.fbar .fbtn')].map(b => b.dataset.fb)", sid)
                self.assertEqual(fb, ["workstream", "status", "due", "owner", "priority", "use_case", "milestone"])
                self.assertTrue(cdp.js("!!document.querySelector('#q') && !!document.querySelector('#group-by')", sid))
                self.assertFalse(cdp.js("!!document.querySelector('.tag.cl')", sid), "no eye or client tag on a client's own page")
                # type switch and Open / Closed / All, with counts
                self.click(cdp, sid, "[data-show=closed]")
                self.settle(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length === 3")
                self.assertEqual(sorted(self.ids(cdp, sid)), CLOSED)
                self.click(cdp, sid, "[data-show=all]")
                self.assertTrue(wait(lambda: self.count(cdp, sid) == len(open_ids) + len(CLOSED)))
                self.click(cdp, sid, "[data-show=open]")
                self.click(cdp, sid, "[data-type=risk]")
                self.settle(cdp, sid, "[...document.querySelectorAll('#work-list tr[data-id]')].every(r => r.dataset.kind !== 'action')")
                self.click(cdp, sid, "[data-type=all]")
                self.assertTrue(wait(lambda: self.ids(cdp, sid) == open_ids))
                # a second filter opens with one click; nothing moves
                before = self.spots(cdp, sid)
                # Where a scrollbar takes room (Linux, Windows; headless Chrome on a Mac draws none, so this cannot be seen moving
                # there), the centred page would shift when a filter shortens the list and the bar goes: its room is kept.
                self.assertEqual(cdp.js("getComputedStyle(document.documentElement).scrollbarGutter", sid), "stable")
                self.tick(cdp, sid, "owner", "Ana Lopez")
                self.settle(cdp, sid, "!!document.querySelector('[data-chip=owner]')")
                self.assertTrue(all(self.ids(cdp, sid)) and self.count(cdp, sid) == 2)
                self.click(cdp, sid, '[data-fb="priority"]')
                self.settle(cdp, sid, "!!document.querySelector('#fbox-priority') && !document.querySelector('#fbox-owner')")
                self.assertEqual(self.spots(cdp, sid), before, "nothing moved when the filters were clicked")
                self.assertTrue(cdp.js("!!document.querySelector('.fbtn[data-fb=owner].on')", sid), "a dot on an active filter")
                self.click(cdp, sid, '[data-fb="priority"]')
                # chip removes one filter
                self.click(cdp, sid, '[data-fx="owner"]')
                self.assertTrue(wait(lambda: self.ids(cdp, sid) == open_ids))
                # search
                self.tick(cdp, sid, "workstream", "Build")
                self.settle(cdp, sid, "!!document.querySelector('[data-chip=workstream]')")
                typed = "const q = document.querySelector('#q'); q.value = %s; q.dispatchEvent(new Event('input', {bubbles: true}));"
                cdp.js("(() => {" + typed % json.dumps("CRANE") + "})()", sid)
                self.settle(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length === 1")
                self.assertEqual(self.ids(cdp, sid), ["PUB-A-102"])
                self.assertEqual(self.spots(cdp, sid), before, "nothing moved when the client searched")
                # Clear all clears the filters and the search, and keeps the type and Open / Closed / All
                self.click(cdp, sid, "[data-show=all]")
                self.click(cdp, sid, "#clearAll")
                self.settle(cdp, sid, "document.querySelector('#q').value === '' && !document.querySelector('.fchip')")
                self.assertTrue(wait(lambda: self.count(cdp, sid) == len(open_ids) + len(CLOSED)), "All is kept")
                self.assertEqual(cdp.js("document.querySelector('[data-show=all]').getAttribute('aria-pressed')", sid), "true")
                # search reads the update text and the id, in any case
                cdp.js("(() => {" + typed % json.dumps("note 101") + "})()", sid)
                self.settle(cdp, sid, "document.querySelectorAll('#work-list tr[data-id]').length === 1")
                self.assertEqual(self.ids(cdp, sid), ["PUB-A-101"])
                cdp.js("(() => {" + typed % json.dumps("zzz-nothing") + "})()", sid)
                self.settle(cdp, sid, "!!document.querySelector('#work-list .empty')")
                self.click(cdp, sid, "#clearAll2")
                self.settle(cdp, sid, "document.querySelector('#q').value === ''")

    def test_group_by(self):
        with chrome() as cdp:
            sid = self.go(cdp, 1400, "light")
            self.click(cdp, sid, "#group-by")
            self.settle(cdp, sid, "!!document.querySelector('[role=menuitem][data-kind=owner]')")
            self.click(cdp, sid, "[role=menuitem][data-kind=owner]")
            self.settle(cdp, sid, "[...document.querySelectorAll('tr.grp')].some(t => /Ana Lopez/.test(t.textContent))")
            heads = cdp.js("[...document.querySelectorAll('tr.grp th')].map(t => t.textContent)", sid)
            self.assertTrue(any("Bo Chen" in h for h in heads))
            self.click(cdp, sid, "#group-by")
            self.settle(cdp, sid, "!!document.querySelector('[role=menuitem][data-kind=nothing]')")
            self.click(cdp, sid, "[role=menuitem][data-kind=nothing]")
            self.settle(cdp, sid, "!document.querySelector('tr.grp')")

    def test_choices_are_remembered_in_the_pages_own_key(self):
        with chrome() as cdp:
            sid = self.go(cdp, 1400, "light")
            self.click(cdp, sid, "[data-show=all]")
            self.tick(cdp, sid, "owner", "Bo Chen")
            self.settle(cdp, sid, "!!document.querySelector('[data-chip=owner]')")
            self.click(cdp, sid, "#group-by")
            self.settle(cdp, sid, "!!document.querySelector('[data-kind=status]')")
            self.click(cdp, sid, "[data-kind=status]")
            cdp.js("(() => { const q = document.querySelector('#q'); q.value = 'crane'; q.dispatchEvent(new Event('input', {bubbles: true})); })()", sid)
            self.settle(cdp, sid, "!!localStorage.getItem('clark.work.PUB') && /status/.test(localStorage.getItem('clark.work.PUB'))")
            kept = json.loads(cdp.js("localStorage.getItem('clark.work.PUB')", sid))
            self.assertEqual(sorted(kept), ["filters", "group", "mode", "not", "type", "v"])
            self.assertNotIn("crane", json.dumps(kept).lower(), "the search words are not kept")
            self.assertIsNone(cdp.js("localStorage.getItem('clark.work.v1')", sid), "the editor's key is not written")
            # open the file again with a bare address, as a new visit (an empty page first, so no earlier page is still running and
            # no hash change redraws the old one with no filters while it saves): the choices come back, the search does not
            cdp.call("Page.navigate", {"url": "about:blank"}, sid)
            self.settle(cdp, sid, "location.href === 'about:blank'")
            cdp.call("Page.navigate", {"url": self.path.as_uri() + "#work"}, sid)
            self.settle(cdp, sid, "!!document.querySelector('#work-list') && !!document.querySelector('[data-chip=owner]')")
            self.assertEqual(cdp.js("document.querySelector('[data-show=all]').getAttribute('aria-pressed')", sid), "true")
            self.assertEqual(cdp.js("document.querySelector('#q').value", sid), "")
            self.assertTrue(cdp.js("[...document.querySelectorAll('#work-list tr[data-id]')].every(r => /Bo Chen/.test(r.textContent))", sid))

    def test_a_damaged_kept_choice_gives_the_start_page(self):
        for bad in ("{", "[]", "null", json.dumps({"v": 2}), json.dumps({"v": 1, "group": [], "type": {}, "mode": 5, "filters": {"owner": ["Gone"]}})):
            with self.subTest(bad=bad), chrome() as cdp:
                sid = open_page(cdp, self.path.as_uri() + "#work", 1400, "light")
                self.settle(cdp, sid, "!!document.querySelector('#work-list')")
                cdp.js(f"localStorage.setItem('clark.work.PUB', {json.dumps(bad)})", sid)
                cdp.call("Page.reload", {}, sid)
                self.settle(cdp, sid, "!!document.querySelector('#work-list')")
                self.assertEqual(self.count(cdp, sid), 6, "the start page: every open row")
                self.assertFalse(cdp.js("!!document.querySelector('.fchip')", sid))


class ModelMatchesPage(unittest.TestCase):
    """The reference model (client_filters.py) and the page's own functions (filters.js, workItems.js, clientView.js, bundled and run
    in Chrome) give the same ids and the same Open / Closed / All and type counts for every case in the shared cases file."""
    PAGE_DIM = {"ws": "workstream", "status": "status", "due": "due", "owner": "owner", "priority": "priority", "uc": "use_case",
                "ms": "milestone"}
    PAGE_TYPE = {"all": "all", "A": "action", "R": "risk", "D": "decision"}

    def test_every_case_gives_the_same_answer(self):
        need_chrome()
        f = json.loads((ROOT / "tests" / "fixtures" / "client-filter-cases.json").read_text(encoding="utf-8"))
        entry = Path(tempfile.mkdtemp(prefix="clark-parity-")) / "entry.js"
        src = ROOT / "src" / "clark" / "page" / "src"
        entry.write_text(f'export * from "{src / "filters.js"}"; export {{ rowsOf }} from "{src / "workItems.js"}"; '
                         f'export {{ searchIndex, searchRows, normalise }} from "{src / "clientView.js"}";\n', encoding="utf-8")
        script = bundled(entry, "P") + """;
        window.run = (data, today, st) => {
          P.setPublished(true);
          const rows = P.rowsOf(data), index = P.searchIndex(data);
          const state = P.normalise(st, rows, today);
          const hit = P.searchRows(rows, index, st.q || "");
          const s = { mode: state.mode, type: state.type, filters: state.filters, not: state.not };
          const ids = P.applyFilters(hit, s, today).map((r) => r.id);
          return { ids, show: P.counts(hit, s, today), type: P.typeCounts(hit, s, today), filters: state.filters };
        }; true"""
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": script, "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            for c in f["cases"]:
                want = c["expect"]
                st = {"type": self.PAGE_TYPE[c["state"].get("type", "all")], "mode": c["state"].get("show", "open"),
                      "filters": {self.PAGE_DIM[k]: v for k, v in c["state"].get("f", {}).items()},
                      "not": {self.PAGE_DIM[k]: v for k, v in c["state"].get("not", {}).items()}, "q": c["state"].get("q", "")}
                got = cdp.js(f"window.run({json.dumps(f['published'])}, {json.dumps(f['today'])}, {json.dumps(st)})", sid)
                with self.subTest(state=c["state"]):
                    self.assertEqual(sorted(got["ids"]), sorted(i["id"] for i in want["items"]))
                    self.assertEqual(got["show"], want["counts"]["show"])
                    self.assertEqual({self.PAGE_TYPE[k]: v for k, v in want["counts"]["type"].items()}, got["type"])
                    self.assertEqual(sorted(got["filters"]), sorted(self.PAGE_DIM[k] for k in want["state"]["f"]),
                                     "a stale choice is dropped on both sides")


if __name__ == "__main__":
    unittest.main()
