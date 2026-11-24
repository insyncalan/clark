// Callout (#96), store type "callout": its Edit part. Fill in place: the tone, a title and the paragraphs (one per line). Each save
// is one change() (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Callout.jsx.
import { source, tidyCallout, TONES, TONE_WORDS, LIMITS } from "../../templates/notes.js";
import { Field, useSaver } from "./noteEdit.jsx";

export function Edit({ section }) {
  const saved = tidyCallout(source(section));
  const write = useSaver(section, saved, "Callout saved.");
  return (
    <div class="tpl-edit tpl-edit-callout" data-tpl="callout">
      <label class="tpl-lbl">Kind
        <select class="tpl-field" aria-label="Callout kind" value={saved.tone} onChange={(e) => write({ tone: e.currentTarget.value })}>
          {TONES.map((t) => <option value={t} key={t}>{TONE_WORDS[t]}</option>)}
        </select>
      </label>
      <label class="tpl-lbl">Title (optional)
        <Field value={saved.title} label="Callout title" max={LIMITS.title} onCommit={(title) => write({ title })} />
      </label>
      <label class="tpl-lbl">Words (one paragraph a line)
        <Field multiline value={saved.paras.join("\n")} label="Callout words" onCommit={(t) => write({ paras: t.split(/\n+/).map((p) => p.trim()).filter(Boolean) })} />
      </label>
      {!saved.title && saved.paras.length === 0 ? <p class="quiet">Empty for now: add a title or some words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
