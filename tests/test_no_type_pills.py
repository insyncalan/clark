"""Row 1059: the Work items page has no type pills (All, Actions, Risks and issues, Decisions) and no status pills (Open, Closed, All).

Type and status are reached through the filter line (type:, status:, is:open, is:closed) and the saved view tabs. Driven in the real page at
1400 and 900 px, in light and in dark. The published file has no filter line, so its switches stay (it has no other way to them).
"""
import unittest

from test_filter_line_page import INPUT, Line, chrome, wait  # noqa: E402
from test_work_filters import set_line  # noqa: E402

PILLS = "[data-type=all], [data-type=action], [data-type=risk], [data-type=decision], [data-show], .wbar [aria-label=Type], .wbar [aria-label='Open or closed']"


class NoTypePills(Line):
    def test_the_app_page_has_no_type_or_status_pills_and_the_line_still_does_their_job(self):
        s = self.serve()
        for width in (1400, 900):
            for theme in ("light", "dark"):
                with self.subTest(width=width, theme=theme), chrome() as cdp:
                    sid = self.load(cdp, s.port, width, theme=theme)
                    self.assertEqual(cdp.js(f"document.querySelectorAll({PILLS!r}).length", sid), 0)
                    self.assertEqual(self.chips(cdp, sid), ["is:open"])
                    self.assertTrue(cdp.js(f"!!document.querySelector({INPUT!r})", sid), "the filter line is there")
                    self.assertTrue(cdp.js("document.querySelectorAll('.vtabs button, .vtabs [role=tab]').length > 0", sid), "the saved view tabs are there")
                    rows = self.rows(cdp, sid)
                    for line in ("is:closed", "type:action", "status:Open"):
                        set_line(cdp, sid, line)
                        self.assertTrue(wait(lambda: self.chips(cdp, sid) == [line]), line)
                        self.assertTrue(wait(lambda: len(self.shown(cdp, sid)) <= len(rows)), line)
                    self.assertEqual(cdp.js("document.documentElement.scrollWidth <= window.innerWidth", sid), True)


for _name in [n for n in dir(Line) if n.startswith("test_")]:     # only the helpers of Line are wanted here, not its tests
    if _name not in NoTypePills.__dict__:
        setattr(NoTypePills, _name, None)


if __name__ == "__main__":
    unittest.main()
