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

    def action(self, **values):
        base = {"project": "ABC", "description": "Draft the cut-over plan", "raised": "2026-10-01", "source": "demo"}
        with self.store.step("dashboard", USER) as st:
            return st.create("actions", {**base, **values})

    def update(self, kind, ref, changes, **kw):
        with self.store.step("dashboard", USER) as st:
            st.update(kind, ref, changes, **kw)
        return self.last_step()
