"""#189 piece 4, the progress tracker on the page: Edit in place for the Full and Half styles, View, the plain words of a refusal, and
that a published file carries none of Edit. Fictional data. The checker is tested in test_tracker_content.py and the totals in
test_tracker_logic.py.

Run: python3 dev/run_tests.py test_tracker_page
Needs Chrome (the harness in tests/test_server.py): these tests fail, never skip, without it. Everything runs in the real page against
the real change and undo routes over a real store.
"""
import json
import re
import unittest

from _editor_checks import edit_elements
from _paths import SRC
from clark import section_bodies as sb
from test_report_editor import Base, IDS
from test_server import chrome

PAGE = SRC / "clark" / "page"
OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: %s, opener: document.activeElement}, cancelable: true, bubbles: true}))"


def line(text, weight=0, planned=0, achieved=0, **more):
    return {"no": "", "text": text, "start": "2026-01-05", "end": "2026-03-27", "status": "inprogress", "weight": weight, "planned": planned,
            "achieved": achieved, "tasks": None, "agents": None, "workflows": None, **more}


# Fictional. Group one is 5 points behind plan; the weights add up to 94%.
BODY = {"v": 1, "overall": {"actual": None, "planned": None, "health": "atrisk", "note": "Supplier slipped a week"},
        "columns": {"tasks": False, "agents": False, "workflows": False},
        "groups": [{"name": "Foundations", "lines": [line("Agree the plan", 200, 200, 200), line("Set up the site", 300, 100, 50)]},
                   {"name": "Build", "lines": [line("Build the first release", 440, 200, 200)]},
                   {"name": "Hand over", "lines": []}]}


