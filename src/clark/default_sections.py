"""The report's default sections (FR-10, #65): the eleven every new project starts with, in this order.

A constant module, so changing the default layout is not a change to the guarded store. store.py only reads it, at project
creation, and gives each its own id (<CODE>-S-001 to <CODE>-S-011) and its place (GAP, 2 * GAP and so on, from clark.order).
The types and titles are those of the editor prototype (system/prototype/db.js, defaultReport). Only a text section has a
body, and only a text section can sit beside another: This week is set beside the next section, as in the prototype.
tests/test_sections_store.py pins this list.
"""
DEFAULT_SECTIONS = (
    {"type": "current", "title": "Current state"},
    {"type": "glance", "title": "At a glance"},
    {"type": "usecases", "title": "Use case summary"},
    {"type": "milestones", "title": "Milestones"},
    {"type": "text", "title": "Summary"},
    {"type": "text", "title": "This week", "beside": 1},
    {"type": "text", "title": "Next week"},
    {"type": "raid", "title": "Risks and issues"},
    {"type": "actions", "title": "Open actions"},
    {"type": "decisions", "title": "Decisions"},
    {"type": "docs", "title": "Supporting documents"},
)
