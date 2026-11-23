"""Row 1261 slice 1: the Report headline template's data layer (section_kinds/reportheadline.py): defaults, bad values, what is
published, the registry and the step that lets the store keep the type. Fictional data only.

Run: python3 dev/run_tests.py test_tpl_reportheadline
"""
import json
import sqlite3
import unittest

from _demo import USER
from test_report_editor import Base, tearDownModule  # noqa: F401
from test_server import chrome, wait

from clark import section_bodies, section_kinds, store as store_module
from clark.section_kinds import base, reportheadline as rh
from test_changes import KIND
from test_report_editor import Base as PageBase


class Rules:
    plain = visible = staticmethod(lambda t: t)


def check(v):
    return rh.check(v, Rules)


class Check(unittest.TestCase):
    def test_a_full_body_is_kept_as_it_is(self):
        body = {"v": 1, "health": "at_risk", "headline": "Go-live moves a week", "sentence": "The test cut-over found two gaps."}
        self.assertEqual(check(body), body)

    def test_missing_fields_take_their_defaults_and_are_not_stored(self):
        self.assertEqual(check({"v": 1}), {"v": 1})
        self.assertEqual(check({"v": 1, "health": None, "headline": "  ", "sentence": None}), {"v": 1})
        self.assertEqual(rh.upgrade({"v": 1}), {"v": 1, "health": "", "headline": "", "sentence": "", "pill": True})
        self.assertEqual(rh.upgrade(None), {"v": 1, "health": "", "headline": "", "sentence": "", "pill": True})
        self.assertEqual(rh.upgrade({"health": "nope", "headline": 4, "sentence": " a "}), {"v": 1, "health": "", "headline": "", "sentence": "a", "pill": True})

    def test_words_are_trimmed_and_a_long_headline_is_kept(self):
        self.assertEqual(check({"v": 1, "headline": "  Plan holds  "}), {"v": 1, "headline": "Plan holds"})
        long = "x" * 5000
        self.assertEqual(check({"v": 1, "headline": long})["headline"], long)

    def test_bad_values_are_refused_in_plain_words_that_never_quote_them(self):
        for bad in (None, [], "text", {}, {"v": 2}, {"v": "1"}, {"v": 1, "health": "green"}, {"v": 1, "health": 3}, {"v": 1, "health": ["on_track"]},
                    {"v": 1, "headline": 5}, {"v": 1, "sentence": ["a"]}, {"v": 1, "extra": "secret-word"}, {"v": 1, "headline": "x" * rh.LIMIT}):
            with self.subTest(bad=bad), self.assertRaises(base.Bad) as got:
                check(bad)
            self.assertNotIn("secret-word", str(got.exception))
            self.assertNotIn("green", str(got.exception))

    def test_published_carries_every_field_and_leaves_an_empty_one_out(self):
        self.assertEqual(rh.published({"v": 1, "health": "on_track", "headline": "H"}, None),
                         {"content": {"health": "on_track", "headline": "H", "sentence": "", "pill": True}})
        self.assertEqual(rh.published({"v": 1, "sentence": "S"}, None), {"content": {"health": "", "headline": "", "sentence": "S", "pill": True}})
        self.assertIsNone(rh.published({"v": 1}, None))
        self.assertIsNone(rh.published("", None))


