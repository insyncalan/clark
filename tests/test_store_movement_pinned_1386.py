"""Row 1386: Store.milestone_moves, pinned over one busy scenario before it was split into smaller functions (no behaviour change).
The scenario holds every branch: a made step, a lone note, a note beside a date, a cited decision, an undone move, a reverted
first agreement, a milestone with no changes, an archived one, and both caps (lowered here so the cut is reached)."""
import json
import unittest
from unittest import mock

from _demo import USER, DemoStore
from clark import store as st_mod

REBASE = {"agreed_with": "Pat Placeholder", "reason": "Build ran long", "source": "Steering, 01-10-2026"}


def scenario(demo):
    s = demo.store
    with s.step("dashboard", USER) as st:
        a = st.create("milestones", {"project": "ABC", "name": "Alpha", "source": "demo", "baseline_date": "2030-01-01"})
        b = st.create("milestones", {"project": "ABC", "name": "Beta", "source": "demo"})
        c = st.create("milestones", {"project": "ABC", "name": "Gamma", "source": "demo", "baseline_date": "2030-02-01"})
        dead = st.create("milestones", {"project": "ABC", "name": "Dead", "source": "demo"})
    for i in range(1, 5):
        demo.update("milestones", a, {"forecast_date": "2030-03-%02d" % i})
    demo.update("milestones", a, {"baseline_date": "2030-04-01"}, rebaseline=REBASE, note="Build ran long, see ABC-D-004")
    undone = demo.update("milestones", b, {"baseline_date": "2030-08-01"})
    s.undo(undone, USER)
    demo.update("milestones", b, {"baseline_date": "2030-09-01"})
    demo.update("milestones", b, {"forecast_date": "2030-10-01"}, note="a note beside a date")
    demo.update("milestones", c, {"status": "Done"})
    demo.update("milestones", dead, {"forecast_date": "2030-05-01"})
    with s.step("dashboard", USER) as st:
        st.archive("milestones", dead)
    return a, b, c


class Pinned(unittest.TestCase):
    def setUp(self):
        self.demo = DemoStore()
        self.addCleanup(self.demo.close)
        self.ids = scenario(self.demo)

    def summary(self, got):
        rows = {}
        today = st_mod.today()  # Done stamps the achieved date with today, so the golden holds a marker, not a date
        for mid, blk in got["milestones"].items():
            rows[mid] = {"original": blk["original"], "total": blk["total"], "moves": blk["moves"],
                         "events": [(e["event_id"], e["step"], e["field"], e["before"], "<today>" if e["field"] == "actual_date" and e["after"] == today else e["after"], e["op"], e["decision"],
                                     e["undoes"], e["is_undo"], e["undone_by"], e["in_force"], e["src_ref"]) for e in blk["events"]]}
        return {"project": got["project"], "truncated": got["truncated"], "milestones": rows}

    def test_the_whole_reply(self):
        got = self.demo.store.milestone_moves("ABC")
        self.assertEqual(json.loads(json.dumps(self.summary(got))), GOLDEN_FULL)

    def test_the_milestone_cap(self):
        with mock.patch.object(st_mod, "MOVE_PER_MILESTONE", 2):
            got = self.demo.store.milestone_moves("ABC")
        self.assertEqual(json.loads(json.dumps(self.summary(got))), GOLDEN_MILESTONE_CAP)

    def test_the_project_cap(self):
        with mock.patch.object(st_mod, "MOVE_PER_PROJECT", 4):
            got = self.demo.store.milestone_moves("ABC")
        self.assertEqual(json.loads(json.dumps(self.summary(got))), GOLDEN_PROJECT_CAP)

    def test_no_such_project(self):
        self.assertIsNone(self.demo.store.milestone_moves("NOPE"))


GOLDEN_FULL = json.loads('{"project":"ABC","truncated":false,"milestones":{"ABC-M-001":{"original":"2030-03-01","total":0,"moves":0,"events":[]},"ABC-M-002":{"original":"2030-01-01","total":6,"moves":5,"events":[[179,7,"note",null,"Build ran long, see ABC-D-004. Agreed with Pat Placeholder. Decision ABC-D-001","update","ABC-D-001",null,false,null,true,null],[167,7,"baseline_date","2030-01-01","2030-04-01","update","ABC-D-001",null,false,null,true,null],[166,6,"forecast_date","2030-03-03","2030-03-04","update","",null,false,null,true,null],[165,5,"forecast_date","2030-03-02","2030-03-03","update","",null,false,null,true,null],[164,4,"forecast_date","2030-03-01","2030-03-02","update","",null,false,null,true,null],[163,3,"forecast_date",null,"2030-03-01","update","",null,false,null,true,null]]},"ABC-M-003":{"original":"2030-09-01","total":5,"moves":1,"events":[[184,11,"note",null,"a note beside a date","update","",null,false,null,true,null],[183,11,"forecast_date",null,"2030-10-01","update","",null,false,null,true,null],[182,10,"baseline_date",null,"2030-09-01","update","",null,false,null,true,null],[181,9,"baseline_date","2030-08-01",null,"update","",180,true,null,true,null],[180,8,"baseline_date",null,"2030-08-01","update","",null,false,181,false,null]]},"ABC-M-004":{"original":"2030-02-01","total":2,"moves":0,"events":[[186,12,"actual_date",null,"<today>","update","",null,false,null,true,null],[185,12,"status","Planned","Done","update","",null,false,null,true,null]]}}}')
GOLDEN_MILESTONE_CAP = json.loads('{"project":"ABC","truncated":true,"milestones":{"ABC-M-001":{"original":"2030-03-01","total":0,"moves":0,"events":[]},"ABC-M-002":{"original":"2030-01-01","total":6,"moves":5,"events":[[179,7,"note",null,"Build ran long, see ABC-D-004. Agreed with Pat Placeholder. Decision ABC-D-001","update","ABC-D-001",null,false,null,true,null],[167,7,"baseline_date","2030-01-01","2030-04-01","update","ABC-D-001",null,false,null,true,null]]},"ABC-M-003":{"original":"2030-09-01","total":5,"moves":1,"events":[[184,11,"note",null,"a note beside a date","update","",null,false,null,true,null],[183,11,"forecast_date",null,"2030-10-01","update","",null,false,null,true,null]]},"ABC-M-004":{"original":"2030-02-01","total":2,"moves":0,"events":[[186,12,"actual_date",null,"<today>","update","",null,false,null,true,null],[185,12,"status","Planned","Done","update","",null,false,null,true,null]]}}}')
GOLDEN_PROJECT_CAP = json.loads('{"project":"ABC","truncated":true,"milestones":{"ABC-M-001":{"original":"2030-03-01","total":0,"moves":0,"events":[]},"ABC-M-002":{"original":"2030-01-01","total":6,"moves":5,"events":[]},"ABC-M-003":{"original":"2030-09-01","total":5,"moves":1,"events":[[184,11,"note",null,"a note beside a date","update","",null,false,null,true,null],[183,11,"forecast_date",null,"2030-10-01","update","",null,false,null,true,null]]},"ABC-M-004":{"original":"2030-02-01","total":2,"moves":0,"events":[[186,12,"actual_date",null,"<today>","update","",null,false,null,true,null],[185,12,"status","Planned","Done","update","",null,false,null,true,null]]}}}')

if __name__ == "__main__":
    unittest.main()
