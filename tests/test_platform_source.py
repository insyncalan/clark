"""#56: source rules that keep clark ready for Windows, checked on the Mac.

Run: python3 tests/test_platform_source.py
Over every .py file in src/ (the code clark ships; dev tools and tests may start programs):
- Only src/clark/platform.py may start a program or reach the system: no `subprocess`, `ctypes`, `os.startfile`,
  `os.system` or `os.popen`, and no "osascript" or "~/Library" text, anywhere else.
- Nowhere: `shell=True`, or a text-mode open() (or Path.open, read_text, write_text) without encoding="utf-8".
The encoding rule alone also covers every .py file in tests/ and dev/ (vendor/ is left out). Dev tools and tests may
still start programs, so the other rules stay with src/.
The rules are read from the syntax tree, so a word in a comment or a docstring doesn't count.
"""
import ast
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
ENCODING_ONLY = (ROOT / "tests", ROOT / "dev")           # also read for the encoding rule; vendor/ is not
SKIPPED_FOLDERS = {"node_modules", "vendor", "__pycache__"}
PLATFORM = Path("clark") / "platform.py"
SYSTEM_ALLOWED = {PLATFORM, Path("clark") / "update_helper.py"}      # the update helper (#109) runs standalone from the data folder, so it starts the new server itself
SYSTEM_MODULES = {"subprocess", "ctypes"}
SYSTEM_CALLS = {("os", "startfile"), ("os", "system"), ("os", "popen")}
SYSTEM_TEXT = ("osascript", "~/Library", "Library/Application Support")
TEXT_CALLS = {"open", "read_text", "write_text"}
NOT_TEXT_FILES = {"os", "tarfile", "zipfile", "gzip", "bz2", "lzma", "webbrowser"}     # their open() isn't text-mode open()


def _is_docstring(node, parents):
    parent = parents.get(node)
    return isinstance(parent, ast.Expr) and isinstance(parents.get(parent), (ast.Module, ast.FunctionDef,
                                                                               ast.AsyncFunctionDef, ast.ClassDef))


def _mode(call):
    """The mode given to an open() call, or "" if none (or not a plain string)."""
    for kw in call.keywords:
        if kw.arg == "mode":
            return kw.value.value if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str) else ""
    name = call.func.attr if isinstance(call.func, ast.Attribute) else getattr(call.func, "id", "")
    index = 0 if isinstance(call.func, ast.Attribute) and name == "open" else 1     # Path.open(mode), open(file, mode)
    if len(call.args) > index and isinstance(call.args[index], ast.Constant) and isinstance(call.args[index].value, str):
        return call.args[index].value
    return ""


def problems(source, rel, encoding_only=False):
    """Every rule `source` (the text of src/<rel>) breaks, as "rel:line: what" strings. With `encoding_only`, only the
    text-mode encoding rule is checked (for tests/ and dev/)."""
    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    system_allowed = encoding_only or Path(rel) in SYSTEM_ALLOWED
    out = []

    def say(node, what):
        out.append(f"{Path(rel).as_posix()}:{node.lineno}: {what}")

    for node in ast.walk(tree):
        if not system_allowed:
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[0] in SYSTEM_MODULES:
                        say(node, f"imports {a.name} (only platform.py may)")
            elif isinstance(node, ast.ImportFrom):
                if (node.module or "").split(".")[0] in SYSTEM_MODULES:
                    say(node, f"imports from {node.module} (only platform.py may)")
                if node.module == "os" and any(("os", a.name) in SYSTEM_CALLS for a in node.names):
                    say(node, "imports a program-starting call from os (only platform.py may)")
            elif isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                    and (node.value.id, node.attr) in SYSTEM_CALLS:
                say(node, f"uses os.{node.attr} (only platform.py may)")
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) and not _is_docstring(node, parents):
                for text in SYSTEM_TEXT:
                    if text in node.value:
                        say(node, f'names "{text}" (only platform.py may)')
                        break
        if not encoding_only and isinstance(node, ast.keyword) and node.arg == "shell" and not (
                isinstance(node.value, ast.Constant) and node.value.value is False):
            say(node.value, "passes shell= (start programs from an argument list)")
        if isinstance(node, ast.Call):
            func = node.func
            name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
            if name not in TEXT_CALLS or (isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name)
                                          and func.value.id in NOT_TEXT_FILES):
                continue                                       # os.open takes flags, tarfile.open a tar mode
            if name == "open" and "b" in _mode(node):
                continue
            enc = [kw.value for kw in node.keywords if kw.arg == "encoding"]
            if not enc or not (isinstance(enc[0], ast.Constant) and str(enc[0].value).lower().replace("-", "") == "utf8"):
                say(node, f'{name}() without encoding="utf-8"')
    return sorted(out, key=lambda s: int(s.split(":")[1]))


