// Row 1180: what the editor adds to the peek's chip row and Details. `chipPop(row, field)` gives a chip its popover (the table cell's own pickers and the
// same change, request and Undo, in the peek's place so a pick is about this item alone); `ClientLine` is the one clickable Client visible line.
// A published file and the Dashboard in View never reach this file: Peek.jsx draws their chips without a popover.
import { classicTheme } from "../components/Contents.jsx";
import { data } from "../stores/report.js";
import { changeCell, changeNewPerson, changeRating } from "../stores/changes.js";
import { todayIso } from "../workItems.js";
import { canPick, changeFor, newPersonChange, pickField, people, tableOf } from "./itemEdit.js";
import { PICKERS } from "./cells/Cell.jsx";
import { eyeChange } from "../logic/rowMenu.js";
import { Icon } from "../components/Icon.jsx";
import { Matrix } from "./PeekRating.jsx";

const PLACE = "peek";

/** The popover of one chip, `({ anchor, close }) => element`, or null when the field is not a picker (a read-only chip). */
export function chipPop(row, field) {
  if (!canPick(row, field)) return null;
  const Picker = PICKERS[field];
  if ((row.kind === "risk" || row.kind === "issue") && field === "priority") return ({ anchor, close }) => <Matrix row={row} anchor={anchor} onClose={close} />;      // rows 1182 1183: a risk's or an issue's rating is set from impact and likelihood only
  return ({ anchor, close }) => {
    const pick = (value) => {
      const c = changeFor(row, pickField(field, value), value, todayIso());
      if (c && c.error) return c.error;
      close(true);
      if (c) (c.one ? changeRating : changeCell)(tableOf(row), row.id, c.changes, { text: c.words, back: c.back, always: row.kind === "decision" && field === "status" && value === "Made", place: PLACE });
      return "";
    };
    const add = async (person) => {
      const c = newPersonChange(row, person, todayIso());
      if (c && c.error) return { ok: false, message: c.error, code: "", person: null };
      if (!c) { close(true); return { ok: true }; }
      const r = await changeNewPerson(tableOf(row), row.id, c, PLACE);
      if (r.ok) close(true);
      return r;
    };
    return <Picker row={row} place={PLACE} anchor={anchor} today={todayIso()} names={field === "owner" ? people(data.value) : undefined} onPick={pick} onAdd={field === "owner" ? add : undefined} onClose={close} />;
  };
}

/** The Client visible line: the eye, brand coloured when the item is shown to the client, grey "Client not visible" when it is not. One click is one change with one Undo. */
// Row 1285: under the Classic look the line also draws the 40 x 22 switch at the right of its row (the words are the same); Cards draws none.
export function ClientLine({ row }) {
  const on = !!row.client;
  const run = () => { const c = eyeChange(row); changeCell(c.table, c.id, c.changes, { text: c.words, back: c.back, place: PLACE }); };
  return (
    <button type="button" class={`pk-client cv${on ? " on" : ""}`} data-pk-client aria-pressed={on ? "true" : "false"} onClick={run}>
      <Icon name={on ? "eye" : "eyeoff"} />{on ? (classicTheme() ? "Shown to the client" : "Client visible") : (classicTheme() ? "Hidden from the client" : "Client not visible")}{classicTheme() ? <span class="pk-sw" aria-hidden="true" /> : null}
    </button>
  );
}
