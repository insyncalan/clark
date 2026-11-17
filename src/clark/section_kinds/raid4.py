"""RAID cards, four (F9, #96): the content of a section of type 'raid4', four shorter cards across. The same content and rules as
three across (raid3.py: a card is a work item's id and where its words come from); only the number of cards differs.
"""
from clark.section_kinds import raid3

READY = True
SIZE = 4
ACROSS = (3, 4)                            # row 1270: the one library card RAID cards stores a body of version 2 with the choice, up to eight cards
LIMIT = raid3.LIMIT
EMPTY = ""


def check(value, rules):
    return raid3._check(value, rules, SIZE, ACROSS)


def published(value, ctx):
    return raid3._published(value, ctx, SIZE)
