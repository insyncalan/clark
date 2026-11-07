"""Row 985: recent names and search of the people register for the Assign-to picker, src/clark/page/src/logic/assignTo.js, on the real source.

Run: python3 dev/run_tests.py test_assign_recent_logic
assignTo.js is bundled the way the page is (dev/tools/build_page.py's flags) and run in headless Chrome, the page's real engine, with
fictional people. Covers: search over the register (name, alias, email, role) that ignores case and accents, ranks a word that starts with
the typed text before a name that only contains it, never reads the typed text as a pattern, leaves out archived people, caps the list, and
adds this project's names that are not on the register; recents (newest first, distinct, at most RECENT_MAX, never TBC, never a hostile or
over-long name), the recents shown (a person removed from the register is dropped, a renamed one shows the register's name), and what is kept in the
browser (one list per project, and nothing breaks with the storage refused). Chrome is required: it fails, never skips, without it (set CLARK_CHROME).
"""
import json
import tempfile
import unittest
from pathlib import Path

from _paths import SRC
import build_page  # noqa: E402  (dev/tools)
import esbuild  # noqa: E402  (dev/tools)
from test_help_logic import page_target  # noqa: E402
from test_server import CHROME, chrome  # noqa: E402

LOGIC = SRC / "clark" / "page" / "src" / "logic" / "assignTo.js"


