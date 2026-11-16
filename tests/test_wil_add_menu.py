"""Row 1268, slice Add menu: the + of a Work items list in Edit opens Action, Risk, Issue, Decision; a pick makes the item at once and opens its
peek. A new list starts with a saved filter (the template sends it, the store takes exactly that body and no other).

Run: python3 dev/run_tests.py test_wil_add_menu"""
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

from clark import changes
from clark.section_kinds import workitems as wi
import test_tpl_workitems as base
from test_changes import Api
from test_report_editor import tearDownModule  # noqa: F401
from test_server import chrome

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "wil_templates_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"


def template_start():
    """The body the page's Work items list template sends for a new list, from the page's own code (bundled and run in node)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "t.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=T", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                            *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"], cwd=tmp, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        code = out.read_text(encoding="utf-8") + ";console.log(JSON.stringify(T.TEMPLATES.find((t) => t.id === 'work-items').start))"
    got = subprocess.run(["node", "-"], input=code, capture_output=True, text=True, cwd=tempfile.gettempdir())
    assert got.returncode == 0, got.stderr
    return json.loads(got.stdout)


class StartsWithAFilter(Api):
    def setUp(self):
        super().setUp()
        base.plant(self)

    def test_the_start_body_is_the_checkers_own_form(self):
        self.assertEqual(json.loads(wi.START), base.check(json.loads(wi.START)))

    def test_the_page_template_sends_exactly_the_body_the_store_takes(self):
        if shutil.which("node") is None:
            self.skipTest("node is not installed on this computer (CI has it)")
        self.assertEqual(template_start(), wi.START)

    def test_a_new_list_given_the_start_body_holds_it(self):
        ref = self.ok("new", values={"type": "workitems", "title": "Work items", "body": wi.START}, after=None)["ref"]
        self.assertEqual(json.loads(self.s.read("report_sections", ref=ref)["body"]), json.loads(wi.START), "the store keeps it in its own canonical text")

    def test_no_other_body_is_taken_for_a_new_list(self):
        for body in ('{"v":1}', wi.START.replace('"max":10', '"max":9'), ""):
            with self.subTest(body=body):
                self.refused(self.req("new", values={"type": "workitems", "title": "Work items", "body": body}, after=None), changes.NO_BODY_HERE)


class AddMenu(base.InThePage):
    def test_the_plus_opens_four_kinds_and_a_pick_adds_one_item_and_opens_its_peek(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo"]})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.show(cdp, width)
                p.edit()
                btn = f"[data-id=\"{ref}\"] [data-wil-add] button"
                p.until(f"!!document.querySelector({json.dumps(btn)})", "the + is drawn")
                self.assertEqual(p.js(f"document.querySelector({json.dumps(btn)}).getAttribute('aria-label')"), "Add work item")
                self.assertEqual(p.js(f"document.querySelector({json.dumps(btn)}).getAttribute('aria-haspopup')"), "menu")
                p.js(f"document.querySelector({json.dumps(btn)}).click()")
                p.until("!!document.querySelector('[role=menu] [role=menuitem]')", "the menu opened")
                words = p.js("[...document.querySelectorAll('[role=menu] [role=menuitem]')].map(e => e.textContent.trim())")
                self.assertEqual(words, ["Action", "Risk", "Issue", "Decision"])
                before = self.store.con.execute("SELECT count(*) FROM raid").fetchone()[0]
                p.js("[...document.querySelectorAll('[role=menu] [role=menuitem]')].find(e => e.textContent.trim() === 'Risk').click()")
                p.until("!!document.querySelector('#peek')", "its peek opened")
                self.assertEqual(self.store.con.execute("SELECT count(*) FROM raid").fetchone()[0], before + 1, "one risk was made at once")

    def test_view_has_no_plus(self):
        ref = self.add({"mode": "all", "owner": ["Pat Demo"]})
        with chrome() as cdp:
            p = self.show(cdp)
            p.until(f"!!document.querySelector('[data-id=\"{ref}\"] .wil-table')", "the list drew")
            self.assertFalse(p.js(f"!!document.querySelector('[data-id=\"{ref}\"] [data-wil-add]')"))


if __name__ == "__main__":
    unittest.main()
