"""Row 1074: every drop-down shows an icon beside its words (coloured where the item has a colour), for work items and milestones.

Run: python3 dev/run_tests.py test_menu_icons
Part 1 is the rules (page/src/menuIcons.js) run in node. Part 2 reads the source: the icons come from the existing icon set only,
no colour is written out, and no new word is added. Part 3 drives the real page: each picker's choices carry an icon whose shape is
the field's and whose tone is the choice's, and the words are the words they were.
"""
import json
import re
import shutil
import subprocess
import unittest

from _paths import ROOT

from test_inline_edits import Live, chrome, click, key  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"


def run_js(body):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    code = f'import * as M from "{(SRC / "menuIcons.js").as_uri()}"; {body}'
    done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


class Rules(unittest.TestCase):
    def test_a_status_takes_the_half_circle_in_the_pills_tone(self):
        rows = [{"kind": "action", "status": "Open", "due_date": "2026-12-30"}, {"kind": "action", "status": "Closed"},
                {"kind": "decision", "status": "Pending"}]
        out = run_js(f"const R = {json.dumps(rows)}; console.log(JSON.stringify(R.map((r) => M.statusIcon(r, r.status, '2026-10-28'))))")
        self.assertEqual(out, [{"icon": "half", "tone": "b"}, {"icon": "half", "tone": "n"}, {"icon": "half", "tone": "b"}])

    def test_a_decision_made_is_green_and_withdrawn_grey(self):
        out = run_js("const r = {kind: 'decision', status: 'Pending'}; console.log(JSON.stringify([M.statusIcon(r, 'Made', '2026-10-28').tone, M.statusIcon(r, 'Withdrawn', '2026-10-28').tone]))")
        self.assertEqual(out, ["g", "n"])

    def test_a_rating_takes_its_own_colour(self):
        out = run_js("console.log(JSON.stringify(['Red', 'Amber', 'Green'].map((w) => M.ratingIcon(w))))")
        self.assertEqual(out, [{"icon": "half", "tone": "r"}, {"icon": "half", "tone": "a"}, {"icon": "half", "tone": "g"}])

    def test_a_priority_takes_the_bars_in_its_tone(self):
        out = run_js("console.log(JSON.stringify(['Urgent', 'High', 'Medium', 'Low'].map(M.priorityIcon)))")
        self.assertEqual([o["tone"] for o in out], ["r", "a", "b", "n"])
        self.assertEqual({o["icon"] for o in out}, {"bars"})

    def test_a_field_without_a_colour_is_grey_and_a_clearing_choice_has_the_minus(self):
        out = run_js("console.log(JSON.stringify([M.fieldIcon('workstream'), M.fieldIcon('milestone'), M.fieldIcon('use_case'), M.fieldIcon('workstream', true)]))")
        self.assertEqual([o["tone"] for o in out], ["n"] * 4)
        self.assertEqual([o["icon"] for o in out], ["board", "flag", "doc", "circleminus"])

    def test_the_due_choices_carry_the_calendar(self):
        self.assertEqual(run_js("console.log(JSON.stringify(M.dueIcon()))"), {"icon": "cal", "tone": "n"})


