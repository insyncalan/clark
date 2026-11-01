"""Run clark's test files in parallel and report each one (development only; standard library only).

    python3 dev/run_tests.py                       # every test file, the newest Python
    /usr/bin/python3 dev/run_tests.py              # Python 3.9, the oldest supported
    python3 dev/run_tests.py test_layout           # the test files whose name contains it
    python3 dev/run_tests.py test_layout.LayoutTest.test_line_endings_are_lf_except_cmd   # one class or test
    python3 dev/run_tests.py --push origin/main    # before an ordinary push: the quick tier and the browser files reached

Run: python3 dev/run_tests.py [-j N] [--quick] [--changed [BASE]] [--push BASE] [--deep] [--list] [--flaky]
                              [--repeat N [--stress N]] [--file-timeout S] [--rerun-max N] [--shard I/N] [--max-fail N]
                              [name ...]
  name       only the test files whose name contains it (e.g. "vendor" runs the three test_vendor_ files); a dotted name
             (test_layout.LayoutTest or test_layout.LayoutTest.test_x) runs just that class or test
  -j N       how many files run at once (default: half the processor cores, at least 2)
  --quick    only the quick tier: the files that never start Chrome, read from the files themselves (dev/tools/run_support.py)
  --changed  only the test files that can reach a file changed since BASE (default: origin/main; the working tree and
             untracked files count). A test file is reached when it names a changed module of src/clark/ or dev/tools/
             (an import, or a string such as "esbuild.py"), directly or through a test helper it names (tests/_paths.py),
             or is itself the changed file; test_<name>.py is reached by <name>.py. A change to the rules, the settings,
             the workflows, the vendored libraries, guarded files, the runner (dev/run_tests.py, dev/tools/run_support.py),
             or a file this list doesn't know runs everything. Any change also runs tests/test_no_real_names.py (it reads
             every tracked file, documents included), and a change to a document also runs the test files that name it
             (by file name, e.g. the reuse-record test names the reuse record); a documents-only change runs just
             those. It never replaces the full run (CI on the pull request is the gate).
  --push BASE
             the run before an ordinary push: the quick tier, plus the browser files the change since BASE reaches
             (--changed BASE). Use origin/main, never a stale local main
  --deep     with --changed or --push: follow a changed module through the modules that import it too
  --list     print the test files that would run and stop
  --flaky    list the files that failed under load and passed alone (tests/.flaky.jsonl), most often first, and stop
  --repeat N run each file N times side by side (-j at a time), with no re-run alone, and report each file's passes under
             load: the proof that a flaky file is steady
  --stress N with --repeat: N processes spin the processor meanwhile, so a fast laptop is as slow as a CI runner
  --file-timeout S
             stop a test file that runs longer than S seconds (default 900, or CLARK_FILE_TIMEOUT; 0: never): it fails as
             TIMEOUT, and it and everything it started are stopped through its own process group
  --shard I/N
             run only shard I of N (1 to N) of the files chosen by the other options. Every file is in exactly one shard.
             They are balanced greedily, slowest first, by the times in dev/tools/shard_times.txt (read from a real run; a
             file it doesn't list counts as 30 s), never by this machine's last run, so every machine, and every CI job,
             computes the same split. Print one with --list.
  --max-fail N
             once N files have failed, start no more (the ones running finish) and report: a machine where everything
             fails says so in minutes, not at the job's time limit (default 0: no limit; CI passes 8)
  --rerun-max N
             re-run failures alone only when at most N files failed (default 15, or CLARK_RERUN_MAX). More than that is not
             load: something is broken for the whole machine

#70: copied from creaite v2.6.11 `dev/tools/run_tests.py` (BL-246, BL-247, #89) and adapted; the reuse row is in
the reuse record. Each test file runs in a process of its own (`python -m unittest <module>`, from tests/, with
tests/, src/, dev/tools/ and vendor/ on PYTHONPATH, as #28's in-process runner put them on sys.path), with a private
TMPDIR (/tmp/clark-test-run-<pid>/<n>) removed when the file ends. The slowest files start first, and the files that failed last
creaite: a file that fails under load and passes alone counts as passing; it is named as such and logged). Exits 1 if
any file still fails, printing the end of its output, or if no test ran. The last line is the summary, e.g.
"Python 3.9.6: pass, 97 tests in 1.3 s".

Left out from creaite: `--clean` and its orphaned live server and Chrome clean-up, `--update-snapshots`, the machine-wide
Chrome cap (here at most CHROME_AT_ONCE browser files at once in one run), the vault leak warning (BL-172), the stale page
check (split_dashboard) and SLOW_FILES: all for creaite's vault, pages and browser files.
"""
import argparse
import ast
import functools
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
TOOLS = ROOT / "dev" / "tools"
OLDEST = (3, 9)
sys.path.insert(0, str(TOOLS))
import run_support as support  # noqa: E402

