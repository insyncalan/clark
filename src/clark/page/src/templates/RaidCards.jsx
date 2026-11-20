// RAID cards (item 96): the view part both raid3 and raid4 draw with. Text nodes only, never markup. Each card is a work item the file
// (or the served View) already shows, with its latest update underneath. An old saved body may carry a client or own words choice (raid.js
// wordsOf, raid3._words); it stays readable and kept, but the View draws no such words.
<<<<<<< ours
import { openPeek } from "../stores/report.js";
import { classicTheme } from "../components/Contents.jsx";
import { cardsOf, layoutOf, titleOf, kindWords, partWords, metaBits, ratingOf, latestOf } from "./raid.js";
=======
import { classicTheme } from "../components/Contents.jsx";
import { openPeek, item } from "../stores/report.js";
import { cardsOf, layoutOf, titleOf, whatLabel, kindWords, metaBits, ratingOf, latestOf } from "./raid.js";
>>>>>>> theirs

export function RaidView({ section, data, size }) {
  const { across, max } = layoutOf(section, size);      // row 1270: a body of version 2 is three or four across and up to eight cards
  const cards = cardsOf(section, data, max);
  return (
    <ul class={`raid-cards raid-n${across}`} aria-label={section.title}>
      {cards.map((c) => (
<<<<<<< ours
        <li class={`raid-card ${ratingOf(c.row, c.kind).tone}`} key={c.id} data-card={c.id}>
          <p class="raid-top"><span class="raid-kind">{kindWords(c.row, c.kind)}</span> <button type="button" class="idl raid-id" data-open aria-label={`Open ${c.id} details`} onClick={() => openPeek(c.id, "item")}>{c.id}</button>{ratingOf(c.row, c.kind).word ? <span class="raid-rating">{ratingOf(c.row, c.kind).word}</span> : null}</p>
          {classicTheme() ? <p class="raid-part">{partWords(c.row, c.kind)}</p> : null}<p class="raid-title">{titleOf(c.row, c.kind)}</p>
=======
        <li class={`raid-card ${ratingOf(c.row, c.kind).tone}${item.value === c.id ? " rc-sel" : ""}`} key={c.id} data-card={c.id}>
          <p class="raid-top"><span class="raid-kind">{kindWords(c.row, c.kind)}</span> <button type="button" class="idl raid-id" data-open aria-haspopup="dialog" aria-label={`Open ${c.id} details`} onClick={() => openPeek(c.id, "item")}>{c.id}</button>{ratingOf(c.row, c.kind).word ? <span class="raid-rating">{ratingOf(c.row, c.kind).word}</span> : null}</p>
          {classicTheme() ? <p class="raid-label raid-what">{whatLabel(c.row, c.kind)}</p> : null}
          <p class="raid-title">{titleOf(c.row, c.kind)}</p>
>>>>>>> theirs
          {latestOf(c.row) ? <><p class="raid-label">Latest update</p><p class="raid-latest">{latestOf(c.row)}</p></> : null}
          {metaBits(c.row, c.kind).length ? <p class="raid-meta">{metaBits(c.row, c.kind).map((b, i) => <>{i ? " · " : ""}<span class="raid-bit">{b}</span></>)}</p> : null}
        </li>
      ))}
    </ul>
  );
}

export const isEmptyCards = (section, data, size) => cardsOf(section, data, layoutOf(section, size).max).length === 0;