class Source(unittest.TestCase):
    def test_every_icon_named_is_in_the_existing_set(self):
        icons = (SRC / "components" / "Icon.jsx").read_text(encoding="utf-8")
        names = run_js("console.log(JSON.stringify(M.NAMES))")
        self.assertTrue(names)
        for name in names:
            self.assertRegex(icons, rf'(?m)^\s*"?{name}"?:', name)

    def test_the_menu_draws_the_icon_with_its_tone(self):
        text = (SRC / "edit" / "cells" / "MenuPick.jsx").read_text(encoding="utf-8")
        self.assertIn("Icon", text)
        self.assertIn("iconClass", text)

    def test_every_menu_of_a_work_item_gives_its_choices_icons(self):
        for name in ("StatusPick.jsx", "PriorityPick.jsx", "RatingPick.jsx", "DuePick.jsx"):
            self.assertIn("menuIcons.js", (SRC / "edit" / "cells" / name).read_text(encoding="utf-8"), name)
        self.assertIn("menuIcons.js", (SRC / "edit" / "PeekPick.jsx").read_text(encoding="utf-8"))
        self.assertIn("menuIcons.js", (SRC / "edit" / "bulkLogic.js").read_text(encoding="utf-8"))

    def test_the_milestone_peek_workstream_is_a_menu_with_icons_not_a_native_select(self):
        text = (SRC / "edit" / "MilestonePeek.jsx").read_text(encoding="utf-8")
        body = text[text.index("function Workstream"):text.index("function Visible")]
        self.assertNotIn("<select", body)
        self.assertIn("MenuPick", body)
        self.assertIn("fieldIcon", body)

    def test_no_colour_is_written_out(self):
        text = (SRC / "menuIcons.js").read_text(encoding="utf-8")
        self.assertNotRegex(re.sub(r"//.*", "", text), r"#[0-9a-fA-F]{3,8}\b|rgb\(")


class Browser(Live):
    def pop_icons(self, cdp, sid):
        return cdp.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => { const s = b.querySelector('svg.i');"
                      " return {t: b.textContent.trim(), icn: s ? s.dataset.icn : '', tone: s ? s.parentElement.className : '', hidden: s ? s.getAttribute('aria-hidden') : ''}; })", sid)

    def test_status_and_priority_menus_show_the_icon_and_the_same_words(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            click(cdp, sid, "[data-cell='TUL-A-001:priority']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "priority menu")
            got = self.pop_icons(cdp, sid)
            self.assertEqual([g["t"] for g in got], ["Urgent", "High", "Medium", "Low"])
            self.assertEqual([g["icn"] for g in got], ["bars"] * 4)
            self.assertEqual([g["tone"] for g in got], ["ic-r", "ic-a", "ic-b", "ic-n"])
            self.assertEqual({g["hidden"] for g in got}, {"true"})
            key(cdp, sid, "Escape")
            self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
            click(cdp, sid, "[data-cell='TUL-007:status']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "status menu")
            got = self.pop_icons(cdp, sid)
            self.assertEqual([g["t"] for g in got], ["Open", "Closed", "Cancelled", "Red", "Amber", "Green"])
            self.assertEqual({g["icn"] for g in got}, {"half"})
            self.assertEqual([g["tone"] for g in got][3:], ["ic-r", "ic-a", "ic-g"])
            self.assertEqual([g["tone"] for g in got][1:3], ["ic-n", "ic-n"])

    def test_the_due_panel_choices_carry_the_calendar(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400)
            click(cdp, sid, "[data-cell='TUL-A-001:due']")
            self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-quick]')", "due panel")
            n = cdp.js("document.querySelectorAll('[data-pop] [data-quick]').length", sid)
            self.assertGreater(n, 1)
            self.assertEqual(cdp.js("[...document.querySelectorAll('[data-pop] [data-quick]')].filter(b => b.querySelector('svg.i[data-icn=cal]')).length", sid), n)

    def test_the_peek_workstream_menu_shows_icons(self):
        with chrome() as cdp:
            sid = self.open_page(cdp, 1400, hash_="#work&p=TUL&f=mode:all&item=TUL-A-001")
            self.until(cdp, sid, "!!document.querySelector('[data-pk-pick=workstream]')", "peek pick")
            click(cdp, sid, "[data-pk-pick=workstream]")
            self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "menu")
            got = self.pop_icons(cdp, sid)
            self.assertGreater(len(got), 1)
            self.assertTrue(all(g["icn"] for g in got), got)
            self.assertEqual(got[-1]["icn"], "circleminus")
            self.assertEqual(got[-1]["t"], "No workstream")


if __name__ == "__main__":
    unittest.main()
