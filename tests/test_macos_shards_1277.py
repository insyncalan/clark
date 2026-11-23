"""Row 1539 / 1277: the four tests that failed on the macOS shards wait on a condition, never on a fixed sleep.

The files are read as text with ast; no browser is started."""
import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent

# file -> the test functions that must hold no time.sleep (None: every function in the file)
SHARD_TESTS = {
    "test_drag_lost_capture_real_1214.py": None,
    "test_live_layout_e2e_1214.py": None,
    "test_table_columns.py": {"test_the_dashboard_milestones_choice_and_widths_are_kept_under_msdash_and_leave_the_milestones_keys_alone"},
    "test_section_drag_guards_1214.py": None,
}


def is_sleep(node):
    f = node.func if isinstance(node, ast.Call) else None
    return isinstance(f, ast.Attribute) and f.attr == "sleep" and isinstance(f.value, ast.Name) and f.value.id == "time" \
        or isinstance(f, ast.Name) and f.id == "sleep"


def sleeps(name, only):
    tree = ast.parse((HERE / name).read_text(encoding="utf-8"), name)
    found, seen = [], set()
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)) and (only is None or fn.name in only):
            seen.add(fn.name)
            found += [(fn.name, n.lineno) for n in ast.walk(fn) if is_sleep(n)]
    return found, seen


class MacosShards(unittest.TestCase):
    def test_no_sleep_waits_in_the_four_shard_tests(self):
        for name, only in SHARD_TESTS.items():
            found, seen = sleeps(name, only)
            if only:
                self.assertEqual(seen, only, f"{name}: the named test function is not there")
            self.assertFalse(found, f"{name}: time.sleep in " + ", ".join(f"{fn} at line {ln}" for fn, ln in found))

    def test_the_check_sees_a_sleep(self):
        tree = ast.parse("import time\ndef t():\n    time.sleep(1)\n")
        self.assertEqual([n.lineno for n in ast.walk(tree) if is_sleep(n)], [3])


if __name__ == "__main__":
    unittest.main()
