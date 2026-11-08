"""A claims registry (#233): each thing the Help, the product page or the published page text says the product has is tied to a proof.

A claim is a sentence (or a phrase) in a text file, plus ONE proof that the thing it describes exists and works. A word appearing
somewhere in the page's code is not a proof. The proofs are:
  component(name)      a component file is mounted: some other file of the page (not Help, not a test) imports it
  selector(pattern)    the page's code (outside Help) draws it: the pattern is found in a file that is not Help's own
  test(file, name)     a test in tests/ exercises it: the file defines a function of that name
A claim whose proof fails is reported with the claim and the file that makes it. The checks run on plain dicts of file text, so a test can
hand in a fixture instead of the real tree.
"""
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Claim:
    id: str
    text: str          # the words as shown (a plain substring of the file's text)
    file: str          # the file that says it, as the report names it
    proof: tuple       # ("component", "Picker") | ("selector", r"type=.search.") | ("test", "test_x.py", "test_name")


def component(name):
    return ("component", name)


def selector(pattern):
    return ("selector", pattern)


def test(file, name):
    return ("test", file, name)


def _imports(code, name):
    stem = re.escape(name)
    return re.search(r"""(?:from\s+|import\s+|require\(\s*)['"][^'"]*/%s(?:\.jsx?)?['"]""" % stem, code) is not None


def why_unbacked(claim, page, tests):
    """page: {path: code} of the page's own source with Help's files and the tests left out. tests: {file name: text} of tests/.
    Returns "" when the claim is backed, else the reason."""
    kind = claim.proof[0]
    if kind == "component":
        name = claim.proof[1]
        homes = [p for p in page if p.rsplit("/", 1)[-1].split(".")[0] == name]
        if not homes:
            return f"no component file {name}"
        if not any(_imports(code, name) for p, code in page.items() if p not in homes):
            return f"{name} exists but nothing mounts it (no page file imports it)"
        return ""
    if kind == "selector":
        pattern = claim.proof[1]
        return "" if any(re.search(pattern, code) for code in page.values()) else f"the page draws nothing matching {pattern}"
    if kind == "test":
        _, file, name = claim.proof
        if file not in tests:
            return f"no test file {file}"
        return "" if re.search(r"def %s\(" % re.escape(name), tests[file]) else f"{file} has no test {name}"
    return f"unknown proof kind {kind}"


def unbacked(claims, texts, page, tests):
    """Every failure as a line naming the claim and the file. A claim whose words are no longer in its file is stale, and also reported."""
    out = []
    for c in claims:
        if c.text not in texts.get(c.file, ""):
            out.append(f"claim {c.id!r} ({c.text!r}) is not in {c.file}: remove it from the registry")
            continue
        reason = why_unbacked(c, page, tests)
        if reason:
            out.append(f"unbacked claim {c.id!r}: {c.text!r} in {c.file}: {reason}")
    return out
