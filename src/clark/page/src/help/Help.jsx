// The Help panel (#82; BRD 5.13): Start here, How do I… and Reference, all drawn from help/helpContent.json, with one search across
// the three tabs. A layer in place of the open page; Esc returns to it. Edit-served pages only (edit/index.js).
import { useEffect, useRef } from "preact/hooks";
import { content, TABS, tabList, tasks, sections, guides, jobs, undoLink, nextOf, firstTen, loopSteps, iconLegend, milestoneMarks, buildIndex, resultsView, whereLabels, goLabel, markParts, stepPicture } from "./helpLogic.js";
import { pictureUrl } from "./helpPictures.js";
import { helpOpen, helpTab, helpTarget, helpQuery, helpFocusSearch, helpHere, helpLand, landing, setTab, follow, goTo, canGo } from "./helpStore.js";
import { Md } from "./helpText.jsx";
import { Icon } from "../components/Icon.jsx";

let INDEX = null;
const index = () => INDEX || (INDEX = buildIndex());
const S = content.start, T = S.text;

function GoLink({ to, cls }) {
  if (!to || !canGo(to)) return null;
  return <a href="#" class={cls} data-hgo={to} onClick={(e) => { e.preventDefault(); goTo(to); }}>{goLabel(to)} ›</a>;
}

// A tab with nothing to show yet: its entries are held until the part of clark they describe is on the page (helpLater.json).
function Later() {
  return <p class="hp-later muted" id="hp-later">Nothing here yet. This appears when the part of clark it describes is ready.</p>;
}

function Start() {
  const where = S.where, on = (p) => S.parts.includes(p), undo = undoLink();
  if (!S.parts.length) return <Later />;
  return (
    <div class="hp-two">
      <Contents tab="start" />
      <div class="hp-col">
      {on("top") ? <section class="hp-hero" id="hp-start-top" aria-labelledby="hpT0">
        <div><div class="hp-lab">{S.hero.label}</div><h2 id="hpT0">{S.hero.title}</h2><p><Md text={S.hero.lead} /></p></div>
      </section> : null}
      {on("loop") ? <section class="hp-sec hp-loop" id="hp-start-loop" aria-labelledby="hpT1">
        <div class="hp-sh"><h2 id="hpT1">{T.loop_title}</h2><p>{T.loop_intro}</p></div>
        <ol class="hp-steps">
          {loopSteps().map((s, i) => (
            <li key={s.t} class={s.gate ? "gate" : ""}>
              <div class="hp-n">{i + 1} · {s.n}</div>
              <div class="hp-st"><b>{s.t}</b></div>
              <p><Md text={s.d} /></p>
              {s.gate ? <div class="hp-gate">{s.gate}</div> : null}
            </li>
          ))}
        </ol>
        <p class="hp-ret">{T.loop_return}</p>
      </section> : null}
      {on("first") ? <section class="hp-sec" id="hp-start-first" aria-labelledby="hpT2">
        <div class="hp-lab">Once</div><h2 id="hpT2">{T.first_title}</h2>
        <ol class="hp-first">{firstTen().map((f, i) => <li key={f.t}><span class="hp-big">{i + 1}</span><b>{f.t}</b><p><Md text={f.d} /></p></li>)}</ol>
      </section> : null}
      {on("jobs") ? <section class="hp-sec hp-start-jobs" id="hp-start-jobs" data-k="start-jobs" aria-labelledby="hpT3" tabIndex={helpHere.value === "start-jobs" ? 0 : -1}>
        <h2 id="hpT3">{T.jobs_head}</h2>
        <p class="hp-lead">{T.jobs_lead}</p>
        <h3 class="hp-jobs-h">{T.jobs_title}</h3>
        <ol class="hp-jobs">
          {jobs().map((j) => (
            <li key={j.id}>
              <a href="#" class="hp-job" data-hlink={j.place} onClick={(e) => { e.preventDefault(); follow(j.place); }}><div><b>{j.title}</b><span>{j.does}</span></div></a>
            </li>
          ))}
        </ol>
        {undo ? <p class="hp-undo muted">{undo.lead} <a href="#" data-hlink={undo.place} onClick={(e) => { e.preventDefault(); follow(undo.place); }}>{undo.link}</a></p> : null}
      </section> : null}
      {on("where") ? <section class="hp-sec" id="hp-start-where" aria-labelledby="hpT4">
        <div class="hp-lab">The screens</div><h2 id="hpT4">{T.where_title}</h2>
        <ul class="hp-where-g">
          {where.map(([t, d, go]) => (
            <li key={t}>
              {go && canGo(go) ? <a href="#" class="hp-wt" data-hgo={go} onClick={(e) => { e.preventDefault(); goTo(go); }}>{t}</a> : <b class="hp-wt">{t}</b>}
              <p><Md text={d} /></p>
            </li>
          ))}
        </ul>
        <p class="hp-keyline"><Md text={T.keyline} /> · <Md text={`[${T.keyline_link}](#ref-keys)`} /></p>
      </section> : null}
      {on("rules") ? <section class="hp-sec" id="hp-start-rules" aria-labelledby="hpT5">
        <div class="hp-lab">Never bends</div><h2 id="hpT5">{T.rules_title}</h2>
        <ul class="hp-rules">{S.rules.map(([t, d]) => <li key={t}><b>{t}</b><p><Md text={d} /></p></li>)}</ul>
      </section> : null}
      {on("foot") ? <footer class="hp-foot" id="hp-start-foot">
        <p>{T.foot}</p>
        <a href="#" class="hp-a" data-htab="howto" onClick={(e) => { e.preventDefault(); setTab("howto"); }}>{T.foot_link} ›</a>
      </footer> : null}
      </div>
    </div>
  );
}