class Page(Base):
    def make(self, body=None, after=None, beside=None):
        req = {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "tracker", "title": "Progress tracker"}}
        if after:
            req["after"] = after
        if beside is not None:
            req["beside"] = beside
        status, got = self.real_change(req)
        self.assertEqual(status, 200, got)
        ref = got["ref"]
        if body is not None:
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"body": json.dumps(body)}})
            self.assertEqual(status, 200, got)
        return ref

    def steps(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def stored(self, ref):
        text = self.store.read("report_sections", ref=ref)["body"]
        return json.loads(text) if text else {}

    @staticmethod
    def scoped(ref, rest):
        head = ".secs > .sec[data-id=" + json.dumps(ref) + "]"
        return ", ".join((head + " " + part.strip()).strip() for part in rest.split(",")) if rest else head

    def one(self, ref, rest=""):
        return "document.querySelector(" + json.dumps(self.scoped(ref, rest)) + ")"

    def many(self, ref, rest=""):
        return "document.querySelectorAll(" + json.dumps(self.scoped(ref, rest)) + ")"

    def text_of(self, ref, rest):
        return self.one(ref, rest) + ".textContent.replace(/\\s+/g, ' ').trim()"

    def present(self, ref, rest):
        return "!!" + self.one(ref, rest)

    def count(self, ref, rest):
        return self.many(ref, rest) + ".length"

    def click(self, p, ref, selector):
        p.js(self.one(ref, selector) + ".click()")

    def set(self, p, ref, selector, value, event="input"):
        p.js("(function(){var el=" + self.one(ref, selector) + "; el.value=" + json.dumps(value) + "; el.dispatchEvent(new Event(" + json.dumps(event) + ", {bubbles: true}));})()")

    def fill(self, p, ref, **fields):
        for key, value in fields.items():
            self.set(p, ref, "[data-line-form] [data-f=" + key + "]", value, "change" if key == "status" else "input")

    def resize(self, cdp, p, width, scheme):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.until("window.innerWidth === " + str(width), "resized")

    def fits(self, p, ref):
        return not self.overflow(p, ref)

    def overflow(self, p, ref):
        return p.js("(function(){var s=" + self.one(ref) + ".getBoundingClientRect();var out=[];" + self.many(ref, ".sec-tracker, .sec-tracker *") +
                    ".forEach(function(e){var r=e.getBoundingClientRect();if(r.width&&(r.left<s.left-1||r.right>s.right+1))out.push(e.tagName+'.'+e.className+' '+Math.round(r.left)+'-'+Math.round(r.right)+' in '+Math.round(s.left)+'-'+Math.round(s.right));});"
                    "if(document.documentElement.scrollWidth>innerWidth)out.push('page scrolls sideways');return out.slice(0,5);})()")

    # ── View ─────────────────────────────────────────────────────────────────

    def test_view_full_has_the_bar_the_table_the_totals_and_nothing_to_change(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-actual]")), "45%")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-planned]")), "50%")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-health]")), "At risk")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-behind]")), "5 points behind plan")
            self.assertEqual(p.js(self.count(ref, "[data-tr-weights]")), 0, "the weights note is for the author: View never shows it")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-group] caption")), "Foundations")
            self.assertEqual(p.js("[..." + self.many(ref, "th.t-what, thead th") + "].slice(0, 8).map(e => e.textContent)"),
                             ["No.", "Description", "Start", "End", "Status", "Weight", "Planned", "Achieved"])
            row = p.js("[..." + self.one(ref, "[data-tr-line='1']") + ".cells].map(td => td.textContent.replace(/\\s+/g, ' ').trim())")
            self.assertEqual((row[1], row[2], row[3], row[4], row[5], row[6]), ("Set up the site", "05-01-2026", "27-03-2026", "In progress", "30%", "10%"))
            self.assertIn("▼ 5", row[7])
            self.assertIn("5 points behind plan", row[7])
            self.assertEqual(p.js(self.count(ref, "[data-tr-line] .tr-behind")), 1, "only the line behind plan is flagged")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-nolines]")), "No lines yet")
            total = p.js("[..." + self.many(ref, "[data-tr-total]") + "].map(tr => [...tr.cells].map(c => c.textContent.replace(/\\s+/g, ' ').trim()).filter(Boolean))")
            self.assertEqual(total[0][:4], ["Total", "50%", "30%", "25%▼ 55 points behind plan"], total)
            self.assertEqual(total[1][:4], ["Total", "44%", "20%", "20%"])
            self.assertEqual(edit_elements(cdp, p.sid), [], "View has no field, button or edit part")
            self.assertEqual(p.js(self.count(ref, "button, input, select, textarea, a")), 0)

    def test_view_overall_is_three_tiles_a_labelled_bar_and_a_scale(self):
        """#451 rows 49 and 50, as the approved weekly-snapshot design draws them."""
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            tiles = p.js("[..." + self.many(ref, "[data-tr-tile]") + "].map(t => t.textContent.replace(/\\s+/g, ' ').trim())")
            self.assertEqual(len(tiles), 3)
            self.assertEqual(tiles[0], "Project health At risk 5 points behind plan Supplier slipped a week")
            self.assertEqual(tiles[1], "Actual 45% of the whole project")
            self.assertRegex(tiles[2], r"^Planned 50% by \d{2}-\d{2}-\d{4}$")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-mark-label]")), "Planned 50%")
            self.assertEqual(p.js("[..." + self.many(ref, "[data-tr-scale] span") + "].map(e => e.textContent)"), ["0%", "100%"])
            self.assertEqual(p.js(self.one(ref, "[data-tr-scale]") + ".getAttribute('aria-hidden')"), "true")
            self.assertEqual(p.js(self.one(ref, ".tr-mark") + ".style.left"), "50%")
            self.assertEqual(p.js(self.one(ref, ".tr-fill") + ".style.width"), "45%")

    def test_view_achieved_column_has_a_bar_the_figure_and_the_red_chip(self):
        """#451 row 51: a bar in each line's Achieved cell; the red chip only on the line behind plan; the total row has no bar."""
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.count(ref, "[data-tr-line] .tr-pbar")), 3)
            self.assertEqual(p.js(self.count(ref, "[data-tr-total] .tr-pbar")), 0)
            self.assertEqual(p.js(self.one(ref, "[data-tr-line='1'] .tr-pbar i") + ".style.width"), "17%", "50 of a 300 weight")
            self.assertEqual(p.js(self.one(ref, "[data-tr-line='0'] .tr-pbar i") + ".style.width"), "100%")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-line='1'] .t-ach b")), "5%")
            self.assertEqual(p.js(self.count(ref, "[data-tr-line] .tr-behind")), 1)
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-line='1'] .tr-behind [aria-hidden]")), "\u25bc 5")
            self.assertEqual(p.js(self.one(ref, "[data-tr-line='1'] .tr-pbar") + ".getAttribute('aria-hidden')"), "true", "the figure says it; the bar is a picture")
            self.assertNotEqual(p.js("getComputedStyle(" + self.one(ref, "[data-tr-line='1'] .tr-behind") + ").backgroundColor"), "rgba(0, 0, 0, 0)", "the chip is filled")

    def test_the_weights_note_is_in_edit_for_the_author_and_not_in_view(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.count(ref, "[data-tr-weights]")), 0)
            p.edit()
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-weights]")), "Weights add up to 94%")

    def test_the_new_overall_parts_fit_at_1400_and_900_in_light_and_dark(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            for scheme in ("light", "dark"):
                for width in (1400, 900):
                    self.resize(cdp, p, width, scheme)
                    where = " at " + str(width) + " in " + scheme
                    self.assertEqual(self.overflow(p, ref), [], "nothing leaves the section" + where)
                    self.assertTrue(p.js("[..." + self.many(ref, "[data-tr-tile]") + "].every(t => t.getBoundingClientRect().width > 80)"), "tiles have room" + where)
                    self.assertTrue(p.js(self.one(ref, "[data-tr-mark-label]") + ".getBoundingClientRect().left >= " + self.one(ref, "[data-tr-bar]") + ".getBoundingClientRect().left - 1"), "the label stays over the bar" + where)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, p.sid)

    def test_view_half_is_the_bar_and_a_short_list_with_no_dates(self):
        ref = self.make(BODY, after="ABC-S-005", beside=1)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.one(ref, "[data-tracker]") + ".dataset.fit"), "half")
            self.assertEqual(p.js(self.count(ref, "table")), 0)
            first = p.js(self.text_of(ref, "[data-tr-line='1']"))
            self.assertIn("Set up the site", first)
            self.assertIn("In progress", first)
            self.assertNotIn("2026", first, "no dates in Half")
            self.assertIn("5 points behind plan", first)
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-actual]")), "45%")

    def test_a_group_with_no_lines_and_an_empty_tracker(self):
        ref = self.make({"groups": [{"name": "Only", "lines": []}]})
        empty = self.make(None)
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-nolines]")), "No lines yet")
            self.assertEqual(p.js(self.text_of(ref, "[data-tr-total]")), "Total0%0%0%")
            self.assertFalse(p.js(self.present(empty, "[data-tracker]")), "an empty tracker draws nothing in View")

    def test_the_markup_in_every_text_is_only_text(self):
        evil = "<img src=x onerror=window.pwned=1>"
        ref = self.make({"overall": {"note": evil}, "groups": [{"name": evil, "lines": [line(evil, no=evil[:10])]}]})
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.count(ref, "img")), 0)
            self.assertIn(evil, p.js(self.text_of(ref, "")))
            self.assertIsNone(p.js("window.pwned"))

    # ── Edit ─────────────────────────────────────────────────────────────────

    def test_add_a_group_then_a_line_each_one_request_one_step_and_one_undo(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            before, sent = self.steps(), len(self.sent)
            self.click(p, ref, "[data-add-group]")
            p.until(self.present(ref, "[data-f=group]"), "the name field")
            self.set(p, ref, "[data-f=group]", "Roll out")
            self.click(p, ref, "[data-save-name]")
            p.until(self.count(ref, "[data-group]") + " === 4", "the group is drawn")
            self.assertEqual((self.steps(), len(self.sent)), (before + 1, sent + 1))
            req = self.sent[-1][1]
            self.assertEqual((req["op"], req["id"], list(req["changes"])), ("update", ref, ["body"]))
            self.assertEqual([g["name"] for g in self.stored(ref)["groups"]], ["Foundations", "Build", "Hand over", "Roll out"])
            self.click(p, ref, "[data-group='3'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the line form")
            self.fill(p, ref, text="Train the team", no="4.1", start="05-01-2026", end="27-03-2026", weight="5", planned="7.5", achieved="2", status="late")
            self.click(p, ref, "[data-save]")
            p.until(self.count(ref, "[data-group='3'] [data-tr-line]") + " === 1", "the line is drawn")
            self.assertEqual(self.steps(), before + 2)
            saved = self.stored(ref)["groups"][3]["lines"][0]
            self.assertEqual((saved["text"], saved["no"], saved["weight"], saved["planned"], saved["achieved"], saved["status"], saved["start"]),
                             ("Train the team", "4.1", 50, 75, 20, "late", "2026-01-05"))
            self.assertEqual(p.toast(), "Line added.")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(self.count(ref, "[data-group='3'] [data-tr-line]") + " === 0", "Undo took the line away")
            self.assertEqual(self.stored(ref)["groups"][3]["lines"], [])

    def test_edit_move_and_remove_a_line_and_a_group_are_each_one_step(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            order = lambda: [g["lines"][0]["text"] if g["lines"] else g["name"] for g in self.stored(ref)["groups"]]   # noqa: E731
            texts = lambda: [x["text"] for x in self.stored(ref)["groups"][0]["lines"]]   # noqa: E731
            steps = self.steps()
            self.click(p, ref, "[data-group='0'] [data-line='0'] [data-down]")
            self.assertTrue(self.wait_until(lambda: texts() == ["Set up the site", "Agree the plan"]))
            self.click(p, ref, "[data-group='0'] [data-line='1'] [data-edit]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            self.fill(p, ref, status="completed", achieved="20")
            self.click(p, ref, "[data-save]")
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["groups"][0]["lines"][1]["status"] == "completed"))
            self.assertEqual(self.stored(ref)["groups"][0]["lines"][1]["achieved"], 200)
            self.click(p, ref, "[data-group='0'] [data-line='0'] [data-remove]")
            self.assertTrue(self.wait_until(lambda: texts() == ["Agree the plan"]))
            self.click(p, ref, "[data-group='1'] [data-gup]")
            self.assertTrue(self.wait_until(lambda: [g["name"] for g in self.stored(ref)["groups"]][:2] == ["Build", "Foundations"]))
            self.click(p, ref, "[data-group='2'] [data-remove-group]")
            self.assertTrue(self.wait_until(lambda: [g["name"] for g in self.stored(ref)["groups"]] == ["Build", "Foundations"]))
            self.assertEqual(self.steps(), steps + 5, "one step each")
            self.assertEqual(order(), ["Build the first release", "Agree the plan"])

    def wait_until(self, test, seconds=10):
        import time
        end = time.time() + seconds
        while time.time() < end:
            if test():
                return True
            time.sleep(0.05)
        return False

    def test_the_overall_health_note_and_columns_are_each_one_change(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.set(p, ref, "[data-overall-edit] [data-f=health]", "ontrack", "change")
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["overall"]["health"] == "ontrack"))
            p.until("!" + self.one(ref, "[data-overall-edit] [data-f=note]") + ".disabled", "the note field is free again")
            p.js("(function(){var el=" + self.one(ref, "[data-overall-edit] [data-f=note]") + "; el.focus(); el.select();})()")
            p.type("All good")
            p.key("Enter", code="Enter", vk=13)
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["overall"]["note"] == "All good"))
            p.js(self.one(ref, "[data-col=tasks]") + ".click()")
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["columns"]["tasks"] is True))
            p.until(self.present(ref, "th.t-count"), "the Tasks column is drawn")

    def test_a_line_that_cannot_be_saved_says_why_in_plain_words_and_sends_nothing(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-group='0'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            sent = len(self.sent)
            cases = (({"text": ""}, sb.TRACKER_TEXT_MISSING), ({"text": "x" * 101}, "A line description can be 100 characters at most."),
                     ({"text": "Fine", "planned": "101"}, sb.TRACKER_PERCENT), ({"text": "Fine", "planned": "50", "achieved": "-1"}, sb.TRACKER_PERCENT),
                     ({"text": "Fine", "achieved": "", "weight": "abc"}, sb.TRACKER_PERCENT),
                     ({"text": "Fine", "weight": "", "start": "31-02-2026"}, "A date must be a real day written DD-MM-YYYY, between 2000 and 2100, or empty."),
                     ({"text": "Fine", "start": "27-03-2026", "end": "05-01-2026"}, sb.TRACKER_DATE_ORDER))
            for fields, words in cases:
                self.fill(p, ref, **{"text": "Fine", "planned": "", "achieved": "", "weight": "", "start": "", "end": "", **fields})
                self.click(p, ref, "[data-save]")
                p.until(self.present(ref, "[data-line-error]"), "a sentence appears")
                self.assertEqual(p.js(self.text_of(ref, "[data-line-error]")), words)
                self.assertEqual(p.js(self.one(ref, "[data-line-error]") + ".getAttribute('role')"), "alert")
                self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertEqual(len(self.stored(ref)["groups"][0]["lines"]), 2)

    def test_a_refusal_from_the_store_is_said_in_words_and_the_form_stays_open(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.failure = lambda req: (400, {"message": sb.TRACKER_TEXT_MISSING})
            self.click(p, ref, "[data-group='0'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            self.fill(p, ref, text="Fine")
            self.click(p, ref, "[data-save]")
            p.until("!!document.querySelector('.toast-text') && /nothing was changed/i.test(document.querySelector('.toast-text').textContent)", "a plain toast")
            self.assertEqual(p.toast(), "Describe each line. Nothing was changed.")
            self.assertTrue(p.js(self.present(ref, "[data-line-form]")), "the form stays open")

    def test_a_too_big_refusal_from_the_change_route_reaches_the_person_in_plain_words(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.failure = lambda req: (400, {"ok": False, "code": "too_large", "message": "That is too big to save. Shorten a line or remove some lines, then try again."})
            self.click(p, ref, "[data-group='0'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            self.fill(p, ref, text="Fine")
            self.click(p, ref, "[data-save]")
            p.until("!!document.querySelector('.toast-text') && /too big to save/i.test(document.querySelector('.toast-text').textContent)", "the plain sentence")
            self.assertEqual(p.toast(), "That is too big to save, and nothing was changed. Shorten a line or remove some lines, then try again.")
            self.assertTrue(p.js(self.present(ref, "[data-line-form]")), "the form stays open")

    def test_the_totals_sit_under_their_headings_at_1400_and_900(self):
        """At 900 px the date columns collapse; the total row, the no-lines row and a line form must still line up with the columns that remain."""
        ref = self.make({**BODY, "columns": {"tasks": True, "agents": False, "workflows": False}})
        with chrome() as cdp:
            p = self.visit(cdp)
            for width in (1400, 900):
                self.resize(cdp, p, width, "light")
                p.until(self.one(ref, "thead tr") + ".cells.length === " + ("9" if width == 1400 else "6"), "the table has the columns of this width")
                for name, index in (("Weight", 5 if width == 1400 else 3), ("Planned", 6 if width == 1400 else 4), ("Achieved", 7 if width == 1400 else 5)):
                    head = p.js("(function(){var r=" + self.one(ref, "[data-tr-group] thead tr") + ".cells[" + str(index) + "].getBoundingClientRect();return [r.left, r.right, r.width];})()")
                    cell = p.js("(function(){var r=" + self.one(ref, "[data-tr-total]") + ".cells[" + str(index - (4 if width == 1400 else 2)) + "].getBoundingClientRect();return [r.left, r.right, r.width];})()")
                    self.assertGreater(cell[2], 0, name)
                    self.assertAlmostEqual(head[0], cell[0], delta=1.5, msg="the total is under " + name + " at " + str(width))
                    self.assertAlmostEqual(head[1], cell[1], delta=1.5, msg=name + " " + str(width))
                row = p.js(self.one(ref, "[data-tr-total]") + ".cells[0].textContent")
                self.assertEqual(row, "Total")
                if width == 900:
                    self.assertEqual(p.js("[..." + self.one(ref, "thead tr") + ".cells].map(c => c.textContent)"), ["No.", "Description", "Status", "Weight", "Planned", "Achieved"], "no dates or counts at 900")
                    self.assertEqual(p.js(self.one(ref, "[data-tr-total]") + ".cells[0].colSpan"), 3, "the label spans the three columns before the figures")
                    self.assertGreater(p.js(self.one(ref, "thead tr") + ".cells[5].getBoundingClientRect().width"), 40, "Achieved stays in view")

    def test_the_no_lines_row_and_the_form_row_fit_the_table_at_900(self):
        ref = self.make({"groups": [{"name": "Only", "lines": []}]})
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.resize(cdp, p, 900, "light")
            p.until(self.one(ref, "thead tr") + ".cells.length === 7", "the table is drawn for 900 px")
            self.click(p, ref, "[data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            self.assertEqual(self.overflow(p, ref), [])
            row = p.js("(function(){var t=" + self.one(ref, "table.tracker") + ".getBoundingClientRect(),r=" + self.one(ref, ".t-form-row td") + ".getBoundingClientRect();return [Math.round(t.left),Math.round(t.right),Math.round(r.left),Math.round(r.right)];})()")
            self.assertAlmostEqual(row[0], row[2], delta=2)
            self.assertAlmostEqual(row[1], row[3], delta=2)

    def test_a_half_typed_line_survives_another_save_and_only_its_own_save_closes_it(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-group='0'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            self.fill(p, ref, text="Half typed", planned="12")
            self.set(p, ref, "[data-overall-edit] [data-f=health]", "ontrack", "change")
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["overall"]["health"] == "ontrack"))
            p.until("!" + self.one(ref, "[data-overall-edit] [data-f=health]") + ".disabled", "free again")
            self.assertTrue(p.js(self.present(ref, "[data-line-form]")), "the form is still open")
            self.assertEqual(p.js(self.one(ref, "[data-line-form] [data-f=text]") + ".value"), "Half typed")
            self.assertEqual(p.js(self.one(ref, "[data-line-form] [data-f=planned]") + ".value"), "12")
            p.js(self.one(ref, "[data-col=tasks]") + ".click()")
            self.assertTrue(self.wait_until(lambda: self.stored(ref)["columns"]["tasks"] is True))
            p.until("!" + self.one(ref, "[data-col=tasks]") + ".disabled", "free again")
            self.assertEqual(p.js(self.one(ref, "[data-line-form] [data-f=text]") + ".value"), "Half typed", "still there after a second save")
            self.click(p, ref, "[data-save]")
            p.until("!" + self.one(ref, "[data-line-form]"), "its own save closes it")
            self.assertEqual(self.stored(ref)["groups"][0]["lines"][-1]["text"], "Half typed")

    def test_a_line_that_would_take_a_total_past_100_is_refused_in_words_and_sends_nothing(self):
        ref = self.make(BODY)               # planned adds up to 50% already; weights to 94%
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-group='0'] [data-add-line]")
            p.until(self.present(ref, "[data-line-form]"), "the form")
            sent = len(self.sent)
            self.fill(p, ref, text="Too much", weight="7", planned="51", achieved="0")
            self.click(p, ref, "[data-save]")
            p.until(self.present(ref, "[data-line-error]"), "a sentence")
            self.assertEqual(p.js(self.text_of(ref, "[data-line-error]")), sb.TRACKER_TOTAL)
            self.assertEqual(len(self.sent), sent)

    def test_the_stores_total_refusal_has_its_plain_words_on_the_page(self):
        text = (PAGE / "src" / "stores" / "report.js").read_text(encoding="utf-8")
        self.assertIn(json.dumps(sb.TRACKER_TOTAL) + ":", text)

    def test_escape_cancels_with_nothing_sent(self):
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sent = len(self.sent)
            self.click(p, ref, "[data-group='0'] [data-line='0'] [data-edit]")
            p.until("document.activeElement.matches('[data-f=text]')", "the description has focus")
            p.key("Escape", code="Escape", vk=27)
            p.until("!" + self.one(ref, "[data-line-form]"), "the form closed")
            self.assertEqual(len(self.sent), sent)

    def test_edit_draws_the_trackers_own_parts_and_view_does_not(self):
        # Edit adds its own parts; View (the first test) has none.
        ref = self.make(BODY)
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.assertTrue(p.js(self.present(ref, "[data-edit-only]")), "Edit draws the tracker's own parts")
            self.assertEqual(p.js(self.count(ref, "[data-tr-group]")), 3)

    def test_it_fits_at_1400_and_900_in_light_and_dark_in_view_and_in_edit_full_and_half(self):
        full = self.make(BODY)
        half = self.make(BODY, after="ABC-S-005", beside=1)
        with chrome() as cdp:
            p = self.visit(cdp)
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                    self.click(p, full, "[data-group='0'] [data-line='1'] [data-edit]")
                    self.click(p, half, "[data-group='0'] [data-line='1'] [data-edit]")
                    p.until(self.present(half, "[data-line-form]"), "a line open for editing")
                for scheme in ("light", "dark"):
                    for width in (1400, 900):
                        self.resize(cdp, p, width, scheme)
                        where = mode + " at " + str(width) + " in " + scheme
                        for ref in (full, half):
                            self.assertEqual(self.overflow(p, ref), [], "nothing leaves the section or scrolls sideways: " + where)
                            small = p.js("[..." + self.many(ref, "*") + "].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)")
                            self.assertEqual(small, [], "no text under 13 px: " + where)
                        if width == 900:
                            p.until(self.count(full, "th.t-date") + " === 0", "dates drop at 900: " + where)
                            self.assertTrue(p.js(self.one(full, "[data-tr-actual]") + ".getBoundingClientRect().right <= innerWidth"), "the figures stay in view")
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, p.sid)


class Source(unittest.TestCase):
    """What needs no browser."""

    def test_a_published_file_carries_no_edit_code_for_the_tracker(self):
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for marker in ("tracker-edit", "data-line-form", "t-form-row", "data-add-group", "data-remove-group", "OverallNumber"):
            self.assertNotIn(marker, view, marker)
        self.assertIn("data-tr-overall", view, "the reading part is in it")
        served = (PAGE / "page.html").read_text(encoding="utf-8")
        for marker in ("tracker-edit", "data-line-form", "data-add-group"):
            self.assertIn(marker, served, marker)

    def test_a_published_file_has_nothing_internal_in_the_tracker(self):
        """#451 item 6: the weights note and every author instruction stay out of View and the published file."""
        view = (PAGE / "page-view.html").read_text(encoding="utf-8")
        for words in ("Weights add up", "data-tr-weights", "weightsNote", "Nothing was changed"):
            self.assertNotIn(words, view, words)
        text = (PAGE / "src" / "components" / "Tracker.jsx").read_text(encoding="utf-8")
        self.assertNotIn("weightsNote", text, "only Edit may draw the weights note")
        for marker in ("data-tr-tile", "data-tr-mark-label", "data-tr-scale", "tr-pbar", "of the whole project"):
            self.assertIn(marker, view, marker)

    def test_the_page_view_reads_the_publish_date_for_the_planned_tile(self):
        text = (PAGE / "src" / "components" / "Tracker.jsx").read_text(encoding="utf-8")
        self.assertIn("asAt", text)
        self.assertIn("todayIso", text)

    def test_every_word_of_the_stores_tracker_checker_has_its_plain_words_on_the_page(self):
        text = (PAGE / "src" / "stores" / "report.js").read_text(encoding="utf-8")
        known = re.search(r"const CHANGE_KNOWN = \{(.*?)\n\};", text, re.S).group(1)
        said = [getattr(sb, n) for n in dir(sb) if n.startswith("TRACKER_") and isinstance(getattr(sb, n), str)]
        self.assertGreater(len(said), 15)
        for words in said:
            self.assertIn(json.dumps(words, ensure_ascii=False) + ":", known, words)
        for tail in re.findall(r'"[^"]*": ("[^"]*")', known.split("#189")[1]):
            self.assertRegex(tail, r"[Nn]othing was changed|nothing was changed")

    def test_the_change_routes_too_big_sentence_has_its_words_on_the_page(self):
        from clark import server
        text = (PAGE / "src" / "stores" / "report.js").read_text(encoding="utf-8")
        self.assertIn(json.dumps(server.MESSAGES["change_too_large"]) + ":", text)

    def test_the_tracker_has_a_help_entry_in_the_pages_own_words(self):
        help_ = json.loads((PAGE / "src" / "help" / "helpContent.json").read_text(encoding="utf-8"))
        task = next(t for t in help_["howto"]["tasks"] if t["id"] == "show-progress")
        text = " ".join(task["s"])
        for label in ("Add a group", "Add a line", "Status", "Weight", "Planned", "Achieved", "Health", "Rename", "Remove group", "Undo"):
            self.assertIn("**" + label, text, label)
        self.assertFalse(re.match(r"\s*(\*\*)?clark\b", text, re.I))

    def test_the_tracker_styles_use_tokens_only(self):
        for path in (PAGE / "shell.css", PAGE / "src" / "edit" / "edit.css"):
            css = path.read_text(encoding="utf-8")
            block = re.sub(r"/\*.*?\*/", "", css[css.rindex("/*", 0, css.index("Progress tracker")):], flags=re.S)
            self.assertIsNone(re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", block.split("@media print")[0] if path.name == "shell.css" else block), path.name)


if __name__ == "__main__":
    unittest.main()
