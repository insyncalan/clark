// #80: the Owner picker (a decision's decider): type a name, or choose one of the people already named in this project. Enter
// keeps what is typed; Down moves into the names, Up from the first name back to the box. A name that can't be used is said in
// the panel and nothing is sent. `onPick(value)` returns "" when it made (or skipped) the change, or the words to say.
// The same props as StatusPick, plus `names`, so the peek (#42) can use it as it is.
import { useEffect, useLayoutEffect, useRef, useState } from "preact/hooks";
import { Pop, roam } from "./Pop.jsx";
import { fieldName } from "../itemEdit.js";
import { readPeople } from "../peopleApi.js";
import { project } from "../../stores/report.js";
import { browse, loadRecents, noteAssigned, sameName, searchPeople } from "../../logic/assignTo.js";

// Row 985: the register is read once per picker; with no answer there is no register and the project's own names are all there is.
const Name = ({ n, start, choose }) => (
  <li>
    <button type="button" class="cp-name" data-name={n} aria-pressed={sameName(n, start) ? "true" : "false"} onClick={() => choose(n)}>
      <span class="av" aria-hidden="true">{n.split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase()}</span>
      <span>{n}</span>
    </button>
  </li>
);

export function OwnerPick({ row, anchor, names, onPick, onClose }) {
  const start = String(row.owner == null ? "" : row.owner);
  const [typed, setTyped] = useState(start);
  const [problem, setProblem] = useState("");
  const box = useRef(null), list = useRef(null);
  const what = fieldName(row, "owner");
  const [register, setRegister] = useState(null);       // null until the list has been read (or has failed), so Recent is never drawn short
  const code = project.value, recents = loadRecents(code);
  useEffect(() => { let on = true; readPeople().then((r) => { if (on) setRegister(r.ok ? r.people : []); }); return () => { on = false; }; }, []);
  useLayoutEffect(() => { if (box.current) { box.current.focus({ preventScroll: true }); box.current.select(); } }, []);
  const searching = typed !== start && !!typed.trim();
  const found = searching ? searchPeople(register || [], names, typed).map((h) => h.name) : [];
  const lists = searching || register === null ? null : browse(recents, register, names);
  const choose = (v) => { const p = onPick(v); if (p) setProblem(p); else noteAssigned(code, v); };
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
      <div ref={list} onKeyDown={inList}>
        {register === null ? null : searching ? (found.length ? (
          <ul class="cp-names" aria-label="People found" data-section="found">
            {found.map((n) => <Name key={n} n={n} start={start} choose={choose} />)}
          </ul>
        ) : null) : (
          <>
            {lists.recent.length ? (
              <>
                <p class="cp-sec" id={`own-r-${row.id}`}>Recent</p>
                <ul class="cp-names" aria-labelledby={`own-r-${row.id}`} data-section="recent">
                  {lists.recent.map((n) => <Name key={n} n={n} start={start} choose={choose} />)}
                </ul>
              </>
            ) : null}
            {lists.people.length ? (
              <>
                <p class="cp-sec" id={`own-q-${row.id}`}>People</p>
                <ul class="cp-names" aria-labelledby={`own-q-${row.id}`} data-section="people">
                  {lists.people.map((n) => <Name key={n} n={n} start={start} choose={choose} />)}
                </ul>
              </>
            ) : null}
            {lists.more ? <p class="cp-more" data-more>{`And ${lists.more} more. Keep typing to find them.`}</p> : null}
          </>
        )}
        <button type="button" class="cp-name cp-clear" data-clear onClick={() => choose("TBC")}><span>TBC (no one yet)</span></button>
      </div>
      <p class="cp-hint">Press Enter to keep what you typed.</p>
    </Pop>
  );
}