PATHS = (TESTS, ROOT / "src", TOOLS, ROOT / "vendor")   # each test file's PYTHONPATH (#28's sys.path, in its order)
TIMES = TESTS / ".durations"          # last run's time per file, so the slowest start first (git-ignored)
LAST_FAILED = TESTS / ".last-failed"  # the files that failed in their last run, one per line: they start first next time (git-ignored)
SHARD_TIMES = TOOLS / "shard_times.txt"   # "test_x.py seconds" from a real run (committed), for --shard
SHARD_DEFAULT = 30                    # seconds assumed for a test file the times don't list
FLAKY = TESTS / ".flaky.jsonl"        # one line each time a file failed under load and passed alone (git-ignored)
REPO = ROOT
# A change here can reach any test: the rules, the settings, the workflows, the vendored libraries, the runner itself.
EVERYTHING = ("VERSION", "docs/RULES.md", ".claude/", ".github/", "vendor/", ".gitattributes",
              "dev/run_tests.py", "dev/tools/run_support.py", "dev/tools/shard_times.txt")
# The copies here of creaite's guarded files (docs/RULES.md); a change to one runs everything. #31 and #33 land these
# (the store, its schema and history, the server); listing a path that is not on main yet is fine. The workflow is already
# covered by EVERYTHING (.github/).
GUARDED = ("src/clark/store.py", "src/clark/schema.sql", "src/clark/history.py", "src/clark/server.py",
           ".github/workflows/tests.yml",
           # the update trust chain (#282): the pinned key, the signature check, the vendored verifier, the helper, the installer
           "src/clark/updates.py", "vendor/ed25519_verify/", "src/clark/update_helper.py", "src/clark/update_install.py",
           "dev/tools/sign_release.py")
DOCUMENTS = ("docs/",)                # and any *.md: these reach only the tests that name them (see `guard_tests`)
NAMES_GUARD = "test_no_real_names"    # reads every tracked file, so any change runs it
FILE_TIMEOUT = float(os.environ.get("CLARK_FILE_TIMEOUT") or 900)   # seconds; 0 means no limit (see --file-timeout)
RERUN_MAX = int(os.environ.get("CLARK_RERUN_MAX") or 15)            # more failures than this are not re-run alone
CHROME_AT_ONCE = 3                    # browser files at once in one run (creaite: about 3 on the machine)
TIMED_OUT = -1000                     # the exit code a file gets when it was stopped for running too long
CI = bool(os.environ.get("GITHUB_ACTIONS"))   # on a runner, print a failure's output as it happens (folded), not only at the end


# ===== #89 (CI shards) (creaite) =====
def shard_arg(text):
    """'I/N' as (I, N) with 1 <= I <= N, or an argparse error."""
    m = re.fullmatch(r"(\d+)/(\d+)", text.strip())
    if not m or not 1 <= int(m.group(1)) <= int(m.group(2)):
        raise argparse.ArgumentTypeError(f"{text!r}: expected I/N with 1 <= I <= N (for example 2/3)")
    return int(m.group(1)), int(m.group(2))


def shard_weights():
    """{test file name: seconds} from dev/tools/shard_times.txt (empty when the file is missing). clark's files take
    well under a second, so the seconds may have decimals (creaite's are whole)."""
    out = {}
    if SHARD_TIMES.exists():
        for ln in SHARD_TIMES.read_text(encoding="utf-8").splitlines():
            name, _, secs = ln.partition(" ")
            if name and not name.startswith("#") and re.fullmatch(r"\d+(\.\d+)?", secs.strip()):
                out[name] = float(secs)
    return out


