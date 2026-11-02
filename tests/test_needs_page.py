"""The 'Needs from you' section on the page (#121): the plain words, the logic, the template, Edit in place, View, the published file and
the layout at 1400 and 900 px in light and dark. Fictional data. The content's own checker is tested in test_needs_content.py.

Run: python3 dev/run_tests.py test_needs_page
Needs Chrome (the harness in tests/test_server.py): these tests fail, never skip, without it. The logic runs on a bare page bundled by
the pinned esbuild; everything else runs in the real page against the real change and undo routes over a real store.
"""
import contextlib
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

import test_placement as tp
from _demo import USER
from _editor_checks import edit_elements
from _paths import ROOT, SRC
from _publish_fixture import spellings
from clark import publish, section_bodies as sb
from clark.store import BODY_RULES
from test_report_editor import Base, EMPTY_BRANDING, IDS
from test_server import chrome, wait
from test_work_items import page_target

PAGE_SRC = SRC / "clark" / "page" / "src"
FIXTURE = ROOT / "tests" / "fixtures" / "needs_demo.js"
MARK = "ZQ-NEEDS-PAGE-MARK"
OPEN = "document.dispatchEvent(new CustomEvent('clark:add-section', {detail: {after: %s, opener: document.activeElement}, cancelable: true, bubbles: true}))"
JARGON = re.compile(r"\b(RAID|JSON|schema|id|IDs?|database|payload|null|token|API|SQL|field|fields|string|array|object|boolean|undefined|NaN|hook|stage|staged|"
                    r"parse|checker|template|templates)\b|\bUI\b")      # the Help words say "template" because the page does, so that one is allowed there
_PAGE = {}


def page_html():
    if "html" not in _PAGE:
        saved = tp.DEMO
        tp.DEMO = FIXTURE
        try:
            tp._PAGE.pop("html", None)
            _PAGE["html"] = tp.test_page_html()
            tp._PAGE.pop("html", None)
        finally:
            tp.DEMO = saved
    return _PAGE["html"]


def lit(x):
    return json.dumps(x)


def row(**more):
    return {"what": "Choose the pilot site", "kind": "decision", "from": "Steering group", "by": "2099-03-04", "hidden": 0, **more}


def body(*rows):
    return json.dumps({"v": 1, "rows": list(rows)})


