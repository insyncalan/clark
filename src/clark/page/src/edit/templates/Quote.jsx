// Quote (#96), store type "quote": its Edit part. Fill in place (one line each; a line break isn't allowed in the store): the words, who said it and their role. Each save is one change()
// (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Quote.jsx.
import { source, tidyQuote, LIMITS } from "../../templates/notes.js";
import { Field, useSaver } from "./noteEdit.jsx";

export function Edit({ section }) {
  const saved = tidyQuote(source(section));
  const write = useSaver(section, saved, "Quote saved.");
  return (
    <div class="tpl-edit tpl-edit-quote" data-tpl="quote">
      <label class="tpl-lbl">Quote
        <Field value={saved.quote} label="Quote words" max={LIMITS.quote} onCommit={(quote) => write({ quote })} />
      </label>
      <label class="tpl-lbl">Said by
        <Field value={saved.by} label="Quote said by" max={LIMITS.name} onCommit={(by) => write({ by })} />
      </label>
      <label class="tpl-lbl">Role
        <Field value={saved.role} label="Quote role" max={LIMITS.name} onCommit={(role) => write({ role })} />
      </label>
      {!saved.quote ? <p class="quiet">Empty for now: add the words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
