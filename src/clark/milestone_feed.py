"""The Milestones view's rows for the page (#146; read only, no database, no clock of its own beyond milestones.today).

  editor_rows(data, today)  -> {"as_at", "milestones"}: milestone_rows' output cut to the fields the Calendar and its list draw

`data` is Store.data_for(code)'s dict. The server hands this to GET /api/milestones through a seam (the server imports
nothing from clark). Only the fields in PAGE_FIELDS leave: no internal note, state reason, Movement choice, original date or
description. The published page does not use this: its rows come from the file's own data block (logic/msrows.js).
"""
from clark import milestones as ms
from clark.milestone_rows import milestone_rows

PAGE_FIELDS = ("id", "name", "owner", "state", "client_word", "colour", "mark", "baseline", "forecast", "achieved", "expected",
               "slip", "slip_text", "marks", "client_visible")


def editor_rows(data, today=None):
    """The project's milestones for the editor's Milestones view, in milestone_rows' order, each cut to PAGE_FIELDS."""
    on = today or ms.today()
    rows = milestone_rows(data.get("milestones") or (), on, data.get("workstreams"))
    return {"as_at": on, "milestones": [{k: r[k] for k in PAGE_FIELDS} for r in rows]}


def make_feed(data_for):
    """The seam for GET /api/milestones: a function from a project code to editor_rows of `data_for(code)`, None when there is
    no such project."""
    def feed(code):
        data = data_for(code)
        return None if data is None else editor_rows(data)
    return feed
