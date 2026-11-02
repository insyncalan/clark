// Settings › People (#454, the prototype's People card; the table is #115's). Everyone who owns a work item or a milestone, with email,
// organisation and role, a line saying how many need details (with Show only these), and Paste from Excel: rows of name, email,
// organisation and role separated by tabs, read here (logic/people.js), shown as a preview with every bad row named, and sent as ONE
// step, so one Undo takes the whole paste back. Edit's page only: a published file has no Settings and no people, and nothing here
// is in it. The Excel import of work items (the buttons, the box, "Check the import") is not this card's: it follows #444 and #449.
import { useEffect, useRef, useState } from "preact/hooks";
import { data, rows as workRows } from "../stores/report.js";
import { peopleRows, needDetails, countLine, doneLine, readPaste, planLine, toSend, NONE_TO_ADD, NOTHING_NEW } from "../logic/people.js";
import { readPeople, pastePeople, undoPeople } from "./peopleApi.js";

const PREVIEW_ROWS = 50;                       // the preview draws this many rows; the line under it says how many more
const WILL = { add: "New person", update: "Update", same: "No change", "": "Not added" };

export function People() {
  const [list, setList] = useState(null);            // null: not read yet; otherwise the people clark holds
  const [failed, setFailed] = useState("");           // why the list could not be read ("" when it could)
  const [only, setOnly] = useState(false);            // the list filtered to those who need details
  const [open, setOpen] = useState(false);            // the paste box
  const [text, setText] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(null);             // {text, step, problem}: what the last paste did, with Undo while its step can be taken back
  const pasteBtn = useRef(null), box = useRef(null);

  const load = async () => {
    const r = await readPeople();
    if (r.ok) { setList(r.people); setFailed(""); } else { setFailed(r.message); setList((was) => was || []); }
  };
  useEffect(() => { load(); }, []);

  const owners = workRows.value.map((r) => r.owner).concat(((data.value && data.value.milestones) || []).map((m) => m.owner));
  const all = peopleRows(list || [], owners);
  const need = needDetails(all).length;
  const filtered = only && need > 0;
  const shown = filtered ? needDetails(all) : all;
  const read = open && text.trim() ? readPaste(text, list || []) : null;

  const toggle = () => { const on = !open; setOpen(on); setMsg(""); if (on) setTimeout(() => box.current && box.current.focus(), 0); };

  const add = async () => {
    if (busy) return;
    if (!text.trim()) { setMsg(NONE_TO_ADD); return; }
    const r = readPaste(text, list || []);
    if (r.refused.length) { setMsg(r.tooMuch || `${r.refused.length === 1 ? "One row needs" : `${r.refused.length} rows need`} fixing before anything is added. Nothing was changed.`); return; }
    const send = toSend(r.rows);
    if (!send.length) { setMsg(NOTHING_NEW); return; }
    setBusy(true);
    setMsg("");
    setDone(null);
    const got = await pastePeople(send);
    setBusy(false);
    if (!got.ok) { setMsg(got.message); return; }
    setList(got.people);
    if (got.step === null) { setMsg(NOTHING_NEW); return; }
    setText(""); setOpen(false); setMsg("");
    setTimeout(() => pasteBtn.current && pasteBtn.current.focus(), 0);
    setDone({ text: doneLine(got.added + got.updated), step: got.step, problem: false });
  };

  // One Undo for the whole paste (the people route's, not the project's). The line is in the card, not in the change toast, so it is
  // seen in View as well as Edit; it stays until the next paste or Undo.
  const undo = async () => {
    if (busy || !done || done.step === null) return;
    setBusy(true);
    const back = await undoPeople(done.step);
    setBusy(false);
    if (back.ok) { setList(back.people); setDone({ text: "Undone.", step: null, problem: false }); } else setDone({ text: back.message, step: null, problem: true });
  };

  const dash = (v) => (v ? v : <span class="muted">—</span>);
  return (
    <section class="frame setting people" id="people" aria-labelledby="people-h">
      <div class="pp-h">
        <h2 id="people-h">People</h2>
        <button type="button" class="btn sm" id="ppPasteBtn" ref={pasteBtn} aria-expanded={open ? "true" : "false"} aria-controls="ppPaste" onClick={toggle}>Paste from Excel</button>
      </div>
      <p class="muted pp-intro">Everyone who owns a work item or a milestone. Owners are still picked by name. Add an email, organisation and role so people can be found and emailed.</p>
      <div class="pp-paste" id="ppPaste" hidden={!open}>
        <label for="ppText">Rows from Excel: name, email, organisation, role, separated by tabs</label>
        <textarea id="ppText" ref={box} rows={5} value={text} placeholder="Sam Rivers[tab]sam@example.com[tab]Supplier[tab]Delivery lead"
          aria-describedby="ppPlan" onInput={(e) => { setText(e.currentTarget.value); setMsg(""); }} />
        <div id="ppPlan" role="status" aria-live="polite">
          {read ? (
            <>
              {read.rows.length ? <p class="pp-plan">{planLine(read.rows)}</p> : null}
              {read.refused.length ? (
                <ul class="pp-bad" id="ppBad">{read.refused.map((p) => <li key={p}>{p}</li>)}</ul>
              ) : null}
              {read.rows.length ? (
                <table class="pp-prev" id="ppPreview">
                  <thead><tr><th>Row</th><th>Name</th><th>Email</th><th>Organisation</th><th>Role</th><th>What happens</th></tr></thead>
                  <tbody>
                    {read.rows.slice(0, PREVIEW_ROWS).map((r) => (
                      <tr key={r.line} class={r.problem ? "bad" : ""} data-line={r.line}>
                        <td class="num">{r.line}</td><td>{dash(r.name)}</td><td>{dash(r.email)}</td><td>{dash(r.org)}</td><td>{dash(r.role)}</td><td>{WILL[r.will]}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : null}
              {read.rows.length > PREVIEW_ROWS ? <p class="muted">And {read.rows.length - PREVIEW_ROWS} more rows.</p> : null}
            </>
          ) : null}
        </div>
        <div class="pp-acts">
          <button type="button" class="btn sm pri" id="ppAdd" disabled={busy} onClick={add}>Add to the list</button>
          <span class="muted" id="ppMsg" role="status">{msg}</span>
        </div>
      </div>
      <p class={`pp-done${done && done.problem ? " error" : ""}`} id="ppDone" role="status" hidden={!done}>
        {done ? <>{done.text}{done.step !== null ? <> <button type="button" class="link" id="ppUndo" disabled={busy} onClick={undo}>Undo</button></> : null}</> : null}
      </p>
      {list === null ? <p class="muted" id="ppLoading">Reading the people list.</p> : null}
      {failed ? <p class="error" id="ppFailed" role="alert">{failed} <button type="button" class="btn sm" id="ppAgain" onClick={load}>Try again</button></p> : null}
      {list !== null && !failed ? (
        all.length ? (
          <>
            <p class="pp-sum" id="ppCount">
              <span>{countLine(need, all.length)}</span>
              {need || only ? <button type="button" class="link" id="ppOnly" aria-pressed={filtered ? "true" : "false"} onClick={() => setOnly(!only)}>{filtered ? "Show everyone" : "Show only these"}</button> : null}
            </p>
            <table class="pp-table" id="ppTable">
              <thead><tr><th>Name</th><th>Email</th><th>Organisation</th><th>Role</th></tr></thead>
              <tbody>
                {shown.map((r) => (
                  <tr key={r.id || `o:${r.name}`} data-person={r.name}>
                    <td class="nm"><b>{r.name}</b>{filtered && !r.email ? <> <span class="tag need">Needs details</span></> : null}</td>
                    <td data-l="Email">{dash(r.email)}</td><td data-l="Organisation">{dash(r.org)}</td><td data-l="Role">{dash(r.role)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : <p class="muted" id="ppNone">No owners yet.</p>
      ) : null}
    </section>
  );
}
