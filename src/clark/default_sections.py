"""The report's default sections (FR-10, #65): the ten every new project starts with, in this order.

A constant module, so changing the default layout is not a change to the guarded store. store.py only reads it, at project
creation, and gives each its own id (<CODE>-S-001 to <CODE>-S-010) and its place (GAP, 2 * GAP and so on, from clark.order).
The types and titles are those of the editor prototype (system/prototype/db.js, defaultReport). Only a text section has a
body, and only a text section can sit beside another: This week is set beside the next section, as in the prototype.
tests/test_sections_store.py pins this list.
"""
CURRENT_STATE_PREFILL = "Say where the project stands today, at a high level: what is done, what comes next, and anything that needs attention."   # item 1188: the editor's hint for the first section, never its body (a client must not read instruction text); the page gets it from the build (dev/tools/build_page.py)
SECTION_HINTS = {          # item 1193: the guiding sentence of each text section that has one; the editor's hint only, never a body
    "Current state": CURRENT_STATE_PREFILL,
    "This week": "List what was done this week, and what moved forward.",
    "Next week": "List what is planned for next week, and who is doing it.",
}
DECISIONS_LIST = ('{"v":1,"kinds":["decision"],"mode":"open","status":[],"due":[],"owner":[],"workstream":[],"use_case":[],"priority":[],"sort":"due","max":10,'
                  '"columns":["type","id","owner","due","priority"],"caption":"","milestone":[],"not":{"kinds":[],"status":[],"due":[],"owner":[],'
                  '"workstream":[],"use_case":[],"priority":[],"milestone":[]},"has":[],"no":[],"text":[]}')   # row 10 of item 1193 (1266 row 9): the saved view Decisions, the open ones (Pending); the Work items list's own start body with its kind set (a test pins it equal)
# row 1193-9: Open actions starts as a Work items list, filled with that list's own saved filter (open actions, soonest due first, at most 50 so it holds every row the built-in did); new projects only, an existing report keeps its own section
OPEN_ACTIONS_BODY = '{"caption":"","columns":["type","id","owner","due","priority"],"due":[],"has":[],"kinds":["action"],"max":50,"milestone":[],"mode":"open","no":[],"not":{"due":[],"kinds":[],"milestone":[],"owner":[],"priority":[],"status":[],"use_case":[],"workstream":[]},"owner":[],"priority":[],"sort":"due","status":[],"text":[],"use_case":[],"v":1,"workstream":[]}'   # stored the way the store writes it (keys sorted)
DEFAULT_SECTIONS = (
    {"type": "text", "title": "Current state", "body": ""},   # item 1188: a text section now; the older type "current" is still read and stored, and existing reports keep it
    {"type": "glance", "title": "At a glance"},
    {"type": "usecases", "title": "Use case summary"},
    {"type": "milestones", "title": "Milestones"},
    {"type": "text", "title": "This week", "beside": 1},
    {"type": "text", "title": "Next week"},
    {"type": "raid", "title": "Risks and issues"},
    {"type": "workitems", "title": "Open actions", "body": OPEN_ACTIONS_BODY},   # row 1193-9
    {"type": "workitems", "title": "Decisions", "body": DECISIONS_LIST},   # row 10 of item 1193: a Work items list on the saved view Decisions (new projects only; existing reports keep their built-in)
    {"type": "docs", "title": "Supporting documents"},
)
