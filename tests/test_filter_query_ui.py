"""Issue 662 steps 4 and 5: the filter line box's pure parts (logic/filterQueryUi.js): the pieces a typed line is drawn in, the words for
a token that cannot be used, the rows a line shows, and the autocomplete list with what choosing a row does to the text.

Run: python3 dev/run_tests.py test_filter_query_ui
Quick tier: no browser. The module is bundled by the pinned esbuild and run in node (skipped when node is not on the machine).
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from _paths import ROOT, SRC, TOOLS

import sys
sys.path.insert(0, str(TOOLS))
import build_page  # noqa: E402
import esbuild  # noqa: E402

ENTRY = ROOT / "tests" / "fixtures" / "filterqueryui_node.js"
PAGE_SRC = SRC / "clark" / "page" / "src"
_BUNDLE = {}


def bundle():
    if "code" not in _BUNDLE:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "fqui.js"
            done = esbuild.run(["--bundle", "--format=iife", "--global-name=Q", "--target=es2020", "--charset=utf8", "--tsconfig-raw={}",
                                *build_page.preact_flags(), f"--alias:@src={PAGE_SRC}", str(ENTRY), f"--outfile={out}"],
                               cwd=tmp, capture_output=True, text=True)
            assert done.returncode == 0, done.stderr
            _BUNDLE["code"] = out.read_text(encoding="utf-8")
    return _BUNDLE["code"]


def run_node(probe):
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("no node")
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / "probe.js"
        script.write_text(bundle() + ";\nconsole.log(JSON.stringify(" + probe + "));", encoding="utf-8")
        done = subprocess.run([node, str(script)], capture_output=True, text=True)
        assert done.returncode == 0, done.stderr
        return json.loads(done.stdout)


def lit(x):
    return json.dumps(x)


ROWS = [
    {"id": "T-A-001", "kind": "action", "title": "Draft the plan", "status": "Open", "owner": "Owner One", "priority": "High", "workstream": "Build", "uc": "", "milestone": "", "client": False, "due_date": "2026-10-20"},
    {"id": "T-A-002", "kind": "action", "title": "Book the room", "status": "Closed", "owner": "", "priority": "Low", "workstream": "", "uc": "", "milestone": "", "client": True, "due_date": None},
    {"id": "T-R-001", "kind": "risk", "title": "Supplier slips", "status": "Open", "owner": "Owner Two", "priority": "Urgent", "workstream": "Data", "uc": "", "milestone": "", "client": False, "due_date": None},
]
CTX = {"today": "2026-10-29", "me": "Owner One"}


def sug(text, caret=None, extra=None):
    caret = len(text) if caret is None else caret
    return run_node(f"Q.suggestions({lit(text)}, {caret}, {lit(ROWS)}, {lit(CTX)}, {lit(extra or [])})")


FIELDS = "You can filter by type:, status:, owner:, priority:, due:, workstream:, usecase:, milestone:, client: and is:, or type plain words to search titles."

class Pieces(unittest.TestCase):
    def pieces(self, line, caret=None):
        c = "undefined" if caret is None else str(caret)
        return run_node(f"(() => {{ const p = Q.parseFor({lit(line)}, {lit(ROWS)}, {lit(CTX)}); return Q.pieces({lit(line)}, p, {c}); }})()")

    def test_the_pieces_are_exactly_the_line(self):
        for line in ("", "  a  status:Open,Pending  priority:\"High\" -owner:@me stat:x ", 'has:owner "two words" is:open'):
            self.assertEqual("".join(p["text"] for p in self.pieces(line)), line)

    def test_field_names_are_plain_and_values_are_chips(self):
        p = self.pieces("status:Open,Pending foo")
        self.assertEqual([(x["cls"], x["text"]) for x in p],
                         [("fld", "status:"), ("val", "Open"), ("sep", ","), ("val", "Pending"), ("gap", " "), ("txt", "foo")])

    def test_single_select_values_carry_their_colour(self):
        tones = {x["text"]: x.get("tone") for x in self.pieces("priority:Urgent,Medium,Low status:Closed,Delayed owner:Owner") if x["cls"] == "val"}
        self.assertEqual(tones["Urgent"], "r")
        self.assertEqual(tones["Medium"], "a")
        self.assertEqual(tones["Low"], "g")
        self.assertEqual(tones["Closed"], "n")
        self.assertEqual(tones["Delayed"], "a")
        self.assertEqual(tones["Owner"], "")

    def test_an_unusable_token_is_an_error_piece_with_its_words(self):
        p = [x for x in self.pieces("stat:x opn") if x["cls"] == "err"]
        self.assertEqual([(x["text"], x["message"]) for x in p], [("stat:x", "There is no \u201cstat\u201d filter. Did you mean status? "+FIELDS)])

    def test_a_token_still_being_typed_is_not_marked_while_the_caret_is_in_it(self):
        self.assertEqual([x["cls"] for x in self.pieces("status:", 7)], ["txt"])
        self.assertEqual([x["cls"] for x in self.pieces("status:", None)], ["err"])
        self.assertEqual([x["cls"] for x in self.pieces("status: type:action", 19)], ["err", "gap", "fld", "val"])


class Chips(unittest.TestCase):
    """Row 845: the complete filters of a line are chips; the box keeps the rest."""

    def split(self, line):
        return run_node(f"Q.splitLine({lit(line)}, {lit(ROWS)}, {lit(CTX)})")

    def test_a_line_is_cut_into_its_filters_and_the_rest(self):
        self.assertEqual(self.split('is:open status:Open,Pending supplier stat:x owner:"Owner One"'),
                         {"chips": ["is:open", "status:Open,Pending", 'owner:"Owner One"'], "rest": "supplier stat:x"})
        self.assertEqual(self.split(""), {"chips": [], "rest": ""})
        self.assertEqual(self.split("status:"), {"chips": [], "rest": "status:"})

    def test_the_chips_and_the_box_are_one_line_again(self):
        self.assertEqual(run_node("Q.joinLine(['is:open', 'no:owner'], 'foo')"), "is:open no:owner foo")
        self.assertEqual(run_node("Q.joinLine(['is:open'], '')"), "is:open")
        self.assertEqual(run_node("Q.joinLine([], 'foo')"), "foo")

    def test_a_filter_the_caret_has_moved_past_becomes_a_chip(self):
        c = lambda text, caret: run_node(f"Q.commitDraft({lit(text)}, {caret}, {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual(c("status:Open ", 12), {"chips": ["status:Open"], "text": "", "caret": 0})
        self.assertEqual(c("foo status:Open bar", 19), {"chips": ["status:Open"], "text": "foo bar", "caret": 7})
        self.assertEqual(c("status:Open", 11), {"chips": [], "text": "status:Open", "caret": 11}, "the word still being typed stays")
        self.assertEqual(c("stat:x ", 7), {"chips": [], "text": "stat:x ", "caret": 7}, "a word that cannot be used stays, with its message")
        self.assertEqual(c("status: ", 8), {"chips": [], "text": "status: ", "caret": 8})
        self.assertEqual(c("foo ", 4), {"chips": [], "text": "foo ", "caret": 4}, "a plain word stays")

    def test_a_value_row_counts_the_items_it_would_leave_with_the_chips_on_other_fields(self):
        opts = [{"kind": "value", "ins": "status:Open", "label": "Open", "close": True}, {"kind": "value", "ins": "status:Closed", "label": "Closed", "close": True},
                {"kind": "field", "ins": "owner:", "label": "owner:", "close": False}]
        out = run_node(f"Q.withCounts({lit(opts)}, ['status:Closed', 'priority:High'], {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual([o.get("n") for o in out], [1, 0, None], "Open and High: one item; Closed replaces the chip on its own field, High is not Closed's: none")

    def test_a_chips_remove_button_is_named_by_its_field(self):
        n = lambda chip: run_node(f"Q.chipName({lit(chip)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertEqual(n("status:Open"), "Status")
        self.assertEqual(n("-owner:none"), "Owner")
        self.assertEqual(n("is:open"), "is")
        self.assertEqual(n("no:owner"), "no")


class Words(unittest.TestCase):
    def say(self, line):
        return run_node(f"Q.parseFor({lit(line)}, {lit(ROWS)}, {lit(CTX)}).errors.map(Q.messageOf)")

    def test_each_approved_sentence(self):
        self.assertEqual(self.say("stat:x"), ["There is no \u201cstat\u201d filter. Did you mean status? "+FIELDS])
        self.assertEqual(self.say("zzzzzz:x"), ["There is no \u201czzzzzz\u201d filter. "+FIELDS])
        self.assertEqual(self.say("is:opn"), ["Unknown state 'opn'. Did you mean open?"])
        self.assertEqual(self.say("status:"), ["Add a value after 'status:'."])
        self.assertEqual(self.say("has:zzzzzz"), ["Unknown field 'zzzzzz'."])

    def test_ambiguous_says_to_use_the_full_name(self):
        out = run_node(f"Q.messageOf({{code: 'ambiguous-field', name: 'phase'}})")
        self.assertEqual(out, "'phase' could mean more than one field. Use the full name.")

    def test_an_unknown_state_with_no_near_word_still_gets_a_sentence(self):
        self.assertEqual(self.say("is:zzzzzz"), ["Unknown state 'zzzzzz'."])
        self.assertEqual(self.say("is:qqqqqqqq"), ["Unknown state 'qqqqqqqq'."])

    def test_a_very_long_field_name_is_answered_at_once(self):
        out = run_node(f"(() => {{ const t = Date.now(); const m = Q.parseFor({lit('x' * 200000 + ':1')}, {lit(ROWS)}, {lit(CTX)}).errors.map(Q.messageOf); return [m.length, Date.now() - t < 300]; }})()")
        self.assertEqual(out[0], 1)
        self.assertTrue(out[1])

    def test_the_page_cannot_answer_some_states_yet(self):
        self.assertEqual(len(self.say("is:needed")), 1)                  # an error (the token filters nothing), with no approved sentence

    def test_the_schema_follows_archived_ready_on_the_same_rows(self):
        """Item 1067: is:archived is a word only where the page answers it; the cached schema must not outlive a change of that flag."""
        probe = (f"(() => {{ const r = {lit(ROWS)}; const n = (c) => Q.parseFor('is:archived', r, c).errors.length;"
                 f" return [n({lit(CTX)}), n({lit(dict(CTX, archivedReady=True))}), n({lit(CTX)})]; }})()")
        self.assertEqual(run_node(probe), [1, 0, 1])

    def test_me_with_no_name_is_noticed(self):
        for ctx, want in ((CTX, False), ({"today": "2026-10-29", "me": ""}, True)):
            for line, asks in (("owner:@me", True), ("owner:me", True), ("status:Open", False)):
                got = run_node(f"Q.wantsMe(Q.parseFor({lit(line)}, {lit(ROWS)}, {lit(ctx)}), {lit(ctx)})")
                self.assertEqual(got, want and asks, (line, ctx))


class Rows(unittest.TestCase):
    def ids(self, line, ctx=CTX):
        return run_node(f"Q.rowsFor({lit(ROWS)}, {lit(line)}, {lit(ctx)}).map((r) => r.id)")

    def test_a_line_shows_its_rows(self):
        self.assertEqual(self.ids(""), ["T-A-001", "T-A-002", "T-R-001"])
        self.assertEqual(self.ids("is:open owner:@me"), ["T-A-001"])
        self.assertEqual(self.ids("status:NoSuchStatus"), [])
        self.assertEqual(self.ids("stat:Open"), ["T-A-001", "T-A-002", "T-R-001"])          # an unknown field filters nothing
        self.assertEqual(self.ids("t-r-001"), ["T-R-001"])                                    # free text also matches the ID

    def test_the_switches_edit_the_text_and_keep_the_rest_as_typed(self):
        w = lambda call: run_node(call)
        self.assertEqual(w(f"Q.withMode('type:action foo is:open \"a b\"', 'closed', {lit(ROWS)}, {lit(CTX)})"), 'is:closed type:action foo "a b"')
        self.assertEqual(w(f"Q.withMode('is:open has:owner', 'all', {lit(ROWS)}, {lit(CTX)})"), "has:owner")
        self.assertEqual(w(f"Q.withType('is:open priority:High', 'risk', {lit(ROWS)}, {lit(CTX)})"), "is:open type:risk,issue,assumption,dependency priority:High")
        self.assertEqual(w(f"Q.withType('type:action is:open', 'all', {lit(ROWS)}, {lit(CTX)})"), "is:open")

    def test_a_view_differs_only_when_the_line_means_something_else(self):
        d = lambda a, b: run_node(f"Q.differsQuery({{line: {lit(a)}}}, {lit(b)}, {lit(ROWS)}, {lit(CTX)})")
        self.assertFalse(d("is:open  type:action", "type:action is:open"))
        self.assertFalse(d("status:Open,Pending", "STATUS:pending,open"))
        self.assertTrue(d("is:open", "is:closed"))
        self.assertTrue(d("is:open", ""))


class Autocomplete(unittest.TestCase):
    def test_an_empty_box_lists_every_field_with_its_description(self):
        out = sug("")
        self.assertEqual([o["ins"] for o in out], ["is:", "type:", "status:", "owner:", "priority:", "due:", "workstream:", "usecase:", "milestone:", "client:", "has:", "no:"])
        notes = {o["ins"]: o["note"] for o in out}
        self.assertEqual(notes["status:"], "Where the item has got to")
        self.assertEqual(notes["no:"], "Has no owner, date, workstream…")
        self.assertEqual(notes["has:"], "")                       # no description is approved yet (an open question)
        self.assertTrue(all(o["kind"] == "field" and not o["close"] for o in out))

    def test_custom_fields_follow_the_built_in_ones_and_have_no_description(self):
        out = sug("", None, [{"key": "region", "name": "Sales region"}])
        keys = [o["ins"] for o in out]
        self.assertEqual(keys.index("region:"), keys.index("client:") + 1)
        self.assertEqual(next(o for o in out if o["ins"] == "region:")["note"], "")

    def test_the_list_narrows_as_a_field_is_typed(self):
        self.assertEqual([o["ins"] for o in sug("pr")], ["priority:"])
        self.assertEqual([o["ins"] for o in sug("US")], ["usecase:"])
        self.assertEqual(sug("zzz"), [])

    def test_after_a_colon_the_values_are_led_by_no_has_exclude(self):
        out = sug("status:")
        self.assertEqual([o["label"] for o in out[:4]], ["No Status", "Has Status", "Exclude Status", "Open"])
        self.assertEqual([o["ins"] for o in out[:3]], ["no:status", "has:status", "-status:"])
        self.assertEqual([o["close"] for o in out[:3]], [True, True, False])
        self.assertEqual(sug("usecase:")[0]["label"], "No Use case")

    def test_single_select_values_show_their_colour_and_the_rest_do_not(self):
        pr = {o["label"]: o.get("tone") for o in sug("priority:") if o["kind"] == "value"}
        self.assertEqual(pr, {"Urgent": "r", "High": "r", "Medium": "a", "Low": "g"})
        self.assertTrue(all(not o.get("tone") for o in sug("workstream:") if o["kind"] == "value"))

    def test_values_narrow_as_typed_and_a_value_taken_is_not_offered_again(self):
        self.assertEqual([o["label"] for o in sug("status:pend") if o["kind"] == "value"], ["Pending"])
        self.assertEqual([o["label"] for o in sug("status:Open,") if o["kind"] == "value"][:2], ["Pending", "Delayed"])
        self.assertEqual([o["label"] for o in sug("status:Open,") if o["kind"] == "lead"], [])

    def test_owner_offers_me_as_at_me_and_none_is_a_lead_row_not_a_value(self):
        vals = [o for o in sug("owner:") if o["kind"] == "value"]
        self.assertEqual(vals[0]["ins"], "owner:@me")
        self.assertNotIn("none", [o["label"] for o in vals])

    def test_is_has_and_no_offer_states_or_fields(self):
        self.assertEqual([o["ins"] for o in sug("is:")][:2], ["is:open", "is:closed"])
        self.assertEqual([o["ins"] for o in sug("no:ow")], ["no:owner"])
        self.assertIn("has:priority", [o["ins"] for o in sug("has:")])

    def test_the_word_the_caret_is_in_is_the_one_changed(self):
        self.assertEqual([o["ins"] for o in sug("is:open pr", 10)], ["priority:"])
        self.assertEqual([o["ins"] for o in sug("is:open pr is:closed", 10)], ["priority:"])
        self.assertEqual(run_node('Q.wordAt(\'a "b c" d\', 9)'), {"start": 8, "word": "d"})
        self.assertEqual(run_node('Q.wordAt(\'a "b c\', 6)'), {"start": 2, "word": '"b c'})

    def test_a_half_typed_field_value_goes_whole_when_the_caret_is_right_after_it(self):
        d = lambda text, caret, key="Backspace": run_node(f"Q.dropWordAt({lit(text)}, {caret}, {lit(key)})")
        self.assertEqual(d("status:Open", 11), {"text": "", "caret": 0})
        self.assertEqual(d("fix status:Op", 13), {"text": "fix ", "caret": 4})
        self.assertEqual(d("-owner:Ann x", 10), {"text": "x", "caret": 0})
        self.assertIsNone(d("status:", 7), "a bare field: loses its colon the usual way")
        self.assertIsNone(d("status:Open", 8), "a caret inside the word is the usual one letter")
        self.assertIsNone(d("fix", 3), "a plain word is the usual one letter")
        self.assertEqual(d("status:Open", 11, "Delete"), {"text": "", "caret": 0}, "Delete with nothing after the caret goes whole too")
        self.assertEqual(d("status:Open x", 11), {"text": "x", "caret": 0}, "Backspace right before the space after the word takes the word")
        self.assertIsNone(d("status:Open x", 11, "Delete"), "Delete before a space takes that space, not the word behind the caret")
        self.assertIsNone(d("status:Open ", 12), "Backspace after the space takes the space")

    def test_accepting_a_value_adds_a_space_and_a_field_adds_none(self):
        a = lambda text, caret, opt: run_node(f"Q.accept({lit(text)}, {caret}, {lit(opt)})")
        self.assertEqual(a("is:open sta", 11, {"ins": "status:", "close": False}), {"text": "is:open status:", "caret": 15})
        self.assertEqual(a("status:", 7, {"ins": "status:Open", "close": True}), {"text": "status:Open ", "caret": 12})
        self.assertEqual(a("sta other", 3, {"ins": "status:Open", "close": True}), {"text": "status:Open other", "caret": 12})


class Icons(unittest.TestCase):
    """Row 931: every field row, and the lead rows of a field, carry an icon name; a value keeps its tone dot and has no icon."""
    ICON = {"is": "check", "type": "table", "status": "half", "owner": "user", "priority": "flash", "due": "cal", "workstream": "bars",
            "usecase": "doc", "milestone": "flag", "client": "ext", "has": "eye", "no": "eyeoff"}

    def test_each_field_row_has_the_icon_of_its_field(self):
        rows = sug("")
        self.assertEqual([o["ins"] for o in rows][:2], ["is:", "type:"])
        for o in rows:
            key = o["ins"].rstrip(":")
            if key in self.ICON:
                self.assertEqual(o["icon"], self.ICON[key], key)
            self.assertTrue(o.get("icon"), o["ins"])
        self.assertEqual({o["ins"].rstrip(":") for o in rows} & set(self.ICON), set(self.ICON), "all twelve fields are listed")

    def test_the_lead_rows_show_the_field_icon_and_exclude_a_circle_minus(self):
        lead = {o["label"]: o for o in sug("owner:") if o["kind"] == "lead"}
        self.assertEqual(lead["No Owner"]["icon"], "user")
        self.assertEqual(lead["Has Owner"]["icon"], "user")
        self.assertEqual(lead["Exclude Owner"]["icon"], "circleminus")

    def test_values_keep_their_tone_dot_and_get_no_icon(self):
        vals = [o for o in sug("priority:") if o["kind"] == "value"]
        self.assertTrue(vals)
        for o in vals:
            self.assertNotIn("icon", o)
        self.assertTrue(any(o.get("tone") for o in vals), "the tone dots stay")

    def test_the_fields_listed_after_has_and_no_carry_their_icons(self):
        got = {o["label"]: o.get("icon") for o in sug("has:")}
        self.assertEqual(got["priority"], "flash")

    def test_a_negated_field_row_keeps_the_icon(self):
        self.assertEqual(sug("-sta")[0]["icon"], "half")