def shard(files, index, count, weights=None):
    """The files of shard `index` (1-based) of `count`. Greedy, slowest first, each to the lightest shard so far; ties go
    to the lowest shard and the name, so the split depends only on the names and the weights. Every file is in exactly one
    shard, and the same file list gives the same split on every machine."""
    weights = shard_weights() if weights is None else weights
    load, mine = [0] * count, []
    for f in sorted(files, key=lambda f: (-weights.get(f.name, SHARD_DEFAULT), f.name)):
        k = load.index(min(load))
        load[k] += max(weights.get(f.name, SHARD_DEFAULT), 0.01)   # a 0 s file still counts, so files spread out
        if k == index - 1:
            mine.append(f)
    return sorted(mine, key=lambda f: f.name)


def apply_shard(files, spec):
    """`files` narrowed to shard `spec` ((I, N) or None for all), saying so."""
    if not spec:
        return files
    mine = shard(files, *spec)
    print(f"--shard {spec[0]}/{spec[1]}: {len(mine)} of {len(files)} test files.", flush=True)
    return mine


def last_failed():
    """The set of file names that failed in their last run."""
    return set(LAST_FAILED.read_text(encoding="utf-8").split()) if LAST_FAILED.exists() else set()


def remember_failed(ran, failed):
    """Keep the failed file names: those of the files just run replaced by `failed`, the others kept (a partial run
    doesn't forget a failure it didn't re-check)."""
    keep = (last_failed() - set(ran)) | set(failed)
    try:
        LAST_FAILED.write_text("".join(f"{n}\n" for n in sorted(keep)), encoding="utf-8")
    except OSError:
        pass                              # a read-only checkout loses only the ordering


# ===== end #89 =====


# ===== --changed (creaite, adapted to clark's folders) =====
def changed_paths(base):
    """Files changed since `base` (committed, staged, edited) and untracked ones, as repo-relative paths."""
    def git(*args):
        """The lines git prints."""
        r = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True)
        if r.returncode:
            raise SystemExit(f"git {' '.join(args)} failed: {r.stderr.strip()} (is {base!r} a branch or commit?)")
        return [x for x in r.stdout.splitlines() if x]
    mb = git("merge-base", "HEAD", base)
    return sorted(set(git("diff", "--name-only", mb[0] if mb else base)) | set(git("ls-files", "-o", "--exclude-standard")))


def _module_name(rel):
    """The name clark's code is imported by, from its path under src/ ("clark/server.py" is clark.server)."""
    parts = Path(rel).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


@functools.lru_cache(maxsize=None)
def module_paths(repo=REPO):
    """{module name: file} over clark's code (as imported: clark, clark.server), the dev tools and the tests."""
    repo = Path(repo)
    mods = {_module_name(p.relative_to(repo / "src")): p for p in sorted((repo / "src").glob("clark/**/*.py"))}
    for pat in ("dev/tools/*.py", "tests/*.py"):
        mods.update({p.stem: p for p in sorted(repo.glob(pat))})
    return mods


def _named(node, package):
    """The modules an import names: `from clark import server` names clark and clark.server. `package` is the importing
    module's package, for a relative import inside src/clark/."""
    if isinstance(node, ast.Import):
        bases, leaves = [a.name for a in node.names], []
    else:
        base = node.module or ""
        if node.level:
            up = package.split(".")[:max(0, len(package.split(".")) - node.level + 1)]
            base = ".".join(up + ([base] if base else []))
        bases, leaves = [base], [f"{base}.{a.name}" for a in node.names]
    out = set(leaves)
    for b in bases:
        bits = b.split(".")
        out.update(".".join(bits[:i]) for i in range(1, len(bits) + 1))
    return out


@functools.lru_cache(maxsize=None)
def module_graph(repo=REPO):
    """{module: set of modules it uses} over clark's code, the tools and the tests. A module is used when the file imports
    it or runs it by name (a string such as "esbuild.py"); words in comments and messages don't count (creaite)."""
    mods = module_paths(repo)
    by_stem = {}
    for m in mods:
        by_stem.setdefault(m.split(".")[-1], set()).add(m)
    graph = {}
    for m, p in mods.items():
        package = m if p.name == "__init__.py" else m.rpartition(".")[0]
        used = set()
        for n in ast.walk(ast.parse(p.read_text(encoding="utf-8", errors="replace"))):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                used |= _named(n, package)
            elif isinstance(n, ast.Constant) and isinstance(n.value, str) and ".py" in n.value:
                for stem in re.findall(r"([A-Za-z_]\w*)\.py\b", n.value):
                    used |= by_stem.get(stem, set())
        graph[m] = (used & set(mods)) - {m}
    return graph


