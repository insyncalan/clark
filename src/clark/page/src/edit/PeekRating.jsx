// Rows 1182 1183: the Risk and Issue peek's Rating (the approved mockup, button Risk). A risk's or issue's colour and level come only from its impact and likelihood,
// so the Rating chip (the chip row, row 1180) opens a 3 x 3 matrix: rows Impact High, Medium, Low; columns Likelihood Low, Medium, High. Each cell shows
// its level word in its colour; one click sets BOTH fields in one change (changeRating, one step, one Undo). The line under the matrix
// says what the pick gives. Keys: the arrows move over the cells, Enter or Space picks, Esc leaves it as it was (Pop). The rule is
// the store's (store.py priority): High and High is Urgent, any High is High (Red), Low and Low is Low (Green), the rest Medium (Amber).
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { Pop } from "./cells/Pop.jsx";
import { changeRating } from "../stores/changes.js";
import { colourOf } from "../workItems.js";
import { tableOf } from "./itemEdit.js";
import { classicTheme } from "../components/Contents.jsx";

export const IMPACTS = ["High", "Medium", "Low"];          // the matrix rows, top to bottom
export const LIKELIHOODS = ["Low", "Medium", "High"];      // the matrix columns, left to right

/** The level the store works out (store.py priority), so the matrix draws what a pick will give. */
export function levelOf(impact, likelihood) {
  if (!impact || !likelihood) return null;
  if (impact === "High" && likelihood === "High") return "Urgent";
  if (impact === "High" || likelihood === "High") return "High";
  if (impact === "Low" && likelihood === "Low") return "Low";
  return "Medium";
}
/** Row 1409: the colour word in the line under the matrix; Classic names Urgent's colour Maroon (the chip and cell are maroon there), Cards keeps Red. */
export const lineWord = (level) => (level === "Urgent" && classicTheme() ? "Maroon" : colourOf(level).word);
/** "High impact, Medium likelihood: High (Red)": the line under the matrix. */
export const hintOf = (impact, likelihood) => {
  const p = levelOf(impact, likelihood);
  return `${impact} impact, ${likelihood} likelihood: ${p} (${lineWord(p)})`;
};

export function Matrix({ row, anchor, onClose, place = "peek" }) {   // row 1282: the one control, in the peek and in the Work items list (place: where the change says it was made)
  const box = useRef(null);
  const [at, setAt] = useState({ i: row.impact, l: row.likelihood });      // the cell under the pointer or the focus: the hint says its result
  const cells = () => Array.from(box.current ? box.current.querySelectorAll("[data-impact]") : []);
  useLayoutEffect(() => {
    const all = cells();
    (all.find((b) => b.getAttribute("aria-pressed") === "true") || all[0]).focus({ preventScroll: true });
  }, []);                                                 // eslint-disable-line react-hooks/exhaustive-deps
  const pick = (impact, likelihood) => {
    onClose(true);
    if (impact === row.impact && likelihood === row.likelihood) return;
    const was = [row.impact, row.likelihood];
    changeRating(tableOf(row), row.id, { impact, likelihood },
      { text: `Impact of ${row.id} is ${impact} and likelihood ${likelihood}.`, back: `Impact and likelihood of ${row.id} are back to ${was[0]} and ${was[1]}.`, place });
  };
  const key = (e) => {
    const ar = { ArrowLeft: [0, -1], ArrowRight: [0, 1], ArrowUp: [-1, 0], ArrowDown: [1, 0] }[e.key];
    if (!ar) return;
    const b = document.activeElement, r = IMPACTS.indexOf(b && b.dataset.impact), c = LIKELIHOODS.indexOf(b && b.dataset.likelihood);
    if (r < 0 || c < 0) return;
    e.preventDefault(); e.stopPropagation();
    const nr = Math.max(0, Math.min(2, r + ar[0])), nc = Math.max(0, Math.min(2, c + ar[1]));
    const to = cells().find((x) => x.dataset.impact === IMPACTS[nr] && x.dataset.likelihood === LIKELIHOODS[nc]);
    if (to) to.focus({ preventScroll: true });
  };
  return (
    <Pop anchor={anchor} label={`Rating of ${row.id}: pick impact and likelihood`} cls="rmatrix" onClose={onClose}>
      <div ref={box} class="rmx" data-pk-matrix onKeyDown={key}>
        <span class="rmx-h rmx-corner">Impact ↓</span><span class="rmx-h rmx-top">Likelihood →</span>
        {IMPACTS.map((im) => (
          <>
            <span class="rmx-l" key={`r-${im}`}>{im}</span>
            {LIKELIHOODS.map((li) => {
              const p = levelOf(im, li), c = colourOf(p);
              return <button type="button" key={`${im}-${li}`} class={`rmx-c rmx-${c.class}`} data-impact={im} data-likelihood={li} data-mx={`${im}|${li}`} data-level={p}
                aria-pressed={im === row.impact && li === row.likelihood ? "true" : "false"} aria-label={`Impact ${im}, likelihood ${li}: ${p}, ${c.word}`}
                onFocus={() => setAt({ i: im, l: li })} onMouseEnter={() => setAt({ i: im, l: li })} onClick={() => pick(im, li)}>{p}</button>;
            })}
          </>
        ))}
        <span class="rmx-colhead" aria-hidden="true" />
        {LIKELIHOODS.map((li) => <span class="rmx-h rmx-col" key={`h-${li}`} aria-hidden="true">{li}</span>)}
      </div>
      <p class="rmx-hint" data-rmx-hint data-pk-matrix-say>{at.i && at.l ? <>{at.i} impact, {at.l} likelihood: <b data-rmx-level>{levelOf(at.i, at.l)}</b> ({lineWord(levelOf(at.i, at.l))})</> : ""}</p>
    </Pop>
  );
}
