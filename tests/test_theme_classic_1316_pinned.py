"""Row 1316: every rule line the three 1316 blocks (a: the top of the Use cases page, b: the table, c: Next steps) add to the Classic theme,
exact and in order. They stack after the other rows (test_theme_prototype_pinned stops at Row 1318). Source only, no browser.
Run: python3 dev/run_tests.py test_theme_classic_1316_pinned"""
import unittest

from _paths import SRC

RULES = (SRC / "clark" / "themes" / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
START = "/* Row 1316a"

RULE_LINES = [
    '/* Row 1316a (issue 1316: Crumb, Tabs and menus, Search; the prototype files are not on this box, so the sizes are by eye, +/-2 px, from the issue table). Classic only; the Cards look layers none of this. Bare lengths with no token: the 560px search width, the 34px left padding that clears the magnifier, the 9px/2px magnifier ring and the 5px handle, the 1px clip box of the visually hidden count. */',
    '.ucd-crumb, .ucf-crumb { font-weight: var(--weight-regular); font-size: var(--size-caption); text-transform: none; letter-spacing: normal; }',
    '#usecases #ucl-group .nch, #usecases #ucl-sort .nch, #usecases .vtabmenu .nch { display: none; }',
    '#usecases #ucl-group, #usecases #ucl-sort { box-sizing: border-box; display: inline-flex; align-items: center; justify-content: center; gap: 6px; width: auto; min-width: 0; height: auto; min-height: 28px; padding: 0 10px; border: 1px solid var(--grey-500); border-radius: 6px; background: transparent; color: var(--text); font-size: var(--size-body); font-weight: 500; }',
    '#usecases #ucl-group:hover, #usecases #ucl-sort:hover, #usecases #ucl-group[aria-expanded="true"], #usecases #ucl-sort[aria-expanded="true"] { background: var(--grey-100); }',
    '#usecases .vtabmenu::after { content: "\\2026"; font-size: var(--size-body); line-height: 1; letter-spacing: .05em; }',
    '#usecases #ucAddPage.newb, #usecases #ucAddPage.newb:hover, #usecases #ucAddPage.newb:focus-visible, #usecases #ucAddPage.newb[aria-expanded="true"] { box-sizing: border-box; min-height: 28px; min-width: 28px; padding: 0 8px; border: 1px dashed var(--brand-blue); border-radius: 6px; background: transparent; color: var(--brand-blue); font-weight: 600; }      /* ruling 19-11: Group by, Sort by and + per the prototype (28px high, 6px radius, padding 0 10 / 0 8, + dashed brand 600); bare px have no token */',
    '#usecases .fline-row { max-width: 560px; }',
    '#usecases .fline { padding-left: 34px; }',
    '#usecases .fline::before { content: ""; position: absolute; left: 12px; top: 50%; width: 9px; height: 9px; margin-top: -8px; border: 2px solid var(--text-muted); border-radius: 50%; box-sizing: content-box; }',
    '#usecases .fline::after { content: ""; position: absolute; left: 23px; top: 50%; width: 5px; height: 2px; margin-top: 4px; background: var(--text-muted); transform: rotate(45deg); transform-origin: 0 50%; }',
    '#usecases .fcount { position: absolute; width: 1px; height: 1px; margin: -1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }',
    '/* Row 1316 (Table and Status cell; sizes by eye, +/-2 px, no prototype file on this box): the use cases list as a framed card with a grey capitals header strip, the commitment as a quiet pill under the status pill (which the base already stacks). */',
    '#usecases .ucl-box { border: 1px solid var(--line-soft); border-radius: var(--radius); background: var(--surface); overflow: hidden; }',
    '#usecases .ucl-box .ucl-cols { padding: 10px var(--space-4); background: var(--grey-50); font-weight: var(--weight-semibold); letter-spacing: var(--tracking-caps); text-transform: uppercase; }',
    '#usecases .ucl-box .ucl-list .ucl-row { padding-left: var(--space-4); padding-right: var(--space-4); }',
    '#usecases .ucl-box .ucl-st .cchip { padding: 2px 9px; border: 1px solid var(--grey-300); border-radius: var(--radius-pill); background: transparent; color: var(--text-muted); font-size: var(--size-small); font-weight: var(--weight-regular); }',
    '/* Row 1316c (issue 1316, Classic only): the Use cases Next steps count is plain text, not a round badge (prototype "1 next step"; by eye, the prototype files are not on this box). Rebrand only. */',
    '#usecases .ucsteps .ucn-b { min-width: 0; min-height: 0; padding: 0; margin-right: 0; border-radius: 0; background: none; color: inherit; font-size: inherit; font-weight: inherit; line-height: inherit; }',
    '/* Row 1316d (issue 1316, ruling 00:31; Classic only, Cards unchanged): the Use cases filter at rest is a box as in the prototype (pages/usecases.css:47: 34px high, 1px border, radius 6px). The border is --grey-500, the Classic token that equals the prototype --ui in light and in dark. Focus adds no ring and no colour (ruling 1137); a line the filter cannot read keeps its red. Bare lengths: 34px box height, 6px radius. */',
    '#usecases .fline { min-height: 34px; padding-top: 0; padding-bottom: 0; border: 1px solid var(--grey-500); border-radius: 6px; background: var(--surface); }',
    '#usecases .fline.bad, #usecases .fline.bad:focus-within { border-color: var(--status-red); box-shadow: none; }',
    '/* Row 1316 gap (ruling 19-11): the 560px is the search box alone; the view icons stand beside it, not inside the 560. */',
    '#usecases .fline-row { max-width: none; }',
    '#usecases .fline-row > .fline { flex: 0 1 560px; }',
]


class Pinned1316(unittest.TestCase):
    def block(self):
        """From the 1316a comment to the next row's comment that is not a 1316 one (or the end): rows stack after it."""
        lines = RULES.split("\n")
        i = next(n for n, l in enumerate(lines) if l.startswith(START))
        out = [l for l in lines[i:i + 1] if l.strip()]
        for l in lines[i + 1:]:
            if l.startswith("/* Row ") and not l.startswith("/* Row 1316"):
                break
            if l.strip():
                out.append(l)
        return out

    def test_every_rule_line_is_exact_and_in_order(self):
        self.assertEqual(self.block(), RULE_LINES)


if __name__ == "__main__":
    unittest.main()
