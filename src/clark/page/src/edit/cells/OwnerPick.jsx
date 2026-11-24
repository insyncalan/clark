// #80: the Owner picker (a decision's decider): type a name, or choose one of the people already named in this project. Enter
// keeps what is typed; Down moves into the names, Up from the first name back to the box. A name that can't be used is said in
// the panel and nothing is sent. `onPick(value)` returns "" when it made (or skipped) the change, or the words to say.
// The same props as StatusPick, plus `names`, so the peek (#42) can use it as it is.
import { useLayoutEffect, useRef, useState } from "preact/hooks";
import { Pop, roam } from "./Pop.jsx";
import { matching, fieldName } from "../itemEdit.js";

const SHOWN = 8;

export function OwnerPick({ row, anchor, names, onPick, onClose }) {
  const start = String(row.owner == null ? "" : row.owner);
  const [typed, setTyped] = useState(start);
  const [problem, setProblem] = useState("");
  const box = useRef(null), list = useRef(null);
  const what = fieldName(row, "owner");
  useLayoutEffect(() => { if (box.current) { box.current.focus({ preventScroll: true }); box.current.select(); } }, []);
  const shown = matching(names, typed === start ? "" : typed).slice(0, SHOWN);
  const choose = (v) => { const p = onPick(v); if (p) setProblem(p); };
  const options = () => Array.from(list.current ? list.current.querySelectorAll("button") : []);
  const inBox = (e) => {
    if (e.key === "Enter") { e.preventDefault(); choose(typed); }
    else if (e.key === "ArrowDown") { const o = options(); if (o.length) { e.preventDefault(); o[0].focus(); } }
  };
  const inList = (e) => {
    const o = options();
    if (e.key === "ArrowUp" && o.indexOf(document.activeElement) === 0) { e.preventDefault(); box.current.focus(); return; }
    roam(e, o);
  };
  return (
    <Pop anchor={anchor} label={`${what} of ${row.id}`} cls="cowner" onClose={onClose}>
      <label class="cp-l">
        <span class="sr">{`${what} of ${row.id}`}</span>
        <input ref={box} type="text" class="cp-in" value={typed} autocomplete="off" spellcheck={false} maxLength={200}
          placeholder="Type a name" aria-describedby={problem ? `own-p-${row.id}` : undefined}
          onInput={(e) => { setTyped(e.currentTarget.value); setProblem(""); }} onKeyDown={inBox} />
      </label>
      {problem ? <p class="cp-problem" id={`own-p-${row.id}`} role="alert">{problem}</p> : null}
      {shown.length ? (
        <ul class="cp-names" ref={list} onKeyDown={inList} aria-label="People in this project">
          {shown.map((n) => (
            <li key={n}>
              <button type="button" class="cp-name" data-name={n} aria-pressed={n === start ? "true" : "false"} onClick={() => choose(n)}>
                <span class="av" aria-hidden="true">{n.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span>
                <span>{n}</span>
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      <p class="cp-hint">Press Enter to keep what you typed.</p>
    </Pop>
  );
}
