"""Numbers, stored as 'figures3' (#96, F3b; one card since row 1263): the type the old "Key figures, three" card stored: 3 places, each a
typed figure or a live one (the same figures as the At a glance tiles), or the body's own count of 3 or 4. The rules are shared with
the Numbers card's own type (figures4.py); a stored figures3 section is read by the one card and is never rewritten to another type.
"""
from clark.section_kinds import figures4

READY = True
PLACES = 3
LIMIT = figures4.LIMIT
EMPTY = ""
check = figures4.checker(PLACES)
published = figures4.publisher(PLACES)
