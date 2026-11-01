"""Checklist (H5, #96): the content of a section of type 'checklist'. STUB: READY is False, the content is checked only by
the generic walls, and nothing of it is ever published. Its builder fills this file (and page/src/templates/ and
tests/test_tpl_checklist.py) and nothing shared: see base.py for the contract.
"""
from clark.section_kinds.base import STUB_LIMIT, stub_check, stub_published

READY = False
LIMIT = STUB_LIMIT
EMPTY = ""
check = stub_check
published = stub_published
