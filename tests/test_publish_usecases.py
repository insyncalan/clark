"""The Use Cases tab in the published file, in the style of test_publish.

Run: python3 dev/run_tests.py test_publish_usecases
The rule lives in publish.client_use_cases; select calls it. Each dropped thing carries a marker (ZQ-...) that is searched for in
the finished file's bytes in the four spellings (fx.spellings). The browser test opens the file from file:// at 1400 and 900 px,
light and dark.
"""
import copy
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT

import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402
from test_publish import EMPTY_BRANDING, block, chrome, opened, wait  # noqa: E402
import test_server  # noqa: E402,F401  (this file drives Chrome through test_publish: it is in the browser tier)

MARKERS = {
    "archived_uc": ("PUB-U-004", "ZQ-ARCHIVED-USECASE"),
    "hidden_uc": ("PUB-U-005", "ZQ-REPORT-HIDDEN-USECASE"),
    "off_step": ("PUB-A-020", "ZQ-OFF-STEP"),
    "sensitive_step": ("PUB-A-021", "ZQ-SENSITIVE-STEP"),
    "hidden_ms": ("PUB-M-005", "ZQ-HIDDEN-USECASE-MILESTONE"),
    "note": (None, "ZQ-STEP-INTERNAL-NOTE"),
    "history": (None, "ZQ-USECASE-HISTORY"),
}


def planted(plant):
    """Add to the plant what the Use Cases tab must not carry; every id above is new, so the plant's other tests are untouched."""
    d = plant["data"]
    base = {k: copy.deepcopy(d[k][0]) for k in ("use_cases", "actions", "milestones")}

    def add(table, id_, **over):
        row = copy.deepcopy(base[table])
        row.update(id=id_, **over)
        d[table].append(row)

    add("use_cases", "PUB-U-004", title=MARKERS["archived_uc"][1], archived=1, sort_order=4)
    add("use_cases", "PUB-U-005", title=MARKERS["hidden_uc"][1], sort_order=5)
    plant["hidden"].append("PUB-U-005")
    add("actions", "PUB-A-020", description=MARKERS["off_step"][1], client_message=None, client_visible=0, use_case="PUB-U-001", milestone=None)
    add("actions", "PUB-A-021", description=MARKERS["sensitive_step"][1], client_message=None, use_case="PUB-U-001", milestone=None)
    d["labels"]["PUB-A-021"] = ["Sensitive"]
    add("milestones", "PUB-M-005", name=MARKERS["hidden_ms"][1], client_visible=0)
    add("actions", "PUB-A-022", description="ZQ-KEEP-STEP-OF-HIDDEN-MILESTONE", client_message=None, use_case="PUB-U-001", milestone="PUB-M-005")
    d["actions"][0]["internal_note"] = MARKERS["note"][1]
    plant["changes"].append({"at": "2026-10-20 09:00:00", "apply_id": 1, "tbl": "use_cases", "item_id": "PUB-U-001",
                             "field": "headline", "old_value": MARKERS["history"][1], "new_value": "Going to plan", "op": "update",
                             "via": "test"})
    for key, (id_, marker) in MARKERS.items():
        plant["markers"][key] = marker
        if id_:
            plant["markers"][id_] = marker


def made(mutate=planted, hide_use_cases=False):
    plant = fx.load()
    mutate(plant)
    if hide_use_cases:
        for s in plant["sections"]:
            if s["type"] == "usecases":
                s["hidden"] = 1
    pub = publish.select(fx.inputs(plant))
    return plant, pub, publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])


