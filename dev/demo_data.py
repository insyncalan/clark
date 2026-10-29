"""Build a fresh clark.db of fictional demo data (#30; BRD NFR-6), to see clark with data in it.

    python3 dev/demo_data.py                       # builds dev/.cache/demo/clark.db (git-ignored)
    python3 dev/demo_data.py --out /some/folder/clark.db
    CLARK_NOW="2026-10-28 09:00" python3 dev/demo_data.py

Two fictional projects (TUL and MOSS), each with workstreams, use cases, actions, risks, assumptions, issues and
dependencies, decisions (Made, Pending and Withdrawn), links, a label, weekly updates and milestones in every state
(Achieved, On track, At risk, Slipped, Overdue, Forecast, and a Cancelled one). Every row goes in through the store's
steps (src/clark/store.py, the one writer); this script writes no SQL.

The clock: CLARK_NOW fixes "now" (YYYY-MM-DD, or YYYY-MM-DD HH:MM[:SS], UTC; a date alone means 09:00). Every date in
the data is an offset from it, and every timestamp the store writes is CLARK_NOW plus one millisecond per write, so two
runs with the same CLARK_NOW give the same data in every table. Unset, it is the real time. The store has no clock of
its own to set, so this script swaps the store's now(), today() and uuid for fixed ones while it builds (fixed_clock),
and puts them back after.

Output: --out PATH (default dev/.cache/demo/clark.db, inside the repo's ignored area). An existing database there is
replaced only if it is a demo database made by this script; anything else is refused. The database is built beside it and
moved into place, so a failed build leaves nothing half-made.

Only the names below appear in the data: nobody and no organisation is real (tests/test_demo_data.py checks it).
Structure and approach follow creaite's dev/tools/demo_data.py (v2.6.9): fictional projects with dates relative to today,
written through the one writer. The rows themselves are new, for clark's tables.
"""
import argparse
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import uuid
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _folder in (ROOT / "vendor", ROOT / "src"):
    if str(_folder) not in sys.path:
        sys.path.insert(0, str(_folder))

from clark import platform  # noqa: E402
from clark import store as clark_store  # noqa: E402

DEFAULT_OUT = ROOT / "dev" / ".cache" / "demo" / "clark.db"
SOURCE = "Demo data (fictional)"

# ── The fictional list: every person, organisation, project and use case in the data, and nothing else ────────────

ADA, BARNABY, CRESSIDA = "Ada Quillfeather", "Barnaby Tumblewick", "Cressida Pennywhistle"
DORIAN, EDNA, FENWICK = "Dorian Fogwhistle", "Edna Marblethorpe", "Fenwick Oddsock"
GWENDOLEN, HAMISH, IMOGEN = "Gwendolen Thistlebrook", "Hamish Cobblesnout", "Imogen Dribblewick"
DEMO_USER = "Demo Author"                      # who the steps are made by (the settings name)
PEOPLE = (ADA, BARNABY, CRESSIDA, DORIAN, EDNA, FENWICK, GWENDOLEN, HAMISH, IMOGEN, DEMO_USER)

WOBBLETON, FIZZLEWICK = "Wobbleton Council", "Fizzlewick Ltd"
ORGANISATIONS = (WOBBLETON, FIZZLEWICK)

TULIP, MOSSGROVE = "Tulip Records Migration", "Mossgrove Customer Portal"
PROJECT_NAMES = (TULIP, MOSSGROVE)
CODES = ("TUL", "MOSS")

UC_TULIP = ("Paper files scanned and indexed", "Planning applications moved across", "Old archive switched off")
UC_MOSS = ("Customers sign in once", "Bills and payments in one place", "Faults reported from a phone")
USE_CASES = UC_TULIP + UC_MOSS

FICTIONAL = {"people": PEOPLE, "organisations": ORGANISATIONS, "projects": PROJECT_NAMES, "use_cases": USE_CASES}


class DemoError(Exception):
    """Something the person can fix, said plainly."""


# ── The clock ────────────────────────────────────────────────────────────────────────────────────────────────────

