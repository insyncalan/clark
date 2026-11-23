"""Row 1535 step 1 (AP1 to AP3): the preference registry (src/clark/preferences.py).

Run: python3 -m unittest test_preferences_1535 (from tests/). Quick tier: no browser; it reads the page source and settings.py. Steps 2 onward bundle the page's stored-preference code with esbuild and run it in node
(skipped when node is not on the machine).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402
from clark import preferences  # noqa: E402

PAGE = ROOT / "src" / "clark" / "page" / "src"
Q = r"""["'`]"""
# A key is the text after "clark."; a template hole or a variable part becomes "*".
CLARK_LITERAL = re.compile(Q + r"clark\.([A-Za-z0-9_.\-]*(?:\$\{[^}]*\}[A-Za-z0-9_.\-]*)*)")
CALL = re.compile(r"\b(?:recall|remember|forget)\(\s*(" + Q + r")([^\"'`]+)\1")
DEFN = re.compile(r"\bconst\s+(?:\w*KEY|STORE|key|keyOf|keyFor)\b\s*=\s*(?:\([^)]*\)\s*=>\s*)?" + r"""(["'`])([^"'`]+)\1""")
DEFN_CONCAT = re.compile(r"""const key = \(\) => "(askChats\.)" \+""")
# Not preferences, or not a key: a prefix helper, and the one-time sentences in sessionStorage.
SKIP_FILES = {"remember.js", "prefsSync.js"}


def norm(text):
    return re.sub(r"\$\{[^}]*\}", "*", text)


def found_keys():
    """Every browser storage key the page source names, as `clark.<key>` with `*` for the part that varies."""
    out = {}
    for path in sorted(PAGE.rglob("*.js*")):
        if path.name in SKIP_FILES:
            continue
        text = path.read_text(encoding="utf-8")
        for m in CLARK_LITERAL.finditer(text):
            k = norm(m.group(1))
            k = k + "*" if k.endswith(".") else k   # a prefix: the part after it varies
            if k and k not in ("*",):
                out.setdefault("clark." + k, path.name)
        for rx in (CALL, DEFN):
            for m in rx.finditer(text):
                k = norm(m.group(2)).strip()
                if re.fullmatch(r"[A-Za-z][A-Za-z0-9_.*\-]*", k) and not k.startswith("clark"):
                    out.setdefault("clark." + k, path.name)
        if DEFN_CONCAT.search(text):
            out.setdefault("clark.askChats.*", path.name)
    return out


def python_setting_keys():
    text = (ROOT / "src" / "clark" / "settings.py").read_text(encoding="utf-8")
    return {"settings.json:" + m.group(1) for m in re.finditer(r'^[A-Z_]+ = "([a-z_]+)"\s*(?:#.*)?$', text, re.M)
            if m.group(1) not in ("settings",)}


def is_registered(key, registered):
    return key in registered or any(r.endswith("*") and key.startswith(r[:-1]) for r in registered) or any(
        key.startswith(r.split("*")[0]) and "*" in r and re.fullmatch(re.escape(r).replace(r"\*", r"[A-Za-z0-9_.\-]*"), key) for r in registered)


class Registry1535(unittest.TestCase):
    def test_registry_holds_every_audit_key(self):
        """AP1: every key of audit tables 1, 2 and 3 is in the registry."""
        have = preferences.keys()
        audit = [
            "app_settings.ask_enabled", "app_settings.theme", "app_settings.ask_instructions", "projects.layout_brand_review_gantt_client",
            "report_sections", "glance_tiles", "report_hidden", "source_folders", "saved_views",
            "settings.json:profile_name", "settings.json:profile_email", "settings.json:profile_alias", "settings.json:backups_kept",
            "settings.json:backup_copy_folder", "settings.json:ai_model", "settings.json:ai_claude_off", "settings.json:ai_chatgpt_on",
            "settings.json:ai_accepted", "ask_folders_all.json", "ask-commands/", "clark-brand.json", "excel-export-state.json",
            "clark.appearance", "clark.density", "clark.motion", "clark.single-keys", "clark.welcome", "clark.lastProject", "clark.peekWidth",
            "clark.askWidth", "clark.work.v1", "clark.cols.show.*", "clark.fviews", "clark.forder", "clark.fcore", "clark.tlZoom.*",
            "clark.tlScale.*", "clark.msv.*", "clark.msDet.*", "clark.msAll.*", "clark.msp.view", "clark.ucAll", "clark.recentTemplates",
            "clark.dragHintSeen", "clark.import.sheets", "clark.askChats.*", "clark.reader.name", "clark.reader.look",
        ]
        self.assertEqual([k for k in audit if k not in have], [])

    def test_unregistered_key_fails_build(self):
        """AP2: every storage key in the page and every settings.json key is registered; an unregistered one is caught."""
        found = found_keys()
        self.assertGreater(len(found), 30, "the scan found too few keys to be trusted")
        registered = preferences.keys()
        missing = {k: f for k, f in found.items() if not is_registered(k, registered)}
        self.assertEqual(missing, {}, "a storage key is not in src/clark/preferences.py")
        py = python_setting_keys()
        self.assertGreaterEqual(len(py), 9)
        self.assertEqual(sorted(k for k in py if k not in registered), [])
        # the check itself fails on a made-up key
        self.assertFalse(is_registered("clark.madeUpKey1535", registered))
        self.assertFalse(is_registered("settings.json:made_up_1535", registered))

    def test_registry_entries_state_scope(self):
        """AP3: each entry states its place and scope (and default, shape, migration); no key twice."""
        seen = set()
        for p in preferences.REGISTRY:
            self.assertIn(p.where, preferences.WHERES, p.key)
            self.assertIn(p.scope, preferences.SCOPES, p.key)
            for f in (p.default, p.shape, p.migrates):
                self.assertTrue(f and f.strip(), p.key)
            self.assertNotIn(p.key, seen)
            seen.add(p.key)
            if p.where == "browser":
                self.assertTrue(p.key.startswith("clark."), p.key)


ENTRY = ROOT / "tests" / "fixtures" / "prefs_node.js"
_BUNDLE = {}
# A browser store that holds `store` (a dict) in node, and prints what it holds afterwards with the probe's result.
PRELUDE = """
const __m = %s; globalThis.window = { localStorage: { getItem: (k) => (k in __m ? __m[k] : null), setItem: (k, v) => { __m[k] = String(v); },
  removeItem: (k) => { delete __m[k]; } } };
"""


def run_node(store, probe, prelude=None):
    """Run `probe` (JS using Q.board, Q.cols, Q.client, Q.remember) against a store; gives (result, store afterwards)."""
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        if "code" not in _BUNDLE:
            out = Path(tmp) / "p.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=Q", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={SRC / 'clark' / 'page' / 'src'}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
        script = Path(tmp) / "probe.js"
        script.write_text((prelude or PRELUDE % json.dumps(store)) + _BUNDLE["code"] + ";\nconst __r = (" + probe + ");\nconsole.log(JSON.stringify([__r, __m]));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        result, after = json.loads(done.stdout)
        return result, after


class Migration1535(unittest.TestCase):
    def test_old_version_value_migrated(self):
        """AP4: a published page's choice from an older version is carried forward by its step, not dropped; a newer one is left alone."""
        probe = """(() => {
          const steps = { 0: (o) => ({ ...o, group: o.oldGroup }) };
          const got = Q.client.migrate({ v: 0, oldGroup: "owner", type: "all" }, 1, steps);
          const none = Q.client.migrate({ v: 0, group: "owner" }, 1, {});
          const future = Q.client.migrate({ v: 9 }, 1, steps);
          const twice = Q.client.migrate({ v: 0, a: 1 }, 2, { 0: (o) => ({ ...o, b: 2 }), 1: (o) => ({ ...o, c: o.b + 1 }) });
          return { got, none, future, twice };
        })()"""
        r, _ = run_node({}, probe)
        self.assertEqual(r["got"], {"v": 1, "oldGroup": "owner", "group": "owner", "type": "all"})
        self.assertEqual(r["none"], {"v": 1, "group": "owner"})      # no step: carried as it is, nothing dropped
        self.assertIsNone(r["future"])
        self.assertEqual(r["twice"], {"v": 2, "a": 1, "b": 2, "c": 3})

    def test_newer_version_is_not_overwritten_by_save(self):
        """AP4: after a roll back, the page does not overwrite what a newer release kept."""
        newer = json.dumps({"v": 7, "keep": "me"})
        r, after = run_node({"clark.work.P1": newer}, 'Q.client.save("P1", Q.client.remember({type: "all", mode: "open", filters: {}, not: {}}, "workstream"))')
        self.assertEqual(after["clark.work.P1"], newer)
        r, after = run_node({"clark.work.P1": json.dumps({"v": 1})}, 'Q.client.save("P1", Q.client.remember({type: "all", mode: "open", filters: {}, not: {}}, "workstream"))')
        self.assertEqual(json.loads(after["clark.work.P1"])["v"], 1)
        self.assertIn("group", json.loads(after["clark.work.P1"]))

    def test_unknown_key_survives(self):
        """AP5: an unknown or retired key and an unknown field survive every write the page makes."""
        stored = {"clark.future.thing": "x", "clark.work.v1": json.dumps({"P1": {"view": "board", "later": {"a": 1}, "order": {"retiredGroup": ["a", "b"]}, "widths": {}}, "OLD": {"view": "table"}})}
        probe = """(() => {
          Q.remember.remember("peekless", 1); Q.remember.forget("peekless");
          Q.board.writeState("P1", { group: "owner" });
          Q.cols.writeChoice("work", "P1", ["item", "status", "owner"]);
          return Q.board.readState("P1").group;
        })()"""
        r, after = run_node(stored, probe)
        self.assertEqual(r, "owner")
        self.assertEqual(after["clark.future.thing"], "x")
        work = json.loads(after["clark.work.v1"])
        self.assertEqual(work["OLD"], {"view": "table"})
        self.assertEqual(work["P1"]["later"], {"a": 1})
        self.assertEqual(work["P1"]["order"]["retiredGroup"], ["a", "b"])
        self.assertEqual(work["P1"]["group"], "owner")
        self.assertEqual(work["P1"]["view"], "board")

    def test_unknown_column_id_survives(self):
        """AP6: an unknown column id stays in the kept choice (hidden, not drawn) when the person changes columns."""
        stored = {"clark.cols.show.work.P1": json.dumps(["item", "status", "retired_col", "owner"])}
        probe = """(() => {
          const before = Q.cols.readChoice("work", "P1");
          Q.cols.writeChoice("work", "P1", Q.cols.toggled("work", before, "due"));
          return { before, after: Q.cols.readChoice("work", "P1") };
        })()"""
        r, after = run_node(stored, probe)
        self.assertNotIn("retired_col", r["before"])
        self.assertNotIn("retired_col", r["after"])
        self.assertIn("due", r["after"])
        self.assertIn("retired_col", json.loads(after["clark.cols.show.work.P1"]))
        # picking the standard set again keeps the unknown id too (the key is not taken away)
        probe2 = 'Q.cols.writeChoice("work", "P1", Q.cols.standardIds("work"))'
        _, after2 = run_node(stored, probe2)
        self.assertIn("retired_col", json.loads(after2["clark.cols.show.work.P1"]))

    def test_changed_default_keeps_set_value(self):
        """AP7: when a release changes a default (the standard columns, the board's group), what a person set is read back unchanged."""
        stored = {"clark.cols.show.work.P1": json.dumps(["item", "status", "owner"]),
                  "clark.work.v1": json.dumps({"P1": {"view": "board", "group": "owner"}})}
        probe = """(() => {
          Q.cols.TABLE_COLUMNS.work.find((c) => c.id === "labels").standard = true;      // a release makes Labels standard
          Q.board.DEFAULT_STATE.group = "status"; Q.board.DEFAULT_STATE.view = "board";  // and changes the board's defaults
          return { cols: Q.cols.readChoice("work", "P1"), st: Q.board.readState("P1"), other: Q.cols.readChoice("work", "P2") };
        })()"""
        r, after = run_node(stored, probe)
        self.assertEqual(r["cols"], ["status", "item", "owner"])
        self.assertEqual((r["st"]["view"], r["st"]["group"]), ("board", "owner"))
        self.assertIn("labels", r["other"])                 # a person who never set it gets the new default
        self.assertEqual(after, stored)                     # reading changes nothing


# ===== Step 3 and step 6: the choices kept in the data folder (src/clark/preferences.py, stores/prefsSync.js) =====
STORE_JS = """
const mk = (init) => { const m = { ...init }; return { m, get length() { return Object.keys(m).length; }, key: (i) => Object.keys(m)[i] ?? null,
  getItem: (k) => (k in m ? m[k] : null), setItem: (k, v) => { m[k] = String(v); }, removeItem: (k) => { delete m[k]; } }; };
const blocked = () => { const f = () => { throw new Error("blocked"); }; return { get length() { f(); }, key: f, getItem: f, setItem: f, removeItem: f }; };
"""
CHOICES = {"clark.peekWidth": "512", "clark.askWidth": "640", "clark.work.v1": json.dumps({"P1": {"view": "board"}, "P2": {"view": "table"}}),
           "clark.cols.show.work.P1": json.dumps(["item", "owner"]), "clark.cols.show.work.P2": json.dumps(["item", "due"]),
           "clark.fviews": json.dumps({"P1": [{"id": "v1", "name": "Mine"}]}), "clark.askChats.P1": json.dumps([{"id": 1, "q": "Hello"}])}


def iife(body):
    """A probe: `body` (statements, ending in `return ...`) after the store helpers, as one expression."""
    return "(() => {" + STORE_JS + body + "})()"


class Folder1535(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = Path(self.tmp.name)
        self.prefs = preferences.Preferences(self.dir)

    def disk(self):
        f = self.dir / preferences.FILE
        return f.read_bytes() if f.exists() else None

    def page_values(self, httpd=None):
        """The values a page is given, read from the real page route of a server on a port of its own."""
        import http.client
        from clark import server as sv
        own = httpd is None
        httpd = httpd or sv.LocalServer((sv.HOST, 0), preferences=self.prefs)
        if own:
            threading.Thread(target=httpd.serve_forever, daemon=True).start()
            self.addCleanup(lambda: (httpd.shutdown(), httpd.server_close()))
        conn = http.client.HTTPConnection(sv.HOST, httpd.server_port, timeout=10)
        try:
            conn.request("GET", "/", headers={"Host": f"127.0.0.1:{httpd.server_port}"})
            html = conn.getresponse().read().decode("utf-8")
        finally:
            conn.close()
        m = re.search(r'<script type="application/json" id="clark-prefs">(.*?)</script>', html)
        return httpd.server_port, (json.loads(m.group(1)) if m else None), html


class DataFolder1535(Folder1535):
    def test_new_port_browser_profile_keeps_choices(self):
        """AP8: the choices of each project are in the data folder; a new port, a new browser and a new profile each start with an empty store and are given all of them."""
        status, body = self.prefs.save({"set": CHOICES})
        self.assertEqual(status, 200)
        seen = []
        for change in ("port", "browser", "profile"):
            port, doc, _ = self.page_values()                        # a server on a port of its own, the same data folder
            probe = iife("const s = mk({}); Q.sync.hydrate(s, %s); return s.m;" % json.dumps(doc["values"]))      # an empty store: the new browser or profile
            got, _ = run_node({}, probe)
            seen.append((port, got))
            self.assertEqual(got, CHOICES, change)
        self.assertEqual(len({p for p, _ in seen}), 3)
        self.assertEqual(json.loads(seen[0][1]["clark.work.v1"])["P2"], {"view": "table"})       # each project keeps its own

    def test_import_once_is_idempotent(self):
        """AP9: the browser's old values go into the folder once; a second run (2 runs) changes 1 thing, then nothing."""
        old = {"clark.peekWidth": "480", "clark.fviews": "[1]"}
        probe = iife("const s = mk(%s); return [Q.sync.importBodies(s, {imported: false, values: {}}), Q.sync.importBodies(s, {imported: true, values: {}})];" % json.dumps(old))
        (before, after), _ = run_node({}, probe)
        self.assertEqual(before, [{"import": old}])
        self.assertEqual(after, [])                        # the folder has taken them: the page offers nothing
        self.assertEqual(self.prefs.save(before[0])[1]["values"], old)
        first = self.disk()
        self.assertEqual(self.prefs.save({"import": {"clark.peekWidth": "999"}})[1]["values"], old)      # a second offer changes nothing
        self.assertEqual(self.disk(), first)
        self.assertEqual(self.prefs.get()[1]["imported"], True)

    def test_a_big_import_is_cut_into_requests_the_first_is_the_import_and_the_rest_are_sets(self):
        """AP9 (edges): the browser's values are sent in requests under the server's limit; only the first is the one-time import."""
        probe = iife("const s = mk({'clark.a': 'x'.repeat(600000), 'clark.b': 'y'.repeat(600000), 'clark.c': 'z'.repeat(2000000)}); "
                     "return Q.sync.importBodies(s, {imported: false}).map((b) => [Object.keys(b)[0], Object.keys(Object.values(b)[0])]);")
        r, _ = run_node({}, probe)
        self.assertEqual(r, [["import", ["clark.a"]], ["set", ["clark.b"]]])      # the 2 MB value is left in the browser

    def test_the_page_installs_the_sync_reads_the_folder_offers_the_browser_and_sends_each_later_change(self):
        """AP8/AP9 (the page's own start): with the page's data blocks present, the folder's value is written into the store, the browser's other value is offered once,
        and a later set and remove of a `clark.` key are sent (a key outside `clark.` and a reader's key are not); a refused send is tried again."""
        prelude = """
        const __m = {"clark.askWidth": "640", "other": "o"}; const __calls = []; const __timers = []; let __fail = true;
        class Storage { getItem(k) { return k in __m ? __m[k] : null; } setItem(k, v) { __m[k] = String(v); } removeItem(k) { delete __m[k]; }
          get length() { return Object.keys(__m).length; } key(i) { return Object.keys(__m)[i] ?? null; } }
        const __ls = new Storage();
        const __blocks = { "clark-prefs": JSON.stringify({ imported: false, values: { "clark.peekWidth": "300" } }), "clark-boot": JSON.stringify({ token: "test-run-value" }) };
        globalThis.document = { readyState: "complete", getElementById: (id) => (id in __blocks ? { textContent: __blocks[id] } : null), addEventListener() {} };
        globalThis.window = { document, Storage, localStorage: __ls, setTimeout: (f) => { __timers.push(f); return 1; }, addEventListener() {},
          fetch: async (u, o) => { __calls.push(JSON.parse(o.body)); return { ok: !(__fail && "set" in JSON.parse(o.body)) }; } };
        """
        probe = """(async () => {
          await new Promise((r) => setTimeout(r, 20));
          const first = JSON.parse(JSON.stringify(__calls)); const peek = __m["clark.peekWidth"];
          __ls.setItem("clark.x", "1"); __ls.setItem("other", "2"); __ls.setItem("clark.reader.name", "Reader One"); __ls.setItem("clark.y", "2"); __ls.removeItem("clark.y");
          __timers.splice(0).forEach((f) => f()); await new Promise((r) => setTimeout(r, 20));      // the send is refused
          __fail = false; __ls.setItem("clark.z", "3");
          __timers.splice(0).forEach((f) => f()); await new Promise((r) => setTimeout(r, 20));
          return { first, peek, later: __calls.slice(first.length) };
        })()"""
        import tempfile as _t
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        with _t.TemporaryDirectory() as tmp:
            run_node({}, "0")      # builds the bundle
            script = Path(tmp) / "probe.js"
            script.write_text(prelude + _BUNDLE["code"] + ";\n(" + probe + ").then((r) => console.log(JSON.stringify(r)));", encoding="utf-8")
            done = subprocess.run([node, str(script)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        r = json.loads(done.stdout)
        self.assertEqual(r["peek"], "300")                                  # the folder's value is in the store
        self.assertEqual(r["first"], [{"import": {"clark.askWidth": "640", "clark.peekWidth": "300"}}])      # the store is offered once (the server keeps the folder's own value for a key it has)
        self.assertEqual(r["later"][0], {"set": {"clark.x": "1"}, "remove": ["clark.y"]})
        self.assertEqual(r["later"][1], {"set": {"clark.x": "1", "clark.z": "3"}, "remove": ["clark.y"]})      # the refused send is kept and sent again with the newer change

    def test_a_second_storage_object_is_never_synced(self):
        """AP8 (edges): a set or remove on another Storage object (the tab's session store) is not sent to the folder; the real store still is."""
        prelude = """
        const __m = {}; const __calls = []; const __timers = [];
        class Storage { getItem(k) { return k in __m ? __m[k] : null; } setItem(k, v) { __m[k] = String(v); } removeItem(k) { delete __m[k]; }
          get length() { return Object.keys(__m).length; } key(i) { return Object.keys(__m)[i] ?? null; } }
        const __ls = new Storage(); const __ss = new Storage();
        const __blocks = { "clark-prefs": JSON.stringify({ imported: true, values: {} }), "clark-boot": JSON.stringify({ token: "test-run-value" }) };
        globalThis.document = { readyState: "complete", getElementById: (id) => (id in __blocks ? { textContent: __blocks[id] } : null), addEventListener() {} };
        globalThis.window = { document, Storage, localStorage: __ls, setTimeout: (f) => { __timers.push(f); return 1; }, addEventListener() {},
          fetch: async (u, o) => { __calls.push(JSON.parse(o.body)); return { ok: true }; } };
        """
        probe = """(async () => {
          await new Promise((r) => setTimeout(r, 20));
          __ss.setItem("clark.s", "1"); __ss.removeItem("clark.t");
          const queued = __timers.length; __timers.splice(0).forEach((f) => f()); await new Promise((r) => setTimeout(r, 20));
          const afterSession = JSON.parse(JSON.stringify(__calls));
          __ls.setItem("clark.x", "1"); __timers.splice(0).forEach((f) => f()); await new Promise((r) => setTimeout(r, 20));
          return { queued, afterSession, later: __calls.slice(afterSession.length) };
        })()"""
        node = shutil.which("node")
        if not node:
            self.skipTest("no node")
        with tempfile.TemporaryDirectory() as tmp:
            run_node({}, "0")      # builds the bundle
            script = Path(tmp) / "probe.js"
            script.write_text(prelude + _BUNDLE["code"] + ";\n(" + probe + ").then((r) => console.log(JSON.stringify(r)));", encoding="utf-8")
            done = subprocess.run([node, str(script)], capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stderr)
        r = json.loads(done.stdout)
        self.assertEqual(r["queued"], 0)                                    # nothing is waiting to be sent for the other store
        self.assertEqual(r["afterSession"], [])                             # and nothing was sent
        self.assertEqual(r["later"], [{"set": {"clark.x": "1"}}])           # the real store still sends

    def test_import_never_overwrites_a_kept_value_and_a_huge_value_stays_in_the_browser(self):
        """AP9 (edges): a value already in the folder wins over the browser's on the one-time import; one over the limit is not taken."""
        self.prefs.save({"set": {"clark.peekWidth": "300"}})
        got = self.prefs.save({"import": {"clark.peekWidth": "999", "clark.askWidth": "640", "clark.big": "x" * (preferences.VALUE_MAX + 1)}})[1]["values"]
        self.assertEqual(got, {"clark.peekWidth": "300", "clark.askWidth": "640"})

    def test_backup_and_restore_keep_preferences(self):
        """AP10: a backup puts preferences.json in the backups folder and the copy folder; a restore brings it back, never over a newer one."""
        from test_store_migration import make_v1
        from clark import backup, settings
        db = make_v1(self.dir)
        copy_to = Path(tempfile.mkdtemp(prefix="clark-test-copy-"))
        self.addCleanup(shutil.rmtree, copy_to, True)
        (self.dir / settings.FILE).write_text(json.dumps({"backup_copy_folder": str(copy_to)}), encoding="utf-8")
        self.prefs.save({"set": CHOICES})
        made = backup.make(db, self.dir / "backups", [], tag="daily")
        for _ in range(100):
            if (copy_to / preferences.FILE).exists():
                break
            time.sleep(0.05)
        for place in (self.dir / "backups", copy_to):
            self.assertEqual(json.loads((place / preferences.FILE).read_text(encoding="utf-8"))["values"], CHOICES, place)
        kept = self.disk()
        (self.dir / preferences.FILE).unlink()               # the data folder lost it
        backup.restore_path(db, Path(made).name, self.dir / "backups", [])
        self.assertEqual(self.disk(), (self.dir / "backups" / preferences.FILE).read_bytes())
        self.assertEqual(json.loads(self.disk())["values"], CHOICES)
        self.prefs.save({"set": {"clark.peekWidth": "700"}})  # a newer choice is never replaced by a restore
        newer = self.disk()
        backup.restore_path(db, Path(made).name, self.dir / "backups", [])
        self.assertEqual(self.disk(), newer)
        self.assertNotEqual(kept, newer)

    def test_blocked_store_draws_defaults(self):
        """AP11: with a blocked store nothing throws: nothing is hydrated, held or offered, and a change is simply not kept."""
        probe = iife("""const s = blocked();
          return [Q.sync.hydrate(s, {"clark.peekWidth": "9"}), Q.sync.held(s), Q.sync.importBodies(s, {imported: false})];""")
        r, _ = run_node({}, probe)
        self.assertEqual(r, [0, {}, []])
        # the page's own reads and writes (remember.js) with a store that throws: the fallback comes back, no error
        blocked_window = "globalThis.window.localStorage = { getItem() { throw new Error('x'); }, setItem() { throw new Error('x'); }, removeItem() { throw new Error('x'); } };"
        r2, _ = run_node({}, "(() => {" + blocked_window + "return [Q.remember.recall('peekWidth', 5), Q.remember.remember('peekWidth', 1), Q.board.readState('P1').view];})()")
        self.assertEqual(r2[:2], [5, False])

    def test_no_preference_content_leaves(self):
        """AP12: no value is logged, sent to a server other than this one, put in a published file; only the live page is given them, and reader keys never go."""
        import logging
        sentinel = "SENTINEL-WIDTH-7731"
        records = []
        handler = logging.Handler()
        handler.emit = lambda r: records.append(r.getMessage())
        root = logging.getLogger()
        old = root.level
        root.addHandler(handler); root.setLevel(1)
        try:
            self.prefs.save({"set": {"clark.askWidth": sentinel}})
            self.prefs.get()
            self.prefs.save({"reset": True})
            self.prefs.save({"set": {"clark.askWidth": sentinel}})
            from test_store_migration import make_v1
            from clark import backup
            backup.make(make_v1(self.dir), self.dir / "backups", [], tag="daily")
        finally:
            root.removeHandler(handler); root.setLevel(old)
        self.assertEqual([m for m in records if sentinel in m], [])
        src = ROOT / "src" / "clark"
        users = sorted(p.name for p in src.glob("*.py") if re.search(r"\bpreferences\.(?:Preferences|FILE|read|kept)|import preferences|, preferences,", p.read_text(encoding="utf-8")))
        self.assertEqual(sorted(set(users) - {"__main__.py", "backup.py", "preferences.py", "server.py"}), [])      # not the publishers, the exports or the log
        imports = sorted(p.name for p in PAGE.rglob("*.js*") if "prefsSync" in p.read_text(encoding="utf-8") and p.name != "prefsSync.js")
        self.assertEqual(imports, ["Preferences.jsx", "main.jsx"])      # the live page only (Settings, and the first thing it loads); a published page (view.jsx) never loads it
        _, doc, html = self.page_values()
        self.assertIn(sentinel, json.dumps(doc))             # the live page is given its own values
        reader = "(() => { const sent = []; const s = Q.sync.makeSender(async (b) => { sent.push(JSON.stringify(b)); return true; }, (f) => f()); s.note('clark.reader.name', 'Reader One'); return sent; })()"
        got, _ = run_node({}, reader)
        self.assertEqual(got, [])                          # a reader key is never queued
        self.assertEqual(self.prefs.save({"set": {"clark.reader.name": "Reader One", "clark.x y": "no"}})[1]["values"], {"clark.askWidth": sentinel})
        self.assertNotIn("clark.reader.name", json.dumps(got))

    def test_reset_all_preferences_only(self):
        """AP17 (the folder's half): a reset empties preferences.json and nothing else: the database and settings.json are the same bytes, and the old browser values are not taken back."""
        import sqlite3
        from test_store_migration import make_v1
        db = make_v1(self.dir)
        (self.dir / "settings.json").write_text('{"backups_kept": 21}\n', encoding="utf-8")
        self.prefs.save({"set": CHOICES})

        def rows():
            con = sqlite3.connect(str(db))
            try:
                return {t: con.execute(f"SELECT * FROM {t}").fetchall() for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")}
            finally:
                con.close()
        before, kept = rows(), (self.dir / "settings.json").read_bytes()
        self.assertEqual(self.prefs.save({"reset": True}), (200, {"ok": True, "imported": True, "values": {}}))
        self.assertEqual(rows(), before)
        self.assertEqual((self.dir / "settings.json").read_bytes(), kept)
        self.assertEqual(self.prefs.save({"import": CHOICES})[1]["values"], {})          # an old browser's values do not come back
        self.assertEqual(self.prefs.save({"set": {"clark.peekWidth": "5"}})[1]["values"], {"clark.peekWidth": "5"})      # and a new choice is kept again

    def test_tauri_new_port_keeps_preferences(self):
        """AP19: 3 starts on 3 different ports of the same data folder each give the page the same preferences."""
        self.prefs.save({"set": CHOICES})
        ports, docs = set(), []
        for _ in range(3):
            port, doc, _ = self.page_values()
            ports.add(port)
            docs.append(doc)
        self.assertEqual(len(ports), 3)
        self.assertTrue(all(d == docs[0] and d["values"] == CHOICES for d in docs))

    def test_new_container_keeps_preferences(self):
        """AP20: a new container is a new process on the same data folder (/data, a bind mount): the folder, not the process, holds them."""
        compose = (ROOT / "docker" / "compose.yaml").read_text(encoding="utf-8")
        self.assertIn("target: /data", compose)
        self.assertIn("--data /data", compose)
        self.prefs.save({"set": CHOICES})
        self.assertEqual(preferences.Preferences(self.dir).get()[1]["values"], CHOICES)      # a second process reading the same folder


class Route1535(Folder1535):
    def setUp(self):
        super().setUp()
        import http.client
        from clark import server as sv
        self.sv, self.http = sv, http.client
        self.httpd = sv.LocalServer((sv.HOST, 0), preferences=self.prefs)
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()
        self.addCleanup(lambda: (self.httpd.shutdown(), self.httpd.server_close()))

    def ask(self, method, body=None, token=True):
        conn = self.http.HTTPConnection(self.sv.HOST, self.httpd.server_port, timeout=10)
        try:
            conn.putrequest(method, "/api/preferences", skip_host=True, skip_accept_encoding=True)
            conn.putheader("Host", f"127.0.0.1:{self.httpd.server_port}")
            if token:
                conn.putheader(self.sv.TOKEN_HEADER, self.sv.TOKEN)
            raw = json.dumps(body).encode() if body is not None else None
            if raw is not None:
                conn.putheader("Content-Type", "application/json")
                conn.putheader("Content-Length", str(len(raw)))
            conn.endheaders(raw)
            r = conn.getresponse()
            data = r.read()
            return r.status, json.loads(data)
        finally:
            conn.close()

    def test_get_and_post_need_the_token_and_keep_unknown_keys(self):
        self.assertEqual(self.ask("GET", token=False)[0], 403)
        self.assertEqual(self.ask("POST", {"set": {"clark.future.thing": "x"}}, token=False)[0], 403)
        self.assertEqual(self.ask("POST", {"set": {"clark.future.thing": "x", "clark.peekWidth": "9"}})[0], 200)
        self.assertEqual(self.ask("POST", {"remove": ["clark.peekWidth"]})[1]["values"], {"clark.future.thing": "x"})
        self.assertEqual(self.ask("GET")[1]["values"], {"clark.future.thing": "x"})
        self.assertEqual(self.ask("POST", {"set": [1]})[0], 400)
        self.assertEqual(self.ask("POST", {})[0], 400)

    def test_a_file_that_cannot_be_read_is_never_replaced(self):
        (self.dir / preferences.FILE).write_text("{not json", encoding="utf-8")
        self.assertEqual(self.ask("POST", {"set": {"clark.peekWidth": "9"}})[0], 400)
        self.assertEqual(self.disk(), b"{not json")


if __name__ == "__main__":
    unittest.main()
