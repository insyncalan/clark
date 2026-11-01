// The eye in the Work items table's Client-visible column (#456; prototype views.js `data-weye`): it shows whether the client sees
// the item, and a click in Edit turns that on or off (View shows the mark only). It uses the routes the report's eye already has (changes.py report_hidden: `new`
// hides one item, `delete` shows it again, `pick` shows it and turns its client flag on, and refuses a Sensitive one in plain words),
// so the table adds no new way to write and Undo is the one every step has. The state is the page's mirror of what a publish keeps
// (logic/publishable.js): the flag, the hidden list and the labels that keep an item out.
import { computed } from "@preact/signals";
import { data, mode } from "../../stores/report.js";
import { change } from "../../stores/changes.js";
import { Icon } from "../../components/Icon.jsx";
import { rulesFor, publishable } from "../../logic/publishable.js";
import { tableOf } from "../itemEdit.js";

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

export function Eye({ row }) {
  const { on, back } = eyeOf(row);
  const go = (e) => {
    e.stopPropagation();
    if (on) change({ kind: "report_hidden", op: "new", id: row.id }, `${row.id} hidden from the client.`);
    else if (back) change({ kind: "report_hidden", op: "delete", id: row.id }, `${row.id} shown to the client.`);
    else change({ kind: "report_hidden", op: "pick", ids: [row.id] }, `${row.id} shown to the client.`);
  };
  const words = on ? "Shown to the client" : "Hidden from the client";
  // In View the mark is read only, as every other cell of the table is: no button, no click, no focus stop, and its words in text.
  if (mode.value !== "edit") {
    return (
      <span class={`weye ro${on ? " on" : ""}`} role="img" aria-label={`${words}: ${row.title}`} title={on ? "In client reports" : "Internal only"}>
        <Icon name={on ? "eye" : "eyeoff"} />
      </span>
    );
  }
  return (
    <button type="button" class="ib weye" tabIndex={-1} aria-pressed={on ? "true" : "false"}
      aria-label={`${on ? "Shown to the client" : "Not shown to the client"}: ${row.title}`}
      title={on ? "In client reports. Select to hide" : "Internal only. Select to show the client"} onClick={go}>
      <Icon name={on ? "eye" : "eyeoff"} />
    </button>
  );
}

Eye.heading = "Client-visible";                // the column's name for a screen reader (the heading is drawn by the table, which holds no word of it)
