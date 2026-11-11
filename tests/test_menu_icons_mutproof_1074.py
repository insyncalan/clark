"""Row 1074, mutation proof: the icons of the drop-downs, pinned where test_menu_icons left them loose.

Run: python3 dev/run_tests.py test_menu_icons_mutproof_1074
Part 1 runs the rules in node: a status choice takes the tone of the pill the item would have (Overdue red, Due soon amber, with the
date of today handed in), and the bulk bar's choices carry the right icon and tone for every control. Part 2 drives the real page at
1400 and 900 px only: the status menu of a late and of a soon-due action, the rating menu of a risk, the bulk bar's four menus, the
milestone peek's workstream menu, and that the icon is drawn (shown, 16 px, before the words).
"""
import json
import shutil
import subprocess
import unittest

from _paths import ROOT

import test_inline_edits as ie  # noqa: E402
from test_inline_edits import click, key  # noqa: E402
from test_server import chrome  # noqa: E402  (the browser tier: this file drives Chrome through chrome())
import test_bulk_bar as bb  # noqa: E402
import test_milestone_peek_828 as mp  # noqa: E402
from test_movement_page import GO_LIVE, Base as MoveBase  # noqa: E402

SRC = ROOT / "src" / "clark" / "page" / "src"
WIDTHS = (1400, 900)


