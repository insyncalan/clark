// Row 1295: the slash commands editor, a page of its own that opens in a new browser tab (not inside Settings). The list on the left (Yours, then Built in), the
// editor in the middle, a live preview on the right and Test it underneath. Built-in commands are edited as the person's own version (Reset brings the original
// back) or copied; /history and /new are actions and are shown locked. Files are kept by the server (ask_commands_service.py). Classic only.
// AI help (Describe-and-write-all, Write it, Make it clearer, Shorter, Undo) and the AI check go through the page's one AI client (aiShared.js, /api/ai/suggest) with
// only the person's own words; the live run of the test on Claude is not in this page yet (see the pull request).
import { useEffect, useRef, useState } from "preact/hooks";
import { BUILTINS, PLACEHOLDERS, problems, fill, unfillable, nameProblem, copy } from "../logic/askShortcuts.js";
import { askCommandsRead, askCommandsChange, words } from "./publishApi.js";
import { todayDate } from "../workItems.js";
import { askOn, askStatus, loadAsk, ASK_OFF_LINE } from "./askState.js";
import { aiClient } from "./aiShared.js";
import { AI_FAILED_LINE } from "./aiClient.js";
import { WORDS } from "../logic/aiMenu.js";
import { describeRequest, menuRequest, clearerRequest, shorterRequest, checkRequest, htmlToLines, parseDescribe, parseCheck, menuLine, addedLines, tokens } from "../logic/slashAi.js";
import { rows, SLASH_ALL_HEAD, SLASH_PROJECT_HEAD, TAG_EDITED, TAG_PROJECT, TAG_ACTION } from "./SlashCommandsList.jsx";

export const BACK = "← Back to Settings";
export const SCOPE_LABEL = { anywhere: "Anywhere", item: "About a work item", section: "About a section", usecase: "About a use case" };
export const RESULT_LABEL = { answer: "An answer", changes: "An answer + changes", draft: "A draft" };
const NEW_LABEL = "+ New slash command";
const YOURS = "Yours", BUILT = "Built in";
const LOCKED_TITLE = "An action, not a question: it cannot be edited";
const BUILTIN_NAME_LINE = "A built-in name cannot change. Make a copy to use another name.";
const FREE_LINE = "Free. Lower case letters, numbers and hyphens.";
const NOTE_BUILTIN = "This one comes with clark. Save makes your own version that replaces it; the original is kept and Reset to the built-in brings it back. Make a copy keeps this one as it is and gives you a new slash command to change.";
const PLACE_HEAD = "Placeholders";
const PLACE_ROWS = [
  ["{item}", "The work item you pressed the sparkle on: its ID, title, owner, due date, status and latest update", "About a work item"],
  ["{owner}", "That item’s owner", "About a work item"],
  ["{section}", "The report section you asked about, with its title and what is in it", "About a section"],
  ["{today}", "Today’s date, as DD-MM-YYYY", "Anywhere"],
  ["{input}", "Whatever you type after the name. /who Priya makes {input} read Priya", "Anywhere"],
];
const HINT_ADD = "(what you type after the name)";
const TEST_HEAD = "Test it", READS = "What ask clark reads";
const NOT_SET = "not set";
const NOT_YET = "Nothing is sent to Claude here. This shows the instructions with each placeholder filled in.";
const CANT_READ = "Slash commands aren't ready on this computer yet. Nothing was changed.";
const NO_FILL = (k) => `{${k}} has nothing to fill where this appears.`;
const LONG = "The instructions are long.";
const LONG_AT = 800;
const DESCRIBE_LABEL = "Describe it and let AI write all of it";                                                  // the ticket's words
const WRITE_IT = "Write it", CLEARER = "Make it clearer", SHORTER = "Shorter", UNDO = "Undo";                      // the ticket's words
const AI_NOTE = "Written with AI. Read it before you save.";                                                       // the ticket's words
const AI_CHECK = "AI check";
const CHECK_RUN = "Check with AI";
const Q_CLEAR = "Clear?", Q_READS = "Reads only what a question reads?", Q_CHANGES = "What it can change?";         // the ticket's words
const TOKENS = (n) => `${n} ${n === 1 ? "token" : "tokens"}`;
const EMPTY_INS = "The instructions are empty.";
const NEED_SENTENCE = "Say what you want first.";
const ADDED = "Added";
const AI_LINES = { off: WORDS.off, not_signed_in: WORDS.notSignedIn };
const REMOVE_ALL = "This slash command is kept for all projects. Remove it from the all projects tab.";
const RESET_ALL = "This version is kept for all projects. Reset it from the all projects tab.";
const COPY_NOTE = "Saving makes a copy for this project only. The one for all projects stays as it is.";

