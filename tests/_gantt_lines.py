"""Fictional plan lines shared by the Gantt table tests (#926). Dates run on from 06-11-2026 in the tests."""


def line(id, n, t, s, e, pct=0, **more):
    return {"id": id, "n": n, "t": t, "par": "", "s": s, "e": e, "pct": pct, "rag": "", "dep": [], "o": "", "ws": "", "pri": "", "bs": "", "be": "",
            "eff": "", "cost": "", "del": "", "show": True, "note": "", **more}


LINES = [
    line("GNT-001", "Discovery", "p", "2026-09-01", "2026-10-20", 100, o="Ada Example"),
    line("GNT-002", "Scan paper files", "t", "2026-09-01", "2026-10-14", 100, par="GNT-001", show=False),
    line("GNT-003", "Records audit complete", "m", "2026-10-20", "2026-10-20", 100, par="GNT-001", dep=["GNT-002"]),
    line("GNT-004", "Migration", "p", "2026-10-22", "2027-02-26", 30, o="Sam Example"),
    line("GNT-005", "Staff training", "t", "2026-10-22", "2026-12-04", 60, par="GNT-004", dep=["GNT-003"], show=False, note="Room booked"),
    line("GNT-006", "Move applications", "t", "2026-11-20", "2027-02-12", 20, par="GNT-004", dep=["GNT-005"], show=False),
    line("GNT-007", "Go-live", "p", "2027-02-15", "2027-05-28", 0),
]
