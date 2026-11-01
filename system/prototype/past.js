/* Past reports: a mockup for review (design item #125). Three ways in to a past report (a week picker beside "Week ending", the
   Published reports list and a timeline of publications) and one way of showing that you are looking at the past: a banner
   with "Back to now", a tinted frame, and nothing that can be edited. The publications here are made up for the review and
   are not read from the browser's database; nothing on this page changes the project. Opened from the profile menu
   ("Past reports (mockup)") or the address #past. The design note is docs/handoff/design-125-historic-view.md. */
(() => {
  const C = window.C, D = window.ClarkDB, esc = s => C.esc(s);
  const HN = { G: 'On track', A: 'At risk', R: 'Off track' };
  /* the made-up publications: number, the day it was published, the week it covers, health and reason, and a few figures */
  const PUBS = [
    { n: 4, at: '2026-09-30', week: '2026-10-02', h: 'G', why: 'Build on plan; test environment ready a week early.', open: 14, late: 1, ms: 'Design signed off', where: 'Local and to client' },
    { n: 5, at: '2026-10-07', week: '2026-10-09', h: 'A', why: 'Supplier data load slipped by a week; recovery plan agreed.', open: 17, late: 3, ms: 'First data load', where: 'Local and to client' },
    { n: 6, at: '2026-10-14', week: '2026-10-16', h: 'A', why: 'Data load done; two test cases still failing.', open: 16, late: 2, ms: 'First data load', where: 'Local' },
    { n: 7, at: '2026-10-21', week: '2026-10-23', h: 'R', why: 'Go-live date at risk: sign-off needed from the client by 28-10-2026.', open: 19, late: 4, ms: 'User testing starts', where: 'Local and to client' }
  ];
  const NOW_WEEK = '2026-10-30';
  const WAYS = [['picker', 'Week picker'], ['list', 'Published reports'], ['timeline', 'Timeline']];
  const S = { way: 'picker', open: null, mode: 'pub' };   // open: the publication number shown, or null; mode: 'pub' (as published) or 'asat' (rebuilt from history)
  const pub = n => PUBS.find(x => x.n === n);

  /* the way in, one of three */
  const pickerHtml = () => `<div class="pv-bar" id="pvPicker"><label class="muted">Week ending <select class="field" id="pvWeek" aria-label="Week ending">
      <option value="now">${D.fd(NOW_WEEK)} · this week (draft)</option>${PUBS.slice().reverse().map(x => `<option value="${x.n}"${S.open === x.n ? ' selected' : ''}>${D.fd(x.week)} · Publication ${x.n}</option>`).join('')}</select></label>
      <div class="seg" role="group" aria-label="Show"><button data-pv-mode="pub" aria-pressed="${S.mode === 'pub'}">As published</button><button data-pv-mode="asat" aria-pressed="${S.mode === 'asat'}">As at that date</button></div>
      <span class="muted pv-hint">Pick a past week to open it. Every past week is read only.</span></div>`;
  const listHtml = () => `<div class="pv-list" id="pvList"><table class="set stack"><thead><tr><th>#</th><th>Week ending</th><th>Published</th><th>Where</th><th></th></tr></thead><tbody>
      ${PUBS.slice().reverse().map(x => `<tr><td data-l="Publication"><b style="font-weight:500">${x.n}</b></td><td data-l="Week ending">${D.fd(x.week)}</td><td data-l="Published">${D.fd(x.at)}</td><td data-l="Where">${esc(x.where)}</td><td class="acts"><button class="btn sm" data-pv-open="${x.n}">Open</button></td></tr>`).join('')}</tbody></table></div>`;
  const timelineHtml = () => `<div class="pv-tl" id="pvTimeline" role="list" aria-label="Publications in order">
      ${PUBS.map(x => `<div role="listitem" class="pv-tl-i"><button class="pv-dot ${x.h}${S.open === x.n ? ' on' : ''}" data-pv-tl="${x.n}" aria-label="Publication ${x.n}, published ${D.fd(x.at)}, ${HN[x.h]}" aria-pressed="${S.open === x.n}"></button><span><b>${x.n}</b> · ${D.fd(x.at)}</span></div>`).join('')}
      <div role="listitem" class="pv-tl-i now"><span class="pv-dot now" aria-hidden="true"></span><span>Now · draft</span></div></div>`;

  /* the past itself: the banner, then the report in a tinted frame, inert (nothing in it can be focused, typed in or clicked) */
  const pastHtml = x => {
    const asat = S.mode === 'asat';
    const say = asat ? `You are looking at the dashboard as at ${D.fd(x.week)}, rebuilt from the change history.` : `You are looking at ${D.fd(x.at)}, as it was published.`;
    return `<div class="pv-banner" id="pvBanner" role="status"><span class="pv-b-ic">${C.icon('eye', 's')}</span><p><b>${say}</b> <button class="link" id="pvBack">Back to now</button><br>
        <small>${asat ? `Week ending ${D.fd(x.week)} · read only · this was not published in this form` : `Publication ${x.n} · week ending ${D.fd(x.week)} · read only · corrections go into the next report`}</small></p></div>
      <div class="pv-frame${asat ? ' asat' : ''}" id="pvFrame" inert aria-label="${asat ? 'The dashboard as at ' + D.fd(x.week) : 'Publication ' + x.n + ' as it was published'}">
        <div class="pv-mark" aria-hidden="true">${asat ? 'As at ' + D.fd(x.week) : 'Publication ' + x.n + ' · ' + D.fd(x.at)}</div>
        <article class="pv-sheet"><header class="pv-cover"><h2>${esc((C.P() || {}).name || 'Demo project')}</h2><div class="wk"><b>WEEKLY REPORT</b> · Week ending ${D.fd(x.week)}</div></header>
          <div class="pv-body"><div class="pv-tiles"><div class="pv-tile"><span class="hpill ${x.h}">${HN[x.h]}</span><p>${esc(x.why)}</p></div>
            <div class="pv-tile"><b>${x.open}</b><span>open items</span></div><div class="pv-tile"><b>${x.late}</b><span>late</span></div><div class="pv-tile"><b>${esc(x.ms)}</b><span>next milestone</span></div></div>
            <p class="muted pv-foot">${asat ? 'Rebuilt from the change history: the figures are what the project held at the end of that day.' : `The kept copy of the page the client was sent. Published ${D.fd(x.at)}. Publication ${x.n} · ${D.fd(x.at)}. View only.`}</p></div></article></div>`;
  };

  C.views.past = {
    html() {
      const x = S.open ? pub(S.open) : null;
      return `<div class="pv" data-past="${x ? 'on' : 'off'}"><div class="card-h"><h1 class="pv-h">Past reports</h1><span class="tag">Mockup for review</span></div>
        <p class="muted pv-intro">Three ways to reach a past report. The publications on this page are made up; nothing here changes the project.</p>
        <div class="seg pv-ways" role="group" aria-label="Way in">${WAYS.map(([k, l]) => `<button data-pv-way="${k}" aria-pressed="${S.way === k}">${l}</button>`).join('')}</div>
        <div class="card pv-way">${S.way === 'picker' ? pickerHtml() : S.way === 'list' ? listHtml() : timelineHtml()}</div>
        ${x ? pastHtml(x) : '<p class="muted pv-none" id="pvNone">Nothing past is open: you are looking at now.</p>'}</div>`;
    },
    wire() {
      const draw = () => { const y = scrollY; C.render(); scrollTo(0, y); };
      const open = n => { S.open = n; if (S.way !== 'picker') S.mode = 'pub'; draw(); };
      C.$$('[data-pv-way]').forEach(b => b.addEventListener('click', () => { S.way = b.dataset.pvWay; draw(); }));
      C.$$('[data-pv-open]').forEach(b => b.addEventListener('click', () => open(+b.dataset.pvOpen)));
      C.$$('[data-pv-tl]').forEach(b => b.addEventListener('click', () => open(+b.dataset.pvTl)));
      C.$$('[data-pv-mode]').forEach(b => b.addEventListener('click', () => { S.mode = b.dataset.pvMode; draw(); }));
      C.$('#pvWeek')?.addEventListener('change', e => { S.open = e.target.value === 'now' ? null : +e.target.value; draw(); });
      /* Back to now: the past closes and you are on this week's dashboard */
      C.$('#pvBack')?.addEventListener('click', () => { S.open = null; S.mode = 'pub'; C.go('dashboard'); });
    }
  };
  C.pastReset = () => { S.way = 'picker'; S.open = null; S.mode = 'pub'; };
})();

