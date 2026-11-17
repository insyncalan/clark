// Quote (item 96, item 1271), store type "quote": its Edit part, in place. A toolbar above (Tile and Heading, two switches), then the quote as the reader sees it (look B),
// with the words, the name and the role typed inside it (the words wrap and grow; Enter saves and a line break is never stored; the name and the role are one line each). Each save is one change() (noteEdit.jsx saveContent):
// one step, one Undo. The view part is templates/Quote.jsx.
import { source, tidyQuote, quoteShows, LIMITS } from "../../templates/notes.js";
import { Field, useSaver } from "./noteEdit.jsx";
import { Icon } from "../../components/Icon.jsx";

// A switch is stored only when off (section_kinds/quote.py): turning it on again writes nothing for it.
export function Edit({ section }) {
  const saved = tidyQuote(source(section));
  const on = quoteShows(saved);
  const write = useSaver(section, saved, "Quote saved.");
  const flip = (name) => write({ [name]: on[name] ? false : true });
  return (
    <div class="tpl-edit tpl-edit-quote qb" data-tpl="quote">
      <div class="cb-bar" role="toolbar" aria-label="Quote tools">
        <div class="cb-set"><span class="cb-lbl">Show</span>
          <button type="button" role="switch" class="cb-btn" aria-checked={on.tile ? "true" : "false"} aria-label="Show the tile (the card around the quote)" onClick={() => flip("tile")}><Icon name={on.tile ? "eye" : "eyeoff"} />Tile</button>
          <button type="button" role="switch" class="cb-btn" aria-checked={on.heading ? "true" : "false"} aria-label="Show the heading" onClick={() => flip("heading")}><Icon name={on.heading ? "eye" : "eyeoff"} />Heading</button>
        </div>
      </div>
      <figure class="tpl-quote">
        <Field value={saved.quote} label="Quote words" max={LIMITS.quote} placeholder="Type or paste the quote here" cls="qb-words" grow onCommit={(quote) => write({ quote })} />
        <div class="qb-who">
          <Field value={saved.by} label="Quote said by" max={LIMITS.name} placeholder="Name (optional)" cls="qb-by" onCommit={(by) => write({ by })} />
          <Field value={saved.role} label="Quote role" max={LIMITS.name} placeholder="Role (optional)" cls="qb-role" onCommit={(role) => write({ role })} />
        </div>
      </figure>
      {!saved.quote ? <p class="quiet">Empty for now: add the words. It stays out of the published page until then.</p> : null}
    </div>
  );
}
