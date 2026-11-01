// Quote (#96), store type "quote": its view part. One quotation with who said it, as text nodes. isEmpty: no words in the quote.
// The Edit part is edit/templates/Quote.jsx; the content rules are section_kinds/quote.py.
import { source, tidyQuote, quoteEmpty } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => quoteEmpty(tidyQuote(source(section)));

export function View({ section }) {
  const q = tidyQuote(source(section));
  const who = [q.by, q.role].filter(Boolean).join(", ");
  return (
    <figure class="tpl-quote">
      <blockquote class="tpl-quote-q"><p>{q.quote}</p></blockquote>
      {who ? <figcaption class="tpl-quote-by">{who}</figcaption> : null}
    </figure>
  );
}
