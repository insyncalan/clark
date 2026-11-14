// Item 1182: what a risk's (or issue's) peek adds to the shared frame. The Rating chip's matrix popover (3 x 3: Impact down, Likelihood
// across, each cell its level word and its colour; one click sets both fields), the chip itself, and the Details rating row. The caller
// (Peek.jsx) draws `RatingChip` in the chip row after Status and `RatingRow` in Details; `ratingPop(row)` is the chip's popover.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { Pop } from "../edit/cells/Pop.jsx";
import { PeekChip } from "./PeekChips.jsx";
import { Icon } from "./Icon.jsx";
import { iconClass, priorityTone } from "../iconColours.js";
import { changeRating } from "../stores/changes.js";
import { tableOf } from "../edit/itemEdit.js";
import { MATRIX_ROWS, MATRIX_COLS, RATING_TIP, levelOf, colourWord, ratingOf, matrixLine, matrixChange, detailsRating } from "../logic/riskRating.js";

/** The matrix popover. onPick(impact, likelihood) makes the change; onClose(back) closes it. Keys: Right, Left, Down, Up move by cell, Home and End the first and last; Enter or Space picks. */
export function RatingMatrix({ row, anchor, onPick, onClose }) {
  const grid = useRef(null), [said, setSaid] = useState(matrixLine(row.impact, row.likelihood));      // the sentence is the focused or hovered cell's; at first the current one's
  const on = (el) => { if (el) setSaid(matrixLine(el.dataset.impact, el.dataset.likelihood)); };
  const cells = () => Array.from(grid.current ? grid.current.querySelectorAll("[data-pk-cell]") : []);
  useLayoutEffect(() => {
    const all = cells();
    const now = all.find((el) => el.getAttribute("aria-checked") === "true") || all[0];
    if (now) now.focus({ preventScroll: true });
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  const key = (e) => {
    const all = cells(), at = all.indexOf(document.activeElement);
    if (at < 0 || e.altKey || e.ctrlKey || e.metaKey) return;
    const r = Math.floor(at / 3), c = at % 3;
    let to = -1;
    if (e.key === "ArrowRight") to = r * 3 + Math.min(2, c + 1);
    else if (e.key === "ArrowLeft") to = r * 3 + Math.max(0, c - 1);
    else if (e.key === "ArrowDown") to = Math.min(2, r + 1) * 3 + c;
    else if (e.key === "ArrowUp") to = Math.max(0, r - 1) * 3 + c;
    else if (e.key === "Home") to = 0;
    else if (e.key === "End") to = 8;
    if (to < 0) return;
    e.preventDefault();
    e.stopPropagation();                                  // the peek never takes an arrow meant for the matrix
    all[to].focus({ preventScroll: true });
  };
  const line = said;
  return (
    <Pop anchor={anchor} label={`Rating of ${row.id}: ${RATING_TIP}`} role="dialog" cls="pk-matrix-pop" onClose={onClose}>
      <div class="pk-matrix" data-pk-matrix>
        <div class="pk-mx-top"><span class="pk-mx-axis">Impact</span><span class="pk-mx-axis pk-mx-across">Likelihood</span></div>
        <div class="pk-mx-grid" role="radiogroup" aria-label={RATING_TIP} ref={grid} onKeyDown={key}>
          <span aria-hidden="true" />
          {MATRIX_COLS.map((l) => <span class="pk-mx-head" key={l} aria-hidden="true">{l}</span>)}
          {MATRIX_ROWS.map((i) => [
            <span class="pk-mx-head pk-mx-side" key={`h${i}`} aria-hidden="true">{i}</span>,
            ...MATRIX_COLS.map((l) => {
              const level = levelOf(i, l), colour = colourWord(level), on = row.impact === i && row.likelihood === l;
              return (
                <button type="button" role="radio" class={`pk-cell${on ? " on" : ""}`} key={`${i}-${l}`} data-pk-cell data-impact={i} data-likelihood={l} data-colour={colour} data-level={level}
                  aria-checked={on ? "true" : "false"} aria-label={`Impact ${i}, likelihood ${l}: ${level} (${colour})`} onClick={() => onPick(i, l)} onFocus={(e) => on(e.currentTarget)} onMouseEnter={(e) => on(e.currentTarget)}>{level}</button>
              );
            }),
          ])}
        </div>
        {line ? <p class="pk-mx-line" data-pk-matrix-line aria-live="polite">{line}</p> : null}
      </div>
    </Pop>
  );
}

/** The Rating chip's popover, `({ anchor, close }) => element`; a click that changes nothing only closes it. */
export function ratingPop(row) {
  return ({ anchor, close }) => {
    const pick = (impact, likelihood) => {
      const c = matrixChange(row, impact, likelihood);
      close(true);
      if (c && !c.error) changeRating(tableOf(row), row.id, c.changes, { text: c.words, back: c.back, place: "peek" });
    };
    return <RatingMatrix row={row} anchor={anchor} onPick={pick} onClose={close} />;
  };
}

/** The Rating chip: bars icon, colour and level word, the tooltip. `pop` is ratingPop(row) in Edit, absent when read only. */
export function RatingChip({ row, pop, flash, sub }) {
  const r = ratingOf(row);
  return <PeekChip id={row.id} field="rating" name="Rating" icon="bars" tone={priorityTone(row.priority)} value={r.text} sub={sub || ""} flash={flash} tip={RATING_TIP} pop={pop || undefined} />;
}

/** The Details row, one line: "Rating: Red · High (impact High, likelihood Medium)". */
export function RatingRow({ row }) {
  return <div class="pk-row" data-pk-rating-row><dd><span class="pk-val"><span class={iconClass(priorityTone(row.priority))}><Icon name="bars" /></span><span data-pk-rating-line>{detailsRating(row)}</span></span></dd></div>;
}
