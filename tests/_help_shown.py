"""What Help shows (#82): the source (helpContent.json) without the entries held in helpLater.json.

A Python copy of shownContent() in src/clark/page/src/help/helpLogic.js, for the tests. test_help_logic.py runs the real one in
the browser and checks that the two give the same content, so they cannot drift apart.
"""
import copy
import json

from _paths import ROOT

HELP = ROOT / "src" / "clark" / "page" / "src" / "help"
RAW = json.loads((HELP / "helpContent.json").read_text(encoding="utf-8"))
LATER = json.loads((HELP / "helpLater.json").read_text(encoding="utf-8"))
START_PARTS = ["top", "loop", "first", "jobs", "where", "rules", "foot"]
START_FIELDS = {
    "top": {"hero": {"label": "", "title": "", "lead": ""}},
    "loop": {"loop": [], "text": ["loop_title", "loop_intro", "loop_return"]},
    "first": {"first": [], "text": ["first_title"]},
    "jobs": {"jobs": [], "text": ["jobs_title", "jobs_intro"]},
    "where": {"where": [], "text": ["where_title", "keyline", "keyline_link"]},
    "rules": {"rules": [], "text": ["rules_title"]},
    "foot": {"text": ["foot", "foot_link"]},
}


def shown_content(raw=RAW, later=LATER):
    later = later or {}
    c = copy.deepcopy(raw)
    held_start = list((later.get("start") or {}).keys())
    c["start"]["parts"] = [p for p in START_PARTS if p not in held_start]
    for p in held_start:
        for k, v in START_FIELDS.get(p, {}).items():
            if k == "text":
                for t in v:
                    c["start"]["text"][t] = ""
            else:
                c["start"][k] = copy.deepcopy(v)
    c["howto"]["tasks"] = [x for x in c["howto"]["tasks"] if x["id"] not in (later.get("howto") or {})]
    c["reference"]["sections"] = [x for x in c["reference"]["sections"] if x["id"] not in (later.get("reference") or {})]
    c["howto"]["groups"] = [g for g in c["howto"]["groups"] if any(x["g"] == g for x in c["howto"]["tasks"])]
    c["reference"]["groups"] = [g for g in c["reference"]["groups"] if any(x["g"] == g for x in c["reference"]["sections"])]
    held_keys = {k["at"] for k in later.get("keys") or []}
    c["reference"]["keys"] = [k for i, k in enumerate(c["reference"]["keys"]) if i not in held_keys]
    return c
