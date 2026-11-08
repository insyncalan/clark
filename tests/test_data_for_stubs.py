"""A data_for stub given to a test server must take the archived keyword.

GET /api/data?project=X&archived=hide calls data_for(code, archived="hide") (server.py, the data route). A stub that takes only the
code (DATA.get, lambda code: ..., def read(self, code)) answers that read with "dict.get() takes no keyword arguments" and the page
draws its error, but only when the page happens to send the keyword, so the test passes or fails by timing.
Run: python3 dev/run_tests.py test_data_for_stubs
"""
import ast
import unittest
import warnings
from pathlib import Path

TESTS = Path(__file__).resolve().parent


def takes_archived(args):
    names = [a.arg for a in args.args + args.kwonlyargs]
    return "archived" in names or args.kwarg is not None


def bad_stubs(source, name="<test>"):
    """(line, what) for each `data_for=<stub>` in the source whose stub cannot take archived=."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(source, name)
    defs = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, []).append(node)
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for kw in node.keywords:
            if kw.arg != "data_for":
                continue
            v = kw.value
            if isinstance(v, ast.Lambda) and not takes_archived(v.args):
                found.append((v.lineno, "a lambda without archived"))
            elif isinstance(v, ast.Attribute) and v.attr == "get":
                found.append((v.lineno, "a dict's .get"))
            elif isinstance(v, (ast.Name, ast.Attribute)):
                n = v.id if isinstance(v, ast.Name) else v.attr
                for d in defs.get(n, []):
                    if not takes_archived(d.args):
                        found.append((v.lineno, f"{n}() without archived"))
    return found


class DataForStubs(unittest.TestCase):
    def test_the_check_sees_the_three_shapes(self):
        src = ("Running(data_for=DATA.get)\nRunning(data_for=lambda code: 1)\nRunning(data_for=lambda code, **kw: 1)\n"
               "def read(self, code): pass\nRunning(data_for=self.read)\n"
               "def ok(code, archived=None): pass\nRunning(data_for=ok)\n")
        self.assertEqual([w for _, w in bad_stubs(src)], ["a dict's .get", "a lambda without archived", "read() without archived"])

    def test_no_test_gives_a_server_a_data_for_that_cannot_take_archived(self):
        bad = []
        for path in sorted(TESTS.glob("*.py")):
            if path.name == Path(__file__).name:
                continue
            text = path.read_text(encoding="utf-8")
            bad += [f"{path.name}:{line} {what}" for line, what in bad_stubs(text, path.name)]
        self.assertEqual(bad, [], "each of these answers ?archived= with a TypeError: take archived=None")


if __name__ == "__main__":
    unittest.main()
