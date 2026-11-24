"""A fresh store with fictional demo data, for the store tests (#31)."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

import _paths  # noqa: F401  (puts src/ on the path)
from clark.store import open_store

USER = "Demo User"


class DemoStore:
    """A store in a temporary folder with project ABC ("Example Programme"), workstream Build, use case ABC-U-001 and
    milestone ABC-M-001. Use as a context manager, or call close()."""

    def __init__(self):
        self.dir = Path(tempfile.mkdtemp(prefix="clark-test-"))
        self.store = open_store(self.dir / "clark.db", onedrive_roots=[])
        with self.store.step("dashboard", USER) as st:
            st.create("projects", {"code": "ABC", "name": "Example Programme", "health": "On track"})
            st.create("workstreams", {"project": "ABC", "name": "Build", "source": "demo"})
            self.use_case = st.create("use_cases", {"project": "ABC", "title": "Invoice matching", "status": "On track",
                                                    "source": "demo"})
            self.milestone = st.create("milestones", {"project": "ABC", "name": "Pilot live", "baseline_date": "2030-03-01",
                                                      "source": "demo"})

    def __enter__(self):
        return self.store

    def __exit__(self, *exc):
        self.close()

    def close(self):
        self.store.close()
        shutil.rmtree(self.dir, ignore_errors=True)

    def last_step(self):
        return self.store.con.execute("SELECT max(apply_id) FROM applies").fetchone()[0]

    def old_layout(self, project="ABC", built_in_lists=False):
        """Row 1266: a new project starts with Headline, At a glance (the template), Header, This week beside Next week, Milestones, Use cases,
        the three lists, Documents. An existing report keeps the ten sections it was given before, and these tests are that report's: the
        eleven rows are written back, in place (the same ids and places), as the ten older ones; with built_in_lists the three Work items lists are
        the built-in Risks and issues, Open actions and Decisions sections of the report before row 1193, with no body."""
        from clark.default_sections import DECISIONS_LIST, OPEN_ACTIONS_BODY, RISKS_AND_ISSUES_LIST
        older = (("text", "Current state", 0, ""), ("glance", "At a glance", 0, ""), ("usecases", "Use case summary", 0, ""),
                 ("milestones", "Milestones", 0, ""), ("text", "This week", 1, ""), ("text", "Next week", 0, ""),
                 ("workitems", "Risks and issues", 0, RISKS_AND_ISSUES_LIST), ("workitems", "Open actions", 0, OPEN_ACTIONS_BODY),
                 ("workitems", "Decisions", 0, DECISIONS_LIST), ("docs", "Supporting documents", 0, ""))
        con = sqlite3.connect(str(self.store.path))
        try:
            for n, (kind, title, beside, body) in enumerate(older, 1):
                con.execute("UPDATE report_sections SET type = ?, title = ?, beside = ?, body = ? WHERE project = ? AND id = ?",
                            (kind, title, beside, body, project, f"{project}-S-{n:03d}"))
            con.execute("DELETE FROM report_sections WHERE project = ? AND id = ?", (project, f"{project}-S-011"))
            con.execute("DELETE FROM change_log WHERE tbl = 'report_sections' AND item_id = ?", (f"{project}-S-011",))      # a number ever logged is never given again, and the next section is the eleventh
            if built_in_lists:
                for title, kind in (("Risks and issues", "raid"), ("Open actions", "actions"), ("Decisions", "decisions")):
                    con.execute("UPDATE report_sections SET type = ?, body = '' WHERE project = ? AND type = 'workitems' AND title = ?", (kind, project, title))
            con.commit()
        finally:
            con.close()

    def plant_builtin_sections(self, project="ABC"):
        """A new project's report has Work items lists where the built-in Actions, RAID and Decisions sections used to be (row 1193), and a list
        reaches only the rows it names. Tests that pin the built-in sections give the project section rows: the default sections but those lists,
        then the three built-in ones."""
        from clark.default_sections import DEFAULT_SECTIONS
        rows = [dict(s) for s in DEFAULT_SECTIONS if s["type"] != "workitems"]
        rows += [{"type": "actions", "title": "Open actions"}, {"type": "raid", "title": "Risks and issues"}, {"type": "decisions", "title": "Decisions"}]
        with self.store.step("dashboard", USER) as st:
            for i, r in enumerate(rows):
                st.create("report_sections", {"project": project, "sort_order": i, **r})

    def action(self, **values):
        base = {"project": "ABC", "description": "Draft the cut-over plan", "raised": "2026-10-01", "source": "demo"}
        with self.store.step("dashboard", USER) as st:
            return st.create("actions", {**base, **values})

    def update(self, kind, ref, changes, **kw):
        with self.store.step("dashboard", USER) as st:
            st.update(kind, ref, changes, **kw)
        return self.last_step()


def builtin_glance(store, codes):
    """Row 1266: a new project starts with the template glance; these tests are the built-in one's, which an existing project keeps, so it takes the template's place."""
    with store.step("dashboard", "tester") as st:
        for code in codes:
            for row in store.read("report_sections", code):
                if row["type"] == "glancetemplate":
                    st.cancel("report_sections", row["id"])
                    st.create("report_sections", {"project": code, "type": "glance", "title": "At a glance", "sort_order": row["sort_order"]})
