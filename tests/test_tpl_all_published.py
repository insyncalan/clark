"""#96, every section template together: a project with one of each of the eighteen filled in, beside a hidden, an archived and a
Sensitive work item, is published; the file holds only what the rules allow, and the served View (the Local View) shows each
template section with the same words as the file draws.

Run: python3 dev/run_tests.py test_tpl_all_published
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from _demo import USER
from _pictures import GOOD
from test_report_editor import EMPTY_BRANDING, Base, Pg, tearDownModule  # noqa: F401
from test_server import chrome

from clark import publish, section_kinds
from clark import store as store_module

AS_AT = "2030-01-15"
HIDDEN, ARCHIVED, SENSITIVE = "ZQ-ALL-HIDDEN", "ZQ-ALL-ARCHIVED", "ZQ-ALL-SENSITIVE"     # never in the file or the served View
KEPT, RISK, MILESTONE = "Fictional kept action", "Fictional kept risk", "Fictional pilot go-live"
# Dates that read the same on any day from now to past AS_AT, so the served View (today) and the file (AS_AT) agree:
OVERDUE, LATER = "2025-01-01", "2031-02-01"


class AllTemplates(Base):
    def setUp(self):
        super().setUp()
        d = self.demo
        self.kept = d.action(description=KEPT, due_date=OVERDUE)
        self.hid = d.action(description=HIDDEN, due_date=OVERDUE)
        self.arc = d.action(description=ARCHIVED, due_date=OVERDUE)
        self.secret = d.action(description=SENSITIVE, due_date=OVERDUE)
        with self.store.step("dashboard", USER) as st:
            st.create("report_hidden", {"project": "ABC", "item_id": self.hid})
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": RISK, "raised": "2026-10-01", "source": "demo",
                                           "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
            self.ms = st.create("milestones", {"project": "ABC", "name": MILESTONE, "baseline_date": LATER, "source": "demo"})
        self.store.con.execute("INSERT OR IGNORE INTO item_labels (item_id, label) VALUES (?, 'Sensitive')", (self.secret,))
        self.store.con.commit()
        with self.store.step("dashboard", USER) as st:
            st.archive("actions", self.arc)
        gone = [self.hid, self.arc, self.secret]
        self.bodies = {
            "textimage": {"v": 1, "words": ["Fictional site visit on Tuesday."], "caption": "Fictional hall", "alt": "The new hall", "pictures": {"image": GOOD}},
            "headline": {"v": 1, "words": "Fictional pilot is live in all three regions.", "label": "Read the plan", "href": "https://example.org/plan"},
            "figures4": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"}, {"mode": "live", "metric": "risks"},
                                             {"mode": "typed", "label": "Budget used", "value": "62%", "detail": "of the approved budget", "asof": "2030-01-10"},
                                             {"mode": "typed", "label": "Sites ready", "value": "3", "detail": "of four", "asof": "2030-01-10"}]},
            "figures3": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"},
                                             {"mode": "typed", "label": "Users trained", "value": "120", "detail": "this month", "asof": "2030-01-10"},
                                             {"mode": "live", "metric": "decisions"}]},
            "gallery": {"v": 1, "items": {"1": {"caption": "Fictional room one", "alt": "A room"}}, "pictures": {"1": GOOD}},
            "table": {"v": 1, "cols": ["Item", "Owner"], "rows": [["Fictional scope", "Sam Example"]], "caption": "Fictional table."},
            "doclinks": {"v": 1, "items": [{"kind": "link", "href": "https://example.org/plan", "label": "The plan"}]},
            "linkcard": {"v": 1, "href": "https://example.org/dashboards/pilot", "title": "Pilot dashboard", "site": "Example Analytics",
                         "text": ["Updated every Monday."]},
            "raid3": {"v": 1, "cards": [{"id": i, "source": "client"} for i in (self.kept, self.hid, self.secret)]},
            "raid4": {"v": 1, "cards": [{"id": i, "source": "client"} for i in (self.risk, self.arc, self.kept, self.hid)]},
            "workitems": {"v": 1},
            "callout": {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words about the budget."]},
            "imagecap": {"v": 1, "caption": "Fictional plan", "alt": "A plan", "pictures": {"image": GOOD}},
            "quote": {"v": 1, "quote": "Fictional words of thanks.", "by": "Sam Example", "role": "Fictional sponsor"},
            "contacts": {"v": 1, "people": [{"name": "Sam Example", "role": "Fictional lead", "email": "sam@example.org", "phone": "+44 20 7946 0000"}]},
            "checklist": {"v": 1, "items": [{"item": self.kept}, *({"item": i} for i in gone), {"text": "Fictional typed line", "done": 1}]},
            "keydates": {"v": 1, "items": [{"milestone": self.ms}, {"label": "Fictional typed date", "date": LATER}]},
            "onedoc": {"v": 1, "file": {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2048}, "label": "The signed SOW",
                       "text": ["Signed on 12-01-2030."]},
        }
        self.assertEqual(set(self.bodies), set(section_kinds.TYPES), "one of every template")
        self.refs = {}
        with self.store.step("dashboard", USER) as st:
            for n, (kind, value) in enumerate(self.bodies.items()):
                self.refs[kind] = st.create("report_sections", {
                    "project": "ABC", "type": kind, "title": f"Fictional {kind} section", "sort_order": 900 + n,
                    "body": store_module.check_section_body(kind, json.dumps(value))})
        self.out = tempfile.mkdtemp(prefix="clark-96-all-")
        self.addCleanup(shutil.rmtree, self.out, ignore_errors=True)

    def build(self):
        return publish.build(self.store, "ABC", now=AS_AT)

    def test_the_file_holds_every_template_and_only_what_the_rules_allow(self):
        built = self.build()
        text = built["body"].decode("utf-8")
        published = built["published"]
        kinds = {s["type"]: s for s in published["sections"] if s["type"] in section_kinds.TYPES}
        self.assertEqual(set(kinds), set(section_kinds.TYPES), "every filled template is in the file")
        for mark in (HIDDEN, ARCHIVED, SENSITIVE, self.hid, self.arc, self.secret):
            self.assertNotIn(mark, text, mark)
        for kept in (KEPT, RISK, MILESTONE, self.kept, self.risk):
            self.assertIn(kept, text, kept)
        self.assertEqual([r["id"] for r in published["data"]["actions"]], [self.kept], "the file carries the one action the rules allow")
        self.assertEqual([c["id"] for c in kinds["raid3"]["cards"]], [self.kept])
        self.assertEqual([c["id"] for c in kinds["raid4"]["cards"]], [self.risk, self.kept])
        self.assertEqual(kinds["checklist"]["items"], [{"item": self.kept}, {"text": "Fictional typed line", "done": 1}])
        for kind in ("textimage", "gallery", "imagecap"):
            self.assertIn(GOOD, json.dumps(kinds[kind]), f"{kind}: its picture is in the file")
        for never in ("/api/section-image", "/api/section-file", "/api/section-body", "/api/change"):      # the routes that change things are never in the file
            self.assertNotIn(never, text, never)

    def draw_file(self, cdp):
        path = Path(publish.publish(self.store, "ABC", self.out, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)["path"])
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        return p

    def words(self, p):
        """Each template section's words, by id, with white space folded. How late a work item is counts from the day it is read
        (the served View: today; the file: its as-at day), so that count is folded too."""
        got = p.js("(function(refs){ try { return JSON.stringify(Object.fromEntries(refs.map(function(id){"
                   " var e = document.querySelector('[data-id=\"' + id + '\"]');"
                   " return [id, e ? e.textContent.replace(/\\s+/g, ' ').replace(/\\d+ days? late/g, 'N days late').trim() : null]; }))); }"
                   " catch (x) { return 'ERROR ' + x.message; } })("
                   + json.dumps(sorted(self.refs.values())) + ")")
        self.assertFalse(str(got).startswith("ERROR"), got)
        return json.loads(got)

    def test_the_local_view_shows_what_the_file_shows(self):
        with chrome() as cdp:
            served = self.visit(cdp)
            served.until(f"!!document.querySelector('[data-id={json.dumps(self.refs['onedoc'])}]')", "the served View drew the templates")
            view = self.words(served)
            report = served.js("document.querySelector('#report').textContent")
        with chrome() as cdp:
            drawn = self.words(self.draw_file(cdp))
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind):
                self.assertTrue(drawn[ref], f"{kind} is drawn in the file")
                self.assertEqual(view[ref], drawn[ref], f"{kind}: the served View and the file say the same")
        for mark in (HIDDEN, ARCHIVED, SENSITIVE):
            self.assertNotIn(mark, report, f"{mark} is not in the served View")
        self.assertIn(KEPT, report)


if __name__ == "__main__":
    unittest.main()
