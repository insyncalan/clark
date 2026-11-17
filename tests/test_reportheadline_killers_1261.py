"""Row 1261: killers for mutants that survived the template's own tests. Fictional data only.

Run: python3 dev/run_tests.py test_reportheadline_killers_1261
"""
import json
import os
import re
import subprocess
import unittest

from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import store as store_module

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "clark", "page", "src", "templates", "ReportHeadline.jsx")


class Step(unittest.TestCase):
    def test_the_step_number_is_the_schema_version_and_the_plan_runs_without_a_gap(self):
        self.assertEqual(store_module.REPORT_HEADLINE_STEP, store_module.SCHEMA_VERSION)
        self.assertEqual(store_module.MIGRATIONS[-1], (store_module.SCHEMA_VERSION, store_module.migrate_report_headline_section_type))
        plan = store_module.migration_plan(1)
        self.assertEqual([n for n, _ in plan], list(range(2, store_module.SCHEMA_VERSION + 1)))


class Tidy(unittest.TestCase):
    def run_tidy(self, value):
        src = open(SRC, encoding="utf-8").read()
        healths = re.search(r"^const HEALTHS = .*;$", src, re.M).group(0)
        text = re.search(r"^const text = .*;$", src, re.M).group(0)
        tidy = re.search(r"^export function tidyReportHeadline\(v\) \{.*?^\}$", src, re.M | re.S).group(0).replace("export ", "", 1)
        js = f"{healths}\n{text}\n{tidy}\nprocess.stdout.write(JSON.stringify(tidyReportHeadline({json.dumps(value)})));"
        out = subprocess.run(["node", "-e", js], capture_output=True, text=True, timeout=60)
        self.assertEqual(out.returncode, 0, out.stderr[:200])
        return json.loads(out.stdout)

    def test_an_unknown_health_reads_as_not_set_and_the_words_are_trimmed(self):
        self.assertEqual(self.run_tidy({"health": "green", "headline": " H ", "sentence": 4}), {"health": "", "headline": "H", "sentence": ""})
        self.assertEqual(self.run_tidy({"health": "toString"}), {"health": "", "headline": "", "sentence": ""})
        self.assertEqual(self.run_tidy({"health": "at_risk"})["health"], "at_risk")
        self.assertEqual(self.run_tidy(None), {"health": "", "headline": "", "sentence": ""})


class Unchanged(Base):
    def test_leaving_a_box_with_the_same_words_saves_nothing(self):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional headline", "sort_order": 998,
                                                 "body": json.dumps({"v": 1, "health": "at_risk", "headline": "Fictional plan holds", "sentence": "Fictional reason."})})
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
            p.edit()
            box = f'[data-id="{ref}"] textarea[aria-label=Headline]'
            p.until(f"!!document.querySelector({json.dumps(box)})", "the headline field")
            applies = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            p.js("window.posts = []; var f = window.fetch; window.fetch = function (u, o) { if (o && o.body) window.posts.push(String(o.body)); return f.apply(this, arguments); };")
            p.js(f"(function(){{var e=document.querySelector({json.dumps(box)}); e.focus(); e.value='  Fictional   plan holds '; e.dispatchEvent(new Event('input', {{bubbles: true}})); e.blur();}})()")
            import time
            time.sleep(1.5)
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], applies, "same words after trimming: no save, no step")
            self.assertEqual(p.js("window.posts.length"), 0, "same words after trimming: nothing is sent")


if __name__ == "__main__":
    unittest.main()
