"""Tech debt row 1384: the Gantt line rules (store._gantt_rules) are pinned one rule at a time, in the order they run, so the function
can be split into small ones without a change in behaviour. Each case calls the rule check directly on a row and the fields a step
writes. Fictional data only.

Run: python3 dev/run_tests.py test_gantt_rules_pin
"""
import unittest

from _demo import DemoStore
from _paths import SRC  # noqa: F401
from clark import store as S
from clark.store import Invalid

PH, T1, T2 = "ABC-GNT-001", "ABC-GNT-002", "ABC-GNT-003"


def line(**kw):
    row = {"project": "ABC", "type": "task", "name": "Dig", "start": "2026-11-02", "end": "2026-11-13", "pct": 0, "sort_order": 1,
           "health": "", "priority": "", "depends": "", "parent": None}
    row.update(kw)
    return row


class Rules(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.con = self.demo.store.con
        for i, (typ, parent, deps) in enumerate(((  "phase", None, ""), ("task", PH, ""), ("task", PH, T1)), 1):
            self.con.execute("INSERT INTO gantt_lines (id, project, type, name, start, \"end\", parent, depends, sort_order) "
                             "VALUES (?, 'ABC', ?, ?, '2026-11-02', '2026-11-13', ?, ?, ?)", (f"ABC-GNT-00{i}", typ, f"L{i}", parent, deps, i))
        self.con.execute("INSERT INTO projects (code, name) VALUES ('DEF', 'Other')")
        self.con.execute("INSERT INTO gantt_lines (id, project, type, name, start, \"end\", sort_order) "
                         "VALUES ('DEF-GNT-001', 'DEF', 'task', 'Far', '2026-11-02', '2026-11-13', 1)")

    def run_rules(self, row, changed=()):
        S._gantt_rules(self.con, "gantt_lines", row, set(changed))
        return row

    def refuse(self, words, row, changed=()):
        with self.assertRaises(Invalid) as cm:
            self.run_rules(row, changed)
        self.assertEqual(str(cm.exception), words)

    # a new row (no id) is checked on every field
    def test_a_good_new_row_passes_and_is_tidied(self):
        row = self.run_rules(line(name="  Dig\r\n".strip(), owner=None, note="a\r\nb", pct=None, health=None, parent=""))
        self.assertEqual((row["name"], row["owner"], row["note"], row["pct"], row["health"], row["parent"]), ("Dig", "", "a\nb", 0, "", None))

    def test_type(self):
        self.refuse(S.GANTT_BAD_TYPE, line(type="epic"))
        self.refuse(S.GANTT_BAD_TYPE, line(id=T2, type=None), ["name"])           # the type is checked even when it is not written

    def test_name(self):
        self.refuse(S.GANTT_NO_NAME, line(name="  "))
        self.refuse(S.GANTT_BAD_TEXT, line(name="a​b"))
        self.refuse(S.GANTT_BAD_TEXT, line(name="x" * 201))
        self.run_rules(line(name="x" * 200))
        self.run_rules(line(id=T2, name=""), ["pct"])                              # an untouched field is not checked again (an older row never locks)
        self.refuse(S.GANTT_NO_NAME, line(id=T2, name=""), ["name"])

    def test_owner_workstream_deliverable_note(self):
        for f, limit in (("owner", 200), ("workstream", 200), ("deliverable", 500), ("note", 2000)):
            self.refuse(S.GANTT_BAD_TEXT, line(**{f: "x" * (limit + 1)}))
            self.run_rules(line(**{f: "x" * limit}))
            self.run_rules(line(id=T2, **{f: "x" * (limit + 1)}), ["pct"])
            self.refuse(S.GANTT_BAD_TEXT, line(id=T2, **{f: "x" * (limit + 1)}), [f])
            self.refuse(S.GANTT_BAD_TEXT, line(id=T2, **{f: 5}), [f])
        self.run_rules(line(note="a\nb"))
        self.refuse(S.GANTT_BAD_TEXT, line(owner="a\nb"))

    def test_pct(self):
        for bad in (-1, 101, 5.0, "5", True):
            self.refuse(S.GANTT_BAD_PCT, line(pct=bad))
        self.run_rules(line(pct=0))
        self.run_rules(line(pct=100))
        self.assertEqual(self.run_rules(line(pct=None))["pct"], 0)
        self.run_rules(line(id=T2, pct=101), ["name"])                             # not written, not checked
        self.refuse(S.GANTT_BAD_PCT, line(id=T2, pct=101), ["pct"])
        self.refuse(S.GANTT_BAD_PCT, line(id=T2, pct=None), ["pct"])

    def test_health_and_priority(self):
        for f in ("health", "priority"):
            self.refuse(S.GANTT_BAD_CHOICE, line(**{f: "Purple"}))
            self.run_rules(line(**{f: ""}))
            self.assertEqual(self.run_rules(line(**{f: None}))[f], "")
            self.run_rules(line(id=T2, **{f: "Purple"}), ["name"])
            self.refuse(S.GANTT_BAD_CHOICE, line(id=T2, **{f: "Purple"}), [f])
        self.run_rules(line(health="Amber", priority="High"))

    def test_effort_and_budget(self):
        for f, top in (("effort", S.GANTT_MAX_EFFORT), ("budget", S.GANTT_MAX_BUDGET)):
            for bad in (-1, top + 1, True, "1", float("nan"), float("inf")):
                self.refuse(S.GANTT_BAD_NUMBER, line(**{f: bad}))
            self.run_rules(line(**{f: top}))
            self.run_rules(line(**{f: 0}))
            self.run_rules(line(**{f: None}))
            self.run_rules(line(id=T2, **{f: -1}), ["name"])
            self.refuse(S.GANTT_BAD_NUMBER, line(id=T2, **{f: -1}), [f])

    def test_sort_order(self):
        self.refuse(S.GANTT_BAD_PLACE, line(sort_order="1"))
        self.refuse(S.GANTT_BAD_PLACE, line(sort_order=None))
        self.run_rules(line(id=T2, sort_order="1"), ["name"])
        self.refuse(S.GANTT_BAD_PLACE, line(id=T2, sort_order=1.5), ["sort_order"])

    def test_dates(self):
        self.refuse(S.GANTT_BAD_DATE, line(start=""))
        self.refuse(S.GANTT_BAD_DATE, line(end=None))
        self.refuse(S.GANTT_END_BEFORE_START, line(start="2026-11-13", end="2026-11-02"))
        self.run_rules(line(start="2026-11-02", end="2026-11-02"))
        self.refuse(S.GANTT_MILESTONE_ONE_DATE, line(type="milestone"))
        self.run_rules(line(type="milestone", end="2026-11-02"))
        for ch in ("start", "end", "type"):
            self.refuse(S.GANTT_END_BEFORE_START, line(id=T2, start="2026-11-13", end="2026-11-02"), [ch])
        self.run_rules(line(id=T2, start="2026-11-13", end="2026-11-02"), ["name"])
        self.run_rules(line(id=T2, start="", end=""), ["name"])

    def test_baseline(self):
        self.refuse(S.GANTT_BAD_BASELINE, line(baseline_start="2026-11-13", baseline_end="2026-11-02"))
        self.run_rules(line(baseline_start="2026-11-13", baseline_end="2026-11-13"))
        self.run_rules(line(baseline_start="2026-11-13", baseline_end=""))
        self.run_rules(line(baseline_start="", baseline_end="2026-11-02"))
        self.run_rules(line(id=T2, baseline_start="2026-11-13", baseline_end="2026-11-02"), ["name"])
        for ch in ("baseline_start", "baseline_end"):
            self.refuse(S.GANTT_BAD_BASELINE, line(id=T2, baseline_start="2026-11-13", baseline_end="2026-11-02"), [ch])

    def test_parent(self):
        self.run_rules(line(parent=PH))
        self.refuse(S.GANTT_PHASE_TOP, line(type="phase", parent=PH))
        self.refuse(S.GANTT_NO_PARENT.format("ABC-GNT-099"), line(parent="ABC-GNT-099"))
        self.refuse(S.GANTT_NO_PARENT.format("DEF-GNT-001"), line(parent="DEF-GNT-001"))          # another project's line
        self.refuse(S.GANTT_NO_PARENT.format("T2"), line(parent="T2"))                              # not an id
        self.refuse(S.GANTT_NO_PARENT.format(T2), line(id=T2, parent=T2), ["parent"])               # itself
        self.refuse(S.GANTT_PARENT_PHASE, line(parent=T1))
        self.run_rules(line(id=T2, parent=T1), ["name"])
        self.assertIsNone(self.run_rules(line(id=T2, parent=""), ["name"])["parent"])

    def test_a_phase_with_lines_under_it_stays_a_phase(self):
        self.refuse(S.GANTT_PHASE_KEEPS, line(id=PH, type="task"), ["type"])
        self.refuse(S.GANTT_PHASE_KEEPS, line(id=PH, type="milestone", end="2026-11-02"), ["parent"])
        self.run_rules(line(id=PH, type="task"), ["name"])
        self.run_rules(line(id=PH, type="phase"), ["type"])
        self.run_rules(line(id=T1, type="milestone", end="2026-11-02", parent=PH), ["type"])         # a task with nothing under it may change

    def test_depends(self):
        self.assertEqual(self.run_rules(line(depends=f"{PH},{T1}"))["depends"], f"{PH},{T1}")
        self.assertEqual(self.run_rules(line(depends=None))["depends"], "")
        self.refuse(S.GANTT_TOO_MANY_DEPENDS, line(depends=",".join(f"ABC-GNT-{i:03d}" for i in range(100, 151))))
        self.refuse(S.GANTT_SELF_DEPENDS, line(id=T2, depends=T2), ["depends"])
        self.refuse(S.GANTT_NO_DEPEND.format("ABC-GNT-099"), line(depends="ABC-GNT-099"))
        self.refuse(S.GANTT_NO_DEPEND.format("DEF-GNT-001"), line(depends="DEF-GNT-001"))
        self.refuse(S.GANTT_NO_DEPEND.format("x"), line(depends="x"))
        self.run_rules(line(id=T2, depends="ABC-GNT-099"), ["name"])
        # an id already in the stored list is not asked about again
        self.con.execute("UPDATE gantt_lines SET depends = 'ABC-GNT-099' WHERE id = ?", (T2,))
        self.run_rules(line(id=T2, depends="ABC-GNT-099"), ["depends"])

    def test_fifty_depends_pass_and_fifty_one_do_not(self):
        fifty = [f"ABC-GNT-{i:03d}" for i in range(100, 150)]
        self.con.execute("UPDATE gantt_lines SET depends = ? WHERE id = ?", (",".join(fifty), T2))
        self.run_rules(line(id=T2, depends=",".join(fifty)), ["depends"])
        self.refuse(S.GANTT_TOO_MANY_DEPENDS, line(id=T2, depends=",".join(fifty + ["ABC-GNT-150"])), ["depends"])

    def test_a_loop_is_refused_and_an_old_one_is_not_asked_about_again(self):
        self.refuse(S.GANTT_LOOP, line(id=T1, depends=T2), ["depends"])                              # T2 depends on T1
        self.refuse(S.GANTT_LOOP, line(id=T1, depends=f"{PH},{T2}"), ["depends"])
        self.run_rules(line(id=T1, depends=PH), ["depends"])
        self.con.execute("UPDATE gantt_lines SET depends = ? WHERE id = ?", (T2, T1))
        self.run_rules(line(id=T1, depends=T2), ["depends"])                                         # already stored: not asked again

    def test_the_most_lines(self):
        self.con.execute("DELETE FROM gantt_lines WHERE project = 'ABC'")
        self.con.executemany("INSERT INTO gantt_lines (id, project, type, name, start, \"end\", sort_order) VALUES (?, 'ABC', 'task', 'x', '2026-11-02', '2026-11-03', ?)",
                             [(f"ABC-GNT-{i:03d}", i) for i in range(1, S.MAX_GANTT_LINES)])
        self.run_rules(line())
        self.con.execute("INSERT INTO gantt_lines (id, project, type, name, start, \"end\", sort_order) VALUES ('ABC-GNT-900', 'ABC', 'task', 'x', '2026-11-02', '2026-11-03', 900)")
        self.refuse(S.GANTT_TOO_MANY, line())
        self.refuse(S.GANTT_TOO_MANY, line(id="ABC-GNT-901"), ["id"])
        self.run_rules(line(id="ABC-GNT-900"), ["name"])                                             # an existing row is not counted as new
        self.con.execute("INSERT INTO gantt_lines (id, project, type, name, start, \"end\", sort_order) VALUES ('ABC-GNT-901', 'ABC', 'task', 'x', '2026-11-02', '2026-11-03', 901)")
        self.run_rules(line(id="ABC-GNT-900"), ["name"])                                             # a project already over the limit never locks an edit

    def test_the_order_the_rules_run_in(self):
        row = dict(type="epic", name="", pct=500, sort_order="x", start="", health="Purple", parent="nope", depends="nope")
        order = [S.GANTT_BAD_TYPE, S.GANTT_NO_NAME, S.GANTT_BAD_PCT, S.GANTT_BAD_CHOICE, S.GANTT_BAD_PLACE, S.GANTT_BAD_DATE,
                 S.GANTT_NO_PARENT.format("nope"), S.GANTT_NO_DEPEND.format("nope")]
        for words in order:
            self.refuse(words, line(**row))
            for k in {S.GANTT_BAD_TYPE: ("type",), S.GANTT_NO_NAME: ("name",), S.GANTT_BAD_PCT: ("pct",), S.GANTT_BAD_CHOICE: ("health",),
                      S.GANTT_BAD_PLACE: ("sort_order",), S.GANTT_BAD_DATE: ("start",), S.GANTT_NO_PARENT.format("nope"): ("parent",)}.get(words, ()):
                row.pop(k)
                if k == "start":
                    row["start"] = "2026-11-02"
        # text fields come before pct, and note before pct
        self.refuse(S.GANTT_BAD_TEXT, line(owner="x" * 300, pct=500))
        self.refuse(S.GANTT_BAD_NUMBER, line(effort=-1, sort_order="x"))
        self.refuse(S.GANTT_END_BEFORE_START, line(start="2026-11-13", end="2026-11-02", baseline_start="2026-11-13", baseline_end="2026-11-02", parent="nope"))
        self.refuse(S.GANTT_BAD_BASELINE, line(baseline_start="2026-11-13", baseline_end="2026-11-02", parent="nope"))
        self.refuse(S.GANTT_PHASE_TOP, line(type="phase", parent="nope", depends="nope"))
        self.refuse(S.GANTT_PARENT_PHASE, line(parent=T1, depends="nope"))


if __name__ == "__main__":
    unittest.main()
