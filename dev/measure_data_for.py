"""How long Store.data_for takes over a large change_log (#251).

Run: python3 dev/measure_data_for.py [rows] [calls] [share]     (rows default 50000, calls default 5, share default 0.1)
Builds a temporary store with one project of open actions, adds `rows` change_log rows (each with its item_events row) by
direct SQL (`share` of them about the project's own items, the rest about another project's), then times data_for for that
project (it reads each open item's freshness from the log). Prints the first call, the later calls and the first call after
an edit, in milliseconds. Exit 1 if a call after the first is over LIMIT_MS. Nothing outside a temporary folder is touched.
"""
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "tests"))
from _demo import DemoStore  # noqa: E402

LIMIT_MS = 50
ITEMS = 60


def build(demo, rows, share):
    """Make ITEMS open actions in project ABC, then `rows` log rows spread over them and over another project's ids."""
    ids = [demo.action(description=f"Action {n}") for n in range(ITEMS)]
    con = demo.store.con
    step = demo.last_step()
    others = [f"XYZ-A-{n:03d}" for n in range(ITEMS)]
    fields = ("status", "priority", "owner", "due", "description")
    base = con.execute("SELECT max(rowid) FROM change_log").fetchone()[0] or 0
    mine = round(rows * share)           # the first `mine` rows are the project's own, the rest another project's
    con.execute("BEGIN")                      # one transaction: this connection commits every statement unless told otherwise
    con.executemany("INSERT INTO change_log (apply_id, tbl, item_id, field, old_value, new_value, op, via) "
                    "VALUES (?, 'actions', ?, ?, ?, ?, 'update', 'dashboard')",
                    [(step, (ids if n < mine else others)[n % ITEMS], fields[n % len(fields)], str(n), str(n + 1)) for n in range(rows)])
    con.executemany("INSERT INTO item_events (at, apply_id, item_id, change, kind, route, place, actor) "
                    "VALUES ('2026-10-01 09:00:00', ?, ?, ?, 'change', 'dashboard', 'cell', 'you')",
                    [(step, (ids if n < mine else others)[n % ITEMS], base + n + 1) for n in range(rows)])
    con.execute("COMMIT")


def timed(store):
    start = time.perf_counter()
    data = store.data_for("ABC")
    return (time.perf_counter() - start) * 1000, data


def measure(rows=50000, calls=5, share=0.1):
    """(first call, median of the later calls, first call after one edit), in ms, of data_for("ABC") on a log of `rows` rows."""
    demo = DemoStore()
    try:
        build(demo, rows, share)
        first, data = timed(demo.store)
        later = [timed(demo.store)[0] for _ in range(calls - 1)]
        assert len(data["actions"]) == ITEMS
        demo.update("actions", data["actions"][0]["id"], {"priority": "High"})
        return first, statistics.median(later), timed(demo.store)[0]
    finally:
        demo.close()


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    share = float(sys.argv[3]) if len(sys.argv) > 3 else 0.1
    first, later, edited = measure(n, k, share)
    print(f"python {sys.version.split()[0]}: data_for over {n} change_log rows ({share:.0%} the project's own): "
          f"first call {first:.1f} ms, next calls (median of {k - 1}) {later:.1f} ms, first call after an edit {edited:.1f} ms "
          f"(limit {LIMIT_MS} ms)")
    sys.exit(0 if max(later, edited) <= LIMIT_MS else 1)