class Registered(unittest.TestCase):
    def test_it_is_in_the_registry_and_the_store(self):
        self.assertIs(section_kinds.REGISTRY["reportheadline"], rh)
        self.assertIn("reportheadline", store_module.SECTION_TYPES)
        self.assertIs(section_bodies.CHECKERS["reportheadline"], rh.check)
        self.assertEqual(section_bodies.EMPTY["reportheadline"], "")

    def test_step_27_lets_an_older_file_keep_the_type_and_a_second_run_changes_nothing(self):
        con = sqlite3.connect(":memory:")
        con.execute(store_module.REPORT_SECTIONS_WITH_GANTT_TABLE.replace("CREATE TABLE IF NOT EXISTS report_sections (", "CREATE TABLE report_sections (", 1)
                    .replace("  project TEXT NOT NULL REFERENCES projects(code) ON DELETE CASCADE,", "  project TEXT NOT NULL,"))
        con.execute("INSERT INTO report_sections VALUES ('ABC','s1','callout','T','b',0,0,1)")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("INSERT INTO report_sections VALUES ('ABC','s2','reportheadline','T','',0,0,2)")
        store_module.migrate_report_headline_section_type(con)
        con.execute("INSERT INTO report_sections VALUES ('ABC','s2','reportheadline','T','',0,0,2)")
        self.assertEqual([r[0] for r in con.execute("SELECT id FROM report_sections ORDER BY sort_order")], ["s1", "s2"])
        store_module.migrate_report_headline_section_type(con)
        self.assertEqual(con.execute("SELECT count(*) FROM report_sections").fetchone()[0], 2)


ICONS = {"on_track": ("On track", "g", "check-circle"), "at_risk": ("At risk", "a", "triangle"),
         "off_track": ("Off track", "r", "cross-circle"), "": ("Not set", "n", "ring")}


