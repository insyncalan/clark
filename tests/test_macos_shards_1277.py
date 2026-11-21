"""Row 1277 AP5: the four macOS-shard tests wait on the end state, never on a sleep.
Run: python3 dev/run_tests.py test_macos_shards_1277
The CI run id for shards 2/6, 5/6 and 6/6 is evidence from CI and is not checked here."""
import ast
import unittest

from _paths import ROOT

# file -> the test functions (or whole classes' tests, when None) that the shards run
FOUR = {
    "test_drag_lost_capture_real_1214.py": None,
    "test_live_layout_e2e_1214.py": None,
    "test_table_columns.py": ["test_the_dashboard_milestones_choice_and_widths_are_kept_under_msdash_and_leave_the_milestones_keys_alone"],
    "test_section_drag_guards_1214.py": None,
}


def sleeps(path, only):
    """Lines of every call to sleep(...) (time.sleep or a bare sleep) inside the named functions, or the whole file."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    scopes = [tree] if only is None else [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name in only]
    found = []
    for scope in scopes:
        for n in ast.walk(scope):
            if isinstance(n, ast.Call):
                f = n.func
                if (isinstance(f, ast.Attribute) and f.attr == "sleep") or (isinstance(f, ast.Name) and f.id == "sleep"):
                    found.append(n.lineno)
    return found, len(scopes)


class MacosShards1277(unittest.TestCase):
    def test_no_sleep_waits_in_the_four_shard_tests(self):
        for name, only in FOUR.items():
            with self.subTest(file=name):
                path = ROOT / "tests" / name
                found, scopes = sleeps(path, only)
                self.assertEqual(scopes, 1 if only is None else len(only), f"{name}: the named tests exist")
                self.assertEqual(found, [], f"{name}: sleep waits at these lines")

    def test_the_finder_sees_a_sleep(self):
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "t.py"
            p.write_text("import time\ndef test_a():\n    time.sleep(1)\ndef test_b():\n    pass\n")
            self.assertEqual(sleeps(p, None)[0], [3])
            self.assertEqual(sleeps(p, ["test_a"])[0], [3])
            self.assertEqual(sleeps(p, ["test_b"])[0], [])


if __name__ == "__main__":
    unittest.main()