def changed_roots(paths):
    """(the modules that changed, or None and the reason when the change can reach any test)."""
    roots = set()
    for p in paths:
        if any(p == e or p.startswith(e) for e in EVERYTHING + GUARDED):
            return None, f"{p} can reach any test"
        if is_document(p):
            continue                      # documents reach no module (guard_tests adds the tests that read them)
        folder, _, name = p.rpartition("/")
        if p.startswith("src/clark/") and p.endswith(".py"):
            roots.add(_module_name(p[len("src/"):]))
        elif folder in ("dev/tools", "tests") and name.endswith(".py"):
            roots.add(name[:-len(".py")])
        else:
            return None, f"{p} can reach any test (nothing says which tests read it)"
    return roots, ""


def reach(roots, deep=False, repo=REPO):
    """The modules that use one of `roots`. Quick (the default): the modules that name a changed module, and anything
    that names a changed helper (a tests/ module that isn't a test file, such as _paths). Deep: through clark's own
    modules and the tools too (creaite)."""
    graph = module_graph(repo)
    reached = set(roots) | {"test_" + r.split(".")[-1] for r in roots if "test_" + r.split(".")[-1] in graph}
    todo = list(reached)
    helpers = {m for m, p in module_paths(repo).items() if p.parent.name == "tests" and not m.startswith("test_")}
    while todo:
        cur = todo.pop()
        for m, used in graph.items():
            if cur in used and m not in reached:
                reached.add(m)
                if deep or m in helpers or cur in helpers or cur in roots and m.startswith("test_"):
                    todo.append(m)
    return reached


def is_document(p):
    return p.endswith(".md") or p.startswith(DOCUMENTS)


def guard_tests(files, paths):
    """The stems of the test files a change reaches by what they read rather than what they import: test_no_real_names
    (it reads every tracked file, so any change runs it) and, for a changed document, every test file that names the
    document by its file name (the reuse-record test names the reuse record). Without this a documents-only change
    would run nothing, and a real name added to a document would pass the local run."""
    if not paths:
        return set()
    names = {Path(p).name for p in paths if is_document(p)}
    found = {f.stem for f in files if f.stem == NAMES_GUARD}
    if names:
        for f in files:
            text = f.read_text(encoding="utf-8", errors="replace")
            if any(n in text for n in names):
                found.add(f.stem)
    return found


def choose(files, paths, deep=False, repo=None, since="BASE"):
    """(the test files that can reach `paths`, why); the whole list when the change can reach any test. `repo`: the
    folder whose modules count (default: this one)."""
    roots, reason = changed_roots(paths)
    if roots is None:
        return list(files), reason
    extra = guard_tests(files, paths)
    if not roots and not extra:
        return [], "nothing that a test reads has changed"
    reached = (reach(roots, deep, repo or REPO) if roots else set()) | extra
    plural = "s" if len(paths) != 1 else ""
    what = ", ".join(sorted(roots)) if roots else "documents only"
    if extra:
        what += f"; also {', '.join(sorted(extra))}"
    return [f for f in files if f.stem in reached], f"{len(paths)} changed file{plural} since {since}: {what}"


def select(files, base, deep=False):
    """(the test files that can reach what changed since `base`, why) (creaite)."""
    return choose(files, changed_paths(base), deep, since=base)


def for_push(files, base, deep=False):
    """--push BASE: the quick tier, and the browser files the change since BASE reaches. (files, why)."""
    quick = [f for f in files if not support.is_chrome(f)]
    reached, why = select(files, base, deep)
    browser = [f for f in reached if support.is_chrome(f)]
    return sorted(set(quick) | set(browser)), f"{len(quick)} quick, {len(browser)} browser ({why})"


# ===== end --changed =====