def parse_now(text):
    """CLARK_NOW as a datetime (UTC, naive); a date alone is 09:00; empty is the real time."""
    text = (text or "").strip()
    if not text:
        return datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    for form in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M"):
        try:
            return datetime.strptime(text, form)
        except ValueError:
            pass
    try:
        return datetime.strptime(text, "%Y-%m-%d").replace(hour=9)
    except ValueError:
        raise DemoError(f"CLARK_NOW must be YYYY-MM-DD or YYYY-MM-DD HH:MM[:SS] (got {text!r})")


class _FixedUuid:
    """Stands in for the store's uuid module: the ids it makes are a function of the seed and their count."""

    def __init__(self, seed):
        self.seed, self.n = seed, 0

    def uuid4(self):
        self.n += 1
        return uuid.UUID(bytes=hashlib.sha256(f"{self.seed}:{self.n}".encode("utf-8")).digest()[:16], version=4)


@contextmanager
def fixed_clock(start):
    """While inside, the store's now() is `start` plus one millisecond per call (so steps keep their order), its today() is
    start's date and its uuid4() is repeatable; put back after. The store reads the real clock itself and has no setting for
    this, so the swap is of its module names (finding for #31)."""
    count = [0]

    def now():
        count[0] += 1
        return (start + timedelta(milliseconds=count[0])).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    saved = (clark_store.now, clark_store.today, clark_store.uuid)
    clark_store.now, clark_store.today = now, lambda: start.date().isoformat()
    clark_store.uuid = _FixedUuid(start.isoformat())
    try:
        yield
    finally:
        clark_store.now, clark_store.today, clark_store.uuid = saved


# ── The data ─────────────────────────────────────────────────────────────────────────────────────────────────────
# Offsets are days from CLARK_NOW (negative: past). Each project is one spec; "ms", "uc" and "ws" in an item are the
# position in that project's own milestones, use cases and workstreams (counting from 0).

