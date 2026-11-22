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

    def builtin_section(self, template_type, built_in_type, title, project="ABC"):
        """Row 1266: a new project starts with the template sections (At a glance, Documents); a test of the built-in one (which an
        existing report keeps) gives the project that one, in the template's place."""
        with self.store.step("dashboard", USER) as st:
            for row in self.store.read("report_sections", project):
                if row["type"] == template_type:
                    st.cancel("report_sections", row["id"])
                    st.create("report_sections", {"project": project, "type": built_in_type, "title": title, "sort_order": row["sort_order"]})

    def builtin_glance(self, project="ABC"):
        self.builtin_section("glancetemplate", "glance", "At a glance", project)

    def builtin_docs(self, project="ABC"):
        self.builtin_section("doclinks", "docs", "Supporting documents", project)

    def action(self, **values):
        base = {"project": "ABC", "description": "Draft the cut-over plan", "raised": "2026-10-01", "source": "demo"}
        with self.store.step("dashboard", USER) as st:
            return st.create("actions", {**base, **values})

    def update(self, kind, ref, changes, **kw):
        with self.store.step("dashboard", USER) as st:
            st.update(kind, ref, changes, **kw)
        return self.last_step()
