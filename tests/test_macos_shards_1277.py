"""Row 1277, the four macOS-shard tests wait on a condition and never on a fixed sleep, pinned.

Run: python3 dev/run_tests.py test_macos_shards_1277
The four files are read as text and parsed (no browser). In the named test functions, and in every helper of the
same file they call (by name or as self.name), there is no call to time.sleep or sleep.
"""
import ast
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ONE = "test_the_dashboard_milestones_choice_and_widths_are_kept_under_msdash_and_leave_the_milestones_keys_alone"
FILES = {
    "test_drag_lost_capture_real_1214.py": None,       # None: every test_ function in the file
    "test_live_layout_e2e_1214.py": None,
    "test_table_columns.py": (ONE,),
    "test_section_drag_guards_1214.py": None,
}


def is_sleep(call):
    f = call.func
    return (isinstance(f, ast.Attribute) and f.attr == "sleep") or (isinstance(f, ast.Name) and f.id == "sleep")


def called_names(fn):
    for n in ast.walk(fn):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Name):
                yield f.id
            elif isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name) and f.value.id in ("self", "cls"):
                yield f.attr


def sleeps(name, wanted):
    tree = ast.parse((HERE / name).read_text(encoding="utf-8"), filename=name)
    defs = {}
    for n in ast.walk(tree):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(n.name, []).append(n)
    roots = [k for k in defs if (k in wanted if wanted else k.startswith("test_"))]
    found, seen, todo = [], set(), list(roots)
    while todo:
        k = todo.pop()
        if k in seen:
            continue
        seen.add(k)
        for fn in defs[k]:
            found += [(n.lineno, k) for n in ast.walk(fn) if isinstance(n, ast.Call) and is_sleep(n)]
            todo += [c for c in called_names(fn) if c in defs]
    return roots, sorted(set(found))


class NoSleepWaits(unittest.TestCase):
    def test_no_sleep_waits_in_the_four_shard_tests(self):
        for name, wanted in FILES.items():
            with self.subTest(file=name):
                roots, found = sleeps(name, wanted)
                self.assertTrue(roots, f"{name}: the test functions are found")
                self.assertEqual(found, [], "\n".join(f"{name}:{ln} sleeps in {fn}" for ln, fn in found))


if __name__ == "__main__":
    unittest.main()
