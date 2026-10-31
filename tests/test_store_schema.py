"""#31: schema.sql refuses bad data, and creaite's tables match creaite v2.6.9 apart from lines marked "-- clark:"."""
import re
import sqlite3
import unittest

from _paths import ROOT, SRC

SCHEMA = SRC / "clark" / "schema.sql"
CREAITE = ROOT / "tests" / "fixtures" / "creaite-v2.6.9-schema.sql"
CREAITE_TABLES = ("projects", "milestones", "workstreams", "actions", "raid", "decisions", "links", "labels", "item_labels",
                  "updates", "applies", "change_log", "item_events")
NOT_COPIED = {("projects", "next_milestone"), ("projects", "milestone_date"), ("workstreams", "channel")}   # data-model.md


def table_lines(sql):
    """{table: {column or constraint: (normalised definition, marked clark)}}; a wrapped definition is joined to its line."""
    out = {}
    for m in re.finditer(r"CREATE TABLE IF NOT EXISTS (\w+) \((.*?)\n\);", sql, re.S):
        entries = []
        for raw in m.group(2).splitlines():
            if not raw.strip() or raw.strip().startswith("--"):
                continue
            code, marked = raw.split("--")[0], "-- clark:" in raw
            if re.match(r"  \S", raw) or not entries:
                entries.append([code, marked])
            else:
                entries[-1][0] += " " + code
                entries[-1][1] |= marked
        lines = {}
        for code, marked in entries:
            code = re.sub(r"\s+", " ", code).strip().rstrip(",")
            first = code.split()[0]
            lines[first if first not in ("CHECK", "UNIQUE", "PRIMARY") else code] = (code, marked)
        out[m.group(1)] = lines
    return out


def fresh():
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.executescript("""
        INSERT INTO projects (code, name) VALUES ('ABC', 'Example Programme');
        INSERT INTO milestones (id, project, name, source) VALUES ('ABC-M-001', 'ABC', 'Pilot live', 'demo');
        INSERT INTO decisions (id, project, decision, date, source) VALUES ('ABC-D-001', 'ABC', 'Go', '2026-10-01', 'demo');
    """)
    return con


GOOD = {
    "projects": {"code": "XYZ", "name": "Other"},
    "milestones": {"id": "ABC-M-002", "project": "ABC", "name": "M", "source": "s"},
    "workstreams": {"id": "ABC-W-001", "project": "ABC", "name": "Build", "created": "2026-10-01", "source": "s"},
    "actions": {"id": "ABC-A-002", "project": "ABC", "description": "d", "raised": "2026-10-01", "source": "s"},
    "raid": {"id": "ABC-003", "project": "ABC", "type": "Risk", "description": "d", "raised": "2026-10-01", "source": "s"},
    "decisions": {"id": "ABC-D-004", "project": "ABC", "decision": "d", "date": "2026-10-01", "source": "s"},
    "use_cases": {"id": "ABC-U-001", "project": "ABC", "title": "t", "status": "On track", "source": "s"},
    "links": {"from_item": "ABC-A-002", "to_item": "ABC-M-001", "source": "s"},
    "labels": {"name": "Watch"},
    "updates": {"week_ending": "2026-10-02", "project": "ABC", "health": "On track", "summary": "s"},
}
# One bad value per rule: (table, field, value).
BAD = [
    ("projects", "code", "ab"), ("projects", "code", "1ABC"), ("projects", "code", "ABCDEFGH"), ("projects", "health", "Green"),
    ("projects", "layout", "wide"), ("projects", "week_ending", "02-10-2026"), ("projects", "active", 2),
    ("milestones", "id", "ABC-M-02"), ("milestones", "id", "ABC-A-002"), ("milestones", "status", "Missed"),
    ("milestones", "state", "Late"), ("milestones", "percent_complete", 101), ("milestones", "baseline_date", "2030/03/01"),
    ("milestones", "movement", "drop"), ("milestones", "client_visible", 2), ("milestones", "project", "NOPE"),
    ("workstreams", "name", "  "), ("workstreams", "status", "Open"), ("workstreams", "created", "today"),
    ("actions", "id", "ABC-D-002"), ("actions", "priority", "Critical"), ("actions", "status", "Done"),
    ("actions", "due_date", "2026-1-1"), ("actions", "closed", "2026-09-01"), ("actions", "milestone", "ABC-M-099"),
    ("raid", "id", "ABC-A-003"), ("raid", "type", "Opportunity"), ("raid", "impact", "Huge"), ("raid", "likelihood", "Rare"),
    ("raid", "priority", "Top"), ("raid", "status", "Delayed"),
    ("decisions", "status", "Agreed"), ("decisions", "date", None), ("decisions", "replaces", "ABC-D-004"),
    ("decisions", "needed_by", "soon"),
    ("use_cases", "id", "ABC-U-1"), ("use_cases", "status", "Red"),
    ("links", "kind", "relates"), ("links", "to_item", "ABC-A-002"),
    ("labels", "name", "a,b"), ("labels", "behaviour", "hide"), ("labels", "default_choice", "maybe"),
    ("updates", "health", "Amber"),
]


class Checks(unittest.TestCase):
    def insert(self, con, table, row):
        con.execute(f"INSERT INTO {table} ({', '.join(row)}) VALUES ({', '.join('?' * len(row))})", list(row.values()))

    def test_the_good_rows_go_in(self):
        con = fresh()
        for table, row in GOOD.items():
            self.insert(con, table, row)

    def test_each_check_refuses_bad_data(self):
        for table, field, value in BAD:
            with self.subTest(table=table, field=field, value=value):
                con = fresh()
                con.execute("PRAGMA foreign_keys = ON")
                if table == "links":
                    self.insert(con, "actions", GOOD["actions"])
                row = dict(GOOD[table], **{field: value})
                with self.assertRaises(sqlite3.IntegrityError):
                    self.insert(con, table, row)

    def test_the_sensitive_label_is_built_in_and_kept(self):
        con = fresh()
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("DELETE FROM labels WHERE name = 'Sensitive'")
        with self.assertRaises(sqlite3.IntegrityError):
            con.execute("UPDATE labels SET name = 'Private' WHERE name = 'Sensitive'")


class MatchesCreaite(unittest.TestCase):
    def test_creaite_tables_match_v2_6_9_apart_from_marked_lines(self):
        creaite = table_lines(CREAITE.read_text(encoding="utf-8"))
        clark = table_lines(SCHEMA.read_text(encoding="utf-8"))
        problems = []
        for t in CREAITE_TABLES:
            for key, (code, _) in creaite[t].items():
                if key not in clark[t]:
                    if (t, key) not in NOT_COPIED:
                        problems.append(f"{t}: {key} is missing")
                elif clark[t][key][0] != code and not clark[t][key][1]:
                    problems.append(f"{t}: {key} differs and isn't marked -- clark:")
            for key, (_, marked) in clark[t].items():
                if key not in creaite[t] and not marked:
                    problems.append(f"{t}: {key} is new and isn't marked -- clark:")
        self.assertEqual(problems, [])

    def test_the_checker_sees_a_change(self):
        clark = SCHEMA.read_text(encoding="utf-8").replace("'Urgent','High','Medium','Low')),\n  due_date",
                                                           "'Urgent','High','Low')),\n  due_date", 1)
        creaite = table_lines(CREAITE.read_text(encoding="utf-8"))
        self.assertNotEqual(table_lines(clark)["actions"]["priority"][0], creaite["actions"]["priority"][0])


if __name__ == "__main__":
    unittest.main()