def bundled():
    assert LOGIC.is_file(), f"{LOGIC} does not exist yet"
    with tempfile.TemporaryDirectory() as tmp:
        entry, out = Path(tmp) / "entry.js", Path(tmp) / "at.js"
        entry.write_text(f'import * as A from {json.dumps(str(LOGIC))};\nglobalThis.AT = A;\n', encoding="utf-8")
        done = esbuild.run(["--bundle", "--format=iife", "--target=es2020", "--tsconfig-raw={}", *build_page.preact_flags(held=False), str(entry), f"--outfile={out}"],
                           cwd=SRC, capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return out.read_text(encoding="utf-8")


def person(i, name, **kw):
    return {"id": f"P-{i:03d}", "name": name, "email": kw.get("email", ""), "aliases": kw.get("aliases", ""), "role": kw.get("role", ""),
            "organisation": "", "archived": kw.get("archived", 0)}


REGISTER = [person(1, "José Álvarez", email="jose.alvarez@example.com", role="Programme Director"),
            person(2, "Anna García", aliases="Annie G;A. Garcia", role="Analyst"),
            person(3, "Sam Okafor", email="sam@example.com", role="Supplier lead"),
            person(4, "Samantha Reed", role="Analyst"),
            person(5, "Old Timer", archived=1),
            person(6, "Ruth Samson")]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        assert Path(CHROME).is_file(), f"Chrome is needed for the required browser tests: set CLARK_CHROME ({CHROME!r})"
        cls.code = bundled()

    def run_js(self, expr):
        with chrome() as cdp:
            sid = page_target(cdp)
            res = cdp.call("Runtime.evaluate", {"expression": self.code + ";\n(() => { return " + expr + "; })()", "returnByValue": True}, sid)
            self.assertNotIn("exceptionDetails", res, res)
            return res["result"]["value"]

    def find(self, q, names=(), reg=None, limit=None):
        extra = "" if limit is None else ", " + json.dumps(limit)
        return self.run_js("AT.searchPeople(" + json.dumps(REGISTER if reg is None else reg) + ", " + json.dumps(list(names)) + ", "
                           + json.dumps(q) + extra + ").map((r) => r.name)")


class Search(Base):
    def test_an_empty_or_blank_search_finds_nothing_so_the_picker_shows_recents_and_people(self):
        self.assertEqual(self.find(""), [])
        self.assertEqual(self.find("   "), [])

    def test_an_empty_register_and_no_names_finds_nothing(self):
        self.assertEqual(self.find("sam", reg=[]), [])

    def test_case_and_accents_do_not_matter_in_either_direction(self):
        self.assertEqual(self.find("JOSE"), ["José Álvarez"])
        self.assertEqual(self.find("josé"), ["José Álvarez"])
        self.assertEqual(self.find("garcia"), ["Anna García"])
        self.assertEqual(self.find("GARCÍA"), ["Anna García"])
        self.assertEqual(self.find("alvarez"), ["José Álvarez"])

    def test_a_word_that_starts_with_the_text_comes_before_a_name_that_only_contains_it(self):
        got = self.find("sam")
        self.assertEqual(got[:3], ["Sam Okafor", "Samantha Reed", "Ruth Samson"], "word starts first (register order), then contains")
        self.assertEqual(self.find("mson"), ["Ruth Samson"])

    def test_the_search_reads_alias_email_and_role_too(self):
        self.assertEqual(self.find("annie"), ["Anna García"])
        self.assertEqual(self.find("a. garcia"), ["Anna García"])
        self.assertEqual(self.find("jose.alvarez@"), ["José Álvarez"])
        self.assertEqual(self.find("director"), ["José Álvarez"])
        self.assertEqual(self.find("analyst"), ["Anna García", "Samantha Reed"])

    def test_a_name_match_comes_before_an_alias_email_or_role_match(self):
        reg = [person(1, "Zed Role", role="Sam helper"), person(2, "Samuel Name")]
        self.assertEqual(self.find("sam", reg=reg), ["Samuel Name", "Zed Role"])

    def test_an_archived_person_is_never_offered(self):
        self.assertEqual(self.find("old"), [])
        self.assertEqual(self.find("timer"), [])

    def test_this_projects_names_are_searched_and_added_after_the_register(self):
        self.assertEqual(self.find("sam", names=["Sammy Contractor"])[-1], "Sammy Contractor")
        self.assertEqual(self.find("contractor", names=["Sammy Contractor"]), ["Sammy Contractor"])

    def test_a_project_name_that_is_already_a_person_or_an_alias_or_twice_is_drawn_once(self):
        self.assertEqual(self.find("garcia", names=["anna garcía", "Annie G", "ANNA GARCÍA"]), ["Anna García"])
        self.assertEqual(self.find("temp", names=["Temp One", "temp one", "Temp  One"]), ["Temp One"])

    def test_tbc_is_not_a_person_to_find(self):
        self.assertEqual(self.find("tbc", names=["TBC"]), [])

    def test_at_most_eight_are_drawn_and_the_limit_can_be_given(self):
        many = [person(i, f"Pat Number{i:02d}") for i in range(1, 30)]
        self.assertEqual(len(self.find("pat", reg=many)), 8)
        self.assertEqual(len(self.find("pat", reg=many, limit=3)), 3)
        self.assertEqual(self.find("pat", names=[f"Pat Z{i}" for i in range(20)], reg=many)[0], "Pat Number01")

    def test_the_typed_text_is_text_not_a_pattern(self):
        for q in [".*", "(", "[", "\\", "a|b", "^", "$", "(?<x>", "*", "+", "?"]:
            self.assertEqual(self.find(q), [], q)
        self.assertEqual(self.find("a. garcia"), ["Anna García"], "a dot matches only a dot")

    def test_hostile_text_is_inert_and_never_throws(self):
        for q in ["<script>alert(1)</script>", "'; DROP TABLE people;--", "\u0000‮", "😀" * 500, "x" * 100000, "__proto__", "constructor"]:
            self.assertEqual(self.find(q), [], q[:20])

    def test_a_hostile_register_row_is_skipped_or_read_safely(self):
        bad = [None, 5, "x", {}, {"name": None}, {"name": 7}, {"name": "Fine Person", "aliases": None, "email": None, "role": 3},
               person(9, "x" * 300), person(10, "Good‮Name")]
        self.assertEqual(self.find("fine", reg=bad), ["Fine Person"])
        self.assertEqual(self.find("xxx", reg=bad), [], "a name over 200 characters can't be an owner, so it is not offered")
        self.assertEqual(self.find("good", reg=bad), [], "a name with a hidden character is not offered")

    def test_a_very_long_typed_text_matches_nothing_and_a_name_of_200_is_found(self):
        long200 = "L" * 200
        self.assertEqual(self.find("l" * 150, reg=[person(1, long200)]), [long200])
        self.assertEqual(self.find("l" * 5000, reg=[person(1, long200)]), [])

    def test_a_result_says_who_it_is_so_the_picker_can_draw_it(self):
        got = self.run_js("AT.searchPeople(" + json.dumps(REGISTER) + ", ['Sammy Contractor'], 'sam')")
        by = {r["name"]: r for r in got}
        self.assertEqual(by["Sam Okafor"]["id"], "P-003")
        self.assertEqual(by["Sam Okafor"]["listed"], True)
        self.assertEqual(by["Sammy Contractor"]["id"], "")
        self.assertEqual(by["Sammy Contractor"]["listed"], False)

    def test_the_inputs_are_not_changed(self):
        self.assertEqual(self.run_js("(() => { const r = " + json.dumps(REGISTER) + "; const s = JSON.stringify(r); AT.searchPeople(r, ['A'], 'sam'); return s === JSON.stringify(r); })()"), True)


class Recents(Base):
    def add(self, lst, name):
        return self.run_js("AT.addRecent(" + json.dumps(lst) + ", " + json.dumps(name) + ")")

    def test_the_constants_are_five_recents_and_eight_results(self):
        self.assertEqual(self.run_js("[AT.RECENT_MAX, AT.SHOWN]"), [5, 8])

    def test_a_new_name_goes_first(self):
        self.assertEqual(self.add(["Ann", "Bob"], "Cy"), ["Cy", "Ann", "Bob"])
        self.assertEqual(self.add([], "Cy"), ["Cy"])

    def test_a_name_again_moves_to_the_front_once_whatever_its_case_or_spacing(self):
        self.assertEqual(self.add(["Ann", "Bob", "Cy"], "  cy "), ["cy", "Ann", "Bob"])
        self.assertEqual(self.add(["Ann Lee", "Bob"], "ann   LEE"), ["ann LEE", "Bob"])

    def test_only_the_last_five_are_kept(self):
        five = ["A1", "A2", "A3", "A4", "A5"]
        self.assertEqual(self.add(five, "A6"), ["A6", "A1", "A2", "A3", "A4"])
        self.assertEqual(len(self.add(["a", "b", "c", "d", "e", "f", "g"], "h")), 5, "a stored list that is too long is cut too")

    def test_tbc_blank_and_not_text_are_never_remembered(self):
        for bad in ["", "   ", "TBC", "tbc", " Tbc ", None, 7, {}, []]:
            self.assertEqual(self.add(["Ann"], bad), ["Ann"], repr(bad))

    def test_a_hostile_or_over_long_name_is_never_remembered(self):
        for bad in ["x" * 201, "a\u202eb", "a\u0000b", "a\u200bb"]:
            self.assertEqual(self.add(["Ann"], bad), ["Ann"], repr(bad[:10]))
        self.assertEqual(self.add([], "y" * 200), ["y" * 200])

    def test_a_damaged_stored_list_is_read_as_far_as_it_is_sound(self):
        self.assertEqual(self.run_js("AT.addRecent(null, 'Ann')"), ["Ann"])
        self.assertEqual(self.run_js("AT.addRecent('Bob', 'Ann')"), ["Ann"])
        self.assertEqual(self.run_js("AT.addRecent([1, null, 'Bob', {}, 'Bob'], 'Ann')"), ["Ann", "Bob"])

    def test_the_list_given_is_not_changed(self):
        self.assertEqual(self.run_js("(() => { const l = ['A', 'B']; AT.addRecent(l, 'C'); return l.join(); })()"), "A,B")

    def shown(self, recents, names=(), reg=None):
        return self.run_js("AT.shownRecents(" + json.dumps(recents) + ", " + json.dumps(REGISTER if reg is None else reg) + ", " + json.dumps(list(names)) + ")")

    def test_a_person_on_the_register_is_shown_and_one_who_is_gone_is_not(self):
        self.assertEqual(self.shown(["Sam Okafor", "Nobody Here", "Old Timer"]), ["Sam Okafor"])

    def test_an_alias_shows_the_registers_name_once(self):
        self.assertEqual(self.shown(["Annie G", "Anna García", "annie g"]), ["Anna García"])

    def test_a_name_in_this_project_but_not_on_the_register_is_shown_as_typed(self):
        self.assertEqual(self.shown(["Sammy Contractor", "Sam Okafor"], names=["Sammy Contractor"]), ["Sammy Contractor", "Sam Okafor"])
        self.assertEqual(self.shown(["Sammy Contractor"], names=[]), [])

    def test_an_empty_register_shows_only_this_projects_names_and_nothing_breaks(self):
        self.assertEqual(self.shown(["Ann"], reg=[]), [])
        self.assertEqual(self.shown([], reg=[]), [])
        self.assertEqual(self.shown(["Ann"], names=["Ann"], reg=[]), ["Ann"])

    def test_tbc_is_never_shown_and_the_list_is_at_most_five(self):
        reg = [person(i, f"Pat {i}") for i in range(1, 12)]
        got = self.shown(["TBC"] + [f"Pat {i}" for i in range(1, 12)], reg=reg)
        self.assertEqual(got, [f"Pat {i}" for i in range(1, 6)])


FAKE = ("(() => { const m = new Map(); const fake = { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => { m.set(k, String(v)); },"
        " clear: () => m.clear(), key: (i) => Array.from(m.keys())[i], get length() { return m.size; } };"
        " Object.defineProperty(window, 'localStorage', { get: () => fake, configurable: true }); })()")


class Kept(Base):
    def run_js(self, expr):                  # the blank test page has no storage to use: it is given one that is only a Map
        return Base.run_js(self, "(" + FAKE + ", " + expr + ")")

    def test_recents_are_kept_per_project_in_the_browser_newest_first(self):
        got = self.run_js("(() => { window.localStorage.clear(); AT.noteAssigned('ABC', 'Ann'); AT.noteAssigned('ABC', 'Bob'); AT.noteAssigned('XYZ', 'Zed');"
                          " return [AT.loadRecents('ABC'), AT.loadRecents('XYZ'), AT.loadRecents('NONE')]; })()")
        self.assertEqual(got, [["Bob", "Ann"], ["Zed"], []])

    def test_the_stored_text_is_only_names_under_a_clark_key(self):
        got = self.run_js("(() => { window.localStorage.clear(); AT.noteAssigned('ABC', 'Ann'); return [0].every((i) => window.localStorage.key(i).startsWith('clark.')) && window.localStorage.length === 1; })()")
        self.assertTrue(got)

    def test_damaged_stored_text_reads_as_nothing(self):
        got = self.run_js("(() => { window.localStorage.clear(); AT.noteAssigned('ABC', 'Ann'); const k = window.localStorage.key(0);"
                          " const out = []; for (const bad of ['{', 'null', '5', '{\"a\":1}', '\"x\"']) { window.localStorage.setItem(k, bad); out.push(AT.loadRecents('ABC')); } return out; })()")
        self.assertEqual(got, [[], [], [], [], []])

    def test_with_the_storage_refused_nothing_is_kept_nothing_throws_and_the_picker_has_no_recents(self):
        got = self.run_js("(() => { Object.defineProperty(window, 'localStorage', { get() { throw new Error('refused'); }, configurable: true });"
                          " const a = AT.noteAssigned('ABC', 'Ann'); return [AT.loadRecents('ABC'), Array.isArray(a)]; })()")
        self.assertEqual(got[0], [])

    def test_noting_a_name_that_is_not_remembered_leaves_the_stored_list_alone(self):
        got = self.run_js("(() => { window.localStorage.clear(); AT.noteAssigned('ABC', 'Ann'); AT.noteAssigned('ABC', 'TBC'); AT.noteAssigned('ABC', ''); return AT.loadRecents('ABC'); })()")
        self.assertEqual(got, ["Ann"])

    def test_a_hostile_project_code_cannot_reach_another_projects_list(self):
        got = self.run_js("(() => { window.localStorage.clear(); AT.noteAssigned('A', 'Ann'); AT.noteAssigned('A.B', 'Bob'); AT.noteAssigned('__proto__', 'Cy');"
                          " return [AT.loadRecents('A'), AT.loadRecents('A.B'), AT.loadRecents('__proto__')]; })()")
        self.assertEqual(got, [["Ann"], ["Bob"], ["Cy"]])


if __name__ == "__main__":
    unittest.main()
