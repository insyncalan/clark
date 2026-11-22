"""Row 1251, ruling 3: a freshly added empty section of every template type is LEFT OUT of the published report (the file, and the
served View) and appears once it has content. Each section is added through the real change route the way the Add a section box
sends it (type and title, no body), so what is proved is what a person who adds a template and publishes at once gets.

Run: python3 dev/run_tests.py test_tpl_fresh_left_out
Needs Chrome (the harness): the page tests fail, never skip, without it. Fictional data only. Tests only, no source change.
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

from clark import changes, publish, section_kinds

AS_AT = "2030-01-15"
ANCHOR = "Fictional anchor section"
TYPES = (*section_kinds.TYPES, "text")


class FreshLeftOut(Base):
    def setUp(self):
        super().setUp()
        d = self.demo
        d.plant_builtin_sections()      # a new project's lists are Work items lists; these templates sit with the built-in sections (row 1193)
        self.act = d.action(description="Fictional kept action", due_date="2031-02-01")
        with self.store.step("dashboard", USER) as st:
            self.risk = st.create("raid", {"project": "ABC", "type": "Risk", "description": "Fictional kept risk", "raised": "2026-10-01",
                                           "source": "demo", "impact": "High", "likelihood": "High", "owner": "Pat Demo"})
            self.ms = st.create("milestones", {"project": "ABC", "name": "Fictional go-live", "baseline_date": "2031-02-01", "source": "demo"})
        self.content = {
            "text": "<p>Fictional words for the text section.</p>",
            "textimage": {"v": 1, "words": ["Fictional site visit."], "caption": "Fictional hall", "alt": "The hall", "pictures": {"image": GOOD}},
            "headline": {"v": 1, "words": "Fictional pilot is live."},
            "figures4": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"}, {"mode": "live", "metric": "risks"},
                                             {"mode": "typed", "label": "Budget used", "value": "62%", "detail": "of budget", "asof": "2030-01-10"},
                                             {"mode": "typed", "label": "Sites ready", "value": "3", "detail": "of four", "asof": "2030-01-10"}]},
            "figures3": {"v": 1, "figures": [{"mode": "live", "metric": "overdue"},
                                             {"mode": "typed", "label": "Users trained", "value": "120", "detail": "this month", "asof": "2030-01-10"},
                                             {"mode": "live", "metric": "decisions"}]},
            "gallery": {"v": 1, "items": {"1": {"caption": "Fictional room one", "alt": "A room"}}, "pictures": {"1": GOOD}},
            "table": {"v": 1, "cols": ["Item", "Owner"], "rows": [["Fictional scope", "Sam Example"]], "caption": "Fictional table."},
            "doclinks": {"v": 1, "items": [{"kind": "link", "href": "https://example.org/plan", "label": "The plan"}]},
            "linkcard": {"v": 1, "href": "https://example.org/dashboards/pilot", "title": "Pilot dashboard", "site": "Example Analytics",
                         "text": ["Updated every Monday."]},
            "raid3": {"v": 1, "cards": [{"id": self.act, "source": "client"}]},
            "raid4": {"v": 1, "cards": [{"id": self.risk, "source": "client"}]},
            "workitems": {"v": 1},
            "callout": {"v": 1, "tone": "decision", "title": "Fictional decision", "paras": ["Fictional words about the budget."]},
            "imagecap": {"v": 1, "caption": "Fictional plan", "alt": "A plan", "pictures": {"image": GOOD}},
            "quote": {"v": 1, "quote": "Fictional words of thanks.", "by": "Sam Example", "role": "Fictional sponsor"},
            "contacts": {"v": 1, "people": [{"name": "Sam Example", "role": "Fictional lead", "email": "sam@example.org", "phone": "+44 20 7946 0000"}]},
            "checklist": {"v": 1, "items": [{"item": self.act}, {"text": "Fictional typed line", "done": 1}]},
            "keydates": {"v": 1, "items": [{"milestone": self.ms}, {"label": "Fictional typed date", "date": "2031-02-01"}]},
            "reportheadline": {"v": 1, "health": "on_track", "headline": "Fictional pilot is on track.", "sentence": "Fictional sentence."},
            "onedoc": {"v": 1, "file": {"name": "Signed SOW.pdf", "rel": "Report files/Signed SOW.pdf", "bytes": 2048}, "label": "The signed SOW",
                       "text": ["Signed on 12-01-2030."]},
            "glancetemplate": {"v": 1, "bespoke": [{"id": "t1", "label": "Fictional tile", "figure": "3"}]},
        }
        self.assertEqual(set(self.content), set(TYPES), "one of every template type, and text")
        self.anchor = self.new("text", ANCHOR)
        self.fill(self.anchor, self.content["text"])
        self.refs = {kind: self.new(kind, f"Fictional fresh {kind}") for kind in TYPES}
        self.image = changes.make_section_image(self.store.path, [], USER)

    def new(self, kind, title):
        status, body = self.real_change({"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": kind, "title": title}, "after": None})
        self.assertEqual((status, body.get("message")), (200, None), body)
        return body["ref"]

    def fill(self, ref, value):
        text = value if isinstance(value, str) else json.dumps(value)
        status, body = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"body": text}})
        self.assertEqual((status, body.get("message")), (200, None), body)

    def fill_all(self):
        """Words through the body, then a picture through the picture route (a body never carries one)."""
        for kind, ref in self.refs.items():
            value = self.content[kind]
            if isinstance(value, dict) and "pictures" in value:
                value = {k: v for k, v in value.items() if k != "pictures"}
            self.fill(ref, value)
        for kind, slot in (("textimage", "image"), ("gallery", "1"), ("imagecap", "image")):
            status, body = self.image({"project": "ABC", "section": self.refs[kind], "slot": slot, "image": GOOD, "place": "report"})
            self.assertEqual((status, body.get("message")), (200, None), body)

    def in_file(self):
        built = publish.build(self.store, "ABC", now=AS_AT)
        return {s["id"] for s in built["published"]["sections"]}, built["body"].decode("utf-8")

    def drawn(self, cdp):
        out = tempfile.mkdtemp(prefix="clark-1251b-")
        self.addCleanup(shutil.rmtree, out, ignore_errors=True)
        path = Path(publish.publish(self.store, "ABC", out, by_user=USER, now=AS_AT, branding=EMPTY_BRANDING)["path"])
        tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, sid)
        cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
        p = Pg(self, cdp, sid)
        p.until("document.documentElement.dataset.ready === '1' && !!document.querySelector('h1')", "the file drew")
        return p

    def present(self, p):
        """Which of the template sections (by type) the page draws, once the anchor section has drawn."""
        p.until(f"!!document.querySelector('[data-id={json.dumps(self.anchor)}]')", "the anchor section drew")
        return {kind for kind, ref in self.refs.items() if p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')")}

    def test_the_file_leaves_every_fresh_empty_section_out_and_has_each_once_filled(self):
        ids, text = self.in_file()
        self.assertIn(self.anchor, ids, "the filled anchor is in the file")
        for kind, ref in self.refs.items():
            if kind == "text":
                continue       # a fresh Text section is in the file's data with its title and no body, and is not drawn: see the drawn-file test
            with self.subTest(kind=kind, state="fresh"):
                self.assertNotIn(ref, ids)
                self.assertNotIn(f"Fictional fresh {kind}", text)
        self.fill_all()
        ids, text = self.in_file()
        for kind, ref in self.refs.items():
            with self.subTest(kind=kind, state="filled"):
                self.assertIn(ref, ids)

    def test_the_served_view_leaves_every_fresh_empty_section_out_and_draws_each_once_filled(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(self.present(p) - {"text"}, set(), "fresh: none of them is drawn in the View")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(self.refs['text'])}] .quiet').textContent"), "Nothing recorded.",
                             "a fresh Text section is the one the View still draws, with its quiet line")
        self.fill_all()
        with chrome() as cdp:
            self.assertEqual(self.present(self.visit(cdp)), set(TYPES), "filled: every one is drawn in the View")

    def test_the_drawn_file_leaves_every_fresh_empty_section_out_and_draws_each_once_filled(self):
        with chrome() as cdp:
            self.assertEqual(self.present(self.drawn(cdp)), set(), "fresh: none of them is drawn in the file")
        self.fill_all()
        with chrome() as cdp:
            self.assertEqual(self.present(self.drawn(cdp)), set(TYPES), "filled: every one is drawn in the file")


if __name__ == "__main__":
    unittest.main()
