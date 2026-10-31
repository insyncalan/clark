/* clark prototype: the Use cases page (the planning repo #157, the chosen mockup). Every use case of the project, on the dashboard or not,
   in the Milestones page's look: a list (reference, name, where it stands, status word, linked work items, linked milestones, the eye in
   words), and each use case on a page of its own with its own address (Back and Forward work): where it stands in the one editor, the work
   items (each opens beside the page), the milestones, the owner and the history. Archive and Restore, never Delete. The eye is the
   dashboard's own switch; the published page shows only the use cases that are on, and an archived one is on no page at all. */
(function () {
  'use strict';
  const C = window.C, D = C.D, esc = C.esc, UI = C.UI;
  const P = () => C.P();
  const STATUSES = ['On track', 'Flag', 'High risk'], WORST = ['High risk', 'Flag', 'On track'];   /* the schema's three */
  const HOW = 'on the Use cases page';
  const word = s => C.ucWord(s);
  const refOf = u => u.ref || u.id, titles = u => String(u.title || '').split('\n'), nameOf = u => titles(u).join(' · ');
  const tagOf = u => refOf(u).split(/,| and /).map(x => x.trim()).filter(Boolean).map(esc).join(' + ');
  const refLab = u => 'UC ' + refOf(u);
  const plural = (n, one, many) => n + ' ' + (n === 1 ? one : many || one + 's');

  /* the group of a use case: the number before the first dot of its reference (1.3 is in Group 1); one with no number is in Other */
  const groupOf = u => { const m = /^\s*(\d+)/.exec(String(u.id || '')); return m ? 'Group ' + (+m[1]) : 'Other'; };
  const numKey = u => String(u.id || '').split('.').map(n => { const v = parseInt(n, 10); return isNaN(v) ? 1e9 : v; });
  const byNum = (a, b) => { const x = numKey(a), y = numKey(b); for (let i = 0; i < Math.max(x.length, y.length); i++) { const d = (x[i] ?? -1) - (y[i] ?? -1); if (d) return d; } return String(a.id).localeCompare(String(b.id)); };

  const live = () => C.ucs();
  const itemsOf = u => C.items().filter(x => x.uc === u.id);
  const openOf = u => itemsOf(u).filter(C.isOpen);
  /* its linked milestones: the live milestones its work items point at, in date order */
  const msLinked = u => { const ids = new Set(itemsOf(u).map(x => x.ms).filter(Boolean)); return C.mss().filter(m => ids.has(m.id)); };
  /* its next steps, as the published page counts them: its open actions only (a risk, issue or decision is a work item, not a next step) */
  const isStep = x => x.type === 'A' && C.isOpen(x);
  const stepsOf = u => itemsOf(u).filter(isStep);
  /* the published page's linked milestones: only those its open next steps point at, in date order */
  const msOf = steps => { const ids = new Set(steps.map(x => x.ms).filter(Boolean)); return C.mss().filter(m => ids.has(m.id)); };

  const SORTS = {
    num: { t: 'Reference', f: byNum },
    status: { t: 'Status', f: (a, b) => WORST.indexOf(a.status) - WORST.indexOf(b.status) || byNum(a, b) },
    open: { t: 'Open work items', f: (a, b) => openOf(b).length - openOf(a).length || byNum(a, b) },
  };
  /* the filters and the sort, remembered per project */
  const F0 = { st: [], on: 'all', sort: 'num', q: '', arch: false };
  const fOf = code => Object.assign({}, F0, (C.store.get('ucPage', {}) || {})[code] || {});
  const F = () => fOf(P().code);
  const setF = o => { const s = C.store.get('ucPage', {}) || {}; s[P().code] = { ...F(), ...o }; C.store.set('ucPage', s); };
  C.ucPageFilter = fOf;
  const narrowed = f => f.st.length || f.on !== 'all' || f.q.trim();
  function list() {
    const f = F(), q = f.q.trim().toLowerCase();
    return live().filter(u => (!f.st.length || f.st.includes(u.status)) && (f.on === 'all' || (f.on === 'on') === !!u.client)
      && (!q || [u.id, u.ref, 'UC ' + refOf(u), u.title, u.headline, C.plain(u.standing), u.owner].join(' ').toLowerCase().includes(q))).sort((SORTS[f.sort] || SORTS.num).f);
  }
  const find = k => D.S.usecases.find(u => u.key === k);
  const say = (u, msg, undo) => { C.refresh(); C.toast(`Use case ${refOf(u)} ${msg}`, undo); };
  const EYE_ON = 'On the dashboard', EYE_OFF = 'Not on the dashboard';
  let lastKey = '';   /* the use case just left by Back or the crumb: its row takes the focus when the list comes back */

  /* ── the list ── */
  function msWords(u) { const ms = msLinked(u); return ms.length ? ms.map(m => esc(m.name)).join('; ') : '<span class="muted">None</span>'; }
  function rowHtml(u) {
    const K = esc(u.key), on = !!u.client, n = itemsOf(u).length, o = openOf(u).length;
    return `<div class="ucx-row${on ? '' : ' off'}" role="listitem" data-ucx="${K}">
      <span class="ucx-ref" title="${esc(refLab(u))}">${esc(refLab(u))}</span>
      <span class="ucx-name"><button class="ucx-go" data-ucx-go="${K}" title="Open ${esc(nameOf(u))}">${esc(nameOf(u))}</button><small>${esc(u.headline || 'No headline yet')}</small></span>
      <span class="ucx-head" title="${esc(u.headline)}">${esc(u.headline || 'No headline yet')}</span>
      <span class="ucx-st">${word(u.status)}</span>
      <span class="ucx-wi">${n ? `<b>${n}</b> linked<small>${o} open</small>` : 'None linked'}</span>
      <span class="ucx-ms">${msWords(u)}</span>
      <button class="ucx-eye" data-ucx-eye="${K}" aria-pressed="${on}" title="${on ? 'Shown on the dashboard and the published page. Select to take it off' : 'Not shown. Select to put it on the dashboard'}">${C.icon(on ? 'eye' : 'eyeoff', 's')}<span class="w">${on ? EYE_ON : EYE_OFF}</span></button>
    </div>`;
  }
  function archBoxHtml() {
    const f = F(), gone = C.ucAll().filter(u => u.archived).sort(byNum);
    if (!f.arch || !gone.length) return '';
    return `<div class="card arch-box" id="ucxArch"><h2 class="arch-h">Archived <span>${plural(gone.length, 'use case')}</span></h2><ul class="arch-l">${gone.map(u => `<li class="arch"><button class="link" data-ucx-go="${esc(u.key)}">${esc(refLab(u))} · ${esc(nameOf(u))}</button><span class="tag arch">${C.icon('archive', 's')}Archived</span><span>${plural(itemsOf(u).length, 'work item')} still linked</span><button class="btn sm" data-ucx-restore="${esc(u.key)}">Restore</button></li>`).join('')}</ul></div>`;
  }
  function footHtml() {
    const f = F(), n = C.ucAll().filter(u => u.archived).length;
    if (!n) return '';
    return `<p class="ucx-foot">${f.arch ? `Showing ${plural(n, 'archived use case')}.` : `${plural(n, 'archived use case')} ${n === 1 ? 'is' : 'are'} hidden.`} <button class="link" data-ucx-arch>${f.arch ? 'Hide archived' : 'Show archived'}</button></p>`;
  }
  const emptyHtml = f => live().length ? `<div class="empty"><p>No use cases match ${f.q.trim() ? `“${esc(f.q.trim())}”${f.st.length || f.on !== 'all' ? ' with these filters' : ''}` : 'these filters'}.</p><button class="btn" data-ucx-clear>Clear the filters</button></div>`
    : '<div class="empty"><p>No use cases yet. Add one, or import them from an Excel file with a Use cases sheet.</p></div>';
  function listHtml() {
    const us = list(), f = F();
    return `${us.length ? `<div class="ucx-list" role="list"><div class="ucx-row ucx-hd" aria-hidden="true"><span>Ref</span><span>Use case</span><span class="ucx-head">Where it stands</span><span>Status</span><span>Work items</span><span class="ucx-ms">Milestones</span><span>Home dashboard</span></div>${us.map(rowHtml).join('')}</div>` : emptyHtml(f)}${footHtml()}${archBoxHtml()}`;
  }
  const pillLab = (t, vs) => vs.length ? `${t}: ${vs.join(', ')}` : t;
  const countWords = () => { const us = live(), n = list().length; return `Showing ${n} of ${us.length} · ${us.filter(u => u.client).length} on the dashboard`; };
  function barHtml() {
    const f = F(), us = live(), n = { all: us.length, on: us.filter(u => u.client).length, off: us.filter(u => !u.client).length };
    return `<div class="wbar ucx-bar"><label class="search"><span class="sr">Search</span>${C.icon('search')}<input id="ucxQ" type="search" placeholder="Search use cases" value="${esc(f.q)}" autocomplete="off"></label>
      <button class="btn ucx-pill${f.st.length ? ' on' : ''}" id="ucxS" aria-haspopup="dialog" aria-expanded="false">${esc(pillLab('Status', f.st))} ${C.icon('chev', 's')}</button>
      <div class="seg" role="group" aria-label="On the dashboard or not">${[['all', 'All'], ['on', EYE_ON], ['off', EYE_OFF]].map(([v, t]) => `<button data-ucx-on="${v}" aria-pressed="${f.on === v}">${t} <em>${n[v]}</em></button>`).join('')}</div>
      <button class="btn ucx-pill" id="ucxSort" aria-haspopup="menu">Sort: ${esc((SORTS[f.sort] || SORTS.num).t)} ${C.icon('chev', 's')}</button>
      <span class="sp"></span><span class="ucx-count" id="ucxCount" role="status">${countWords()}</span></div>`;
  }
  function listPage() {
    const p = P();
    return `<div class="crumbs">${esc(p.name)}</div><div class="head"><div><h1>Use cases</h1><p>Every use case of this project. The home dashboard shows the ones marked On the dashboard.</p></div>
      <div class="hacts"><button class="btn" id="ucxExp">${C.icon('dl', 's')} Export to Excel</button>${C.addBtn('id="ucxAdd"', 'Add a use case')}</div></div>
      <div id="ucxBar">${barHtml()}</div><div id="ucxList">${listHtml()}</div>`;
  }

  /* ── one use case, on its own page ── */
  const HIST_N = 8; let histAll = '';
  function histHtml(u) {
    const rows = D.historyOf('uc', u.id).filter(h => h.code === u.code);
    if (!rows.length) return '<p class="muted ucx-none">No changes recorded yet.</p>';
    const q = v => esc(String(v).split('\n')[0]);
    const line = h => { const w = D.whoHow(h), life = { '+': 1, '-': 1, '*': 1 }[h.field], t = h.text || '';
      const what = life ? ({ Created: 'added the use case', Archived: 'archived it', Restored: 'restored it' }[t] || esc(t || 'changed it'))
        : h.field === 'client' ? (h.to ? 'put it on the dashboard' : 'took it off the dashboard')
        : D.RICH.includes(h.field) ? `edited ${esc(D.fieldName(h.field, 'uc').toLowerCase())}`
        : (() => { const a = D.showVal(h.field, h.from), b = D.showVal(h.field, h.to), nm = esc(D.fieldName(h.field, 'uc').toLowerCase()); return a === null ? `changed the ${nm}` : `changed the ${nm} from <b>${q(a)}</b> to <b>${q(b)}</b>`; })();
      return `<li><span class="ucx-hw">${w.who ? `<b>${esc(w.who)}</b> ` : ''}${what}</span><time class="ucx-hm">${esc([w.how, D.when(h)].filter(Boolean).join(' · '))}</time></li>`; };
    const shown = histAll === u.key ? rows : rows.slice(0, HIST_N);
    return `<ul class="ucx-hist">${shown.map(line).join('')}</ul>${rows.length > HIST_N ? `<button class="link" data-ucx-hall>${histAll === u.key ? 'Show the latest only' : `Show all ${rows.length} changes`}</button>` : ''}`;
  }
  const itemExtra = x => x.type === 'A' ? (x.due ? 'Due ' + D.fd(x.due) : 'No due date') : esc(x.priority || '');
  function itemsHtml(u, ro) {
    const xs = itemsOf(u).sort((a, b) => (C.isOpen(b) ? 1 : 0) - (C.isOpen(a) ? 1 : 0) || (a.due || '9').localeCompare(b.due || '9') || a.id.localeCompare(b.id)), K = esc(u.key);
    return `${xs.length ? xs.map(x => `<button class="ucx-li" data-open="${esc(x.id)}" title="Open ${esc(x.id)} beside this page"><span class="id">${esc(x.id)}</span><span class="t">${esc(x.title)}</span>${C.pill(C.look(x))}<span class="own">${itemExtra(x)}</span></button>`).join('') : '<p class="muted ucx-none">No work items are linked to this use case yet.</p>'}
      ${ro ? '' : `<div class="ucx-addrow"><input class="add-in" data-ucx-add="${K}" placeholder="+ Add a next step: “Owner: what it is”, then Enter" aria-label="Add a next step to use case ${esc(refOf(u))}"><button class="link" data-ucx-link="${K}">+ Link an existing work item</button></div>`}`;
  }
  function detailPage(u) {
    const K = esc(u.key), R = esc(refLab(u)), RW = esc(refOf(u)), n = itemsOf(u).length, o = openOf(u).length, ms = msLinked(u), arch = !!u.archived, last = D.historyOf('uc', u.id).filter(h => h.code === u.code)[0];
    const on = !!u.client, sub = `${n ? `${o} of ${plural(n, 'work item')} open` : 'No work items'} · ${plural(ms.length, 'milestone')}`;
    const acts = arch ? '' : `<div class="hacts ucx-acts"><button class="btn" id="ucxStatus" aria-haspopup="menu">Change status ${C.icon('chev', 's')}</button>
        <span class="ucx-eye-s${on ? ' on' : ''}">${C.icon(on ? 'eye' : 'eyeoff', 's')}${on ? EYE_ON : EYE_OFF}</span><button class="btn" id="ucxToggle">${on ? 'Take off the dashboard' : 'Put on the dashboard'}</button></div>`;
    const nm = arch ? esc(titles(u)[0]) : `<span class="ucx-ce ucx-nm" contenteditable="plaintext-only" role="textbox" spellcheck="true" data-ucx-name aria-label="Name of use case ${RW}">${esc(titles(u)[0])}</span>`;
    const hl = arch ? `<p class="ucx-hl">${esc(u.headline || 'No headline yet')}</p>` : `<p class="ucx-hl"><span class="ucx-ce" contenteditable="plaintext-only" role="textbox" spellcheck="true" data-ucx-head data-ph="One line on where it stands" aria-label="One line on where use case ${RW} stands">${esc(u.headline)}</span></p>`;
    return `<div class="crumbs ucx-crumb"><button class="link" data-ucx-back>Use cases</button> › ${R}</div>
      <div class="head"><div><h1 tabindex="-1">${R} · ${nm}</h1><p class="ucx-sub">${arch ? `<span class="tag arch">${C.icon('archive', 's')}Archived</span>` : ''}${word(u.status)} <span>${sub}</span></p></div>${acts}</div>
      ${arch ? `<div class="pk-archnote ucx-archnote"><p>Archived, so it is read-only. It is out of the lists, the counts, the dashboard and the published page; nothing in it was deleted.</p><button class="btn pri" id="ucxRestore">Restore</button></div>` : ''}
      <div class="ucx-dgrid"><div class="ucx-main">
        <div class="card"><h3 class="ucx-h"><span>Where it stands</span><span class="sp"></span>${arch ? '' : '<span class="ucx-hint">Click the text to change it</span>'}</h3>${hl}<div class="ucx-std ucd-std" data-ucx-std>${arch ? `<div class="prose">${u.standing || '<p class="muted">Not written yet.</p>'}</div>` : ''}</div></div>
        <div class="card"><h3 class="ucx-h"><span>Work items</span><span class="sp"></span>${n ? `<button class="link" data-ucx-work>Open all ${n} in Work items</button>` : ''}</h3><div class="ucx-items">${itemsHtml(u, arch)}</div></div>
        ${arch ? '' : `<p class="ucx-archrow"><button class="link" data-ucx-archive>Archive this use case</button><span class="muted"> It can be restored; nothing is deleted.</span></p>`}
      </div><div class="ucx-side">
        <div class="card"><h3 class="ucx-h">Details</h3><dl class="ucx-kv"><dt>Owner</dt><dd>${arch ? esc(u.owner || 'No owner') : `<span class="ucx-ce" contenteditable="plaintext-only" role="textbox" data-ucx-owner data-ph="No owner" aria-label="Owner of use case ${RW}">${esc(u.owner || '')}</span>`}</dd>
          <dt>Group</dt><dd>${esc(groupOf(u))}</dd><dt>Dashboard</dt><dd>${arch ? 'Archived' : on ? EYE_ON : EYE_OFF}</dd><dt>Last change</dt><dd>${last ? D.fd(D.whenIso(last).slice(0, 10)) : 'No changes yet'}</dd></dl></div>
        <div class="card"><h3 class="ucx-h">Milestones</h3>${ms.length ? `<ul class="ucx-ms-l">${ms.map(m => { const st = D.msState(m); return `<li><button class="link" data-ucx-ms="${esc(m.id)}">${esc(m.name)}</button><span class="mst ${C.msCls(st)}">${C.msMark(st)}${esc(st)}</span><span class="muted">${D.fd(m.achievedOn || m.agreed)}</span></li>`; }).join('')}</ul>` : '<p class="muted ucx-none">No milestones: none of its work items is linked to one.</p>'}</div>
        <div class="card"><h3 class="ucx-h">History</h3>${histHtml(u)}</div>
      </div></div>`;
  }

  C.views.usecases = {
    html() {
      const u = UI.uc && C.ucAll().find(x => x.id === UI.uc);
      if (UI.uc && !u) { UI.uc = ''; C.ucFixed = true; }   /* a use case that is gone (another project, or undone): back to the list */
      if (u) lastKey = u.key;
      return u ? detailPage(u) : listPage();
    },
    wire() {
      if (C.ucFixed) { C.ucFixed = false; setTimeout(() => C.nav('replace'), 0); }   /* after a Back or Forward has finished, so the address is mended too */
      if (UI.uc) wireDetail(C.ucAll().find(x => x.id === UI.uc)); else { wireBar(); wireList(); if (lastKey) { C.$(`[data-ucx-go="${CSS.escape(lastKey)}"]`)?.focus({ preventScroll: true }); lastKey = ''; } }
    },
  };
  C.openUc = u => { C.go('usecases', { uc: typeof u === 'string' ? u : u.id }); C.$('.head h1')?.focus({ preventScroll: true }); };

  /* a filter, a sort or a search: the list, the count and the pill words redraw; the bar's buttons stay, so an open drop-down stays open */
  function rer() { C.$('#ucxList').innerHTML = listHtml(); sync(); wireList(); }
  function sync() {
    const f = F(), us = live(), n = { all: us.length, on: us.filter(u => u.client).length, off: us.filter(u => !u.client).length };
    const s = C.$('#ucxS'), so = C.$('#ucxSort');
    if (s) { s.firstChild.textContent = pillLab('Status', f.st) + ' '; s.classList.toggle('on', !!f.st.length); }
    if (so) so.firstChild.textContent = `Sort: ${(SORTS[f.sort] || SORTS.num).t} `;
    C.$$('[data-ucx-on]').forEach(b => { b.setAttribute('aria-pressed', f.on === b.dataset.ucxOn); C.$('em', b).textContent = n[b.dataset.ucxOn]; });
    const q = C.$('#ucxQ'); if (q && q.value !== f.q) q.value = f.q;
    const c = C.$('#ucxCount'); if (c) c.textContent = countWords();
  }
  /* the Status pill's drop-down: tick any number; each tick narrows the list at once */
  function pickPop(anchor, key, opts, lab) {
    const vs = new Set(F()[key]);
    C.popover(anchor, `<div class="fpop ucx-pop" role="group" aria-label="${esc(anchor.textContent.trim())}">${opts.map(v => `<label><input type="checkbox" value="${esc(v)}" ${vs.has(v) ? 'checked' : ''}><span>${lab(v)}</span></label>`).join('')}
      <div class="fact ucx-pop-f"><button class="btn sm" data-ucx-none>Clear</button></div></div>`, { cls: 'fpopw', wire: el => {
      const put = () => { setF({ [key]: [...vs] }); rer(); };
      C.$$('input', el).forEach(c => c.addEventListener('change', () => { c.checked ? vs.add(c.value) : vs.delete(c.value); put(); }));
      C.$('[data-ucx-none]', el).addEventListener('click', () => { vs.clear(); C.$$('input', el).forEach(c => { c.checked = false; }); put(); });
      C.$('input', el)?.focus();
    } });
  }
  function addForm() {
    C.dialog(`<form id="ucxF"><div class="dlg-h"><h2>Add a use case</h2></div><div class="dlg-b"><div class="form">
      <label for="ucxI">Reference</label><input class="field" id="ucxI" required placeholder="For example: 3.1">
      <label for="ucxT">Name</label><input class="field" id="ucxT" required placeholder="What it does">
      <label for="ucxSt">Status</label><select class="field" id="ucxSt">${STATUSES.map(s => `<option>${s}</option>`).join('')}</select>
      <label for="ucxD">Dashboard</label><label class="ucx-chk"><input type="checkbox" id="ucxD"> Put it on the dashboard</label></div></div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Cancel</button><button class="btn pri">Add</button></div></form>`, d => C.$('#ucxF', d).addEventListener('submit', e => {
      e.preventDefault(); const p = P(), id = C.$('#ucxI', d).value.trim();
      if (!id) return;
      if (D.S.usecases.some(u => u.code === p.code && u.id === id)) { const i = C.$('#ucxI', d); i.setCustomValidity('That reference is already used'); i.reportValidity(); i.setCustomValidity(''); return; }
      const u = { key: p.code + '/' + id, id, code: p.code, title: C.$('#ucxT', d).value.trim(), status: C.$('#ucxSt', d).value, headline: '', standing: '', client: C.$('#ucxD', d).checked };
      d.close(); const un = D.create('uc', u, D.who(HOW)); C.openUc(u); C.toast(`Use case ${id} added`, un);
    }));
    C.$('#ucxI')?.focus();
  }
  function wireBar() {
    C.$('#ucxExp').addEventListener('click', () => C.exportExcel({ only: 'usecases' }));
    C.$('#ucxAdd').addEventListener('click', addForm);
    C.$('#ucxS').addEventListener('click', e => { e.stopPropagation(); pickPop(e.currentTarget, 'st', STATUSES, s => word(s)); });
    C.$('#ucxSort').addEventListener('click', e => { e.stopPropagation(); C.menu(e.currentTarget, Object.entries(SORTS).map(([k, s]) => ({ label: s.t, selected: F().sort === k, onPick: () => { setF({ sort: k }); rer(); } })), { select: true }); });
    C.$$('[data-ucx-on]').forEach(b => b.addEventListener('click', () => { setF({ on: b.dataset.ucxOn }); rer(); }));
    const q = C.$('#ucxQ'); q.addEventListener('input', () => { setF({ q: q.value }); rer(); });
  }
  function wireList() {
    C.$$('[data-ucx-clear]').forEach(b => b.addEventListener('click', () => { setF({ st: [], on: 'all', q: '' }); rer(); }));
    C.$$('.ucx-row[data-ucx]').forEach(r => r.addEventListener('click', e => { if (e.target.closest('button, a, input') || String(getSelection()).trim()) return; C.openUc(find(r.dataset.ucx)); }));
    C.$$('[data-ucx-go]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); C.openUc(find(b.dataset.ucxGo)); }));
    /* the eye: the dashboard's own switch; the row stays here (muted when off), one step with Undo */
    C.$$('[data-ucx-eye]').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); const u = find(b.dataset.ucxEye), on = !u.client;
      const un = D.change('uc', u, { client: on }, D.who('with the eye')); if (un) say(u, on ? 'is on the dashboard' : 'is no longer on the dashboard', un); }));
    C.$$('[data-ucx-arch]').forEach(b => b.addEventListener('click', () => { setF({ arch: !F().arch }); rer(); C.$('[data-ucx-arch]')?.focus(); }));
    C.$$('[data-ucx-restore]').forEach(b => b.addEventListener('click', () => restore(find(b.dataset.ucxRestore))));
  }
  function restore(u) { const un = D.archive(u, false, D.who(HOW), 'uc'); if (un) say(u, 'restored. It is back in the lists and counts', un); }
  function wireDetail(u) {
    const host = C.$('#main');
    C.$('[data-ucx-back]').addEventListener('click', () => C.go('usecases'));
    if (u.archived) {
      C.$('#ucxRestore').addEventListener('click', () => restore(u));
    } else {
      const ce = (el, get, put, empty) => { const old = get();
        el.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); el.blur(); } if (e.key === 'Escape') { e.stopPropagation(); el.textContent = old; el.blur(); } });
        el.addEventListener('blur', () => { const v = el.textContent.trim(); if (v === old || (!v && !empty)) { el.textContent = old; return; } put(v); }); };
      ce(C.$('[data-ucx-name]', host), () => titles(u)[0], v => { const un = D.change('uc', u, { title: [v, ...titles(u).slice(1)].join('\n') }, D.who(HOW)); if (un) say(u, 'saved', un); });
      ce(C.$('[data-ucx-head]', host), () => u.headline || '', v => { const un = D.change('uc', u, { headline: v }, D.who(HOW)); if (un) say(u, 'saved', un); }, true);
      ce(C.$('[data-ucx-owner]', host), () => u.owner || '', v => { const un = D.change('uc', u, { owner: v }, D.who(HOW)); if (un) say(u, 'saved', un); }, true);
      C.inline(C.$('[data-ucx-std]', host), { html: u.standing, label: 'Where it stands', placeholder: 'Where the use case stands', place: 'current', draft: () => C.draftUc(u),
        onSave: h => { const un = D.change('uc', u, { standing: h }, D.who(HOW)); if (un) say(u, 'saved', un); } });
      C.$('#ucxStatus').addEventListener('click', e => { e.stopPropagation();
        C.menu(e.currentTarget, STATUSES.map(s => ({ html: word(s), selected: u.status === s, onPick: () => { const un = D.change('uc', u, { status: s }, D.who(HOW)); if (un) say(u, `set to ${s}`, un); } })), { select: true }); });
      C.$('#ucxToggle').addEventListener('click', () => { const on = !u.client, un = D.change('uc', u, { client: on }, D.who('with the eye')); if (un) say(u, on ? 'is on the dashboard' : 'is no longer on the dashboard', un); });
      C.$('[data-ucx-archive]').addEventListener('click', () => { const un = D.archive(u, true, D.who(HOW), 'uc'); if (un) say(u, 'archived. It is out of the lists, the dashboard and the published page; Show archived brings it back', un); });
      /* a next step, typed as "Owner: what it is": a new action linked to this use case, due in a week */
      C.$('[data-ucx-add]', host).addEventListener('keydown', e => { const i = e.currentTarget; if (e.key !== 'Enter' || !i.value.trim()) return; e.preventDefault();
        const p = P(), m = /^\s*([^:]{2,40}):\s*(.+)$/.exec(i.value), x = { id: C.nextId('A'), code: p.code, type: 'A', ws: p.ws[0], title: (m ? m[2] : i.value).trim(), owner: m ? m[1].trim() : '', due: D.addDays(D.TODAY, 7), status: 'Open', priority: 'Medium', desc: '', update: '', updatedAt: D.stamp(), client: true, clientText: '', ms: '', uc: u.id, source: 'Added from use case ' + refOf(u) };
        const un = D.create('item', x, D.who(HOW)); C.refresh(); C.toast(`${x.id} added to use case ${refOf(u)}`, un);
        setTimeout(() => { C.changed(C.$(`[data-open="${x.id}"]`)); C.$('[data-ucx-add]')?.focus(); }, 30); });
      /* link a work item that already exists: only its use case changes */
      C.$('[data-ucx-link]', host).addEventListener('click', () => {
        const other = id => { const o = D.S.usecases.find(z => z.code === u.code && z.id === id); return o ? ` · now in use case ${refOf(o)}` : ''; };
        C.picker({ title: `Link work items to use case ${refOf(u)}`, sub: 'Open work items not linked to this use case yet',
          items: C.items().filter(x => x.uc !== u.id && C.isOpen(x)).map(x => ({ id: x.id, title: x.title, type: x.type, meta: `${x.id} · ${x.owner || 'No owner'}${x.due ? ' · ' + D.fd(x.due) : ''}${other(x.uc)}`, badge: C.pill(C.look(x)), search: [x.id, x.title, x.owner, x.ws, x.uc].join(' ') })),
          types: [['A', 'Actions'], ['R', 'Risks'], ['I', 'Issues'], ['D', 'Decisions']],
          onAdd: ids => { const un = D.batch(ids.map(id => () => D.change('item', D.S.items.find(x => x.id === id), { uc: u.id }, D.who(HOW)))); C.refresh(); C.toast(`${plural(ids.length, 'work item')} linked to use case ${refOf(u)}`, un); } }); });
    }
    const ids = C.$$('[data-open]', host).map(x => x.dataset.open);
    C.$$('[data-open]', host).forEach(b => b.addEventListener('click', () => C.openItem(b.dataset.open, ids)));
    C.$$('[data-ucx-ms]', host).forEach(b => b.addEventListener('click', () => C.openMs(b.dataset.ucxMs, msLinked(u).map(m => m.id))));
    C.$('[data-ucx-work]', host)?.addEventListener('click', () => C.workFilter({ uc: [u.id] }));
    C.$('[data-ucx-hall]', host)?.addEventListener('click', () => { histAll = histAll === u.key ? '' : u.key; C.refresh(); });
  }

  /* ── the dashboard's line under its use case summary (the editor only; the published page never mentions what is off) ── */
  C.ucMoreHtml = p => { const us = D.S.usecases.filter(u => u.code === p.code && !u.archived), off = us.filter(u => !u.client).length; if (!us.length) return '';
    return `<p class="uc-more"><button class="link" data-uc-page>${off ? `${off} more on the Use cases page ›` : `See all ${us.length} on the Use cases page ›`}</button></p>`; };

  /* ── the published page's Use Cases tab: view only, the use cases that are on the dashboard and nothing else. Where it stands, the
     next steps shown to the client and the milestones shown to the client; no history, no eye, no editing. ── */
  C.ucPubHtml = p => {
    const us = D.S.usecases.filter(u => u.code === p.code && u.client && !u.archived).sort(byNum);
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
