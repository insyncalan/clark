"""Row 1594: no test class is collected twice because a test file imports it by name.

unittest collects every TestCase subclass it finds in a module's namespace. So `from test_a import Browser` in test_b runs
Browser again in test_b. This scan reads tests/*.py with ast (nothing is imported or run) and fails on:

  * IMPORT: a module-level `from <test module> import <TestCase class that has tests>` (fix: `import <module> as _m` and
    write `_m.Class`; the class then runs once, in the file that defines it).

A second kind (a class that inherits tests and overrides nothing) is added in the next step of this row.
"""
import ast
import tempfile
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def _toplevel(body):
    for n in body:
        yield n
        if isinstance(n, (ast.If, ast.Try)):
            for sub in (n.body, n.orelse, *[h.body for h in getattr(n, "handlers", [])]):
                yield from _toplevel(sub)


def scan(tests_dir):
    """the by-name imports of test classes: a list of (module, class, count of tests, []) read from every tests_dir/*.py."""
    trees = {}
    for f in sorted(Path(tests_dir).glob("*.py")):
        try:
            trees[f.stem] = ast.parse(f.read_text(encoding="utf-8"))
        except (SyntaxError, ValueError):
            continue
    classes, raw, aliases, dels = {}, {}, {}, {}
    for m, tree in trees.items():
        classes[m], raw[m], aliases[m], dels[m] = {}, {}, {}, set()
        for n in _toplevel(tree.body):
            if isinstance(n, ast.ClassDef):
                classes[m][n.name] = n
            elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module in trees:
                for a in n.names:
                    raw[m][a.asname or a.name] = (n.module, a.name)
            elif isinstance(n, ast.Import):
                for a in n.names:
                    if a.name in trees:
                        aliases[m][a.asname or a.name] = a.name
            elif isinstance(n, ast.Delete):
                dels[m].update(t.id for t in n.targets if isinstance(t, ast.Name))

    def canon(k, seen=()):
        """follow a name a module only re-exports to the module that defines the class"""
        if k[0] in trees and k[1] not in classes[k[0]] and k[1] in raw[k[0]] and k not in seen:
            return canon(raw[k[0]][k[1]], seen + (k,))
        return k

    def resolve(m, e):
        if isinstance(e, ast.Name):
            if e.id in classes[m]:
                return (m, e.id)
            if e.id in raw[m]:
                return canon(raw[m][e.id])
        elif isinstance(e, ast.Attribute) and isinstance(e.value, ast.Name) and e.value.id in aliases[m]:
            return canon((aliases[m][e.value.id], e.attr))
        return None

    def own(node):
        tests, other = {}, set()
        for s in node.body:
            if isinstance(s, (ast.FunctionDef, ast.AsyncFunctionDef)):
                (tests.__setitem__(s.name, True) if s.name.startswith("test") else other.add("def:" + s.name))
            elif isinstance(s, ast.Assign):
                for t in s.targets:
                    if isinstance(t, ast.Name):
                        if t.id.startswith("test"):
                            tests[t.id] = not (isinstance(s.value, ast.Constant) and s.value.value is None)
                        else:
                            other.add(t.id)
            elif isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name):
                other.add(s.target.id)
            elif isinstance(s, (ast.For, ast.If, ast.With)):
                text = ast.unparse(s)
                other.add("<none-loop>" if "locals()" in text and "None" in text else "<dyn>")
        return tests, other

    memo = {}

    def info(k, stack=()):
        """(is a TestCase, the test names that run in the class, the names of the bases' tests)"""
        if k in memo:
            return memo[k]
        if k in stack or k[0] not in trees or k[1] not in classes[k[0]]:
            return (False, set())
        node = classes[k[0]][k[1]]
        is_tc, tests = False, set()
        for b in reversed(node.bases):
            if (isinstance(b, ast.Attribute) and b.attr in ("TestCase", "IsolatedAsyncioTestCase")) or (
                    isinstance(b, ast.Name) and b.id == "TestCase"):
                is_tc = True
                continue
            r = resolve(k[0], b)
            if r:
                got = info(r, stack + (k,))
                is_tc |= got[0]
                tests |= got[1]
        t, o = own(node)
        if "<none-loop>" in o:
            tests = set()
        for name, on in t.items():
            (tests.add if on else tests.discard)(name)
        memo[k] = (is_tc, tests)
        return memo[k]

    imports = []
    for m in trees:
        for local, (src, name) in ((l, canon(v)) for l, v in raw[m].items()):
            if local in dels[m] or src not in trees or name not in classes[src]:
                continue
            is_tc, tests = info((src, name))
            if is_tc and tests:
                imports.append((m, src + "." + name, len(tests), []))
    return imports


class NoDuplicateRuns(unittest.TestCase):
    def test_no_test_class_is_imported_by_name(self):
        words = ("Fix: import the module, not the class (`import test_x as _x`, then `_x.Class`), so the class runs once, "
                 "in the file that defines it.")
        self.assertEqual([], scan(TESTS), "a test class imported by name runs a second time in the importing file. " + words)

    def test_the_scan_sees_a_by_name_import(self):
        files = {
            "test_base.py": "import unittest\nclass Base(unittest.TestCase):\n    def test_a(self): pass\n",
            "test_by_name.py": "import unittest\nfrom test_base import Base\nclass Own(unittest.TestCase):\n    def test_b(self): pass\n",
            "test_by_module.py": "import unittest\nimport test_base as _b\nclass Own(unittest.TestCase):\n    def test_c(self): _b.Base\n",
        }
        with tempfile.TemporaryDirectory() as d:
            for name, text in files.items():
                (Path(d) / name).write_text(text, encoding="utf-8")
            imports = scan(d)
        self.assertEqual([("test_by_name", "test_base.Base")], [(m, c) for m, c, n, o in imports])


if __name__ == "__main__":
    unittest.main()
