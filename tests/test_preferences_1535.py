"""Row 1535 step 1 (AP1 to AP3): the preference registry (src/clark/preferences.py).

Run: python3 -m unittest test_preferences_1535 (from tests/). Quick tier: no browser; it reads the page source and settings.py.
"""
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
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


if __name__ == "__main__":
    unittest.main()
