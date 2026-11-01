// The Help panel (#82; BRD 5.13): Start here, How do I… and Reference, all drawn from help/helpContent.json, with one search across
// the three tabs. A layer in place of the open page; Esc or the Back button returns to it. Edit-served pages only (edit/index.js).
import { useEffect, useRef } from "preact/hooks";
import { content, TABS, tabList, tasks, sections, jobs, firstTen, loopSteps, iconLegend, milestoneMarks, buildIndex, resultsView, goLabel, markParts } from "./helpLogic.js";
import { helpOpen, helpTab, helpTarget, helpQuery, helpFocusSearch, setTab, follow, goTo, canGo, closeHelp } from "./helpStore.js";
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
  const where = S.where, on = (p) => S.parts.includes(p);
  if (!S.parts.length) return <Later />;
  return (
    <>
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
      {on("jobs") ? <section class="hp-sec" id="hp-start-jobs" aria-labelledby="hpT3">
        <div class="hp-lab">The jobs you will do most</div><h2 id="hpT3">{T.jobs_title}</h2><p class="hp-lead">{T.jobs_intro}</p>
        <ul class="hp-jobs">
          {jobs().map((j) => (
            <li key={j.id} class="hp-job">
              <a href="#" class="hp-jt" data-hlink={j.place} onClick={(e) => { e.preventDefault(); follow(j.place); }}>{j.title}</a>
              <span>{j.does}</span>
              <GoLink to={j.go} cls="hp-jgo" />
            </li>
          ))}
        </ul>
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
    </>
  );
}

function Contents({ tab }) {
  return (
    <nav class="hp-idx" aria-label="In this part">
      {tabList(tab).map((g) => (
        <div key={g.group}>
          <div class="hp-ig">{g.group}</div>
          <ul>{g.entries.map((e) => <li key={e.id}><a href="#" data-hlink={e.place} onClick={(ev) => { ev.preventDefault(); follow(e.place); }}>{e.title}</a></li>)}</ul>
        </div>
      ))}
    </nav>
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
              <article class="hp-task" key={x.id} id={`hp-howto-${x.id}`} data-k={`howto-${x.id}`}>
                <h3>{x.t}</h3>
                <p class="hp-where">Where: <Md text={x.w} /></p>
                <ol>{x.s.map((s, i) => <li key={i}><Md text={s} /></li>)}</ol>
                {x.n ? <p class="hp-note"><Md text={x.n} /></p> : null}
                <GoLink to={x.go} cls="hp-go" />
              </article>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
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
              <article class="hp-ref" key={x.id} id={`hp-ref-${x.id}`} data-k={`ref-${x.id}`}>
                <h3>{x.t}</h3>
                {x.w ? <p class="hp-where">Where: <Md text={x.w} /></p> : null}
                {x.b.map((b, i) => <Block key={i} b={b} />)}
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
      {r.groups.map((g) => (
        <section class="hp-resg" key={g.tab} aria-label={g.name}>
          <h3>{g.name}</h3>
          {g.results.map((x) => {
            const e = index()[x.n];
            return (
              <a href="#" class="hp-r" key={x.id} data-hit={x.id} onClick={(ev) => { ev.preventDefault(); follow(x.id); }}>
                <span class="hp-rt"><Marked text={x.title} q={helpQuery.value} /></span>
                <span class="hp-rl"><Marked text={x.line < 0 ? e.lines[0] || "" : e.lines[x.line]} q={helpQuery.value} /></span>
              </a>
            );
          })}
        </section>
      ))}
    </>
  );
}

const PANES = { start: Start, howto: HowTo, reference: Reference };

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
    el.scrollIntoView({ block: "start" });
    el.classList.add("hp-found");
    const timer = setTimeout(() => el.classList.remove("hp-found"), 2400);
    return () => clearTimeout(timer);
  }, [helpTarget.value, tab, asked]);
  useEffect(() => { if (helpFocusSearch.value && search.current) { search.current.focus(); search.current.select(); } }, [helpFocusSearch.value]);
  useEffect(() => { if (box.current) box.current.focus({ preventScroll: true }); }, []);
  const onTabKey = (e) => {
    const ks = TABS.map((t) => t.key), i = ks.indexOf(tab);
    const j = e.key === "ArrowRight" ? (i + 1) % ks.length : e.key === "ArrowLeft" ? (i + ks.length - 1) % ks.length : e.key === "Home" ? 0 : e.key === "End" ? ks.length - 1 : -1;
    if (j < 0) return;
    e.preventDefault(); setTab(ks[j]);
    setTimeout(() => { const b = document.getElementById("hpTab-" + ks[j]); if (b) b.focus(); }, 0);
  };
  return (
    <section class="hp" id="help" aria-label="Help" tabIndex={-1} ref={box}>
      <div class="head hp-head">
        <div>
          <h1>Help</h1>
          <p class="muted">How clark works, step by step, and every screen and key. <span class="hp-keyhint">Press <kbd>?</kbd> on any page to open Help; Esc or Back takes you where you were.</span><span class="hp-taphint">Tap <b>?</b> in the top bar on any page to open Help; Back takes you where you were.</span></p>
        </div>
        <div class="hp-actions">
          <button type="button" class="hp-back" id="hpBack" onClick={closeHelp}><Icon name="left" />Back</button>
          <label class="search hp-search"><span class="hp-sr">Search Help</span><Icon name="search" />
            <input id="hpQ" ref={search} type="search" placeholder="Search Help" autocomplete="off" aria-describedby="hpQk" value={q} onInput={(e) => { helpQuery.value = e.currentTarget.value; helpTarget.value = null; }}
              onKeyDown={(e) => {
                if (e.key === "Enter") { const a = document.querySelector("#hpRes a.hp-r"); if (a) { e.preventDefault(); a.click(); } }
                else if (e.key === "ArrowDown") { const a = document.querySelector("#hpRes a.hp-r"); if (a) { e.preventDefault(); a.focus(); } }
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
      {asked ? null : <div id="hpPane" class={`hp-pane hp-${tab}`} role="tabpanel" data-tab={tab} aria-labelledby={`hpTab-${tab}`}><Pane /></div>}
    </section>
  );
}

/** What the page puts in <main>: Help while it is open, else the open page it was given. */
export function HelpLayer({ children }) {
  return helpOpen.value ? <Help /> : children;
}
