"""#642: the pictures on the five guides.

Run: python3 dev/run_tests.py test_help_guide_pictures
Every picture id a guide step uses is declared in helpContent.json `pictures` and is a shot in dev/tools/help_shots.json; every
declared picture is used by a step and has its words (alt); the published page holds none of the pictures nor the code that draws
them; and a step draws nothing at all (never a broken image) when the page has no picture for its id (a stub stands in for the
page's pictureUrl). The pictures are light only and total no more than 3 MB (test_help_pictures checks the files themselves).
"""
import base64
import json
import re
import unittest

from _help_shown import RAW
from _paths import ROOT
from test_help_guides import HELP, run_node

SHOTS = {s["id"] for s in json.loads((ROOT / "dev" / "tools" / "help_shots.json").read_text(encoding="utf-8"))["shots"]}
USED = {s["pic"] for g in RAW["guides"] for s in g["steps"] if s.get("pic")}
DECLARED = {p["id"]: p for p in RAW["pictures"]}

# The step (1-based) each picture goes on, by guide; a picture is on the step that names the control it shows.
WHERE = {
    "add-a-section-from-a-template": {2: "templates-add-box", 3: "templates-dialog", 5: "templates-place"},
    "arrange-the-report": {1: "arrange-grip", 3: "arrange-menu", 6: "arrange-leave-out"},
    "bring-in-an-excel-workbook": {1: "excel-in-button", 3: "excel-in-box"},
    "send-the-workbook-out": {2: "excel-out-menu", 3: "excel-out-card"},
    "publish-to-the-client": {2: "publish-menu", 3: "publish-dialog"},
}


class TheDeclaredPictures(unittest.TestCase):
    def test_every_picture_a_step_uses_is_declared_and_is_a_listed_shot(self):
        self.assertTrue(USED)
        self.assertEqual(USED - set(DECLARED), set(), "a step shows a picture that is not declared")
        self.assertEqual(USED - SHOTS, set(), "a step shows a picture that is not in dev/tools/help_shots.json")

    def test_every_listed_shot_is_declared_and_used_once_with_its_words(self):
        self.assertEqual(set(DECLARED), SHOTS)
        self.assertEqual(sorted(s["pic"] for g in RAW["guides"] for s in g["steps"] if s.get("pic")), sorted(SHOTS), "each picture on exactly one step")
        for i, p in DECLARED.items():
            self.assertTrue(p["alt"].strip().endswith("."), i)
            self.assertLess(len(p["alt"]), 120, f"{i}: a short alt text")
        self.assertEqual(len(DECLARED), len(RAW["pictures"]), "a picture declared twice")

    def test_each_picture_is_on_the_step_that_names_its_control(self):
        for g in RAW["guides"]:
            got = {n: s["pic"] for n, s in enumerate(g["steps"], 1) if s.get("pic")}
            self.assertEqual(got, WHERE.get(g["id"], {}), g["id"])      # the four guides C (#642 step 10) have no picture yet


class TheStepDrawsOnlyWhatThePageHas(unittest.TestCase):
    def test_a_step_draws_its_picture_with_the_declared_words(self):
        probe = "(() => HL.guides().flatMap((g) => g.steps.filter((s) => s.pic).map((s) => [g.id, s.n, HL.stepPicture(s, (id) => 'data:image/png;base64,' + id)])))()"
        got = run_node(RAW, probe)
        self.assertEqual(len(got), len(SHOTS))
        for gid, n, pic in got:
            self.assertEqual(pic["alt"], DECLARED[WHERE[gid][n]]["alt"])
            self.assertEqual(pic["src"], "data:image/png;base64," + WHERE[gid][n])

    def test_a_step_draws_nothing_when_the_page_has_no_picture(self):
        probe = ("(() => { const out = []; for (const g of HL.guides()) for (const s of g.steps) out.push([!!s.pic, HL.stepPicture(s, () => null), HL.stepPicture(s, () => ''),"
                 " HL.stepPicture(s, undefined), HL.stepPicture(s, (id) => ({}).nope)]); return out; })()")
        rows = run_node(RAW, probe)
        self.assertTrue(any(r[0] for r in rows))
        for r in rows:
            self.assertEqual(r[1:], [None, None, None, None])

    def test_a_step_without_a_picture_or_with_an_undeclared_one_draws_nothing(self):
        probe = "(() => [HL.stepPicture({ d: 'x', pic: null }, () => 'data:x'), HL.stepPicture({ d: 'x' }, () => 'data:x'), HL.stepPicture({ d: 'x', pic: 'nothing-here' }, () => 'data:x'), HL.stepPicture(null, () => 'data:x')])()"
        self.assertEqual(run_node(RAW, probe), [None, None, None, None])

    def test_the_panel_draws_a_picture_only_through_that_function_and_the_pages_own_copy(self):
        src = (HELP / "Help.jsx").read_text(encoding="utf-8")
        self.assertEqual(len(re.findall(r"<img\b", src)), 1)
        self.assertIn("stepPicture(step, urlOf)", src)
        self.assertIn('import { pictureUrl } from "./helpPictures.js";', src)
        self.assertRegex(src, r"return p \? <img [^>]*alt=\{p\.alt\}[^>]*/> : null;")


class NotOnThePublishedPage(unittest.TestCase):
    def test_the_published_page_holds_no_picture_and_no_help_picture_code(self):
        from clark import page
        page.ensure_built()
        published = page.VIEW_PAGE.read_text(encoding="utf-8")
        for shot in SHOTS:
            b64 = base64.b64encode((ROOT / "src" / "clark" / "page" / "help-pictures" / f"{shot}.png").read_bytes()).decode("ascii")
            self.assertNotIn(b64[:200], published, f"the published page must carry no {shot}")
        self.assertNotIn('"hp-pic"', published, "no step picture drawn")      # the CSS rule is in the shared stylesheet; the class a step draws is not
        for p in DECLARED.values():
            self.assertNotIn(p["alt"], published, p["alt"])


if __name__ == "__main__":
    unittest.main()