def run_js(file, body):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    code = f'import * as M from "{(SRC / file).as_uri()}"; {body}'
    done = subprocess.run([node, "--input-type=module", "-e", code], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def pairs(choices):
    return [(c["value"], c["icon"], c["tone"]) for c in choices]


class Rules(unittest.TestCase):
    def test_a_status_choice_takes_the_tone_of_the_pill_with_todays_date(self):
        row = {"kind": "action", "due_date": "2026-10-01"}
        soon = {"kind": "action", "due_date": "2026-11-02"}
        out = run_js("menuIcons.js", f"const a = {json.dumps(row)}, b = {json.dumps(soon)};"
                     " console.log(JSON.stringify([M.statusIcon(a, 'Open', '2026-10-28').tone, M.statusIcon(a, 'Open', '').tone,"
                     " M.statusIcon(a, 'Closed', '2026-10-28').tone, M.statusIcon(b, 'Open', '2026-10-28').tone, M.statusIcon(b, 'Delayed', '2026-10-28').tone]))")
        self.assertEqual(out, ["r", "b", "n", "a", "a"])

    def test_the_bars_choices_carry_the_icon_and_tone_of_each_control(self):
        out = run_js("edit/bulkLogic.js",
                     "const c = (t, id) => M.choicesFor(t, id, {today: '2026-10-28', workstreams: ['Build'], milestones: [{id: 'M1', name: 'Go'}]});"
                     " console.log(JSON.stringify({status: c('actions', 'status'), risk: c('raid', 'status'), priority: c('actions', 'priority'),"
                     " impact: c('raid', 'impact'), likelihood: c('raid', 'likelihood'), workstream: c('actions', 'workstream'), milestone: c('actions', 'milestone')}))")
        self.assertEqual(pairs(out["status"]), [("Open", "half", "b"), ("Delayed", "half", "a"), ("Closed", "half", "n"), ("Cancelled", "half", "n")])
        self.assertEqual({c["icon"] for c in out["risk"]}, {"half"})
        self.assertEqual([c["text"] for c in out["risk"]], ["Open", "Closed", "Cancelled"])
        self.assertEqual([c["tone"] for c in out["risk"]], ["n", "n", "n"], "a risk or issue is not an action: no blue Open, no amber Delayed")
        self.assertEqual([(c["icon"], c["tone"]) for c in out["priority"]], [("bars", "r"), ("bars", "a"), ("bars", "b"), ("bars", "n")])
        for name in ("impact", "likelihood"):
            self.assertEqual([c["icon"] for c in out[name]], ["bars"] * 3, name)
            self.assertEqual([c["tone"] for c in out[name]], ["a", "b", "n"], name)
        self.assertEqual(pairs(out["workstream"]), [("Build", "board", "n"), ("", "circleminus", "n")])
        self.assertEqual(pairs(out["milestone"]), [("M1", "flag", "n"), ("", "circleminus", "n")])
        self.assertEqual([c["text"] for c in out["milestone"]], ["Go", "No milestone"])


class Shown(unittest.TestCase):
    """Helpers shared by the page tests below."""

    ICONS = ("[...document.querySelectorAll('[data-pop] [role=menuitemradio]')].map(b => { const s = b.querySelector('svg.i');"
             " return {t: b.querySelector('.mi-t').textContent.trim(), icn: s ? s.dataset.icn : '', tone: s ? s.parentElement.className.replace('mi-i ', '') : ''}; })")

    DRAWN = ("(() => { const b = document.querySelector('[data-pop] [role=menuitemradio]'), i = b.querySelector('.mi-i'), s = i && i.querySelector('svg.i'),"
             " t = b.querySelector('.mi-t'); if (!s) return null; const r = s.getBoundingClientRect(), w = t.getBoundingClientRect();"
             " return {display: getComputedStyle(i).display, w: Math.round(r.width), h: Math.round(r.height), before: r.right <= w.left + 0.5, same: Math.abs((r.top + r.bottom) / 2 - (w.top + w.bottom) / 2) < 12}; })()")

    def check_drawn(self, cdp, sid):
        got = cdp.js(self.DRAWN, sid)
        self.assertIsNotNone(got, "the first choice has its icon")
        self.assertNotEqual(got["display"], "none")
        self.assertEqual((got["w"], got["h"]), (16, 16))
        self.assertTrue(got["before"], "the icon is before the words")
        self.assertTrue(got["same"], "the icon is on the line of the words")


class Inline(Shown):
    setUp = ie.Live.setUp
    read = ie.Live.read
    open_page = ie.Live.open_page
    until = ie.Live.until

    def menu(self, cdp, sid, cell):
        click(cdp, sid, f"[data-cell='{cell}']")
        self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "menu " + cell)
        return cdp.js(self.ICONS, sid)

    def test_a_late_and_a_soon_due_action_show_the_tone_the_pill_would_take(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                got = {g["t"]: g["tone"] for g in self.menu(cdp, sid, "TUL-A-001:status")}
                self.assertEqual(got["Open"], "ic-a", "due in five days is Due soon (today is handed in)")
                self.assertEqual(got["Closed"], "ic-n")
                self.check_drawn(cdp, sid)
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
                late = cdp.js("(() => { const t = document.querySelector('tr[data-id=TUL-010]'); return t ? t.querySelector('.due-l') !== null : false; })()", sid)
                self.assertTrue(late, "TUL-010 is the late one")
                got = {g["t"]: g["tone"] for g in self.menu(cdp, sid, "TUL-010:status")}
                self.assertEqual(got["Open"], "ic-r", "a late action's Open is red, as its pill would be")

    def test_the_rating_menu_of_a_risk_shows_the_bars_in_each_levels_tone(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                got = self.menu(cdp, sid, "TUL-007:priority")
                self.assertEqual([g["t"] for g in got], ["High", "Medium", "Low"] * 2)
                self.assertEqual({g["icn"] for g in got}, {"bars"})
                self.assertEqual([g["tone"] for g in got], ["ic-a", "ic-b", "ic-n"] * 2)
                self.check_drawn(cdp, sid)

    def test_the_icon_has_a_gap_before_the_words_and_the_due_choices_keep_their_date_at_the_right(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.open_page(cdp, width)
                got = self.menu(cdp, sid, "TUL-A-001:status")
                self.assertTrue(got)
                gap = cdp.js("(() => { const b = document.querySelector('[data-pop] [role=menuitemradio]'); return Math.round(b.querySelector('.mi-t').getBoundingClientRect().left - b.querySelector('svg.i').getBoundingClientRect().right); })()", sid)
                self.assertGreaterEqual(gap, 6, "a gap between the icon and the words")
                key(cdp, sid, "Escape")
                self.until(cdp, sid, "document.querySelectorAll('[data-pop]').length === 0", "closed")
                click(cdp, sid, "[data-cell='TUL-A-001:due']")
                self.until(cdp, sid, "!!document.querySelector('[data-pop] [data-quick] small')", "due panel with a dated choice")
                spots = cdp.js("(() => { const b = [...document.querySelectorAll('[data-pop] [data-quick]')].find((x) => x.querySelector('small')); const r = b.getBoundingClientRect(),"
                               " s = b.querySelector('small').getBoundingClientRect(), w = b.querySelector('span:not(.mi-i)').getBoundingClientRect(), i = b.querySelector('svg.i').getBoundingClientRect();"
                               " return {gapIcon: Math.round(w.left - i.right), toRight: Math.round(r.right - s.right), wordToDate: Math.round(s.left - w.right)}; })()", sid)
                self.assertGreaterEqual(spots["gapIcon"], 6)
                self.assertLessEqual(spots["toRight"], 24, "the date sits at the right edge of its choice")
                self.assertGreater(spots["wordToDate"], 30, "the words and the date are pushed apart")


class Bar(Shown, bb.Base):
    load = bb.Page.load
    rsel = bb.Page.rsel
    pick = bb.Page.pick
    ROWS = bb.Page.ROWS

    def bar_menu(self, cdp, sid, control):
        click(cdp, sid, f"#sel-bar [data-bulk={control}]")
        self.until(cdp, sid, "!!document.querySelector('.cpop [role=menuitemradio]')", control + " menu")
        return cdp.js(self.ICONS, sid)

    def test_every_menu_of_the_bar_has_its_icons_at_both_widths(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                sid = self.load(cdp, width=width)
                ids = cdp.js(self.ROWS, sid)[:2]
                self.pick(cdp, sid, ids)
                got = self.bar_menu(cdp, sid, "status")
                self.assertEqual({g["icn"] for g in got}, {"half"})
                self.assertEqual({g["t"]: g["tone"] for g in got}["Closed"], "ic-n")
                self.assertEqual({g["t"]: g["tone"] for g in got}["Delayed"], "ic-a")
                self.check_drawn(cdp, sid)
                key(cdp, sid, "Escape")
                got = self.bar_menu(cdp, sid, "priority")
                self.assertEqual([g["icn"] for g in got], ["bars"] * 4)
                self.assertEqual([g["tone"] for g in got], ["ic-r", "ic-a", "ic-b", "ic-n"])
                key(cdp, sid, "Escape")
                got = self.bar_menu(cdp, sid, "workstream")
                self.assertGreater(len(got), 1)
                self.assertEqual([g["icn"] for g in got][:-1], ["board"] * (len(got) - 1))
                self.assertEqual((got[-1]["t"], got[-1]["icn"]), ("No workstream", "circleminus"))
                key(cdp, sid, "Escape")
                got = self.bar_menu(cdp, sid, "milestone")
                self.assertGreater(len(got), 1)
                self.assertEqual([g["icn"] for g in got][:-1], ["flag"] * (len(got) - 1))
                self.assertEqual((got[-1]["t"], got[-1]["icn"]), ("No milestone", "circleminus"))
                self.assertEqual({g["tone"] for g in got}, {"ic-n"})


class Milestone(Shown, MoveBase):
    cur = GO_LIVE
    visit_peek = mp.Fields.visit_peek
    click = mp.Fields.click

    def test_the_workstream_menu_has_the_board_for_each_workstream_and_the_minus_for_none(self):
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                self.click(p, "#peek [data-ms-field=workstream]")
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the workstream menu opened")
                got = p.js(self.ICONS)
                self.assertGreater(len(got), 1)
                self.assertEqual([g["icn"] for g in got][:-1], ["board"] * (len(got) - 1))
                self.assertEqual((got[-1]["t"], got[-1]["icn"], got[-1]["tone"]), ("No workstream", "circleminus", "ic-n"))
                self.assertEqual(p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio] svg.i')].every((s) => s.getAttribute('aria-hidden') === 'true')"), True)
                self.assertTrue(p.js("document.querySelector('[data-pop] [role=menuitemradio]').getBoundingClientRect().width > 0"))


class PeekFields(Shown):
    """The work item peek's three pickers: each field has its own icon, and the one that clears it has the minus."""
    setUp = ie.Live.setUp
    read = ie.Live.read
    open_page = ie.Live.open_page
    until = ie.Live.until

    def test_milestone_and_use_case_menus_have_their_own_icon_and_a_minus_to_clear(self):
        for width in WIDTHS:
            for field, icon, none in (("milestone", "flag", "No milestone"), ("use_case", "doc", "No use case")):
                with self.subTest(width=width, field=field), chrome() as cdp:
                    sid = self.open_page(cdp, width, hash_="#work&p=TUL&f=mode:all&item=TUL-A-001")
                    self.until(cdp, sid, f"!!document.querySelector('[data-pk-pick={field}]')", "peek pick")
                    click(cdp, sid, f"[data-pk-pick={field}]")
                    self.until(cdp, sid, "!!document.querySelector('[data-pop][role=menu]')", "menu")
                    got = cdp.js(self.ICONS, sid)
                    self.assertGreater(len(got), 1)
                    self.assertEqual([g["icn"] for g in got][:-1], [icon] * (len(got) - 1))
                    self.assertEqual((got[-1]["t"], got[-1]["icn"], got[-1]["tone"]), (none, "circleminus", "ic-n"))
                    self.assertEqual({g["tone"] for g in got}, {"ic-n"})


class MilestoneButton(Shown, MoveBase):
    """The milestone peek's workstream button: it names the choice, opens and closes the menu, and takes the focus back after a pick."""
    cur = GO_LIVE
    visit_peek = mp.Fields.visit_peek
    click = mp.Fields.click
    saved = mp.Fields.saved
    until_store = mp.Fields.until_store

    def test_the_button_opens_and_closes_the_menu_shows_the_choice_and_keeps_the_focus(self):
        button = "#peek [data-ms-field=workstream]"
        for width in WIDTHS:
            with self.subTest(width=width), chrome() as cdp:
                p = self.visit_peek(cdp, width=width)
                self.assertEqual(p.js(f"document.querySelector('{button}').getAttribute('aria-expanded')"), "false")
                self.click(p, button)
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the menu opened")
                self.assertEqual(p.js(f"document.querySelector('{button}').getAttribute('aria-expanded')"), "true")
                self.click(p, button)
                p.until("document.querySelectorAll('[data-pop]').length === 0", "the button closes the menu again")
                self.assertEqual(p.js(f"document.querySelector('{button}').getAttribute('aria-expanded')"), "false")
                self.click(p, button)
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the menu opened again")
                p.until("!!document.activeElement.closest('[data-pop]')", "the focus went into the menu")
                p.until("document.getAnimations().length === 0", "the menu stopped moving")
                self.click(p, "[data-pop] [role=menuitemradio][data-value=Build]")
                self.saved(p, "workstream", "Build")
                p.until("document.querySelectorAll('[data-pop]').length === 0", "a pick closes the menu")
                p.until(f"document.querySelector('{button}').textContent === 'Build'", "the button says the choice")
                self.assertIn("Build", p.js(f"document.querySelector('{button}').getAttribute('aria-label')"))
                self.assertTrue(p.js(f"document.activeElement === document.querySelector('{button}')"), "the focus is back on the button")
                self.click(p, button)
                p.until("!!document.querySelector('[data-pop][role=menu]')", "the menu opened once more")
                self.assertEqual(p.js("[...document.querySelectorAll('[data-pop] [role=menuitemradio][aria-checked=true]')].map(b => b.dataset.value)"), ["Build"],
                                 "the menu ticks the workstream it has now")


if __name__ == "__main__":
    unittest.main()
