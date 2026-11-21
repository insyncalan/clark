"""A fresh store with fictional demo data, for the store tests (#31)."""
import shutil
import sqlite3
import tempfile
from pathlib import Path

import _paths  # noqa: F401  (puts src/ on the path)
from clark.store import open_store

USER = "Demo User"


def old_glance_and_docs(path, project="ABC"):
    """A report made before row 1266 has the built-in At a glance and Supporting documents sections; a new project's are the glance and
    Files and links templates. Tests of the built-in ones give the project's two rows the older types (nothing changes when it has none)."""
    con = sqlite3.connect(str(path))
    try:
        con.execute("UPDATE report_sections SET type = 'glance', body = '' WHERE project = ? AND type = 'glancetemplate'", (project,))
        con.execute("UPDATE report_sections SET type = 'docs', title = 'Supporting documents' WHERE project = ? AND type = 'doclinks'", (project,))
        con.commit()
    finally:
        con.close()


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

    def old_glance_and_docs(self, project="ABC"):
        old_glance_and_docs(self.store.path, project)

    def action(self, **values):
        base = {"project": "ABC", "description": "Draft the cut-over plan", "raised": "2026-10-01", "source": "demo"}
        with self.store.step("dashboard", USER) as st:
            return st.create("actions", {**base, **values})

    def update(self, kind, ref, changes, **kw):
        with self.store.step("dashboard", USER) as st:
            st.update(kind, ref, changes, **kw)
        return self.last_step()
