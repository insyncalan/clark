// Report headline (row 1261, slice 2), store type "reportheadline": its Edit part, filled in place. The health (a pill with a menu of
// On track, At risk, Off track), the headline (a multi-line box, no length limit) and the supporting sentence (the same kind of box).
// Each save is one change() (noteEdit.jsx useSaver): one step, one Undo, place "report". A box saves when it is left or on Enter (the store keeps no hard
// line break: a pasted one becomes a space); Esc puts the saved words back. The words are the mock-up's (the row 1261 headline template mock-up). The eye toggle, the
// warning beside At a glance and the library card are not here (not approved or not in this slice). View part: templates/ReportHeadline.jsx.
import { useEffect, useRef, useState } from "preact/hooks";
import { tidyReportHeadline } from "../../templates/ReportHeadline.jsx";
import { source } from "../../templates/notes.js";
import { Menu } from "../../components/Menu.jsx";
import { actionIcon } from "../../menuIcons.js";
import { useSaver } from "./noteEdit.jsx";

export const HINT = "Write the headline the report opens with. Until then this section stays out of the published page.";
const ITEMS = [["on_track", "On track", "g"], ["at_risk", "At risk", "a"], ["off_track", "Off track", "r"]];

// A multi-line box. `value` is what is saved; `onCommit(text)` is told the new words only when they differ.
function Area({ value, onCommit, label, placeholder, id }) {
  const [draft, setDraft] = useState(value);
  const focused = useRef(false), cancelled = useRef(false), latest = useRef(value);
  latest.current = value;
  useEffect(() => { if (!focused.current) setDraft(value); }, [value]);
  const done = (el) => {
    focused.current = false;
    if (cancelled.current) { cancelled.current = false; setDraft(value); return; }
    const text = el.value.replace(/\s+/g, " ").trim();
    setDraft(text);
    if (text === value) return;
    const sent = onCommit(text);
    if (sent && typeof sent.then === "function") sent.then((reply) => { if (reply === null && !focused.current) setDraft(latest.current); });
  };
  const keys = (e) => {
    if (e.isComposing) return;
    if (e.key === "Escape") { e.preventDefault(); cancelled.current = true; e.currentTarget.blur(); }
    else if (e.key === "Enter") { e.preventDefault(); e.currentTarget.blur(); }   // the store keeps no line break (plain text), so Enter leaves the box, as pictureEdit.jsx does
  };
  return (
    <textarea id={id} class="tpl-field tpl-rh-in" rows={2} value={draft} aria-label={label} placeholder={placeholder} spellcheck={true}
      onFocus={() => { focused.current = true; }} onInput={(e) => setDraft(e.currentTarget.value)} onBlur={(e) => done(e.currentTarget)} onKeyDown={keys} />
  );
}

export function Edit({ section }) {
  const saved = tidyReportHeadline(source(section));
  const write = useSaver(section, saved, "Report headline saved.");
  const empty = !saved.health && !saved.headline && !saved.sentence;
  const now = ITEMS.find((i) => i[0] === saved.health);
  const name = now ? now[1] : "Not set";
  return (
    <div class="tpl-edit tpl-edit-reportheadline" data-tpl="reportheadline">
      {empty ? <p class="quiet tpl-hint">{HINT}</p> : null}
      <div class="tpl-rh-edit">
        <div class="tpl-rh-edit-pill">
          <Menu label={name} btnCls={`pill hpill ${now ? now[2] : "n"} pillbtn`} ariaLabel={`Project health: ${name.toLowerCase()}. Change it`}
            id={`rh-pill-${section.id}`} menuId={`rh-menu-${section.id}`} menuLabel="Project health" chevron={false}
            items={ITEMS.map(([key, word, rag]) => ({ id: key, name: word, pill: rag, icon: actionIcon("status"), checked: key === saved.health }))}
            onPick={(key) => write({ health: key })} />
        </div>
        <div class="tpl-rh-edit-text">
          <label class="tpl-lbl" for={`rh-h-${section.id}`}>Headline</label>
          <Area id={`rh-h-${section.id}`} value={saved.headline} label="Headline" placeholder="Headline: say where the project stands (no length limit)" onCommit={(headline) => write({ headline })} />
          <label class="tpl-lbl" for={`rh-s-${section.id}`}>Supporting sentence</label>
          <Area id={`rh-s-${section.id}`} value={saved.sentence} label="Supporting sentence" placeholder="Why the project has this health (a line or two)" onCommit={(sentence) => write({ sentence })} />
        </div>
      </div>
    </div>
  );
}
