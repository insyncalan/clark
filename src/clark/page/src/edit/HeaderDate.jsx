// Item 1177: the week the report covers, in the editor's one header, as a button: "Week ending DD-MM-YYYY". At rest it looks like plain text;
// on hover it shows a background and a dotted underline, and the tooltip says "Click to change date". A click opens clark's own calendar (DuePick,
// the panel the old Week ending box used) and a Friday saves as the new week; a day that is not a Friday keeps the old week and names the Friday
// (item 570, the server says the same). The project that keeps no week yet shows the coming Friday, saved only when a day is picked.
import { useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { todayIso } from "../workItems.js";
import { weekOf, shownDay } from "../logic/week.js";
import { ownToast } from "./BarToast.jsx";
import { DuePick } from "./cells/DuePick.jsx";
import { weekEndingQuick } from "./itemEdit.js";
import { isFriday, notFriday } from "./ReportBar.jsx";

export function HeaderDate() {
  const [open, setOpen] = useState(false), btn = useRef(null);
  if (!data.value || !data.value.project) return null;
  const stored = data.value.project.week_ending || "";
  const week = weekOf(stored, todayIso());
  const picked = (day) => {
    setOpen(false);
    if (btn.current) btn.current.focus();
    if (!day) return;
    if (day === week && stored) return;      // the week already kept: nothing to save
    if (!isFriday(day)) { say("problem", notFriday(day) + " The old week ending date was kept."); ownToast(); return; }
    change({ kind: "projects", op: "update", changes: { week_ending: day }, place: "cell" }, `Week ending changed to ${shownDay(day)}.`).then(ownToast);
  };
  const shown = shownDay(week);
  return (
    <>
      <button type="button" class="hdr-date num" id="week-ending-pick" ref={btn} title="Click to change date" aria-label={`Week ending ${shown}. Click to change date`}
        aria-haspopup="dialog" aria-expanded={open ? "true" : "false"} onClick={() => setOpen(!open)}>Week ending {shown}</button>
      {open ? <DuePick row={{ kind: "task", id: "", due_date: week || "" }} anchor={btn} today={todayIso()} label="Week ending date" quick={[weekEndingQuick(todayIso())]}
        onPick={picked} onClose={(back) => { setOpen(false); if (back && btn.current) btn.current.focus(); }} /> : null}
    </>
  );
}
