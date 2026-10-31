// The project's client contact, on the Publish screen (#51; FR-94; Alan, 31-10-2026: one per project, no warning). A published
// page carries a Draft email addressed to this contact, and only when one is saved. The server checks the address (one plain
// address, not on your own team's domain) and saves it as an ordinary step; the page only shows what the server says. Every value
// is shown as text (Preact escapes it), never as markup. Edit parts only: a published file has none of this.
import { useState } from "preact/hooks";
import { data, project } from "../stores/report.js";
import { contactRequest, words } from "./publishApi.js";

export const NO_CONTACT = "No client contact yet, so the page has no Draft email.";

/** The saved contact, {name, email}, or null. */
export function savedContact() {
  const p = data.value && data.value.project;
  return p && typeof p.contact_email === "string" && p.contact_email ? { name: p.contact_name || "", email: p.contact_email } : null;
}

export function ClientContact({ disabled }) {
  const saved = savedContact();
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);                  // {kind: "error" | "note", text}
  const off = disabled || busy;

  function edit() {
    setName(saved ? saved.name : "");
    setEmail(saved ? saved.email : "");
    setMsg(null);
    setEditing(true);
  }

  async function run(action) {
    setBusy(true);
    setMsg(null);
    const r = await contactRequest(action === "save" ? { project: project.value, action, name, email } : { project: project.value, action });
    setBusy(false);
    const b = r.body;
    if (r.status === 200 && b && b.ok === true) {
      const c = b.contact || null, d = data.value;
      data.value = { ...d, project: { ...d.project, contact_name: c ? c.name || null : null, contact_email: c ? c.email : null } };
      setEditing(false);
      setMsg({ kind: "note", text: b.message || "" });
      return;
    }
    setMsg({ kind: "error", text: words(r, "save the client contact") });
  }

  const enter = (e) => { if (e.key === "Enter") { e.preventDefault(); if (!off) run("save"); } };
  return (
    <div class="pub-contact" id="pub-contact">
      <div class="pub-contact-now">
        <span class="pub-contact-what">
          <b>Client contact</b>
          <small id="pub-contact-now">{saved ? (saved.name ? `${saved.name} · ${saved.email}` : saved.email) : NO_CONTACT}</small>
        </span>
        {editing ? null : (
          <span class="pub-contact-acts">
            <button type="button" class="link" data-contact-edit onClick={edit} disabled={off}>{saved ? "Change" : "Add"}</button>
            {saved ? <button type="button" class="link" data-contact-clear onClick={() => run("clear")} disabled={off}>Clear</button> : null}
          </span>
        )}
      </div>
      {editing ? (
        <div class="pub-contact-form">
          <label class="pub-field">Name
            <input type="text" id="pub-contact-name" value={name} autocomplete="off" spellcheck={false} onInput={(e) => setName(e.currentTarget.value)} onKeyDown={enter} />
          </label>
          <label class="pub-field">Email address
            <input type="text" id="pub-contact-email" inputmode="email" value={email} autocomplete="off" spellcheck={false} onInput={(e) => setEmail(e.currentTarget.value)} onKeyDown={enter} />
          </label>
          <span class="pub-contact-acts">
            <button type="button" class="btn" data-contact-save onClick={() => run("save")} disabled={off}>Save contact</button>
            <button type="button" class="btn quiet" data-contact-cancel onClick={() => { setEditing(false); setMsg(null); }} disabled={busy}>Cancel</button>
          </span>
        </div>
      ) : null}
      <div class="pub-contact-msg" role={msg && msg.kind === "error" ? "alert" : "status"} aria-live="polite">{msg && msg.text ? <p class={msg.kind}>{msg.text}</p> : null}</div>
    </div>
  );
}
