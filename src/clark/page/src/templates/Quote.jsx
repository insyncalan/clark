// Quote (item 96; row 1271), store type "quote": its view part. Up to six quotations, each with who said it, as text nodes. isEmpty: no quote has words.
// The Edit part is edit/templates/Quote.jsx; the content rules are section_kinds/quote.py. The look (centred or left, two or three to a row) is data-align and
// data-per-row on the wrapper; the Classic theme draws it (themes/prototype-2.0/rules-2.css, row 1271 block).
import { source, tidyQuote, quoteEmpty, quoteLook } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => quoteEmpty(tidyQuote(source(section)));

// One quote as View draws it; Edit (edit/templates/Quote.jsx) draws the same box with the words typed in it.
export function Person({ q }) {
  return q.by || q.role ? (
    <figcaption class="tpl-quote-by">
      {q.by ? <span class="tpl-quote-name">{q.by}</span> : null}
      {/* the comma keeps "name, role" one line where the look draws no two lines (Cards, the published text) */}
      {q.by && q.role ? <span class="tpl-quote-sep">, </span> : null}
      {q.role ? <span class="tpl-quote-role">{q.role}</span> : null}
    </figcaption>
  ) : null;
}

export function View({ section }) {
  const k = quoteLook(tidyQuote(source(section)));
  return (
    <div class="tpl-quotes" data-align={k.align} data-per-row={k.perRow}>
      {k.quotes.map((q, i) => (
        <figure class="tpl-quote" key={i}>
          <blockquote class="tpl-quote-q"><p>{q.quote}</p></blockquote>
          <Person q={q} />
        </figure>
      ))}
    </div>
  );
}