// The contents list: stays in view (position: sticky, in the page's CSS), marks the place the reader is at, and is one stop for Tab
// (the marked link; the others are reached with the arrow keys). Up and Down move, Home and End jump, Right opens the entry.
function Contents({ tab }) {
  const here = helpHere.value, lists = tabList(tab);
  const stop = lists.some((g) => g.entries.some((e) => e.place === here)) ? here : (lists[0] && lists[0].entries[0] ? lists[0].entries[0].place : null);
  const onKey = (e) => {
    const links = [...e.currentTarget.querySelectorAll("a")], i = links.indexOf(document.activeElement);
    if (i < 0) return;
    const j = e.key === "ArrowDown" ? Math.min(i + 1, links.length - 1) : e.key === "ArrowUp" ? Math.max(i - 1, 0) : e.key === "Home" ? 0 : e.key === "End" ? links.length - 1 : -1;
    if (j >= 0) { e.preventDefault(); links[j].focus(); }
    else if (e.key === "ArrowRight") { e.preventDefault(); links[i].click(); }
  };
  return (
    <nav class="hp-idx" aria-label="In this part" onKeyDown={onKey}>
      {lists.map((g, n) => (
        <div key={n}>
          {g.group ? <div class="hp-ig">{g.group}</div> : null}
          <ul>{g.entries.map((e) => (
            <li key={e.place}><a href="#" data-hlink={e.place} class={e.place === here ? "cur" : ""} aria-current={e.place === here ? "true" : undefined} tabIndex={e.place === stop ? 0 : -1}
              onClick={(ev) => { ev.preventDefault(); follow(e.place); }}>{e.title}</a></li>
          ))}</ul>
        </div>
      ))}
    </nav>
  );
}

// The links at the foot of an entry: its `next` places that are shown (a place that is held is left out, so no link goes nowhere).
function Next({ places }) {
  const l = nextOf(places);
  if (!l.length) return null;
  return (
    <div class="hp-next">
      <h4>What next</h4>
      <ul>{l.map((n) => <li key={n.place}><a href="#" data-hnext={n.place} onClick={(e) => { e.preventDefault(); follow(n.place); }}>{n.title}</a></li>)}</ul>
    </div>
  );
}

