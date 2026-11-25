// RAID cards (#96): the view part both raid3 and raid4 draw with. Text nodes only, never markup. Each card is a work item the file
// (or the served View) already shows, with its latest update underneath. An old saved body may carry a client or own words choice (raid.js
// wordsOf, raid3._words); it stays readable and kept, but the View draws no such words.
import { classicTheme } from "../components/Contents.jsx";
import { openPeek, item } from "../stores/report.js";
import { cardList } from "../peek/list.js";
import { cardsOf, layoutOf, titleOf, partWords, kindWords, metaBits, ratingOf, latestOf, ratingBits, shows } from "./raid.js";

// The foot line: status, owner and date, then (Classic, risk and issue only) impact and likelihood; each part follows the card's "Also show" choice.
const foot = (c) => [...(shows(c.show, "meta") ? metaBits(c.row, c.kind) : []), ...(classicTheme() && shows(c.show, "rating") ? ratingBits(c.row, c.kind) : [])];

function ClassicRaidView({ section, data, size }) {
  const { across, max } = layoutOf(section, size);      // row 1270: a body of version 2 is three or four across and up to eight cards
  const cards = cardsOf(section, data, max);
  return (
    <ul class={`raid-cards raid-n${across}`} aria-label={section.title}>
      {cards.map((c) => (
        <li class={`raid-card ${ratingOf(c.row, c.kind).tone}${item.value === c.id ? " rc-sel" : ""}`} key={c.id} data-card={c.id}>
          <p class="raid-top"><span class="raid-kind">{kindWords(c.row, c.kind)}</span> <button type="button" class="idl raid-id" data-open aria-haspopup="dialog" aria-label={`Open ${c.id} details`} onClick={() => { cardList.value = cards.map((x) => x.id); openPeek(c.id, "item"); }}>{c.id}</button>{ratingOf(c.row, c.kind).word ? <span class="raid-rating">{ratingOf(c.row, c.kind).word}</span> : null}</p>
          {classicTheme() ? <p class="raid-part">{partWords(c.row, c.kind)}</p> : null}
          <p class="raid-title">{titleOf(c.row, c.kind)}</p>
          {latestOf(c.row) && shows(c.show, "latest") ? <><p class="raid-label">Latest update</p><p class="raid-latest">{latestOf(c.row)}</p></> : null}
          {foot(c).length ? <p class="raid-meta">{foot(c).map((b, i) => <>{i ? " · " : ""}<span class="raid-bit">{b}</span></>)}</p> : null}
        </li>
      ))}
    </ul>
  );
}

// Cards is frozen (product ruling 19-11): its View is main's, word for word; the new card is Classic only.
function CardsRaidView({ section, data, size }) {
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

export function RaidView(props) { return classicTheme() ? <ClassicRaidView {...props} /> : <CardsRaidView {...props} />; }

export const isEmptyCards = (section, data, size) => cardsOf(section, data, layoutOf(section, size).max).length === 0;