def tree_problems(src=SRC):
    out = []
    for path in sorted(Path(src).rglob("*.py")):
        rel = path.relative_to(src)
        out += problems(path.read_text(encoding="utf-8"), rel)
    return out


def encoding_problems(roots=ENCODING_ONLY):
    """The encoding rule over every .py file under `roots` (not in vendor/, node_modules/ or __pycache__/)."""
    out = []
    for root in roots:
        for path in sorted(Path(root).rglob("*.py")):
            if SKIPPED_FOLDERS & set(path.relative_to(root).parts):
                continue
            out += [f"{root.name}/{line}" for line in
                    problems(path.read_text(encoding="utf-8"), path.relative_to(root), encoding_only=True)]
    return out


class Source(unittest.TestCase):
    def test_src_keeps_the_rules(self):
        self.assertTrue((SRC / PLATFORM).is_file())
        self.assertEqual(tree_problems(), [])

    def test_tests_and_dev_name_utf8_for_text_files(self):
        for root in ENCODING_ONLY:
            self.assertTrue(root.is_dir(), root)
        self.assertEqual(encoding_problems(), [])


BAD_TEXT = '''import subprocess
import tarfile
open("a.txt")
Path("a").read_text()
'''
GOOD_OTHER = '''tarfile.open(fileobj=x, mode="r:gz")
os.system("ls")
run(["ls"], shell=True)
open("a.bin", "rb")
'''


class TheChecker(unittest.TestCase):
    """The checker finds each kind of break, and lets the allowed forms through."""

    BAD = '''import subprocess
import ctypes.util
from subprocess import run
from os import startfile
import os
os.startfile("a")
os.system("ls")
x = "osascript -e 'beep'"
y = "~/Library/Application Support/clark"
run(["ls"], shell=True)
open("a.txt")
open("a.txt", "w")
open("a.txt", encoding="latin-1")
Path("a").read_text()
Path("a").write_text("x")
Path("a").open("r")
'''
    GOOD = '''"""Docstrings may say osascript, subprocess and ~/Library."""
import os
from pathlib import Path
# a comment saying osascript
open("a.txt", encoding="utf-8")
open("a.bin", "rb")
open("a.bin", mode="wb")
Path("a").open("rb")
Path("a").read_text(encoding="UTF-8")
Path("a").write_text("x", encoding="utf-8")
Path("a").read_bytes()
os.open("a", os.O_RDONLY)
run(["ls"], shell=False)
'''

    def test_each_break_is_found(self):
        got = problems(self.BAD, Path("clark") / "pages.py")
        self.assertEqual([g.split(": ", 1)[0] for g in got], [f"clark/pages.py:{n}" for n in
                                                              (1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16)])
        self.assertIn('clark/pages.py:10: passes shell= (start programs from an argument list)', got)
        self.assertIn('clark/pages.py:13: open() without encoding="utf-8"', got)

    def test_allowed_forms_pass(self):
        self.assertEqual(problems(self.GOOD, Path("clark") / "pages.py"), [])

    def test_platform_py_may_reach_the_system_but_not_skip_utf8(self):
        got = problems(self.BAD, PLATFORM)
        self.assertEqual([g.split(": ", 1)[0] for g in got], [f"clark/platform.py:{n}" for n in (10, 11, 12, 13, 14, 15, 16)])

    def test_encoding_only_ignores_the_other_rules_and_binary_or_archive_opens(self):
        code = BAD_TEXT + GOOD_OTHER
        got = problems(code, Path("t.py"), encoding_only=True)
        self.assertEqual(got, ["t.py:3: open() without encoding=\"utf-8\"", "t.py:4: read_text() without encoding=\"utf-8\""])

    def test_encoding_problems_skip_vendor_and_node_modules(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "dev"
            for folder in ("tools", "vendor", "tiptap/node_modules/x"):
                (root / folder).mkdir(parents=True)
                (root / folder / "m.py").write_text('open("a.txt")\n', encoding="utf-8")
            self.assertEqual(encoding_problems([root]), ["dev/tools/m.py:1: open() without encoding=\"utf-8\""])

    def test_the_whole_tree_is_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "clark" / "page").mkdir(parents=True)
            (Path(tmp) / "clark" / "page" / "deep.py").write_text("import subprocess\n", encoding="utf-8")
            self.assertEqual(tree_problems(tmp), ["clark/page/deep.py:1: imports subprocess (only platform.py may)"])


if __name__ == "__main__":
    unittest.main()
