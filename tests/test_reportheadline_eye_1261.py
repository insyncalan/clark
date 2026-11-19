"""Row 1261 (reopened): the Report headline in the picker, the eye that hides its health pill, and the warning when At a glance shows the
health too. Server rules (the stored "pill" field, Word and Excel), the card, and the page at 1400 and 900 px, light and dark, measured
against the approved mock-up (mockups/1261-headline-template/headline-approved.html). Fictional data only.

Run: python3 dev/run_tests.py test_reportheadline_eye_1261
"""
import json
import unittest

from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import docx_build, excel_client, page, section_kinds, theme
import _testpage as testpage
from _real_server import real_server
from clark.section_kinds import base, reportheadline as rh
import test_reportheadline_export_1261 as ex


class Rules:
    plain = visible = staticmethod(lambda t: t)


class Stored(unittest.TestCase):
    def test_a_hidden_pill_is_stored_and_a_shown_one_is_not(self):
        self.assertEqual(rh.check({"v": 1, "pill": False, "headline": "H"}, Rules), {"v": 1, "pill": False, "headline": "H"})
        self.assertEqual(rh.check({"v": 1, "pill": True, "headline": "H"}, Rules), {"v": 1, "headline": "H"})
        self.assertEqual(rh.check({"v": 1, "pill": None, "headline": "H"}, Rules), {"v": 1, "headline": "H"})

    def test_a_pill_that_is_not_yes_or_no_is_refused_in_words_that_do_not_quote_it(self):
        for bad in ("no", 0, 1, [], {}, "secret-word"):
            with self.subTest(bad=bad), self.assertRaises(base.Bad) as got:
                rh.check({"v": 1, "pill": bad}, Rules)
            self.assertNotIn("secret-word", str(got.exception))

    def test_an_older_body_without_the_field_shows_the_pill(self):
        self.assertTrue(rh.upgrade({"v": 1, "health": "on_track"})["pill"])
        self.assertTrue(rh.upgrade(None)["pill"])
        self.assertFalse(rh.upgrade({"v": 1, "pill": False})["pill"])
        self.assertTrue(rh.upgrade({"v": 1, "pill": "no"})["pill"], "a wrong kind of value reads as the default")

    def test_the_file_carries_the_choice_and_a_hidden_pill_alone_still_leaves_the_section_out(self):
        self.assertEqual(rh.published({"v": 1, "health": "at_risk", "headline": "H", "pill": False}, None)["content"],
                         {"health": "at_risk", "headline": "H", "sentence": "", "pill": False})
        self.assertTrue(rh.published({"v": 1, "health": "at_risk", "headline": "H"}, None)["content"]["pill"])
        self.assertIsNone(rh.published({"v": 1, "pill": False}, None))
        self.assertIsNone(rh.published({"v": 1, "health": "on_track", "pill": False}, None), "a health whose pill is hidden shows nothing")
        self.assertIsNotNone(rh.published({"v": 1, "health": "on_track"}, None))
        self.assertIsNotNone(rh.published({"v": 1, "sentence": "S", "pill": False}, None))

    def test_the_registry_still_holds_it(self):
        self.assertIs(section_kinds.REGISTRY["reportheadline"], rh)


class Exports(unittest.TestCase):
    BODY = {"v": 1, "health": "at_risk", "headline": "Fictional line", "sentence": "Fictional reason.", "pill": False}

    def test_word_leaves_the_pill_out_and_keeps_the_words(self):
        on = ex.doc_xml(docx_build.build(ex.select()))
        off = ex.doc_xml(docx_build.build(ex.select(body=self.BODY)))
        self.assertEqual(on.count(">At risk<"), off.count(">At risk<") + 1, "the page's health may be named elsewhere in the file; this section's pill is the one that goes")
        self.assertIn("Go live moves one week", on)
        self.assertIn("Fictional line", off)
        self.assertIn("Fictional reason.", off)

    def test_excel_leaves_the_health_word_out_of_the_headline_line(self):
        self.assertEqual(excel_client.headline_line(ex.select(body=self.BODY)), "Fictional line · Fictional reason.")
        self.assertTrue(excel_client.headline_line(ex.select()).startswith("At risk · "))

    def test_a_hidden_pill_with_nothing_else_is_left_out_of_the_workbook_line(self):
        self.assertEqual(excel_client.headline_line(ex.select(body={"v": 1, "health": "on_track", "pill": False})), "")