function HowTo() {
  const groups = content.howto.groups;
  if (!groups.length) return <Later />;
  return (
    <div class="hp-two">
      <Contents tab="howto" />
      <div class="hp-col">
        <div class="hp-sh"><h2>How do I…</h2><p>The common jobs, step by step. Each says where to go; the arrow at its foot takes you there.</p></div>
        {groups.map((g) => (
          <div key={g}>
            <h3 class="hp-grp">{g}</h3>
            {tasks().filter((x) => x.g === g).map((x) => (
              <article class="hp-task" key={x.id} id={`hp-howto-${x.id}`} data-k={`howto-${x.id}`} tabIndex={helpHere.value === `howto-${x.id}` ? 0 : -1}>
                <h3>{x.t}</h3>
                <p class="hp-where">Where: <Md text={x.w} /></p>
                <ol>{x.s.map((s, i) => <li key={i}><Md text={s} /></li>)}</ol>
                {x.n ? <p class="hp-note"><Md text={x.n} /></p> : null}
                <GoLink to={x.go} cls="hp-go" />
                <Next places={x.next} />
              </article>
            ))}
          </div>
        ))}
        {guides().map((g) => (
          <article class="hp-task hp-guide" key={g.id} id={`hp-${g.place}`} data-k={g.place} tabIndex={helpHere.value === g.place ? 0 : -1}>
            <h3>{g.title}</h3>
            <p class="hp-where">{g.job}</p>
            <ol>{g.steps.map((s) => <li key={s.n}><Md text={s.d} /><StepPicture step={s} /></li>)}</ol>
            {g.result ? <p class="hp-note"><b>What you should see:</b> <Md text={g.result} /></p> : null}
            <Next places={g.next} />
          </article>
        ))}
      </div>
    </div>
  );
}

/** A step's picture (light only, from the page's own copy of it); nothing at all when there is none to draw. */
function StepPicture({ step, urlOf = pictureUrl }) {
  const p = stepPicture(step, urlOf);
  return p ? <img class="hp-pic" src={p.src} alt={p.alt} loading="lazy" /> : null;
}

function Table({ head, rows, cls }) {
  return (
    <div class="hp-tw"><table class={`hp-t ${cls || ""}`}>
      <thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}><Md text={c} /></td>)}</tr>)}</tbody>
    </table></div>
  );
}

// The parts that need things the page has not got yet (the work item badges and the writing helper's menu) draw nothing
// until their items land; the icon legend and the milestone marks are listed in words, the pictures waiting for the icon set.
function Block({ b }) {
  const [k, a, rows] = b;
  if (k === "p") return <p><Md text={a} /></p>;
  if (k === "ul") return <ul>{a.map((x, i) => <li key={i}><Md text={x} /></li>)}</ul>;
  if (k === "tbl") return <Table head={a} rows={rows} />;
  if (k === "keys") return <Table cls="hp-keys" head={["Keys", "Does"]} rows={content.reference.keys} />;
  if (k === "icons") return <Table cls="hp-icons" head={["Name", "What it does", "Where"]} rows={iconLegend().map((r) => [r.title, r.does, r.where])} />;
  if (k === "marks") return <Table cls="hp-marks" head={["State", "Means"]} rows={milestoneMarks().map((m) => [m.state, m.means])} />;
  return null;
}