def failed_tests(out):
    """The test names a unittest run reports as FAIL or ERROR, in order (e.g. "Class.test_x")."""
    names = []
    for m in re.finditer(r"^(?:FAIL|ERROR): (\w+) \(([\w.]+)\)", out, re.M):
        where = m.group(2)                          # 3.11+: the whole ID; before: just the class
        full = where if where.endswith("." + m.group(1)) else f"{where}.{m.group(1)}"
        names.append(full[len("__main__."):] if full.startswith("__main__.") else full)
    return names


def tests_ran(out):
    """How many tests a unittest run says it ran ("Ran 7 tests in 0.9s"), 0 if it didn't say."""
    m = re.search(r"^Ran (\d+) tests? in", out, re.M)
    return int(m.group(1)) if m else 0


def result_line(name, code, secs, out, alone=False):
    """One file's result: OK or FAIL (TIMEOUT when it was stopped for running too long); a failure also names the tests
    that failed and its last error line, so a job cancelled before the end still says why its files failed."""
    took = f"{secs:.1f}s, alone" if alone else f"{secs:.1f}s"
    if code == 0:
        return f"OK    {name}  ({took})"
    line = f"FAIL  {name}  ({took}{', TIMEOUT' if code == TIMED_OUT else ''})"
    err = next((ln.strip() for ln in reversed(out.splitlines())
                if re.match(r"\s*(TIMEOUT:|\w*(Error|Exception)\b)", ln)), "")
    which = failed_tests(out)[:4]
    return line + (f"  {', '.join(which)}" if which else "") + (f" — {err[:200]}" if err else "")


def show_now(name, out):
    """On a CI runner, the end of a failed file's output at once, folded in the job's log (::group::)."""
    if CI:
        print(f"::group::{name} output (last 60 lines)\n" + "\n".join(out.splitlines()[-60:]) + "\n::endgroup::", flush=True)


def log_flaky(name, secs, out=""):
    """Remember a file that failed under load and passed alone, so the rule that counts it as passing stays visible, with
    which tests failed and the end of that output, so the flake can be diagnosed later."""
    with FLAKY.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"file": name, "when": time.strftime("%Y-%m-%d %H:%M"), "alone_secs": round(secs),
                             "failed": failed_tests(out), "tail": out.splitlines()[-40:]}) + "\n")


def flaky_report():
    """Print the files that failed under load and passed alone, most often first."""
    if not FLAKY.exists():
        print("No file has failed under load and passed alone (nothing in .flaky.jsonl).")
        return
    rows = [json.loads(x) for x in FLAKY.read_text(encoding="utf-8").splitlines() if x.strip()]
    counts = {}
    for r in rows:
        c = counts.setdefault(r["file"], [0, r["when"]])
        c[0] += 1
        c[1] = max(c[1], r["when"])
    print(f"{len(rows)} failure(s) that passed alone, in {len(counts)} file(s):")
    for name, (n, last) in sorted(counts.items(), key=lambda kv: -kv[1][0]):
        print(f"  {n:3d}  {name}  (last {last})")
        latest = next((r for r in reversed(rows) if r["file"] == name and r.get("failed")), None)
        if latest:                                     # which tests, and the first error line
            err = next((ln.strip() for ln in latest.get("tail", []) if re.match(r"\s*\w*(Error|Exception)\b", ln)), "")
            print(f"        last failed: {', '.join(latest['failed'][:4])}" + (f" — {err[:140]}" if err else ""))


