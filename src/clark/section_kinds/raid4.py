"""RAID cards, four (F9, #96): the content of a section of type 'raid4', four shorter cards across. The same content and rules as
three across (raid3.py: a card is a work item's id and where its words come from); only the number of cards differs.
"""
from clark.section_kinds import raid3

READY = True
SIZE = 4
LIMIT = raid3.LIMIT
EMPTY = ""


def check(value, rules):
    return raid3._check(value, rules, SIZE)


def published(value, ctx):
    return raid3._published(value, ctx, SIZE)
