"""Row 654 part C: measured numbers for the whole-codebase review, one command, no browser (development only).

Run: python3 dev/tools/perf_baseline.py          # prints a table
     python3 dev/tools/perf_baseline.py --json   # the same as JSON

Measures: (1) the served page and the published page, in bytes and by part (style, script, data: pictures and fonts, the rest);
(2) the time to import clark.server in a fresh interpreter (best of 5) and the ten slowest modules, from `python -X importtime`;
(3) the time clark.page.page_html takes (best of 5). Findings that call code "slow" cite these numbers. Nothing is written.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
RUNS = 5
STYLE = re.compile(r"<style\b[^>]*>.*?</style\s*>", re.I | re.S)
SCRIPT = re.compile(r"<script\b[^>]*>.*?</script\s*>", re.I | re.S)
DATA_URI = re.compile(r"data:[a-z0-9.+/-]+;base64,[A-Za-z0-9+/=]+", re.I)


def parts(html):
    """Bytes of a page by part. data_uris sits inside style and script (and in head links), so it is reported as its own
    line and the parts are not meant to add up: `rest` is what is left after the style and script blocks."""
    b = len(html.encode("utf-8"))
    style = sum(len(m.encode("utf-8")) for m in STYLE.findall(html))
    script = sum(len(m.encode("utf-8")) for m in SCRIPT.findall(html))
    data = sum(len(m.encode("utf-8")) for m in DATA_URI.findall(html))
    return {"total": b, "style": style, "script": script, "rest": b - style - script, "data_uris": data}


def best_of(fn, runs=RUNS):
    times = []
    for _ in range(runs):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return min(times)


def import_once(module="clark.server"):
    subprocess.run([sys.executable, "-c", f"import {module}"], cwd=str(SRC), check=True, capture_output=True)


def slowest_imports(module="clark.server", n=10):
    """The n slowest modules by their own (self) microseconds, from -X importtime (stderr: 'import time: self | cumulative | name')."""
    p = subprocess.run([sys.executable, "-X", "importtime", "-c", f"import {module}"], cwd=str(SRC),
                       capture_output=True, text=True, check=True)
    rows = []
    for line in p.stderr.splitlines():
        m = re.match(r"import time:\s+(\d+) \|\s+(\d+) \| (\s*)(\S+)", line)
        if m:
            rows.append((int(m.group(1)), int(m.group(2)), m.group(4)))
    rows.sort(reverse=True)
    return [{"module": r[2], "self_ms": round(r[0] / 1000, 1), "cumulative_ms": round(r[1] / 1000, 1)} for r in rows[:n]]


def measure():
    sys.path.insert(0, str(SRC))
    from clark import page
    served = page.page_html()
    published = page.page_html(view=True)
    return {
        "page_served": parts(served),
        "page_published": parts(published),
        "import_server_ms": round(best_of(import_once) * 1000, 1),
        "page_html_ms": round(best_of(page.page_html) * 1000, 1),
        "slowest_imports": slowest_imports(),
    }


def render(m):
    out = []
    for key in ("page_served", "page_published"):
        out.append(f"{key}: " + ", ".join(f"{k} {v:,} B" for k, v in m[key].items()))
    out.append(f"import clark.server (best of {RUNS}): {m['import_server_ms']} ms")
    out.append(f"page_html() (best of {RUNS}): {m['page_html_ms']} ms")
    out.append("slowest imports by own time:")
    out += [f"  {r['self_ms']:>8} ms self {r['cumulative_ms']:>8} ms total  {r['module']}" for r in m["slowest_imports"]]
    return "\n".join(out)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    m = measure()
    print(json.dumps(m, indent=2) if "--json" in argv else render(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
