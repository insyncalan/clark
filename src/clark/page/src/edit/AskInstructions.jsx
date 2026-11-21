// The standing instructions of asking (row 1294, A8): one box for all projects (the All projects tab) and one for the open project (its own tab, which
// also shows the one for all projects, read only, with a Change button that goes to the All projects tab). Both are sent with every question, the one
// for all projects first. The text is saved when the box is left, as one change with Undo (the server's, POST /api/ask-instructions); a refusal
// is said in the server's own words under the box and the box keeps what was typed so it can be mended. The box is under its label and as wide as
// the card. Edit parts only: a published file has no Settings.
import { useEffect, useRef, useState } from "preact/hooks";
import { project } from "../stores/report.js";
import { announceSwitch } from "./switchToast.js";
import { askInstructionsRead, askInstructionsChange, words } from "./publishApi.js";

export const INSTRUCTIONS_MAX = 4000;
export const ALL_NAME = "Standing instructions for all projects";
export const ALL_HELP = "Up to 4,000 characters, sent with every question, before each project's own. Long instructions count towards the size of one question every time.";
export const OWN_HELP = "Up to 4,000 characters, sent after the ones for all projects. Long instructions count towards the size of one question every time.";
export const SENT_FIRST = "Set under All projects. Sent first.";
const SAVE_WHAT = "save the standing instructions";

/** What the server keeps now: {all, project} ("" for none), or null until it has answered, or "unavailable". */
function useKept(code) {
  const [kept, setKept] = useState(null);
  useEffect(() => {
    let live = true;
    setKept(null);
    askInstructionsRead(code).then((r) => {
      if (!live) return;
      const b = r.body;
      setKept(r.status === 200 && b && b.ok === true && typeof b.all === "string" ? { all: b.all, project: typeof b.project === "string" ? b.project : "" } : "unavailable");
    });
    return () => { live = false; };
  }, [code]);
  return [kept, setKept];
}

function Box({ scope, name, help, kept, setKept, code }) {
  const own = scope === "project";
  const now = kept && kept !== "unavailable" ? (own ? kept.project : kept.all) : "";
  const [typed, setTyped] = useState(null);          // null: the box shows what is kept
  const [msg, setMsg] = useState(null);              // {kind: "error" | "note", text}
  const busy = useRef(false);
  const id = own ? "ask-instructions-project" : "ask-instructions-all";
  const shown = typed === null ? now : typed;
  const base = own ? { scope, project: code } : { scope };

  const apply = (b) => setKept((k) => ({ ...k, all: b.all, project: b.project }));

  async function save() {
    if (typed === null || busy.current) return;
    if (typed === now) { setTyped(null); return; }
    busy.current = true;
    const r = await askInstructionsChange({ ...base, text: typed });
    busy.current = false;
    const b = r.body;
    if (r.status === 200 && b && b.ok === true && typeof b.all === "string") {
      apply(b);
      setTyped(null);
      setMsg(null);
      announceSwitch(b.message || "Saved.", async () => {
        const u = await askInstructionsChange({ ...base, undo: b.apply_id });
        const ub = u.body;
        if (u.status === 200 && ub && ub.ok === true) { apply(ub); return { ok: true }; }
        return { ok: false, message: words(u, SAVE_WHAT) };
      }, "Undone.");
      return;
    }
    setMsg({ kind: "error", text: words(r, SAVE_WHAT) });
  }

  return (
    <div class="ask-instr">
      <label for={id} class="ask-instr-name">{name}</label>
      <small id={`${id}-help`} class="muted">{help}</small>
      <textarea id={id} class="ask-instr-box" rows={9} maxLength={INSTRUCTIONS_MAX} value={shown} disabled={kept === null || kept === "unavailable"}
        aria-describedby={`${id}-help ${id}-count`} aria-invalid={msg && msg.kind === "error" ? "true" : undefined}
        onInput={(e) => { setTyped(e.currentTarget.value); setMsg(null); }} onBlur={save} />
      <div class="ask-instr-foot">
        <span class="muted" id={`${id}-count`}>{shown.length.toLocaleString("en-GB")} of {INSTRUCTIONS_MAX.toLocaleString("en-GB")}</span>
        <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
      </div>
    </div>
  );
}

/** The card on the All projects tab. */
export function AllInstructions() {
  const code = project.value;
  const [kept, setKept] = useKept("");
  return (
    <section class="frame setting" id="ask-instructions-all-card">
      <h2>{ALL_NAME}</h2>
      {kept === "unavailable" ? <p class="muted" id="ask-instructions-note">The standing instructions could not be read just now. Reload the page to try again.</p> : null}
      <Box scope="all" name={ALL_NAME} help={ALL_HELP} kept={kept} setKept={setKept} code={code} />
    </section>
  );
}

/** The card on the project's tab: the one for all projects (read only, with Change) and the project's own. `goAll` shows the All projects tab. */
export function OwnInstructions({ goAll }) {
  const code = project.value;
  const [kept, setKept] = useKept(code);
  const all = kept && kept !== "unavailable" ? kept.all : "";
  return (
    <section class="frame setting" id="ask-instructions-own-card">
      <h2>Standing instructions</h2>
      {kept === "unavailable" ? <p class="muted" id="ask-instructions-note">The standing instructions could not be read just now. Reload the page to try again.</p> : null}
      <div class="set-row">
        <div class="set-row-text"><div class="set-row-name">For all projects</div><small class="muted">{SENT_FIRST}</small></div>
        <div class="set-row-ctl"><button type="button" class="btn" data-ask-instructions-change onClick={goAll}>Change</button></div>
      </div>
      {all ? <div class="ask-instr-read muted" id="ask-instructions-read">{all}</div> : null}
      <Box scope="project" name={`For ${code}`} help={OWN_HELP} kept={kept} setKept={setKept} code={code} />
    </section>
  );
}