def tulip(d):
    return {
        "project": dict(code="TUL", name=TULIP, sponsor=CRESSIDA, phase="Build", health="At risk", client_name=WOBBLETON,
                        health_reason="Scanning is a fortnight behind; the training date has already passed",
                        current_state="<p>Scanning is two thirds done and the planning archive is being indexed. "
                                      "Training was due last week and has not happened.</p>",
                        week_ending=d(-2), layout="boxed"),
        "workstreams": [("Scanning", ADA), ("Indexing", BARNABY), ("Training", EDNA)],
        "use_cases": [
            dict(ref="1.1", title=UC_TULIP[0], status="Flag", headline="Two thirds scanned, a fortnight behind",
                 standing="<p>The second scanner arrived late. Catch-up is planned over two weekends.</p>"),
            dict(ref="1.2", title=UC_TULIP[1], status="On track", headline="Indexing rules agreed",
                 standing="<p>Rules for the planning index are signed off and the first batch has loaded.</p>"),
            dict(ref="1.3", title=UC_TULIP[2], status="High risk", headline="No switch-off date without the legal hold",
                 standing="<p>The old archive cannot be switched off until the records hold is lifted.</p>"),
        ],
        "milestones": [
            dict(name="Records audit complete", ws=0, owner=ADA, baseline=d(-60), status="Done", actual=d(-58),
                 msg="The audit finished two days early."),
            dict(name="Pilot office live", ws=1, owner=BARNABY, baseline=d(14), msg="One office goes first."),
            dict(name="Supplier contract signed", ws=0, owner=CRESSIDA, baseline=d(30), forecast=d(45),
                 note="Legal review is the long pole."),
            dict(name="Staff training complete", ws=2, owner=EDNA, baseline=d(-10), movement="escalate",
                 note="Rooms were double-booked."),
            dict(name="Cut-over rehearsal", ws=1, owner=BARNABY, baseline=d(40), state="At risk",
                 reason="Depends on the scanner catch-up weekends"),
            dict(name="Full roll-out", ws=0, owner=CRESSIDA, forecast=d(120), state="Forecast",
                 msg="The date is not agreed yet."),
        ],
        "rebaseline": dict(ms=1, baseline=d(21), agreed_with=CRESSIDA, reason="Pilot office asked for a quieter week",
                           source="Steering note (demo)"),
        "actions": [
            dict(description="Book two weekend scanning shifts", ws=0, owner=ADA, priority="Urgent", due=d(5), status="Open",
                 raised=d(-9), ms=4, uc=0, update="Agency has offered both Saturdays", client=1, labels="Sensitive"),
            dict(description="Rebook the training rooms", ws=2, owner=EDNA, priority="High", due=d(-6), status="Delayed",
                 raised=d(-20), ms=3, update="Venue has one date left", client=1),
            dict(description="Agree the planning index rules", ws=1, owner=BARNABY, priority="Medium", due=d(-15), status="Closed",
                 raised=d(-40), closed=d(-16), uc=1, client=1),
            dict(description="Ask legal about lifting the records hold", ws=0, owner=CRESSIDA, priority="High", due=d(12),
                 status="Open", raised=d(-7), uc=2, client=0),
            dict(description="Order a third scanner", ws=0, owner=ADA, priority="Low", due=d(-30), status="Cancelled",
                 raised=d(-45), closed=d(-35), client=0),
            dict(description="Send the pilot office its welcome pack", ws=1, owner=IMOGEN, priority="Medium", due=d(10),
                 status="Open", raised=d(-3), ms=1, client=1),
        ],
        "raid": [
            dict(type="Risk", description="Scanner catch-up weekends are not enough", ws=0, owner=ADA, impact="High",
                 likelihood="Medium", due=d(7), response="Hold a third weekend in reserve", raised=d(-12), ms=4, uc=0),
            dict(type="Risk", description="Staff lose track of the old filing codes", ws=2, owner=EDNA, impact="Medium",
                 likelihood="Low", raised=d(-30), status="Closed", closed=d(-14)),
            dict(type="Assumption", description="The council keeps the planning archive on its own network", ws=1,
                 owner=BARNABY, impact="Medium", likelihood="Low", raised=d(-50)),
            dict(type="Issue", description="Training rooms double-booked", ws=2, owner=EDNA, impact="High", likelihood="High",
                 response="Rebook; ask the venue for a second date", due=d(-3), raised=d(-11), ms=3),
            dict(type="Dependency", description="Records hold lifted by the legal team", ws=0, owner=CRESSIDA, impact="High",
                 likelihood="Medium", due=d(25), raised=d(-20), uc=2),
            dict(type="Issue", description="Duplicate scan numbers in batch 14", ws=0, owner=ADA, impact="Low",
                 likelihood="High", raised=d(-25), status="Cancelled", closed=d(-24)),
        ],
        "decisions": [
            dict(decision="Scan the planning files first, then property files", by=CRESSIDA, date=d(-70), status="Made",
                 reasoning="Planning requests are the most frequent", uc=1),
            dict(decision="Buy a third scanner", by=CRESSIDA, status="Withdrawn", reasoning="Weekend shifts chosen instead"),
            dict(decision="Use weekend shifts to catch up", by=ADA, date=d(-8), status="Made", replaces=1,
                 reasoning="Cheaper than a third scanner", options="Third scanner; weekend shifts; move the date", ms=4),
            dict(decision="Switch the old archive off at roll-out or keep it read-only", status="Pending", needed_by=d(30),
                 options="Switch off; keep read-only for a year", uc=2),
        ],
        "links": [("action", 3, "action", 0)],
        "updates": [(-2, "At risk", "Scanning a fortnight behind; training date missed."),
                    (-9, "At risk", "Second scanner arrived late."),
                    (-16, "On track", "Indexing rules agreed."),
                    (-23, "On track", "Records audit finished early.")],
    }


