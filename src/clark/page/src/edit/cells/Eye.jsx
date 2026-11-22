// The eye in the Work items table's Client-visible column (#456; prototype views.js `data-weye`): it shows whether the client sees
// the item, and a click turns that on or off, in View as in Edit (row 819: the Work items page is live). It uses the routes the report's eye already has (changes.py report_hidden: `new`
// hides one item, `delete` shows it again, `pick` shows it and turns its client flag on, and refuses a Sensitive one in plain words),
// so the table adds no new way to write and Undo is the one every step has. The state is the page's mirror of what a publish keeps
// (logic/publishable.js): the flag, the hidden list and the labels that keep an item out.
import { computed } from "@preact/signals";
import { data } from "../../stores/report.js";
import { change } from "../../stores/changes.js";
import { blink } from "../../stores/motion.js";
import { Icon } from "../../components/Icon.jsx";
import { rulesFor, publishable } from "../../logic/publishable.js";
import { tableOf } from "../itemEdit.js";
import { AskAbout } from "../AskAbout.jsx";
import { eyeWords } from "../../logic/eyeWords.js";

const state = computed(() => {
  const d = data.value;
  if (!d) return null;
  const rules = rulesFor({ code: d.project && d.project.code, hidden: (d.report_hidden || []).map((h) => (h && h.item_id) || h), labelRules: d.label_rules || [], labels: d.labels || {} });
  const byId = new Map([...(d.actions || []), ...(d.raid || []), ...(d.decisions || [])].map((r) => [r.id, r]));
  return { rules, byId };
});

// Is the item one the client sees now, and would a click hide it (`hidden` and the flag on: show it again) or pick it (the flag is off)?
export function eyeOf(row) {
  const st = state.value, raw = st && st.byId.get(row.id);
  if (!raw) return { on: !!row.client, back: false };
  return { on: publishable(raw, tableOf(row), st.rules), back: st.rules.hidden.has(row.id) && Number(raw.client_visible) === 1 };
}

export function Eye({ row, card }) {   // `card`: the board's card, whose buttons never use the shared `ib` name (tests/test_ib_scope.py)
  const { on, back } = eyeOf(row);
  const w = eyeWords(on, row);   // row 1195: one string for the label and the announcement after a toggle
  const go = (e) => {
    e.stopPropagation();
    blink(e);
    if (on) change({ kind: "report_hidden", op: "new", id: row.id }, w.said);
    else if (back) change({ kind: "report_hidden", op: "delete", id: row.id }, w.said);
    else change({ kind: "report_hidden", op: "pick", ids: [row.id] }, w.said);
  };
  return (
    <button type="button" class={card ? "weye" : "ib weye"} tabIndex={-1} aria-pressed={on ? "true" : "false"}
      aria-label={w.label} title={w.title} onClick={go}>
      <Icon name={on ? "eye" : "eyeoff"} />
    </button>
  );
}

Eye.Ask = ({ row }) => <AskAbout kind="item" id={row.id} name={`${row.id} ${row.title || ""}`.trim()} />;   // row 1292: the sparkle beside the eye, at the right end of a Work items row (Classic and Edit only: AskAbout draws nothing else)
Eye.isOff = (row) => !eyeOf(row).on;        // row 1268: the list greys a row the client eye has taken off, as the mock-up draws it
Eye.heading = "Client-visible";                // the column's name for a screen reader (the heading is drawn by the table, which holds no word of it)
