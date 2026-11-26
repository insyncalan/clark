"""The test-honesty script: three separate checks on the test files a change touches (development only; standard library only).

    python3 dev/tools/honesty_check.py --base BASE [--head HEAD] [--repo PATH] [--json]

1. No test deleted: every test function a touched test file held at the base is still there at the head (in that file, or
   new in another test file the change touches, so moving a test is not deleting it; a same-name test that file already
   held does not count). A moved file (git's rename detection) is compared with the file it was.
2. No new skip or xfail: a touched test file holds no more skip or expected-failure markers than it did at the base.
3. Assert count not lower: a touched test file holds no fewer asserts (assert statements and assert* calls) than at the base.

It reads the two commits with git and nothing else: no test is run, nothing is written, no model is asked. Exit 0: all three
pass. Exit 1: at least one fails (each is reported on its own line). Exit 2: it could not check (not checked is never a pass).

LIMIT: it counts, it does not judge. An assert swapped for a weaker one, a test body emptied but kept, or a skip written as an
early `return` passes here; the read is what catches those. A file moved and rewritten so far that git no longer pairs it
is a delete and an add: its tests must all be new in touched files, but its assert count is not compared.
"""
import argparse
import ast
import json
import subprocess
import sys

SKIPS = {"skip", "skipIf", "skipUnless", "expectedFailure", "skipTest", "SkipTest", "xfail", "skipif", "importorskip"}
CHECKS = (("deleted", "no test deleted"), ("skips", "no new skip or xfail"), ("asserts", "assert count not lower"))


class CannotCheck(Exception):
    pass


def tests_in(source):
    """The test functions of a file: "Class.test_x" for a method, "test_x" for a plain function."""
    out = set()
    tree = ast.parse(source)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            out.add(node.name)
        elif isinstance(node, ast.ClassDef):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)) and sub.name.startswith("test"):
                    out.add("%s.%s" % (node.name, sub.name))
    return out


def skips_in(source):
    """How many skip and expected-failure markers a file holds (decorators, self.skipTest, raise SkipTest, pytest marks)."""
    count = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Attribute) and node.attr in SKIPS:
            count += 1
        elif isinstance(node, ast.Name) and node.id in SKIPS:
            count += 1
    return count


def asserts_in(source):
    """How many asserts a file holds: assert statements and calls of a name that starts with "assert"."""
    count = 0
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Assert):
            count += 1
        elif isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if name.startswith("assert"):
                count += 1
    return count


def git(repo, *args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    if r.returncode:
        raise CannotCheck("git %s failed" % args[0])
    return r.stdout.decode("utf-8", "replace")


def is_test_file(path):
    return path.startswith("tests/") and path.endswith(".py")


def changed(repo, base, head):
    """[(status, path, path at the base)] for the files that differ between the merge base and the head. A moved file is one
    entry, status R, with the path it had."""
    mb = git(repo, "merge-base", base, head).strip()
    out = []
    for line in git(repo, "diff", "--name-status", "-M", mb, head).splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0][:1] == "R":
            out.append(("R", parts[2], parts[1]))
        elif len(parts) >= 2:
            out.append((parts[0][:1], parts[-1], parts[-1]))
    return mb, out


def check(repo, base, head="HEAD"):
    """The three checks as one result: {"ok", "files", "deleted", "skips", "asserts", "errors"}. Raises CannotCheck."""
    mb, files = changed(repo, base, head)
    touched = [(s, p, was) for s, p, was in files if is_test_file(p) or is_test_file(was)]
    result = {"ok": True, "files": sorted(p for _, p, _ in touched), "deleted": [], "skips": [], "asserts": [], "errors": []}
    before, after = {}, {}
    for status, path, was in touched:
        if status != "A":
            before[path] = git(repo, "show", "%s:%s" % (mb, was))
        if status != "D":
            after[path] = git(repo, "show", "%s:%s" % (head, path))
    old, new = {}, {}
    for path in sorted(set(before) | set(after)):
        try:
            src = before.get(path)
            old[path] = (tests_in(src), skips_in(src), asserts_in(src)) if src is not None else (set(), 0, 0)
        except (SyntaxError, ValueError):
            old[path] = (set(), 0, 0)            # the base did not parse: nothing to hold the head to
        try:
            src = after.get(path)
            new[path] = (tests_in(src), skips_in(src), asserts_in(src)) if src is not None else (set(), 0, 0)
        except (SyntaxError, ValueError):
            result["errors"].append("%s: does not parse" % path)
    for path in sorted(new):
        moved_in = set()                         # tests that are new in another touched file: moved there, not deleted
        for other in new:
            if other != path:
                moved_in |= new[other][0] - old[other][0]
        for name in sorted(old[path][0] - new[path][0] - moved_in):
            result["deleted"].append("%s: %s" % (path, name))
        if new[path][1] > old[path][1]:
            result["skips"].append("%s: %d -> %d" % (path, old[path][1], new[path][1]))
        if path in before and path in after and new[path][2] < old[path][2]:
            result["asserts"].append("%s: %d -> %d" % (path, old[path][2], new[path][2]))
    result["ok"] = not (result["deleted"] or result["skips"] or result["asserts"] or result["errors"])
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", default="HEAD")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    try:
        result = check(a.repo, a.base, a.head)
    except CannotCheck as exc:
        print("Test honesty: not checked (%s)" % exc)
        return 2
    if a.json:
        print(json.dumps(result, indent=1))
        return 0 if result["ok"] else 1
    for key, label in CHECKS:
        print("%s: %s" % (label, "FAIL" if result[key] else "pass"))
        for line in result[key]:
            print("  " + line)
    for line in result["errors"]:
        print("not checked: " + line)
    print("Test honesty: %s (%d test file%s touched)" % ("passed" if result["ok"] else "FAILED", len(result["files"]),
                                                        "" if len(result["files"]) == 1 else "s"))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