def mossgrove(d):
    return {
        "project": dict(code="MOSS", name=MOSSGROVE, sponsor=FENWICK, phase="Pilot", health="On track",
                        client_name=FIZZLEWICK, health_reason="Pilot sign-ups are ahead of plan",
                        current_state="<p>The pilot portal has 300 customers. Sign-in works; payments are being tested.</p>",
                        week_ending=d(-2), layout="spine"),
        "workstreams": [("Sign-in", GWENDOLEN), ("Payments", HAMISH), ("Mobile", DORIAN)],
        "use_cases": [
            dict(ref="1", title=UC_MOSS[0], status="On track", headline="Single sign-in live for the pilot",
                 standing="<p>300 pilot customers use one login for every service.</p>"),
            dict(ref="2", title=UC_MOSS[1], status="Flag", headline="Card payments failing for one bank",
                 standing="<p>One bank rejects test payments. The provider is looking at it.</p>"),
            dict(ref="3 and 4", title=UC_MOSS[2], status="On track", headline="Phone reporting designed",
                 standing="<p>Screens are approved and building starts next sprint.</p>"),
        ],
        "milestones": [
            dict(name="Pilot launch", ws=0, owner=GWENDOLEN, baseline=d(-30), status="Done", actual=d(-31),
                 msg="Launched a day early."),
            dict(name="Payments go-live", ws=1, owner=HAMISH, baseline=d(18)),
            dict(name="Mobile app in the stores", ws=2, owner=DORIAN, baseline=d(14), forecast=d(30), state="At risk",
                 reason="Store review may take longer than planned; the date has not moved yet"),
            dict(name="Customer data import", ws=0, owner=GWENDOLEN, baseline=d(35), forecast=d(50),
                 note="Waiting on the old system's export."),
            dict(name="Accessibility audit", ws=2, owner=DORIAN, baseline=d(-4), movement="recover"),
            dict(name="Public launch", ws=0, owner=FENWICK, forecast=d(100), state="Forecast"),
            dict(name="Loyalty scheme link", ws=1, owner=HAMISH, baseline=d(60), status="Cancelled",
                 note="Dropped from the scope."),
        ],
        "rebaseline": dict(ms=1, baseline=d(25), agreed_with=FENWICK, reason="Bank testing needs another week",
                           source="Project board note (demo)"),
        "actions": [
            dict(description="Fix declined card payments for the one bank", ws=1, owner=HAMISH, priority="Urgent", due=d(4),
                 status="Open", raised=d(-6), ms=1, uc=1, update="Provider has reproduced it", client=1),
            dict(description="Book the accessibility re-test", ws=2, owner=DORIAN, priority="High", due=d(-5), status="Delayed",
                 raised=d(-18), ms=4, client=1),
            dict(description="Write the pilot feedback summary", ws=0, owner=IMOGEN, priority="Medium", due=d(-12), status="Closed",
                 raised=d(-25), closed=d(-13), uc=0, client=1),
            dict(description="Draft the store listing text", ws=2, owner=DORIAN, priority="Low", due=d(20), status="Open",
                 raised=d(-4), ms=2, uc=2, client=0),
            dict(description="Agree the loyalty scheme data feed", ws=1, owner=HAMISH, priority="Low", due=d(-20), status="Cancelled",
                 raised=d(-35), closed=d(-10), client=0),
            dict(description="Export the old customer list", ws=0, owner=GWENDOLEN, priority="High", due=d(8), status="Open",
                 raised=d(-10), ms=3, client=1),
        ],
        "raid": [
            dict(type="Risk", description="App store review takes longer than a week", ws=2, owner=DORIAN, impact="Medium",
                 likelihood="High", due=d(10), response="Submit early with a fall-back web app", raised=d(-14), ms=2, uc=2),
            dict(type="Risk", description="Pilot customers outgrow the test servers", ws=0, owner=GWENDOLEN, impact="High",
                 likelihood="Low", raised=d(-22), status="Closed", closed=d(-5)),
            dict(type="Assumption", description="The payment provider keeps its test bank list stable", ws=1, owner=HAMISH,
                 impact="Medium", likelihood="Medium", raised=d(-40), uc=1),
            dict(type="Issue", description="One bank rejects every test payment", ws=1, owner=HAMISH, impact="High",
                 likelihood="High", response="Provider is checking the card network settings", due=d(3), raised=d(-6), ms=1, uc=1),
            dict(type="Dependency", description="Export from the old customer system", ws=0, owner=IMOGEN, impact="High",
                 likelihood="Medium", due=d(15), raised=d(-16), ms=3),
            dict(type="Risk", description="Loyalty partner changes its terms", ws=1, owner=HAMISH, impact="Low",
                 likelihood="Low", raised=d(-45), status="Cancelled", closed=d(-10)),
        ],
        "decisions": [
            dict(decision="Use one sign-in for every service", by=FENWICK, date=d(-90), status="Made",
                 reasoning="Customers asked for it in the survey", uc=0),
            dict(decision="Delay payments go-live by a week", by=FENWICK, date=d(-3), status="Made",
                 reasoning="Bank testing needs more time", ms=1),
            dict(decision="Build the mobile app natively or as a web app", status="Pending", needed_by=d(9),
                 options="Native app; web app; both", uc=2),
            dict(decision="Include the loyalty scheme in the pilot", by=FENWICK, status="Withdrawn",
                 reasoning="Dropped from scope"),
        ],
        "links": [("action", 0, "milestone", 1), ("raid", 3, "action", 0)],
        "updates": [(-2, "On track", "Payments testing under way."),
                    (-9, "On track", "300 pilot customers signed in."),
                    (-16, "At risk", "Sign-in outage for two hours."),
                    (-23, "On track", "Pilot launched.")],
    }


