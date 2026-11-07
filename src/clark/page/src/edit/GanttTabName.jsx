// The Gantt tab's name in Edit (#926): click the tab label while on the Gantt page and it turns into a box. Enter or leaving the box saves
// (one change with Undo, like every change), Esc puts it back. A name that is empty or too long is refused here, in words, and nothing is sent.
import { useEffect, useRef, useState } from "preact/hooks";
import { data } from "../stores/report.js";
import { change, say } from "../stores/changes.js";
import { tabName, nameOf, requestFor, NAME_MAX } from "../gantt/ganttTab.js";
import { NAME_REFUSED } from "./ganttWords.js";

/** Save a new tab name. Resolves to true when it was kept or needed no change, false when it was refused (the words are in the toast). */
export async function saveTabName(text) {
  const p = data.value && data.value.project, now = tabName(p), n = nameOf(text);
  if (n === null) { say("problem", NAME_REFUSED); return false; }
  if (n === now) return true;
  await change(requestFor("name", n), `Gantt tab renamed to ${n}.`);
  return true;
}

export function GanttTabName({ onDone }) {
  const p = data.value && data.value.project;
  const [typed, setTyped] = useState(tabName(p));
  const box = useRef(null);
  const done = useRef(false);                       // Enter then leaving the box is one save, not two
  useEffect(() => { if (box.current) { box.current.focus(); box.current.select(); } }, []);
  const finish = async (save) => {
    if (done.current) return;
    done.current = true;
    if (save) await saveTabName(typed);
    onDone();
  };
  return (
    <input ref={box} class="tab-name" type="text" value={typed} maxLength={NAME_MAX + 20} aria-label="Tab name" data-gantt-tab-name
      onInput={(e) => setTyped(e.currentTarget.value)} onBlur={() => finish(true)}
      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); finish(true); } else if (e.key === "Escape") { e.preventDefault(); finish(false); } }} />
  );
}
