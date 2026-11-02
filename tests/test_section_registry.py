"""#96 R0, the section template registry that lands before any template is built: every template type is named alike in the
store, the schema, the Python registry (src/clark/section_kinds/), the page's catalogue (logic/templates.js), its view parts
(templates/index.js) and its Edit parts (edit/templates/index.js); a stub is never published and never shown in View; a template
is placeable only when its catalogue entry is ready, and ready is refused on a stub; the page's publishable() keeps exactly the
rows publish.select keeps; the shared link, picture and file checks (templates/safe.js).

Run: python3 dev/run_tests.py test_section_registry
Needs Chrome (the #33 harness): the page tests fail, never skip, without it. Fictional data only.
"""
import ast
import contextlib
import json
import re
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

from _demo import USER
from _paths import ROOT, SRC
from clark import changes, publish, section_bodies, section_kinds, server as sv, store as store_module
from clark.section_kinds import base
from test_changes import Api
from test_report_editor import Base as PageBase
from test_server import Running, chrome, wait

PAGE_SRC = SRC / "clark" / "page" / "src"
DEMO = ROOT / "tests" / "fixtures" / "registry_demo.js"
BUILT_IN = ("current", "glance", "usecases", "milestones", "text", "raid", "actions", "decisions", "docs", "needs", "tracker")
_PAGE = {}


def bare_page():
    """The registry's page side, bundled by the pinned esbuild in a temporary folder, on a bare page."""
    if "html" not in _PAGE:
        import sys
        sys.path.insert(0, str(ROOT / "dev" / "tools"))
        import build_page
        import esbuild
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "t.js"
            done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(DEMO), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            script = out.read_text(encoding="utf-8").replace("</script", "<\\/script")
        _PAGE["html"] = (f'<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8"><title>t</title></head>\n'
                         f'<body><div id="root"></div>\n<script>{script}</script>\n</body></html>\n')
    return _PAGE["html"]


PURE_LIBRARY = ("base64", "binascii", "re")      # #96: standard library parts that read no file and no database
STUBS = tuple(t for t in section_kinds.TYPES if not section_kinds.REGISTRY[t].READY)   # the real stubs left (none once every template is built)
STAND_IN = "callout"      # a real type that a test turns back into a stub, while no real stub is left


@contextlib.contextmanager
def fake_stub(kind=STAND_IN):
    """`kind` is a stub for the length of the block, as base.py's stub contract writes one: any body passes the generic walls and
    nothing of it is ever published. Patches the registry and the tables section_bodies builds from it, and puts them back."""
    stub = types.SimpleNamespace(READY=False, LIMIT=base.STUB_LIMIT, EMPTY="", check=base.stub_check, published=base.stub_published)
    with mock.patch.dict(section_kinds.REGISTRY, {kind: stub}), mock.patch.dict(section_bodies.CHECKERS, {kind: stub.check}), \
            mock.patch.dict(section_bodies.EMPTY, {kind: stub.EMPTY}), mock.patch.dict(section_bodies.LIMITS, {kind: stub.LIMIT}):
        yield kind


def schema_types():
    sql = store_module.SCHEMA.read_text(encoding="utf-8")
    statement = next(st for st in store_module._statements(sql) if "TABLE IF NOT EXISTS report_sections (" in st)
    return tuple(re.findall(r"'([a-z0-9]+)'", statement.split("CHECK (type IN (")[1].split("))")[0]))


