// Link preview (#96), store type "linkcard": its Edit part. The card's link, title, site line and words, typed and saved together
// with Save card: one change, one step, one Undo, place "report". clark never fetches the page: what the card says is what is typed.
import { useState, useEffect, useRef } from "preact/hooks";
import { linkProblem } from "../../templates/files.js";
import { stored, oneLine, paragraphsOf, linesProblem, labelProblem, saveContent } from "./filesEdit.js";

export const TEXT_LINES = 3, LINE_MAX = 400;
export const BAD_TEXT = `The words on the card can be ${TEXT_LINES} paragraphs of ${LINE_MAX} characters at most. Shorten them and try again.`;

const asText = (v) => (typeof v === "string" ? v : "");

export function Edit({ section }) {
  const content = stored(section);
  const saved = { href: asText(content.href), title: asText(content.title), site: asText(content.site),
                  text: (Array.isArray(content.text) ? content.text : []).filter((t) => typeof t === "string").join("\n") };
  const [f, setF] = useState(saved);
  const [problem, setProblem] = useState("");
  const seen = useRef(section.body);
  useEffect(() => {                       // a save or an Undo brought another body: show it (never on the first draw, which would undo typing)
    if (seen.current === section.body) return;
    seen.current = section.body;
    setF(saved);
  }, [section.body]);
  const set = (k) => (e) => setF({ ...f, [k]: e.currentTarget.value });

  const save = (e) => {
    e.preventDefault();
    const next = { href: f.href.trim(), title: oneLine(f.title), site: oneLine(f.site), text: paragraphsOf(f.text) };
    const why = (next.href ? linkProblem(next.href) : "") || labelProblem(next.title) || labelProblem(next.site)
      || linesProblem(next.text, TEXT_LINES, LINE_MAX, BAD_TEXT);
    setProblem(why);
    if (why) return;
    const body = { ...content, title: next.title, site: next.site, text: next.text };
    if (next.href) body.href = next.href; else delete body.href;
    saveContent(section, body, "Card saved.");
  };
  const fid = `tpl-${section.id}`;
  const changed = f.href.trim() !== saved.href || oneLine(f.title) !== saved.title || oneLine(f.site) !== saved.site
    || paragraphsOf(f.text).join("\n") !== saved.text;
  return (
    <div class="tpl-edit">
      {saved.href ? null : <p class="quiet tpl-empty">No link yet. Type the page's address: until then this section stays out of the published page.</p>}
      <form class="tpl-form" onSubmit={save} data-save>
        <label for={`${fid}-href`}>Link</label>
        <input id={`${fid}-href`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://" value={f.href} onInput={set("href")} />
        <label for={`${fid}-title`}>Title (optional; the link shows without one)</label>
        <input id={`${fid}-title`} type="text" autocomplete="off" value={f.title} onInput={set("title")} />
        <label for={`${fid}-site`}>Line above the title (optional, such as the site's name)</label>
        <input id={`${fid}-site`} type="text" autocomplete="off" value={f.site} onInput={set("site")} />
        <label for={`${fid}-text`}>Words on the card (optional, one paragraph a line)</label>
        <textarea id={`${fid}-text`} rows={3} value={f.text} onInput={set("text")} />
        <button type="submit" class="btn" disabled={!changed}>Save card</button>
      </form>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">The card shows only what you type here: the page itself is never opened to fill it in.</p>
    </div>
  );
}
