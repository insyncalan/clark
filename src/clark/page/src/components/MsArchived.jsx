// "Show archived" on the Milestones page (C-M4; the prototype's pill with a count and its Archived box). The archived milestones
// come from the route that exists (GET /api/data?archived=only, #126); nothing is written here. A published file has neither:
// it holds no archived milestone and asks no server for anything. A name is plain text: the peek opens only a live milestone, so
// the prototype's open-read-only-with-Restore is a gap (reported with C-M4).
import { signal } from "@preact/signals";
import { useEffect } from "preact/hooks";
import { data, fromFile, project, token } from "../stores/report.js";
import { recall, remember } from "../logic/remember.js";
import { showDate } from "../logic/milestones.js";
import { Icon } from "./Icon.jsx";

const shown = signal(!!recall("msArch", false));     // the box is open (remembered)
const found = signal({ code: "", rows: null });      // the archived milestones of one project; rows null until read

async function read(code) {
  try {
    const r = await fetch(`/api/data?project=${encodeURIComponent(code)}&archived=only`, { headers: { "X-Clark-Token": token() }, cache: "no-store" });
    const body = await r.json().catch(() => ({}));
    const rows = r.ok && body.ok && body.data && Array.isArray(body.data.milestones) ? body.data.milestones : [];
    if (code === project.value) found.value = { code, rows };
  } catch (e) {
    if (code === project.value) found.value = { code, rows: [] };
  }
}

const mine = () => (found.value.code === project.value ? found.value.rows : null);

export function MsArchPill() {
  const code = project.value;
  useEffect(() => { if (!fromFile.value && code && found.peek().code !== code) read(code); }, [code]);
  if (fromFile.value) return null;
  const rows = mine(), n = rows ? rows.length : 0, on = shown.value;
  const toggle = () => { remember("msArch", !on); shown.value = !on; };
  return (
    <div class="arch-bar">
      <button type="button" class="arch-pill" id="mArchBtn" aria-pressed={String(on)} aria-controls="mArchList" onClick={toggle}>
        <Icon name="archive" />Show archived <em>{n}</em>
      </button>
    </div>
  );
}

export function MsArchBox() {
  if (fromFile.value || !shown.value) return null;
  const rows = mine() || [], d = data.value || {};
  const linked = (id) => [...(d.actions || []), ...(d.raid || [])].filter((w) => w.milestone === id).length;
  return (
    <section class="arch-box" id="mArchList" aria-labelledby="mArchH">
      <h2 class="arch-h" id="mArchH">Archived <span>{rows.length} milestone{rows.length === 1 ? "" : "s"}</span></h2>
      {rows.length ? (
        <ul class="arch-l">
          {rows.map((m) => {
            const n = linked(m.id);
            return (
              <li key={m.id} data-ms={m.id}>
                <span class="arch-n">{m.name}</span>
                <span class="tag arch"><Icon name="archive" />Archived</span>
                <span>{m.baseline_date ? `Agreed ${showDate(m.baseline_date)} · ` : ""}{n} work item{n === 1 ? "" : "s"} still linked</span>
              </li>
            );
          })}
        </ul>
      ) : <p class="muted">No archived milestones.</p>}
    </section>
  );
}