class Page(PageBase):
    """Slice 2: the pill carries an icon and its word in every state, and the title and meta line sit above it (View, light and dark,
    1400 and 900 px). Fictional data only."""
    def make(self, body, client=None, week="2026-11-06"):
        with self.store.step("dashboard", USER) as st:
            ref = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional headline", "sort_order": 999})
            st.update("projects", "ABC", {"client_name": client, "week_ending": week})
        status, got = self.real_change({"project": "ABC", "kind": KIND, "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
        assert status == 200, got
        return ref

    def look(self, ref, width, theme):
        with chrome() as cdp:
            p = self.visit(cdp)
            cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
            p.js(f"document.documentElement.dataset.theme = {json.dumps(theme)}")
            sec = f"document.querySelector('[data-id={json.dumps(ref)}]')"
            p.until(f"!!{sec}", "the section")
            return p.js(f"""(function(){{ var s = {sec}, pill = s.querySelector('.tpl-rh-pill'), svg = pill && pill.querySelector('svg');
              var cs = pill && getComputedStyle(pill), r = svg && svg.getBoundingClientRect();
              return {{pill: pill && pill.textContent.trim(), icon: svg && svg.getAttribute('data-hl'), hidden: svg && svg.getAttribute('aria-hidden'),
                       size: r && [Math.round(r.width), Math.round(r.height)], color: cs && cs.color, bg: cs && cs.backgroundColor,
                       title: (s.querySelector('.tpl-rh-title') || {{}}).textContent, meta: (s.querySelector('.tpl-rh-meta') || {{}}).textContent,
                       overflow: document.documentElement.scrollWidth > window.innerWidth}}; }})()""")

    def test_the_pill_has_an_icon_and_its_word_in_every_state_in_both_looks_and_widths(self):
        for health, (word, tone, icon) in ICONS.items():
            ref = self.make({"v": 1, "health": health, "headline": "Fictional headline words"} if health else {"v": 1, "headline": "Fictional headline words"})
            for width in (1400, 900):
                for theme in ("light", "dark"):
                    with self.subTest(health=health or "unset", width=width, theme=theme):
                        got = self.look(ref, width, theme)
                        self.assertEqual(got["pill"], word)
                        self.assertEqual(got["icon"], icon)
                        self.assertEqual(got["hidden"], "true")
                        self.assertTrue(got["size"][0] > 0 and got["size"][1] > 0, got["size"])
                        self.assertNotEqual(got["color"], got["bg"])
                        self.assertFalse(got["overflow"], "no sideways scroll")

    def test_the_title_and_meta_line_name_the_project_the_client_and_the_week(self):
        ref = self.make({"v": 1, "health": "on_track", "headline": "H"}, client="Sample Client")
        got = self.look(ref, 1400, "light")
        self.assertEqual(got["title"], "Weekly report")
        self.assertEqual(got["meta"], "Example Programme for Sample Client \u00b7 Week ending 06-11-2026")

    def test_without_a_client_the_meta_line_has_no_for(self):
        for client in (None, "   "):
            ref = self.make({"v": 1, "health": "on_track", "headline": "H"}, client=client)
            with self.subTest(client=client):
                self.assertEqual(self.look(ref, 900, "dark")["meta"], "Example Programme \u00b7 Week ending 06-11-2026")


HINT = "Write the headline the report opens with. Until then this section stays out of the published page."
HEAD_PH = "Headline: say where the project stands (no length limit)"
SENT_PH = "Why the project has this health (a line or two)"


class EditInThePage(Base):
    """Row 1261 slice 2: the Edit part in a real browser (1400 and 900, light and dark). Fictional data only."""

    def setUp(self):
        super().setUp()
        with self.store.step("dashboard", USER) as st:
            self.full = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional headline", "sort_order": 998,
                                                       "body": json.dumps({"v": 1, "health": "at_risk", "headline": "Fictional plan holds", "sentence": "Fictional reason."})})
            self.empty = st.create("report_sections", {"project": "ABC", "type": "reportheadline", "title": "Fictional empty headline", "sort_order": 999})

    def page(self, cdp):
        p = self.visit(cdp)
        cdp.call("Emulation.setFocusEmulationEnabled", {"enabled": True}, p.sid)
        p.edit()
        return p

    def sel(self, ref, rest=""):
        return f'[data-id="{ref}"] {rest}'.strip()

    def stored(self, ref=None):
        return json.loads(self.store.read("report_sections", ref=ref or self.full)["body"])

    def fill(self, p, selector, text):
        p.js(f"(function(){{var e=document.querySelector({json.dumps(selector)}); e.focus(); e.value={json.dumps(text)}; e.dispatchEvent(new Event('input', {{bubbles: true}}));}})()")

    def test_the_stub_line_is_gone_and_the_fields_have_their_labels_and_placeholders(self):
        with chrome() as cdp:
            p = self.page(cdp)
            p.until(f"!!document.querySelector('{self.sel(self.empty, 'textarea')}')", "the empty section's fields")
            text = p.js(f"document.querySelector('{self.sel(self.empty)}').textContent")
            self.assertNotIn("comes in the next step", text)
            self.assertIn(HINT, text)
            self.assertEqual(p.js(f"document.querySelector('{self.sel(self.empty, 'textarea[aria-label=Headline]')}').placeholder"), HEAD_PH)
            sentence = self.sel(self.empty, 'textarea[aria-label="Supporting sentence"]')      # outside the f-string: Python 3.9 refuses a backslash inside {}
            self.assertEqual(p.js(f"document.querySelector('{sentence}').placeholder"), SENT_PH)
            self.assertEqual(p.js(f"document.querySelector('{self.sel(self.empty, '.pillbtn')}').getAttribute('aria-label')"), "Project health: not set. Change it")
            self.assertNotIn(HINT, p.js(f"document.querySelector('{self.sel(self.full)}').textContent"), "the hint is for an empty section only")

    def test_leaving_the_headline_saves_it_in_one_step_and_undo_takes_it_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            box = self.sel(self.full, "textarea[aria-label=Headline]")
            p.until(f"!!document.querySelector('{box}')", "the headline field")
            self.assertEqual(p.js(f"document.querySelector('{box}').value"), "Fictional plan holds")
            self.fill(p, box, "Fictional line one\nFictional line two")
            p.js(f"document.querySelector('{box}').blur()")
            self.assertTrue(wait(lambda: self.stored().get("headline") == "Fictional line one Fictional line two", 10), f"saved, a pasted line break read as a space: {self.stored()}")
            self.assertEqual(self.stored()["sentence"], "Fictional reason.")
            applies = self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]
            import time
            time.sleep(0.7)
            self.assertFalse(p.js("!!document.querySelector('.toast, .toast-text, [data-undo]')"), "no toast element, no invented words, after the save")
            p.key("z", modifiers=2, code="KeyZ", vk=90)        # one Undo step, the Cmd/Ctrl+Z the other inline edits have
            self.assertTrue(wait(lambda: self.stored().get("headline") == "Fictional plan holds", 10), "Undo took it back")
            self.assertEqual(self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0], applies + 1, "an Undo is one step")

    def test_enter_leaves_the_headline_and_saves_it_and_escape_puts_the_old_words_back(self):
        with chrome() as cdp:
            p = self.page(cdp)
            box = self.sel(self.full, "textarea[aria-label=Headline]")
            p.until(f"!!document.querySelector('{box}')", "the headline field")
            before = self.stored()
            self.fill(p, box, "Fictional saved by Enter")
            p.key("Enter", code="Enter", vk=13)
            self.assertTrue(wait(lambda: self.stored().get("headline") == "Fictional saved by Enter", 10), "Enter leaves the box and saves")
            before = self.stored()
            self.fill(p, box, "Typed then cancelled")
            p.key("Escape", code="Escape", vk=27)
            p.until(f"document.querySelector('{box}').value === 'Fictional saved by Enter'", "the saved words are back")
            import time
            time.sleep(0.5)
            self.assertEqual(self.stored(), before)

    def test_the_sentence_saves_and_an_empty_field_is_taken_out(self):
        with chrome() as cdp:
            p = self.page(cdp)
            box = self.sel(self.full, 'textarea[aria-label="Supporting sentence"]')
            p.until(f"!!document.querySelector({json.dumps(box)})", "the sentence field")
            self.fill(p, box, "")
            p.js(f"document.querySelector({json.dumps(box)}).blur()")
            self.assertTrue(wait(lambda: "sentence" not in self.stored(), 10), "an empty sentence is not stored")
            self.assertEqual(self.stored()["headline"], "Fictional plan holds")

    def test_the_health_menu_offers_the_three_words_ticks_the_saved_one_and_a_pick_saves_it(self):
        with chrome() as cdp:
            p = self.page(cdp)
            pill = self.sel(self.full, ".pillbtn")
            p.until(f"!!document.querySelector('{pill}')", "the pill")
            self.assertEqual(p.js(f"document.querySelector('{pill}').getAttribute('aria-label')"), "Project health: at risk. Change it")
            p.js(f"document.querySelector('{pill}').click()")
            p.until("document.querySelectorAll('[role=menuitem], [role=menuitemradio]').length === 3", "the menu")
            self.assertEqual(p.js("[...document.querySelectorAll('[role=menuitem], [role=menuitemradio]')].map(e => e.textContent.replace(/\\s+/g, ' ').trim())"),
                             ["On track", "At risk", "Off track"])
            p.js("[...document.querySelectorAll('[role=menuitem], [role=menuitemradio]')].find(e => /Off track/.test(e.textContent)).click()")
            self.assertTrue(wait(lambda: self.stored().get("health") == "off_track", 10), "the pick was saved")
            self.assertEqual(self.stored()["headline"], "Fictional plan holds")

    def test_both_sections_fit_at_1400_and_900_in_light_and_dark_with_no_sideways_scroll(self):
        for width, dark in ((1400, False), (1400, True), (900, False), (900, True)):
            with self.subTest(width=width, dark=dark), chrome() as cdp:
                p = self.page(cdp)
                cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 1100, "deviceScaleFactor": 1, "mobile": False}, p.sid)
                if dark:
                    p.js("document.documentElement.dataset.theme = 'dark'")
                self.fill(p, self.sel(self.full, "textarea[aria-label=Headline]"), "Fictional long headline " * 40)
                p.until(f"!!document.querySelector('{self.sel(self.empty, 'textarea')}')", "the fields drew")
                self.assertTrue(p.js("document.documentElement.scrollWidth <= window.innerWidth"), "no sideways scroll")
                for ref in (self.full, self.empty):
                    self.assertTrue(p.js(f"[...document.querySelectorAll('{self.sel(ref, 'textarea')}')].every(t => t.getBoundingClientRect().right <= document.querySelector('{self.sel(ref)}').getBoundingClientRect().right + 1)"), "fields inside the section")


if __name__ == "__main__":
    unittest.main()