class Runner:
    """Runs test files, each in its own process group with a private TMPDIR (creaite)."""

    def __init__(self, timeout=FILE_TIMEOUT, ids=None):
        self.timeout = timeout or None    # seconds a file may run before it is stopped (None: no limit)
        self.ids = ids or {}              # {file name: [unittest names]} when only some of a file's tests run
        self.dir = support.RunDir()
        self.procs = set()
        self.lock = threading.Lock()

    def run(self, f):
        """Run one test file: (file, exit code, seconds, output)."""
        tmp = self.dir.for_file()
        path = os.pathsep.join([str(p) for p in PATHS] + [x for x in [os.environ.get("PYTHONPATH")] if x])
        env = {**os.environ, "PYTHONPATH": path, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8",
               "TMPDIR": str(tmp), "TMP": str(tmp), "TEMP": str(tmp)}   # BL-246: everything it makes lands here
        t, p, out, timed_out, reader = time.time(), None, [], False, None
        try:
            p = support.spawn([sys.executable, "-m", "unittest", *self.ids.get(f.name, [f.stem])], cwd=f.parent,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8",
                              errors="replace", env=env)
            with self.lock:
                self.procs.add(p)
            reader = threading.Thread(target=lambda: out.append(p.stdout.read()), daemon=True)
            reader.start()
            try:
                p.wait(timeout=self.timeout)  # the test itself, not its output: a leaked child may hold the pipe open
            except subprocess.TimeoutExpired:
                timed_out = True          # a hung file fails here instead of holding the run to its time limit
                support.stop(p, grace=10)
            support.stop(p, grace=2)      # whatever it started and left in its group ends now
            reader.join(5)
            if timed_out:
                out.append(f"\nTIMEOUT: {f.name} ran over {self.timeout:.0f}s (--file-timeout) and was stopped, with "
                           f"everything it started.\n")
        finally:
            with self.lock:
                self.procs.discard(p)
            if p is not None and p.returncode is None:
                support.stop(p, grace=2)
            if reader is not None and not reader.is_alive():
                p.stdout.close()          # not while a leaked child still holds it open: closing would wait on the read
            support.RunDir.finish(tmp)
        code = TIMED_OUT if timed_out else p.returncode
        return f, code, time.time() - t, "".join(out)

    def stop(self):
        """Kill every test still running, with what it started."""
        with self.lock:
            procs = list(self.procs)
        for p in procs:
            support.stop(p, grace=0)

    def close(self):
        """Remove the run's folder."""
        self.dir.close()


def rerun_alone(failed, runner, most=None):
    """Run each failed file once more on its own: a failure under load that passes alone counts (and is logged).
    More than `most` failures (--rerun-max) are not load, so none is run again.
    Returns (the files still failing, with their output; the files that passed alone, with the first output and the
    alone run's)."""
    alone, still = [], []
    most = RERUN_MAX if most is None else most
    if len(failed) > most:
        print(f"\n{len(failed)} files failed, more than --rerun-max {most}: that is not load, so none is run again alone "
              f"(something is wrong for the whole machine; see the first failures below).", flush=True)
        return list(failed), []
    if failed:
        print(f"\nRunning {len(failed)} failed file{'s' if len(failed) != 1 else ''} again, one at a time…", flush=True)
    for name, out in failed:
        f, code, secs, out2 = runner.run(TESTS / name)
        print(result_line(name, code, secs, out2, alone=True), flush=True)
        if code == 0:
            alone.append((name, out, out2))
            log_flaky(name, secs, out)
        else:
            still.append((name, out2))
    return still, alone


def slowest_first(files):
    """Sort `files` in place: the files that failed last time first, then slowest first by the last run's times (unknown
    files count as slow); return those times."""
    last = {}
    if TIMES.exists():
        for ln in TIMES.read_text(encoding="utf-8").splitlines():
            name, _, secs = ln.partition(" ")
            last[name] = float(secs or 0)
    bad = last_failed()
    files.sort(key=lambda f: (f.name not in bad, -last.get(f.name, 1e9)))
    return last


def execute(files, jobs, runner, max_fail=0):
    """Run `files` `jobs` at a time, the browser files at most CHROME_AT_ONCE at a time. With `max_fail` (--max-fail),
    once that many files have failed no further file starts (those running finish), and the rest are named.
    Returns {file name: seconds}, [(failed file name, output)], {file name: output}."""
    chrome = [f for f in files if support.is_chrome(f)]
    quick = [f for f in files if f not in chrome]
    print(f"Running {len(files)} test file{'s' if len(files) != 1 else ''}: {len(quick)} quick, {len(chrome)} browser, "
          f"{jobs} at a time…", flush=True)
    took, failed, outs = {}, [], {}
    qpool = ThreadPoolExecutor(max_workers=max(1, jobs))
    cpool = ThreadPoolExecutor(max_workers=max(1, min(jobs, CHROME_AT_ONCE)))
    try:
        futures = [cpool.submit(runner.run, f) for f in chrome] + [qpool.submit(runner.run, f) for f in quick]
        named = dict(zip(futures, chrome + quick))
        for fut in as_completed(futures):
            if fut.cancelled():
                continue
            f, code, secs, out = fut.result()
            took[f.name], outs[f.name] = secs, out
            report(f.name, code, secs, out)
            if code:
                failed.append((f.name, out))
                if max_fail and len(failed) == max_fail:
                    stop_starting(futures, named, max_fail)
    finally:
        for pool in (qpool, cpool):
            pool.shutdown(wait=False, cancel_futures=True)
    return took, failed, outs