# ── Building ─────────────────────────────────────────────────────────────────────────────────────────────────────

def _maybe(values, **pairs):
    """`values` plus each pair whose value is not None."""
    values.update({k: v for k, v in pairs.items() if v is not None})
    return values


def at(items, i):
    """items[i], or None when i is None."""
    return items[i] if i is not None else None


def load_project(st, spec, d):
    """One project's rows, through the step. Returns {"actions": [ids], "raid": [...], ...} in the spec's order."""
    code = spec["project"]["code"]
    st.create("projects", dict(spec["project"]))
    names = [n for n, _ in spec["workstreams"]]
    for n, lead in spec["workstreams"]:
        st.create("workstreams", dict(project=code, name=n, lead=lead, source=SOURCE))
    uc = [st.create("use_cases", dict(project=code, sort_order=i + 1, source=SOURCE, **u))
          for i, u in enumerate(spec["use_cases"])]
    ms = []
    for i, m in enumerate(spec["milestones"]):
        ms.append(st.create("milestones", _maybe(
            dict(project=code, name=m["name"], status=m.get("status", "Planned"), sort_order=i + 1, source=SOURCE),
            workstream=at(names, m.get("ws")), owner=m.get("owner"), baseline_date=m.get("baseline"),
            forecast_date=m.get("forecast"), actual_date=m.get("actual"), state=m.get("state"), state_reason=m.get("reason"),
            client_message=m.get("msg"), internal_note=m.get("note"), movement=m.get("movement"))))
    out = {"use_cases": uc, "milestones": ms, "actions": [], "raid": [], "decisions": []}
    for a in spec["actions"]:
        out["actions"].append(st.create("actions", _maybe(
            dict(project=code, description=a["description"], owner=a["owner"], priority=a["priority"], status=a["status"],
                 raised=a["raised"], client_visible=a["client"], source=SOURCE),
            workstream=at(names, a.get("ws")), due_date=a.get("due"), closed=a.get("closed"), latest_update=a.get("update"),
            milestone=at(ms, a.get("ms")), use_case=at(uc, a.get("uc")), labels=a.get("labels"),
            label_reason="Names a supplier's price" if a.get("labels") else None)))
    for r in spec["raid"]:
        out["raid"].append(st.create("raid", _maybe(
            dict(project=code, type=r["type"], description=r["description"], owner=r["owner"], impact=r["impact"],
                 likelihood=r["likelihood"], raised=r["raised"], status=r.get("status", "Open"), source=SOURCE),
            workstream=at(names, r.get("ws")), due_date=r.get("due"), response_action=r.get("response"), closed=r.get("closed"),
            milestone=at(ms, r.get("ms")), use_case=at(uc, r.get("uc")))))
    for dc in spec["decisions"]:
        out["decisions"].append(st.create("decisions", _maybe(
            dict(project=code, decision=dc["decision"], status=dc["status"], source=SOURCE),
            made_by=dc.get("by"), date=dc.get("date"), needed_by=dc.get("needed_by"), reasoning=dc.get("reasoning"),
            options=dc.get("options"), use_case=at(uc, dc.get("uc")), replaces=at(out["decisions"], dc.get("replaces")))))
    kinds = {"action": out["actions"], "raid": out["raid"], "milestone": ms}
    for a_kind, a_i, b_kind, b_i in spec["links"]:
        st.create("links", dict(from_item=kinds[a_kind][a_i], to_item=kinds[b_kind][b_i], source=SOURCE))
    for offset, health, summary in spec["updates"]:
        st.create("updates", dict(week_ending=d(offset), project=code, health=health, summary=summary))
    return out


