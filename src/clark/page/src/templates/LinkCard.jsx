// Link preview (#96), store type "linkcard": its view part. A web page shown as a card: a small line with the site, the title as
// the link, and a few typed lines. A card, not a live embed: every word is typed in Edit and clark never fetches the page. Text
// nodes only; the address through ./safe.js (files.js).
// isEmpty: no link to draw, so the section is left out of the served View and the published file alike (FR-11).
import { linkCard } from "./files.js";

export const READY = true;

export function View({ section }) {
  const c = linkCard(section);
  if (!c) return null;
  return (
    <div class="tpl-lc">
      <p class="tpl-lc-site">{c.site || c.link.shown}</p>
      <p class="tpl-lc-title"><a href={c.link.href} target="_blank" rel="noopener noreferrer">{c.title || c.link.shown}</a></p>
      {c.text.map((t, n) => <p key={n} class="tpl-lc-text">{t}</p>)}
    </div>
  );
}

export const isEmpty = (section) => linkCard(section) === null;