const query = () => { try { return new URLSearchParams(location.search); } catch (e) { return new URLSearchParams(""); } };
const blank = () => ({ name: "", menu: "", text: "", scope: "anywhere", result: "answer", was: "", builtin: false, edited: false });
const toDraft = (c) => ({ name: c.name, menu: c.menu, text: c.text, scope: c.scope, result: c.result, was: c.builtin ? "" : c.name, builtin: !!c.builtin, edited: !!c.edited, ai: !!c.ai, inherited: !!c.inherited });
const dmy = (d) => String(d.getDate()).padStart(2, "0") + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + d.getFullYear();

// The instructions with each placeholder filled: a filled value is marked, one with nothing to fill reads "not set".
export function readParts(draft, input, now = todayDate()) {
  const out = [];
  String(draft.text || "").split(/(\{(?:item|owner|section|today|input)\})/).forEach((p, i) => {
    const m = /^\{(item|owner|section|today|input)\}$/.exec(p);
    if (!m) { if (p) out.push({ t: p }); return; }
    const r = fill({ text: p, scope: draft.scope }, { today: now, input });
    out.push(r.notSet.length ? { t: NOT_SET, off: true, k: m[1] } : { t: r.text, on: true, k: m[1] });
  });
  return out;
}

export function SlashEditor() {
  const q = query();
  const project = (q.get("project") || "").trim();
  const scope = q.get("scope") === "all" || !project ? "all" : "project";
  const [data, setData] = useState(null);
  const [draft, setDraft] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [help, setHelp] = useState(false);
  const [input, setInput] = useState("");
  const [undo, setUndo] = useState(null);
  const [aiState, setAiState] = useState("unknown"), [aiLine, setAiLine] = useState(""), [running, setRunning] = useState(false);
  const [aiUndo, setAiUndo] = useState(null), [added, setAdded] = useState([]), [sentence, setSentence] = useState(""), [verdict, setVerdict] = useState(null);
  const ctl = useRef(null);
  const textRef = useRef(null), helpBtn = useRef(null), helpBox = useRef(null);

  async function load(select, keepMsg) {
    const r = await askCommandsRead(scope === "all" ? "" : project);
    const b = r.body;
    if (r.status !== 200 || !b || b.ok !== true || !Array.isArray(b.all)) { setData("unavailable"); return null; }
    setData(b);
    if (select !== undefined) {
      const list = rows(b, scope, project);
      const hit = select && list.find((c) => c.name === select && !c.locked);
      setDraft(hit ? toDraft(hit) : select === "" ? blank() : null);
    }
    if (!keepMsg) setMsg(null);
    return b;
  }
  useEffect(() => { load(q.get("new") ? "" : (q.get("name") || null)); document.title = "Slash commands"; }, []);
  useEffect(() => { loadAsk(); }, []);
  useEffect(() => { const c = aiClient(); Promise.resolve(c.refresh ? c.refresh() : null).then(() => setAiState(c.status())); }, []);
  useEffect(() => { if (help && helpBox.current) helpBox.current.focus(); }, [help]);

  const list = data && data !== "unavailable" ? rows(data, scope, project) : [];
  const mineOwn = scope === "all" ? list.filter((c) => !c.builtin) : list.filter((c) => c.tag === TAG_PROJECT(project));
  const found = draft ? problems({ ...draft, was: draft.was }, mineOwn.map((c) => ({ name: c.name })).filter((c) => c.name !== draft.was), BUILTINS) : [];
  const nameMsg = draft ? (draft.builtin ? BUILTIN_NAME_LINE : nameProblem(draft.name, mineOwn.map((c) => c.name), draft.was, BUILTINS) || FREE_LINE) : "";
  const nameBad = draft && !draft.builtin && nameProblem(draft.name, mineOwn.map((c) => c.name), draft.was, BUILTINS) !== "";
  const edit = (patch) => {
    if (ctl.current) ctl.current.abort();                  // a run that was asked of older words is stopped, not applied
    setDraft((d) => ({ ...d, ...patch })); setUndo(null); setAiUndo(null); setAdded([]);
    if ("text" in patch) setVerdict(null);
  };
  // One AI run at a time, through the page's one client: it asks the route only while the server says ready, and Stop ends it.
  async function runAi(request, apply) {
    setAiLine("");
    const c = aiClient();
    if (c.refresh) await c.refresh();
    const st = c.status();
    setAiState(st);
    if (st !== "ready") { setAiLine(AI_LINES[st] || WORDS.failed); return; }
    const mine = new AbortController();
    ctl.current = mine; setRunning(true);
    try { const r = await c.suggest(request, mine.signal); if (!mine.signal.aborted && !apply(r)) setAiLine(AI_FAILED_LINE); }
    catch (e) { if (!mine.signal.aborted && !(e && e.name === "AbortError")) setAiLine(AI_FAILED_LINE); }
    finally { if (ctl.current === mine) { ctl.current = null; setRunning(false); } }
  }
  const writeAi = (patch, extra) => {                      // the AI's words go into the form for the person to read; the old words are kept for Undo
    const keep = {}; Object.keys(patch).forEach((k) => { keep[k] = draft[k]; }); keep.ai = !!draft.ai;
    setDraft((d) => ({ ...d, ...patch, ai: true })); setAiUndo(keep); setAdded(extra || []); setUndo(null);
    return true;
  };
  const needText = () => { if (draft.text.trim()) return false; setAiLine(EMPTY_INS); return true; };
  const describe = () => {
    if (!sentence.trim()) { setAiLine(NEED_SENTENCE); return; }
    runAi(describeRequest(sentence), (r) => {
      const got = parseDescribe(htmlToLines(r.html));
      if (!got) return false;
      return writeAi(draft.builtin ? { menu: got.menu, text: got.text, scope: got.scope, result: got.result } : got);
    });
  };
  const writeMenu = () => { if (!needText()) runAi(menuRequest(draft.text), (r) => { const l = menuLine(htmlToLines(r.html)); return !!l && writeAi({ menu: l }); }); };
  const clearer = () => { if (!needText()) runAi(clearerRequest(draft.text), (r) => { const l = htmlToLines(r.html); return l.length > 0 && writeAi({ text: l.join("\n") }, addedLines(r.changes)); }); };
  const shorter = () => { if (!needText()) runAi(shorterRequest(draft.text), (r) => { const l = htmlToLines(r.html); return l.length > 0 && writeAi({ text: l.join("\n") }); }); };
  const check = () => { if (!needText()) runAi(checkRequest(draft.text), (r) => { const v = parseCheck(htmlToLines(r.html)); if (v) setVerdict(v); return !!v; }); };
  const undoAi = () => { const k = aiUndo; setAiUndo(null); setAdded([]); if (k) setDraft((d) => ({ ...d, ...k })); };
  const aiOff = aiState === "unknown" || aiState === "off" || aiState === "not_signed_in" || running;
  const aiShown = aiLine || AI_LINES[aiState] || "";

  async function send(body, select) {
    setBusy(true); setMsg(null);
    const r = await askCommandsChange({ scope, ...(scope === "project" ? { project } : {}), ...body });
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true) {
      await load(select, true);
      setMsg({ kind: "note", text: b.message || "" });
      return true;
    }
    setMsg({ kind: "error", text: b && b.code === "refused" && b.message ? b.message : words(r, "save that") });
    return false;
  }
  const record = () => (draft.builtin ? { name: draft.name, replaces: draft.name, menu: draft.menu, text: draft.text, scope: draft.scope, result: draft.result, ...(draft.ai ? { ai: true } : {}) }
    : { name: draft.name, menu: draft.menu, text: draft.text, scope: draft.scope, result: draft.result, ...(draft.ai ? { ai: true } : {}) });
  const save = () => { if (!found.length) send({ action: "save", record: record(), ...(draft.was ? { was: draft.was } : {}) }, draft.name); };
  const reset = () => draft.inherited ? setMsg({ kind: "note", text: RESET_ALL }) : send({ action: "reset", name: draft.name }, draft.name);
  async function remove() {
    if (draft.inherited) { setMsg({ kind: "note", text: REMOVE_ALL }); return; }
    const gone = { ...record() }; const was = draft.name;
    if (await send({ action: "remove", name: was }, null)) setUndo(gone);
  }
  async function unremove() { const r = undo; setUndo(null); if (r) await send({ action: "save", record: r }, r.name); }
  async function makeCopy() {
    try {
      const strip = (c) => ({ name: c.name, menu: c.menu, text: c.text, scope: c.scope, result: c.result });
      const pool = list.filter((c) => !c.builtin).map(strip);
      if (draft.builtin) pool.push({ ...strip(draft), replaces: draft.name });      // an edited built-in is copied as the person's version of it
      const made = copy(pool, { name: draft.was || draft.name, builtin: draft.builtin }, BUILTINS).slice(-1)[0];
      await send({ action: "save", record: made }, made.name);
    } catch (e) { setMsg({ kind: "error", text: e.message }); }
  }
  function insert(tag) {
    const el = textRef.current;
    const at = el && typeof el.selectionStart === "number" ? [el.selectionStart, el.selectionEnd] : [draft.text.length, draft.text.length];
    const next = draft.text.slice(0, at[0]) + tag + draft.text.slice(at[1]);
    edit({ text: next });
    setTimeout(() => { if (el) { el.focus(); el.setSelectionRange(at[0] + tag.length, at[0] + tag.length); } }, 0);
  }
  function closeHelp() { setHelp(false); setTimeout(() => helpBtn.current && helpBtn.current.focus(), 0); }

  const head = scope === "all" ? SLASH_ALL_HEAD : SLASH_PROJECT_HEAD(project);
  const back = "/" + (project ? "?project=" + encodeURIComponent(project) : "") + "#settings&s=claude";
  const yours = list.filter((c) => !c.builtin), built = list.filter((c) => c.builtin);
  const reset0 = () => { if (ctl.current) ctl.current.abort(); setAiUndo(null); setAdded([]); setVerdict(null); setAiLine(""); };
  const pick = (c) => { reset0(); setUndo(null); setMsg(null); setDraft(toDraft(c)); };
  const warn = draft ? [...(draft.text.trim() ? [] : [EMPTY_INS]), ...unfillable(draft).map(NO_FILL), ...(draft.text.length > LONG_AT ? [LONG] : [])] : [];
  const parts = draft ? readParts(draft, input) : [];

  return (
    <main class="slash-page" id="slash-page">
      <header class="slash-top">
        <a href={back} id="slash-back">{BACK}</a>
        <h1 id="slash-h">{head}</h1>
      </header>
      <div class="pub-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}{undo ? <button type="button" class="btn sm" id="slash-undo" onClick={unremove}>Undo</button> : null}</div>
      {askStatus.value === "ready" && !askOn.value ? <p class="muted" id="slash-off">{ASK_OFF_LINE}</p> : null}
      {data === "unavailable" ? <p class="muted" id="slash-note">{CANT_READ}</p> : null}
      {data && data !== "unavailable" ? (
        <div class="slash-grid">
          <nav class="slash-side" aria-label="Slash commands">
            <h2>{YOURS}</h2>
            {yours.map((c) => <button type="button" key={c.name} data-pick={c.name} aria-current={draft && !draft.builtin && draft.name === c.name ? "true" : undefined} onClick={() => pick(c)}><b>/{c.name}</b><small>{c.menu}</small></button>)}
            <button type="button" id="slash-new" onClick={() => { reset0(); setUndo(null); setMsg(null); setDraft(blank()); }}>{NEW_LABEL}</button>
            <h2>{BUILT}</h2>
            {built.map((c) => c.locked
              ? <button type="button" key={c.name} data-pick={c.name} disabled title={LOCKED_TITLE}><b>/{c.name}</b><small>{c.menu} ({TAG_ACTION.toLowerCase()})</small></button>
              : <button type="button" key={c.name} data-pick={c.name} aria-current={draft && draft.builtin && draft.name === c.name ? "true" : undefined} onClick={() => pick(c)}><b>/{c.name}</b>{c.edited ? <span class="slash-tag"> {TAG_EDITED}</span> : null}<small>{c.menu}</small></button>)}
          </nav>
          {draft ? (
            <div class="slash-main">
              <section class="slash-edit-card" aria-label="Edit slash command">
                <h2>{draft.builtin || draft.was ? "/" + (draft.was || draft.name) : "New slash command"}</h2>
                {draft.inherited ? <p class="muted" id="slash-copy-note">{COPY_NOTE}</p> : null}
                {draft.builtin ? <p class="muted" id="slash-builtin-note">{NOTE_BUILTIN}</p> : null}
                <div class="slash-ai" id="slash-ai">
                  <label for="slash-ai-describe-in">{DESCRIBE_LABEL}</label>
                  <div class="row"><input id="slash-ai-describe-in" value={sentence} autocomplete="off" onInput={(e) => setSentence(e.currentTarget.value)} onKeyDown={(e) => { if (e.key === "Enter" && !e.isComposing && !aiOff) { e.preventDefault(); describe(); } }} />
                    <button type="button" class="btn" id="slash-ai-describe" aria-describedby="slash-ai-describe-in" disabled={aiOff} onClick={describe}>{WRITE_IT}</button></div>
                  {running ? <button type="button" class="btn quiet" id="slash-ai-stop" onClick={() => ctl.current && ctl.current.abort()}>{WORDS.stop}</button> : null}
                  {aiUndo ? <button type="button" class="btn quiet" id="slash-ai-undo" onClick={undoAi}>{UNDO}</button> : null}
                  {aiShown ? <p class="muted" id="slash-ai-line" role="status" aria-live="polite">{aiShown}</p> : null}
                  {draft.ai ? <p class="muted" id="slash-ai-note">{AI_NOTE}</p> : null}
                </div>
                <label for="sl-name">Name</label> <span class="muted">what you type after /</span>
                <div class="slash-name-in"><span>/</span><input id="sl-name" value={draft.name} autocomplete="off" spellcheck={false} readOnly={draft.builtin} aria-describedby="sl-name-m" aria-invalid={nameBad ? "true" : undefined} onInput={(e) => edit({ name: e.currentTarget.value })} /></div>
                <div id="sl-name-m" class={nameBad ? "slash-err" : "muted"}>{nameMsg}</div>
                <label for="sl-menu">What it says in the menu</label>
                <div class="row"><input id="sl-menu" value={draft.menu} onInput={(e) => edit({ menu: e.currentTarget.value })} />
                  <button type="button" class="btn quiet" id="slash-ai-write" aria-describedby="sl-menu" disabled={aiOff} onClick={writeMenu}>{WRITE_IT}</button></div>
                <label for="sl-text">What it should do, in plain words</label>
                <textarea id="sl-text" ref={textRef} value={draft.text} onInput={(e) => edit({ text: e.currentTarget.value })} />
                <div class="row slash-ai-text">
                  <button type="button" class="btn quiet" id="slash-ai-clearer" disabled={aiOff} onClick={clearer}>{CLEARER}</button>
                  <button type="button" class="btn quiet" id="slash-ai-shorter" disabled={aiOff} onClick={shorter}>{SHORTER}</button>
                </div>
                {added.length ? <div class="slash-added" id="slash-ai-added"><span class="muted">{ADDED}</span>{added.map((a) => <ins key={a}>{a}</ins>)}</div> : null}
                <div class="slash-add">
                  <span>Add: {Object.keys(PLACEHOLDERS).map((k) => <button type="button" class="slash-ph" key={k} data-ins={k} onClick={() => insert("{" + k + "}")}>{"{" + k + "}"}{k === "input" ? " " + HINT_ADD : ""}</button>)}</span>
                  <button type="button" class="slash-help" id="slash-help" ref={helpBtn} aria-label="About placeholders" aria-expanded={help ? "true" : "false"} onClick={() => setHelp(true)}>?</button>
                </div>
                {help ? (
                  <div class="slash-pop" id="slash-pop" role="dialog" aria-label="About placeholders" tabIndex={-1} ref={helpBox} onKeyDown={(e) => { if (e.key === "Escape") { e.stopPropagation(); closeHelp(); } }}>
                    <div class="slash-pop-h"><b>{PLACE_HEAD}</b><button type="button" id="slash-pop-x" aria-label="Close" title="Close (Esc)" onClick={closeHelp}>×</button></div>
                    <p><b>What they are.</b> A placeholder is a word in curly brackets. When the slash command runs, ask clark swaps it for the real thing from your project.</p>
                    <table><thead><tr><th>Write</th><th>It becomes</th><th>Works when it appears</th></tr></thead>
                      <tbody>{PLACE_ROWS.map((r) => <tr key={r[0]}><td><code>{r[0]}</code></td><td>{r[1]}</td><td>{r[2]}</td></tr>)}</tbody></table>
                    <p><b>How to use them.</b></p>
                    <ol><li>Click one above, or type it, where you want the real value.</li><li>Set <b>Where it appears</b> to match, as in the last column.</li></ol>
                    <p class="muted">A placeholder only fills in text from the project. It cannot make a slash command read or change more than a question you type yourself.</p>
                  </div>
                ) : null}
                <div class="slash-pickers">
                  <div role="group" aria-label="Where it appears"><span class="slash-lab">Where it appears</span>
                    {Object.keys(SCOPE_LABEL).map((k) => <button type="button" key={k} data-scope={k} aria-pressed={draft.scope === k ? "true" : "false"} onClick={() => edit({ scope: k })}>{SCOPE_LABEL[k]}</button>)}</div>
                  <div role="group" aria-label="What you get"><span class="slash-lab">What you get</span>
                    {Object.keys(RESULT_LABEL).map((k) => <button type="button" key={k} data-result={k} aria-pressed={draft.result === k ? "true" : "false"} onClick={() => edit({ result: k })}>{RESULT_LABEL[k]}</button>)}</div>
                </div>
                {found.filter((m) => m !== nameMsg).map((m) => <p class="slash-err" key={m}>{m}</p>)}
                <div class="row slash-actions">
                  <button type="button" class="btn pri" id="slash-save" disabled={busy || found.length > 0} onClick={save}>Save slash command</button>
                  {draft.was || draft.builtin ? <button type="button" class="btn" id="slash-copy" disabled={busy} onClick={makeCopy}>Make a copy</button> : null}
                  {draft.builtin && draft.edited ? <button type="button" class="btn" id="slash-reset" disabled={busy} onClick={reset}>Reset to the built-in</button> : null}
                  {!draft.builtin && draft.was ? <button type="button" class="btn quiet" id="slash-remove" disabled={busy} onClick={remove}>Remove</button> : null}
                  <button type="button" class="btn quiet" id="slash-cancel" disabled={busy} onClick={() => { const c = list.find((x) => x.name === (draft.was || draft.name)); setDraft(c ? toDraft(c) : null); setMsg(null); }}>Cancel</button>
                </div>
              </section>
              <section class="slash-test" id="slash-test" aria-label={TEST_HEAD}>
                <h3>{TEST_HEAD}</h3>
                <label for="sl-input">What you type after /{draft.name || "name"}</label>
                <input id="sl-input" value={input} placeholder="For example: Priya" onInput={(e) => setInput(e.currentTarget.value)} />
                <h4>{READS}</h4>
                <div class="slash-reads" id="slash-reads">{parts.length ? parts.map((p, i) => <span key={i} class={p.on ? "ph-on" : p.off ? "ph-off" : undefined}>{p.t}</span>) : <span class="muted">{" "}</span>}</div>
                <p class="muted" id="slash-test-note">{NOT_YET}</p>
              </section>
            </div>
          ) : <p class="muted slash-pick-note">Pick a slash command to edit it, or press <b>{NEW_LABEL}</b>.</p>}
          {draft ? (
            <aside class="slash-preview" aria-label="Live preview">
              <h3>Live preview</h3>
              <div class="slash-menu-prev" aria-label="How it looks in the box">
                {[...BUILTINS.slice(0, 3).filter((b) => b.name !== draft.name).map((b) => ({ ...b, mark: "" })), { name: draft.name || "name", menu: draft.menu, mark: draft.builtin ? "" : YOURS, on: true }].map((c) => (
                  <div key={c.name} class={c.on ? "on" : undefined}><b>/{c.name}</b><span class="muted">{c.menu}</span>{c.mark ? <span class="slash-tag">{c.mark}</span> : null}</div>
                ))}
              </div>
              <section class="slash-check" id="slash-check" aria-label={AI_CHECK}>
                <h3>{AI_CHECK}</h3>
                <p id="slash-tokens">{TOKENS(tokens(draft.text))}</p>
                {warn.length ? <ul class="slash-warn" id="slash-warn">{warn.map((w) => <li key={w}>{w}</li>)}</ul> : null}
                <button type="button" class="btn quiet" id="slash-check-run" disabled={aiOff} onClick={check}>{CHECK_RUN}</button>
                {verdict ? <dl class="slash-verdict"><dt>{Q_CLEAR}</dt><dd id="slash-check-clear">{verdict.clear}</dd><dt>{Q_READS}</dt><dd id="slash-check-reads">{verdict.reads}</dd><dt>{Q_CHANGES}</dt><dd id="slash-check-changes">{verdict.changes}</dd></dl> : null}
              </section>
            </aside>
          ) : null}
        </div>
      ) : null}
    </main>
  );
}