class Absent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plant, cls.pub, cls.text = made()

    def assertAbsent(self, *keys):
        for key in keys:
            marker = self.plant["markers"][key]
            for spelling in fx.spellings(marker) + [marker.split()[0]]:
                self.assertNotIn(spelling, self.text, f"{key}: {spelling!r} is in the file")
            self.assertNotIn(marker.lower(), self.text.lower(), key)
            if re.fullmatch(r"PUB-[A-Z0-9-]+", key):
                self.assertNotIn(key, self.text, f"the id {key} is in the file")

    def test_use_case_with_the_eye_off(self):
        self.assertAbsent("PUB-U-002")

    def test_archived_use_case(self):
        self.assertAbsent("archived_uc", "PUB-U-004")

    def test_sensitive_use_case(self):
        self.assertAbsent("PUB-U-003")

    def test_report_hidden_use_case(self):
        self.assertAbsent("hidden_uc", "PUB-U-005")

    def test_next_step_that_is_not_client_visible(self):
        self.assertAbsent("off_step", "PUB-A-020")

    def test_sensitive_next_step(self):
        self.assertAbsent("sensitive_step", "PUB-A-021")

    def test_milestone_that_is_not_client_visible(self):
        self.assertAbsent("hidden_ms", "PUB-M-005")
        steps = {p["id"]: p for p in self.pub["data"]["use_case_pages"]}["PUB-U-001"]
        self.assertIn("PUB-A-022", steps["next_steps"], "its step is shown; only the milestone is not")
        self.assertNotIn("PUB-M-005", steps["milestones"])
        self.assertIsNone(next(a for a in self.pub["data"]["actions"] if a["id"] == "PUB-A-022")["milestone"])

    def test_internal_note_on_a_next_step(self):
        self.assertAbsent("note")

    def test_history_text_of_a_use_case(self):
        self.assertAbsent("history")

    def test_everything_when_the_section_is_hidden(self):
        _, pub, text = made(hide_use_cases=True)
        self.assertNotIn("usecases", pub["tabs"])
        self.assertEqual(pub["data"]["use_case_pages"], [])
        self.assertEqual(pub["data"]["use_cases"], [])
        self.assertEqual(block(text)["tabs"], ["dashboard", "work", "milestones", "clientreport"])
        self.assertNotIn("ZQ-KEEP-USECASE-1", text)
        self.assertNotIn("ZQ-KEEP-STANDING", text)

    def test_no_tab_when_no_use_case_is_on_the_dashboard(self):
        def all_off(plant):
            planted(plant)
            for u in plant["data"]["use_cases"]:
                u["client_visible"] = 0
        _, pub, text = made(all_off)
        self.assertEqual(pub["data"]["use_case_pages"], [])
        self.assertNotIn("usecases", pub["tabs"])
        self.assertEqual(block(text)["tabs"], ["dashboard", "work", "milestones", "clientreport"])
        self.assertNotIn("ZQ-KEEP-USECASE-1", text)

    def test_a_use_case_carries_no_eye_no_history_and_no_note(self):
        allowed = set(publish.PUBLISH_FIELDS["use_cases"])
        for u in self.pub["data"]["use_cases"]:
            self.assertLessEqual(set(u), allowed)
            self.assertNotIn("client_visible", u)
        for f in ("client_visible", "internal_note", "movement", "source", "updated_at", "archived"):
            self.assertNotIn(f, allowed, f)
        self.assertEqual(set(block(self.text)["data"]["use_case_pages"][0]), {"id", "next_steps", "milestones"})

    def test_a_next_step_that_is_closed_is_not_shown(self):
        def closed(plant):
            planted(plant)
            plant["data"]["actions"][0]["status"] = "Closed"
        _, pub, _ = made(closed)
        self.assertEqual(pub["data"]["use_case_pages"], [{"id": "PUB-U-001", "next_steps": ["PUB-A-022"], "milestones": []}], "the closed step and its milestone go")


class Present(unittest.TestCase):
    def test_the_kept_use_case_with_its_step_and_milestone(self):
        plant, pub, text = made()
        self.assertEqual(pub["data"]["use_case_pages"], [{"id": "PUB-U-001", "next_steps": ["PUB-A-001", "PUB-A-022"], "milestones": ["PUB-M-001"]}])
        self.assertEqual([u["id"] for u in pub["data"]["use_cases"]], ["PUB-U-001"])
        for kept in ("ZQ-KEEP-USECASE-1", "ZQ-KEEP-STANDING", "ZQ-KEEP-ACTION-1", "ZQ-KEEP-MESSAGE-1", "ZQ-KEEP-MILESTONE-1"):
            self.assertIn(kept, text, kept)
        self.assertEqual(block(text)["data"]["use_case_pages"], pub["data"]["use_case_pages"])

    def test_rule_is_one_function_and_select_calls_it(self):
        plant = fx.load()
        planted(plant)
        d = fx.inputs(plant)
        pages = publish.client_use_cases(d["data"], "PUB", d["hidden"], d["label_rules"], ())
        self.assertEqual(pages, publish.select(d)["data"]["use_case_pages"])
        self.assertEqual(publish.client_use_cases(d["data"], "PUB", d["hidden"], d["label_rules"], ("usecases",)), [])
        self.assertEqual(publish.client_use_cases(d["data"], "OTHER", d["hidden"], d["label_rules"], ()), [])

    def test_tab_order(self):
        _, pub, text = made()
        self.assertEqual(pub["tabs"], ["dashboard", "work", "milestones", "usecases", "clientreport"])
        self.assertEqual(block(text)["tabs"], pub["tabs"])
        router = (ROOT / "src/clark/page/src/router.js").read_text(encoding="utf-8")
        self.assertIn('VIEWS = ["dashboard", "work", "milestones", "usecases", "clientreport", "settings"]', router)
        self.assertIn('get usecases() { return fromFile.value ? "Use Cases" : "Use cases"; }', (ROOT / "src/clark/page/src/stores/report.js").read_text(encoding="utf-8"))

    def test_the_page_has_no_route(self):
        source = (ROOT / "src/clark/page/src/components/UseCasesTab.jsx").read_text(encoding="utf-8")
        self.assertNotRegex(source, r"api\.js|fetch|XMLHttpRequest|/api/|http|location|history|Edit|edit")
        view = (ROOT / "src/clark/page/page-view.html").read_text(encoding="utf-8")
        self.assertEqual(set(re.findall(r"/api/[a-z]+", view)), {"/api/projects", "/api/data"},
                         "the page names the two read routes it always had and no other")

    def test_the_publish_scan_still_passes(self):
        plant, pub, text = made()
        publish.check_brand(text)                           # raises PublishError if the file names a brand it should not
        self.assertEqual(publish.outside_addresses(publish.without_data_block(text)), [])
        self.assertLess(len(text.encode("utf-8")), publish.MAX_BYTES)


