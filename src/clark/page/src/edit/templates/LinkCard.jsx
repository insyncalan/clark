// Link preview (#96), store type "linkcard": its Edit part. The card's link, title, site line and words, typed and saved together
// with Save card: one change, one step, one Undo, place "report". clark never fetches the page: what the card says is what is typed.
import { useState, useEffect, useRef } from "preact/hooks";
import { linkProblem } from "../../templates/files.js";
import { stored, oneLine, labelProblem, saveContent, plainWords, withPlainWords, paragraphsOf, linesProblem } from "./filesEdit.js";
import { StartPrompt } from "../StartPrompt.jsx";
import { startOr } from "../startingText.js";

// The words on the card are Not rich (row 1288): plain lines in a box, saved with the card; the store allows TEXT_LINES paragraphs of LINE_MAX characters (linkcard.py).
const LINES = 3, EACH = 400, BAD_WORDS = `The words on the card can be ${LINES} paragraphs of ${EACH} characters at most. Shorten them and try again.`;
const asText = (v) => (typeof v === "string" ? v : "");

export function Edit({ section }) {
  const content = stored(section);
  const saved = { href: asText(content.href), title: asText(content.title), site: asText(content.site) };
  const savedWords = plainWords(content.html, content.text);
  const [f, setF] = useState({ ...saved, words: savedWords });
  const [problem, setProblem] = useState("");
  const seen = useRef(JSON.stringify([saved, savedWords]));
  useEffect(() => {                       // a save or an Undo brought another link, title or site line: show it. A save of the words alone leaves the typing be (and the first draw never undoes typing)
    const now = JSON.stringify([saved, savedWords]);
    if (seen.current === now) return;
    seen.current = now;
    setF({ ...saved, words: savedWords });
  }, [section.body]);
  const set = (k) => (e) => setF({ ...f, [k]: e.currentTarget.value });

  const save = (e) => {
    e.preventDefault();
    const next = { href: f.href.trim(), title: oneLine(f.title), site: oneLine(f.site) };
    const wordsChanged = f.words !== savedWords;       // words left alone keep what is stored (an old card's formatting stays until they are typed over)
    const why = (next.href ? linkProblem(next.href) : "") || labelProblem(next.title) || labelProblem(next.site) || (wordsChanged ? linesProblem(paragraphsOf(f.words), LINES, EACH, BAD_WORDS) : "");
    setProblem(why);
    if (why) return;
    const body = { ...(wordsChanged ? withPlainWords(content, f.words) : content), title: next.title, site: next.site };
    if (next.href) body.href = next.href; else delete body.href;
    saveContent(section, body, "Card saved.");
  };
  const fid = `tpl-${section.id}`;
  const changed = f.href.trim() !== saved.href || oneLine(f.title) !== saved.title || oneLine(f.site) !== saved.site || f.words !== savedWords;
  return (
    <div class="tpl-edit tpl-files-edit">
      {saved.href ? null : <><StartPrompt id="link-preview" /><p class="quiet tpl-empty">No link yet. Type the page's address: until then this section stays out of the published page.</p></>}
      <form class="tpl-form" onSubmit={save} data-save>
        <label for={`${fid}-href`}>Link</label>
        <input id={`${fid}-href`} type="text" inputMode="url" autocomplete="off" spellcheck={false} placeholder="https://" value={f.href} onInput={set("href")} />
        <label for={`${fid}-title`}>Title (optional; the link shows without one)</label>
        <input id={`${fid}-title`} type="text" autocomplete="off" value={f.title} onInput={set("title")} />
        <label for={`${fid}-site`}>Line above the title (optional, such as the site's name)</label>
        <input id={`${fid}-site`} type="text" autocomplete="off" value={f.site} onInput={set("site")} />
        <label for={`${fid}-words`}>Words on the card (optional)</label>
        <textarea id={`${fid}-words`} rows={3} autocomplete="off" placeholder={startOr("Click to write.", "link-preview", "empty", 1)} value={f.words} onInput={set("words")} />
        <button type="submit" class="btn" disabled={!changed}>Save card</button>
      </form>
      {problem ? <p class="tpl-problem" role="alert">{problem}</p> : null}
      <p class="quiet tpl-hint">The card shows only what you type here: the page itself is never opened to fill it in.</p>
    </div>
  );
}
