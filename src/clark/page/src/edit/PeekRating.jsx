// Items 1182 and 1183: the peek's Rating chip for a risk or an issue (the same for both) and its 3 x 3 matrix. The chip is the bars icon, the
// colour (Red, Amber, Green) and the level word (Urgent, High, Medium, Low), worked out by clark from impact and likelihood; its tooltip
// says so. A click opens the matrix: rows Impact High, Medium, Low, columns Likelihood Low, Medium, High, each cell its level word in its
// colour. One click on a cell sets impact AND likelihood in ONE change (changeCell: one step, one Undo, one Activity line); the line under
// the matrix says what the cell means, in a polite live region. Keys (the month grid's, DuePick.jsx): one tab stop on the cell the rating
// has (the first when it has none), the arrows move along a row or a column and stop at the edge, Home and End the row's ends, Enter or
// Space picks, Esc leaves it as it was. The panel has role dialog, so the peek's own Up and Down stepping leaves its arrows alone.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { changeCell } from "../stores/changes.js";
import { Pop } from "./cells/Pop.jsx";
import { Icon } from "../components/Icon.jsx";
import { colourOf } from "../workItems.js";
import { iconClass } from "../iconColours.js";
import { tableOf } from "./itemEdit.js";
import { IMPACTS, LIKELIHOODS, cellOf, matrixChange, sentenceOf } from "./ratingMatrix.js";

const TIP = "Priority from impact and likelihood";

function Matrix({ row, anchor, onPick, onClose }) {
  const start = IMPACTS.includes(row.impact) && IMPACTS.includes(row.likelihood) ? [IMPACTS.indexOf(row.impact), LIKELIHOODS.indexOf(row.likelihood)] : [0, 0];
  const [at, setAt] = useState(start);
  const grid = useRef(null), moved = useRef(true);
  const rated = IMPACTS.includes(row.impact) && IMPACTS.includes(row.likelihood);
  const [asked, setAsked] = useState(false);                          // an unrated item says "Not rated" until a key has moved onto a cell
  useLayoutEffect(() => {
    const el = moved.current && grid.current && grid.current.querySelector(`[data-cell-at="${at[0]}${at[1]}"]`);
    moved.current = false;
    if (el) el.focus({ preventScroll: true });
  }, [at]);
  const keys = (e) => {
    const [r, c] = at;
    const to = { ArrowLeft: [r, c - 1], ArrowRight: [r, c + 1], ArrowUp: [r - 1, c], ArrowDown: [r + 1, c], Home: [r, 0], End: [r, 2] }[e.key];
    if (!to) return;
    e.preventDefault();
    if (to[0] < 0 || to[0] > 2 || to[1] < 0 || to[1] > 2) return;        // no wrap at the edge
    moved.current = true;
    setAsked(true);
    setAt(to);
  };
  const now = IMPACTS[at[0]], lik = LIKELIHOODS[at[1]];
  const here = rated ? [row.impact, row.likelihood] : null;
  return (
    <Pop anchor={anchor} label={`Rating of ${row.id}: set from impact and likelihood`} cls="crate" onClose={onClose}>
      <div class="mx" ref={grid} role="group" aria-label={`Impact and likelihood of ${row.id}`} onKeyDown={keys}>
        <span class="mh mh-i" aria-hidden="true">Impact ↓</span><span class="mh mh-l" aria-hidden="true">Likelihood →</span>
        {IMPACTS.map((im, r) => (
          <>
            <span class="mr" key={`r${im}`} aria-hidden="true"><i>{im}</i></span>
            {LIKELIHOODS.map((li, c) => {
              const cell = cellOf(im, li), on = here && here[0] === im && here[1] === li;
              return <button type="button" key={`${im}${li}`} class={`mc ${cell.tone}${cell.level === "Urgent" ? " u" : ""}${on ? " on" : ""}`} data-impact={im} data-likelihood={li}
                data-cell-at={`${r}${c}`} tabIndex={at[0] === r && at[1] === c ? 0 : -1} aria-pressed={on ? "true" : "false"} aria-label={cell.label}
                onClick={() => onPick(im, li)}>{cell.level}</button>;
            })}
          </>
        ))}
        <span aria-hidden="true" />{LIKELIHOODS.map((li) => <span class="mh" key={`h${li}`} aria-hidden="true">{li}</span>)}
      </div>
      <p class="mx-say" data-mx-say aria-live="polite">{rated || asked ? sentenceOf(now, lik) : colourOf(null).word}</p>
    </Pop>
  );
}

export function PeekRating({ row }) {
  const [open, setOpen] = useState(false);
  const button = useRef(null);
  const c = colourOf(row.priority), tone = c.class;
  const close = (back) => { setOpen(false); if (back && button.current) button.current.focus(); };
  const pick = (impact, likelihood) => {
    close(true);
    const change = matrixChange(row, impact, likelihood);
    if (!change || change.error) return;
    changeCell(tableOf(row), row.id, change.changes, { text: change.words, back: change.back, place: "peek" });
  };
  return (
    <>
      <button type="button" class="pk-pick pk-rate" ref={button} data-pk-pick="rating" data-tip={TIP} aria-haspopup="dialog" aria-expanded={open ? "true" : "false"}
        aria-label={`Rating of ${row.id}: ${c.word}${row.priority ? `, ${row.priority}` : ""}. Change`} onClick={() => setOpen(!open)}>
        <span class="pk-val"><span class={iconClass(tone)}><Icon name="bars" /></span><span data-pk-rating-word>{c.word}</span>{" "}
          {row.priority ? <span class={`pk-lvl ${tone}`} data-pk-level>{row.priority}</span> : null}</span>
      </button>
      {open ? <Matrix row={row} anchor={button} onPick={pick} onClose={close} /> : null}
    </>
  );
}