class Hostile(unittest.TestCase):
    def test_hostile_text_is_cleaned(self):
        def hostile(plant):
            u = plant["data"]["use_cases"][0]
            u["title"] = "A<script>zq=1</script>‮B​C аdmin"      # markup, a bidi override, a zero-width space, a look-alike a
            u["headline"] = "<img src=x onerror=zq()> " + "long " * 2000
            u["standing"] = '<p onclick="zq()">s</p><a href="javascript:zq()">x</a><script>zq()</script>'
            u["ref"] = "1.1⁦"
        _, pub, text = made(hostile)
        u = pub["data"]["use_cases"][0]
        for f in ("title", "headline", "ref"):
            self.assertNotRegex(u[f], "[‮​⁦]", f)
        self.assertLessEqual(len(u["headline"]), publish.REASON_LIMIT)
        self.assertEqual(u["standing"].count("<script"), 0)
        self.assertNotIn("onclick", u["standing"])
        self.assertNotIn("javascript:", u["standing"])
        self.assertIn("аdmin", u["title"], "look-alike letters stay as text; they are not markup")
        data = re.search(r'<script type="application/json" id="clark-data">(.*?)</script>', text, re.S).group(1)
        self.assertNotRegex(data, r"[<>&]")
        self.assertEqual(len(publish.csp_hashes(text)["script"]), 1)
        self.assertEqual(block(text)["data"]["use_cases"][0]["title"], u["title"])


class RealBrowser(unittest.TestCase):
    def test_the_tab_opens_and_fits_at_1400_and_900_light_and_dark(self):
        plant, pub, text = made()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "r.html"
            path.write_text(text, encoding="utf-8")
            with chrome() as cdp:
                sid = opened(cdp, path.as_uri())
                self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
                self.assertEqual(cdp.js("[...document.querySelectorAll('.tab')].map(t => t.textContent).join()", sid),
                                 "Dashboard,Work items,Milestones,Use Cases,Weekly snapshotSnapshot")   # the last tab holds its wide and its narrow name
                cdp.js("document.querySelector('[data-view=usecases]').click()", sid)
                self.assertTrue(wait(lambda: cdp.js("document.querySelector('h1').textContent", sid) == "Use Cases"))
                cdp.js("document.querySelector('.ucp summary').click()", sid)
                body = cdp.js("document.querySelector('.ucp-body').innerText", sid)
                for word in ("ZQ-KEEP-STANDING", "Next steps", "ZQ-KEEP-MESSAGE-1", "Milestones", "ZQ-KEEP-MILESTONE-1"):
                    self.assertIn(word, body)
                self.assertEqual(cdp.js("document.querySelectorAll('.ucp').length", sid), 1)
                for width in (1400, 900):
                    for scheme in ("light", "dark"):
                        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                        self.assertTrue(wait(lambda: cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid)),
                                        f"no sideways scroll at {width} px, {scheme}")
                        self.assertTrue(cdp.js("(r => r.left >= 0 && r.right <= window.innerWidth)"
                                               "(document.querySelector('.ucp-body').getBoundingClientRect())", sid))
                self.assertEqual(cdp.js("window.violations", sid), [])


if __name__ == "__main__":
    unittest.main()
