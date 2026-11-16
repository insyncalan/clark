// RAID cards (#96): the view part both raid3 and raid4 draw with. Text nodes only, never markup. Each card is a work item the file
// (or the served View) already shows, with the words chosen for it underneath. An item with no client wording carries its title as its
// words (raid.js wordsOf, raid3._words); the title is already the heading, so those words are not drawn a second time.
import { openPeek } from "../stores/report.js";
import { cardsOf, titleOf, kindWords, metaBits, ratingOf, latestOf } from "./raid.js";

export function RaidView({ section, data, size }) {
  const cards = cardsOf(section, data, size);
  return (
    <ul class={`raid-cards raid-n${size}`} aria-label={section.title}>
      {cards.map((c) => (
        <li class={`raid-card ${ratingOf(c.row, c.kind).tone}`} key={c.id} data-card={c.id}>
          <p class="raid-top"><span class="raid-kind">{kindWords(c.row, c.kind)}</span> <button type="button" class="idl raid-id" data-open aria-label={`Open ${c.id}`} onClick={() => openPeek(c.id, "item")}>{c.id}</button>{ratingOf(c.row, c.kind).word ? <span class="raid-rating">{ratingOf(c.row, c.kind).word}</span> : null}</p>
          <p class="raid-title">{titleOf(c.row, c.kind)}</p>
          {c.text && c.text !== titleOf(c.row, c.kind) && c.text !== latestOf(c.row) ? <p class="raid-text">{c.text}</p> : null}
          {latestOf(c.row) ? <><p class="raid-label">Latest update</p><p class="raid-latest">{latestOf(c.row)}</p></> : null}
          {metaBits(c.row, c.kind).length ? <p class="raid-meta">{metaBits(c.row, c.kind).map((b, i) => <>{i ? " · " : ""}<span class="raid-bit">{b}</span></>)}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export const isEmptyCards = (section, data, size) => cardsOf(section, data, size).length === 0;
