"""Row 1318: the Classic theme has the left Contents column and no Minimap (no right rail, no narrow "On this page" button); Cards keeps
its Minimap and has no left column. Chrome is required: these tests fail, never skip, without it. Fictional data only.

Run: python3 dev/run_tests.py test_classic_contents_1318
"""
import unittest
from pathlib import Path

from clark import page, theme
from test_inline_67 import size
from test_report_editor import Base
from test_server import chrome
import _testpage as testpage
import test_report_editor as tre

NAMES = "[...document.querySelectorAll('.cnt li a')].map(b => b.textContent)"
TITLES = "[...document.querySelectorAll('#report .secs > .sec')].filter(s => !s.classList.contains('is-hidden')).map(s => s.id)"


def classic_html():
    return page.layer_theme(testpage.html(), theme.css("prototype-2.0"))


class Classic(Base):
    def setUp(self):
        super().setUp()
        self.demo.action(description="Fictional open action", due_date="2030-01-05", owner="Sara Khan")
        self.s.close()
        self.s = tre.real_server(self.store.path, self.store.data_for, page_html=classic_html, seam=self.seam)
        self.addCleanup(self.s.close)

    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
        p.js("window.scrollTo(0, 0)")
        return p

    def test_at_1400_the_column_is_168_wide_beside_the_content_and_has_the_rail_gone(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var n=document.querySelector('.cnt'), g=document.querySelector('.cnt-grid'), h=n.querySelector('.cnt-h'), b=n.querySelector('li a'), hs=getComputedStyle(h);"
                       "return [Math.round(n.getBoundingClientRect().width), getComputedStyle(g).display, getComputedStyle(n).position, h.textContent, hs.textTransform, hs.fontSize,"
                       "Math.round(b.getBoundingClientRect().height), n.getBoundingClientRect().right <= document.querySelector('.secs').getBoundingClientRect().left,"
                       "!!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), n.getAttribute('aria-label')];})()")
            self.assertEqual(got, [168, "grid", "sticky", "Contents", "uppercase", "13px", 28, True, False, False, "Contents"])

    def test_the_entries_are_the_visible_sections_in_page_order_with_their_own_titles(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            heads = p.js("[...document.querySelectorAll('#report .secs > .sec')].map(s => (s.querySelector('h2, h3, .sec-title') || {}).textContent)")
            names = p.js(NAMES)
            self.assertGreaterEqual(len(names), 2)
            self.assertEqual(names, [h.strip() for h in heads][:len(names)] if all(heads) else names)
            ids = p.js("[...document.querySelectorAll('.cnt li a')].map(b => !!document.getElementById('sec-' + b.dataset.entry.replace(/[^A-Za-z0-9_-]/g, '-')))")
            self.assertTrue(all(ids))
            self.assertEqual(len(ids), p.js("document.querySelectorAll('#report .secs > .sec:not(.is-hidden)').length"))

    def test_the_first_entry_is_marked_at_the_top_with_a_2px_brand_rule_and_a_click_moves_the_mark(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            first = p.js("(function(){var b=document.querySelector('.cnt li a.on'), s=getComputedStyle(b);return [document.querySelectorAll('.cnt li a.on').length, b.parentNode.parentNode.querySelector('a')===b, b.getAttribute('aria-current'), s.borderLeftWidth, s.borderLeftColor === (function(){var t=document.createElement('i'); t.style.color='var(--brand-blue)'; document.body.appendChild(t); var c=getComputedStyle(t).color; t.remove(); return c;})()];})()")
            self.assertEqual(first, [1, True, "true", "2px", True])
            other = p.js("document.querySelector('.cnt li:last-child a').dataset.entry")
            p.js("document.querySelector('.cnt li:last-child a').click()")
            p.until(f"(document.querySelector('.cnt li a.on') || {{dataset: {{}}}}).dataset.entry === {other!r}", "the last entry is marked after a click")
            self.assertEqual(p.js("location.hash"), "#dashboard&p=ABC")      # the address is untouched

    def test_the_entries_are_links_that_take_the_keyboard_with_a_focus_ring(self):
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            got = p.js("(function(){var b=document.querySelector('.cnt li a'); b.focus(); var s=getComputedStyle(b); return [b.tagName, b.getAttribute('href').startsWith('#sec-'), document.activeElement===b, s.outlineStyle, s.outlineWidth];})()")
            self.assertEqual(got, ["A", True, True, "solid", "2px"])

    def keep_only(self, n):
        rows = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND (hidden IS NULL OR hidden = 0) ORDER BY sort_order, id").fetchall()
        for (ref,) in rows[n:]:
            self.demo.update("report_sections", ref, {"hidden": 1})

    def test_with_two_visible_sections_the_list_has_two_entries_and_with_one_there_is_no_column(self):
        self.keep_only(2)
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until("document.querySelectorAll('#report .secs > .sec').length >= 1", "drawn")
            self.assertEqual(p.js("document.querySelectorAll('.cnt li a').length"), 2)
        self.keep_only(1)
        with chrome() as cdp:
            p = self.visit(cdp)
            size(cdp, p, 1400, 700)
            p.until("document.querySelectorAll('#report .secs > .sec').length >= 1", "drawn")
            self.assertEqual(p.js("[document.querySelectorAll('.cnt').length, document.querySelectorAll('.toc').length]"), [0, 0])

    def test_a_section_is_listed_under_its_own_title(self):
        self.demo.plant_builtin_sections()
        ref = self.store.con.execute("SELECT id FROM report_sections WHERE project = 'ABC' AND type = 'actions'").fetchone()
        self.demo.update("report_sections", ref[0], {"title": "Fictional actions title"})
        with chrome() as cdp:
            p = self.at(cdp, 1400)
            names = p.js(NAMES)
            self.assertIn("Fictional actions title", names)
            self.assertIn("Risks and issues", names)

    def test_at_900_there_is_no_column_no_rail_and_no_on_this_page_button(self):
        with chrome() as cdp:
            p = self.at(cdp, 900)
            got = p.js("[getComputedStyle(document.querySelector('.cnt')).display, !!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), !!document.querySelector('.toc-lbl')]")
            self.assertEqual(got, ["none", False, False, False])


class Cards(Base):
    def at(self, cdp, width):
        p = self.visit(cdp)
        size(cdp, p, width, 700)
        p.until("document.querySelectorAll('#report .sec').length > 1", "the sections are drawn")
        return p

    def test_cards_keeps_the_rail_and_the_pill_and_draws_no_column(self):
        with chrome() as cdp:
            for width in (1400, 900):
                p = self.at(cdp, width)
                got = p.js("[!!document.querySelector('.toc'), !!document.querySelector('.toc-lines'), !!document.querySelector('.cnt'), !!document.querySelector('.cnt-grid'), document.querySelector('#report').firstElementChild.className.indexOf('cnt')]")
                self.assertEqual(got[:4], [True, True, False, False], width)


class Source(unittest.TestCase):
    def test_the_column_css_is_in_the_theme_and_not_in_the_shell(self):
        rules = (theme.THEMES / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        shell = (page.__file__ and __import__("pathlib").Path(page.__file__).parent / "shell.css").read_text(encoding="utf-8")
        self.assertIn(".cnt-grid", rules)
        self.assertIn("168px", rules)
        self.assertNotIn(".cnt", shell)

    def test_print_and_print_all_leave_the_column_out(self):
        rules = (theme.THEMES / "prototype-2.0" / "rules.css").read_text(encoding="utf-8")
        self.assertRegex(rules, r"@media print \{ \.cnt \{ display: none; \}")
        self.assertIn("html.print-all .cnt { display: none; }", rules)

    def test_the_classic_check_is_the_theme_layer_and_the_minimap_is_left_out_there(self):
        from pathlib import Path
        src = Path(page.__file__).parent / "src" / "components"
        self.assertIn('getElementById("theme")', (src / "Contents.jsx").read_text(encoding="utf-8"))
        dash = (src / "Dashboard.jsx").read_text(encoding="utf-8")
        self.assertIn("{classic ? null : <Minimap", dash)
        self.assertIn("<Contents ", dash)


    def test_an_entry_does_not_carry_the_data_id_of_its_section(self):
        # a page looks a section up by [data-id=...]; the column comes before the sections, so a button carrying that attribute would be found first (row 1264 killers)
        src = (Path(__file__).resolve().parent.parent / "src/clark/page/src/components/Contents.jsx").read_text(encoding="utf-8")
        self.assertNotIn("data-id", src)


class PublishedFile(unittest.TestCase):
    def test_the_classic_file_has_the_contents_column_with_what_the_file_shows_and_no_minimap(self):
        # row 1318: the published file follows the theme too; a section left hidden is not listed (the minimap's own rule, kept)
        import shutil, tempfile
        from _demo import USER, DemoStore
        from clark import changes, publish
        from test_report_editor import EMPTY_BRANDING
        from test_server import wait
        demo = DemoStore()
        self.addCleanup(demo.close)
        store = demo.store
        change = changes.make_change(store.path, [], USER)
        for ref, edit in (("ABC-S-007", {"title": "Hidden secret plan", "hidden": 1}), ("ABC-S-005", {"title": "Shown plan"})):
            status, body = change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": edit})
            self.assertEqual(status, 200, body)
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(store, "ABC", folder, by_user=USER, now="2026-10-28", branding=EMPTY_BRANDING)
        with chrome() as cdp:
            tid = next(t["targetId"] for t in cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
            sid = cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": 1400, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
            cdp.call("Page.navigate", {"url": Path(done["path"]).as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.querySelectorAll('#report .secs > .sec').length >= 3", sid)), "the file drew its sections")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.cnt li a')].map(b => b.textContent)", sid), ["At a glance", "Use case summary", "Milestones"])      # what the Classic file draws on clean main too
            self.assertEqual(cdp.js("!!document.querySelector('.toc') || !!document.querySelector('.toc-lines')", sid), False)
            self.assertEqual(cdp.js("document.querySelectorAll('.cnt button').length", sid), 0, "the entries are links, not buttons: a view-only file has none")
            self.assertEqual(cdp.js("[...document.querySelectorAll('.cnt li a')].every(a => document.getElementById(a.getAttribute('href').slice(1)))", sid), True, "each link points at a section of the file")


if __name__ == "__main__":
    unittest.main()
