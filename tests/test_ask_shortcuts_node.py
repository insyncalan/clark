"""#1295: the rules of ask clark slash commands (logic/askShortcuts.js): the name rules, built-ins edited, reset and copied, /history and /new locked,
placeholders filled or reported, the limits. The editor screens, the slash menu, the live test and the AI help are not here (browser tests, not built).

Run: python3 dev/run_tests.py test_ask_shortcuts_node
Quick tier: no browser. Bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "askshortcuts_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}
GOOD = '{name:"check",menu:"Check it",text:"Look at {item}",scope:"item",result:"answer"}'
BI = '[{name:"history",menu:"h",text:"",scope:"anywhere",result:"answer",builtin:true,locked:true},' \
     '{name:"who",menu:"Who owns",text:"Who owns {item}?",scope:"item",result:"answer",builtin:true}]'


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "as.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=AS", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def js(expr, timeout=None):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconst B=%s;const T=(f)=>{try{return f()}catch(e){return 'ERR '+e.message}};\nconsole.log(JSON.stringify(%s));" % (BI, expr), encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True, timeout=timeout)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


class Names(unittest.TestCase):
    def test_each_rule_gives_its_message(self):
        self.assertEqual(js('AS.nameProblem("a")'), "The name needs at least 2 characters.")
        self.assertEqual(js('AS.nameProblem("a".repeat(25))'), "The name can be at most 24 characters.")
        self.assertEqual(js('AS.nameProblem("Check")'), "Use lower case letters only in the name.")
        self.assertEqual(js('AS.nameProblem("my check")'), "The name cannot have spaces. Use a hyphen instead.")
        self.assertEqual(js('AS.nameProblem("1ab")'), "The name must start with a letter.")
        self.assertEqual(js('AS.nameProblem("a_b")'), "The name can have only lower case letters, numbers and hyphens.")
        self.assertIn("built-in", js('AS.nameProblem("who",[],"",B)'))
        self.assertIn("already have", js('AS.nameProblem("check",["check"],"",B)'))

    def test_good_names_are_accepted(self):
        for n in ("ab", "check-2", "a" * 24, "q1-report"):
            self.assertEqual(js('AS.nameProblem(%s,[],"",B)' % json.dumps(n)), "")
        self.assertEqual(js('AS.nameProblem("check",["check"],"check",B)'), "")


class Builtins(unittest.TestCase):
    def test_saving_a_built_in_makes_your_version_and_reset_restores_the_original(self):
        r = js('(()=>{const m=AS.save([],{builtin:true,name:"who",menu:"New",text:"Different",scope:"anywhere",result:"changes"},B);'
               'const l=AS.listAll(m,B).builtIn.find(b=>b.name==="who");const back=AS.listAll(AS.reset(m,"who"),B).builtIn.find(b=>b.name==="who");return [m.length,l.edited,l.text,back.text,back.scope,back.result,!!back.edited]})()')
        self.assertEqual(r, [1, True, "Different", "Who owns {item}?", "item", "answer", False])

    def test_a_built_ins_name_cannot_change(self):
        r = js('(()=>{const m=AS.save([],{builtin:true,name:"who",menu:"x",text:"y",scope:"anywhere",result:"answer"},B);return m[0].name+m[0].replaces})()')
        self.assertEqual(r, "whowho")

    def test_history_and_new_are_locked(self):
        self.assertIn("action", js('T(()=>AS.save([],{builtin:true,name:"history",menu:"x",text:"y",scope:"anywhere",result:"answer"},B))'))
        self.assertIn("action", js('T(()=>AS.copy([],{builtin:true,name:"history"},B))'))

    def test_make_a_copy_leaves_the_built_in_alone_and_names_it_check_2(self):
        r = js('(()=>{const m=AS.copy([],{builtin:true,name:"who"},B);const m2=AS.copy(m,{builtin:true,name:"who"},B);return [m.map(x=>x.name),m2.map(x=>x.name),AS.listAll(m,B).builtIn.find(b=>b.name==="who").edited||false,m[0].replaces||null]})()')
        self.assertEqual(r, [["who-2"], ["who-2", "who-3"], False, None])

    def test_copy_of_a_24_character_name_ends_and_stays_within_24(self):
        """The name was cut back to the same name after the suffix, so the search for a free one never ended. A 10 s limit makes a hang a failure."""
        n = "a" * 24
        try:
            r = js('(()=>{const s={name:"%s",menu:"m",text:"t",scope:"anywhere",result:"answer"};let m=[s];for(let k=0;k<3;k++)m=AS.copy(m,s,B);return m.map(x=>x.name)})()' % n, timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("copy() of a 24-character name did not end")
        self.assertEqual(r, [n, "a" * 22 + "-2", "a" * 22 + "-3", "a" * 22 + "-4"])
        self.assertTrue(all(len(x) <= 24 for x in r))
        self.assertEqual([js('AS.nameProblem(%s,[],"",B)' % json.dumps(x)) for x in r[1:]], ["", "", ""])

    def test_remove_is_yours_only(self):
        self.assertEqual(js('AS.remove([%s],"check").length' % GOOD), 0)
        self.assertIn("Only your own", js('T(()=>AS.remove([],"who"))'))


class Limits(unittest.TestCase):
    def test_twenty_shortcuts_at_most(self):
        many = "[" + ",".join('{name:"aa-%d",menu:"m",text:"t",scope:"anywhere",result:"answer"}' % i for i in range(20)) + "]"
        self.assertIn("20 slash commands", js('T(()=>AS.save(%s,%s,B))' % (many, GOOD)))
        self.assertIn("20 slash commands", js('T(()=>AS.copy(%s,{name:"aa-1"},B))' % many))

    def test_lengths_say_why(self):
        self.assertEqual(js('AS.problems({...%s,menu:"m".repeat(71)},[],B)[0]' % GOOD), "The line in the menu can be at most 70 characters.")
        self.assertEqual(js('AS.problems({...%s,text:"t".repeat(1001)},[],B)[0]' % GOOD), "The instructions can be at most 1,000 characters.")
        self.assertEqual(js('AS.problems(%s,[],B)' % GOOD), [])
        self.assertTrue(js('AS.problems({...%s,text:"  "},[],B).length' % GOOD))


class Placeholders(unittest.TestCase):
    def test_filled_when_run(self):
        item = '{id:"A-1",title:"Plan",owner:"Priya",due:"01-12-2026",status:"open",update:"ok"}'
        self.assertEqual(js('AS.fill({text:"{item}|{owner}",scope:"item"},{item:%s})' % item),
                         {"text": "A-1, Plan, Priya, 01-12-2026, open, ok|Priya", "notSet": []})
        self.assertEqual(js('AS.fill({text:"{section}",scope:"section"},{section:"Risks"})')["text"], "Risks")
        self.assertEqual(js('AS.fill({text:"{today}",scope:"anywhere"},{today:new Date(2026,10,7)})')["text"], "07-11-2026")
        self.assertEqual(js('AS.fill({text:"{input}",scope:"anywhere"},{input:"Priya"})')["text"], "Priya")

    def test_an_empty_one_is_reported_not_sent_as_the_word(self):
        r = js('AS.fill({text:"Who: {input} {item}",scope:"anywhere"},{input:""})')
        self.assertEqual(r["notSet"], ["input", "item"])
        self.assertNotIn("{", r["text"])
        self.assertEqual(js('AS.unfillable({text:"{item} {section} {today}",scope:"anywhere"})'), ["item", "section"])


OWN = 'menu:"m",text:"t",scope:"anywhere",result:"answer"'


class Killers(unittest.TestCase):
    """Added after the mutation sweep (~/ag/p1-1295-mutants.md): each test kills a survivor of the first 11 tests."""

    def test_default_built_ins_lock_history_and_new(self):
        for n in ("history", "new"):
            self.assertIn("action", js('T(()=>AS.save([],{builtin:true,name:"%s",%s}))' % (n, OWN)))
            self.assertIn("action", js('T(()=>AS.copy([],{builtin:true,name:"%s"}))' % n))

    def test_a_missing_name_and_unknown_built_in(self):
        self.assertIn("at least 2", js("AS.nameProblem(undefined)"))
        self.assertIn("No built-in", js('T(()=>AS.save([],{builtin:true,name:"nope",%s},B))' % OWN))

    def test_exact_limits_are_allowed_and_empty_or_unknown_choices_refused(self):
        self.assertEqual(js('AS.problems({...%s,menu:"m".repeat(70)},[],B)' % GOOD), [])
        self.assertEqual(js('AS.problems({...%s,text:"t".repeat(1000)},[],B)' % GOOD), [])
        self.assertIn("in the menu", js('AS.problems({...%s,menu:" "},[],B)[0]' % GOOD))
        self.assertIn("where it appears", js('AS.problems({...%s,scope:"x"},[],B)[0]' % GOOD))
        self.assertIn("what you get", js('AS.problems({...%s,result:"x"},[],B)[0]' % GOOD))
        for sc in ("usecase",):
            self.assertEqual(js('AS.problems({...%s,scope:"%s"},[],B)' % (GOOD, sc)), [])
        self.assertEqual(js('AS.problems({...%s,result:"draft"},[],B)' % GOOD), [])

    def test_save_refuses_a_bad_shortcut_and_keeps_ai_and_rename(self):
        self.assertEqual(js('T(()=>AS.save([],{name:"x",%s},B))' % OWN)[:3], "ERR")
        self.assertTrue(js('AS.save([],{name:"ab",ai:true,%s},B)[0].ai' % OWN))
        self.assertEqual(js('AS.save([%s],{name:"renamed",was:"check",%s},B).map(x=>x.name)' % (GOOD, OWN)), ["renamed"])
        self.assertEqual(js('AS.save([{name:"who",%s}],{name:"who",was:"who",%s},B).length' % (OWN, OWN)), 1)

    def test_the_twenty_counts_only_your_own(self):
        own19 = ",".join('{name:"aa-%d",%s}' % (i, OWN) for i in range(19))
        over = '{name:"who",replaces:"who",%s}' % OWN
        self.assertEqual(js('AS.save([%s,%s],{name:"zz",%s},B).length' % (own19, over, OWN)), 21)
        own20 = "[" + ",".join('{name:"aa-%d",%s}' % (i, OWN) for i in range(20)) + "]"
        self.assertEqual(js('AS.save(%s,{builtin:true,name:"who",%s},B).length' % (own20, OWN)), 21)
        self.assertEqual(js('AS.copy([%s,%s],{name:"aa-1"},B).length' % (own19, over)), 21)

    def test_the_list_hides_the_replacing_record_and_marks_the_built_in(self):
        r = js('(()=>{const m=AS.save([%s],{builtin:true,name:"who",%s},B);const l=AS.listAll(m,B);return [l.yours.map(x=>x.name),l.builtIn.find(b=>b.name==="who").builtin]})()' % (GOOD, OWN))
        self.assertEqual(r, [["check"], True])

    def test_remove_does_not_take_a_built_ins_version(self):
        self.assertIn("Only your own", js('T(()=>AS.remove([{name:"who",replaces:"who",%s}],"who"))' % OWN))

    def test_copy_details(self):
        self.assertEqual(js('AS.copy([{name:"check-2",%s,result:"draft"}],{name:"check-2"},B).map(x=>[x.name,x.result])' % 'menu:"m",text:"t",scope:"anywhere"')[1], ["check-3", "draft"])
        self.assertEqual(js('AS.copy([],{builtin:true,name:"who"},[{name:"who",menu:"m",text:"t",scope:"anywhere",result:"answer",builtin:true},{name:"who-2",menu:"m",text:"t",scope:"anywhere",result:"answer",builtin:true}])[0].name'), "who-3")
        self.assertEqual(js('T(()=>AS.copy([],{name:"zz"},B))'), "ERR Nothing to copy.")
        self.assertLessEqual(len(js('AS.copy([{name:%s,%s}],{name:%s},B)[1].name' % ((json.dumps("a" * 23),) + (OWN,) + (json.dumps("a" * 23),)))), 24)
        r = js('AS.copy(AS.save([],{builtin:true,name:"who",menu:"Mine",text:"My text",scope:"anywhere",result:"draft"},B),{builtin:true,name:"who"},B)')
        self.assertEqual([r[1]["text"], r[1]["result"]], ["My text", "draft"])

    def test_fill_details(self):
        d = "AS.fill({text:\"{today}\",scope:\"anywhere\"},{today:new Date(2026,0,5)}).text"
        self.assertEqual(js(d), "05-01-2026")
        self.assertEqual(js('AS.fill({text:"{item}",scope:"item"},{item:{id:"A",title:"T"}}).text'), "A, T")
        for k, sc in (("item", "section"), ("owner", "section"), ("section", "item"), ("item", "usecase")):
            r = js('AS.fill({text:"{%s}",scope:"%s"},{item:{id:"A",owner:"P"},section:"S"})' % (k, sc))
            self.assertEqual(r, {"text": "[not set]", "notSet": [k]})
        r = js('AS.fill({text:"{input} {input}",scope:"anywhere"},{})')
        self.assertEqual(r, {"text": "[not set] [not set]", "notSet": ["input"]})

    def test_unfillable_details(self):
        self.assertEqual(js('AS.unfillable({text:"{owner} {item} {item}",scope:"section"})'), ["owner", "item"])
        self.assertEqual(js('AS.unfillable({text:"{item} {owner}",scope:"item"})'), [])


class KillersRound1(unittest.TestCase):
    """The survivors of the one mutation sweep of askShortcuts.js (history and new are built-ins, digit 9 in a name, the first problem is the one raised, the 20 limit exactly, copy and remove pick the named one)."""

    def test_history_and_new_are_locked_built_ins(self):
        self.assertEqual(js('AS.BUILTINS.filter((b) => b.locked).map((b) => [b.name, b.builtin, b.locked])'), [["history", True, True], ["new", True, True]])

    def test_a_name_may_hold_every_digit(self):
        for n in ("a09", "ab9", "a-9", "z98"):
            self.assertEqual(js('AS.nameProblem("%s")' % n), "", n)

    def test_save_raises_the_first_problem_not_the_second(self):
        msg = js('T(()=>AS.save([],{name:"Ab",menu:"",text:"",scope:"anywhere",result:"answer"},B))')
        self.assertIn("lower case", msg)
        self.assertNotIn("Say what", msg)

    def test_the_twenty_first_own_shortcut_is_refused_by_save_and_copy(self):
        own20 = "[" + ",".join('{name:"aa-%d",%s}' % (i, OWN) for i in range(20)) + "]"
        self.assertIn("You can keep 20", js('T(()=>AS.save(%s,{name:"zz",%s},B))' % (own20, OWN)))
        self.assertIn("You can keep 20", js('T(()=>AS.copy(%s,{name:"aa-1"},B))' % own20))
        own19 = "[" + ",".join('{name:"aa-%d",%s}' % (i, OWN) for i in range(19)) + "]"
        self.assertEqual(js('AS.save(%s,{name:"zz",%s},B).length' % (own19, OWN)), 20)
        self.assertEqual(js('AS.copy(%s,{name:"aa-1"},B).length' % own19), 20)

    def test_copy_and_remove_act_on_the_named_one_among_several(self):
        three = '[{name:"alpha",%s,text:"first"},{name:"beta",%s,text:"second"},{name:"who",replaces:"who",%s,text:"mine"}]' % (OWN.replace(',text:"t"', ""), OWN.replace(',text:"t"', ""), OWN.replace(',text:"t"', ""))
        self.assertEqual(js('AS.copy(%s,{name:"beta"},B)[3].text' % three), "second")
        self.assertEqual(js('AS.remove(%s,"alpha").map((x) => x.name)' % three), ["beta", "who"])
        self.assertEqual(js('AS.remove(%s,"beta").map((x) => x.name)' % three), ["alpha", "who"])


class KillersRound2(unittest.TestCase):
    """Second independent sweep (~/ag/1883-killers.md): the locked sentences whole, a second save of a built-in replaces the first, a taken name is found on a rename, reset returns the records, and a copy keeps hyphens inside the name."""

    def test_the_locked_sentences_are_whole(self):
        self.assertEqual(js('T(()=>AS.save([],{builtin:true,name:"history",%s},B))' % OWN), "ERR /history is an action, not a question, so it cannot be edited.")
        self.assertEqual(js('T(()=>AS.copy([],{builtin:true,name:"history"},B))'), "ERR /history is an action, not a question, so it cannot be copied.")

    def test_saving_a_built_in_twice_keeps_one_version(self):
        r = js('(()=>{const a=AS.save([],{builtin:true,name:"who",menu:"One",text:"t1",scope:"anywhere",result:"answer"},B);'
               'const b=AS.save(a,{builtin:true,name:"who",menu:"Two",text:"t2",scope:"anywhere",result:"answer"},B);return [b.length,b[0].text]})()')
        self.assertEqual(r, [1, "t2"])

    def test_a_rename_onto_a_name_you_already_have_is_refused(self):
        self.assertIn("already have", js('T(()=>AS.save([%s,{name:"other",%s}],{name:"check",was:"other",%s},B))' % (GOOD, OWN, OWN)))

    def test_reset_returns_the_other_records_themselves(self):
        self.assertEqual(js('AS.reset([{name:"check",%s},{name:"who",replaces:"who",%s}],"who")' % (OWN, OWN)),
                         [{"name": "check", "menu": "m", "text": "t", "scope": "anywhere", "result": "answer"}])

    def test_copy_keeps_a_hyphen_inside_the_name_and_only_drops_a_trailing_number(self):
        self.assertEqual(js('AS.copy([{name:"q1-report",%s}],{name:"q1-report"},B)[1].name' % OWN), "q1-report-2")
        self.assertEqual(js('AS.copy([{name:"a-1-b",%s}],{name:"a-1-b"},B)[1].name' % OWN), "a-1-b-2")


if __name__ == "__main__":
    unittest.main()


class BuiltinsAreTheMenus(unittest.TestCase):
    """Row 1295: the built-in slash commands the rules know are the ones the / menu lists (edit/askSlash.js COMMANDS), with the same menu line and question."""

    def test_names_menu_lines_and_questions_agree(self):
        src = (PAGE_SRC / "edit" / "askSlash.js").read_text(encoding="utf-8")
        words = (PAGE_SRC / "edit" / "askWords.js").read_text(encoding="utf-8")
        hints = dict(re.findall(r'^  ([a-z]+): "([^"]+)",$', words.split("export const SLASH_HINT = {", 1)[1].split("};", 1)[0], re.M))
        menu = re.findall(r'\{ name: "([a-z]+)", hint: W\.SLASH_HINT\.[a-z]+,(?: ask: "([^"]+)"| act: "([a-z]+)") \}', src)
        got = js('AS.BUILTINS.map((b) => [b.name, b.menu, b.text])')
        self.assertEqual(got, [[n, hints[n], ask] for n, ask, _ in menu])
        self.assertEqual([n for n, _, act in menu if act], ["history", "new"])


class TheMenuFeed(unittest.TestCase):
    """Row 1295: what the / menu gets from the person's files (edit/askOwn.js menuCommands, askSlash.js withOwn)."""
    REC = '{name:"monday",menu:"Monday summary",text:"Overdue by owner on {today}",scope:"anywhere",result:"answer"}'

    def test_an_own_command_is_filled_with_today_and_marked_yours(self):
        got = js('AS.menuCommands({all:[%s],project:[]}, new Date(2026,10,17))' % self.REC)
        self.assertEqual(got, [{"name": "monday", "hint": "Monday summary", "ask": "Overdue by owner on 17-11-2026", "own": True}])

    def test_today_without_a_second_argument_follows_the_pinned_day_and_the_clock_when_unpinned(self):
        """Row 2032: todayDate() reads the pinned day (pinToday) and the clock again once the pin is cleared."""
        run = 'AS.menuCommands({all:[%s],project:[]})[0].ask'
        self.assertEqual(js('(()=>{AS.pinToday("2026-02-03");return ' + run % self.REC + '})()'), "Overdue by owner on 03-02-2026")
        clock = js('(()=>{AS.pinToday("2026-02-03");AS.pinToday("");return ' + run % self.REC + '})()')
        self.assertNotIn("03-02-2026", clock)
        now = js('(()=>{const d=new Date();return String(d.getDate()).padStart(2,"0")+"-"+String(d.getMonth()+1).padStart(2,"0")+"-"+d.getFullYear()})()')
        self.assertEqual(clock, "Overdue by owner on " + now)

    def test_only_what_runs_from_the_box_as_it_is_is_listed(self):
        recs = ",".join('{...%s,name:"%s",%s}' % (self.REC, n, extra) for n, extra in (("a-item", 'scope:"item"'), ("a-chg", 'result:"changes"'), ("a-inp", 'text:"Who is {input}"')))
        self.assertEqual(js('AS.menuCommands({all:[%s],project:[]}).map((m) => m.name)' % recs), [])

    def test_a_project_command_wins_over_the_same_name_for_all_projects(self):
        got = js('AS.menuCommands({all:[%s],project:[{...%s,menu:"Own line"}]}).map((m) => [m.name, m.hint])' % (self.REC, self.REC))
        self.assertEqual(got, [["monday", "Own line"]])

    def test_an_edited_built_in_replaces_the_question_and_is_not_marked_yours(self):
        mine = '{name:"check",replaces:"check",menu:"My check",text:"Check my way",scope:"anywhere",result:"answer"}'
        own = js('AS.menuCommands({all:[%s],project:[]})' % mine)
        self.assertEqual(own, [{"name": "check", "hint": "My check", "ask": "Check my way", "own": False}])
        menu = js('AS.withOwn(AS.menuCommands({all:[%s],project:[]})).map((c) => [c.name, c.hint, c.ask || c.act])' % mine)
        self.assertEqual(menu[0], ["check", "My check", "Check my way"])
        self.assertEqual([m[0] for m in menu], ["check", "summary", "overdue", "risks", "milestones", "usecases", "history", "new"])

    def test_a_new_one_follows_the_built_ins_and_a_typed_prefix_filters(self):
        menu = js('AS.slashMatches("/m", false, AS.menuCommands({all:[%s],project:[]})).map((c) => c.name)' % self.REC)
        self.assertEqual(menu, ["milestones", "monday"])
        self.assertEqual(js('AS.slashMatches("/", false, []).length'), 8)

    def test_the_built_in_questions_are_answers_that_may_be_anywhere_and_an_act_is_kept_by_its_name(self):
        """Row 1295 mutation sweep: BUILTINS' scope and result, and withOwn keeping a built-in act when a name clashes."""
        self.assertEqual(js('AS.BUILTINS.map((b) => [b.scope, b.result, b.builtin])'), [["anywhere", "answer", True]] * 8)
        self.assertEqual(js('AS.withOwn([{name:"history",hint:"x",ask:"y"}]).find((c) => c.name === "history").act'), "history")

    def test_history_and_new_cannot_be_replaced(self):
        mine = '{name:"history",replaces:"history",menu:"x",text:"y",scope:"anywhere",result:"answer"}'
        self.assertEqual(js('AS.menuCommands({all:[%s],project:[]})' % mine), [])