def report(name, code, secs, out):
    """Print one file's result (and, on a CI runner, a failure's output at once)."""
    print(result_line(name, code, secs, out), flush=True)
    if code:
        show_now(name, out)


def stop_starting(futures, named, max_fail):
    """--max-fail reached: cancel every file not yet started (those running finish) and name them."""
    skipped = [named[x].name for x in futures if x.cancel()]
    print(f"\n{max_fail} failed file{'s' if max_fail != 1 else ''} (--max-fail {max_fail}): no further file starts. "
          f"Not run: {len(skipped)} ({', '.join(skipped[:10])}{', …' if len(skipped) > 10 else ''}).\n", flush=True)


def stop_on_sigterm(_signum, _frame):
    """SIGTERM (a stopped task, a closed terminal) ends the run the way Ctrl+C does, so it cleans up."""
    raise KeyboardInterrupt


def pick(names):
    """(the test files the names choose, {file name: unittest names}). A plain name is part of a file's name (creaite); a
    dotted one (test_layout.LayoutTest.test_x) is one class or test of that file, as #28's runner took them."""
    files, ids = sorted(TESTS.glob("test_*.py")), {}
    if not names:
        return files, ids
    chosen = set()
    for n in names:
        n = n[:-len(".py")] if n.endswith(".py") else n         # "test_layout.py", as the workflow's files input may say
        if "." in n:
            f = TESTS / (n.split(".")[0] + ".py")
            if f.exists():
                chosen.add(f)
                ids.setdefault(f.name, []).append(n)
        else:
            chosen.update(f for f in files if n in f.name)
    return sorted(chosen), ids


def summary(ok, count, secs):
    """The last line, as #28's runner printed it: "Python 3.9.6: pass, 97 tests in 1.3 s"."""
    version = sys.version.split()[0]
    if count == 0:
        return f"Python {version}: no tests ran"
    return f"Python {version}: {'pass' if ok else 'FAIL'}, {count} tests in {secs:.1f} s"


