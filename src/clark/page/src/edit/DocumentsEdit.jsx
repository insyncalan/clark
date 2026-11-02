// The Supporting documents section in Edit (#74): the document links the published page lists, each with Edit and Leave out, a form
// to add one, and "Add back a document" for those left out. Each change is one step with one Undo in the toast: add and edit through
// POST /api/change (kind documents), leave out and add back through the eye's hidden rows (kind report_hidden). clark checks the
// link, the title, the kind and the date and says what is wrong in plain words (the toast); nothing is saved until it agrees.
import { useState, useRef, useEffect } from "preact/hooks";
import { data } from "../stores/report.js";
import { change, changeItem } from "../stores/changes.js";
import { visibleDocs, hiddenDocs, factsOf, changedFields, KINDS } from "../logic/documents.js";
import { Icon } from "../components/Icon.jsx";

const EMPTY = { title: "", kind: "Report", url: "", date: "" };

// The add or edit form. `doc` is the document being edited, or null to add one. Esc or Cancel closes it and gives the focus back.
function DocForm({ doc, onClose }) {
  const [form, setForm] = useState(doc ? { title: doc.title || "", kind: doc.kind || "Report", url: doc.url || "", date: doc.date || "" } : EMPTY);
  const [busy, setBusy] = useState(false);
  const first = useRef(null);
  useEffect(() => { if (first.current) first.current.focus(); }, []);      // the title box takes the focus when the form opens
  const id = doc ? `doc-${doc.id}` : "doc-new";
  const set = (k) => (e) => setForm({ ...form, [k]: e.currentTarget.value });
  const submit = async (e) => {
    e.preventDefault();
    if (busy) return;
    setBusy(true);
    let reply;
    if (doc) {
      const changes = changedFields(doc, form);
      if (!Object.keys(changes).length) { setBusy(false); onClose(); return; }
      reply = await changeItem({ kind: "documents", op: "update", id: doc.id, changes, place: "report" }, "Document saved.");
    } else {
      const values = { title: form.title.trim(), kind: form.kind, url: form.url.trim(), date: form.date };
      reply = await changeItem({ kind: "documents", op: "new", values, place: "report" }, "Document added.");
    }
    setBusy(false);
    if (reply) onClose();
  };
  const keys = (e) => { if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); onClose(); } };
  return (
    <form class="tpl-form docs-form" onSubmit={submit} onKeyDown={keys} aria-label={doc ? "Edit the document link" : "Add a document link"}>
      <label for={`${id}-title`}>Title</label>
      <input id={`${id}-title`} type="text" maxLength={120} autocomplete="off" value={form.title} onInput={set("title")} ref={first} />
      <label for={`${id}-kind`}>Kind</label>
      <select id={`${id}-kind`} value={form.kind} onChange={set("kind")}>
        {KINDS.map((k) => <option key={k} value={k}>{k}</option>)}
      </select>
      <label for={`${id}-url`}>Link</label>
      <input id={`${id}-url`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://" value={form.url} onInput={set("url")} />
      <span class="tpl-facts">The client sees this address. It must start with https://, http:// or mailto:</span>
      <label for={`${id}-date`}>Date (optional)</label>
      <input id={`${id}-date`} type="date" value={form.date} onInput={set("date")} />
      <span class="docs-form-buttons">
        <button type="submit" class="btn" disabled={busy}>{doc ? "Save" : "Add document"}</button>
        <button type="button" class="btn quiet" onClick={onClose}>Cancel</button>
      </span>
    </form>
  );
}

export function DocumentsEdit() {
  const d = data.value;
  const shown = visibleDocs(d);
  const left = hiddenDocs(d);
  const [open, setOpen] = useState(null);              // null, "new" or the id of the document being edited
  const box = useRef(null), back = useRef(null);       // back: the button the form was opened from, to be focused once it is drawn again
  const show = (what) => { back.current = null; setOpen(what); };
  const close = () => { back.current = open; setOpen(null); };
  useEffect(() => {
    if (open !== null || back.current === null || !box.current) return;
    const el = [...box.current.querySelectorAll("[data-opens]")].find((b) => b.dataset.opens === back.current);
    back.current = null;
    if (el) el.focus();
  }, [open]);
  const leaveOut = (doc) => change({ kind: "report_hidden", op: "new", id: doc.id, place: "eye" }, "Document left out of the published page.");
  const addBack = (doc) => change({ kind: "report_hidden", op: "delete", id: doc.id, place: "eye" }, "Document added back to the published page.");
  return (
    <div class="tpl-edit docs-edit" ref={box}>
      {shown.length ? (
        <ul class="tpl-dl docs-list">
          {shown.map((doc) => (
            <li key={doc.id} class="tpl-dl-i docs-row">
              {open === doc.id ? <DocForm doc={doc} onClose={close} /> : (
                <>
                  <span class="tpl-badge">{doc.kind || "Link"}</span>
                  <span class="tpl-main">
                    <span class="tpl-name">{doc.title}</span>
                    <span class="tpl-facts">{factsOf(doc)}</span>
                  </span>
                  <span class="docs-row-buttons">
                    <button type="button" class="btn sm quiet" data-opens={doc.id} onClick={() => show(doc.id)} aria-label={`Edit ${doc.title}`}>Edit</button>
                    <button type="button" class="btn sm quiet" onClick={() => leaveOut(doc)} aria-label={`Leave ${doc.title} out of the published page`}>
                      <Icon name="eyeoff" /><span>Leave out</span>
                    </button>
                  </span>
                </>
              )}
            </li>
          ))}
        </ul>
      ) : <p class="quiet tpl-empty">No documents yet. Add one below: until then this section stays out of the published page.</p>}
      {open === "new" ? <DocForm doc={null} onClose={close} />
        : <div class="tpl-actions"><button type="button" class="btn" data-opens="new" onClick={() => show("new")}>Add a document link</button></div>}
      {left.length ? (
        <details class="docs-left">
          <summary>Add back a document ({left.length})</summary>
          <ul class="docs-left-list">
            {left.map((doc) => (
              <li key={doc.id}>
                <span class="tpl-name">{doc.title}</span>
                <button type="button" class="btn sm quiet" onClick={() => addBack(doc)} aria-label={`Add ${doc.title} back to the published page`}>Add back</button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
    </div>
  );
}
