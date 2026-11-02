"""#433 The Client Requested Report View in a published file: the weekly snapshot tab.

Run: python3 dev/run_tests.py test_client_report_file
The file carries the tab (named "Weekly snapshot": a client has not asked for anything), reads only what the file holds, and shows
exactly the rows the file kept. Source tests pin the tab rule; the browser test opens the finished file from file:// with no
server, at 1400 and 900 px, light and dark, and reads the page as the client does.
"""
import json
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import _publish_fixture as fx

from clark import page, publish
from test_publish import EMPTY_BRANDING, block, made, opened, tearDownModule  # noqa: F401  (the module's own clean-up of the brand-free folder)
from test_server import chrome, wait
from test_client_report import MODULE
from test_work_items import bundled

NOTHING_FOR_THE_AUTHOR = r"on the Dashboard|Nothing written|Nothing here yet|not built|counts the same|Click to write|Not set|No milestones yet|[Nn]o open risks"


def hide_risks(plant):
    for s in plant["sections"]:
        if s["type"] == "raid":
            s["hidden"] = 1


def shown(pub, editing=False, mutate=None):
    """The ids CR.sectionsShown gives for a published file's data, run by Node (no browser): what the file's view draws."""
    d = {**pub["data"], "report_sections": pub["sections"]}
    if mutate:
        mutate(d)
    expr = f"CR.sectionsShown({json.dumps(d)}, true, {json.dumps(editing)}, {json.dumps(pub['as_at'] or '2026-10-20')})"
    done = subprocess.run(["node", "-e", bundled(MODULE, "CR") + f";console.log(JSON.stringify({expr}))"], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def words(plant):
    """The fixture's text section becomes the Highlights box, and a second one the Planned for next week box."""
    plant["sections"][4]["title"] = "This week"
    plant["sections"][4]["body"] = "<p>ZQ-KEEP-HIGHLIGHT</p>"
    plant["sections"].append({**plant["sections"][4], "id": "s-next", "title": "Next week", "body": "<ul><li>ZQ-KEEP-NEXT</li></ul>", "sort_order": 99})


class Tab(unittest.TestCase):
    def test_the_file_carries_the_tab_after_the_use_cases(self):
        _, pub, text = made()
        self.assertEqual(pub["tabs"][-1], "clientreport")
        self.assertEqual(block(text)["tabs"], pub["tabs"])

    def test_a_hidden_milestones_section_leaves_the_tab_out(self):
        def hide(plant):
            for s in plant["sections"]:
                if s["type"] == "milestones":
                    s["hidden"] = 1
        _, pub, _ = made(hide)
        self.assertNotIn("clientreport", pub["tabs"])
        self.assertEqual(pub["data"]["milestones"], [])

    def test_nothing_the_view_needs_is_a_new_field(self):
        # the view reads milestones, risks and text sections: each is already published; no working note is added to the file
        for table in ("milestones", "raid"):
            self.assertNotIn("response_action", publish.PUBLISH_FIELDS[table])
        _, _, text = made()
        self.assertNotIn("response_action", text)


class Nothing(unittest.TestCase):
    """The client reads this page: a part with no value is left out, never a placeholder, and Risks that are hidden are never "none"."""

    def test_hidden_risks_leave_the_whole_part_out_of_the_file(self):
        _, pub, _ = made(hide_risks)
        self.assertEqual(pub["data"]["raid"], [])
        self.assertIn("clientreport", pub["tabs"], "the tab stays: the part leaves, not the page")
        self.assertNotIn("raid", [s["type"] for s in pub["sections"]])
        self.assertNotIn("raid", shown(pub))
        _, shown_pub, _ = made()
        self.assertIn("raid", shown(shown_pub), "with Risks shown the part is there")

    def test_a_shown_risks_section_with_no_open_rows_may_say_so(self):
        # only a Risks section that is shown can say there is nothing: that is true of it
        _, pub, _ = made()
        d = {**pub["data"], "raid": []}
        pub2 = {**pub, "data": d}
        self.assertIn("raid", shown(pub2))

    def test_a_part_with_nothing_to_say_is_left_out_of_the_file_and_kept_in_edit(self):
        _, pub, _ = made(lambda p: p["sections"].__setitem__(slice(None), [s for s in p["sections"] if s["type"] != "text"]))
        got = shown(pub)
        self.assertNotIn("highlights", got)
        self.assertNotIn("nextweek", got)
        self.assertEqual(shown(pub, editing=True), ["progress", "plans", "highlights", "nextweek", "raid"], "Edit keeps its boxes and prompts")

    def test_no_milestones_and_no_health_leave_the_progress_parts_out(self):
        _, pub, _ = made()
        def bare(d):
            d["milestones"] = []
            d["project"] = {**d["project"], "health": ""}
        got = shown(pub, mutate=bare)
        self.assertNotIn("progress", got)
        self.assertNotIn("plans", got)


class RealBrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        plant = fx.load()
        words(plant)
        cls.plant = plant
        pub = publish.select(fx.inputs(plant))
        text = publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"])
        cls.pub = pub
        cls.path = Path(cls.tmp.name) / "report.html"
        cls.path.write_text(text, encoding="utf-8")

    def open_report(self, cdp, width=1400):
        sid = opened(cdp, self.path.as_uri(), width)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"), "the page drew from the file alone")
        cdp.js("document.querySelector('[data-view=clientreport]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#clientreport .sec')", sid)), "the report view drew")
        return sid

    def test_the_view_in_the_file_shows_what_the_file_kept_and_nothing_for_the_author(self):
        with chrome() as cdp:
            sid = self.open_report(cdp)
            js = lambda e: cdp.js(e, sid)  # noqa: E731
            self.assertEqual(js("document.querySelector('[data-view=clientreport]').innerText"), "Weekly snapshot")
            self.assertEqual(js("[...document.querySelectorAll('#clientreport .sec')].map(e => e.dataset.sec)"), ["progress", "plans", "highlights", "nextweek", "raid"])
            self.assertEqual(js("document.querySelector('#clientreport .cr-band h1').textContent"), self.pub["data"]["project"]["name"])
            self.assertIn("WEEKLY PROGRESS SNAPSHOT", js("document.querySelector('.cr-band .cr-cover').textContent"))
            lines = js("[...document.querySelectorAll('[data-line]')].map(e => e.querySelector('.c-tx').textContent)")
            self.assertEqual(sorted(lines), ["Go live ZQ-KEEP-MILESTONE-2", "Pilot live ZQ-KEEP-MILESTONE-1"], "the rows the file kept, none of the others")
            self.assertEqual(js("document.querySelectorAll('[data-fig=actual], [data-fig=planned], [data-bar]').length"), 3)
            self.assertEqual(js("document.querySelectorAll('#cr-raid .wl-row').length"), 1)
            self.assertIn("Steel delivery may slip ZQ-KEEP-RISK-1", js("document.querySelector('#cr-raid').innerText"))
            self.assertIn("ZQ-KEEP-HIGHLIGHT", js("document.querySelector('#cr-highlights').innerText"))
            self.assertIn("ZQ-KEEP-NEXT", js("document.querySelector('#cr-nextweek').innerText"))
            shown = js("document.querySelector('#clientreport').innerText")
            for out in ("ZQ-HIDDEN-MILESTONE", "ZQ-FLAG-OFF-MILESTONE", "ZQ-FLAG-OFF-RISK"):
                self.assertNotIn(out, shown)
            self.assertNotRegex(shown, NOTHING_FOR_THE_AUTHOR, "no placeholder text: not 'Not set', not an empty-state sentence")
            self.assertEqual(js("[...document.querySelectorAll('[data-line]')].every(l => l.querySelector('.c-ac').innerText.trim() !== '')"), True, "an Achieved with no percent is a dash, not blank")
            self.assertEqual(js("document.querySelectorAll('#clientreport input, #clientreport textarea, #clientreport select, #clientreport [contenteditable], #clientreport [data-placeholder]').length"), 0)
            self.assertEqual(js("window.violations"), [], "the policy blocked nothing")

    def test_a_file_with_the_risks_hidden_has_no_risks_part_and_no_claim_of_none(self):
        plant = fx.load()
        words(plant)
        hide_risks(plant)
        pub = publish.select(fx.inputs(plant))
        path = Path(self.tmp.name) / "no-risks.html"
        path.write_text(publish.render(pub, page.page_html(EMPTY_BRANDING), plant["as_at"], pub["data"]["project"]["name"]), encoding="utf-8")
        with chrome() as cdp:
            sid = opened(cdp, path.as_uri())
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
            cdp.js("document.querySelector('[data-view=clientreport]').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#clientreport .sec')", sid)))
            self.assertEqual(cdp.js("[...document.querySelectorAll('#clientreport .sec')].map(e => e.dataset.sec)", sid), ["progress", "plans", "highlights", "nextweek"])
            text = cdp.js("document.querySelector('#clientreport').innerText", sid)
            self.assertNotRegex(text, r"(?i)no open risks|Risks, delays")
            self.assertNotIn("Not set", text)

    def test_it_fits_at_1400_and_900_light_and_dark(self):
        with chrome() as cdp:
            sid = self.open_report(cdp)
            for width in (1400, 900):
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                for theme in ("light", "dark"):
                    cdp.js(f"document.documentElement.dataset.theme = '{theme}'", sid)
                    time.sleep(0.3)
                    where = f"{width}px {theme}"
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True, f"{where}: no sideways scroll")
                    self.assertEqual(cdp.js("(() => { const f = document.querySelector('#clientreport').getBoundingClientRect();"
                                            " return [...document.querySelectorAll('#clientreport *')].filter(e => { const r = e.getBoundingClientRect();"
                                            " return r.width > 0 && (r.right > f.right + 1 || r.left < f.left - 1); }).length; })()", sid), 0, f"{where}: inside the frame")
                    dark = cdp.js("(() => { const c = getComputedStyle(document.querySelector('.cr-band')).backgroundColor.match(/\\d+/g).map(Number); return c[0] < 80 && c[1] < 80 && c[2] < 100; })()", sid)
                    self.assertTrue(dark, f"{where}: the band is dark")
                    small = cdp.js("[...document.querySelectorAll('#clientreport *')].filter(e => e.getBoundingClientRect().width > 0 && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).length", sid)
                    self.assertEqual(small, 0, f"{where}: text at 13 px or more")


if __name__ == "__main__":
    unittest.main()
