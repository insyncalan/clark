// Callout (item 96), store type "callout": its Edit part. Fill in place: the tone, a title and the words (the one editor, with its / menu). Each save
// is one change() (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Callout.jsx.
import { source, tidyCallout, TONES, TONE_WORDS, LIMITS } from "../../templates/notes.js";
import { Field, useSaver } from "./noteEdit.jsx";
import { RichField } from "../RichField.jsx";
import { wordsAsHtml, noBreaks } from "./filesEdit.js";

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
      <div class="tpl-lbl">Words
        <RichField field="callout" empty="Click to write." id={section.id} value={wordsAsHtml(saved.html, saved.paras)} label="Callout words" save={(html) => write({ html: noBreaks(html), paras: [] })} />
      </div>
      {!saved.title && saved.paras.length === 0 && !saved.html ? <p class="quiet">Empty for now: add a title or some words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
