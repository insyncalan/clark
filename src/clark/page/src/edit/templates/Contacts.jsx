// Contacts (#96), store type "contacts": its Edit part. A person is added here and kept on the page only (a blank row) until it has
// a name; a person with details but no name is not saved, and the page says so. Each save is one change() (noteEdit.jsx
// saveContent): one step, one Undo. The view part is templates/Contacts.jsx.
import { useEffect, useRef, useState } from "preact/hooks";
import { source, tidyContacts, PERSON_FIELDS, LIMITS } from "../../templates/notes.js";
import { Field, saveContent } from "./noteEdit.jsx";

const BLANK = { name: "", role: "", email: "", phone: "" };
const FIELD_WORDS = { name: "Name", role: "Role", email: "Email", phone: "Phone" };
const MAX = { name: 80, role: 80, email: 120, phone: 40 };

export function Edit({ section }) {
  const saved = tidyContacts(source(section)).people;
  const [rows, setRows] = useState(saved);
  const [hint, setHint] = useState("");
  const key = JSON.stringify(saved);
  // Take the saved people again only when they differ from the ones the draft started from: a late first run of this effect must not wipe what is being typed.
  const seen = useRef(key);
  useEffect(() => { if (seen.current === key) return; seen.current = key; setRows(saved); setHint(""); }, [key]);
  const save = (next) => {
    setRows(next);
    const used = next.filter((p) => PERSON_FIELDS.some((f) => p[f]));
    if (used.some((p) => !p.name)) { setHint("Add a name to save this contact. It isn't saved until it has one."); return null; }
    setHint("");
    if (JSON.stringify(used) === key) return null;
    return saveContent(section, { v: 1, people: used }, "Contacts saved.");
  };
  const set = (i, f, v) => save(rows.map((p, j) => (j === i ? { ...p, [f]: v } : p)));
  return (
    <div class="tpl-edit tpl-edit-contacts" data-tpl="contacts">
      {rows.map((p, i) => (
        <fieldset class="tpl-person" key={i}>
          <legend class="tpl-sr">{`Person ${i + 1}`}</legend>
          {PERSON_FIELDS.map((f) => (
            <label class="tpl-lbl" key={f}>{FIELD_WORDS[f]}
              <Field value={p[f]} label={`Person ${i + 1} ${FIELD_WORDS[f].toLowerCase()}`} max={MAX[f]} onCommit={(v) => set(i, f, v)} />
            </label>
          ))}
          <button type="button" class="btn sm quiet" aria-label={`Remove person ${i + 1}`} onClick={() => save(rows.filter((_, j) => j !== i))}>Remove</button>
        </fieldset>
      ))}
      {hint ? <p class="quiet" role="status">{hint}</p> : null}
      {rows.length < LIMITS.people
        ? <button type="button" class="btn sm" onClick={() => setRows([...rows, { ...BLANK }])}>Add a person</button>
        : <p class="quiet">A contacts section holds {LIMITS.people} people at most.</p>}
      {rows.length === 0 ? <p class="quiet">Empty for now: add a person. It stays out of the published page until then.</p> : null}
    </div>
  );
}
