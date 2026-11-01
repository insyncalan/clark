// Quote (#96), store type "quote": its Edit part. Fill in place: the words, who said it and their role. Each save is one change()
// (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Quote.jsx.
import { source, tidyQuote, LIMITS } from "../../templates/notes.js";
import { Field, saveContent } from "./noteEdit.jsx";

export function Edit({ section }) {
  const saved = tidyQuote(source(section));
  const write = (next) => saveContent(section, { v: 1, ...next }, "Quote saved.");
  return (
    <div class="tpl-edit tpl-edit-quote" data-tpl="quote">
      <label class="tpl-lbl">Quote
        <Field multiline value={saved.quote} label="Quote words" max={LIMITS.quote} onCommit={(quote) => write({ ...saved, quote })} />
      </label>
      <label class="tpl-lbl">Said by
        <Field value={saved.by} label="Quote said by" max={LIMITS.name} onCommit={(by) => write({ ...saved, by })} />
      </label>
      <label class="tpl-lbl">Role
        <Field value={saved.role} label="Quote role" max={LIMITS.name} onCommit={(role) => write({ ...saved, role })} />
      </label>
      {!saved.quote ? <p class="quiet">Empty for now: add the words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
