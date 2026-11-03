"""The colours of the Excel export (#85a): a table read from the committed design tokens (tokens.css, BRD FR-110) when clark starts,
so the workbook reads like the page. Red, amber and green are the tokens' status colours: a light fill with dark text of the same
hue, as the page's pills (4.5:1 or better, checked by a test). A brand with its own tokens.css gets the committed set until the
workbook reads the brand's tokens at export (a later change); nothing here is read from data.

Only fixed values, written as static cell fills at export. No formulas and no conditional-formatting rules, so a workbook
carries no `<f>` element and a cell's value is never changed by its colour.
"""
from datetime import date

from clark import look

# Token name -> hex (no #): the light values of the committed look (src/clark/brand/tokens.css), read by look.py when clark starts, so the
# workbook and the Word file read like the page and a change to the look reaches them with no edit here. Only the names are listed.
TOKEN_NAMES = (
    "brand-navy", "brand-ink", "white", "brand-blue", "grey-50", "grey-100", "grey-300", "grey-700", "brand-blue-tint",
    "status-blue-text", "status-green-tint", "status-green-text", "status-amber-tint", "status-amber-text",
    "status-red-tint", "status-red-text", "status-red",
)
TOKENS = {name: look.colour(name) for name in TOKEN_NAMES}

# Colour name -> (fill token, text token). The names are what the value tables below use.
COLOURS = {
    "red": ("status-red-tint", "status-red-text"),
    "amber": ("status-amber-tint", "status-amber-text"),
    "green": ("status-green-tint", "status-green-text"),
    "blue": ("brand-blue-tint", "status-blue-text"),
    "grey": ("grey-100", "grey-700"),
}

HEADER_FILL = TOKENS["brand-navy"]
HEADER_TEXT = TOKENS["white"]
LATE_TEXT = TOKENS["status-red-text"]       # an open item past its date: red text (the page's .late)

# Each kind of row follows what the page shows for it (the Head's decision on #85).
# RAID priority: D-12 (Urgent or High red, Medium amber, Low green). Impact and likelihood use the same scale.
PRIORITY = {"Urgent": "red", "High": "red", "Medium": "amber", "Low": "green"}
# Action priority: the page's .prio pills (app.css): Urgent red, High amber, Medium and Low grey; no green.
ACTION_PRIORITY = {"Urgent": "red", "High": "amber", "Medium": "grey", "Low": "grey"}
RATING = {"High": "red", "Medium": "amber", "Low": "green"}
# A milestone's state, as the page draws it (views.js MS_CLS): Achieved and On track green, At risk amber, Slipped and Overdue
# red, Forecast blue.
MILESTONE_STATE = {"Achieved": "green", "On track": "green", "At risk": "amber", "Slipped": "red", "Overdue": "red",
                   "Forecast": "blue"}
DECISION_STATUS = {"Pending": "amber", "Made": "green", "Withdrawn": "grey"}
USE_CASE_STATUS = {"On track": "green", "Flag": "amber", "High risk": "red", "Done": "grey"}     # Done: finished, grey as on the page

# Action and RAID status, in the page's tones: Open blue, Delayed amber, Closed and Cancelled grey.
ACTION_STATUS = {"Open": "blue", "Delayed": "amber", "Closed": "grey", "Cancelled": "grey"}
RAID_STATUS = {"Open": "blue", "Closed": "grey", "Cancelled": "grey"}

# (table, field) -> the value table. A value not in the table (or an empty cell) gets no colour.
BY_FIELD = {
    ("actions", "priority"): ACTION_PRIORITY,
    ("raid", "priority"): PRIORITY,
    ("actions", "status"): ACTION_STATUS,
    ("raid", "status"): RAID_STATUS,
    ("raid", "impact"): RATING,
    ("raid", "likelihood"): RATING,
    ("milestones", "shown_state"): MILESTONE_STATE,
    ("milestones", "state"): MILESTONE_STATE,
    ("decisions", "status"): DECISION_STATUS,
    ("use_cases", "status"): USE_CASE_STATUS,
}

# (table, date field) -> (status field, the statuses that are still open): past this date, the date is drawn red.
LATE = {
    ("actions", "due_date"): ("status", {"Open", "Delayed"}),
    ("raid", "due_date"): ("status", {"Open"}),
    ("decisions", "needed_by"): ("status", {"Pending"}),
}


def colour_for(table, field, value):
    """The colour name for a cell's value (red, amber, green, blue or grey), or None."""
    return BY_FIELD.get((table, field), {}).get(value)


def hexes(name):
    """(fill hex, text hex) for a colour name."""
    fill, text = COLOURS[name]
    return TOKENS[fill], TOKENS[text]


def is_late(table, field, row, today):
    """True when `field` is a date before `today` (a date) on an item that is still open."""
    rule = LATE.get((table, field))
    if not rule:
        return False
    status_field, open_states = rule
    if row.get(status_field) not in open_states:
        return False
    try:
        return date.fromisoformat(row.get(field)) < today      # text that is not a date is never late
    except (TypeError, ValueError):
        return False
