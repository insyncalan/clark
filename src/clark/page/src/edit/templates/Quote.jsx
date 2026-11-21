// Quote (item 96; row 1271), store type "quote": its Edit part, in place. A toolbar (whether the tile and the heading show, Left or Centre, how many to a row), then the quotes
// as the reader sees them, each with its words typed inside it (a box that wraps and grows, with its count of 600), and its name and role under it. Up to six quotes:
// Add a quote, and Remove when there are two or more. Each save is one change() (noteEdit.jsx saveContent): one step, one Undo. The view part is templates/Quote.jsx.
import { useEffect, useState } from "preact/hooks";
import { source, tidyQuote, quoteEmpty, LIMITS } from "../../templates/notes.js";
import { startOr } from "../startingText.js";
import { Icon } from "../../components/Icon.jsx";
import { Field, useSaver } from "./noteEdit.jsx";

// Row 1271 words: the toolbar and field words are the ones approved for the quote mock-up (words list, item 1271); the counts and the Add and Remove words are the ones accepted 17-11.
export const WORDS = { tools: "Quote tools", add: "Add a quote", remove: "Remove",
  tile: "Show the tile (the card around the quote)", heading: "Show the heading" };
export const upTo = (n) => `Up to ${LIMITS.quotes} quotes (${n} of ${LIMITS.quotes})`;
const NARROW = "(max-width: 900px)";

// Whether the page is at 900 or narrower, where a row stacks and "Per row" has nothing to set.
function useNarrow() {
  const [narrow, set] = useState(() => (typeof matchMedia === "function" ? matchMedia(NARROW).matches : false));
  useEffect(() => {
    if (typeof matchMedia !== "function") return undefined;
    const m = matchMedia(NARROW), on = () => set(m.matches);
    on();
    m.addEventListener("change", on);
    return () => m.removeEventListener("change", on);
  }, []);
  return narrow;
}

const nth = (label, i) => (i === 0 ? label : label.replace("Quote ", `Quote ${i + 1} `));

// One quote's box in Edit: the words in the box with their count, and who said it under it. It keeps the length typed so far for its own count.
function Box({ q, i, many, edit, remove }) {
  const [typed, setTyped] = useState(null);
  return (
    <figure class="tpl-quote tpl-quote-pe">
      <div class="tq-head">
        <span class="tq-n">{`Quote ${i + 1}`}</span>
        <span class="tq-count" data-tq-words>{`${typed === null ? q.quote.length : typed} of ${LIMITS.quote}`}</span>
        {many >= 2 ? <button type="button" class="tq-rm" aria-label={`Remove quote ${i + 1}`} onClick={remove}>{WORDS.remove}</button> : null}
      </div>
      <Field area value={q.quote} label={nth("Quote words", i)} max={LIMITS.quote} hint={startOr("", "quote", "empty", 0)} cls="tq-words" onDraft={setTyped} onCommit={(quote) => edit(i, { quote })} />
      <div class="tq-by">
        <Field value={q.by} label={nth("Quote said by", i)} max={LIMITS.name} hint={startOr("", "quote", "empty", 1)} cls="tq-f" onCommit={(by) => edit(i, { by })} />
        <Field value={q.role} label={nth("Quote role", i)} max={LIMITS.name} cls="tq-f" onCommit={(role) => edit(i, { role })} />
      </div>
    </figure>
  );
}

export function Edit({ section, slot }) {
  const saved = tidyQuote(source(section));
  const write = useSaver(section, saved, "Quote saved.");
  const narrow = useNarrow();
  const tile = saved.tile !== false, heading = saved.heading !== false, align = saved.align || "left", perRow = saved.perRow || 2;
  const many = saved.quotes.length;
  const noRow = slot === "left" || slot === "right" || narrow;      // half width is one to a row, and a row stacks at 900
  const edit = (i, patch) => write((now) => ({ quotes: now.quotes.map((q, j) => (j === i ? { ...q, ...patch } : q)) }));
  return (
    <div class="tpl-edit tpl-edit-quote cb" data-tpl="quote">
      <div class="cb-bar" role="toolbar" aria-label={WORDS.tools}>
        <div class="cb-set"><span class="cb-lbl">Show</span>
          <button type="button" role="switch" class="cb-btn" aria-checked={tile ? "true" : "false"} aria-label={WORDS.tile} onClick={() => write({ tile: !tile })}><Icon name={tile ? "eye" : "eyeoff"} />Tile</button>
          <button type="button" role="switch" class="cb-btn" aria-checked={heading ? "true" : "false"} aria-label={WORDS.heading} onClick={() => write({ heading: !heading })}><Icon name={heading ? "eye" : "eyeoff"} />Heading</button>
        </div>
        <div class="cb-set"><span class="cb-lbl">Align</span>
          <div class="cb-grp" role="radiogroup" aria-label="Align">
            {[["left", "Left"], ["centre", "Centre"]].map(([k, w]) => (
              <button type="button" role="radio" class="cb-btn" key={k} aria-checked={align === k ? "true" : "false"} onClick={() => write({ align: k })}>{w}</button>
            ))}
          </div>
        </div>
        <div class="cb-set"><span class="cb-lbl">Per row</span>
          <div class="cb-grp" role="radiogroup" aria-label="Per row">
            {[2, 3].map((n) => (
              <button type="button" role="radio" class="cb-btn" key={n} disabled={noRow} aria-checked={perRow === n ? "true" : "false"} onClick={() => write({ perRow: n })}>{n}</button>
            ))}
          </div>
        </div>
        <span class="cb-sep" aria-hidden="true"></span>
        <span class="cb-count" data-tq-count>{upTo(many)}</span>
      </div>
      <div class="tpl-quotes" data-align={align} data-per-row={perRow}>
        {saved.quotes.map((q, i) => (
          <Box key={i} q={q} i={i} many={many} edit={edit} remove={() => write((now) => ({ quotes: now.quotes.filter((_, j) => j !== i) }))} />
        ))}
      </div>
      <button type="button" class="cb-btn tq-add" disabled={many >= LIMITS.quotes} onClick={() => write((now) => ({ quotes: [...now.quotes, { quote: "", by: "", role: "" }] }))}>{WORDS.add}</button>
      {quoteEmpty(saved) ? <p class="quiet">Empty for now: add the words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