def ratio(a, b):
    def lum(c):
        c = [x / 255 for x in c]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def strings_of(o):
    if isinstance(o, str):
        yield o
    elif isinstance(o, dict):
        for k, v in o.items():
            if k not in ("id", "g", "go"):
                yield from strings_of(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            yield from strings_of(v)


class Logic(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_server import Running
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=page_html)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        cls.sid = page_target(cls.cdp)

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.N && window.N.needs)", self.sid)), "the test bundle ran")

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def n(self, call):
        return self.val(f"N.needs.{call}")

    # ── the words ────────────────────────────────────────────────────────────

    def test_the_words_the_section_uses_are_the_four_the_item_names(self):
        w = self.n("WORDS")
        self.assertEqual((w["title"], w["what"], w["from"], w["by"]), ("Needs from you", "What is needed", "From", "By"))
        self.assertEqual(self.n("KINDS"), [["decision", "Decision"], ["information", "Information"], ["date", "Date"]])

    def test_every_new_string_is_plain_and_none_starts_with_the_product_name(self):
        """Every word the section shows or says (the page's, the template's, Help's and the store's refusals): no jargon, and no sentence
        that starts with the product name."""
        words = list(self.n("ALL_WORDS()"))
        help_words = []
        template = next(t for t in self.val("N.templates.TEMPLATES") if t["id"] == "needs")
        words += [template["name"], template["title"], template["description"], *template["holds"]]
        help_ = json.loads((PAGE_SRC / "help" / "helpContent.json").read_text(encoding="utf-8"))
        task = next(t for t in help_["howto"]["tasks"] if t["id"] == "ask-for-what-you-need")
        help_words += list(strings_of(task))
        words += help_words
        table = next(b for s in help_["reference"]["sections"] if s["id"] == "section-templates" for b in s["b"] if b[0] == "tbl")
        words += list(strings_of(next(r for r in table[2] if r[0] == "Needs from you")))
        words += [getattr(sb, name) for name in dir(sb) if name.startswith("NEEDS_") and isinstance(getattr(sb, name), str) and name.endswith(("SHAPE", "MANY", "MISSING", "LONG", "KIND", "BAD", "BY", "HIDDEN"))]
        words = [w for w in words if isinstance(w, str) and w.strip()]
        self.assertGreater(len(words), 40, "the check read the strings")
        for word in words:
            plain = re.sub(r"\*\*|\[\[|\]\]|\(#[a-z-]+\)|\(go:[a-z+#-]+\)", "", word)
            self.assertFalse(re.match(r"\s*(\*\*)?clark\b", word, re.I), f"starts with the product name: {word}")
            is_help = word in help_words
            found = JARGON.search(plain)
            if found and is_help and found.group(0) in ("template", "templates"):
                found = None
            self.assertIsNone(found, f"jargon in: {word}")
            self.assertNotRegex(plain, r"\b\w+_\w+\b", f"a code name in: {word}")
            self.assertNotRegex(plain, r"[{}<>]|\\", word)
        for word in self.n("ALL_WORDS()"):
            self.assertNotRegex(word, r"\bclark\b", word)

    def test_every_string_of_the_new_files_is_in_the_checked_list_or_a_code_name(self):
        """A word added to a component later, without going through WORDS, is caught here: the quoted strings in the two components are
        only code names, selectors and the dash."""
        for name in ("components/Needs.jsx", "edit/NeedsEdit.jsx"):
            code = (PAGE_SRC / name).read_text(encoding="utf-8")
            code = re.sub(r"/\*.*?\*/", "", code, flags=re.S)
            code = re.sub(r"(?m)(^|\s)//.*$", r"\1", code)
            for quoted in re.findall(r'"([^"\n]*)"', code):
                if not re.search(r"[A-Za-z]{3,}.* [A-Za-z]{2,}", quoted):
                    continue
                self.assertRegex(quoted, r"^(\.\./|\./|preact|\[data-|\.sec|\[|input|select|n-|sec-|tag |btn |pill |needs|quiet|text|numeric|off|plaintext|\$\{|\S+$)",
                                 f"{name}: a sentence in the code, not in WORDS: {quoted}")

    # ── the rows ─────────────────────────────────────────────────────────────

    def test_the_rows_of_a_stored_body_and_of_a_file(self):
        stored = body(row(what="One"), row(what="Two", by="", hidden=1))
        got = self.n(f"rowsOf({{body: {lit(stored)}}}, false)")
        self.assertEqual([(r["what"], r["by"], r["hidden"]) for r in got], [("One", "2099-03-04", 0), ("Two", "", 1)])
        file = self.n(f"rowsOf({{rows: [{{what: 'One', kind: 'date', from: 'Team', by: '04-03-2099'}}]}}, true)")
        self.assertEqual(file, [{"what": "One", "kind": "date", "from": "Team", "by": "2099-03-04", "hidden": 0}])
        for bad in ("", "not json", "[]", "5", '{"rows": 5}', '{"rows": [null, 5, {"what": 1}, {"what": ""}]}'):
            self.assertEqual(self.n(f"rowsOf({{body: {lit(bad)}}}, false)"), [], bad)
        self.assertEqual(self.n("rowsOf({}, false)"), [])
        self.assertEqual(self.n("rowsOf(null, true)"), [])
        self.assertEqual(self.n("rowsOf({rows: 'x'}, true)"), [])

    def test_shown_rows_leave_out_the_left_out_ones(self):
        rows = [{"what": "A", "hidden": 0}, {"what": "B", "hidden": 1}, {"what": "C", "hidden": 0}]
        self.assertEqual([r["what"] for r in self.n(f"shownRows({lit(rows)})")], ["A", "C"])

    def test_dates_are_read_from_either_form_and_a_day_before_today_is_overdue(self):
        self.assertEqual(self.n("isoOf('04-03-2099')"), "2099-03-04")
        self.assertEqual(self.n("isoOf('2099-03-04')"), "2099-03-04")
        self.assertEqual(self.n("isoOf('')"), "")
        self.assertEqual(self.n("isoOf('  ')"), "")
        for bad in ("2027-02-29", "31-02-2027", "04/03/2027", "soon", "1999-12-31", "2101-01-01", "4-3-2027", "2027-3-4"):
            self.assertIsNone(self.n(f"isoOf({lit(bad)})"), bad)
        past, today, future = (self.n(f"dueOf({{by: {lit(by)}}}, '2030-01-15')") for by in ("2030-01-14", "2030-01-15", "2030-01-16"))
        self.assertEqual((past, today, future), ({"text": "14-01-2030", "overdue": True}, {"text": "15-01-2030", "overdue": False},
                                                  {"text": "16-01-2030", "overdue": False}))
        self.assertEqual(self.n("dueOf({by: ''}, '2030-01-15')"), {"text": "No date", "overdue": False})
        self.assertEqual(self.n("dueOf({by: '2030-01-14'}, '')")["overdue"], False, "no today, nothing is overdue")

    def test_a_row_is_checked_in_the_stores_own_words_before_anything_is_sent(self):
        good = {"what": "Pick a site", "kind": "decision", "from": "", "by": ""}
        self.assertEqual(self.n(f"problem({lit(good)})"), "")
        cases = [({"what": ""}, sb.NEEDS_WHAT_MISSING), ({"what": "   "}, sb.NEEDS_WHAT_MISSING), ({"what": "x" * 301}, sb.NEEDS_WHAT_LONG),
                 ({"kind": "task"}, sb.NEEDS_KIND), ({"from": "x" * 101}, sb.NEEDS_FROM_LONG), ({"by": "2027-02-30"}, None), ({"by": "tomorrow"}, None)]
        for change, words in cases:
            got = self.n(f"problem({lit({**good, **change})})")
            self.assertTrue(got and got.endswith("."), change)
            if words:
                self.assertEqual(got, words, "the page and the store say the same")
        self.assertEqual(self.n(f"problem({lit({**good, 'what': 'x' * 300, 'from': 'y' * 100})})"), "")
        self.assertEqual(self.n(f"problem({lit({**good, 'what': chr(0x1F600) * 300})})"), "", "characters, not bytes")
        self.assertIn("DD-MM-YYYY", self.n(f"problem({lit({**good, 'by': '2027-02-30'})})"))
        self.assertEqual(self.n(f"problem({lit({**good, 'by': '04-03-2099'})})"), "")

    def test_what_the_page_sends_is_what_the_store_keeps(self):
        """The page's rows, made and written (logic/needs.js), pass the store's checker and come back as the same rows."""
        drafts = [{"what": "  Pick a site  ", "kind": "decision", "from": " Steering group ", "by": "04-03-2099"},
                  {"what": "Send the list", "kind": "information", "from": "", "by": ""},
                  {"what": "Confirm", "kind": "date", "from": "Finance", "by": "2099-12-31"}]
        rows = [self.n(f"made({lit(d)}, {1 if i == 2 else 0})") for i, d in enumerate(drafts)]
        text = self.n(f"bodyOf({lit(rows)})")
        kept = json.loads(sb.check("needs", text, BODY_RULES))
        self.assertEqual(kept["rows"], rows)
        self.assertEqual(rows[0], {"what": "Pick a site", "kind": "decision", "from": "Steering group", "by": "2099-03-04", "hidden": 0})
        self.assertEqual(rows[2]["hidden"], 1)

    def test_one_change_to_the_list_each(self):
        rows = [{"what": "A", "kind": "date", "from": "", "by": "", "hidden": 0}, {"what": "B", "kind": "date", "from": "", "by": "", "hidden": 0}]
        new = {"what": "C", "kind": "date", "from": "", "by": "", "hidden": 0}
        self.assertEqual([r["what"] for r in self.n(f"withAdded({lit(rows)}, {lit(new)})")], ["A", "B", "C"])
        self.assertEqual([r["what"] for r in self.n(f"withReplaced({lit(rows)}, 0, {lit(new)})")], ["C", "B"])
        self.assertEqual([r["hidden"] for r in self.n(f"withFlipped({lit(rows)}, 1)")], [0, 1])
        self.assertEqual([r["hidden"] for r in self.n(f"withFlipped({lit([{**rows[0], 'hidden': 1}])}, 0)")], [0])
        self.assertEqual([r["what"] for r in self.n(f"withoutRow({lit(rows)}, 0)")], ["B"])
        for call in ("withReplaced(%s, 2, %s)", "withReplaced(%s, -1, %s)"):
            self.assertIsNone(self.n(call % (lit(rows), lit(new))))
        self.assertIsNone(self.n(f"withFlipped({lit(rows)}, 5)"))
        self.assertIsNone(self.n(f"withoutRow({lit(rows)}, 5)"))
        full = [new] * 100
        self.assertIsNone(self.n(f"withAdded({lit(full)}, {lit(new)})"), "a list of 100 rows is full")
        self.assertEqual(len(self.n(f"withoutRow({lit(full)}, 0)")), 99)

    def test_the_template_is_there_and_the_store_takes_it(self):
        t = next(x for x in self.val("N.templates.TEMPLATES") if x["id"] == "needs")
        self.assertEqual((t["name"], t["type"], t["title"], t["kind"], t["fit"]), ("Needs from you", "needs", "Needs from you", "dates", ["full", "half"]))
        self.assertEqual(self.val("N.templates.available(N.templates.find('needs'))"), True)
        self.assertEqual(self.val("N.templates.ACCEPTS.types")[:2], ["text", "needs"])      # then the section templates (#96)
        plan = self.val("N.templates.plan([{id: 'a', title: 'Summary', beside: 0, hidden: 0}], 'needs', 'a', false)")
        self.assertEqual(plan["requests"], [{"op": "new", "values": {"type": "needs", "title": "Needs from you"}, "after": "a", "place": "report"}])
        side = self.val("N.templates.plan([{id: 'a', title: 'Summary', beside: 0, hidden: 0}], 'needs', 'a', true)")
        self.assertEqual(side["requests"], [{"op": "new", "values": {"type": "needs", "title": "Needs from you"}, "after": "a", "beside": 1, "place": "report"}])