def main(argv):
    if sys.version_info < OLDEST:
        print("Python %d.%d or later is needed; this is %s" % (OLDEST + (sys.version.split()[0],)))
        return 2
    ap = argparse.ArgumentParser(prog="run_tests.py")
    ap.add_argument("-j", type=int, default=max(2, (os.cpu_count() or 4) // 2))
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--changed", nargs="?", const="origin/main", metavar="BASE")
    ap.add_argument("--push", metavar="BASE")
    ap.add_argument("--deep", action="store_true")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--flaky", action="store_true")
    ap.add_argument("--repeat", type=int, default=0, metavar="N")
    ap.add_argument("--stress", type=int, default=0, metavar="N")
    ap.add_argument("--file-timeout", type=float, default=FILE_TIMEOUT, metavar="S")
    ap.add_argument("--rerun-max", type=int, default=RERUN_MAX, metavar="N")
    ap.add_argument("--shard", type=shard_arg, metavar="I/N")
    ap.add_argument("--max-fail", type=int, default=0, metavar="N")
    ap.add_argument("names", nargs="*")
    a = ap.parse_args(argv)
    if a.flaky:
        flaky_report()
        return 0
    if a.changed and a.push:
        ap.error("--push already includes --changed: give one of them")
    if a.stress and not a.repeat:
        ap.error("--stress works with --repeat: say how many times to repeat")
    files, ids = pick(a.names)
    if a.names and not files:                     # a typo'd name or files input never goes green, shard or not
        print("No test files match.")
        return 1
    if a.quick:
        files = [f for f in files if not support.is_chrome(f)]
    if a.changed:
        files, why = select(files, a.changed, a.deep)
        print(f"--changed: {len(files)} of the test files ({why}).", flush=True)
    if a.push:
        files, why = for_push(files, a.push, a.deep)
        print(f"--push: {len(files)} of the test files: {why}.", flush=True)
    files = apply_shard(files, a.shard)
    if not files:
        print("No test files to run." if a.changed or a.shard else "No test files match.")
        return 0 if a.changed or a.shard else 1
    if a.list:
        print("\n".join(f"{f.name}{'  (browser)' if support.is_chrome(f) else ''}" for f in files))
        return 0
    return run_all(files, a.j, a.repeat, a.stress, timeout=a.file_timeout, rerun_max=a.rerun_max, max_fail=a.max_fail,
                   ids=ids)


def repeat(files, n, jobs, stress=0, timeout=FILE_TIMEOUT, ids=None):
    """Run each of `files` `n` times, `jobs` at a time, interleaved so each copy runs beside the others; no re-run alone.
    `stress` processes spin the processor meanwhile, so a fast laptop is as slow as a shared CI runner. Prints each
    copy's result, then the passes per file (creaite)."""
    runner, start, results = Runner(timeout, ids), time.time(), {f.name: [] for f in files}
    pool = ThreadPoolExecutor(max_workers=max(1, jobs))
    burners = [subprocess.Popen([sys.executable, "-c", "while True: pass"]) for _ in range(max(0, stress))]
    spin = f", {stress} processes spinning" if stress else ""
    print(f"Running {len(files)} file(s) {n} times each, {jobs} at a time, no re-run alone{spin}…", flush=True)
    try:
        for fut in as_completed([pool.submit(runner.run, f) for _ in range(n) for f in files]):
            f, code, secs, out = fut.result()
            results[f.name].append(code == 0)
            print(result_line(f.name, code, secs, out), flush=True)
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)
        return 130
    finally:
        for b in burners:
            b.kill()
            b.wait()
        pool.shutdown(wait=False, cancel_futures=True)
        runner.stop()
        runner.close()
    print(f"\nUnder load ({jobs} at a time{spin}, {time.time() - start:.0f}s):")
    for name, oks in results.items():
        print(f"  {sum(oks)}/{len(oks)}  {name}")
    return 0 if all(all(v) for v in results.values()) else 1


def run_all(files, jobs, copies=0, stress=0, timeout=FILE_TIMEOUT, rerun_max=None, max_fail=0, ids=None):
    """Run `files`, re-run failures alone, report; always remove the run's temporary folders, even when stopped.
    With `copies` (--repeat), run that many copies of each under load instead, and report each file's passes."""
    support.clean()                       # BL-247: the folders of earlier runs that were killed outright
    signal.signal(signal.SIGTERM, stop_on_sigterm)
    if copies:
        return repeat(files, copies, jobs, stress, timeout, ids)
    files = list(files)
    last = slowest_first(files)
    start, runner = time.time(), Runner(timeout, ids)
    try:
        took, failed, outs = execute(files, jobs, runner, max_fail)
        try:
            TIMES.write_text("".join(f"{k} {v:.2f}\n" for k, v in sorted({**last, **took}.items())), encoding="utf-8")
        except OSError:
            pass                          # a read-only checkout loses only the ordering
        remember_failed([f.name for f in files], [n for n, _ in failed])
        failed, alone = rerun_alone(failed, runner, rerun_max)
    except KeyboardInterrupt:
        runner.stop()
        print("\nStopped. The tests still running were ended and their temporary folders removed.", flush=True)
        return 130
    finally:
        runner.stop()
        runner.close()
    for name, out, out2 in alone:
        outs[name] = out2
        which = failed_tests(out)
        print(f"Passed alone after failing under load: {name}" + (f" ({', '.join(which[:4])} failed)" if which else "")
              + " (logged; python3 dev/run_tests.py --flaky)")
    for name, out in failed:
        print(f"\n===== {name} =====\n" + "\n".join(out.splitlines()[-80:]))
    not_run = len(files) - len(took)
    passed = len(took) - len(failed)
    print(f"\n{passed} file{'s' if passed != 1 else ''} passed, {len(failed)} failed"
          + (f", {not_run} not run (--max-fail)" if not_run else "") + ".")
    count = sum(tests_ran(o) for o in outs.values())
    ok = not failed and not not_run
    print(summary(ok, count, time.time() - start))
    return 0 if ok and count else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
