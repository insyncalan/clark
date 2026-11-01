"""The section template registry (#96): every template store type and the module that holds its content rules.

Filled with all eighteen types up front, so a builder only ever changes their own template's module, never this file,
section_bodies.py, store.py or changes.py. The order is the store's (store.SECTION_TYPES); the store type, this registry, the
page's catalogue (page/src/logic/templates.js) and the page's index (page/src/templates/index.js) name the same eighteen
types (tests/test_section_registry.py).
"""
from clark.section_kinds import textimage
from clark.section_kinds import headline
from clark.section_kinds import figures4
from clark.section_kinds import figures3
from clark.section_kinds import gallery
from clark.section_kinds import table
from clark.section_kinds import doclinks
from clark.section_kinds import linkcard
from clark.section_kinds import raid3
from clark.section_kinds import raid4
from clark.section_kinds import workitems
from clark.section_kinds import callout
from clark.section_kinds import imagecap
from clark.section_kinds import quote
from clark.section_kinds import contacts
from clark.section_kinds import checklist
from clark.section_kinds import keydates
from clark.section_kinds import onedoc

REGISTRY = {
    "textimage": textimage,
    "headline": headline,
    "figures4": figures4,
    "figures3": figures3,
    "gallery": gallery,
    "table": table,
    "doclinks": doclinks,
    "linkcard": linkcard,
    "raid3": raid3,
    "raid4": raid4,
    "workitems": workitems,
    "callout": callout,
    "imagecap": imagecap,
    "quote": quote,
    "contacts": contacts,
    "checklist": checklist,
    "keydates": keydates,
    "onedoc": onedoc,
}
TYPES = tuple(REGISTRY)