class Page(Base):
    """The real page, the real routes."""

    def make(self, *rows, title="Needs from you", after=None, beside=None, hidden=0):
        req = {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "needs", "title": title}}
        if after:
            req["after"] = after
        if beside is not None:
            req["beside"] = beside
        status, got = self.real_change(req)
        self.assertEqual(status, 200, got)
        ref = got["ref"]
        if rows:
            status, got = self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"body": body(*rows)}})
            self.assertEqual(status, 200, got)
        if hidden:
            self.real_change({"project": "ABC", "kind": "report_sections", "op": "update", "id": ref, "changes": {"hidden": 1}})
        return ref

    def steps(self):
        return self.store.con.execute("SELECT count(*) FROM applies").fetchone()[0]

    def stored_rows(self, ref):
        text = self.store.read("report_sections", ref=ref)["body"]
        return json.loads(text)["rows"] if text else []

    # JavaScript for "the first element" and "every element" inside section `ref`; the selector goes in as one JSON string
    @staticmethod
    def scoped(ref, rest):
        """A selector, or a list of them, each one inside section `ref`."""
        head = ".secs > .sec[data-id=" + json.dumps(ref) + "]"
        return ", ".join((head + " " + part.strip()).strip() for part in (rest or "").split(",")) if rest else head

    def one(self, ref, rest=""):
        return "document.querySelector(" + json.dumps(self.scoped(ref, rest)) + ")"

    def many(self, ref, rest=""):
        return "document.querySelectorAll(" + json.dumps(self.scoped(ref, rest)) + ")"

    def text_of(self, ref, rest):
        return self.one(ref, rest) + ".textContent"

    def present(self, ref, rest):
        return "!!" + self.one(ref, rest)

    def cells(self, ref, rest):
        return "[..." + self.many(ref, rest) + "].map(td => td.textContent.replace(/\\s+/g, ' ').trim())"

    def count(self, ref, rest):
        return self.many(ref, rest) + ".length"

    def resize(self, cdp, p, width, scheme):
        cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, p.sid)
        cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, p.sid)
        p.until("window.innerWidth === " + str(width), "resized")

    def open_box(self, p, after):
        p.js(OPEN % json.dumps(after))
        p.until("!!document.querySelector('[role=dialog]') && document.activeElement.matches('input[type=search]')", "the box opened")

    def fill(self, p, ref, what=None, kind=None, frm=None, by=None):
        if what:
            p.js("(function(){var el=" + self.one(ref, "[data-f=what]") + "; el.focus(); el.select();})()")
            p.type(what)
        for key, value in (("what", what if what == "" else None), ("kind", kind), ("from", frm), ("by", by)):
            if value is None:
                continue
            event = "change" if key == "kind" else "input"
            p.js("(function(){var el=" + self.one(ref, "[data-f=" + key + "]") + "; el.value=" + json.dumps(value) +
                 "; el.dispatchEvent(new Event(" + json.dumps(event) + ", {bubbles: true}));})()")

    def click(self, p, ref, selector):
        p.js(self.one(ref, selector) + ".click()")

    # ── the template, in Edit ────────────────────────────────────────────────

    def test_the_template_is_added_like_the_others_and_one_undo_takes_it_away(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-003")
            p.js("document.querySelector('[data-template=needs] input').click()")
            self.assertEqual(p.js("document.querySelector('.ad-prev h3').textContent"), "Needs from you")
            self.assertFalse(p.js("document.querySelector('button[data-place]').disabled"), "it can be added")
            self.assertIsNone(p.js("document.getElementById('ad-later-prev')"))
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12", "a section was added")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual(self.sent[-1][1], {"project": "ABC", "kind": "report_sections", "op": "new", "values": {"type": "needs", "title": "Needs from you"},
                                                "after": "ABC-S-003", "place": "report"})
            self.assertEqual(self.store.read("report_sections", ref=new)["type"], "needs")
            self.assertEqual(p.toast(), "Needs from you added.")
            p.until(self.present(new, "[data-needs-none]"), "an empty list says so in words")
            self.assertEqual(p.js(self.text_of(new, "[data-needs-none]")), "Nothing needed from you yet.")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("document.querySelectorAll('.sec').length === 11", "Undo took it away")
            self.assertEqual(self.ids_in_store(), IDS)

    def test_a_small_section_beside_the_one_above_is_one_request_and_the_rows_are_right(self):
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.open_box(p, "ABC-S-005")
            p.js("document.querySelector('[data-template=needs] input').click()")
            self.assertFalse(p.js("document.querySelector('input[name=where][value=beside]').disabled"), "it fits half width")
            p.js("document.querySelector('input[name=where][value=beside]').click()")
            p.js("document.querySelector('button[data-place]').click()")
            p.until("document.querySelectorAll('.sec').length === 12 && !!document.querySelector('[data-undo]')", "added beside")
            new = [i for i in p.ids() if i not in IDS][0]
            self.assertEqual([r[0] for r in self.sent], ["change"], "one request")
            self.assertEqual(self.sent[-1][1]["beside"], 1)
            self.assertEqual(self.beside_flags()["ABC-S-005"], 1)
            p.until("document.querySelector('[data-id=ABC-S-005]').classList.contains('slot-left') && "
                    "document.querySelector('[data-id=" + new + "]').classList.contains('slot-right')", "a pair")
            self.resize(cdp, p, 1400, "light")
            self.click(p, new, "[data-add-row]")
            p.until(self.present(new, "[data-f=what]"), "the new row's fields")
            self.fill(p, new, what="A needed thing " * 6, frm="Example client team", by="04-03-2099")
            self.assertTrue(self.fits(p, new), "the form fits inside its half")
            self.click(p, new, "[data-cancel]")
            self.assertTrue(self.fits(p, new))

    def fits(self, p, ref):
        return p.js("(function(){var s=" + self.one(ref) + ".getBoundingClientRect();var out=true;"
                    "" + self.many(ref, "table.needs, table.needs *") + ".forEach(function(e){var r=e.getBoundingClientRect();"
                    "if(r.width&&(r.left<s.left-1||r.right>s.right+1))out=false;});"
                    "var t=" + self.one(ref, "table.needs") + ";return out&&(!t||t.scrollWidth<=t.clientWidth+1)&&document.documentElement.scrollWidth<=innerWidth;})()")

    # ── rows, in Edit ────────────────────────────────────────────────────────

    def test_add_a_row_is_one_request_one_step_and_one_undo(self):
        ref = self.make()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            before = self.steps()
            self.click(p, ref, "[data-add-row]")
            p.until("document.activeElement.matches('[data-f=what]')", "the first field has focus")
            self.fill(p, ref, what="Choose the pilot site", kind="information", frm="Steering group", by="04-03-2099")
            sent = len(self.sent)
            self.click(p, ref, "[data-save]")
            p.until(self.count(ref, "tbody tr[data-row]") + " === 1", "the row is drawn")
            self.assertEqual(self.steps(), before + 1, "one step")
            self.assertEqual(len(self.sent), sent + 1, "one request")
            req = self.sent[-1][1]
            self.assertEqual((req["op"], req["id"], list(req["changes"])), ("update", ref, ["body"]))
            self.assertEqual(self.stored_rows(ref), [{"by": "2099-03-04", "from": "Steering group", "hidden": 0, "kind": "information", "what": "Choose the pilot site"}])
            self.assertEqual(p.toast(), "Row added.")
            cells = p.js(self.cells(ref, "tbody tr[data-row] td"))
            self.assertEqual(cells[0], "Information Choose the pilot site")
            self.assertEqual(cells[1], "Steering group")
            self.assertTrue(cells[2].startswith("04-03-2099"), cells[2])
            p.until("document.activeElement.matches('[data-add-row]')", "focus went back to the Add a row button")
            p.js("document.querySelector('[data-undo]').click()")
            p.until("!" + self.one(ref, "tbody tr[data-row]"), "Undo took the row away")
            self.assertEqual(self.stored_rows(ref), [])
            self.assertEqual(self.steps(), before + 2, "an Undo is its own step")

    def test_edit_hide_include_and_remove_a_row_are_each_one_step_with_one_undo(self):
        ref = self.make(row(what="One"), row(what="Two", kind="date", by=""))
        first = "[data-row='0'] .n-text"
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            start = self.stored_rows(ref)
            # edit row 0
            before = self.steps()
            self.click(p, ref, "[data-row='0'] [data-edit]")
            p.until("document.activeElement.matches('[data-f=what]')", "the row's fields")
            self.assertEqual(p.js(self.one(ref, "[data-f=by]") + ".value"), "04-03-2099", "the date is written DD-MM-YYYY")
            self.fill(p, ref, what="One, reworded", frm="Finance")
            self.click(p, ref, "[data-save]")
            p.until(self.text_of(ref, first) + " === 'One, reworded'", "saved")
            self.assertEqual((self.steps(), p.toast()), (before + 1, "Row saved."))
            self.assertEqual(self.stored_rows(ref)[0]["from"], "Finance")
            p.js("document.querySelector('[data-undo]').click()")
            p.until(self.text_of(ref, first) + " === 'One'", "Undo put the row back")
            self.assertEqual(self.stored_rows(ref), start)
            # leave out row 1
            before = self.steps()
            self.click(p, ref, "[data-row='1'] [data-flip]")
            p.until(self.present(ref, "tr.n-left"), "the row is marked as left out")
            p.toast_is("Row left out of the published page.")
            self.assertEqual((self.steps(), p.toast()), (before + 1, "Row left out of the published page."))
            self.assertEqual(p.js(self.text_of(ref, "tr.n-left .tag.hid")), "Left out of the published page", "in words, not only by look")
            self.assertEqual(p.js(self.text_of(ref, "tr.n-left [data-flip]")), "Include")
            self.assertEqual([r["hidden"] for r in self.stored_rows(ref)], [0, 1])
            p.js("document.querySelector('[data-undo]').click()")
            p.until("!" + self.one(ref, "tr.n-left"), "Undo included it again")
            self.assertEqual(self.stored_rows(ref), start)
            # include it again after leaving it out
            self.click(p, ref, "[data-row='1'] [data-flip]")
            p.until(self.present(ref, "tr.n-left"), "left out")
            before = self.steps()
            self.click(p, ref, "[data-row='1'] [data-flip]")
            p.until("!" + self.one(ref, "tr.n-left"), "included")
            p.toast_is("Row included in the published page.")
            self.assertEqual((self.steps(), p.toast()), (before + 1, "Row included in the published page."))
            # remove row 0
            before = self.steps()
            self.click(p, ref, "[data-row='0'] [data-remove]")
            p.until(self.count(ref, "tbody tr[data-row]") + " === 1", "removed")
            p.toast_is("Row removed.")
            self.assertEqual((self.steps(), p.toast()), (before + 1, "Row removed."))
            self.assertEqual([r["what"] for r in self.stored_rows(ref)], ["Two"])
            p.js("document.querySelector('[data-undo]').click()")
            p.until(self.count(ref, "tbody tr[data-row]") + " === 2", "Undo put it back")
            self.assertEqual(self.stored_rows(ref), start)

    def test_a_row_that_cannot_be_saved_says_why_in_plain_words_and_sends_nothing(self):
        ref = self.make(row(what="One"))
        by_words = "By must be a real day written DD-MM-YYYY, between 2000 and 2100, or empty."
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-add-row]")
            p.until(self.present(ref, "[data-f=what]"), "the form")
            sent = len(self.sent)
            for what, kwargs, words in (("", {}, sb.NEEDS_WHAT_MISSING), ("x" * 301, {}, sb.NEEDS_WHAT_LONG),
                                        ("Fine", {"by": "31-02-2099"}, by_words), ("Fine", {"by": "04-03-1999"}, by_words),
                                        ("Fine", {"by": "", "frm": "y" * 101}, sb.NEEDS_FROM_LONG)):
                self.fill(p, ref, what=what, **kwargs)
                self.click(p, ref, "[data-save]")
                p.until(self.present(ref, ".n-err"), "a sentence appears")
                self.assertEqual(p.js(self.text_of(ref, ".n-err")), words)
                self.assertEqual(p.js(self.one(ref, ".n-err") + ".getAttribute('role')"), "alert", "it is read out")
                self.assertEqual(len(self.sent), sent, "nothing was sent")
            self.assertEqual(len(self.stored_rows(ref)), 1)

    def test_escape_cancels_with_nothing_sent_and_focus_goes_back(self):
        ref = self.make(row(what="One"))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            sent = len(self.sent)
            self.click(p, ref, "[data-row='0'] [data-edit]")
            p.until("document.activeElement.matches('[data-f=what]')", "editing")
            self.fill(p, ref, what="Changed my mind")
            p.key("Escape", code="Escape", vk=27)
            p.until("!" + self.one(ref, "[data-f=what]"), "the form closed")
            self.assertEqual(len(self.sent), sent)
            self.assertEqual(p.js(self.text_of(ref, "[data-row='0'] .n-text")), "One")
            p.until("document.activeElement.matches('[data-edit]')", "focus is back on the row's Edit button")

    def test_enter_saves_a_row_from_a_field(self):
        ref = self.make()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-add-row]")
            p.until("document.activeElement.matches('[data-f=what]')", "form")
            p.type("Send the access list")
            p.key("Enter", code="Enter", vk=13)
            p.until(self.count(ref, "tbody tr[data-row]") + " === 1", "saved with Enter")
            self.assertEqual(self.stored_rows(ref)[0]["what"], "Send the access list")

    def test_two_quick_edits_to_different_fields_are_both_kept(self):
        ref = self.make()
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.click(p, ref, "[data-add-row]")
            p.until(self.present(ref, "[data-f=what]"), "form")
            p.js("(function(){var a=" + self.one(ref, "[data-f=what]") + ", b=" + self.one(ref, "[data-f=from]") + ";"
                 "a.value='Quick'; a.dispatchEvent(new Event('input', {bubbles: true}));"
                 "b.value='Fast'; b.dispatchEvent(new Event('input', {bubbles: true}));})()")
            self.click(p, ref, "[data-save]")
            p.until(self.count(ref, "tbody tr[data-row]") + " === 1", "saved")
            row_ = self.stored_rows(ref)[0]
            self.assertEqual((row_["what"], row_["from"]), ("Quick", "Fast"))

    def test_a_refusal_from_the_store_is_said_in_words_and_the_form_stays_open(self):
        ref = self.make(row(what="One"))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.failure = lambda req: (400, {"ok": False, "message": SECRET_FROM_THE_SERVER, "code": "refused"})
            self.click(p, ref, "[data-row='0'] [data-edit]")
            p.until("document.activeElement.matches('[data-f=what]')", "editing")
            self.fill(p, ref, what="Reworded")
            self.click(p, ref, "[data-save]")
            p.until("!!document.querySelector('.toast-text') && /nothing was changed/i.test(document.querySelector('.toast-text').textContent)", "a plain toast")
            self.assertNotIn(SECRET_FROM_THE_SERVER, p.toast())
            self.assertTrue(p.js(self.present(ref, "[data-f=what]")), "the form is still open with what was typed")
            self.assertEqual(p.js(self.one(ref, "[data-f=what]") + ".value"), "Reworded")
            self.assertEqual(self.stored_rows(ref)[0]["what"], "One")

    def test_a_full_list_cannot_take_another_row(self):
        ref = self.make(*[row(what="Row " + str(n)) for n in range(100)])
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            self.assertTrue(p.js(self.one(ref, "[data-add-row]") + ".disabled"))
            self.assertEqual(p.js(self.text_of(ref, ".n-add .muted") + ".trim()"), "A list can have 100 rows at most. Remove one to add another.")

    # ── View ─────────────────────────────────────────────────────────────────

    def test_view_is_a_table_with_the_three_words_and_nothing_to_change(self):
        ref = self.make(row(what="Choose the pilot site", kind="decision", by="2099-03-04", **{"from": "Steering group"}),
                        row(what="Send the access list", kind="information", by="", **{"from": ""}),
                        row(what=MARK, hidden=1))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js("[..." + self.many(ref, "th") + "].map(th => th.textContent)"), ["What is needed", "From", "By"])
            rows = p.js("[..." + self.many(ref, "tbody tr") + "].map(tr => [...tr.cells].map(td => td.textContent.replace(/\\s+/g, ' ').trim()))")
            self.assertEqual(rows, [["Decision Choose the pilot site", "Steering group", "04-03-2099"], ["Information Send the access list", "—", "—"]])
            self.assertNotIn(MARK, p.js("document.body.textContent"), "a row that is left out is absent")
            self.assertEqual(edit_elements(cdp, p.sid), [], "View has no field, button or edit part")
            self.assertEqual(p.js(self.count(ref, "button, input, select, textarea, [tabindex], a")), 0, "nothing to press or type in")
            self.assertEqual(p.js(self.text_of(ref, ".sec-h")), "Needs from you")
            self.assertNotIn("Not shown on this page yet.", p.js(self.text_of(ref, "")))

    def test_a_date_that_has_passed_says_the_word_overdue_and_a_date_to_come_does_not(self):
        ref = self.make(row(what="Late thing", by="2020-01-02"), row(what="Coming thing", by="2099-01-02"), row(what="Undated", by=""))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.cells(ref, "tbody tr td.n-by")), ["02-01-2020 Overdue", "02-01-2099", "—"])
            self.assertEqual(p.js(self.count(ref, ".n-over")), 1)
            p.edit()
            self.assertEqual(p.js(self.cells(ref, "tbody tr .n-date")), ["02-01-2020 Overdue", "02-01-2099", "—"], "Edit says it too")

    def test_hidden_rows_and_hidden_sections_and_empty_lists_are_absent_in_view(self):
        shown = self.make(row(what="Shown"), row(what=MARK + "-row", hidden=1), title="Shown needs")
        left_out = self.make(row(what=MARK + "-section"), title="Left out needs", hidden=1)
        all_left = self.make(row(what=MARK + "-all", hidden=1), title="All left out needs")
        empty = self.make(title="Empty needs")
        with chrome() as cdp:
            p = self.visit(cdp)
            ids = p.ids()
            self.assertIn(shown, ids)
            for ref in (left_out, all_left, empty):
                self.assertNotIn(ref, ids, "absent, not hidden")
            self.assertNotIn(MARK, p.js("document.body.innerHTML"))
            p.edit()
            ids = p.ids()
            for ref in (shown, left_out, all_left, empty):
                self.assertIn(ref, ids, "Edit shows every section")
            self.assertIn(MARK + "-row", p.js("document.body.textContent"), "and every row")
            p.view()
            self.assertNotIn(MARK, p.js("document.body.innerHTML"))

    def test_a_markup_row_is_only_text(self):
        typed = "<img src=x onerror=window.__bad=1> <b>bold</b>"
        ref = self.make(row(what=typed, **{"from": "<script>window.__bad=2</script>"}))
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertEqual(p.js(self.count(ref, "img, b, script")), 0)
            self.assertIsNone(p.js("window.__bad"))
            self.assertIn("<b>bold</b>", p.js(self.text_of(ref, ".n-text")))
            p.edit()
            self.assertEqual(p.js(self.count(ref, "img, b, script")), 0)
            self.click(p, ref, "[data-edit]")
            p.until(self.present(ref, "[data-f=what]"), "form")
            self.assertEqual(p.js(self.one(ref, "[data-f=what]") + ".value"), typed)

    # ── the section's own menu ───────────────────────────────────────────────

    def test_the_menu_of_a_needs_section_can_delete_it_and_one_undo_puts_it_back_with_its_rows(self):
        ref = self.make(row(what="One"))
        with chrome() as cdp:
            p = self.visit(cdp)
            p.edit()
            p.js("document.querySelector('[data-id=ABC-S-004] [data-options]').click()")
            p.until("!!document.querySelector('[data-id=ABC-S-004] .menu')", "menu")
            self.assertNotIn("delete", p.js("[...document.querySelectorAll('[data-id=ABC-S-004] .menu-item')].map(b => b.dataset.act)"), "a milestones section still cannot be deleted")
            p.js("document.querySelector('[data-id=ABC-S-004] [data-options]').click()")
            p.until("!document.querySelector('.menu')", "the menu closed")
            p.js("document.querySelector('[data-id=" + ref + "] [data-options]').click()")
            p.until("!!document.querySelector('[data-id=" + ref + "] .menu')", "menu")
            self.assertEqual(p.js("[...document.querySelectorAll('[data-id=" + ref + "] .menu-item')].map(b => b.dataset.act)"), ["add", "up", "down", "beside", "hide", "delete"])
            self.assertEqual(p.js("document.querySelector('[data-id=" + ref + "] [data-act=delete]').textContent"), "Delete section")
            before = self.steps()
            p.js("document.querySelector('[data-id=" + ref + "] [data-act=delete]').click()")
            p.until("!document.querySelector('[data-id=" + ref + "]')", "deleted")
            self.assertEqual(self.steps(), before + 1)
            p.js("document.querySelector('[data-undo]').click()")
            p.until("!!document.querySelector('[data-id=" + ref + "]')", "Undo put it back")
            self.assertEqual([r["what"] for r in self.stored_rows(ref)], ["One"])

    # ── the published file ───────────────────────────────────────────────────

    def publish_file(self, now="2030-01-15"):
        folder = tempfile.mkdtemp(prefix="clark-pub-")
        self.addCleanup(shutil.rmtree, folder, True)
        done = publish.publish(self.store, "ABC", folder, by_user=USER, now=now, branding=EMPTY_BRANDING)
        return Path(done["path"])

    def test_the_published_file_has_the_table_view_only_and_reads_overdue_as_at_the_day_it_was_published(self):
        ref = self.make(row(what="Late by then", kind="date", by="2029-12-31", **{"from": "Finance"}), row(what="Still to come", by="2031-01-01", **{"from": ""}),
                        row(what=MARK + "-row", hidden=1, by="2029-01-01"), title="Needs from you")
        gone = self.make(row(what=MARK + "-section"), title="Hidden needs", hidden=1)
        empty = self.make(title="Empty needs")
        path = self.publish_file()
        text = path.read_text(encoding="utf-8")
        for marker in (MARK + "-row", MARK + "-section"):
            for spelling in spellings(marker):
                self.assertNotIn(spelling, text)
        with chrome() as cdp:
            sid = page_target(cdp)
            cdp.call("Page.navigate", {"url": path.as_uri()}, sid)
            self.assertTrue(wait(lambda: cdp.js("document.documentElement.dataset.ready === '1'", sid)))
            self.assertTrue(wait(lambda: cdp.js(self.present(ref, "table.needs"), sid)), "the table is drawn")
            self.assertEqual(cdp.js("[..." + self.many(ref, "th") + "].map(th => th.textContent)", sid), ["What is needed", "From", "By"])
            rows = cdp.js("[..." + self.many(ref, "tbody tr") + "].map(tr => [...tr.cells].map(td => td.textContent.replace(/\\s+/g, ' ').trim()))", sid)
            self.assertEqual(rows, [["Date Late by then", "Finance", "31-12-2029 Overdue"], ["Decision Still to come", "—", "01-01-2031"]],
                             "Overdue is read as at the day it was published, not today")
            self.assertEqual(cdp.js("document.querySelectorAll('input, select, textarea, button[data-add-row], [contenteditable], [data-edit-only]').length", sid), 0)
            self.assertEqual(cdp.js(self.count(ref, "button, [tabindex]"), sid), 0)
            ids = cdp.js("[...document.querySelectorAll('.secs > .sec')].map(s => s.dataset.id)", sid)
            self.assertNotIn(gone, ids)
            self.assertNotIn(empty, ids)
            self.assertNotIn(MARK, cdp.js("document.body.textContent", sid))
            for scheme in ("light", "dark"):
                for width in (1400, 900):
                    cdp.call("Emulation.setDeviceMetricsOverride", {"width": width, "height": 900, "deviceScaleFactor": 1, "mobile": False}, sid)
                    cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": scheme}]}, sid)
                    self.assertTrue(wait(lambda: cdp.js("window.innerWidth === " + str(width), sid)))
                    self.assertTrue(cdp.js("document.documentElement.scrollWidth <= innerWidth", sid), "no sideways scroll at " + str(width) + " in " + scheme)

    # ── the layout, light and dark, at 1400 and 900 ──────────────────────────

    CONTRAST = """(function(sel){
      function parse(c){var m=/rgba?\\(([^)]+)\\)/.exec(c);if(!m)return null;var p=m[1].split(',').map(parseFloat);return {r:p[0],g:p[1],b:p[2],a:p.length>3?p[3]:1};}
      function bg(el){while(el){var c=parse(getComputedStyle(el).backgroundColor);if(c&&c.a>0.99)return [c.r,c.g,c.b];el=el.parentElement;}return [255,255,255];}
      var out=[];document.querySelectorAll(sel).forEach(function(el){var f=parse(getComputedStyle(el).color);
        out.push([el.textContent.trim().slice(0,30),[f.r,f.g,f.b],bg(el),parseFloat(getComputedStyle(el).fontSize)]);});return out;})(%s)"""

    def test_it_fits_and_reads_at_1400_and_900_in_light_and_dark_in_view_and_in_edit(self):
        long_what = "A rather long thing the client must decide on, written out in full so that it has to wrap in its column " * 2
        ref = self.make(row(what=long_what, by="2020-02-03", **{"from": "The steering group and the finance team of the client"}),
                        row(what="Short", kind="information", by="2099-12-31"), row(what="Left out", hidden=1, kind="date"))
        colours = ".n-over, .n-kind, .n-err, th, td.n-from, .n-text"
        with chrome() as cdp:
            p = self.visit(cdp)
            for mode in ("view", "edit"):
                if mode == "edit":
                    p.edit()
                    self.click(p, ref, "[data-row='1'] [data-edit]")
                    p.until(self.present(ref, "[data-f=what]"), "a row open for editing")
                for scheme in ("light", "dark"):
                    for width in (1400, 900):
                        self.resize(cdp, p, width, scheme)
                        where = mode + " at " + str(width) + " in " + scheme
                        self.assertTrue(self.fits(p, ref), "nothing leaves the section or scrolls sideways: " + where)
                        small = p.js("[..." + self.many(ref, "table.needs *") + "].filter(e => [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(getComputedStyle(e).fontSize) < 13).map(e => e.className)")
                        self.assertEqual(small, [], "no text under 13 px: " + where)
                        sel = ", ".join(".secs > .sec[data-id=" + json.dumps(ref) + "] table.needs " + part.strip() for part in colours.split(","))
                        found = p.js(self.CONTRAST % json.dumps(sel))
                        self.assertGreater(len(found), 3, where)
                        for text, fg, back, size in found:
                            self.assertGreaterEqual(ratio(fg, back), 4.5, repr(text) + " reads against its background: " + where)
                        if mode == "edit":
                            for sel_ in ("[data-f]", "[data-edit], [data-flip], [data-remove], [data-add-row], [data-save], [data-cancel]"):
                                heights = p.js("[..." + self.many(ref, sel_) + "].filter(e => e.getBoundingClientRect().width).map(e => Math.round(e.getBoundingClientRect().height))")
                                self.assertTrue(heights and min(heights) >= 24, "controls are at least 24 px tall: " + sel_ + " " + where)
            cdp.call("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]}, p.sid)


SECRET_FROM_THE_SERVER = "Server text that a person must never read"


if __name__ == "__main__":
    unittest.main()
