"""#305 (first part of #153's client file): the filter line's logic in the published file's mode. It may use only the client-safe fields
(`CLIENT_FIELDS`, defined once in src/clark/page/src/logic/filterLine.js) and the three `is:` words the file's own rows can answer
(`CLIENT_IS`); a crafted address, a remembered line or a saved view that names anything else is ignored; and nothing a client may not see
(a row that is not the client's, an internal flag, a freshness or review date) is in an option, a suggestion or a count.

Run: python3 dev/run_tests.py test_filter_line_client
The logic runs inside headless Chrome (bundled with the pinned esbuild, as test_client_page_filters does) over the rows of a REAL published
file: it is published from the test plant, its clark-data block is read back and made into rows by the page's own rowsOf.
Chrome is required: these tests fail, never skip, without it.
"""
import json
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT  # noqa: F401  (puts src/ on the path)
import _publish_fixture as fx

from clark import publish
from clark.store import open_store
from test_client_page_filters import EMPTY_BRANDING, HIDDEN_OWNER, HIDDEN_WS, INTERNAL, TODAY, plant
from test_server import chrome
from test_work_filters import need_chrome
from test_work_items import bundled, page_target

SRC = ROOT / "src" / "clark" / "page" / "src"
SAFE = ["type", "status", "owner", "priority", "due", "workstream", "usecase", "milestone", "is"]
SAFE_IS = ["open", "closed", "overdue"]
NOT_THE_CLIENTS = ["client:shown", "client:internal", "-client:yes", "client:no", "no:client", "is:quiet", "is:incomplete",
                   "is:needed", "is:archived", "-is:quiet", "is:open,quiet", "owner:me", "owner:me,Ana", "IS:QUIET", "CLIENT:internal"]


def data_of(html):
    block = re.search(r'<script type="application/json" id="clark-data">([^<]*)</script>', html)
    return json.loads(block.group(1))["data"]


class ClientLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        need_chrome()
        cls.tmp = Path(tempfile.mkdtemp(prefix="clark-fl-client-"))
        db = fx.build_db(cls.tmp / "c.db", plant())
        cls.store = open_store(db, onedrive_roots=[])
        out = cls.tmp / "out"
        out.mkdir()
        path = Path(publish.publish(cls.store, "PUB", out, by_user="Demo User", now=TODAY, branding=EMPTY_BRANDING)["path"])
        cls.html = path.read_text(encoding="utf-8")
        entry = cls.tmp / "entry.js"
        entry.write_text(f'export * as fl from "{SRC / "logic" / "filterLine.js"}"; export * as filters from "{SRC / "filters.js"}"; '
                         f'export {{ rowsOf }} from "{SRC / "workItems.js"}";\n', encoding="utf-8")
        cls.script = bundled(entry, "P") + ";\n"
        cls.cm = chrome()
        cdp = cls.cdp = cls.cm.__enter__()
        cls.sid = page_target(cdp)
        res = cdp.call("Runtime.evaluate", {"expression": cls.script + "true", "returnByValue": True}, cls.sid)
        assert "exceptionDetails" not in res, res
        cdp.js(f"window.DATA = {json.dumps(data_of(cls.html))}; window.CTX = {{ today: {json.dumps(TODAY)} }}; "
               "P.filters.setPublished(true); window.ROWS = P.rowsOf(window.DATA); true", cls.sid)

    @classmethod
    def tearDownClass(cls):
        cls.cm.__exit__(None, None, None)
        cls.store.close()
        shutil.rmtree(cls.tmp, True)

    def val(self, expr):
        got = self.cdp.js(f"(function(){{ try {{ return JSON.stringify({expr}); }} catch (e) {{ return 'ERROR ' + e.message; }} }})()", self.sid)
        self.assertIsNotNone(got, expr)
        self.assertFalse(got.startswith("ERROR"), f"{expr}: {got}")
        return json.loads(got)

    def ids(self, line):
        return [r["id"] for r in self.val(f"P.fl.apply(ROWS, {json.dumps(line)}, CTX)")]

    # -- the list
    def test_the_client_safe_list_is_defined_once(self):
        self.assertEqual(self.val("P.fl.CLIENT_FIELDS"), SAFE)
        self.assertEqual(self.val("P.fl.CLIENT_IS"), SAFE_IS)
        for banned in ("client", "reviewed", "freshness", "archived", "quiet", "needed"):
            self.assertNotIn(banned, self.val("P.fl.CLIENT_FIELDS"))
        defs = [p.name for p in SRC.rglob("*.js*") if re.search(r"\bCLIENT_FIELDS\s*=", p.read_text(encoding="utf-8"))]
        self.assertEqual(defs, ["filterLine.js"], "the list is written in one place")

    def test_it_offers_only_client_safe_fields(self):
        sug = self.val("P.fl.suggest('', ROWS, CTX).concat(P.fl.suggest('c', ROWS, CTX), P.fl.suggest('-', ROWS, CTX), P.fl.suggest('i', ROWS, CTX))")
        offered = {s["ins"].lstrip("-").rstrip(":") for s in sug}
        self.assertTrue(offered, "something is offered")
        self.assertFalse(offered - set(SAFE) - {"no"}, offered)
        self.assertNotIn("client", offered)
        self.assertEqual([s["label"] for s in self.val("P.fl.suggest('is:', ROWS, CTX)")], SAFE_IS)
        self.assertEqual([o[0] for o in self.val("P.fl.offers('is', ROWS, CTX)")], SAFE_IS)
        self.assertEqual([s["label"] for s in self.val("P.fl.suggest('no:', ROWS, CTX)")], [k for k in SAFE if k not in ("type", "status", "is", "client")])
        self.assertNotIn("me", [o[0] for o in self.val("P.fl.offers('owner', ROWS, CTX)")], "there is no signed-in name in a client's file")
        for h in self.val("P.fl.hints(CTX)"):
            self.assertEqual(self.val(f"P.fl.lineIsClientSafe({json.dumps(h['text'])})"), True, h)
            self.assertNotIn(h["text"], ("owner:me", "is:incomplete", "is:quiet"))
        said = self.val("P.fl.parse('nonsense:x', ROWS, CTX).errors[0].msg")
        self.assertNotIn("client:", said)
        self.assertNotIn("is:quiet", said)

    def test_a_crafted_line_naming_another_field_is_ignored(self):
        everything = self.ids("")
        self.assertTrue(everything)
        for line in NOT_THE_CLIENTS:
            with self.subTest(line=line):
                p = self.val(f"P.fl.parse({json.dumps(line)}, ROWS, CTX)")
                self.assertEqual(p["chips"], [], "nothing is applied")
                self.assertTrue(p["errors"], "and it says so, never a silent empty table")
                self.assertEqual(self.ids(line), everything)
                self.assertEqual(self.val(f"P.fl.normalise({json.dumps(line)}, ROWS, CTX)"), "")
                self.assertFalse(self.val(f"P.fl.lineIsClientSafe({json.dumps(line)})"))
                self.assertEqual(self.val(f"P.fl.toState({json.dumps(line)}, ROWS, CTX).rest"), [])
                self.assertNotIn("Did you mean client", json.dumps(p))
        # a safe field beside a crafted one still works, and the crafted one is dropped from what is written back
        self.assertEqual(self.val("P.fl.normalise('is:open client:internal status:Delayed', ROWS, CTX)"), "is:open status:Delayed")

    def test_a_remembered_line_or_view_naming_another_field_is_ignored(self):
        def kept(line=None, views=None):
            lines = json.dumps({"PUB": line}) if line is not None else "null"
            vs = json.dumps({"PUB": views}) if views is not None else "null"
            return ("{ getItem: (k) => k === 'clark.fline' ? %s : k === 'clark.fviews' ? %s : null }"
                    % (json.dumps(lines) if line is not None else "null", json.dumps(vs) if views is not None else "null"))
        for line in ("client:internal is:open", "is:quiet", "owner:me", "is:open no:client"):
            with self.subTest(line=line):
                self.assertEqual(self.val(f"P.fl.lineGet({kept(line=line)}, 'PUB')"), "is:open")
                views = [{"id": "v1", "name": "Mine", "line": line}, {"id": "v2", "name": "Fine", "line": "is:open priority:High"}]
                got = self.val(f"P.fl.viewsGet({kept(views=views)}, 'PUB')")
                self.assertEqual([v["id"] for v in got], ["v2"], "a saved view that names a field the client may not use is not shown")
        self.assertEqual(self.val(f"P.fl.lineGet({kept(line='is:open priority:High')}, 'PUB')"), "is:open priority:High")
        defaults = self.val("P.fl.viewsGet(null, 'PUB')")
        self.assertTrue(defaults)
        for v in defaults:
            self.assertTrue(self.val(f"P.fl.lineIsClientSafe({json.dumps(v['line'])})"), v)
        self.assertTrue(self.val("P.fl.lineIsClientSafe('is:open priority:High \"a plain word\" no:owner')"))

    def test_a_crafted_address_naming_another_field_is_ignored(self):
        for f in ("client:yes", "reviewed:stale", "mode:all;client:no;reviewed:gap", "client:yes;owner:Ana%20Lopez;reviewed:stale"):
            with self.subTest(f=f):
                line = self.val(f"P.fl.fromState(P.filters.decode({json.dumps(f)}))")
                self.assertFalse(re.search(r"client|quiet|incomplete|reviewed", line), line)
        self.assertEqual(self.val("P.fl.fromState(P.filters.decode('owner:Ana%20Lopez'))"), 'is:open owner:"Ana Lopez"')
        # the older state object itself, as the tiles hand it over
        got = self.val("P.fl.fromStateNote({ mode: 'open', type: 'all', filters: { client: ['no'], reviewed: ['stale'], owner: ['Ana Lopez'] }, not: {}, is: ['quiet'] })")
        self.assertEqual(got["line"], 'is:open owner:"Ana Lopez"')
        self.assertTrue(got["dropped"], "and it says what was left out")

    # -- what the rows are
    def test_a_hidden_item_is_in_no_option_suggestion_or_count(self):
        rows = self.val("ROWS")
        self.assertNotIn(INTERNAL, json.dumps(rows))
        self.assertEqual(self.val("P.fl.apply(ROWS, '', CTX).length"), len(rows))
        seen = []
        for field in SAFE:
            seen.append(self.val(f"P.fl.offers({json.dumps(field)}, ROWS, CTX)"))
            seen.append(self.val(f"P.fl.suggest({json.dumps(field + ':')}, ROWS, CTX)"))
            seen.append(self.val(f"P.fl.suggest({json.dumps('-' + field + ':')}, ROWS, CTX)"))
        seen.append(self.val("P.fl.suggest('no:', ROWS, CTX)"))
        text = json.dumps(seen)
        for hidden in (HIDDEN_OWNER, HIDDEN_WS, INTERNAL, "PUB-A-199"):
            self.assertNotIn(hidden, text)
        # every count is a count of the file's own rows
        total = len(rows)
        for field in SAFE:
            for s in self.val(f"P.fl.suggest({json.dumps(field + ':')}, ROWS, CTX)"):
                self.assertLessEqual(s["n"], total, s)
        # the hidden row's owner and workstream are not values, so they say so and narrow nothing
        for line in (f'owner:"{HIDDEN_OWNER}"', f'workstream:"{HIDDEN_WS}"'):
            p = self.val(f"P.fl.parse({json.dumps(line)}, ROWS, CTX)")
            self.assertEqual(p["chips"], [])
            self.assertTrue(p["errors"])
            self.assertNotIn("Hidden", p["errors"][0]["msg"] .replace(HIDDEN_OWNER, "").replace(HIDDEN_WS, ""))
            self.assertEqual(len(self.ids(line)), total)

    def test_the_rows_carry_no_internal_flag_a_line_could_reach(self):
        # the published data holds no client_visible, archived or review column, so none of those is a value a line could find
        for table in ("actions", "raid", "decisions"):
            for r in self.val(f"DATA.{table}"):
                self.assertFalse({"client_visible", "archived", "internal_note", "not_reviewed", "reviewed"} & set(r), r)

    def test_a_line_that_is_safe_still_works(self):
        self.assertIn("PUB-A-101", self.ids("owner:\"Ana Lopez\""))
        self.assertEqual(self.ids("is:closed"), sorted(self.ids("is:closed")))
        self.assertIn("PUB-A-101", self.ids("is:open due:overdue"))
        self.assertNotIn("PUB-A-104", self.ids("is:open"))


if __name__ == "__main__":
    unittest.main()
