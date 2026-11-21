// Row 1181: the Action peek's chip row. Four chips in the approved order: Status, Priority, Owner, Due date. The popovers are the table cells' own
// pickers (StatusPick, PriorityPick, OwnerPick with Recent, People, TBC, "Add <name> as a new person" and "Keep the name only", DuePick with the
// month and Today, Tomorrow, Friday, Next week, No date), given by the caller as `tools.PeekChipPop(row, field)`; with no popover (a published file,
// View) the chips are drawn read only. An overdue date turns the Due chip red with "overdue N days".
import { PeekChips, PeekChip } from "./PeekChips.jsx";
import { flashed } from "../stores/wordsState.js";
import { dueCell, pillOf, ownerOf, todayIso } from "../workItems.js";
import { classicTheme } from "./Contents.jsx";
import { statusTone, priorityTone, dateTone } from "../iconColours.js";

const DASH = "—";
const ROW_OF = { owner: "owner", due_date: "due", priority: "priority", status: "status" };
const text = (v) => (v === null || v === undefined || v === "" ? DASH : String(v));

/** `row`: the action; `tools`: the editor's tools (PeekChipPop); `editing`: true in Edit. */
export function ActionChips({ row, tools, editing }) {
  const today = todayIso(), due = dueCell(row, today), pill = pillOf(row, today), who = ownerOf(row.owner), f = flashed.value;
  const hit = (key) => !!(f && f.list.some((e) => e.ref === row.id && ROW_OF[e.field] === key));
  const pop = (field) => (editing && tools && tools.PeekChipPop ? tools.PeekChipPop(row, field) : null) || undefined;
  const Live = editing && tools && tools.PeekChipLive ? tools.PeekChipLive : undefined;
  const late = due.tone === "late", days = late ? /^(\d+) days? late$/.exec(due.words) : null;
  const n = days ? days[1] : "1";
  const overdue = late ? `overdue ${n} ${n === "1" ? "day" : "days"}` : "";
  // row 1285 (AP16, Classic only): the overdue Status chip says "needed by passed" under Open, in the chip-sub word style of "needed by".
  // row 1256 (3d): an overdue action's Status chip says Open; the lateness is on the Due chip (red, "overdue N days"). The table pill keeps Overdue.
  const lateOpen = pill.text === "Overdue";
  return (
    <PeekChips>
      <PeekChip Live={Live} id={row.id} field="status" name="Status" icon="half" tone={lateOpen ? "b" : statusTone(row, today)} value={lateOpen ? "Open" : pill.text} sub={lateOpen && classicTheme() ? "needed by passed" : ""} subTone={lateOpen && classicTheme() ? "word" : ""} flash={hit("status")} pop={pop("status")} />
      <PeekChip Live={Live} id={row.id} field="priority" name="Priority" icon="bars" tone={priorityTone(row.priority)} value={text(row.priority)} flash={hit("priority")} pop={pop("priority")} />
      <PeekChip Live={Live} id={row.id} field="owner" name="Owner" icon="user" tone="b" value={who.text} flash={hit("owner")} pop={pop("owner")} />
      <PeekChip Live={Live} id={row.id} field="due" name="Due date" icon="cal" tone={dateTone(row, today)} value={due.date} sub={overdue} subTone={late ? "late" : ""} late={late} flash={hit("due")} pop={pop("due")} />
    </PeekChips>
  );
}
