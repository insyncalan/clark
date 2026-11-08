// RAID cards (#96): the view part both raid3 and raid4 draw with. Text nodes only, never markup. Each card is a work item the file
// (or the served View) already shows, with the words chosen for it underneath. An item with no client wording carries its title as its
// words (raid.js wordsOf, raid3._words); the title is already the heading, so those words are not drawn a second time.
import { cardsOf, titleOf, kindWords, metaBits } from "./raid.js";

export function RaidView({ section, data, size }) {
  const cards = cardsOf(section, data, size);
  return (
    <ul class={`raid-cards raid-n${size}`} aria-label={section.title}>
      {cards.map((c) => (
        <li class="raid-card" key={c.id} data-card={c.id}>
          <p class="raid-top"><span class="raid-kind">{kindWords(c.row, c.kind)}</span> <span class="raid-id">{c.id}</span></p>
          <p class="raid-title">{titleOf(c.row, c.kind)}</p>
          {metaBits(c.row, c.kind).length ? <p class="raid-meta">{metaBits(c.row, c.kind).map((b, i) => <>{i ? " · " : ""}<span class="raid-bit">{b}</span></>)}</p> : null}
          {c.text && c.text !== titleOf(c.row, c.kind) ? <p class="raid-text">{c.text}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export const isEmptyCards = (section, data, size) => cardsOf(section, data, size).length === 0;
