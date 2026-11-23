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
SKIP_FILES = {"remember.js"}


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


def run_node(store, probe):
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
        script.write_text(PRELUDE % json.dumps(store) + _BUNDLE["code"] + ";\nconst __r = (" + probe + ");\nconsole.log(JSON.stringify([__r, __m]));", encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
