/* clark prototype: the Use Cases page (the planning repo #162, the accepted mockup). Every use case of the project, on the dashboard or not,
   in the Milestones page's look: a summary strip, one row each (reference, name, where it stands, status word, work items, the eye
   on the right, a caret), the detail in place under the row, and the pills to narrow and sort the list. Edit only: existing use cases
   change in place, each change one step with Undo; there is no Add, Archive or Delete here (new ones come from the project record
   or the Excel import). The eye is the dashboard's own switch, and the published page shows only the use cases that are on. */
(function () {
  'use strict';
  const C = window.C, D = C.D, esc = C.esc, UI = C.UI;
  const P = () => C.P();
  const STATUSES = ['On track', 'Flag', 'High risk'], WORST = ['High risk', 'Flag', 'On track'];   /* the schema's three; there is no Done */
  const HOW = 'on the Use Cases page';
  const word = s => C.ucWord(s);
  const refOf = u => u.ref || u.id, titles = u => String(u.title || '').split('\n'), nameOf = u => titles(u).join(' · ');
  const tagOf = u => refOf(u).split(/,| and /).map(x => x.trim()).filter(Boolean).map(esc).join(' + ');

  /* the group of a use case: the number before the first dot of its reference (1.3 is in Group 1); one with no number is in Other */
  const groupOf = u => { const m = /^\s*(\d+)/.exec(String(u.id || '')); return m ? String(+m[1]) : 'Other'; };
  const groupLab = g => g === 'Other' ? 'Other' : 'Group ' + g;
  const groups = () => { const gs = [...new Set(all().map(groupOf))]; return gs.filter(g => g !== 'Other').sort((a, b) => a - b).concat(gs.includes('Other') ? ['Other'] : []); };
  const numKey = u => String(u.id || '').split('.').map(n => { const v = parseInt(n, 10); return isNaN(v) ? 1e9 : v; });
  const byNum = (a, b) => { const x = numKey(a), y = numKey(b); for (let i = 0; i < Math.max(x.length, y.length); i++) { const d = (x[i] ?? -1) - (y[i] ?? -1); if (d) return d; } return String(a.id).localeCompare(String(b.id)); };

  const all = () => D.S.usecases.filter(u => u.code === P()?.code);
  const itemsOf = u => C.items().filter(x => x.uc === u.id);
  const openOf = u => itemsOf(u).filter(C.isOpen);
  /* its next steps: its open actions only, as main counts them (a risk, issue or decision is a work item, not a next step) */
  const isStep = x => x.type === 'A' && C.isOpen(x);
  const stepsOf = u => itemsOf(u).filter(isStep);
  /* its linked milestones: only those its open next steps point at, in date order (main's rule, and the published file's) */
  const msOf = steps => { const ids = new Set(steps.map(x => x.ms).filter(Boolean)); return C.mss().filter(m => ids.has(m.id)); };

  const SORTS = {
    num: { t: 'Use case', f: byNum },
    status: { t: 'Status', f: (a, b) => WORST.indexOf(a.status) - WORST.indexOf(b.status) || byNum(a, b) },
    open: { t: 'Open work items', f: (a, b) => openOf(b).length - openOf(a).length || byNum(a, b) },
    name: { t: 'Name', f: (a, b) => nameOf(a).localeCompare(nameOf(b)) || byNum(a, b) },
  };
  /* the filters and the sort, remembered per project */
  const F0 = { g: [], st: [], on: 'all', sort: 'num', q: '' };
  const fOf = code => Object.assign({}, F0, (C.store.get('ucPage', {}) || {})[code] || {});
  const F = () => fOf(P().code);
  const setF = o => { const s = C.store.get('ucPage', {}) || {}; s[P().code] = { ...F(), ...o }; C.store.set('ucPage', s); };
  C.ucPageFilter = fOf;
  const narrowed = f => f.g.length || f.st.length || f.on !== 'all' || f.q.trim();
  function list() {
    const f = F(), q = f.q.trim().toLowerCase();
    return all().filter(u => (!f.g.length || f.g.includes(groupOf(u))) && (!f.st.length || f.st.includes(u.status)) && (f.on === 'all' || (f.on === 'on') === !!u.client)
      && (!q || [u.id, u.ref, u.title, u.headline, C.plain(u.standing)].join(' ').toLowerCase().includes(q))).sort((SORTS[f.sort] || SORTS.num).f);
  }
  const opened = () => C.store.get('ucPageOpen', '');

  /* ── the page ── */
  const stripHtml = us => { const n = s => us.filter(u => u.status === s).length, order = STATUSES.filter(s => n(s)), on = us.filter(u => u.client).length;
    return `<div class="uc-strip ucp-strip"><span class="uc-total"><b>${us.length}</b> use case${us.length === 1 ? '' : 's'}</span>${order.map(s => `<span class="uc-count">${word(s)}<b>${n(s)}</b></span>`).join('')}<span class="ucp-on">${C.icon('eye', 's')}<b>${on}</b> on the dashboard</span><span class="uc-meter" aria-hidden="true">${order.map(s => `<i class="${{ 'On track': 'g', Flag: 'a', 'High risk': 'r' }[s]}" style="flex:${n(s)}"></i>`).join('')}</span></div>`; };
  const pillLab = (t, vs, lab) => vs.length ? `${t}: ${vs.map(lab || (v => v)).join(', ')}` : t;
  const wiWords = u => { const n = itemsOf(u).length, o = openOf(u).length; return n ? `${n} work item${n === 1 ? '' : 's'} · ${o} open` : 'No work items'; };
  function rowHtml(u) {
    const K = esc(u.key), on = !!u.client, isOpen = opened() === u.key, R = esc(refOf(u));
    return `<div class="ucp-row${on ? '' : ' off'}${isOpen ? ' open' : ''}" data-ucp="${K}">
      <span class="ucp-ref"><span class="uc-tag">${tagOf(u)}</span></span>
      <span class="ucp-name" title="${esc(nameOf(u))}">${esc(nameOf(u))}</span>
      <span class="ucp-head" title="${esc(u.headline)}">${esc(u.headline || 'No headline yet')}</span>
      <span class="ucp-st"><button class="ucw-btn" data-ucp-status="${K}" aria-haspopup="menu" aria-label="${esc(u.status)}: the status of use case ${R}. Change it">${word(u.status)}</button></span>
      <span class="ucp-wi">${wiWords(u)}</span>
      <button class="ucp-eye" data-ucp-eye="${K}" aria-pressed="${on}" aria-label="${on ? `On the dashboard: use case ${R}. Select to take it off` : `Not on the dashboard: use case ${R}. Select to put it on`}" title="${on ? 'Shown: on the dashboard and the published page. Select to take it off' : 'Not shown. Select to put it on the dashboard'}">${C.icon(on ? 'eye' : 'eyeoff', 's')}<span class="w">${on ? 'On the dashboard' : 'Not on the dashboard'}</span></button>
      <button class="ib ucp-car" data-ucp-tog="${K}" aria-expanded="${isOpen}" aria-controls="ucpd-${K.replace(/[^\w-]/g, '_')}" aria-label="${isOpen ? 'Close' : 'Open'} the detail of use case ${R}">${C.icon('chev', 's chev')}</button>
    </div>
    <div class="ucp-d${isOpen ? ' open' : ''}" id="ucpd-${K.replace(/[^\w-]/g, '_')}" data-ucpd="${K}">${isOpen ? detailHtml(u) : ''}</div>`;
  }
  const HIST_N = 8; let histAll = '';
  function histHtml(u) {
    const rows = D.historyOf('uc', u.id).filter(h => h.code === u.code);
    if (!rows.length) return '<p class="muted ucp-none">No changes recorded yet.</p>';
    const line = h => { const w = D.whoHow(h), life = { '+': 1, '-': 1, '*': 1 }[h.field];
      const what = life ? esc(h.text || 'Changed') : D.RICH.includes(h.field) ? `<b>${esc(D.fieldName(h.field, 'uc'))}</b> changed` : (() => { const a = D.showVal(h.field, h.from), b = D.showVal(h.field, h.to); return `<b>${esc(D.fieldName(h.field, 'uc'))}</b>${a === null ? ' changed' : `: ${esc(String(a).split('\n')[0])} → ${esc(String(b).split('\n')[0])}`}`; })();
      return `<li><span class="ucp-hw">${what}</span><span class="ucp-hm">${esc([w.who, w.how].filter(Boolean).join(', '))} · ${esc(D.when(h))}</span></li>`; };
    const shown = histAll === u.key ? rows : rows.slice(0, HIST_N);
    return `<ul class="ucp-hist">${shown.map(line).join('')}</ul>${rows.length > HIST_N ? `<button class="link" data-ucp-hall="${esc(u.key)}">${histAll === u.key ? 'Show the latest only' : `Show all ${rows.length} changes`}</button>` : ''}`;
  }
  function detailHtml(u) {
    const K = esc(u.key), R = esc(refOf(u)), steps = stepsOf(u).sort((a, b) => (a.due || '9').localeCompare(b.due || '9')), ms = msOf(steps), n = itemsOf(u).length;
    return `<div class="ucp-in">
      <div class="ucp-f"><span class="ucd-lab">Name</span><span class="ucp-ce ucp-nm" contenteditable="plaintext-only" role="textbox" spellcheck="true" data-ucp-name="${K}" aria-label="Name of use case ${R}">${esc(titles(u)[0])}</span></div>
      <div class="ucp-f"><span class="ucd-lab">Headline</span><span class="ucp-ce" contenteditable="plaintext-only" role="textbox" spellcheck="true" data-ucp-head="${K}" aria-label="Headline of use case ${R}" data-ph="One line on where it stands">${esc(u.headline)}</span></div>
      <div class="ucd-cols"><div><div class="ucd-lab">Where it stands</div><div class="ucd-std" data-ucp-std="${K}"></div></div>
        <div><div class="ucd-lab">Next steps · ${steps.length}</div><ul class="ucp-steps">${steps.map(x => `<li data-ucp-step-row="${x.id}"><span class="av" aria-hidden="true">${C.initials(x.owner)}</span><span class="ucp-sm">
            <span class="ucp-ce ucp-ow" contenteditable="plaintext-only" role="textbox" data-ucp-ce="${x.id}" data-f="owner" aria-label="Owner of ${x.id}">${esc(x.owner || 'No owner')}</span>: <span class="ucp-ce" contenteditable="plaintext-only" role="textbox" data-ucp-ce="${x.id}" data-f="title" aria-label="Next step ${x.id}">${esc(x.title)}</span>
            <span class="ucp-sx"><button class="link" data-ucp-open="${x.id}" aria-label="${x.id}: open it">${x.id}</button><span class="dot" aria-hidden="true">·</span><button class="cell-btn ucp-due${x.due && D.days(x.due) < 0 ? ' late' : ''}" data-ucp-due="${x.id}" aria-label="${x.due ? 'due ' + D.fd(x.due) : 'No due date'}: the due date of ${x.id}. Change it">${x.due ? 'due ' + D.fd(x.due) : 'No due date'}</button></span></span></li>`).join('')}
          <li class="addli"><input class="add-in" data-ucp-add="${K}" placeholder="+ Add a next step: “Owner: what it is”, then Enter" aria-label="Add a next step to use case ${R}"></li>
          <li class="addli"><button class="link" data-ucp-link="${K}">+ Link an existing work item</button></li></ul></div></div>
      <div class="ucd-cols"><div><div class="ucd-lab">Linked milestones · ${ms.length}</div>${ms.length ? `<ul class="ucp-ms">${ms.map(m => { const st = D.msState(m); return `<li><button class="link" data-ucp-ms="${esc(m.id)}">${esc(m.name)}</button><span class="mst ${C.msCls(st)}">${C.msMark(st)}${esc(st)}</span><span class="muted">${D.fd(m.achievedOn || m.agreed)}</span></li>`; }).join('')}</ul>` : '<p class="muted ucp-none">No milestones: none of its next steps is linked to one.</p>'}</div>
        <div><div class="ucd-lab">History</div>${histHtml(u)}</div></div>
      <div class="ucd-acts"><button class="link" data-ucp-work="${esc(u.id)}">See all ${n} work item${n === 1 ? '' : 's'} for use case ${R} ›</button></div></div>`;
  }
  const emptyHtml = f => all().length ? `<div class="empty"><p>No use cases match ${f.q.trim() ? `“${esc(f.q.trim())}”${f.g.length || f.st.length || f.on !== 'all' ? ' with these filters' : ''}` : 'these filters'}.</p><button class="btn" data-ucp-clear>Clear the filters</button></div>`
    : '<div class="empty"><p>No use cases yet. They come from the project record, or from an Excel import with a Use cases sheet.</p></div>';
  function listHtml() {
    const f = F(), us = list(), n = all().length;
    return `${narrowed(f) ? `<div class="factive ucp-count"><span>Showing ${us.length} of ${n} use case${n === 1 ? '' : 's'}</span>${us.length ? '<button class="link" data-ucp-clear>Clear all</button>' : ''}</div>` : ''}
      ${us.length ? `<div class="ucp-list" role="list"><div class="ucp-row ucp-hd" aria-hidden="true"><span>Use case</span><span>Name</span><span>Where it stands</span><span>Status</span><span>Work items</span><span class="ucp-hd-eye">Shown</span><span></span></div>${us.map(u => `<div role="listitem" class="ucp-li">${rowHtml(u)}</div>`).join('')}</div>` : emptyHtml(f)}`;
  }
  function barHtml() {
    const f = F(), us = all(), n = { all: us.length, on: us.filter(u => u.client).length, off: us.filter(u => !u.client).length };
    return `<div class="wbar ucp-bar">
      <button class="btn ucp-pill${f.g.length ? ' on' : ''}" id="ucpG" aria-haspopup="dialog" aria-expanded="false">${esc(pillLab('Group', f.g, g => g === 'Other' ? 'Other' : g))} ${C.icon('chev', 's')}</button>
      <button class="btn ucp-pill${f.st.length ? ' on' : ''}" id="ucpS" aria-haspopup="dialog" aria-expanded="false">${esc(pillLab('Status', f.st))} ${C.icon('chev', 's')}</button>
      <div class="seg" role="group" aria-label="On the dashboard or not">${[['all', 'All'], ['on', 'On the dashboard'], ['off', 'Not on the dashboard']].map(([v, t]) => `<button data-ucp-on="${v}" aria-pressed="${f.on === v}">${t} <em>${n[v]}</em></button>`).join('')}</div>
      <button class="btn ucp-pill" id="ucpSort" aria-haspopup="menu">Sort: ${esc((SORTS[f.sort] || SORTS.num).t)} ${C.icon('chev', 's')}</button>
      <span class="sp"></span><label class="search"><span class="sr">Search</span>${C.icon('search')}<input id="ucpQ" type="search" placeholder="Search use cases" value="${esc(f.q)}"></label></div>`;
  }
  C.views.usecases = {
    html() {
      const p = P();
      return `<div class="crumbs">${esc(p.name)}</div><div class="head"><div><h1>Use Cases</h1><p>Every use case of this project. The eye puts one on the dashboard and on the published page; select a row to open its detail.</p></div>
        <div class="hacts">${C.ioBtn('ucpExp', 'dl', 'Export to Excel')}</div></div>
        <div id="ucpBar">${barHtml()}</div>
        <div class="card ucp-card">${stripHtml(all())}<div id="ucpList">${listHtml()}</div><p class="note ucp-note">New use cases come from the project record, or from an Excel import with a Use cases sheet.</p></div>`;
    },
    wire() { wireBar(); wireList(); },
  };
  /* a filter, a sort or a search: the list, the strip and the pill words redraw; the bar's buttons stay, so an open drop-down stays open */
  function rer() { C.$('#ucpList').innerHTML = listHtml(); const c = C.$('.ucp-card .ucp-strip'); if (c) c.outerHTML = stripHtml(all()); sync(); wireList(); }
  function sync() {
    const f = F(), us = all(), n = { all: us.length, on: us.filter(u => u.client).length, off: us.filter(u => !u.client).length };
    const g = C.$('#ucpG'), s = C.$('#ucpS'), so = C.$('#ucpSort');
    if (g) { g.firstChild.textContent = pillLab('Group', f.g) + ' '; g.classList.toggle('on', !!f.g.length); }
    if (s) { s.firstChild.textContent = pillLab('Status', f.st) + ' '; s.classList.toggle('on', !!f.st.length); }
    if (so) so.firstChild.textContent = `Sort: ${(SORTS[f.sort] || SORTS.num).t} `;
    C.$$('[data-ucp-on]').forEach(b => { b.setAttribute('aria-pressed', f.on === b.dataset.ucpOn); C.$('em', b).textContent = n[b.dataset.ucpOn]; });
    const q = C.$('#ucpQ'); if (q && q.value !== f.q) q.value = f.q;
  }
  /* a pill's drop-down: tick any number; each tick narrows the list at once */
  function pickPop(anchor, key, opts, lab) {
    const vs = new Set(F()[key]);
    C.popover(anchor, `<div class="fpop ucp-pop" role="group" aria-label="${esc(anchor.textContent.trim())}">${opts.map(v => `<label><input type="checkbox" value="${esc(v)}" ${vs.has(v) ? 'checked' : ''}><span>${lab(v)}</span></label>`).join('')}
      <div class="fact ucp-pop-f"><button class="btn sm" data-ucp-none>Clear</button></div></div>`, { cls: 'fpopw', wire: el => {
      const put = () => { setF({ [key]: [...vs] }); rer(); };
      C.$$('input', el).forEach(c => c.addEventListener('change', () => { c.checked ? vs.add(c.value) : vs.delete(c.value); put(); }));
      C.$('[data-ucp-none]', el).addEventListener('click', () => { vs.clear(); C.$$('input', el).forEach(c => { c.checked = false; }); put(); });
      C.$('input', el)?.focus();
    } });
  }
  function wireBar() {
    C.$('#ucpExp').addEventListener('click', () => C.exportExcel({ only: 'usecases' }));
    C.$('#ucpG').addEventListener('click', e => { e.stopPropagation(); pickPop(e.currentTarget, 'g', groups(), g => esc(groupLab(g))); });
    C.$('#ucpS').addEventListener('click', e => { e.stopPropagation(); pickPop(e.currentTarget, 'st', STATUSES, s => word(s)); });
    C.$('#ucpSort').addEventListener('click', e => { e.stopPropagation(); C.menu(e.currentTarget, Object.entries(SORTS).map(([k, s]) => ({ label: s.t, selected: F().sort === k, onPick: () => { setF({ sort: k }); rer(); } })), { select: true }); });
    C.$$('[data-ucp-on]').forEach(b => b.addEventListener('click', () => { setF({ on: b.dataset.ucpOn }); rer(); }));
    const q = C.$('#ucpQ'); q.addEventListener('input', () => { setF({ q: q.value }); rer(); });
  }
  const find = k => D.S.usecases.find(u => u.key === k);
  const say = (u, msg, undo) => { C.refresh(); C.toast(`Use case ${refOf(u)} ${msg}`, undo); };
  function toggle(k) {
    const now = opened() === k ? '' : k; C.store.set('ucPageOpen', now);
    C.$$('.ucp-row[data-ucp]').forEach(r => { const on = r.dataset.ucp === now; r.classList.toggle('open', on); const b = C.$('[data-ucp-tog]', r); b.setAttribute('aria-expanded', on); b.setAttribute('aria-label', `${on ? 'Close' : 'Open'} the detail of use case ${refOf(find(r.dataset.ucp))}`); });
    C.$$('.ucp-d').forEach(d => { const on = d.dataset.ucpd === now; d.classList.toggle('open', on); d.innerHTML = on ? detailHtml(find(now)) : ''; });
    wireDetail();
  }
  function wireList() {
    C.$$('[data-ucp-clear]').forEach(b => b.addEventListener('click', () => { setF({ g: [], st: [], on: 'all', q: '' }); rer(); }));
    C.$$('.ucp-row[data-ucp]').forEach(r => {
      r.addEventListener('click', e => { if (e.target.closest('button, a, input, [contenteditable]') || String(getSelection()).trim()) return; toggle(r.dataset.ucp); });
      C.$('[data-ucp-tog]', r).addEventListener('click', e => { e.stopPropagation(); toggle(r.dataset.ucp); });
    });
    C.$$('[data-ucp-status]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); const u = find(b.dataset.ucpStatus);
      C.menu(e.currentTarget, STATUSES.map(s => ({ html: word(s), selected: u.status === s, onPick: () => { const un = D.change('uc', u, { status: s }, D.who(HOW)); if (un) say(u, `set to ${s}`, un); } })), { select: true }); }));
    /* the eye: the same switch as the dashboard's; the row stays here (muted when off), one step with Undo */
    C.$$('[data-ucp-eye]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); const u = find(b.dataset.ucpEye), on = !u.client;
      const un = D.change('uc', u, { client: on }, D.who('with the eye')); say(u, on ? 'is on the dashboard' : 'is no longer on the dashboard', un); }));
    wireDetail();
  }
  function wireDetail() {
    const k = opened(), u = k && find(k), host = k && C.$(`.ucp-d.open[data-ucpd="${CSS.escape(k)}"]`); if (!u || !host) return;
    const ce = (el, get, put) => { const old = get();
      el.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); el.blur(); } if (e.key === 'Escape') { e.stopPropagation(); el.textContent = old; el.blur(); } });
      el.addEventListener('blur', () => { const v = el.textContent.trim(); if (v === old || (!v && el.dataset.f !== 'owner' && !el.dataset.ucpHead)) { el.textContent = old; return; } put(v); }); };
    C.$$('[data-ucp-name]', host).forEach(el => ce(el, () => titles(u)[0], v => { const un = D.change('uc', u, { title: [v, ...titles(u).slice(1)].join('\n') }, D.who(HOW)); if (un) say(u, 'saved', un); }));
    C.$$('[data-ucp-head]', host).forEach(el => ce(el, () => u.headline || '', v => { const un = D.change('uc', u, { headline: v }, D.who(HOW)); if (un) say(u, 'saved', un); }));
    C.$$('[data-ucp-std]', host).forEach(el => C.inline(el, { html: u.standing, label: 'Where it stands', placeholder: 'Where the use case stands', place: 'current', draft: () => C.draftUc(u),
      onSave: h => { const un = D.change('uc', u, { standing: h }, D.who(HOW)); if (un) say(u, 'saved', un); } }));
    C.$$('[data-ucp-ce]', host).forEach(el => { const x = D.S.items.find(i => i.id === el.dataset.ucpCe), f = el.dataset.f;
      ce(el, () => f === 'owner' ? x.owner || 'No owner' : x[f] || '', v => { if (f === 'owner' && v === 'No owner') return; const un = D.change('item', x, { [f]: v }, D.who(HOW)); if (un) { C.refresh(); C.toast(`${x.id} saved`, un); } }); });
    C.$$('[data-ucp-due]', host).forEach(b => b.addEventListener('click', e => { e.stopPropagation(); const x = D.S.items.find(i => i.id === b.dataset.ucpDue);
      C.calPick(b, x.due, v => { if (!v || v === x.due) return; const un = D.change('item', x, { due: v }, D.who(HOW)); if (un) { C.refresh(); C.toast(`${x.id} due ${D.fd(v)}`, un); } }, { quick: [['Today', D.TODAY], ['Friday', D.friday()], ['In a week', D.addDays(D.TODAY, 7)]] }); }));
    C.$$('[data-ucp-open]', host).forEach(b => b.addEventListener('click', e => { e.stopPropagation(); C.openItem(b.dataset.ucpOpen, C.$$('[data-ucp-open]', host).map(x => x.dataset.ucpOpen)); }));
    C.$$('[data-ucp-ms]', host).forEach(b => b.addEventListener('click', e => { e.stopPropagation(); C.openMs(b.dataset.ucpMs); }));
    C.$$('[data-ucp-work]', host).forEach(b => b.addEventListener('click', () => C.workFilter({ uc: [b.dataset.ucpWork] })));
    C.$$('[data-ucp-hall]', host).forEach(b => b.addEventListener('click', () => { histAll = histAll === u.key ? '' : u.key; const d = C.$('.ucp-d.open'); d.innerHTML = detailHtml(u); wireDetail(); }));
    /* a next step, typed as "Owner: what it is": a new action linked to this use case, due in a week */
    C.$$('[data-ucp-add]', host).forEach(i => i.addEventListener('keydown', e => { if (e.key !== 'Enter' || !i.value.trim()) return; e.preventDefault();
      const p = P(), m = /^\s*([^:]{2,40}):\s*(.+)$/.exec(i.value), x = { id: C.nextId('A'), code: p.code, type: 'A', ws: p.ws[0], title: (m ? m[2] : i.value).trim(), owner: m ? m[1].trim() : '', due: D.addDays(D.TODAY, 7), status: 'Open', priority: 'Medium', desc: '', update: '', updatedAt: D.stamp(), client: true, clientText: '', ms: '', uc: u.id, source: 'Added from use case ' + refOf(u) };
      const un = D.create('item', x, D.who(HOW)); C.refresh(); C.toast(`${x.id} added to use case ${refOf(u)}`, un);
      setTimeout(() => { C.changed(C.$(`[data-ucp-step-row="${x.id}"]`)); C.$(`[data-ucp-add="${CSS.escape(u.key)}"]`)?.focus(); }, 30); }));
    /* link a work item that already exists: only its use case changes */
    C.$$('[data-ucp-link]', host).forEach(b => b.addEventListener('click', () => {
      const other = id => { const o = D.S.usecases.find(z => z.code === u.code && z.id === id); return o ? ` · now in use case ${refOf(o)}` : ''; };
      C.picker({ title: `Link work items to use case ${refOf(u)}`, sub: 'Open work items not linked to this use case yet',
        items: C.items().filter(x => x.uc !== u.id && C.isOpen(x)).map(x => ({ id: x.id, title: x.title, type: x.type, meta: `${x.id} · ${x.owner || 'No owner'}${x.due ? ' · ' + D.fd(x.due) : ''}${other(x.uc)}`, badge: C.pill(C.look(x)), search: [x.id, x.title, x.owner, x.ws, x.uc].join(' ') })),
        types: [['A', 'Actions'], ['R', 'Risks'], ['I', 'Issues'], ['D', 'Decisions']],
        onAdd: ids => { const un = D.batch(ids.map(id => () => D.change('item', D.S.items.find(x => x.id === id), { uc: u.id }, D.who(HOW)))); C.refresh(); C.toast(`${ids.length} work item${ids.length > 1 ? 's' : ''} linked to use case ${refOf(u)}`, un); } }); }));
  }

  /* ── the dashboard's line under its use case summary (the editor only; the published page never mentions what is off) ── */
  C.ucMoreHtml = p => { const us = D.S.usecases.filter(u => u.code === p.code), off = us.filter(u => !u.client).length; if (!us.length) return '';
    return `<p class="uc-more">${off ? `${off} more use case${off === 1 ? ' is' : 's are'} not on the dashboard. ` : ''}<button class="link" data-uc-page>See all ${us.length} on the Use Cases page ›</button></p>`; };

  /* ── the published page's Use Cases tab: view only, the use cases that are on the dashboard and nothing else. Where it stands, the
     next steps shown to the client and the milestones shown to the client; no history, no eye, no editing. ── */
  C.ucPubHtml = p => {
    const us = D.S.usecases.filter(u => u.code === p.code && u.client).sort(byNum);
    if (!us.length) return '<p class="muted">No use cases to show.</p>';
    const n = s => us.filter(u => u.status === s).length, order = STATUSES.filter(s => n(s));
    const strip = `<div class="uc-strip ucp-strip"><span class="uc-total"><b>${us.length}</b> use case${us.length === 1 ? '' : 's'}</span>${order.map(s => `<span class="uc-count">${word(s)}<b>${n(s)}</b></span>`).join('')}<span class="uc-meter" aria-hidden="true">${order.map(s => `<i class="${{ 'On track': 'g', Flag: 'a', 'High risk': 'r' }[s]}" style="flex:${n(s)}"></i>`).join('')}</span></div>`;
    return `${strip}<div class="ucp-list ucp-pub">${us.map((u, i) => {
      const xs = D.S.items.filter(x => x.code === p.code && x.uc === u.id && !x.archived), steps = xs.filter(x => x.client && isStep(x)).sort((a, b) => (a.due || '9').localeCompare(b.due || '9')), ms = msOf(steps).filter(m => m.client);
      /* the row is a real button with only words in it; the links to the next steps and milestones are in the detail below it */
      return `<button type="button" class="ucp-row" data-ucp-pub aria-expanded="false" aria-controls="ucpp-${i}"><span class="ucp-ref"><span class="uc-tag">${tagOf(u)}</span></span><span class="ucp-name">${esc(nameOf(u))}</span><span class="ucp-head">${esc(u.headline)}</span><span class="ucp-st">${word(u.status)}</span><span class="ucp-car" aria-hidden="true">${C.icon('chev', 's chev')}</span></button>
        <div class="ucp-d" id="ucpp-${i}"><div class="ucp-in"><div class="ucd-cols"><div><div class="ucd-lab">Where it stands</div><div class="prose">${u.standing || '<p class="muted">Not written yet.</p>'}</div></div>
          <div><div class="ucd-lab">Next steps · ${steps.length}</div>${steps.length ? `<ul class="ucp-steps">${steps.map(x => `<li><span class="av" aria-hidden="true">${C.initials(x.owner)}</span><span class="ucp-sm"><b>${esc(x.owner || 'No owner')}:</b> ${esc(x.clientText ? C.plain(x.clientText) : x.title)} <span class="ucp-sx"><a href="#" data-item="${x.id}">${x.id}</a>${x.due ? ` · due ${D.fd(x.due)}` : ''}</span></span></li>`).join('')}</ul>` : '<p class="muted">No next steps to show.</p>'}</div></div>
          ${ms.length ? `<div class="ucd-lab">Milestones · ${ms.length}</div><ul class="ucp-ms">${ms.map(m => { const st = D.msState(m); return `<li><a href="#" data-ms="${esc(m.id)}">${esc(m.clientText || m.name)}</a><span class="mst ${C.msCls(st)}">${C.msMark(st)}${esc(D.msWord(st, true))}</span><span class="muted">${D.fd(m.achievedOn || m.agreed)}</span></li>`; }).join('')}</ul>` : ''}</div></div>`; }).join('')}</div>`;
  };
  /* the published page's own script for the tab: a row (a button, so Enter and Space work too) opens its detail in place (one at a time) */
  C.UCP_JS = `document.querySelectorAll('[data-ucp-pub]').forEach(r=>{const t=()=>{const on=!r.classList.contains('open');document.querySelectorAll('[data-ucp-pub].open').forEach(x=>{x.classList.remove('open');x.setAttribute('aria-expanded','false');x.nextElementSibling.classList.remove('open')});if(on){r.classList.add('open');r.setAttribute('aria-expanded','true');r.nextElementSibling.classList.add('open')}};r.addEventListener('click',t)});`;
})();
