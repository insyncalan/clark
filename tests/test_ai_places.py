"""#72 slice 6: every editor on the page has its AI place, once, as data (src/clark/page/src/logic/aiPlaces.js).

Run: python3 dev/run_tests.py test_ai_places
The table only names the place; what a place offers is the server's menu (src/clark/ai_menu.py), which this test compares with the
page's menu for each editor. A scan of the page source fails when an editor is mounted that has no place.
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

from _clean_html import wait_for
from _paths import ROOT, TOOLS

sys.path.insert(0, str(TOOLS))
import esbuild  # noqa: E402
from test_server import chrome  # noqa: E402

from clark import ai_menu  # noqa: E402

PAGE_SRC = ROOT / "src" / "clark" / "page" / "src"
LOGIC = PAGE_SRC / "logic"
# The editors the plan names, with the place each must have.
WANTED = {
    "section.body": "current", "current.state": "current", "usecase.standing": "current", "notes.section": "notes",
    "peek.item_text": "plain", "peek.risk_wording": "plain", "milestone.client_wording": "client_message", "email.draft": "email",
}
RICH = ("section.body", "current.state", "usecase.standing", "notes.section")
# The section title is a one-line plain field and stays out of the AI.
LEFT_OUT = {"edit/Title.jsx"}


class Page:
    """aiPlaces.js bundled alone as `AP`, in a Chrome tab."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        tmp = Path(self.tmp.name)
        out = tmp / "ap.js"
        done = esbuild.run(["--bundle", "--format=iife", "--global-name=AP", "--target=es2020", "--tsconfig-raw={}",
                            str(LOGIC / "aiPlaces.js"), f"--outfile={out}"], cwd=LOGIC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        (tmp / "page.html").write_text("<!doctype html><meta charset=utf-8><body><script src=ap.js></script></body>", encoding="utf-8")
        self.chrome = chrome()
        self.cdp = self.chrome.__enter__()
        tid = next(t["targetId"] for t in self.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.cdp.call("Page.enable", {}, self.sid)
        self.cdp.call("Page.navigate", {"url": (tmp / "page.html").as_uri()}, self.sid)
        assert wait_for(lambda: self.cdp.js("typeof AP === 'object'", self.sid) is True, 60), "the script did not load"
        return self

    def __exit__(self, *exc):
        self.chrome.__exit__(*exc)
        self.tmp.cleanup()

    def ev(self, expr):
        return self.cdp.js(expr, self.sid)


def sources():
    for f in sorted(PAGE_SRC.rglob("*")):
        if f.suffix in (".js", ".jsx"):
            yield f.relative_to(PAGE_SRC).as_posix(), f.read_text(encoding="utf-8")


class PageCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = Page().__enter__()
        cls.place_of = cls.page.ev("AP.PLACE_OF")
        cls.fields = cls.page.ev("AP.RICH_FIELDS")
        cls.others = cls.page.ev("AP.OTHER_EDITORS")

    @classmethod
    def tearDownClass(cls):
        cls.page.__exit__(None, None, None)


class Table(PageCase):
    def test_each_editor_has_the_place_the_plan_gives_it(self):
        self.assertEqual(self.place_of, WANTED)
        for key, place in WANTED.items():
            self.assertEqual(self.page.ev(f"AP.placeFor({json.dumps(key)})"), place, key)

    def test_every_place_is_one_of_the_servers_five(self):
        for key, place in self.place_of.items():
            self.assertIn(place, ai_menu.PLACES, key)
        self.assertEqual(set(self.place_of.values()), set(ai_menu.PLACES))        # and all five are used

    def test_an_unknown_editor_gets_no_place(self):
        for key in ("nowhere", "", "__proto__", "constructor", "toString", None, 5):
            self.assertIsNone(self.page.ev(f"AP.placeFor({json.dumps(key)})"), key)
        self.assertIsNone(self.page.ev("AP.keyForField('__proto__')"))
        self.assertIsNone(self.page.ev("AP.keyForField('nowhere')"))

    def test_the_field_and_file_lists_point_at_real_entries(self):
        for key in list(self.fields.values()) + list(self.others.values()):
            self.assertIn(key, self.place_of)

    def test_what_each_editor_is_offered_is_the_servers_menu_for_its_place(self):
        for key, place in WANTED.items():
            with self.subTest(key=key):
                menu = self.page.ev(f"AP.menu(AP.placeFor({json.dumps(key)}))")
                self.assertEqual(menu, ai_menu.menu(place))
                self.assertEqual(bool(menu["make_into"]), key in RICH)               # Make into: the notes and current places only
                self.assertEqual(menu["format_notes"] is not None, key in RICH)
                ids = [i["id"] for g in menu["groups"] for i in g["items"]]
                self.assertEqual("checklist" in ids, place == "notes")
                self.assertEqual("formal" in ids, place == "email")

    def test_the_client_wording_uses_the_client_check(self):
        place = self.page.ev("AP.placeFor('milestone.client_wording')")
        self.assertEqual(place, "client_message")
        # The server's client check turns on this place alone: the same reply is blocked here and let through in a plain field.
        bad, original = "The project is on track, VIP client.", "The project is on track."
        self.assertFalse(ai_menu.check_reply(bad, original, "rewrite", place)["ok"])
        self.assertTrue(ai_menu.check_reply(bad, original, "rewrite", "plain")["ok"])


class Mounts(PageCase):
    """Reads the page source: a new editor with no place fails here."""

    def test_every_rich_field_mount_has_a_place(self):
        seen = []
        for rel, text in sources():
            if rel == "edit/RichField.jsx":
                continue
            for m in re.finditer(r"<(?:\w+\.)?RichField\b([^>]*)>", text):
                found = re.search(r"\bfield=(?:\"([^\"]+)\"|\{\"([^\"]+)\"\})", m.group(1))
                self.assertIsNotNone(found, f"{rel}: a RichField with no fixed field name")
                seen.append(found.group(1) or found.group(2))
        self.assertTrue(seen, "no RichField mount found: the scan is not looking at the right thing")
        for field in seen:
            self.assertIn(field, self.fields, f"the rich field '{field}' has no AI place (add it to aiPlaces.js)")

    def test_the_rich_text_editor_is_mounted_only_by_the_field(self):
        mounts = [rel for rel, text in sources() if re.search(r"<RichText\b", text) and rel != "edit/RichText.jsx"]
        self.assertEqual(mounts, ["edit/RichField.jsx"])

    def test_every_other_editable_box_has_a_place_or_is_left_out(self):
        pattern = re.compile(r"contenteditable|new\s+Editor\b|createEditor\b", re.I)
        boxes = []
        for rel, text in sources():
            if rel == "core/editor.js" or rel in LEFT_OUT or rel.startswith("edit/RichText"):
                continue
            if any(pattern.search(line.replace("isContentEditable", "")) for line in text.splitlines()):
                boxes.append(rel)
        self.assertIn("components/DraftEmail.jsx", boxes)          # the scan finds the one we know of
        for rel in boxes:
            self.assertIn(rel, self.others, f"{rel} mounts an editor with no AI place (add it to aiPlaces.js)")


if __name__ == "__main__":
    unittest.main()
