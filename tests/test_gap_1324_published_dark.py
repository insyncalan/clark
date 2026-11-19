"""Row 1324 (rest after PR 1973): the Work items grouped view as Option A in the three places the audit found open (Classic only):
(1) the PUBLISHED Work items tab draws the same heading line (no tile, no band, one hairline, column names once on top);
(2) dark: the same look in dark, and the heading and the count read at 4.5:1 in light and dark, in the editor page and the published file;
(3) the heading weight is 600 (the --weight-medium token) in the computed style, light and dark.
Design and format only: no word is new. 900 wide is out (Tech Debt, ticket comment 20-11).

Run: python3 dev/run_tests.py test_gap_1324_published_dark
"""
import tempfile
import unittest
from pathlib import Path

from test_server import chrome, wait  # noqa: E402
import test_gap_1324_workitems as base  # noqa: E402
import test_publish_uc_list_1114 as pub  # noqa: E402
import test_use_cases_list as ucl  # noqa: E402
from test_publish import EMPTY_BRANDING, opened  # noqa: E402
import _publish_fixture as fx  # noqa: E402
from clark import page, publish  # noqa: E402

PROBE = base.PROBE
SELS = ["#work .grp-b .gl", "#work .grp-b .gc"]


def check(test, got, ctx):
    test.assertGreaterEqual(got["n"], 2, f"{ctx}: grouped")
    test.assertEqual((got["colh"], got["colhInGroup"]), (1, 0), f"{ctx}: the column names once, on top")
    test.assertEqual(got["tile"], ["rgba(0, 0, 0, 0)", "0px", "0px", "visible"], f"{ctx}: no tile")
    test.assertEqual(got["head"][:5], ["rgba(0, 0, 0, 0)", "0px", "6px", "0px", "1px"], f"{ctx}: no band, one hairline")
    test.assertEqual(got["btn"], ["600", "15px", "Montserrat"], f"{ctx}: heading weight 600, 15 px, heading face")
    test.assertEqual(got["count"][:2], ["13px", "2px"], f"{ctx}: count 13 px, 2 px before it")
    test.assertEqual(got["lineOf"], [got["line"]] * 2, f"{ctx}: the lines are the --grey-200 token")
    test.assertEqual(got["margins"], ["14px"] + ["18px"] * (got["n"] - 1), f"{ctx}: 14 px under the column names, 18 px between groups")
    test.assertTrue(got["wide"], f"{ctx}: no sideways scroll")


class EditorDark(base.WorkItemsOptionA):
    """The editor's grouped Work items page in dark and in light, with contrast (the inherited tests run again in light: left out below)."""

    def test_option_a_light_and_dark_with_contrast(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), chrome() as cdp:
                sid = self.load(cdp, 1400, scheme, "no-preference")
                check(self, cdp.js(PROBE, sid), f"editor {scheme}")
                ratios = cdp.js(ucl.contrast_script(SELS), sid)
                self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"editor {scheme}: heading and count read at 4.5 to 1: {ratios}")

    test_the_grouped_list_is_option_a_at_1400 = None
    test_hover_and_focus_of_the_heading = None
    test_a_group_shuts_and_the_one_column_row_stays = None


class Published(unittest.TestCase):
    """The published Work items tab, Classic Theme layered, grouped by Priority."""

    def go(self, cdp, tmp, scheme):
        plant = fx.load()
        p = publish.select(fx.inputs(plant))
        text = publish.render(p, page.page_html(EMPTY_BRANDING, view=True, theme=pub.THEME), plant["as_at"], p["data"]["project"]["name"])
        path = Path(tmp) / "w.html"
        path.write_text(text, encoding="utf-8")
        sid = opened(cdp, path.as_uri())
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
        self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready", sid) == "1"))
        cdp.js("document.querySelector('[data-view=work]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!!document.querySelector('#work h1')", sid)), "the Work items tab drew")
        cdp.js("document.querySelector('#group-by, [aria-label^=\"Group by\"]').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("!![...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === 'Priority')", sid)))
        cdp.js("[...document.querySelectorAll('[role^=menuitem]')].find(e => e.textContent.replace('✓', '').trim() === 'Priority').click()", sid)
        self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#work .grp-b').length", sid) >= 2))
        return sid

    def test_the_published_group_is_a_heading_line_in_light_and_dark(self):
        for scheme in ("light", "dark"):
            with self.subTest(scheme=scheme), tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
                sid = self.go(cdp, tmp, scheme)
                check(self, cdp.js(PROBE, sid), f"published {scheme}")
                ratios = cdp.js(ucl.contrast_script(SELS), sid)
                self.assertTrue(ratios and all(r[1] >= 4.5 for r in ratios), f"published {scheme}: 4.5 to 1: {ratios}")

    def test_a_published_group_shuts_and_keeps_one_column_row(self):
        with tempfile.TemporaryDirectory() as tmp, chrome() as cdp:
            sid = self.go(cdp, tmp, "light")
            cdp.js("document.querySelector('#work .grp-b').click()", sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelector('#work .grp-b').getAttribute('aria-expanded')", sid) == "false"))
            self.assertEqual(cdp.js("document.querySelectorAll('#work tr.colh').length", sid), 1)


if __name__ == "__main__":
    unittest.main()