/* ═══ Past publications, real (#342 to #350, #120): the publications this browser really holds, not the made-up ones above ═══
   Every publication is kept: its page and a copy of its data, never pruned; an old one is archived (hidden, never deleted) and can be
   restored. A past publication opens read only behind the banner "Publication N · DD-MM-YYYY · read only", with a tinted frame and
   "Back to now", and its checksum is checked on open. Compare with the one before marks what was added, changed and closed, from the
   two data copies. The dashboard "as at" a date is rebuilt from the change history. A search finds words across the data copies.
   A client comment on the published page names the publication and the work item. The data copy holds only what the client sees:
   a client-facing view shows nothing rather than internal text. The checksum here is a short one (the product uses SHA-256). ═══ */
(() => {
  const C = window.C, D = window.ClarkDB, esc = s => C.esc(s);
  const HN = { G: 'On track', A: 'At risk', R: 'Off track' }, plain = h => C.plain(h || '').replace(/\s+/g, ' ').trim();
  const CLOSED = ['Closed', 'Cancelled', 'Withdrawn', 'Made'];
  /* a short checksum of a page's text (cyrb53); the product keeps a SHA-256 */
  const sum = str => { let h1 = 0xdeadbeef, h2 = 0x41c6ce57; for (let i = 0, ch; i < str.length; i++) { ch = str.charCodeAt(i); h1 = Math.imul(h1 ^ ch, 2654435761); h2 = Math.imul(h2 ^ ch, 1597334677); }
    h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507) ^ Math.imul(h2 ^ (h2 >>> 13), 3266489909); h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507) ^ Math.imul(h1 ^ (h1 >>> 13), 3266489909);
    return (h2 >>> 0).toString(16).padStart(8, '0') + (h1 >>> 0).toString(16).padStart(8, '0'); };
  C.pubSum = sum;
  const msAt = (m, iso) => m.achievedOn && m.achievedOn <= iso ? 'Achieved' : m.manual === 'At risk' ? 'At risk' : m.manual === 'Forecast' ? 'Forecast' : m.agreed < iso ? 'Late' : m.forecast && m.forecast > m.agreed ? 'Expected later' : 'On track';

  /* the project as it stood at the end of a day, from the change history: each later change is put back, newest first. What a client sees only. */
  function snapshot(p, iso) {
    const rows = D.S.history.filter(h => h.code === p.code && (h.at || '').slice(0, 10) > iso).sort((a, b) => b.seq - a.seq);
    const its = new Map(D.S.items.filter(x => x.code === p.code).map(x => [x.id, { ...x }])), ms = new Map(D.S.milestones.filter(m => m.code === p.code).map(m => [m.id, { ...m }]));
    const pr = { health: p.health, reason: p.reason, current: p.current, report: p.report }, gone = new Set();
    rows.forEach(h => {
      if (h.kind === 'item' && its.has(h.id)) { const x = its.get(h.id);
        if (h.field === '+' && !/^Restored/.test(h.text || '')) gone.add(h.id);
        else if (h.field === '*') { if (/^Archived$|^Undone: restored/i.test(h.text || '')) x.archived = false; else if (/^Restored$|^Undone: archived/i.test(h.text || '')) x.archived = true; }
        else if (!['+', '-'].includes(h.field)) x[h.field] = h.from; }
      else if (h.kind === 'ms' && ms.has(h.id) && !['+', '-', '*'].includes(h.field)) ms.get(h.id)[h.field] = h.from;
      else if (h.kind === 'project' && ['health', 'reason', 'current', 'report'].includes(h.field)) pr[h.field] = h.from;
    });
    const secs = ((pr.report || {}).sections || []).filter(s => s.type === 'text' && !s.hidden);
    return { at: iso, health: pr.health, reason: plain(pr.reason), current: plain(pr.current), sections: secs.map(s => ({ id: s.id, title: s.title, text: plain(s.html) })),
      items: [...its.values()].filter(x => x.client && !x.archived && !gone.has(x.id)).sort((a, b) => a.id.localeCompare(b.id)).map(x => ({ id: x.id, type: x.type, title: plain(x.clientText) || x.title, owner: x.owner || '', due: x.due || '', status: x.status, priority: x.priority })),
      ms: [...ms.values()].filter(m => m.client && !m.archived).sort((a, b) => (a.agreed || '').localeCompare(b.agreed || '')).map(m => ({ id: m.id, name: plain(m.clientText) || m.name, agreed: m.agreed || '', state: msAt(m, iso) })) };
  }
  C.pubSnapshot = snapshot;

  /* what changed between two data copies (a before, b after) */
  function compare(a, b) {
    const A = new Map(a.items.map(x => [x.id, x])), B = new Map(b.items.map(x => [x.id, x])), out = { added: [], removed: [], closed: [], changed: [], ms: [], top: [] };
    b.items.forEach(x => { const o = A.get(x.id); if (!o) { out.added.push(x); return; }
      if (CLOSED.includes(x.status) && !CLOSED.includes(o.status)) { out.closed.push({ x, from: o.status }); return; }
      const ch = [['title', 'Title'], ['status', 'Status'], ['owner', 'Owner'], ['due', 'Due'], ['priority', 'Priority']].filter(([k]) => x[k] !== o[k]).map(([k, n]) => `${n}: ${k === 'due' ? (D.fd(o[k]) || 'none') : o[k] || 'none'} to ${k === 'due' ? (D.fd(x[k]) || 'none') : x[k] || 'none'}`);
      if (ch.length) out.changed.push({ x, ch }); });
    a.items.forEach(x => { if (!B.has(x.id)) out.removed.push(x); });
    const AM = new Map(a.ms.map(m => [m.id, m])); b.ms.forEach(m => { const o = AM.get(m.id); if (!o) out.ms.push({ m, what: 'New milestone' }); else { const ch = []; if (o.agreed !== m.agreed) ch.push(`Agreed date: ${D.fd(o.agreed)} to ${D.fd(m.agreed)}`); if (o.state !== m.state) ch.push(`State: ${o.state} to ${m.state}`); if (ch.length) out.ms.push({ m, what: ch.join('; ') }); } });
    if (a.health !== b.health) out.top.push(`Health: ${HN[a.health]} to ${HN[b.health]}`);
    if (a.reason !== b.reason && (a.reason || b.reason)) out.top.push('The reason for the health changed');
    if (a.current !== b.current) out.top.push('The Current state text changed');
    b.sections.forEach(s => { const o = a.sections.find(z => z.id === s.id); if (!o && s.text) out.top.push(`New text section: ${s.title}`); else if (o && o.text !== s.text) out.top.push(`The text of ${s.title} changed`); });
    return out;
  }
  C.pubCompare = compare;
  const nothing = r => !(r.added.length + r.removed.length + r.closed.length + r.changed.length + r.ms.length + r.top.length);

  /* the page kept for a demo publication, made from its data copy (a real publish keeps the real page) */
  const demoPage = (p, d, n) => { const say = t => t ? `<p>${esc(t)}</p>` : '', tbl = (h, r) => r.length ? `<table><tr>${h.map(x => `<th>${x}</th>`).join('')}</tr>${r.map(c => `<tr>${c.map(x => `<td>${esc(x)}</td>`).join('')}</tr>`).join('')}</table>` : '';
    return `<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><title>${esc(p.name)}: week ending ${D.fd(d.at)}</title><style>body{margin:0;font:15px/1.5 Inter,Arial,sans-serif;color:#18232B;background:#F3F5F8}header{background:#14233A;color:#fff;padding:24px 32px}header h1{margin:4px 0;font-size:26px;font-weight:500}.lab{color:#4FD1E8;font-size:12px;letter-spacing:.08em;text-transform:uppercase}.hp{display:inline-block;margin-top:10px;padding:4px 10px;border-radius:4px;font-size:13px;letter-spacing:.06em;text-transform:uppercase;font-weight:500;color:#fff}.hp.G{background:#0F7B5F}.hp.A{background:#E8A013;color:#18232B}.hp.R{background:#BE3A2B}main{max-width:960px;margin:16px auto;padding:0 20px}section{background:#fff;border:1px solid #E0E2E5;border-radius:8px;padding:6px 24px 14px;margin-bottom:12px}h2{font-size:17px;font-weight:500;color:#14233A}table{width:100%;border-collapse:separate;border-spacing:2px;font-size:14px}th{background:#3B5BDB;color:#fff;text-align:left;font-weight:400;padding:6px 10px}td{background:#E0E2E5;padding:6px 10px}footer{max-width:960px;margin:0 auto 24px;padding:0 20px;color:#5A6270;font-size:12px}</style></head><body><header><div class="lab">Weekly report</div><h1>${esc(p.name)}</h1><div>Week ending ${D.fd(d.at)}${p.client ? ' · for ' + esc(p.client) : ''}</div><span class="hp ${d.health}">${HN[d.health]}</span>${say(d.reason)}</header><main>
      ${d.current ? `<section><h2>Current state</h2>${say(d.current)}</section>` : ''}${d.sections.filter(s => s.text).map(s => `<section><h2>${esc(s.title)}</h2>${say(s.text)}</section>`).join('')}
      <section><h2>Work items</h2>${tbl(['ID', 'Item', 'Owner', 'Due', 'Status'], d.items.map(x => [x.id, x.title, x.owner, D.fd(x.due), x.status]))}</section><section><h2>Milestones</h2>${tbl(['Milestone', 'Agreed', 'State'], d.ms.map(m => [m.name, D.fd(m.agreed), m.state]))}</section></main>
      <footer>Published ${D.fd(d.at)}. Publication ${n} · ${D.fd(d.at)}. View only.</footer></body></html>`; };

  /* ── what the Published reports card and the pickers read ── */
  const recs = p => (p.published || []).map((r, i) => ({ r, n: D.pubNo(p, i), arch: !!r.archived, week: r.week || r.at.slice(0, 10) }));
  C.pubList = (p, withArch) => recs(p).filter(x => withArch || !x.arch).reverse();
  const cmOf = (code, n) => D.pubComments(code).filter(c => !n || c.n === n);
  C.cmRows = (code, itemId) => D.pubComments(code).filter(c => c.item === itemId).map(c => ({ ...c }));

  const PS = { n: null, mode: 'pub', date: '', unlock: false, q: '' };   /* the open past publication; mode: pub, asat or cmp */
  let showArch = false, searchQ = '';
  const pastRec = (p, n) => recs(p).find(x => x.n === n);
  C.openPast = (n, opts = {}) => { const p = C.P(); Object.assign(PS, { n: n || null, mode: opts.mode || 'pub', unlock: false, q: opts.q || '' });
    PS.date = opts.date || (n && pastRec(p, n) ? pastRec(p, n).week : D.addDays(D.friday(), -7)); C.go('pastpub'); };
  C.pastPickHtml = p => { const l = C.pubList(p); if (!l.length) return '';
    return `<select class="field" id="wkPast" aria-label="Open a published week" style="width:auto;max-width:260px"><option value="">Published weeks</option>${l.map(x => `<option value="${x.n}">${D.fd(x.week)} · Publication ${x.n}</option>`).join('')}<option value="asat">Dashboard as at a date…</option></select>`; };
  document.addEventListener('change', e => { if (e.target.id !== 'wkPast' || !e.target.value) return; const v = e.target.value; if (v === 'asat') C.openPast(null, { mode: 'asat' }); else C.openPast(+v); });

  /* ── Archive and Restore: one step, with Undo ── */
  function archive(n, on) { const p = C.P(), list = D.clone(p.published || []), i = list.findIndex((r, k) => (r.n || k + 1) === n); if (i < 0) return; if (on) list[i].archived = true; else delete list[i].archived;
    const u = D.change('project', p, { published: list }, D.who('in the published reports'), `${on ? 'Archived' : 'Restored'} Publication ${n}`); if (!u) return; C.refresh();
    C.toast(on ? `Archived Publication ${n}. It is hidden from the list and the pickers; it is not deleted.` : `Restored Publication ${n}`, u); }
  C.pubArchive = archive;

  /* ── search across past publications: words in the data copies, all of them (#350) ── */
  function search(p, q) { const toks = q.toLowerCase().split(/\s+/).filter(Boolean); if (!toks.length) return [];
    return C.pubList(p).map(({ r, n, week }) => { const cp = D.pubCopy(p.code, n), d = cp && cp.data; if (!d) return null;
      const lines = [['Health', HN[d.health] + (d.reason ? ': ' + d.reason : '')], ['Current state', d.current], ...d.sections.map(s => [s.title, s.text]), ...d.items.map(x => [`${x.id}`, `${x.title} · ${x.owner || 'no owner'} · ${x.status}`]), ...d.ms.map(m => ['Milestone', `${m.name} · ${m.state}`])].filter(([, t]) => t);
      const hay = lines.map(([k, t]) => k + ' ' + t).join(' ').toLowerCase(); if (!toks.every(t => hay.includes(t))) return null;
      return { n, week, hits: lines.filter(([k, t]) => toks.some(z => (k + ' ' + t).toLowerCase().includes(z))).slice(0, 4) }; }).filter(Boolean); }
  const mark = (t, q) => { let h = esc(t); q.split(/\s+/).filter(Boolean).forEach(w => { h = h.replace(new RegExp('(' + w.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi'), '<mark>$1</mark>'); }); return h; };
  const resultsHtml = (p, q) => { const r = search(p, q); if (!q.trim()) return '';
    return `<div class="pp-res" id="pbRes" role="status"><p class="muted">${r.length ? `${r.length} ${r.length === 1 ? 'publication has' : 'publications have'} all of those words. Archived ones are not searched. Open shows it read only.` : 'No publication has those words. Archived ones are not searched.'}</p>
      ${r.map(x => `<div class="pp-hit"><div><b>Publication ${x.n}</b> <span class="muted">· week ending ${D.fd(x.week)}</span><ul>${x.hits.map(([k, t]) => `<li><span class="muted">${esc(k)}</span> ${mark(t.length > 140 ? t.slice(0, 140) + '…' : t, q)}</li>`).join('')}</ul></div><button class="btn sm" data-pbhit="${x.n}">Open</button></div>`).join('')}</div>`; };

  /* ── the Published reports card ── */
  C.pubsCardHtml = p => {
    const all = recs(p), na = all.filter(x => x.arch).length, list = C.pubList(p, showArch), cm = D.pubComments(p.code);
    return `<div class="card" id="pubs"><div class="card-h"><h2>Published reports · ${esc(p.name)}</h2></div><p class="muted" style="font-size:14px;margin:-4px 0 12px">Every time you publish, the report gets the next number for this project, and the page and a copy of its data are kept. Every publication is kept; none is pruned. A Word copy made in the same Publish has the same number. Open shows it read only. Archive hides an old one from this list and the pickers; it is never deleted.</p>
      <div class="pp-tools"><form id="pbSearch" class="pp-search" role="search"><input class="field" id="pbQ" type="search" placeholder="Search past reports for a word" aria-label="Search past reports" value="${esc(searchQ)}"><button class="btn sm">Search</button></form>
        <button class="arch-pill" id="pbArchBtn" aria-pressed="${showArch}">${C.icon('archive', 's')}Show archived <em>${na}</em></button><button class="btn sm" id="pbCm">Client comments <em class="pp-n">${cm.length}</em></button>${all.length ? '' : '<button class="btn sm" id="pbDemo">Add 12 demo publications</button>'}</div>
      ${resultsHtml(p, searchQ)}
      ${list.length ? `<table class="set stack ppl"><thead><tr><th>#</th><th>Date and time</th><th>Where</th><th>Who</th><th>Comments</th><th></th></tr></thead><tbody>${list.map(({ r, n, arch }) => `<tr data-pub="${n}"${arch ? ' class="arch-row"' : ''}><td class="nm" data-l="Publication"><b style="font-weight:500">${n}</b>${arch ? ' <span class="tag arch">Archived</span>' : ''}</td><td data-l="Date and time">${D.fd(r.at.slice(0, 10))} ${esc(r.at.slice(11))}</td><td data-l="Where">${esc(r.where || (r.client ? 'Local and to client' : 'Local'))}${r.word ? ' · Word (same number)' : ''}${r.pdf ? ' · PDF' : ''}</td><td data-l="Who">${esc(r.who || 'Not recorded')}</td><td data-l="Comments">${cmOf(p.code, n).length || '<span class="muted">None</span>'}</td>
        <td class="acts">${D.pubCopy(p.code, n) ? `<button class="btn sm" data-pubopen="${n}">Open</button><button class="btn sm quiet" data-pubtab="${n}">New tab</button>` : '<span class="muted">Not kept</span>'}${arch ? `<button class="btn sm quiet" data-pbrest="${n}">Restore</button>` : `<button class="btn sm quiet" data-pbarch="${n}">Archive</button>`}</td></tr>`).join('')}</tbody></table>` : `<p class="muted" id="pubsNone">${all.length ? 'Every publication is archived. Show archived brings them back.' : 'Nothing published yet. Each publish is listed here with its number.'}</p>`}</div>`; };
  C.pubsWire = () => {
    const p = C.P(); if (!p) return;
    C.$$('[data-pubopen]').forEach(b => b.addEventListener('click', () => C.openPast(+b.dataset.pubopen)));
    C.$$('[data-pubtab]').forEach(b => b.addEventListener('click', () => C.openPub(+b.dataset.pubtab)));
    C.$$('[data-pbarch]').forEach(b => b.addEventListener('click', () => archive(+b.dataset.pbarch, true)));
    C.$$('[data-pbrest]').forEach(b => b.addEventListener('click', () => archive(+b.dataset.pbrest, false)));
    C.$('#pbArchBtn')?.addEventListener('click', () => { showArch = !showArch; C.render(); C.$('#pbArchBtn')?.focus(); });
    C.$('#pbSearch')?.addEventListener('submit', e => { e.preventDefault(); searchQ = C.$('#pbQ').value.trim(); C.render(); C.$('#pbQ')?.focus(); });
    C.$$('[data-pbhit]').forEach(b => b.addEventListener('click', () => C.openPast(+b.dataset.pbhit, { q: searchQ })));
    C.$('#pbCm')?.addEventListener('click', () => C.cmDialog());
    C.$('#pbDemo')?.addEventListener('click', () => C.demoPubs());
  };

  /* ── demo publications: twelve weekly publications made from the project, with a change history behind them, so the past views can be tried ── */
  C.demoPubs = async () => {
    const p = C.P(); if (!p || (p.published || []).length) return C.toast('Demo publications are added only to a project with none.');
    const F = D.friday(), W = Array.from({ length: 12 }, (_, k) => D.addDays(F, -7 * (12 - k))), how = D.who('prototype demo history'), rows = [];
    const row = (k, kind, id, field, from, to, text) => rows.push({ kind, id, code: p.code, field, from, to, how, at: `${W[k]} 10:00`, ...(text ? { text } : {}) });
    const its = D.S.items.filter(x => x.code === p.code && !x.archived && x.client).sort((a, b) => a.id.localeCompare(b.id)), first = t => D.STATUSES[t][0];
    its.slice(-3).forEach((x, i) => row([5, 7, 9][i], 'item', x.id, '+', undefined, undefined, 'Created'));
    const rest = its.slice(0, -3), closed = rest.filter(x => CLOSED.includes(x.status)), live = rest.filter(x => !CLOSED.includes(x.status));
    live.filter(x => x.status !== first(x.type)).slice(0, 4).forEach((x, i) => row([3, 4, 6, 8][i], 'item', x.id, 'status', first(x.type), x.status));
    closed.slice(0, 2).forEach((x, i) => row([8, 10][i], 'item', x.id, 'status', first(x.type), x.status));
    live.filter(x => x.due).slice(-3).forEach((x, i) => row([2, 6, 9][i], 'item', x.id, 'due', D.addDays(x.due, -7), x.due));
    live.slice(0, 2).forEach((x, i) => row([4, 7][i], 'item', x.id, 'priority', x.priority === 'High' ? 'Medium' : 'High', x.priority));
    const o = ['G', 'A', 'R'].filter(h => h !== p.health); row(3, 'project', p.code, 'health', o[0], o[1]); row(8, 'project', p.code, 'health', o[1], p.health);
    const r0 = 'Build on plan; test environment ready.', r1 = 'Supplier data load slipped; recovery plan agreed.'; row(3, 'project', p.code, 'reason', r0, r1); row(8, 'project', p.code, 'reason', r1, p.reason);
    const c0 = '<p>Setting up the project: the team is agreed, the plan is being drawn and the first tests are booked.</p>', c1 = '<p>The build is under way and the first data load is being prepared.</p>'; row(2, 'project', p.code, 'current', c0, c1); row(7, 'project', p.code, 'current', c1, p.current);
    const m0 = D.S.milestones.find(m => m.code === p.code && m.agreed && !m.archived && m.client); if (m0) row(6, 'ms', m0.id, 'agreed', D.addDays(m0.agreed, -14), m0.agreed);
    await D.write(D.addHistory(rows));
    const me = (D.S.profile || {}).name || 'You', loc = p.publish || {}, recsNew = [];
    for (let k = 0; k < 12; k++) { const n = k + 1, d = snapshot(p, W[k]), html = demoPage(p, d, n); await D.pubKeep(p.code, n, { n, code: p.code, at: W[k] + ' 16:00', html, texts: {}, data: d, sum: sum(html) });
      recsNew.push({ at: W[k] + ' 16:00', week: W[k], local: loc.local || '', client: k % 3 === 0 ? (loc.client || 'client folder') : '', word: k % 4 === 0, pdf: false, n, who: me, where: k % 3 === 0 ? 'Local and to client' : 'Local', hseq: D.lastSeq() }); }
    const u = D.change('project', p, { published: recsNew }, D.who('by adding demo publications'), '12 demo publications added');
    const pick = [[5, its[0]], [8, its[1]], [10, its[2]]].filter(([, x]) => x), by = ['Priya Nair (client)', 'Tom Hale (client)', 'Priya Nair (client)'], says = ['Can this be done before the board meeting?', 'We need this owner to be named.', 'Thank you: this has been closed on our side too.'];
    D.pubCommentsSet(p.code, pick.map(([k, x], i) => ({ id: 'c' + (i + 1), n: k + 1, item: x.id, by: by[i], at: W[k] + ' 18:20', text: says[i] })));
    C.refresh(); C.toast('Added 12 demo publications, with a change history behind them (prototype)', () => { u && u(); });
  };

  /* ── client comments: a comment on the published page names the publication and the item; the author brings them in here (#120) ── */
  const cmParse = txt => String(txt || '').split(/\r?\n/).map(l => l.trim()).filter(l => /^clark-comment\|/.test(l)).map(l => { const [, n, item, by, ...t] = l.split('|'); return { n: +n, item: (item || '').trim(), by: (by || '').trim(), text: t.join('|').trim() }; }).filter(c => c.n > 0 && c.item && c.text);
  C.cmParse = cmParse;
  function cmAdd(rows) { const p = C.P(), have = D.pubComments(p.code), ok = [], bad = [];
    rows.forEach(c => { const rec = recs(p).find(x => x.n === c.n), it = D.S.items.find(x => x.id === c.item && x.code === p.code);
      if (!rec) bad.push(`Publication ${c.n} is not one of this project's publications.`); else if (!it) bad.push(`${c.item} is not a work item in this project.`); else ok.push({ id: 'c' + (have.length + ok.length + 1) + '-' + Date.now().toString(36), n: c.n, item: c.item, by: c.by || 'The client', at: D.stamp(), text: c.text }); });
    const u = ok.length ? D.pubCommentsSet(p.code, [...have, ...ok]) : null; return { ok, bad, u }; }
  C.cmAdd = cmAdd;
  C.cmDialog = () => { const p = C.P(), list = () => D.pubComments(p.code).slice().reverse();
    const body = () => `${list().length ? `<ul class="cm-list">${list().map(c => `<li><span class="tag cl">Publication ${c.n}</span> <b>${esc(c.item)}</b> <span class="muted">· ${esc(c.by)} · ${D.fd(c.at.slice(0, 10))}</span><p>${esc(c.text)}</p></li>`).join('')}</ul>` : '<p class="muted" id="cmNone">No client comments yet.</p>'}`;
    C.dialog(`<form id="cmF"><div class="dlg-h"><h2>Client comments</h2><p>Each comment is tied to the publication the client saw and the work item. On the published page the client adds a comment and presses Copy my comments; paste what they send you here.</p></div>
      <div class="dlg-b"><div id="cmBody">${body()}</div><label class="muted" for="cmPaste" style="display:block;margin-top:12px">Paste comments from the client</label><textarea class="field" id="cmPaste" rows="3" placeholder="clark-comment|5|${esc((D.S.items.find(x => x.code === p.code) || {}).id || 'ID')}|Priya Nair|Can this be done sooner?"></textarea><p class="muted" id="cmMsg" role="status" style="font-size:13px;margin:6px 0 0">In the product a comment comes back to the project itself; here the client's page is a file, so the comments travel as text.</p></div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Close</button><button class="btn pri" id="cmAdd">Add the comments</button></div></form>`, d => {
      C.$('#cmF', d).addEventListener('submit', e => { e.preventDefault(); const rows = cmParse(C.$('#cmPaste', d).value); if (!rows.length) { C.$('#cmMsg', d).textContent = 'Nothing to add: each line reads clark-comment, the publication number, the work item ID, a name and the comment, with | between.'; return; }
        const r = cmAdd(rows); C.$('#cmMsg', d).textContent = `${r.ok.length ? `Added ${r.ok.length}. ` : 'Nothing was added. '}${r.bad.join(' ')}`; if (r.ok.length) { C.$('#cmPaste', d).value = ''; C.$('#cmBody', d).innerHTML = body(); C.refresh(); C.toast(`${r.ok.length} client ${r.ok.length === 1 ? 'comment' : 'comments'} added`, r.u); } }); }); };

  /* ═══ the past publication page ═══ */
  const tag = (c, t) => `<span class="pc-tag ${c}">${t}</span>`;
  const line = x => `<b>${esc(x.id)}</b> ${esc(x.title)}`;
  const compareHtml = (p, n, cp) => {
    const prev = recs(p).filter(x => x.n < n && D.pubCopy(p.code, x.n)).pop();
    if (!cp.data) return `<div class="pc card" id="pcCmp"><p class="muted">No data copy was kept for Publication ${n}, so it can't be compared.</p></div>`;
    if (!prev) return `<div class="pc card" id="pcCmp"><p class="muted">Publication ${n} is the first one kept for this project, so there is nothing before it to compare with.</p></div>`;
    const pc = D.pubCopy(p.code, prev.n); if (!pc.data) return `<div class="pc card" id="pcCmp"><p class="muted">No data copy was kept for Publication ${prev.n}, so Publication ${n} can't be compared with it.</p></div>`;
    const r = compare(pc.data, cp.data), sec = (t, items) => items.length ? `<h3>${t}</h3><ul class="pc-list">${items.join('')}</ul>` : '';
    return `<div class="pc card" id="pcCmp"><h2 style="margin:0 0 4px;font-size:17px;font-weight:500">Publication ${n} compared with Publication ${prev.n}</h2><p class="muted" style="margin:0 0 10px;font-size:13px">${D.fd(recs(p).find(x => x.n === n).week)} against ${D.fd(prev.week)}. Marked from the two data copies; only what the client sees.</p>
      ${nothing(r) ? '<p id="pcSame">Nothing changed between the two.</p>' : `${sec('The report', r.top.map(t => `<li>${tag('ch', 'Changed')} ${esc(t)}</li>`))}${sec('Work items', [...r.added.map(x => `<li>${tag('add', 'Added')} ${line(x)} <span class="muted">· ${esc(x.status)}</span></li>`), ...r.closed.map(({ x, from }) => `<li>${tag('cl', 'Closed')} ${line(x)} <span class="muted">· was ${esc(from)}</span></li>`), ...r.changed.map(({ x, ch }) => `<li>${tag('ch', 'Changed')} ${line(x)} <span class="muted">· ${esc(ch.join('; '))}</span></li>`), ...r.removed.map(x => `<li>${tag('rm', 'No longer shown')} ${line(x)}</li>`)])}${sec('Milestones', r.ms.map(({ m, what }) => `<li>${tag(what === 'New milestone' ? 'add' : 'ch', what === 'New milestone' ? 'Added' : 'Changed')} <b>${esc(m.name)}</b> <span class="muted">· ${esc(what)}</span></li>`))}`}</div>`; };
  const asatHtml = (p, iso) => { const d = snapshot(p, iso), open = d.items.filter(x => !CLOSED.includes(x.status)), late = open.filter(x => x.type === 'A' && x.due && x.due < iso), next = d.ms.find(m => m.state !== 'Achieved');
    return `<div class="pv-frame asat" id="pvFrame" aria-label="The dashboard as at ${D.fd(iso)}"><div class="pv-mark" aria-hidden="true">As at ${D.fd(iso)}</div><article class="pv-sheet"><header class="pv-cover"><h2>${esc(p.name)}</h2><div class="wk"><b>WEEKLY REPORT</b> · As at ${D.fd(iso)}</div></header>
      <div class="pv-body"><div class="pv-tiles"><div class="pv-tile"><span class="hpill ${d.health}">${HN[d.health]}</span>${d.reason ? `<p>${esc(d.reason)}</p>` : ''}</div><div class="pv-tile"><b>${open.length}</b><span>open items</span></div><div class="pv-tile"><b>${late.length}</b><span>late actions</span></div><div class="pv-tile"><b>${next ? esc(next.name) : 'None'}</b><span>next milestone</span></div></div>
        ${d.current ? `<h3 class="pc-h">Current state</h3><p>${esc(d.current)}</p>` : ''}<h3 class="pc-h">Work items (${d.items.length})</h3>${d.items.length ? `<ul class="pc-list">${d.items.map(x => `<li>${line(x)} <span class="muted">· ${esc(x.status)}${x.due ? ' · due ' + D.fd(x.due) : ''}</span></li>`).join('')}</ul>` : '<p class="muted">None shown to the client at that date.</p>'}
        <p class="muted pv-foot">Rebuilt from the change history: what the project held at the end of that day, as the client would have seen it. This was not published in this form.</p></div></article></div>`; };
  const frameHtml = (p, n, cp, rec) => { const bad = cp.sum && sum(cp.html) !== cp.sum;
    if (bad && !PS.unlock) return `<div class="pc-bad" id="pcBad" role="alert"><b>Publication ${n} no longer matches what was published.</b><p>The kept file has changed since it was saved, so it may not be what the client saw. Do not rely on it. Restore the file from the folder it was saved to, or publish a new report.</p><button class="btn sm" id="pcShow">Show it anyway</button></div>`;
    const doc = cp.html.replace('<head>', '<head><script>window.CLARK_READONLY=1<\/script>');
    return `<div class="pv-frame" id="pvFrame" aria-label="Publication ${n} as it was published"><div class="pv-mark" aria-hidden="true">Publication ${n} · ${D.fd(rec.r.at.slice(0, 10))}</div><iframe class="pv-if" id="pvIf" sandbox="allow-scripts" title="Publication ${n}, week ending ${D.fd(rec.week)}, as it was published" srcdoc="${esc(doc)}"></iframe></div>`; };

  C.views.pastpub = {
    html() {
      const p = C.P(), n = PS.n, rec = n ? pastRec(p, n) : null, cp = n ? D.pubCopy(p.code, n) : null, mode = n ? PS.mode : 'asat';
      const iso = PS.date || D.addDays(D.friday(), -7), all = C.pubList(p, true);
      const banner = mode === 'asat' ? `<b>You are looking at the dashboard as at ${D.fd(iso)}, rebuilt from the change history.</b> <button class="link" id="pvBack">Back to now</button><br><small>Read only · this was not published in this form</small>`
        : `<b>Publication ${n} · ${rec ? D.fd(rec.r.at.slice(0, 10)) : ''} · read only.</b> <button class="link" id="pvBack">Back to now</button><br><small>${mode === 'cmp' ? 'Compared with the publication before' : 'The report as it was published'} · week ending ${rec ? D.fd(rec.week) : ''}${rec && rec.arch ? ' · archived' : ''} · corrections go into the next report</small>`;
      const found = PS.q && cp && cp.data ? search(p, PS.q).find(x => x.n === n) : null;
      return `<div class="pv" data-past="on" id="ppPast"><div class="card-h"><h1 class="pv-h">Past publication</h1><span class="tag">Read only</span></div>
        <div class="card pv-way"><div class="pv-bar"><label class="muted">Publication <select class="field" id="ppSel" aria-label="Publication">${n ? '' : '<option value="">None open</option>'}${all.map(x => `<option value="${x.n}"${x.n === n ? ' selected' : ''}>${x.n} · ${D.fd(x.week)}${x.arch ? ' · archived' : ''}</option>`).join('')}</select></label>
          <div class="seg" role="group" aria-label="Show">${n ? `<button data-pp-mode="pub" aria-pressed="${mode === 'pub'}">As published</button>` : ''}<button data-pp-mode="asat" aria-pressed="${mode === 'asat'}">As at a date</button>${n ? `<button data-pp-mode="cmp" aria-pressed="${mode === 'cmp'}">Compare with the one before</button>` : ''}</div>
          ${mode === 'asat' ? `<label class="muted">Date <input class="field" type="date" id="ppDate" value="${iso}" max="${D.TODAY}" style="width:auto"></label>` : ''}</div></div>
        <div class="pv-banner" id="pvBanner" role="status"><span class="pv-b-ic">${C.icon('eye', 's')}</span><p>${banner}</p></div>
        ${found ? `<div class="pp-found" id="ppFound"><b>Found here for “${esc(PS.q)}”:</b> ${found.hits.map(([k, t]) => `<span>${esc(k)}: ${mark(t.length > 100 ? t.slice(0, 100) + '…' : t, PS.q)}</span>`).join(' · ')}</div>` : ''}
        ${mode === 'asat' ? asatHtml(p, iso) : !cp ? '<p class="muted" id="pcGone">That copy is not kept.</p>' : mode === 'cmp' ? compareHtml(p, n, cp) : frameHtml(p, n, cp, rec)}
        ${n && cp ? `<p class="muted pc-sum" id="pcSum">${cp.sum ? `Checksum ${cp.sum}, checked when it opened${sum(cp.html) === cp.sum ? ': it matches.' : ': it does not match.'}` : 'No checksum was kept for this publication.'} <button class="link" id="pcTamper">Prototype: ${sum(cp.html) !== cp.sum && cp.sum ? 'put the kept file back' : 'change the kept file to see the warning'}</button></p>` : ''}</div>`;
    },
    wire() {
      const p = C.P(), draw = () => { const y = scrollY; C.render(); scrollTo(0, y); };
      C.$('#pvBack')?.addEventListener('click', () => C.go('dashboard'));
      C.$('#ppSel')?.addEventListener('change', e => { if (e.target.value) C.openPast(+e.target.value, { mode: PS.mode === 'asat' ? 'asat' : PS.mode }); });
      C.$$('[data-pp-mode]').forEach(b => b.addEventListener('click', () => { PS.mode = b.dataset.ppMode; if (PS.mode === 'asat' && PS.n && !PS.date) PS.date = pastRec(p, PS.n).week; draw(); }));
      C.$('#ppDate')?.addEventListener('change', e => { PS.date = e.target.value || PS.date; draw(); });
      C.$('#pcShow')?.addEventListener('click', () => { PS.unlock = true; draw(); });
      C.$('#pcTamper')?.addEventListener('click', () => { const cp = D.pubCopy(p.code, PS.n); if (!cp) return; const t = '<!-- changed -->'; const bad = cp.sum && sum(cp.html) !== cp.sum;
        cp.html = bad ? cp.html.split(t).join('') : cp.html + t; PS.unlock = false; D.pubKeep(p.code, PS.n, cp); draw(); });
    }
  };
})();
