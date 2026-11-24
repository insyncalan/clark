"""Row 1261 (reopened): the Report headline in the picker, the eye that hides its health pill, and the warning when At a glance shows the
health too. Server rules (the stored "pill" field, Word and Excel), the card, and the page at 1400 and 900 px, light and dark, measured
against the approved mock-up (mockups/1261-headline-template/headline-approved.html). Fictional data only.

Run: python3 dev/run_tests.py test_reportheadline_eye_1261
"""
import json
from pathlib import Path
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
            # The save is silent and the page keeps its step for Undo a moment after the stored body changes (after it reads the project again), so a key
            # pressed in that gap finds nothing to undo and says so. Press again until the pill is back; a key that found nothing changes nothing.
            for _ in range(6):
                p.key("z", modifiers=2, code="KeyZ", vk=90)
                if wait(lambda: "pill" not in self.stored(self.on), 3):
                    break
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

    WARNING = "Health is also on in At a glance. It would show twice on this page. Turn it off here."

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
    # --- Ruling 20-11 (2): no section heading in View and in the published page -------------------------------------------------------
    def test_view_has_no_visible_section_heading_for_the_headline_but_keeps_its_name_and_edit_keeps_it(self):
        gone = "(function(h){var r=h.getBoundingClientRect();return [r.width,r.height,h.textContent]})(document.querySelector('[data-id=\"%s\"] > .sec-head'))"
        for width in (1400, 900):
            with self.subTest(width=width), chrome() as cdp:
                p = self.sized(cdp, width, "light")
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-text')", "drew")
                w, h, text = p.js(gone % self.on)
                self.assertLessEqual((w, h), (1, 1), "View: the heading is visually hidden (the mock-up has only the page title)")
                self.assertEqual(text.strip().split()[-2:], ["Fictional", "on"], "but it is still in the page, so the section keeps its accessible name")
                self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] .sec-h').textContent"), "Fictional on")
                other = p.js("(function(){var s=document.querySelector('#report .sec:not([data-type=reportheadline]) > .sec-head');return s.getBoundingClientRect().width})()")
                self.assertGreater(other, 50, "another section keeps its visible heading")
                p.edit()
                p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] textarea')", "edit drew")
                w, h, _ = p.js(gone % self.on)
                self.assertGreater(w, 50, "Edit keeps the heading")

    def test_cards_view_keeps_the_heading(self):
        self.s.close()
        self.s = real_server(self.store.path, self.store.data_for, page_html=lambda: testpage.html(), seam=self.seam)
        self.addCleanup(self.s.close)
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-text')", "drew")
            self.assertGreater(p.js(f"document.querySelector('[data-id=\"{self.on}\"] > .sec-head').getBoundingClientRect().width"), 50, "Cards is unchanged")

    def test_the_published_page_hides_the_heading_the_same_way(self):
        css = "".join((Path(page.__file__).parent.parent / "themes" / "prototype-2.0" / f).read_text(encoding="utf-8") for f in ("rules.css", "rules-2.css"))
        self.assertIn('#report[data-mode="view"] .sec[data-type="reportheadline"] > .sec-head', css, "one rule for View and the published page (both draw #report in view mode)")
        self.assertLess(css.index('.sec[data-type="reportheadline"] > .sec-head'), css.index("/* Row 1314"), "Classic CSS before the Row 1314 block")

    # --- Ruling 20-11 (3): the pill default follows the health tile ------------------------------------------------------------------
    def test_the_server_takes_the_pill_off_start_body_and_no_other_body_for_a_new_report_headline(self):
        self.assertEqual(rh.START, '{"pill":false,"v":1}')
        self.assertEqual(json.dumps(rh.check(json.loads(rh.START), Rules), sort_keys=True, separators=(",", ":")), rh.START, "canonical, as the store writes it")
        from clark import changes
        self.assertEqual(changes.REPORT_HEADLINE_START, rh.START)

    def test_a_new_headline_with_the_pill_off_start_is_stored_and_shows_no_pill_and_one_with_no_body_shows_it(self):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Headline", "sort_order": 995, "body": rh.START})
        self.assertEqual(self.stored(ref), {"pill": False, "v": 1})
        self.assertFalse(rh.upgrade(self.stored(ref))["pill"])
        self.assertTrue(rh.upgrade("")["pill"], "no health tile showing: a new Report headline has the pill on")

    def test_the_change_api_takes_the_pill_off_start_body_for_a_new_report_headline_and_refuses_any_other_body(self):
        from clark import changes
        change = changes.make_change(self.store.path, [], USER)
        req = lambda body: {"project": "ABC", "kind": "report_sections", "op": "new", "place": "report", "values": {"type": "reportheadline", "title": "Headline", "body": body}}
        status, got = change(req('{"pill":false,"v":1}'))
        self.assertEqual((status, got.get("message")), (200, None), got)
        made = [r for r in self.store.read("report_sections", "ABC") if r["type"] == "reportheadline" and r["title"] == "Headline"]
        self.assertEqual([json.loads(r["body"]) for r in made], [{"pill": False, "v": 1}], "stored with the pill off")
        for other in ('{"v":1,"headline":"x"}', '{"pill":true,"v":1}', "x"):
            status, got = change(req(other))
            self.assertEqual((status, got["message"]), (400, changes.NO_BODY_HERE), other)
        status, got = change({"project": "ABC", "kind": "report_sections", "op": "new", "place": "report", "values": {"type": "reportheadline", "title": "Headline"}})
        self.assertEqual(status, 200, "with no health tile showing the card sends no body: the pill is on")

    # --- Ruling 20-11 (4): the Edit pill and fields match the mock-up ----------------------------------------------------------------
    def test_the_edit_pill_is_the_view_capsule_with_an_arrow_and_the_fields_are_the_mock_ups_boxes(self):
        with chrome() as cdp:
            p = self.sized(cdp, 1400, "light")
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-pill')", "drew")
            view = self.box(p, self.on, ".tpl-rh-pill")
            p.edit()
            p.until(f"!!document.querySelector('[data-id=\"{self.on}\"] textarea')", "edit drew")
            pill = self.box(p, self.on, "button.pillbtn")
            self.assertEqual(pill["h"], 28, "28px high, as the View capsule")
            self.assertEqual(pill["bg"], view["bg"], "the same tint as the View capsule, not the old solid amber")
            self.assertEqual((pill["fs"], pill["fw"], pill["pad"]), (view["fs"], view["fw"], view["pad"]))
            self.assertEqual(p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] button.pillbtn')).borderTopLeftRadius"), p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-pill')).borderTopLeftRadius"), "pill radius")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] button.pillbtn svg[data-hl=triangle]') !== null"), True, "the state's icon")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] button.pillbtn .nch') !== null"), True, "plus a small arrow")
            self.assertEqual(p.js(f"document.querySelector('[data-id=\"{self.on}\"] button.pillbtn').getAttribute('aria-label')"), "Project health: at risk. Change it")
            f = p.js(f"""(function(){{ var a = document.querySelector('[data-id="{self.on}"] textarea[aria-label=Headline]'), b = document.querySelector('[data-id="{self.on}"] textarea[aria-label="Supporting sentence"]'),
              c = getComputedStyle(a), d = getComputedStyle(b), l = document.querySelector('[data-id="{self.on}"] .tpl-lbl').getBoundingClientRect();
              return [c.borderTopColor, c.borderTopWidth, c.borderTopLeftRadius, parseFloat(c.minHeight), c.paddingTop + ' ' + c.paddingRight, c.fontWeight, d.fontWeight, Math.round(a.getBoundingClientRect().top - l.bottom)]; }})()""")
            self.assertEqual(f, ["rgb(135, 148, 179)", "1px", "6px", 64, "6px 10px", "700", "400", 2], "mock-up field: 1px rgb(135,148,179) edge, radius 6, min-height 64, padding 6px 10px, headline bold, 2px under its label")

    # --- Ruling 20-11 (5): the card's name ---------------------------------------------------------------------------------------------
    def test_the_picker_card_is_named_report_headline_and_keeps_its_approved_words(self):
        src = open(page.__file__.replace("__init__.py", "src/logic/templates.js"), encoding="utf-8").read()
        self.assertIn('{ id: "report-headline", name: "Report headline"', src)
        self.assertIn('"A health pill, a headline and a supporting sentence at the top of the report."', src)
        self.assertIn('"Health pill · optional"', src)

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
                self.assertTrue(p.js(f"getComputedStyle(document.querySelector('[data-id=\"{self.on}\"] .tpl-rh-title')).fontFamily").startswith("Montserrat"), "mock-up h1 is Montserrat")
                self.assertEqual(meta["margin"], "4px", "the rendered mock-up: 4px under the meta line (ruling 20-11; its .top p rule beats .meta 16px)")
                self.assertAlmostEqual(row["y"] - title["y"], 65, delta=0.6, msg=f"title top to the top rule is 65px in the rendered mock-up, not 77: {row['y'] - title['y']}")
                self.assertEqual((row["gap"], row["pad"]), ("12px", "12px 0px"), "mock-up .health gap 12px, padding 12px 0")
                self.assertEqual(row["border"][:3], "1px")
                want = p.js("(function(){ var e = document.createElement('i'); e.style.borderTop = '1px solid var(--grey-200)'; document.body.appendChild(e); var c = getComputedStyle(e).borderTopColor; e.remove(); return c; })()")
                self.assertEqual(row["border"][4:], want, "the rule colour is the mock-up's: --grey-200 (rgb 217, 224, 239 in light), not --border")
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
        for width, theme in ((1400, "light"), (1400, "dark"), (900, "light"), (900, "dark")):
            with self.subTest(width=width, theme=theme), chrome() as cdp:
                p = self.sized(cdp, width, theme)
                p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] .tpl-rh-text')", "drew")
                sec = self.box(p, self.on, ".tpl-rh-block")
                cells = p.js("(function(){ var g = document.querySelector('.secs'), cols = getComputedStyle(g).gridTemplateColumns.split(' ').map(parseFloat); "
                             "return {cols: cols, left: document.querySelector('.slot-left').getBoundingClientRect().width, right: document.querySelector('.slot-right').getBoundingClientRect().width}; })()")
                for ref in (self.on, self.off):
                    w = p.js(f"document.querySelector('[data-id=\"{ref}\"]').getBoundingClientRect().width")
                    self.assertTrue(any(abs(w - c) <= 1 for c in cells["cols"]), f"the half section fills its grid cell at {width} in {theme}: {w} vs {cells['cols']}")
                self.assertAlmostEqual(cells["left"], cells["right"], delta=1, msg=f"the two halves are equally wide at {width} in {theme}")
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


    # --- contrast (WCAG 2.x AA, 4.5:1) in both themes: headline, supporting sentence and pill text, from the computed colours ----------
    def test_the_headline_the_sentence_and_the_pill_text_pass_4_5_to_1_in_light_and_dark(self):
        js = """(function(ref, rest){
          function parse(c){ var m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; }
          function over(f, b){ return {r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1}; }
          function lin(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
          function lum(c){ return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b); }
          var el = document.querySelector('[data-id="' + ref + '"] ' + rest); if (!el) return null;
          var layers = [], n = el; while (n && n.nodeType === 1) { layers.push(parse(getComputedStyle(n).backgroundColor)); n = n.parentElement; }
          var bg = {r: 255, g: 255, b: 255, a: 1}; for (var i = layers.length - 1; i >= 0; i--) bg = over(layers[i], bg);
          var fg = over(parse(getComputedStyle(el).color), bg), a = lum(fg), b = lum(bg);
          return (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05); })(%s, %s)"""
        for theme in ("light", "dark"):
            with chrome() as cdp:
                p = self.sized(cdp, 1400, theme)
                p.until(f"!!document.querySelector('[data-id=\"{self.off}\"] .tpl-rh-text')", "drew")
                for ref, rest in ((self.on, ".tpl-rh-h"), (self.on, ".tpl-rh-p"), (self.on, ".tpl-rh-pill"), (self.off, ".tpl-rh-h"), (self.off, ".tpl-rh-p")):
                    ratio = p.js(js % (json.dumps(ref), json.dumps(rest)))
                    self.assertIsNotNone(ratio, f"{rest} drawn")
                    self.assertGreaterEqual(ratio, 4.5, f"{rest} in {theme}: {ratio:.2f}:1")


    def test_all_four_pills_text_passes_4_5_to_1_in_light_and_dark_at_1400(self):
        js = """(function(ref, rest){
          function parse(c){ var m = c.match(/[\\d.]+/g).map(Number); return {r: m[0], g: m[1], b: m[2], a: m.length > 3 ? m[3] : 1}; }
          function over(f, b){ return {r: f.r * f.a + b.r * (1 - f.a), g: f.g * f.a + b.g * (1 - f.a), b: f.b * f.a + b.b * (1 - f.a), a: 1}; }
          function lin(v){ v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }
          function lum(c){ return 0.2126 * lin(c.r) + 0.7152 * lin(c.g) + 0.0722 * lin(c.b); }
          var el = document.querySelector('[data-id="' + ref + '"] ' + rest); if (!el) return null;
          var layers = [], n = el; while (n && n.nodeType === 1) { layers.push(parse(getComputedStyle(n).backgroundColor)); n = n.parentElement; }
          var bg = {r: 255, g: 255, b: 255, a: 1}; for (var i = layers.length - 1; i >= 0; i--) bg = over(layers[i], bg);
          var fg = over(parse(getComputedStyle(el).color), bg), a = lum(fg), b = lum(bg);
          return [el.textContent.trim(), (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05)]; })(%s, %s)"""
        refs = {}
        with self.store.step("dashboard", USER) as st:
            for i, (health, word) in enumerate((("at_risk", "At risk"), ("on_track", "On track"), ("off_track", "Off track"), ("", "Not set"))):
                refs[word] = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional " + word, "sort_order": 980 + i,
                                                           "body": json.dumps({"v": 1, "health": health, "headline": "Fictional plan holds", "sentence": "Fictional reason."})})
        for theme in ("light", "dark"):
            with chrome() as cdp:
                p = self.sized(cdp, 1400, theme)
                p.until(f"!!document.querySelector('[data-id=\"{refs['Not set']}\"] .tpl-rh-pill')", "drew")
                for word, ref in refs.items():
                    got = p.js(js % (json.dumps(ref), json.dumps(".tpl-rh-pill")))
                    self.assertIsNotNone(got, f"{word} pill drawn")
                    self.assertEqual(got[0], word)
                    self.assertGreaterEqual(got[1], 4.5, f"{word} pill in {theme}: {got[1]:.2f}:1")


if __name__ == "__main__":
    unittest.main()
