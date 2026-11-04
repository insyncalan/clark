// Settings › Published reports: "Dashboard as at a day" (item 349, follow-on 8 of the item 125 design note). A day typed as DD-MM-YYYY
// (clark's own way, as Week ending takes it: never the browser's calendar) and Show: the server rebuilds the project's data as it
// stood at the end of that day (as_at.py) and the page shows the Dashboard read only, behind the banner, until Back to now.
// Edit parts only (a published file has no Settings). `api` is a seam for the tests; the page passes none.
import { useState } from "preact/hooks";
import { project, showAsAt } from "../stores/report.js";
import { parseDay } from "../templates/keydates.js";
import { readAsAt } from "./asAtApi.js";
import * as L from "../logic/asAt.js";

export function AsAtPick({ api = readAsAt, code = project.value }) {
  const [msg, setMsg] = useState(null);                      // {kind: "error" | "note", text}
  const [busy, setBusy] = useState(false);

  async function go(e) {
    e.preventDefault();
    if (busy) return;
    const box = document.getElementById("as-at-day");
    const day = parseDay(box ? box.value : "");
    if (!day) { setMsg({ kind: "error", text: L.NO_DAY }); return; }
    setBusy(true);
    setMsg({ kind: "note", text: L.READING });
    const r = await api(code, day);
    setBusy(false);
    if (r.status === 200 && L.isData(r.body, code, day) && showAsAt(day, r.body.data)) { setMsg(null); return; }
    setMsg({ kind: "error", text: L.failWords(r.status, r.status === 200 ? null : r.body) });
  }

  return (
    <form class="asat-pick" id="as-at-pick" onSubmit={go}>
      <h3>{L.LABEL}</h3>
      <p class="muted small">{L.HINT}</p>
      <div class="asat-row">
        <label for="as-at-day" class="sr">Day</label>
        <input type="text" id="as-at-day" inputMode="numeric" placeholder="DD-MM-YYYY" autocomplete="off" disabled={busy} />
        <button type="submit" class="btn sm" id="as-at-show" disabled={busy}>{L.SHOW}</button>
      </div>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </form>
  );
}