function Reference() {
  const groups = content.reference.groups;
  if (!groups.length) return <Later />;
  return (
    <div class="hp-two">
      <Contents tab="reference" />
      <div class="hp-col">
        <div class="hp-sh"><h2>Reference</h2><p>Every screen and control, as clark has them today.</p></div>
        {groups.map((g) => (
          <div key={g}>
            <h3 class="hp-grp">{g}</h3>
            {sections().filter((x) => x.g === g).map((x) => (
              <article class="hp-ref" key={x.id} id={`hp-ref-${x.id}`} data-k={`ref-${x.id}`} tabIndex={helpHere.value === `ref-${x.id}` ? 0 : -1}>
                <h3>{x.t}</h3>
                {x.w ? <p class="hp-where">Where: <Md text={x.w} /></p> : null}
                {x.b.map((b, i) => <Block key={i} b={b} />)}
                <Next places={x.next} />
              </article>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

// A line of a result with the words the search matched marked (the prototype's yellow mark), drawn as text, never as markup.
function Marked({ text, q }) {
  return <>{markParts(text, q).map((p, i) => (p.hit ? <mark key={i}>{p.t}</mark> : p.t))}</>;
}

function Results() {
  const r = resultsView(index(), helpQuery.value);
  if (r.kind === "empty") return <div class="hp-none" role="status"><b>{r.title}</b><span>{r.hint}</span></div>;
  return (
    <>
      <p class="hp-resn" role="status">{r.line}</p>
      {r.lead && <p class="hp-resl">{r.lead}</p>}
      {r.groups.map((g) => (
        <section class="hp-resg" key={g.tab} aria-label={g.name}>
          <h3>{g.name}</h3>
          {g.results.map((x) => {
            const lab = whereLabels(x.where);
            return (
              <a href="#" class="hp-r" key={x.id} data-hit={x.id} onClick={(ev) => { ev.preventDefault(); follow(x.id); }}>
                <span class="hp-rt"><Marked text={x.title} q={helpQuery.value} /></span>
                {(lab.step || lab.part) && (
                  <span class="hp-where">
                    {lab.step && <span class="hp-chip" data-where="step">{lab.step}</span>}
                    {lab.part && <span class="hp-chip hp-chip-g" data-where="part">{lab.part}</span>}
                  </span>
                )}
                <span class="hp-rl"><Marked text={x.text} q={helpQuery.value} /></span>
              </a>
            );
          })}
        </section>
      ))}
    </>
  );
}

const PANES = { start: Start, howto: HowTo, reference: Reference };

let landedAt = 0;      // when a link last took the reader to a place: the scroll that follows is not the reader reading on

export function Help() {
  const tab = helpTab.value, q = helpQuery.value, asked = !!q.trim();
  const box = useRef(null), search = useRef(null);
  const Pane = PANES[tab];
  // Scroll to the place asked for and flash it.
  useEffect(() => {
    const t = helpTarget.value;
    if (!t) { window.scrollTo(0, 0); return; }
    const el = document.getElementById("hp-" + t);
    if (!el) return;
    landedAt = performance.now();
    el.scrollIntoView({ block: "start" });
    el.classList.add("hp-found");
    const timer = setTimeout(() => el.classList.remove("hp-found"), 2400);
    return () => clearTimeout(timer);
  }, [helpTarget.value, tab, asked]);
  // The place the reader is at follows the page as it scrolls (the marked link in the contents list); focus goes to the entry a link opened.
  useEffect(() => {
    if (asked) return;
    let raf = 0;
    const pick = () => {
      raf = 0;
      const wait = 800 - (performance.now() - Math.max(landedAt, landing.at));
      if (wait > 0) { raf = -1; setTimeout(() => { raf = 0; on(); }, wait + 20); return; }      // a link's own scroll is not the reader reading on; look again once it is done
      const els = [...document.querySelectorAll("#hpPane [data-k]")];
      if (!els.length) return;
      const line = (parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--topbar")) || 56) + 40;
      let cur = els[0];
      for (const e of els) { if (e.getBoundingClientRect().top <= line) cur = e; else break; }
      const de = document.documentElement;
      let k = cur.dataset.k;
      if (de.scrollTop + de.clientHeight >= de.scrollHeight - 1) {      // at the foot of the page the last entry of the contents is the one on screen
        const last = [...document.querySelectorAll(".hp-idx a[data-hlink]")].pop();
        if (last) k = last.dataset.hlink;
      }
      if (k !== helpHere.peek()) helpHere.value = k;
    };
    function on() { if (!raf) raf = requestAnimationFrame(pick); }
    window.addEventListener("scroll", on, { passive: true });
    return () => { window.removeEventListener("scroll", on); if (raf > 0) cancelAnimationFrame(raf); };
  }, [tab, asked]);
  useEffect(() => {
    if (!helpLand.value) return;
    const here = helpHere.value, el = here && document.querySelector(`#hpPane [data-k="${here}"]`);
    if (el) el.focus({ preventScroll: true });
  }, [helpLand.value]);
  useEffect(() => { if (helpFocusSearch.value && search.current) { search.current.focus(); search.current.select(); } }, [helpFocusSearch.value]);
  useEffect(() => { if (box.current) box.current.focus({ preventScroll: true }); }, []);
  const onTabKey = (e) => {
    const ks = TABS.map((t) => t.key), i = ks.indexOf(tab);
    const j = e.key === "ArrowRight" ? (i + 1) % ks.length : e.key === "ArrowLeft" ? (i + ks.length - 1) % ks.length : e.key === "Home" ? 0 : e.key === "End" ? ks.length - 1 : -1;
    if (j < 0) return;
    e.preventDefault(); setTab(ks[j]);
    setTimeout(() => { const b = document.getElementById("hpTab-" + ks[j]); if (b) b.focus(); }, 0);
  };
  // Left from an entry goes back to its link in the contents list.
  const onPaneKey = (e) => {
    if (e.key !== "ArrowLeft" || !e.target.dataset || !e.target.dataset.k) return;
    const a = document.querySelector(`.hp-idx a[data-hlink="${e.target.dataset.k}"]`);
    if (a) { e.preventDefault(); a.focus(); }
  };
  return (
    <section class="hp" id="help" aria-label="Help" tabIndex={-1} ref={box}>
      <div class="head hp-head">
        <div>
          <h1>Help</h1>
          <p class="muted">How clark works, step by step, and every screen and key. <span class="hp-keyhint">Press <kbd>?</kbd> on any page to open Help; Esc takes you where you were.</span><span class="hp-taphint">Choose <b>Help</b> in the profile circle’s menu on any page to open Help.</span></p>
        </div>
        <div class="hp-actions">
          <label class="search hp-search"><span class="hp-sr">Search Help</span><Icon name="search" />
            <input id="hpQ" ref={search} type="search" placeholder="Search Help" autocomplete="off" aria-describedby="hpQk" value={q} onInput={(e) => { helpQuery.value = e.currentTarget.value; helpTarget.value = null; }}
              onKeyDown={(e) => {
                if (e.key === "Enter") { const a = document.querySelector("#hpRes a.hp-r"); if (a) { e.preventDefault(); a.click(); } }
                else if (e.key === "ArrowDown") { const a = document.querySelector(asked ? "#hpRes a.hp-r" : ".hp-idx a[tabindex='0']"); if (a) { e.preventDefault(); a.focus(); } }
              }} />
            <kbd id="hpQk" aria-label="Press slash to search">/</kbd>
          </label>
        </div>
      </div>
      <div class="hp-tabs" role="tablist" aria-label="Help" onKeyDown={onTabKey}>
        {TABS.map((t) => (
          <button type="button" role="tab" key={t.key} id={`hpTab-${t.key}`} data-htab={t.key} aria-controls="hpPane" aria-selected={tab === t.key ? "true" : "false"}
            tabIndex={tab === t.key ? 0 : -1} onClick={() => setTab(t.key)}>{t.name}</button>
        ))}
      </div>
      {asked ? <div id="hpRes" class="hp-res" aria-live="polite"><Results /></div> : null}
      {asked ? null : <div id="hpPane" class={`hp-pane hp-${tab}`} role="tabpanel" data-tab={tab} aria-labelledby={`hpTab-${tab}`} onKeyDown={onPaneKey}><Pane /></div>}
    </section>
  );
}

/** What the page puts in <main>: Help while it is open, else the open page it was given. */
export function HelpLayer({ children }) {
  return helpOpen.value ? <Help /> : children;
}
