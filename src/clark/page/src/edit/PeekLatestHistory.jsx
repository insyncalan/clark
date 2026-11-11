// Row 1082: 'Show history' under the peek's Latest update (Edit only, like the Latest update itself). It opens the changes of that one field,
// newest first, from the Activity read (GET /api/activity, read only); five rows are in view and the rest scroll. Every value is drawn as text.
// A published file and View have no Latest update box, so they have none of this and the file carries no history.
import { useEffect, useState } from "preact/hooks";
import { project, data } from "../stores/report.js";
import { readActivity } from "./activityApi.js";

const FIELD = "Latest update";
const SHOWN = 5;                                                     // rows in view; the panel scrolls for the rest

export function PeekLatestHistory({ id }) {
  const [open, setOpen] = useState(false);
  const [got, setGot] = useState(null);
  const d = data.value;                                              // a change anywhere replaces the data, so an open list reads again
  useEffect(() => {
    if (!open) return undefined;
    let live = true;
    readActivity(project.value, id).then((r) => { if (live) setGot(r); });
    return () => { live = false; };
  }, [open, id, d]);                                                // eslint-disable-line react-hooks/exhaustive-deps
  const rows = got && got.ok ? got.view.rows.filter((r) => r.field === FIELD && r.kind !== "Created" && r.kind !== "Comment") : [];
  const panel = `pk-lh-${id}`;
  return (
    <div class="pk-lh" data-pk-lh>
      <button type="button" class="pk-lh-btn" data-pk-lh-btn aria-expanded={open ? "true" : "false"} aria-controls={panel} onClick={() => setOpen(!open)}>{open ? "Hide history" : "Show history"}</button>
      {open ? (
        <section id={panel} class="pk-lh-panel" data-pk-lh-panel aria-label="Latest update history">
          <h4 class="pk-lh-h">Latest update history</h4>
          {!got ? <p class="muted pa-none" data-pk-lh-loading>Reading the history…</p>
            : !got.ok ? <p class="muted pa-none" data-pk-lh-failed>The history could not be read just now.</p>
            : !rows.length ? <p class="muted pa-none" data-pk-lh-empty>Nothing has changed on this item yet.</p>
            : (
              <ol class="pk-lh-list" data-pk-lh-list tabIndex={0} aria-label="Latest update changes, newest first">
                {rows.map((r, i) => (
                  <li key={r.step || i} class="pk-lh-row" data-pk-lh-row>
                    <p class="pa-meta"><span class="pa-who">{r.who || "Someone on this computer"}</span>{r.how ? <span> · {r.how}</span> : null}<span> · {r.when_text}</span></p>
                    <p class="pa-what">{r.to || "nothing"}</p>
                  </li>
                ))}
              </ol>
            )}
        </section>
      ) : null}
    </div>
  );
}