def local_onedrive_roots():
    """The OneDrive folders to keep the demo database out of, where the platform layer can find them (the Mac now; Windows
    later). Elsewhere (Linux CI) there is no such check: a demo database never needs OneDrive, so the answer is none."""
    try:
        return platform.onedrive_roots()
    except platform.NotBuiltYet:
        return []


def build(out, now, onedrive_roots=None):
    """Build the demo database at `out` with the clock at `now` (a datetime). Returns {table: row count} for the data tables."""
    if onedrive_roots is None:
        onedrive_roots = local_onedrive_roots()
    out = Path(out)
    check_can_replace(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    building = out.with_name(out.name + ".building")
    remove_database(building)
    base = now.date()
    d = lambda n: (base + timedelta(days=n)).isoformat()      # noqa: E731  (creaite demo_data.d: a date n days from now)
    specs = [tulip(d), mossgrove(d)]
    try:
        with fixed_clock(now):
            store = clark_store.open_store(building, onedrive_roots=onedrive_roots)
            try:
                made = []
                with store.step("dashboard", DEMO_USER) as st:
                    for spec in specs:
                        made.append(load_project(st, spec, d))
                with store.step("dashboard", DEMO_USER, place="peek") as st:       # an agreed date moves: a rebaseline
                    for spec, ids in zip(specs, made):
                        rb = spec["rebaseline"]
                        st.update("milestones", ids["milestones"][rb["ms"]], {"baseline_date": rb["baseline"]},
                                  rebaseline={"agreed_with": rb["agreed_with"], "reason": rb["reason"], "source": rb["source"]})
                counts = {t: len(store.read(t)) for t in clark_store.TABLES}
            finally:
                store.close()
        remove_database(out)
        os.replace(str(building), str(out))
    finally:
        remove_database(building)
    return counts


def sidecars(path):
    """The database file and the files SQLite keeps beside it."""
    return [Path(str(path) + s) for s in ("", "-wal", "-shm", "-journal")]


def remove_database(path):
    """Delete a database file and its SQLite sidecars, if there."""
    for p in sidecars(path):
        if p.exists():
            p.unlink()


def is_demo_database(path):
    """True if `path` is a clark database made by this script: it has projects, every project code is one of ours, and every
    step was made by the demo author. The file is never opened where it lies: it is copied (with any -wal, -shm and
    -journal files) into a temporary folder and the copy is opened normally. A read-only open (?mode=ro) of a database in
    WAL mode fails on some SQLite builds (macOS's /usr/bin/python3), and an immutable open is unsafe if anything is
    writing; a copy works on every build and cannot change the original. Anything unreadable is not a demo database."""
    path = Path(path)
    try:
        with tempfile.TemporaryDirectory(prefix="clark-demo-check-") as folder:
            target = Path(folder) / "check.db"
            for source, copy in zip(sidecars(path), sidecars(target)):
                if source.is_file():
                    shutil.copyfile(str(source), str(copy))
            con = sqlite3.connect(str(target))
            try:
                codes = {r[0] for r in con.execute("SELECT code FROM projects")}
                users = {r[0] for r in con.execute("SELECT DISTINCT by_user FROM applies")}
            finally:
                con.close()
    except (sqlite3.Error, OSError):
        return False
    return bool(codes) and codes <= set(CODES) and users == {DEMO_USER}


def check_can_replace(out):
    """Raise DemoError unless `out` is free or is an earlier demo database."""
    out = Path(out)
    if out.is_dir():
        raise DemoError(f"{out} is a folder; give --out a file name such as {out / 'clark.db'}")
    if out.exists() and not is_demo_database(out):
        raise DemoError(f"{out} already exists and is not a demo database made by this script, so it is left alone. "
                        "Choose another --out, or move that file away yourself.")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build a fresh clark.db of fictional demo data.")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="where to build it (default: %(default)s)")
    args = parser.parse_args(argv)
    try:
        now = parse_now(os.environ.get("CLARK_NOW"))
        counts = build(Path(args.out).expanduser(), now)
    except (DemoError, clark_store.Invalid, platform.PlatformError) as e:
        print(f"demo_data: {e}", file=sys.stderr)
        return 1
    shown = ", ".join(f"{n} {t}" for t, n in counts.items() if n)
    print(f"Built {args.out} at {now:%d-%m-%Y %H:%M}: {shown}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
