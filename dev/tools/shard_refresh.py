"""Refresh dev/tools/shard_times.txt from the real per-file times of a full run (development only; standard library only).

    python3 dev/tools/shard_refresh.py --durations DIR [--tests tests] [--out dev/tools/shard_times.txt]

DIR holds the tests/.durations file of each shard of one full run ("test_x.py seconds" a line, as dev/run_tests.py writes it).
A test file the run timed takes its new time (the slowest, if two shards timed it); one it did not time keeps its old line; a
line whose test file is gone is removed; the header comment is kept. The nightly runs this and uploads the result, so the
shards stay balanced without anyone editing the file by hand.

Exit 0: the file was written. Exit 2: no time was measured (nothing is changed; not checked is never "no change").

LIMIT: one run's times. A file that was slow once because the runner was busy is recorded as slow until the next night.
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
LINE = re.compile(r"^(test_\w+\.py) (\d+(?:\.\d+)?)\s*$")


def read_times(text):
    """{test file: seconds} from "name seconds" lines; comments, zero times and lines that do not read are left out."""
    out = {}
    for ln in text.splitlines():
        m = LINE.match(ln)
        if m and float(m.group(2)) > 0:
            out[m.group(1)] = float(m.group(2))
    return out


def combine(many):
    """One {file: seconds} from several: the slowest time of each file."""
    out = {}
    for times in many:
        for name, secs in times.items():
            out[name] = max(secs, out.get(name, 0.0))
    return out


def merge(old, new, existing):
    """The new table: only test files that exist; the measured time where there is one, else the old line."""
    out = {}
    for name in sorted(existing):
        if name in new:
            out[name] = round(new[name], 1) or 0.1
        elif name in old:
            out[name] = old[name]
    return out


def render(old_text, times):
    header = [ln for ln in old_text.splitlines() if ln.startswith("#")]
    return "\n".join(header + ["%s %s" % (n, ("%.1f" % s)) for n, s in sorted(times.items())]) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--durations", required=True, metavar="DIR")
    ap.add_argument("--tests", default=str(ROOT / "tests"))
    ap.add_argument("--out", default=str(ROOT / "dev" / "tools" / "shard_times.txt"))
    a = ap.parse_args(argv)
    found = sorted(p for p in Path(a.durations).rglob("*") if p.is_file())
    new = combine(read_times(p.read_text(encoding="utf-8", errors="replace")) for p in found)
    existing = {p.name for p in Path(a.tests).glob("test_*.py")}
    measured = set(new) & existing
    if not measured:
        print("Shard times: not checked (no measured time in %s); nothing changed" % a.durations)
        return 2
    out = Path(a.out)
    old_text = out.read_text(encoding="utf-8") if out.exists() else ""
    old = read_times(old_text)
    times = merge(old, new, existing)
    out.write_text(render(old_text, times), encoding="utf-8")
    print("Shard times: %d measured, %d kept, %d removed (%d files of durations read)"
          % (len(measured), len(times) - len(measured), len(set(old) - existing), len(found)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
