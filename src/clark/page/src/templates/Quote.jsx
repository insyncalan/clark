// Quote (#96, #1271), store type "quote": its view part. One quotation with who said it, as text nodes (look B: the panel, a short blue rule above, the name
// in small capitals and the role under it). isEmpty: no words in the quote. The Edit part is edit/templates/Quote.jsx; the content rules are section_kinds/quote.py.
import { source, tidyQuote, quoteEmpty } from "./notes.js";

export const READY = true;
export const isEmpty = (section) => quoteEmpty(tidyQuote(source(section)));

// The words and who said them, as View draws them and as Edit draws them with its fields typed in place (edit/templates/Quote.jsx).
export function Who({ by, role }) {
  if (!by && !role) return null;
  return (
    <figcaption class="tpl-quote-by">
      {by ? <span class="tpl-quote-nm">{by}</span> : null}
      {by && role ? <span class="tpl-sr">, </span> : null}
      {role ? <span class="tpl-quote-rl">{role}</span> : null}
    </figcaption>
  );
}

export function View({ section }) {
  const q = tidyQuote(source(section));
  return (
    <figure class="tpl-quote">
      <blockquote class="tpl-quote-q"><p>{q.quote}</p></blockquote>
      <Who by={q.by} role={q.role} />
    </figure>
  );
}
