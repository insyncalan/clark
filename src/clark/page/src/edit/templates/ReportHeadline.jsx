// Report headline (row 1261, slice 2), store type "reportheadline": its Edit part, filled in place. The health (a pill with a menu of
// On track, At risk, Off track), the headline (a multi-line box, no length limit) and the supporting sentence (the same kind of box).
// Row 1261: the pill has an eye (aria-pressed true = hidden, as the At a glance tiles' eye) and Edit warns when At a glance also shows the health. Each save is one change() (noteEdit.jsx useSaver): one step, one Undo, place "report". A box saves when it is left or on Enter (the store keeps no hard
// line break: a pasted one becomes a space); Esc puts the saved words back. The words are the mock-up's (the row 1261 headline template mock-up). View part: templates/ReportHeadline.jsx.
import { useEffect, useRef, useState } from "preact/hooks";
import { tidyReportHeadline, HealthIcon } from "../../templates/ReportHeadline.jsx";
import { source } from "../../templates/notes.js";
import { Menu } from "../../components/Menu.jsx";
import { actionIcon } from "../../menuIcons.js";
import { useSaver } from "./noteEdit.jsx";
import { Icon } from "../../components/Icon.jsx";
import { data } from "../../stores/report.js";
import { classicTheme } from "../../components/Contents.jsx";
import { glanceShowsHealth } from "../../templates/glanceBody.js";

export const HINT = "Write the headline the report opens with. Until then this section stays out of the published page.";
// Words from the approved mock-up (mockups/1261-headline-template/headline-approved.html): the row label, its hidden form, the warning.
export const EYE_WORDS = { hide: "Hide project health from the Report headline", show: "Show project health in the Report headline",
  label: "Show project health here", labelHidden: "Show project health here (hidden)",
  warnLead: "Health is also on in At a glance.", warn: " It would show twice on this page. Turn it off here." };
const ITEMS = [["on_track", "On track", "g"], ["at_risk", "At risk", "a"], ["off_track", "Off track", "r"]];

// A multi-line box. `value` is what is saved; `onCommit(text)` is told the new words only when they differ.
function Area({ value, onCommit, label, placeholder, id, cls }) {
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
    <textarea id={id} class={`tpl-field tpl-rh-in${cls ? " " + cls : ""}`} rows={2} value={draft} aria-label={label} placeholder={placeholder} spellcheck={true}
      onFocus={() => { focused.current = true; }} onInput={(e) => setDraft(e.currentTarget.value)} onBlur={(e) => done(e.currentTarget)} onKeyDown={keys} />
  );
}

export { glanceShowsHealth };      // moved to templates/glanceBody.js (the picker needs it too); kept here for the Edit part and its tests

export function Edit({ section }) {
  const saved = tidyReportHeadline(source(section));
  const write = useSaver(section, saved, "", { silent: true });      // row 1261: no toast and no new words; the save is one step, undone with Cmd/Ctrl+Z like the others
  const empty = !(saved.health && saved.pill) && !saved.headline && !saved.sentence;      // a health whose pill is hidden shows nothing, so it does not make the section non-empty
  const now = ITEMS.find((i) => i[0] === saved.health);
  const eye = classicTheme();      // Row 1261 is Classic only: the Cards theme keeps its Edit as it was (no eye, no warning); a stored "pill": false is still honoured by View
  const twice = eye && saved.pill && glanceShowsHealth(data.value && data.value.report_sections);
  const name = now ? now[1] : "Not set";
  return (
    <div class="tpl-edit tpl-edit-reportheadline" data-tpl="reportheadline">
      {empty ? <p class="quiet tpl-hint">{HINT}</p> : null}
      {eye ? <div class="tpl-rh-eyerow">
        <button type="button" class="teye inl" data-edit-only data-rh-eye aria-pressed={saved.pill ? "false" : "true"}
          aria-label={saved.pill ? EYE_WORDS.hide : EYE_WORDS.show} title={saved.pill ? EYE_WORDS.hide : EYE_WORDS.show} onClick={() => write({ pill: !saved.pill })}>
          <Icon name={saved.pill ? "eye" : "eyeoff"} />
        </button>
        <span>{saved.pill ? EYE_WORDS.label : EYE_WORDS.labelHidden}</span>
      </div> : null}
      {twice ? <p class="tpl-rh-warn" role="status" data-rh-warn><b>{EYE_WORDS.warnLead}</b>{EYE_WORDS.warn}</p> : null}
      <div class="tpl-rh-edit">
        {saved.pill || !eye ? <div class="tpl-rh-edit-pill">
          <Menu label={eye ? <><HealthIcon health={saved.health} />{name}</> : name} btnCls={eye ? `pill hpill tpl-rh-pill ${now ? now[2] : "n"} pillbtn` : `pill hpill ${now ? now[2] : "n"} pillbtn`} ariaLabel={`Project health: ${name.toLowerCase()}. Change it`}
            id={`rh-pill-${section.id}`} menuId={`rh-menu-${section.id}`} menuLabel="Project health" chevron={eye}      // Classic: the View capsule plus a small arrow (row 1261); Cards keeps its pill
           
            items={ITEMS.map(([key, word, rag]) => ({ id: key, name: word, pill: rag, icon: actionIcon("status"), checked: key === saved.health }))}
            onPick={(key) => write({ health: key })} />
        </div> : null}
        <div class="tpl-rh-edit-text">
          <label class="tpl-lbl" for={`rh-h-${section.id}`}>Headline</label>
          <Area id={`rh-h-${section.id}`} cls="tpl-rh-hin" value={saved.headline} label="Headline" placeholder="Headline: say where the project stands (no length limit)" onCommit={(headline) => write({ headline })} />
          <label class="tpl-lbl" for={`rh-s-${section.id}`}>Supporting sentence</label>
          <Area id={`rh-s-${section.id}`} value={saved.sentence} label="Supporting sentence" placeholder="Why the project has this health (a line or two)" onCommit={(sentence) => write({ sentence })} />
        </div>
      </div>
    </div>
  );
}
