"""Key figures, three (#96, F3b): the content of a section of type 'figures3': 3 places, each a typed figure or a live one
(the same figures as the At a glance tiles). The rules are shared with the other Key figures template (figures4.py).
"""
from clark.section_kinds import figures4

READY = True
PLACES = 3
LIMIT = figures4.LIMIT
EMPTY = ""
check = figures4.checker(PLACES)
published = figures4.publisher(PLACES)