class Eye(Base):
    """The page. A section with the pill on, one with it off, an empty one, and (per test) At a glance sections."""

    def setUp(self):
        super().setUp()
        self.s.close()      # the Classic page: the test page with the Classic theme layered (the rules of this row are in the Classic layer only)
        css = theme.css("prototype-2.0")
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: page.layer_theme(testpage.html(), css), seam=self.seam)
        self.addCleanup(self.s.close)
        with self.store.step("dashboard", USER) as st:
            self.on = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional on", "sort_order": 990,
                                                    "body": json.dumps({"v": 1, "health": "at_risk", "headline": "Fictional plan holds", "sentence": "Fictional reason."})})
            self.off = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional off", "sort_order": 991,
                                                     "body": json.dumps({"v": 1, "health": "at_risk", "pill": False, "headline": "Fictional plan holds", "sentence": "Fictional reason."})})

    def add(self, type_, body, order=992):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": type_, "title": "Fictional glance", "sort_order": order, "body": json.dumps(body) if body else ""})

    def hide_glance(self):
        """The demo report starts with the built-in At a glance (its health tile cannot be hidden), which makes the warning true; hide it for the tests that need none."""
        with self.store.step("dashboard", USER) as st:
            for r in self.store.read("report_sections", "ABC"):
                if r["type"] in ("glance", "glancetemplate"):
                    st.update("report_sections", r["id"], {"hidden": 1})

    def stored(self, ref):
        return json.loads(self.store.read("report_sections", ref=ref)["body"])

    def sized(self, cdp, width, theme):
        p = self.visit(cdp)
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
        return p

    def box(self, p, ref, rest):
        return p.js(f"""(function(){{ var e = document.querySelector('[data-id="{ref}"] {rest}'); if (!e) return null; var r = e.getBoundingClientRect(), c = getComputedStyle(e);
          return {{x: r.left, y: r.top, w: r.width, h: r.height, right: r.right, fs: c.fontSize, fw: c.fontWeight, pad: c.padding, border: c.borderTopWidth + ' ' + c.borderTopColor,
                   bg: c.backgroundColor, margin: c.marginBottom, gap: c.columnGap, ls: c.letterSpacing}}; }})()""")

    # --- View -----------------------------------------------------------------------------------------------------------------
    def test_view_draws_the_pill_when_on_and_starts_the_text_at_the_left_when_off(self):
        for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] .tpl-rh-text')", "the sections drew")
                self.assertIsNotNone(self.box(p, self.on, ".tpl-rh-pill"), "pill on: the pill is drawn")
                self.assertIsNone(self.box(p, self.off, ".tpl-rh-pill"), "pill off: no pill in the page")
                row, text = self.box(p, self.off, ".tpl-rh"), self.box(p, self.off, ".tpl-rh-text")
                self.assertAlmostEqual(text["x"], row["x"], delta=1, msg=f"the text starts at the left edge of the row: {text['x']} vs {row['x']}")
                self.assertAlmostEqual(text["right"], row["right"], delta=1, msg="and runs to its right edge")
                self.assertFalse(p.js("document.documentElement.scrollWidth > window.innerWidth"), "no sideways scroll")

    def test_the_page_texts_of_a_hidden_pill_do_not_name_the_health(self):
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] .tpl-rh-text')", "drew")
            self.assertNotIn("At risk", p.js(f"document.querySelector('[data-id=\"{self.off}\"]').textContent"))
            self.assertIn("At risk", p.js(f"document.querySelector('[data-id=\"{self.on}\"]').textContent"))

    # --- Edit: the eye --------------------------------------------------------------------------------------------------------
    def test_the_eye_hides_and_shows_the_pill_and_saves_one_field(self):
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.edit()
            eye = f'[data-id="{self.on}"] [data-rh-eye]'
            p.until(f"!!document.querySelector('{eye}')", "the eye")
            self.assertEqual(p.js(f"document.querySelector('{eye}').getAttribute('aria-pressed')"), "false")
            self.assertEqual(p.js(f"document.querySelector('{eye}').getAttribute('aria-label')"), "Hide project health from the Report headline")
            self.assertEqual(p.js(f"document.querySelector('{eye}').tagName"), "BUTTON")
            self.assertIsNone(p.js(f"document.querySelector('{eye}').getAttribute('role')"), "a button with aria-pressed, never a switch")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-eyerow span').textContent"), "Show project health here")
            self.assertIsNotNone(self.box(p, self.on, ".pillbtn"))
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: self.stored(self.on).get("pill") is False, 10), f"saved as hidden: {self.stored(self.on)}")
            self.assertEqual(self.stored(self.on)["health"], "at_risk", "the health is kept")
            p.until(f"document.querySelector('{eye}').getAttribute('aria-pressed') === 'true'", "pressed means hidden")
            self.assertEqual(p.js(f"document.querySelector('{eye}').getAttribute('aria-label')"), "Show project health in the Report headline")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-eyerow span').textContent"), "Show project health here (hidden)")
            self.assertIsNone(self.box(p, self.on, ".pillbtn"), "no pill menu while the pill is hidden")
            self.assertIsNotNone(self.box(p, self.on, "textarea[aria-label=Headline]"), "the headline stays")
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: "pill" not in self.stored(self.on), 10), f"shown again: the default is not stored: {self.stored(self.on)}")
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .pillbtn')", "the pill menu is back")

    def test_the_eye_is_undone_in_one_step(self):
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.edit()
            eye = f'[data-id="{self.on}"] [data-rh-eye]'
            p.until(f"!!document.querySelector('{eye}')", "the eye")
            n = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            p.js(f"document.querySelector('{eye}').click()")
            self.assertTrue(wait(lambda: self.stored(self.on).get("pill") is False, 10))
            p.js("document.activeElement && document.activeElement.blur()")
            p.key("z", modifiers=2, code="KeyZ", vk=90)
            self.assertTrue(wait(lambda: "pill" not in self.stored(self.on), 10), "Undo shows the pill again")
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], n + 2, "one change, one undo")

    def test_the_eye_row_is_the_mock_ups_size_at_1400_and_900_in_light_and_dark(self):
        for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]')", "the eye")
                eye = self.box(p, self.on, "[data-rh-eye]")
                self.assertEqual((round(eye["w"]), round(eye["h"])), (28, 28), f"mock-up .teye.inl 28 x 28: {eye}")
                self.assertTrue(eye["border"].startswith("1px"), eye["border"])
                row = self.box(p, self.on, ".tpl-rh-eyerow")
                self.assertEqual(row["fs"], "13px", "mock-up .swrow 13px")
                self.assertEqual(row["gap"], "8px", "mock-up .swrow gap 8px")
                self.assertEqual(row["margin"], "10px", "mock-up .swrow margin-bottom 10px")
                self.assertFalse(p.js("document.documentElement.scrollWidth > window.innerWidth"), "no sideways scroll")

    # --- Edit: the warning ----------------------------------------------------------------------------------------------------
    def warn(self, p, ref):
        return p.js(f"""(function(){{ var e = document.querySelector('[data-id="{ref}"] [data-rh-warn]'); return e ? e.textContent : null; }})()""")

    WARNING = "Health is also on in At a glance. It would show twice on this page. Turn it off here or hide the Project health tile in At a glance."

    def test_no_other_health_no_warning(self):
        self.hide_glance()
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]')", "the eye")
            self.assertIsNone(self.warn(p, self.on))

    def test_the_built_in_at_a_glance_and_a_template_with_the_health_on_warn_a_template_with_it_off_does_not(self):
        cases = ((None, None, False), ("glance", "", True), ("glancetemplate", {"v": 1}, True),
                 ("glancetemplate", {"v": 1, "health": {"shown": True}}, True), ("glancetemplate", {"v": 1, "health": {"shown": False}}, False),
                 ("hidden-glance", "", False))
        for type_, body, warns in cases:
            with self.subTest(type=type_, body=body), chrome() as cdp:
                self.hide_glance()
                if type_ == "hidden-glance":
                    self.add("glance", body)
                    with self.store.step("dashboard", USER) as st:
                        for r in self.store.read("report_sections", "ABC"):
                            st.update("report_sections", r["id"], {"hidden": 1}) if r["type"] == "glance" else None
                elif type_:
                    ref = self.add(type_, body)
                p = self.sized(cdp, 1400, "light")
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]')", "the eye")
                self.assertEqual(self.warn(p, self.on), self.WARNING if warns else None)
                self.assertIsNone(self.warn(p, self.off), "a section with its pill off never warns")
            with self.store.step("dashboard", USER) as st:
                for r in self.store.read("report_sections", "ABC"):
                    if r["sort_order"] == 992:
                        st.update("report_sections", r["id"], {"hidden": 1})

    def test_the_warning_goes_when_the_pill_is_turned_off_and_is_the_mock_ups_look(self):
        self.add("glance", "")
        for width, theme in ((1400, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] [data-rh-warn]')", "the warning")
                w = self.box(p, self.on, "[data-rh-warn]")
                self.assertEqual(w["fs"], "13px")
                self.assertEqual(w["pad"], "6px 10px", "mock-up .warnline padding")
                self.assertEqual(p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] [data-rh-warn]')).borderLeftWidth"), "3px")
                self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] [data-rh-warn]').getAttribute('role')"), "status")
                self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] [data-rh-warn] b').textContent"), "Health is also on in At a glance.")
                self.assertFalse(p.js("document.documentElement.scrollWidth > window.innerWidth"))
                p.js(f"document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]').click()")
                p.until(f"!document.querySelector('[data-id=\"{self.on}\"] [data-rh-warn]')", "the warning goes with the pill")
                p.js(f"document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]').click()")      # put it back for the next width
                self.assertTrue(wait(lambda: "pill" not in self.stored(self.on), 10))

    def test_cards_keeps_its_edit_as_it_was_no_eye_and_no_warning_and_a_hidden_pill_still_has_its_menu(self):
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] textarea')", "drew")
            for ref in (self.on, self.off):
                self.assertIsNone(self.box(p, ref, "[data-rh-eye]"), "Cards: no eye")
                self.assertIsNone(self.warn(p, ref), "Cards: no warning")
                self.assertIsNotNone(self.box(p, ref, ".pillbtn"), "Cards: the pill menu stays, as on main")

    # --- Defaults -------------------------------------------------------------------------------------------------------------
    def test_defaults_a_new_headline_has_the_pill_on_and_a_new_glance_template_has_its_health_off(self):
        self.hide_glance()      # the built-in At a glance a new project starts with keeps its tile (it cannot be hidden); the template is the one with the eye
        self.assertTrue(rh.upgrade("")["pill"], "a new Report headline starts with the pill on")
        self.assertTrue(rh.upgrade({"v": 1})["pill"])
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] [data-rh-eye]')", "page drew")
            new = self.add("reportheadline", "", 993)
            new_glance = self.add("glancetemplate", "", 994)
            p.reload()
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{new}\"] [data-rh-eye]')", "the new sections drew")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{new}\"] [data-rh-eye]').getAttribute('aria-pressed')"), "false", "pill on")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{new_glance}\"] [data-tile=health]') === null"), True, "the At a glance health tile starts off")
            self.assertIsNone(self.warn(p, new), "so a new page shows health once and warns about nothing")

    # --- Sizes against the approved mock-up -------------------------------------------------------------------------------------
    def test_the_view_sizes_are_the_mock_ups_at_1400_and_900_in_light_and_dark(self):
        for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-pill')", "drew")
                title, meta, row = (self.box(p, self.on, c) for c in (".tpl-rh-title", ".tpl-rh-meta", ".tpl-rh"))
                pill, head = self.box(p, self.on, ".tpl-rh-pill"), self.box(p, self.on, ".tpl-rh-h")
                self.assertEqual((title["fs"], title["fw"], title["margin"]), ("30px", "600", "4px"), f"mock-up h1 30px 600, 4px under: {title}")
                self.assertEqual(p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-title')).lineHeight"), "36px", "line height 1.2")
                self.assertEqual(meta["margin"], "16px", "mock-up .meta 16px under")
                self.assertEqual((row["gap"], row["pad"]), ("12px", "12px 0px"), "mock-up .health gap 12px, padding 12px 0")
                self.assertEqual(row["border"][:3], "1px")
                self.assertEqual((pill["fs"], pill["fw"], pill["pad"], pill["gap"]), ("14px", "700", "2px 12px", "6px"), f"mock-up .rag 14px bold, 2px 12px, gap 6px: {pill}")
                self.assertGreaterEqual(pill["h"], 28, "mock-up .rag min-height 28px")
                self.assertEqual(pill["ls"], "0.42px", "mock-up .rag tracking .03em of 14px")
                self.assertEqual((head["fs"], head["fw"]), ("16px", "700"), "mock-up .lead 16px bold")
                self.assertLess(pill["x"] + pill["w"], self.box(p, self.on, ".tpl-rh-text")["x"], "the pill stays beside the text, also at 900")
                print(f"view {width} {theme}: title {title['fs']}/{title['fw']}, pill {pill['w']:.0f} x {pill['h']:.0f} {pill['fs']}/{pill['fw']}, headline {head['fs']}/{head['fw']}, text column {self.box(p, self.on, '.tpl-rh-text')['w']:.0f} px", flush=True)

    # --- Half width and sizes -------------------------------------------------------------------------------------------------
    def test_half_width_fits_with_the_pill_and_without_at_1400_and_900(self):
        with self.store.step("dashboard", USER) as st:
            for ref in (self.on, self.off):
                st.update("report_sections", ref, {"beside": 1})
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] .tpl-rh-text')", "drew")
                sec = self.box(p, self.on, ".tpl-rh-block")
                print(f"half width {width}: section block {sec['w']:.0f} px", flush=True)
                for ref in (self.on, self.off):
                    block = self.box(p, ref, ".tpl-rh-block")
                    for rest in (".tpl-rh-text", ".tpl-rh-h", ".tpl-rh-p"):
                        part = self.box(p, ref, rest)
                        self.assertLessEqual(part["right"], block["right"] + 1, f"{rest} inside the block")
                self.assertFalse(p.js("document.documentElement.scrollWidth > window.innerWidth"))
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] textarea')", "edit drew")
                for ref in (self.on, self.off):
                    block = self.box(p, ref, ".tpl-edit")
                    for rest in ("textarea[aria-label=Headline]", "textarea:nth-of-type(2)", "[data-rh-eye]"):
                        part = self.box(p, ref, rest)
                        self.assertLessEqual(part["right"], block["right"] + 1, f"{rest} inside the section in Edit")


if __name__ == "__main__":
    unittest.main()
