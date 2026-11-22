"""A fresh store with fictional demo data, for the store tests (#31)."""
import shutil
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

    def use_older_default_sections(self, project="ABC"):
        """An existing report keeps the ten sections a project started with before row 1266 (Current state, At a glance, Use case summary,
        Milestones, This week beside Next week, the three lists, Supporting documents); a new project starts with the eleven of
        clark.default_sections. Tests that pin the older ten, in their ids ABC-S-001 to ABC-S-010 and their places, call this once, right after
        the store is made: the rows of the new default are rewritten in place (past the writer, as an older report's rows are) and the eleventh goes."""
        from clark.default_sections import DECISIONS_LIST, OPEN_ACTIONS_BODY, RISKS_AND_ISSUES_LIST
        older = (("text", "Current state", "", 0), ("glance", "At a glance", "", 0), ("usecases", "Use case summary", "", 0),
                 ("milestones", "Milestones", "", 0), ("text", "This week", "", 1), ("text", "Next week", "", 0),
                 ("workitems", "Risks and issues", RISKS_AND_ISSUES_LIST, 0), ("workitems", "Open actions", OPEN_ACTIONS_BODY, 0),
                 ("workitems", "Decisions", DECISIONS_LIST, 0), ("docs", "Supporting documents", "", 0))
        con = self.store.con
        for n, (kind, title, body, beside) in enumerate(older, 1):
            con.execute("UPDATE report_sections SET type = ?, title = ?, body = ?, beside = ? WHERE project = ? AND id = ?",
                        (kind, title, body, beside, project, f"{project}-S-{n:03d}"))
        con.execute("DELETE FROM report_sections WHERE project = ? AND id = ?", (project, f"{project}-S-011"))
        con.commit()

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