class PythonSide(unittest.TestCase):
    def test_the_store_the_schema_and_the_registry_name_the_same_eighteen_types(self):
        self.assertEqual(len(section_kinds.TYPES), 18)
        self.assertEqual(len(set(section_kinds.TYPES)), 18)
        self.assertEqual(store_module.SECTION_TYPES, BUILT_IN + section_kinds.TYPES, "the store lists them in the registry's order")
        self.assertEqual(schema_types(), store_module.SECTION_TYPES)
        self.assertEqual(store_module.ALLOWED[("report_sections", "type")], store_module.SECTION_TYPES)

    def test_every_table_built_from_the_registry_covers_every_type(self):
        for t in section_kinds.TYPES:
            m = section_kinds.REGISTRY[t]
            self.assertEqual(m.__name__, f"clark.section_kinds.{t}", "one module per type, named after it")
            self.assertIs(section_bodies.CHECKERS[t], m.check)
            self.assertEqual(section_bodies.EMPTY[t], m.EMPTY)
            self.assertEqual(section_bodies.LIMITS[t], m.LIMIT)
            self.assertIn(t, section_bodies.BODY_TYPES)
            self.assertIn(t, store_module.BODY_TYPES)
            self.assertIn(t, store_module.DELETABLE_TYPES)
            self.assertIn(t, changes.NEW_SECTION_TYPES)
            self.assertIn(t, publish.SECTION_TYPES)
        self.assertEqual(sorted(p.stem for p in (SRC / "clark" / "section_kinds").glob("*.py") if p.stem not in ("__init__", "base")),
                         sorted(section_kinds.TYPES), "no module is left out of the registry")

    def test_every_template_module_keeps_the_contract(self):
        for t, m in section_kinds.REGISTRY.items():
            with self.subTest(type=t):
                self.assertIsInstance(m.READY, bool)
                self.assertTrue(type(m.LIMIT) is int and 0 < m.LIMIT)
                self.assertIsInstance(m.EMPTY, str)
                self.assertTrue(callable(m.check) and callable(m.published))

    def test_a_template_saved_through_the_change_route_fits_its_limit(self):
        """The route's body limit is above the largest content (with room for the request around it and its escaping)."""
        biggest = max(getattr(m, "TEXT_LIMIT", m.LIMIT) for m in section_kinds.REGISTRY.values())   # a picture template's words; its pictures come by their own route
        limit = sv.ROUTE_BODY_LIMITS["/api/change"]
        self.assertEqual(limit, 2 * biggest + 4 * 1024)
        # worst case: a stored body of quotes and backslashes, escaped once in the stored text and again as a string in the request
        stored = '"\\' * (biggest // 2)
        self.assertEqual(len(stored), biggest)
        head = json.dumps({"project": "ABC", "op": "edit", "changes": {"body": stored}, "pad": ""}).encode("ascii")
        self.assertGreater(len(head), 2 * biggest, "the worst case is about twice the content")
        pad = limit - len(head)
        self.assertGreaterEqual(pad, 0, "the worst case fits the limit")
        calls = []

        def change(req):
            calls.append(req)
            return 200, {"ok": True}
        running = Running(change=change, undo=lambda req: (200, {"ok": True}))
        self.addCleanup(running.close)
        fits = head.replace(b'"pad": ""', b'"pad": "' + b"x" * pad + b'"')
        self.assertEqual(len(fits), limit)
        self.assertEqual(running.api("POST", "/api/change", fits)[0], 200)
        self.assertEqual(calls[0]["changes"]["body"], stored)
        self.assertEqual(running.api("POST", "/api/change", fits + b" ")[0], 400, "one past the limit is refused")

    def test_the_change_route_limit_is_worked_out_from_the_largest_body_and_the_escape_factor(self):
        """#378: the limit is the largest body, times what escaping can make of it, plus the request around it; none of the three is a bare number in the sum."""
        biggest = max(getattr(m, "TEXT_LIMIT", m.LIMIT) for m in section_kinds.REGISTRY.values())
        self.assertEqual(sv.SECTION_BODY_MAX, biggest, "the server's copy of the largest body follows the registry")
        self.assertEqual(sv.CHANGE_BODY_LIMIT, sv.ESCAPE_FACTOR * sv.SECTION_BODY_MAX + sv.REQUEST_ENVELOPE)
        self.assertEqual(sv.ROUTE_BODY_LIMITS["/api/change"], sv.CHANGE_BODY_LIMIT)
        self.assertGreaterEqual(sv.CHANGE_BODY_LIMIT, 2 * 64 * 1024 + 4 * 1024, "never smaller than before")
        self.assertEqual(sv.change_body_limit(biggest), sv.CHANGE_BODY_LIMIT)
        self.assertEqual(sv.change_body_limit(biggest + 1024), sv.CHANGE_BODY_LIMIT + sv.ESCAPE_FACTOR * 1024, "a larger body moves the limit")
        self.assertEqual(sv.change_body_limit(biggest - 1024), sv.CHANGE_BODY_LIMIT - sv.ESCAPE_FACTOR * 1024, "and a smaller one")

    def test_the_largest_body_fully_escaped_and_the_request_around_it_fit_the_change_limit(self):
        biggest = max(getattr(m, "TEXT_LIMIT", m.LIMIT) for m in section_kinds.REGISTRY.values())
        for letter in ('"', "\\"):                    # the two letters JSON writes as two bytes
            body = json.dumps({"project": "ABCDEFG", "kind": "report_section", "op": "update", "id": "ABCDEFG-S-001",
                               "changes": {"body": letter * biggest}}, separators=(",", ":")).encode("ascii")
            envelope = len(body) - sv.ESCAPE_FACTOR * biggest
            self.assertGreater(envelope, 0, letter)
            self.assertLessEqual(envelope, sv.REQUEST_ENVELOPE, "the request around the body fits its allowance")
            self.assertLessEqual(len(body), sv.CHANGE_BODY_LIMIT, letter)

    # #356 (a): the tracker's and the needs section's own maximums (section_bodies.LIMITS, 262,144 stored bytes each) are not the
    # route's: what keeps their widest body inside CHANGE_BODY_LIMIT is the checkers' structural caps (rows, lines, characters).
    # These build the widest body each checker accepts, send it the way the page does (one JSON string inside the request, so each
    # quote and backslash is written twice), and pin the sizes exactly, so a cap that moves by one byte fails here.
    ENVELOPE_IDS = ("ABCDEFG", "ABCDEFG-S-9999")                   # the longest project code and a section id: the request around the body

    def widest_request(self, kind, value, ascii_only):
        """(stored bytes, request bytes) for `value` saved as a `kind` section; the body text is JSON inside the request JSON."""
        inner = json.dumps(value, ensure_ascii=ascii_only, separators=(",", ":"))
        stored = section_bodies.check(kind, inner, store_module.BODY_RULES)
        project, ref = self.ENVELOPE_IDS
        request = json.dumps({"project": project, "kind": "report_sections", "op": "update", "id": ref, "changes": {"body": inner}},
                             ensure_ascii=ascii_only, separators=(",", ":")).encode("utf-8")
        return len(stored.encode("ascii")), len(request)

    @staticmethod
    def widest_needs(letter):
        """The widest needs body the checker accepts: the most rows, `what` and `from` at their longest, a date in every row."""
        row = {"what": letter * section_bodies.NEEDS_WHAT_MAX, "kind": "decision", "from": letter * section_bodies.NEEDS_FROM_MAX,
               "by": "2030-12-31", "hidden": 0}
        return {"v": 1, "rows": [dict(row) for _ in range(section_bodies.NEEDS_MAX_ROWS)]}

    def test_the_widest_tracker_in_every_kind_of_letter_fits_the_change_limit_to_the_byte(self):
        from test_tracker_content import biggest
        got = {}
        for letter in ("a", '"', "\\", "\u00e9", "\u4e2d", "\U00010400"):
            for ascii_only in (False, True):
                got[(letter, ascii_only)] = self.widest_request("tracker", biggest(letter), ascii_only)
        stored = max(s for s, _ in got.values())
        widest = max(r for _, r in got.values())
        self.assertLess(stored, section_bodies.LIMITS["tracker"], "the checker's caps keep the widest tracker under its stored-byte limit")
        self.assertEqual((stored, widest), (81288, 95122), "a tracker cap moved: work out the new widest request, then set these two numbers")
        self.assertLessEqual(widest, sv.CHANGE_BODY_LIMIT)
        self.assertEqual(sv.CHANGE_BODY_LIMIT - widest, 40046, "the room left under the change limit")

    def test_the_widest_needs_body_with_nothing_but_plain_letters_fits_the_change_limit_to_the_byte(self):
        got = {letter: self.widest_request("needs", self.widest_needs(letter), False) for letter in ("a", "\u00e9", "\u4e2d")}
        self.assertEqual(got, {"a": (46916, 48824), "\u00e9": (246916, 88824), "\u4e2d": (246916, 128824)},
                         "a needs cap moved: work out the new sizes, then set these")
        for letter, (stored, request) in got.items():
            self.assertLessEqual(stored, section_bodies.LIMITS["needs"], letter)
            self.assertLessEqual(request, sv.CHANGE_BODY_LIMIT, letter)
        self.assertEqual(sv.CHANGE_BODY_LIMIT - max(r for _, r in got.values()), 6344, "the room left under the change limit")

    def test_the_widest_quote_heavy_needs_body_is_larger_than_the_change_limit_by_these_bytes(self):
        """The sizes of the gap #356 (a) names, pinned so it can neither grow nor close unnoticed. 100 rows of `what` and `from`
        at their longest, all quotes (or all backslashes), are 86,916 stored bytes (each character stored as two) and, escaped
        again inside the request, 168,824 bytes (four each), which the route refuses as too large before the checker sees it. (With no `by` date in each row it is the 85,916
        stored bytes and the roughly 167,800 byte request the reader cited.)"""
        for letter in ('"', "\\"):
            stored, request = self.widest_request("needs", self.widest_needs(letter), False)
            self.assertEqual((stored, request), (86916, 168824), letter)
            self.assertLess(stored, section_bodies.LIMITS["needs"], letter)
            self.assertEqual(request - sv.CHANGE_BODY_LIMIT, 33656, letter)

    @unittest.expectedFailure       # #356 (a), a real gap and a decision for the owner of server.py: a cap or the limit would have to change
    def test_the_widest_quote_heavy_needs_body_fits_the_change_limit(self):
        for letter in ('"', "\\"):
            _, request = self.widest_request("needs", self.widest_needs(letter), False)
            self.assertLessEqual(request, sv.CHANGE_BODY_LIMIT, letter)

    def test_a_stub_publishes_nothing_whatever_its_body_holds(self):
        ctx = base.Context({"actions": [{"id": "ABC-A-001", "description": "Fictional"}]}, "2030-01-15")
        for t, m in section_kinds.REGISTRY.items():
            if m.READY:
                continue
            for value in ({}, [], {"v": 1, "text": "Words"}, [{"id": "ABC-A-001"}]):
                self.assertIsNone(section_bodies.published(t, value, ctx), t)
                self.assertIsNone(section_bodies.published(t, value), t)

    def test_the_context_is_a_copy_of_what_was_kept(self):
        rows = {"actions": [{"id": "ABC-A-001", "description": "Fictional"}]}
        ctx = base.Context(rows, "2030-01-15")
        ctx.rows["actions"][0]["description"] = "changed"
        self.assertEqual(rows["actions"][0]["description"], "Fictional")
        self.assertEqual(ctx.ids["actions"], frozenset({"ABC-A-001"}))
        self.assertEqual(ctx.as_at, "2030-01-15")

    def test_no_template_module_quotes_sql_or_reaches_the_store(self):
        for f in sorted((SRC / "clark" / "section_kinds").glob("*.py")):
            tree = ast.parse(f.read_text(encoding="utf-8"))
            used = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)} | \
                   {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
            self.assertTrue(all(u.startswith("clark.section_kinds") or u in PURE_LIBRARY for u in used), (f.name, used))


class StubNeverPublished(Api):
    """Every real stub, or (once every template is built) a real type turned back into a stub for the test (fake_stub)."""

    def setUp(self):
        super().setUp()
        stack = contextlib.ExitStack()
        self.addCleanup(stack.close)
        self.stubs = STUBS or (stack.enter_context(fake_stub()),)

    def test_a_stub_section_with_a_body_is_left_out_of_the_file_and_its_neighbour_takes_the_full_row(self):
        for t in self.stubs:
            with self.subTest(type=t):
                made = self.ok("new", values={"type": t, "title": f"Fictional {t}"}, after=None)["ref"]
                status, got = self.change(self.req(changes.UPDATE, id=made, changes={"body": json.dumps({"v": 1, "words": ["Fictional words"]})}))
                self.assertEqual(status, 200, got)
        built = publish.build(self.s, "ABC", now="2030-01-15")
        kinds = {s["type"] for s in built["published"]["sections"]}
        self.assertEqual(kinds & set(self.stubs), set(), "no stub section is in the file")
        text = built["body"].decode("utf-8")
        self.assertNotIn("Fictional words", text)
        for t in self.stubs:
            self.assertNotIn(f"Fictional {t}", text)

    def test_a_pair_with_a_stub_half_is_not_a_pair_in_the_file(self):
        text_ref = self.ok("new", values={"type": "text", "title": "Fictional notes"}, after=None)["ref"]
        stub_ref = self.ok("new", values={"type": self.stubs[0], "title": "Fictional stub"}, after=text_ref, beside=1)["ref"]
        self.change(self.req(changes.UPDATE, id=stub_ref, changes={"body": json.dumps({"v": 1})}))
        con_rows = {r["id"]: r for r in self.s.read("report_sections", "ABC")}
        self.assertEqual(con_rows[text_ref]["beside"], 1, "the two share a row in the report")
        sections = {s["id"]: s for s in publish.build(self.s, "ABC", now="2030-01-15")["published"]["sections"]}
        self.assertNotIn(stub_ref, sections)
        if text_ref in sections:
            self.assertEqual(sections[text_ref]["beside"], 0)


class PageSide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.stack = contextlib.ExitStack()
        cls.server = Running(page_html=bare_page)
        cls.stack.callback(cls.server.close)
        cls.cdp = cls.stack.enter_context(chrome())
        tid = next(t["targetId"] for t in cls.cdp.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        cls.sid = cls.cdp.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]

    @classmethod
    def tearDownClass(cls):
        cls.stack.close()

    def setUp(self):
        self.cdp.call("Page.navigate", {"url": f"http://127.0.0.1:{self.server.port}/"}, self.sid)
        self.assertTrue(wait(lambda: self.cdp.js("!!(window.T && window.T.templates)", self.sid)), "the test bundle ran")

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    # ── completeness ─────────────────────────────────────────────────────────

    def test_catalogue_type_is_store_type_is_registry_is_page_index(self):
        """Every template type once in each list: the catalogue (box and later entries), the page's type list, the view parts,
        the Edit parts, the Python registry and the store."""
        types = list(section_kinds.TYPES)
        self.assertEqual(self.val("T.TEMPLATE_TYPES"), types)
        self.assertEqual(sorted(self.val("T.parts")), sorted(types))
        self.assertEqual(sorted(self.val("T.edits")), sorted(types))
        self.assertTrue(all(v == "function" for v in self.val("T.edits").values()))
        self.assertTrue(all(p["view"] == "function" and p["isEmpty"] == "function" for p in self.val("T.parts").values()))
        cat = self.val("T.templates.CATALOGUE")
        cat_types = [x["type"] for x in cat if x["type"] not in ("text", "needs")]
        self.assertEqual(sorted(cat_types), sorted(types), "one catalogue entry per template type")
        self.assertEqual([x["type"] for x in cat if x["type"] in ("text", "needs")], ["text", "needs"], "and Text and Needs from you (#121), once each")
        self.assertEqual(len({x["id"] for x in cat}), len(cat))
        self.assertEqual(self.val("T.templates.TEMPLATES.length + T.templates.LATER.length"), len(cat))
        self.assertTrue(set(store_module.SECTION_TYPES) >= set(x["type"] for x in cat))

    def test_every_template_view_file_and_edit_file_is_there_and_pre_filled(self):
        for t in section_kinds.TYPES:
            self.assertIn(f'store type "{t}"', "".join(p.read_text(encoding="utf-8") for p in (PAGE_SRC / "templates").glob("*.jsx")))
            self.assertIn(f'store type "{t}"', "".join(p.read_text(encoding="utf-8") for p in (PAGE_SRC / "edit" / "templates").glob("*.jsx")))
        for p in list((PAGE_SRC / "templates").glob("*.js*")) + list((PAGE_SRC / "edit" / "templates").glob("*.js*")):
            self.assertNotIn("dangerouslySetInnerHTML=", p.read_text(encoding="utf-8"), p.name)

    # ── a stub type is placeable only when ready ─────────────────────────────

    def test_a_stub_type_is_placeable_only_when_ready(self):
        """Replaces the first slice's 'the store refuses every type but text': the store now takes every template type, and only
        the catalogue's ready flag (switched on by the lead once a template is built) makes one placeable."""
        accepts = self.val("T.templates.ACCEPTS.types")
        self.assertEqual(accepts, ["text", "needs"] + list(section_kinds.TYPES))      # needs: the section that carries content (#121)
        self.assertLessEqual(set(accepts), set(changes.NEW_SECTION_TYPES), "the page's ACCEPTS is all taken by the change route")
        self.assertEqual(changes.CHANGE_KINDS["report_sections"][changes.NEW], ("type", "title"), "new still takes a type and a title only")
        for x in self.val("T.templates.CATALOGUE"):
            tid = x["id"]
            if x["type"] in ("text", "needs"):       # not templates of the registry: always placeable
                self.assertIs(x["ready"], True)
                continue
            ready = x["ready"]
            self.assertIs(type(ready), bool, tid)
            self.assertEqual(self.val(f"T.templates.available(T.templates.CATALOGUE.find(t => t.id === {json.dumps(tid)}))"), ready, tid)
            self.assertIs(self.val(f"T.templates.available({{...T.templates.CATALOGUE.find(t => t.id === {json.dumps(tid)}), ready: true}})"), True,
                          f"{tid}: ready is the one switch")
            if not ready:
                if self.val(f"!!T.templates.find({json.dumps(tid)})"):
                    p = self.val(f"T.templates.plan([{{id: 'a', type: 'text', title: 'A', beside: 0, hidden: 0}}], {json.dumps(tid)}, 'a', false)")
                    self.assertEqual((p["ok"], p["message"]), (False, "Coming with a later release."), tid)
            else:
                self.assertTrue(section_kinds.REGISTRY[x["type"]].READY, f"{tid} is ready, but its section_kinds module is a stub")
                self.assertTrue(self.val("T.parts")[x["type"]]["ready"], f"{tid} is ready, but its page part is a stub")
        self.assertIs(self.val("T.templates.available({id: 'x', type: 'raid5', ready: true})"), False, "a type the store does not take")

    def test_the_later_entries_are_not_in_the_box_yet_and_carry_no_words(self):
        """Their words are held back with Help's until their slice ships: no name, description or parts on the page."""
        self.assertEqual({k for x in self.val("T.templates.LATER") for k in x}, {"id", "type", "ready"})
        later = [x["id"] for x in self.val("T.templates.LATER")]
        self.assertEqual(len(later), 7)      # nine at R0; Link preview and One document moved into the box (#96 G7)
        listed = [x["id"] for x in self.val("T.templates.list()")]
        self.assertEqual(set(later) & set(listed), set())
        for tid in later:
            self.assertIsNone(self.val(f"T.templates.find({json.dumps(tid)})"))

    def test_a_stub_is_empty_and_a_built_in_type_is_not_a_template(self):
        for t in section_kinds.TYPES:
            self.assertIs(self.val(f"T.templateEmpty({{id: 'x', type: {json.dumps(t)}, body: '{{\"v\":1}}'}}, {{}})"), True, t)
        for t in BUILT_IN:
            self.assertIsNone(self.val(f"T.templateFor({json.dumps(t)})"), t)
            self.assertIs(self.val(f"T.templateEmpty({{id: 'x', type: {json.dumps(t)}}}, {{}})"), False, t)
        self.assertIsNone(self.val("T.templateFor('__proto__')"))
        self.assertIsNone(self.val("T.templateFor('constructor')"))

    # ── publishable() is publish.select's keep ───────────────────────────────

    def test_publishable_keeps_exactly_what_publish_keeps(self):
        def row(i, kind, **more):
            prefix = {"milestones": "M", "actions": "A", "decisions": "D", "use_cases": "U"}.get(kind)
            rid = f"ABC-{prefix}-{i:03d}" if prefix else f"ABC-{i:03d}"
            base_row = {"id": rid, "project": "ABC", "archived": 0, "client_visible": 1}
            base_row.update({"milestones": {"name": "Fictional", "status": "Planned", "baseline_date": "2030-02-01"},
                             "actions": {"description": "Fictional", "status": "Open"},
                             "raid": {"description": "Fictional", "type": "Risk", "status": "Open"},
                             "decisions": {"decision": "Fictional", "status": "Pending"},
                             "use_cases": {"title": "Fictional", "status": "On track", "standing": ""}}[kind])
            base_row.update(more)
            return base_row
        variants = [{}, {"archived": 1}, {"archived": None}, {"archived": True}, {"archived": False}, {"archived": "0"},
                    {"client_visible": 0}, {"client_visible": None}, {"client_visible": True}, {"client_visible": "1"},
                    {"project": "XYZ"}, {"project": None}, {"hidden_id": True}, {"label": "Sensitive"}, {"label": "SENSITIVE"},
                    {"label": "Board only"}, {"label": "Kept label"},
                    {"label": "STRASSE"}, {"label": "Stra\u00dfe"}, {"label": "Mi\u1e9e"}, {"label": "Mi\u017f\u017f"}, {"label": "\u039f\u0394\u039f\u03a3"}, {"label": "Default out"}, {"no_project": True}]
        data = {"project": {"code": "ABC", "name": "Fictional Programme", "health_reason": "", "current_state": ""},
                "workstreams": [], "links": [], "labels": {}}
        hidden = []
        for kind in publish.KINDS:
            data[kind] = []
            for i, v in enumerate(variants, 1):
                v = dict(v)
                r = row(i, kind, **{k: x for k, x in v.items() if k not in ("hidden_id", "label", "no_project")})
                if v.get("no_project"):
                    r.pop("project")
                if v.get("hidden_id"):
                    hidden.append(r["id"])
                if v.get("label"):
                    data["labels"][r["id"]] = [v["label"]]
                data[kind].append(r)
        label_rules = [{"name": "Board only", "behaviour": "exclude", "default_choice": None},
                       {"name": "Strasse", "behaviour": "exclude", "default_choice": None},      # ß, ẞ, long s and final sigma fold as casefold does
                       {"name": "Miss", "behaviour": "exclude", "default_choice": None},
                       {"name": "\u03bf\u03b4\u03bf\u03c2", "behaviour": "exclude", "default_choice": None},
                       {"name": "Default out", "behaviour": None, "default_choice": "exclude"},
                       {"name": "Kept label", "behaviour": "show", "default_choice": None}]
        for hidden_section in (None, "raid", "usecases"):
            sections = [{"id": "ABC-S-001", "type": "text", "title": "Notes", "body": "", "beside": 0, "hidden": 0, "sort_order": 1}]
            if hidden_section:
                sections.append({"id": "ABC-S-002", "type": hidden_section, "title": "Hidden", "body": "", "beside": 0, "hidden": 1, "sort_order": 2})
            got = publish.select({"data": data, "hidden": hidden, "sections": sections, "label_rules": label_rules,
                                  "changes": [], "undone": [], "as_at": "2030-01-15"})
            rules = json.dumps({"code": "ABC", "hidden": hidden, "labelRules": label_rules, "labels": data["labels"], "sections": sections})
            for kind in publish.KINDS:
                want = [r["id"] for r in got["data"][kind]]
                page = self.val(f"T.publishable.keptRows({json.dumps(data)}, {json.dumps(kind)}, T.publishable.rulesFor({rules})).map(r => r.id)")
                self.assertEqual(page, want, (hidden_section, kind))
        self.assertEqual(self.val("T.publishable.KINDS"), list(publish.KINDS))
        self.assertEqual(self.val("T.publishable.SECTION_OF_KIND"), publish.SECTION_OF_KIND)
        self.assertEqual(sorted(self.val("[...T.publishable.excludedLabels([{name: 'Board only', behaviour: 'exclude'}])]")),
                         sorted(publish._excluded_labels([{"name": "Board only", "behaviour": "exclude"}])))

    # ── the shared checks ────────────────────────────────────────────────────

    def test_safe_href_follows_publish_safe_href(self):
        for href in ("https://example.org/a", " https://example.org", "mailto:someone@example.org", "#ref-section-templates",
                     "HTTPS://EXAMPLE.ORG", "java\tscript:alert(1)", "javascript:alert(1)", "http://example.org", "data:text/html,x",
                     "//example.org", "relative/page.html", "", "ht\ntps://example.org", "\u0000https://example.org", "vbscript:x"):
            with self.subTest(href=href):
                got = self.val(f"T.safe.safeHref({json.dumps(href)})")
                self.assertEqual(bool(got), publish.safe_href(href))
                self.assertFalse(any(ord(c) < 32 for c in got))
        self.assertEqual(self.val("T.safe.safeHref(null)"), "")
        self.assertEqual(self.val("T.safe.safeHref({})"), "")

    def test_safe_image_takes_png_jpeg_and_webp_data_only(self):
        good = ["data:image/png;base64,iVBORw0KGgo=", "data:image/jpeg;base64,/9j/4AAQ", "data:image/webp;base64,UklGRg=="]
        bad = ["data:image/svg+xml;base64,PHN2Zz4=", "data:image/gif;base64,R0lGOD", "https://example.org/a.png",
               "data:image/png;base64,iVBOR w0", "data:image/png,raw", "DATA:image/png;base64,iVBO", "data:image/png;base64,", "",
               "data:image/png;base64,iVBO\"><script>"]
        for v in good:
            self.assertEqual(self.val(f"T.safe.safeImage({json.dumps(v)})"), v)
        for v in bad:
            self.assertEqual(self.val(f"T.safe.safeImage({json.dumps(v)})"), "", v)

    def test_file_href_is_one_name_in_the_report_files_folder(self):
        self.assertEqual(self.val("T.safe.fileHref('Report files/Plan v2.pdf')"), "Report%20files/Plan%20v2.pdf")
        self.assertEqual(self.val("T.safe.fileHref('Report files/a#b?.docx')"), "Report%20files/a%23b%3F.docx")
        for v in ("Report files/../secret.txt", "Report files/sub/a.pdf", "Report files/", "Report files/..", "../Report files/a.pdf",
                  "/Report files/a.pdf", "https://example.org/a.pdf", "Report files\\a.pdf", "Report files/C:a.pdf", "a.pdf", "Report files/a\u0007.pdf"):
            self.assertEqual(self.val(f"T.safe.fileHref({json.dumps(v)})"), "", v)

    def test_date_words_are_dd_mm_yyyy_and_never_a_made_up_day(self):
        self.assertEqual(self.val("T.safe.dateWords('2030-01-15')"), "15-01-2030")
        for v in ("2030-02-31", "soon", "", None, "15-01-2030", "2030-1-5"):
            self.assertEqual(self.val(f"T.safe.dateWords({json.dumps(v)})"), "", v)


class InThePage(PageBase):
    """A stub section in the page clark serves: Edit shows its labelled empty state; View leaves it out, as the file does. Once
    every template is built no stub is left to place, so the served page carries no stub part, and an empty template section
    (one with no content yet) is what View leaves out instead."""

    def add_section(self, kind, title):
        with self.store.step("dashboard", USER) as st:
            return st.create("report_sections", {"project": "ABC", "type": kind, "title": title, "sort_order": 999})

    def test_view_leaves_a_stub_out_and_edit_shows_its_empty_state_in_words(self):
        kind = STUBS[0] if STUBS else STAND_IN
        ref = self.add_section(kind, "Fictional section")
        with chrome() as cdp:
            p = self.visit(cdp)
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"), "View: a stub or an empty template is not shown")
            self.assertNotIn("Fictional section", p.js("document.querySelector('#report').textContent"))
            p.edit()
            p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}]')", "Edit: the section is there to fill in")
            self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}]').dataset.type"), kind)
            stub_shown = p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-stub')")
            if STUBS:
                p.until(f"!!document.querySelector('[data-id={json.dumps(ref)}] .tpl-stub')", "Edit: the stub's empty state")
                self.assertEqual(p.js(f"document.querySelector('[data-id={json.dumps(ref)}] .tpl-stub').textContent"),
                                 "This template can't be filled in yet. It stays out of the published page, so you can remove it or keep it for later.")
            else:
                self.assertFalse(stub_shown, "a built template shows its own Edit part, never the stub's words")
            p.view()
            self.assertFalse(p.js(f"!!document.querySelector('[data-id={json.dumps(ref)}]')"))

    def test_the_published_page_carries_no_template_edit_part(self):
        view = (SRC / "clark" / "page" / "page-view.html").read_text(encoding="utf-8")
        served = (SRC / "clark" / "page" / "page.html").read_text(encoding="utf-8")
        if STUBS:
            self.assertIn("can't be filled in yet", served)
        else:
            self.assertNotIn("can't be filled in yet", served, "no template is a stub, so the stub's Edit part is not in the page")
        self.assertNotIn("can't be filled in yet", view)
        self.assertNotIn("tpl-stub", view)


if __name__ == "__main__":
    unittest.main()
