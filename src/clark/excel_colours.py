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
    "tone-red-text", "tone-red-tint", "tone-amber-text", "tone-amber-tint", "tone-green-text", "tone-green-tint", "tone-blue-text",
    "tone-blue-tint", "tone-grey-text", "tone-grey-tint", "tone-urgent",
)
# Item 1390: tokens only the workbook reads, so they are not in the page's tokens.css (the Cards page's style blocks are pinned by md5 and
# tokens.css is one of them). locked-fill is the fill of a locked cell, the Cover's grey (E7E7E7); a brand's own tokens.css may still set --locked-fill.
EXPORT_TOKENS = {"locked-fill": "E7E7E7"}
TOKEN_NAMES += tuple(EXPORT_TOKENS)
TOKENS = {name: look.colour(name) for name in TOKEN_NAMES if name not in EXPORT_TOKENS}
TOKENS.update(EXPORT_TOKENS)

# Colour name -> (fill token, text token). The names are what the value tables below use.
COLOURS = {
    "red": ("tone-red-tint", "tone-red-text"),
    "amber": ("tone-amber-tint", "tone-amber-text"),
    "green": ("tone-green-tint", "tone-green-text"),
    "blue": ("tone-blue-tint", "tone-blue-text"),
    "grey": ("tone-grey-tint", "tone-grey-text"),
    "maroon": ("tone-urgent", "white"),      # item 1390: Urgent, the page's solid tile with a white letter
}

HEADER_FILL = TOKENS["brand-navy"]
HEADER_TEXT = TOKENS["white"]
LATE_TEXT = TOKENS["tone-red-text"]       # an open item past its date: red text (the page's .late)

# Each kind of row follows what the page shows for it (item 1390: the page's tone pairs).
# RAID priority, the page's chip: Urgent maroon, High red, Medium amber, Low green. Impact and likelihood: High red, Medium amber, Low green.
PRIORITY = {"Urgent": "maroon", "High": "red", "Medium": "amber", "Low": "green"}
# Action priority, the page's chip: Urgent maroon, High red, Medium and Low grey; no amber and no green.
ACTION_PRIORITY = {"Urgent": "maroon", "High": "red", "Medium": "grey", "Low": "grey"}
RATING = {"High": "red", "Medium": "amber", "Low": "green"}
# A milestone's state, as the page draws it (views.js MS_CLS): Achieved and On track green, At risk amber, Slipped and Overdue
# red, Forecast blue.
MILESTONE_STATE = {"Achieved": "green", "On track": "green", "At risk": "amber", "Slipped": "red", "Overdue": "red",
                   "Forecast": "blue"}
DECISION_STATUS = {"Pending": "blue", "Made": "green", "Withdrawn": "grey"}
USE_CASE_STATUS = {"On track": "green", "Flag": "amber", "High risk": "red", "Done": "grey"}     # Done: finished, grey as on the page

# Action status (item 1390): Open blue, Delayed amber, Closed and Cancelled grey.
ACTION_STATUS = {"Open": "blue", "Delayed": "amber", "Closed": "grey", "Cancelled": "grey"}
# RAID status: Closed and Cancelled grey. Open takes the row's own Priority colour (the page's workItems.js colourOf): a rule that reads
# the Priority cell, written by excel.add_open_by_priority_rules from OPEN_BY_PRIORITY, so it is not in this table.
RAID_STATUS = {"Closed": "grey", "Cancelled": "grey"}
OPEN_BY_PRIORITY = dict(PRIORITY)

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
    if not isinstance(value, str):      # a stored list or dict has no colour, and is never an unhashable lookup
        return None
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
    status = row.get(status_field)
    if not isinstance(status, str) or status not in open_states:      # a stored list or dict is no open state, and never an unhashable lookup
        return False
    try:
        return date.fromisoformat(row.get(field)) < today      # text that is not a date is never late
    except (TypeError, ValueError):
        return False
