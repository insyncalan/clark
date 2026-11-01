/* clark prototype: the peek (creaite's work-item panel and milestone editor) and Sneak peek (change it in words).
   The peek opens over the page from the right, at the width the user last chose (drag its left edge; the expand button takes it
   across the whole screen). Every change saves at once through ClarkDB.change, with history and Undo. */
(function () {
  'use strict';
  const C = window.C, D = C.D, UI = C.UI, esc = C.esc;
  const pk = () => C.$('#peek');
  let cur = null;   // {kind: 'item'|'ms', id, list: [ids]}
  let tab = 'all';

  /* ── width: the user's preference, kept ── */
  const applyWidth = () => { const w = C.store.get('peekW', 0), p = pk(); p.style.setProperty('--peek-w', w ? Math.min(w, innerWidth) + 'px' : '50vw'); p.classList.toggle('wide', !!C.store.get('peekWide', false)); };
  function wireResize() {
    const h = C.$('.resize', pk()); if (!h) return;
    h.addEventListener('pointerdown', e => {
      e.preventDefault(); h.classList.add('drag'); h.setPointerCapture(e.pointerId); C.store.set('peekWide', false); pk().classList.remove('wide');
      const move = ev => { const w = Math.max(420, Math.min(innerWidth, innerWidth - ev.clientX)); pk().style.setProperty('--peek-w', w + 'px'); };
      const up = ev => { h.classList.remove('drag'); h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); C.store.set('peekW', Math.round(innerWidth - ev.clientX)); syncWideBtn(); };
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', up);
    });
    h.addEventListener('dblclick', () => { C.store.set('peekW', 0); C.store.set('peekWide', false); applyWidth(); syncWideBtn(); });
  }
  const syncWideBtn = () => { const b = C.$('#pkWide'); if (!b) return; const w = pk().classList.contains('wide'); b.innerHTML = C.icon(w ? 'collapse' : 'expand'); b.setAttribute('aria-label', w ? 'Back to your width' : 'Across the whole screen'); b.setAttribute('aria-pressed', w); };
  const toggleWide = () => { const w = !pk().classList.contains('wide'); C.store.set('peekWide', w); applyWidth(); syncWideBtn(); };

  /* focus: opening moves it into the peek; closing (Esc, the close button, a click away) gives it back to the row or card that
     opened it, if that is still on the page (the design review, #87). The opener is the focused element, or else what was just clicked. */
  let opener = null, lastDown = { t: 0, el: null };
  const KEYED = ['data-id', 'data-card', 'data-ms', 'data-msel', 'data-item', 'data-open', 'data-row'], KEYSEL = KEYED.map(k => `[${k}]`).join(',');
  const grabOpener = () => { let el = document.activeElement; if (!el || el === document.body || el.closest('#peek, .menu, dialog')) el = Date.now() - lastDown.t < 1500 ? lastDown.el : null;
    if (!el || !el.isConnected || el.closest('#peek, .menu, dialog')) return null;
    const k = el.closest(KEYSEL), at = k && KEYED.find(n => k.hasAttribute(n)); return { el, sel: at ? `${k.tagName.toLowerCase()}[${at}="${CSS.escape(k.getAttribute(at))}"]` : '' }; };
  document.addEventListener('keydown', () => { lastDown.t = 0; }, true);   /* a key press: the opener is the focused element, not the last click */
  const opened = o => o && (o.el.isConnected ? o.el : o.sel ? C.$(o.sel) : null);
  C.peekKind = () => cur ? cur.kind : '';
  /* closing by hand steps Back, so the address follows (#63); a page change closes it quietly (and leaves the focus where the page puts it) */
  C.closePeek = (o = {}) => { if (!UI.peek) return; if (!o.quiet && !C.navBusy && history.state && history.state.id === UI.peek) { C.navSkip = true; history.back(); } /* closes now; the Back it takes only moves the address */ UI.peek = null; cur = null; C.sneakClose(true); pk().classList.remove('on'); pk().setAttribute('aria-hidden', 'true'); pk().inert = true; C.$('#scrim').classList.remove('on'); C.$$('.sel[data-id], .mv-row.sel, .mv-mk.sel').forEach(r => r.classList.remove('sel'));
    const back = o.quiet ? null : opened(opener); opener = null;
    if (pk().contains(document.activeElement)) { if (back && back.focus) back.focus({ preventScroll: true }); else document.activeElement.blur(); }
    /* a click away: the browser then moves the focus to what was clicked, or to nothing; when it is nothing, the opener has it */
    if (o.outside && back) setTimeout(() => { const a = document.activeElement; if ((!a || a === document.body) && back.isConnected) back.focus({ preventScroll: true }); }, 0); };
  /* with the peek open, a click on another work item or milestone moves the peek to it; a click anywhere
     else outside the peek closes it. The scrim no longer catches clicks, so the item under the pointer gets its own. */
  const ITEMISH = '[data-id], [data-card], .wl-row[data-row], [data-open], [data-item], [data-ms], [data-msel], .ucr';
  document.addEventListener('mousedown', e => {
    lastDown = { t: Date.now(), el: e.target };
    if (!UI.peek || e.button !== 0) return;
    if (e.target.closest('#peek, .menu, dialog, .toast, #ask, .top, .ai-bubble') || e.target.closest(ITEMISH)) return;
    C.closePeek({ outside: true });
  }, true);

  C.openItem = (id, list) => open({ kind: 'item', id, list: list || (cur && cur.kind === 'item' ? cur.list : [id]) });
  C.openMs = (id, list) => open({ kind: 'ms', id, list: list || C.mss().map(m => m.id) });
  C.redrawPeek = () => { if (cur) draw(false, 'redraw'); };
  function open(c) { const was = !!UI.peek, same = UI.peek === c.id; { const g = grabOpener(); if (!was) opener = g; else if (g) opener = g; /* moved by a click on another row: that row is the one to go back to */ } cur = c; UI.peek = c.id; tab = 'all'; C.sneakClose(true); draw(was, 'open'); markSel(); if (!same) C.nav && C.nav(was ? 'replace' : 'push'); }
  function markSel() { C.$$('[data-id]').forEach(r => r.classList.toggle('sel', !!cur && cur.kind === 'item' && r.dataset.id === cur.id && r.tagName === 'TR'));
    C.$$('.mv-row, .mv-mk').forEach(r => r.classList.toggle('sel', !!cur && cur.kind === 'ms' && r.dataset.ms === cur.id)); }

  const findItem = id => D.S.items.find(x => x.id === id);
  const findMs = id => C.mssAll().find(m => m.id === id);   /* an archived milestone opens too, read-only */
  const save = (kind, rec, ch, label, how = 'in the peek') => { const u = D.change(kind, rec, ch, D.who(how)); if (u) { C.refresh(); if (kind === 'item') C.changed(C.$(`tr[data-id="${rec.id}"], [data-card="${rec.id}"]`)); C.toast(label || `${kind === 'ms' ? rec.name : rec.id} saved`, u); } };

  function draw(swap, how) {
    const p = pk(); applyWidth();
    const a = document.activeElement, inside = !!a && p.contains(a), had = inside && a.id && a.tagName === 'BUTTON' ? a.id : '';   // the button that had the focus, to give it back after the redraw
    if (cur.kind === 'item') { const x = findItem(cur.id); if (!x) return C.closePeek(); if (x.archived) { p.innerHTML = archHtml('item', x); wireArch('item', x); } else { p.innerHTML = itemHtml(x); wireItem(x); } }
    else { const m = findMs(cur.id); if (!m) return C.closePeek(); if (m.archived) { p.innerHTML = archHtml('ms', m); wireArch('ms', m); } else { p.innerHTML = msHtml(m); wireMs(m); } }
    p.insertAdjacentHTML('afterbegin', '<div class="resize" title="Drag to change the width; double-click for the usual width"></div>');
    p.insertAdjacentHTML('beforeend', '<div class="sneak" id="sneak" role="dialog" aria-label="Sneak peek"></div>');
    wireResize(); syncWideBtn();
    const idx = cur.list.indexOf(cur.id);
    C.$('#pkPrev').disabled = idx <= 0; C.$('#pkNext').disabled = idx < 0 || idx >= cur.list.length - 1;
    C.$('#pkPrev').addEventListener('click', () => open({ ...cur, id: cur.list[idx - 1] }));
    C.$('#pkNext').addEventListener('click', () => open({ ...cur, id: cur.list[idx + 1] }));
    C.$('#pkClose').addEventListener('click', C.closePeek);
    C.$('#pkWide').addEventListener('click', toggleWide);
    C.$('#pkSneak')?.addEventListener('click', () => C.sneakOpen());   /* an archived record has neither: it is read-only */
    C.$('#pkFootSneak')?.addEventListener('click', () => C.sneakOpen());
    p.classList.add('on'); p.setAttribute('aria-hidden', 'false'); p.inert = false; C.$('#scrim').classList.add('on');
    /* stepping to another item (Previous, Next, a click on another row): the body fades from .4 to 1, the panel stays still (idea 4) */
    if (swap && how === 'open' && !C.reduce) { const bd = C.$('.pk-inner', p); if (bd) bd.classList.add('swap'); }
    /* the focus goes into the peek (its first control, Close) when it opens, and is kept when it moves or redraws: on the button that had it
       (Previous, Next), or on whatever was clicked outside; it is never left on nothing */
    if (how) { const was = had && C.$('#' + had, p), act = document.activeElement, lost = !act || act === document.body, go = was && !was.disabled ? was : null;
      if (go) go.focus({ preventScroll: true }); else if (how === 'open' && (!swap || lost)) C.$('#pkClose', p)?.focus({ preventScroll: true }); }
    if (swap) { const s = C.$('.pk-scroll', p); s.style.animation = 'none'; void s.offsetWidth; s.style.animation = 'view-in 260ms var(--ease-enter)'; }
  }

  const topBar = (right) => `<div class="pk-top"><button class="ib" id="pkClose" aria-label="Close">${C.icon('close')}</button><button class="ib" id="pkWide"></button><span class="vsep"></span>
    <button class="ib" id="pkPrev" aria-label="Previous">${C.icon('up')}</button><button class="ib" id="pkNext" aria-label="Next">${C.icon('down')}</button><span class="sp"></span>${right}</div>`;
  const foot = (what) => `<div class="pk-foot"><button class="kb" id="pkFootSneak"><kbd>/</kbd><kbd>/</kbd>Change this ${what} in words</button><span class="sp"></span><span class="pk-saved">Each change saves on its own, with Undo</span></div>`;

  /* ── feed ──
     Every history row is shown in full (FR-43a): when (local time), who and how, the field by its plain name, and from → to with the values
     formatted. Rich text (the latest update, notes) shows a compact word diff. The Activity tab carries a small filter. */
  const FN = D.FN, show = (f, v) => D.showVal(f, v) ?? 'changed';   /* the plain field names and values; Sneak peek reads them too */
  let actF = 'all';   /* the Activity tab's filter: all, changes or comments */
  const clip = (t, n = 140) => t.length > n ? t.slice(0, n).replace(/\s+\S*$/, '') + '…' : t;
  /* the words that changed, with a few words either side; the rest of an unchanged run becomes … (reuses the editor's word diff) */
  function compactDiff(from, to) {
    const A = C.plain(from || '').replace(/\s+/g, ' ').trim(), B = C.plain(to || '').replace(/\s+/g, ' ').trim();
    if (!A && !B) return '<span class="muted">empty</span>';
    if (!A) return `added <ins>${esc(clip(B))}</ins>`;
    if (!B) return `removed <del>${esc(clip(A))}</del>`;
    if (A.split(' ').length * B.split(' ').length > 90000 || !C.wdiff) return `changed to ${esc(clip(B))}`;
    const t = C.wdiff(A, B).split(' '), ch = t.map(w => w.startsWith('<ins>') || w.startsWith('<del>')), keep = t.map((w, i) => ch.slice(Math.max(0, i - 3), i + 4).some(Boolean));
    const out = []; t.forEach((w, i) => { if (keep[i]) out.push(w); else if (out[out.length - 1] !== '…') out.push('…'); });
    return out.join(' ');
  }
  const LIFE = { '+': 'Created', '-': 'Deleted', '*': 'Undone' }, LIFE_IC = { '+': 'plus', '-': 'trash', '*': 'undo' };
  /* one history row as a list item; k: 'upd' for comments and updates, 'act' for every other change */
  function histRow(h, kind) {
    const w = D.whoHow(h), who = w.who ? `<b>${esc(w.who)}</b>${w.how ? ', ' + esc(w.how) : ''}` : `<b>${esc(w.how || 'You')}</b>`, undone = /^Undone/.test(h.text || ''), life = LIFE[h.field];
    const head = `<span class="hh">${who} <span class="t">· ${D.when(h)}</span></span>`;
    let body, ic;
    if (life) { body = `<span class="hw"><span class="hf">${esc(h.text || life)}</span></span>`; ic = /^(Archived|Restored)$/.test(h.text || '') ? 'archive' : LIFE_IC[h.field]; }
    else if (D.RICH.includes(h.field)) { body = `<span class="hw"><span class="hf">${esc(D.fieldName(h.field, kind))}</span> <span class="hd">${compactDiff(h.from, h.to)}</span></span>`; ic = D.COMMENT.includes(h.field) ? 'pen' : 'doc'; }
    else { const f = D.showVal(h.field, h.from), t = D.showVal(h.field, h.to);
      body = `<span class="hw"><span class="hf">${esc(D.fieldName(h.field, kind))}</span> ${f === null || t === null ? '<span class="hv">changed</span>' : `<span class="hv">${esc(f)} <span class="ar" aria-label="to">→</span> ${esc(t)}</span>`}</span>`; ic = 'doc'; }
    if (undone && !life) { body += `<span class="hn">${esc(h.text)}</span>`; ic = 'undo'; }
    return { k: D.COMMENT.includes(h.field) && !undone ? 'upd' : 'act', ch: !D.COMMENT.includes(h.field), html: `<li><span class="fi">${C.icon(ic, 's')}</span><span class="hb">${head}${body}</span></li>` };
  }
  function feedHtml(kind, rec, which) {
    const hs = D.historyOf(kind, kind === 'project' ? rec.code : rec.id).filter(h => h.code === rec.code);
    let rows = hs.map(h => histRow(h, kind));
    if (kind === 'item' && rec.updatedAt && !hs.some(h => h.field === '+')) rows.push({ k: 'act', ch: true, html: `<li><span class="fi">${C.icon('doc', 's')}</span><span class="hb"><span class="hh"><b>Imported</b> <span class="t">· ${D.fd(rec.updatedAt.slice(0, 10))}</span></span><span class="hw"><span class="hf">from ${esc(rec.source || 'the project record')}</span></span></span></li>` });
    if (kind === 'item' && C.cmRows) C.cmRows(rec.code, rec.id).forEach(c => rows.push({ k: 'upd', ch: false, html: `<li><span class="fi">${C.icon('pen', 's')}</span><span class="hb"><span class="hh"><b>${esc(c.by)}</b>, client comment <span class="t">· ${D.fd(c.at.slice(0, 10))}</span></span><span class="hw"><span class="hf">Publication ${c.n}</span> <span class="hd">${esc(c.text)}</span></span></span></li>` }));
    if (kind === 'item') rows.push({ k: 'src', html: `<li><span class="fi">${C.icon('doc', 's')}</span><span class="hb"><span class="hh"><b>Source</b></span><span class="hw"><span class="hf">${esc(rec.source || 'Added by hand in clark')}</span></span></span></li>` });
    rows = rows.filter(r => which === 'all' || (which === 'activity' && r.k !== 'src' && (actF === 'all' || (actF === 'changes' ? r.ch : !r.ch))) || (which === 'updates' && r.k === 'upd') || (which === 'source' && r.k === 'src'));
    return rows.length ? `<ul class="feed">${rows.map(r => r.html).join('')}</ul>` : '<p class="muted" style="font-size:13px;padding:10px 0">Nothing here yet.</p>';
  }
  const tabsHtml = () => `<div class="pk-tabs" role="tablist">${[['all', 'All'], ['activity', 'Activity'], ['updates', 'Updates'], ['source', 'Source']].map(([k, t]) => `<button role="tab" data-tab="${k}" aria-selected="${tab === k}">${t}</button>`).join('')}</div><div id="pkFeed"></div>`;
  const filtHtml = () => `<div class="pk-filt"><div class="seg" role="group" aria-label="Show">${[['all', 'All'], ['changes', 'Changes'], ['comments', 'Comments and updates']].map(([k, t]) => `<button data-hf="${k}" aria-pressed="${actF === k}">${t}</button>`).join('')}</div></div>`;
  function wireTabs(kind, rec) { const f = (focus) => { C.$('#pkFeed').innerHTML = (tab === 'activity' ? filtHtml() : '') + feedHtml(kind, rec, tab); C.$$('.pk-tabs button').forEach(b => b.setAttribute('aria-selected', b.dataset.tab === tab));
      C.$$('[data-hf]', pk()).forEach(b => b.addEventListener('click', () => { actF = b.dataset.hf; f(actF); })); if (focus) C.$(`[data-hf="${focus}"]`, pk())?.focus(); };
    C.$$('.pk-tabs button').forEach(b => b.addEventListener('click', () => { tab = b.dataset.tab; f(); })); f(); }

  /* ── the work item peek ── */
  function warn(x) {
    if (!x.due || !C.isOpen(x)) return '';
    const dow = new Date(x.due + 'T00:00:00').getDay();
    if (dow === 0 || dow === 6) { const fri = D.addDays(x.due, dow === 0 ? -2 : -1), mon = D.addDays(x.due, dow === 0 ? 1 : 2);
      return `<div class="pk-warn">${C.icon('flash', 's')} Due on a ${C.dayName(x.due)} (${D.fd(x.due)}): a working day is usually meant</div><div class="pk-fix"><button data-move="${fri}">Move to Friday ${D.fd(fri)}</button><button data-move="${mon}">Move to Monday ${D.fd(mon)}</button></div>`; }
    if (x.type === 'A' && D.days(x.due) < 0) { const f = D.friday() === D.TODAY ? D.addDays(D.TODAY, 7) : D.friday();
      return `<div class="pk-warn">${C.icon('flash', 's')} ${C.dy(-D.days(x.due))} overdue (due ${D.fd(x.due)})</div><div class="pk-fix"><button data-move="${f}">Move to Friday ${D.fd(f)}</button><button data-move="${D.addDays(D.TODAY, 7)}">Move a week on</button></div>`; }
    return '';
  }
  /* the peek's property icons in colour ("give my icons in peek some colouring"): the state's colour, the priority's, and the date's (late red, due soon amber) */
  const IC = { r: 'var(--status-red)', a: 'var(--status-amber)', g: 'var(--status-green)', b: 'var(--brand-blue)', n: 'var(--grey-500)' };
  const PRI_IC = { Urgent: IC.r, High: IC.a, Medium: IC.b, Low: IC.n };
  function itemHtml(x) {
    const p = C.P(), late = x.type === 'A' && x.due && D.days(x.due) < 0 && C.isOpen(x);
    const st = x.type === 'R' || x.type === 'I' ? `${x.status} · ${{ R: 'Red', A: 'Amber', G: 'Green' }[C.ragOf(x)]}` : x.status;
    const msOpts = C.mssAll().filter(m => !m.archived || m.id === x.ms).map(m => `<option value="${m.id}"${x.ms === m.id ? ' selected' : ''}>${esc(C.msName(m.id))}</option>`).join('');   /* the link to an archived milestone is kept, and says so */
    const ucOpts = D.S.usecases.filter(u => u.code === x.code && (!u.archived || u.id === x.uc)).map(u => `<option value="${u.id}"${x.uc === u.id ? ' selected' : ''}>${esc(u.ref || u.id)}: ${esc(u.title.split('\n')[0])}</option>`).join('');
    return `${topBar(`<button class="ib" id="pkEye" aria-label="Client-visible: ${x.client ? 'on' : 'off'}" aria-pressed="${x.client}" title="${x.client ? 'Shown to the client' : 'Not shown to the client'}">${C.icon(x.client ? 'eye' : 'eyeoff')}</button>
      <button class="ib" id="pkSneak" aria-label="Sneak peek: change this item in words">${C.icon('sparkle')}</button>${C.isOpen(x) ? `<button class="ib" id="pkMail" aria-label="Draft email (C)" title="Draft email (C)">${C.icon('mail')}</button>` : ''}<button class="ib" id="pkLink" aria-label="Copy link">${C.icon('link')}</button><button class="ib" id="pkMore" aria-label="More">${C.icon('more')}</button>`)}
    <div class="pk-scroll"><div class="pk-inner">
      <div class="pk-meta"><span class="type ${x.type}">${x.type}</span>${x.id} · ${esc(p.name)}${x.client ? ' <span class="tag cl">' + C.icon('eye', 's') + 'Client</span>' : ''}</div>
      ${warn(x)}
      <div class="pk-title" id="pkTitle" contenteditable="plaintext-only" role="textbox" aria-label="Title" spellcheck="true">${esc(x.title)}</div>
      <div class="pk-props">
        <button class="pk-prop" data-prop="status" aria-label="Status: ${esc(st)}" style="--ic:${IC[C.look(x)[0]]}">${C.icon('half')}<span class="v">${esc(st)}</span></button>
        <button class="pk-prop" data-prop="priority" aria-label="Priority: ${x.priority}" style="--ic:${PRI_IC[x.priority] || IC.n}">${C.icon('bars')}<span class="v">${esc(x.priority)}</span></button>
        <button class="pk-prop" data-prop="owner" aria-label="${x.type === 'D' ? 'Decision by' : 'Owner'}: ${esc(x.owner || 'none')}"><span class="av">${C.initials(x.owner)}</span><span class="v">${esc(x.owner || 'No owner')}</span></button>
        <button class="pk-prop${late ? ' late' : ''}" data-prop="due" aria-label="${x.type === 'D' ? 'Date' : 'Due'}: ${D.fd(x.due) || 'none'}" style="--ic:${late ? IC.r : x.due && C.isOpen(x) && D.days(x.due) <= 7 ? IC.a : x.due ? IC.b : IC.n}">${C.icon('cal')}<span class="v">${D.fd(x.due) || 'No date'}${late ? '<span class="od">overdue</span>' : x.due ? `<small>${C.dueWords(x.due)}</small>` : ''}</span></button>
      </div>
      <div class="pk-fresh" id="pkFresh">${(f => `Raised ${D.fd(f.raised)} · Last reviewed ${D.fd(f.reviewed)}${D.notReviewed(x) ? ' <span class="tag" title="Open, and not changed by hand for 14 days or more">Not reviewed in 14 days</span>' : ''}`)(D.fresh(x))}</div>
      <label class="sw pk-act"><button class="switch" id="pkAct" role="switch" aria-checked="${!!x.clientAct}" aria-label="Needed from the client"></button>Needed from the client<small>Lists it under “Needs from you”</small></label>
      <div class="pk-lab">Latest update <button class="pk-draft" id="pkDraft">${C.icon('sparkle', 's')}Draft</button></div>
      <div class="pk-text" id="pkUpd"></div>
      <div class="pk-last">${C.icon('clock', 's')} Last updated ${D.fd((x.updatedAt || '').slice(0, 10))} ${(x.updatedAt || '').slice(11)}</div>
      <details class="pk-det" ${C.store.get('pkDetails', false) ? 'open' : ''}><summary>${C.icon('chev', 's')}Details</summary><div class="pk-fields">
        <label>Description</label><div class="field-inl" id="pkDesc"></div>
        <label for="pkType">Type</label><select class="field" id="pkType" data-f="type">${Object.entries(D.TYPES).map(([k, t]) => `<option value="${k}"${x.type === k ? ' selected' : ''}>${t}</option>`).join('')}</select>
        <label for="pkWs">Workstream</label><select class="field" id="pkWs" data-f="ws">${p.ws.map(w => `<option${x.ws === w ? ' selected' : ''}>${esc(w)}</option>`).join('')}</select>
        <label for="pkMs">Milestone</label><select class="field" id="pkMs" data-f="ms"><option value="">None</option>${msOpts}</select>
        <label for="pkUc">Use case</label><select class="field" id="pkUc" data-f="uc"><option value="">None</option>${ucOpts}</select>
        
        <label>Client wording</label><div class="field-inl" id="pkClT"></div>
      </div></details>
      ${tabsHtml()}
    </div></div>${foot('item')}`;
  }
  function wireItem(x) {
    const t = C.$('#pkTitle');
    t.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); t.blur(); } if (e.key === 'Escape') { e.stopPropagation(); t.textContent = x.title; t.blur(); } });
    t.addEventListener('blur', () => { const v = t.textContent.trim(); if (v && v !== x.title) save('item', x, { title: v }); else t.textContent = x.title; });
    C.$$('[data-f]', pk()).forEach(el => el.addEventListener('change', () => save('item', x, { [el.dataset.f]: el.value.trim() })));
    C.$$('[data-move]', pk()).forEach(b => b.addEventListener('click', () => save('item', x, { due: b.dataset.move }, `${x.id} moved to ${D.fd(b.dataset.move)}`)));
    C.$('details.pk-det', pk()).addEventListener('toggle', e => C.store.set('pkDetails', e.target.open));
    C.$('#pkEye').addEventListener('click', () => save('item', x, { client: !x.client }, x.client ? `${x.id} hidden from the client` : `${x.id} shown to the client`, 'with the eye'));
    C.$('#pkMail')?.addEventListener('click', () => mailPane(x));
    C.$('#pkAct').addEventListener('click', () => save('item', x, { clientAct: !x.clientAct }, x.clientAct ? `${x.id} is no longer needed from the client` : `${x.id} marked as needed from the client`));
    C.$('#pkLink').addEventListener('click', () => { try { navigator.clipboard.writeText(location.href.split('#')[0] + '#work&item=' + x.id); } catch (e) { /* no clipboard */ } C.toast('Link copied'); });
    C.$('#pkMore').addEventListener('click', e => C.menu(e.currentTarget, [
      { html: `${C.icon('plus', 's')} Duplicate`, onPick: () => { const n = { ...D.clone(x), id: C.nextId(x.type), title: x.title + ' (copy)', updatedAt: D.stamp(), source: 'Duplicated from ' + x.id }; const u = D.create('item', n, D.who('in the peek')); C.refresh(); C.openItem(n.id); C.toast(`${n.id} added`, u); } },
      /* archived, never deleted (FR-43c, #166): one step, Undo in the toast, a history line */
      { sep: true }, { html: `${C.icon('archive', 's')} Archive`, onPick: () => { const u = D.archive(x, true, D.who('in the peek'), 'item'); if (!u) return; C.closePeek(); C.refresh(); C.toast(`Archived ${x.id}. It's out of the lists and counts.`, u); } }], { align: 'right' }));
    const rich = (sel, f, label, ph) => C.inline(C.$(sel, pk()), { html: C.toHtml(x[f]), label, placeholder: ph, place: f === 'clientText' ? 'client_message' : 'plain', draft: f === 'update' ? () => `<p>${esc(C.draftUpdate(x))}</p>` : null, onSave: h => save('item', x, { [f]: h }) });
    rich('#pkUpd', 'update', 'Latest update', 'Add the latest update…'); rich('#pkDesc', 'desc', 'Description', 'What this is about'); rich('#pkClT', 'clientText', 'Client wording', 'Plain wording a client can read (leave empty to use the title)');
    C.$('#pkDraft').addEventListener('click', () => { const u = D.change('item', x, { update: `<p>${esc(C.draftUpdate(x))}</p>` }, D.who('with a draft')); C.refresh(); C.toast('Latest update drafted (prototype: written by rules, not AI)', u); });
    C.$$('.pk-prop', pk()).forEach(b => b.addEventListener('click', () => propPick(b, x)));
    wireTabs('item', x);
  }
  /* ── Draft email (#50; creaite's Draft email and Draft chase: its FR-79, FR-186, FR-241): from the peek, an email about this item,
     written in plain code (no model), ready to paste into Outlook. clark never sends it. Three kinds: an update request, a chase
     (First chase, Second chase, Firmer chase) and, for a decision, a decision request. Nothing changes until "I sent it", which records the date in history. ── */
  const MAILC = { red: '#B3261E', amber: '#8A5A00', ink: '#1E1F1E', head: '#F1F3F4', rule: '#D9D9E0' };
  const greet = () => { const h = new Date().getHours(); return h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening'; };
  const workdays = (iso, n) => { let d = iso; while (n > 0) { d = D.addDays(d, 1); const w = new Date(d + 'T00:00:00').getDay(); if (w && w < 6) n--; } return d; };
  function mailText(x, o) {
    const first = (x.owner || 'there').split(/\s+/)[0], late = x.due && D.days(x.due) < 0 && C.isOpen(x), p = C.P(), me = (D.S.profile || {}).name || '';
    const chased = D.S.history.filter(h => h.kind === 'item' && h.id === x.id && h.field === 'chase').length;
    const kind = x.type === 'D' && x.status === 'Pending' ? 'decision' : late || o.chase ? 'chase' : 'update';
    const tone = o.tone || ['first', 'second', 'firmer'][Math.min(2, chased)];
    /* the wording follows the product's draft_email.py (#50, d13dc57): no filler, no deadline or claim clark can't know, tones that step up politely */
    const dl = late ? -D.days(x.due) : 0, times = chased === 1 ? 'once' : chased === 2 ? 'twice' : `${chased} times`;
    const open = { update: `I'm pulling together where things stand on the item below.`, decision: `A quick note on the decision below${o.by ? `, needed by ${D.fd(o.by)}` : ''}.`,
      chase: { first: `A quick reminder about the item below${late ? ', which is now past its due date' : ''}.`, second: `I'm following up on my earlier note about the item below, which is still ${late ? 'overdue' : 'open'}.`, firmer: `${late ? `This item is now ${dl} day${dl === 1 ? '' : 's'} overdue.` : 'This item is still open.'}${chased ? ` I have chased it ${times}.` : ''}` }[tone] }[kind];
    const ask = kind === 'decision' ? `Could you let me have the decision, or tell me what you need to make it${o.by ? `, by ${D.fd(o.by)}` : ''}?` : kind === 'chase' ? { first: 'Could you let me know where it stands, and when I can expect it?', second: 'Could you let me have an update, and a date for it?', firmer: 'Please reply with a firm date, or tell me what is blocking it, so that we can resolve it together.' }[tone] : "Could you let me know where it stands, and flag anything that's blocking you or that you need from me?";
    const subject = `${p.name} · ${x.id} · ${kind === 'decision' ? (tone === 'second' ? 'Decision needed (second reminder)' : 'Decision needed') : kind === 'chase' ? { first: 'Reminder', second: 'Second reminder', firmer: 'Reply needed' }[tone] : 'Update request'}`;
    const dueTxt = x.due ? `${D.fd(x.due)}${late ? ` (${C.dy(-D.days(x.due))} overdue)` : D.days(x.due) <= 7 ? ` (due in ${C.dy(D.days(x.due))})` : ''}` : 'No date';
    const td = 'style="padding:6px 10px;border-bottom:1px solid ' + MAILC.rule + ';font-family:Calibri,Arial,sans-serif;font-size:11pt;color:' + MAILC.ink + ';vertical-align:top"';
    const html = `<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:${MAILC.ink}"><p style="margin:0 0 10px">${greet()} ${esc(first)},</p><p style="margin:0 0 10px">${esc(open)}</p>
      <table cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 10px"><tr><td ${td.replace('style="', `style="background:${MAILC.head};font-weight:bold;`)}>ID</td><td ${td.replace('style="', `style="background:${MAILC.head};font-weight:bold;`)}>Item</td><td ${td.replace('style="', `style="background:${MAILC.head};font-weight:bold;`)}>Due</td><td ${td.replace('style="', `style="background:${MAILC.head};font-weight:bold;`)}>Priority</td></tr>
      <tr><td ${td}>${x.id}</td><td ${td}>${esc(x.title)}${o.update && C.plain(x.update) ? `<br><span style="color:#5A6270">Latest: ${esc(C.plain(x.update))}</span>` : ''}</td><td ${td.replace('color:' + MAILC.ink, 'color:' + (late ? MAILC.red : x.due && D.days(x.due) <= 7 ? MAILC.amber : MAILC.ink) + (late ? ';font-weight:bold' : ''))}>${dueTxt}</td><td ${td.replace('color:' + MAILC.ink, 'color:' + MAILC.ink + (x.priority === 'Urgent' ? ';font-weight:bold' : ''))}>${esc(x.priority)}</td></tr></table>
      <p style="margin:0 0 10px">${esc(ask)}${o.by && kind !== 'decision' ? ` If you can reply by ${D.fd(o.by)}, that would help.` : ''}</p><p style="margin:0 0 10px">Thank you.</p><p style="margin:0">Kind regards,<br>${esc(me.split(/\s+/)[0] || '')}</p></div>`;
    const text = `${greet()} ${first},\n\n${open}\n\n${x.id}  ${x.title}\nDue: ${dueTxt} · Priority: ${x.priority}${o.update && C.plain(x.update) ? `\nLatest: ${C.plain(x.update)}` : ''}\n\n${ask}${o.by && kind !== 'decision' ? ` If you can reply by ${D.fd(o.by)}, that would help.` : ''}\n\nThank you.\n\nKind regards,\n${me.split(/\s+/)[0] || ''}`;
    return { kind, tone, subject, html, text, chased };
  }
  function mailPane(x) {
    const o = { by: workdays(D.TODAY, 2), update: false, tone: '' };
    const draw = () => { const m = mailText(x, o);
      C.dialog(`<div class="dlg-h"><h2>${C.icon('mail', 's')} Draft email: ${esc(x.owner || 'no owner')}</h2><p>${{ update: 'An update request', chase: `A chase · ${m.chased ? `chased ${m.chased} time${m.chased > 1 ? 's' : ''} before` : 'not chased yet'}`, decision: 'A decision request' }[m.kind]}. clark never sends it: copy it into Outlook.</p></div>
        <div class="mail-f"><label>To</label><span>${esc(x.owner || 'No owner')} <small class="muted">· no email recorded</small></span>
          <label for="mlSub">Subject</label><input class="field" id="mlSub" value="${esc(m.subject)}">
          <label for="mlBy">Reply by</label><input class="field" type="date" id="mlBy" min="${D.TODAY}" value="${o.by}">
          ${m.kind === 'chase' ? `<label>Tone</label><span class="seg">${[['first', 'First chase'], ['second', 'Second chase'], ['firmer', 'Firmer chase']].map(([v, t]) => `<button type="button" data-tone="${v}" aria-pressed="${m.tone === v}">${t}</button>`).join('')}</span>` : ''}
          <label></label><label class="chk"><input type="checkbox" id="mlUpd" ${o.update ? 'checked' : ''}> Include the latest update</label></div>
        <div class="mail-prev" id="mlPrev" contenteditable="true" aria-label="The email; you can edit it">${m.html}</div>
        <div class="dlg-f"><button type="button" class="btn quiet" id="mlSent">I sent it</button><span class="sp"></span><button type="button" class="btn" id="mlText">Copy as text</button><button type="button" class="btn pri" id="mlCopy">Copy for Outlook</button></div>`, d => {
        C.$('#mlBy', d).addEventListener('change', e => { o.by = e.target.value < D.TODAY ? D.TODAY : e.target.value; d.close(); draw(); });
        C.$('#mlUpd', d).addEventListener('change', e => { o.update = e.target.checked; d.close(); draw(); });
        C.$$('[data-tone]', d).forEach(b => b.addEventListener('click', () => { o.tone = b.dataset.tone; o.chase = true; d.close(); draw(); }));
        const copy = async rich => { const h = C.$('#mlPrev', d).innerHTML, t = C.$('#mlPrev', d).innerText, sub = C.$('#mlSub', d).value;
          try { if (rich && window.ClipboardItem) await navigator.clipboard.write([new ClipboardItem({ 'text/html': new Blob([h], { type: 'text/html' }), 'text/plain': new Blob([t], { type: 'text/plain' }) })]); else await navigator.clipboard.writeText(rich ? t : `Subject: ${sub}\n\n${t}`); C.toast(rich ? 'Copied for Outlook' : 'Copied as text'); }
          catch (e) { const r = document.createRange(); r.selectNodeContents(C.$('#mlPrev', d)); getSelection().removeAllRanges(); getSelection().addRange(r); C.toast('Press ⌘C to copy'); } };
        C.$('#mlCopy', d).addEventListener('click', () => copy(true)); C.$('#mlText', d).addEventListener('click', () => copy(false));
        C.$('#mlSent', d).addEventListener('click', () => { const u = D.change('item', x, { chase: (x.chase || 0) + 1 }, D.who('sent ' + (m.kind === 'update' ? 'an update' : 'a ' + m.kind) + ' email'), `${m.kind === 'chase' ? 'Chased' : 'Asked'} ${x.owner || ''} on ${D.fd(D.TODAY)}`); d.close(); C.refresh(); C.toast(`Recorded: ${m.kind === 'chase' ? 'chased' : 'emailed'} ${x.owner || 'the owner'} on ${D.fd(D.TODAY)}`, u); });
      }); };
    draw();
  }
  C.mailPane = x => mailPane(x);
  document.addEventListener('keydown', e => { if (!UI.peek || e.key !== 'c' || e.metaKey || e.ctrlKey || e.altKey || C.typing(document.activeElement) || C.popOpen() || document.querySelector('dialog[open]') || C.edIsOpen()) return; const x = findItem(UI.peek); if (x && C.isOpen(x) && !x.archived) { e.preventDefault(); mailPane(x); } });
  C.propPick = (b, x, how) => propPick(b, x, how);   // the same pickers inline in the Work items table
  function propPick(b, x, how = 'in the peek') {
    const f = b.dataset.prop, sv = ch => save('item', x, ch, undefined, how);
    if (f === 'status') {
      const its = D.STATUSES[x.type].map(s => ({ label: s, selected: x.status === s, onPick: () => sv({ status: s }) }));
      if (x.type === 'R' || x.type === 'I') its.push({ sep: true }, { lab: 'Rating' }, ...[['R', 'Red'], ['A', 'Amber'], ['G', 'Green']].map(([v, t]) => ({ label: t, selected: C.ragOf(x) === v, onPick: () => sv(C.ragSet(x, v)) })));
      return C.menu(b, its, { select: true });
    }
    if (f === 'priority') return C.menu(b, D.PRIORITIES.map(s => ({ label: s, selected: x.priority === s, onPick: () => sv({ priority: s }) })), { select: true });
    if (f === 'owner') {
      /* a name field over the first eight people, on C.menu so the people have its keys: Down from the field, Up and Down, Home and End (#99) */
      return C.menu(b, C.people().slice(0, 8).map(n => ({ html: `<span class="av">${C.initials(n)}</span>${esc(n)}`, onPick: () => sv({ owner: n }) })), {
        head: `<div style="padding:6px" role="presentation"><input class="field" id="ownIn" placeholder="Type a name" aria-label="Owner" value="${esc(x.owner)}" list="ownList"><datalist id="ownList">${C.people().map(n => `<option value="${esc(n)}">`).join('')}</datalist></div>`,
        wire: el => { const i = C.$('#ownIn', el); i.focus(); i.select();
          i.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); C.closePop(); sv({ owner: i.value.trim() }); } }); } });
    }
    if (f === 'due') {
      const opts = [['Today', D.TODAY], ['Tomorrow', D.addDays(D.TODAY, 1)], ['Friday', D.friday() === D.TODAY ? D.addDays(D.TODAY, 7) : D.friday()], ['Next week', D.addDays(D.TODAY, 7)]];
      C.calPick(b, x.due, v => sv({ due: v }), { quick: [...opts, ['No date', '']] });
    }
  }
  /* creaite's IDs: <CODE>-A-NNN and <CODE>-D-NNN; risks and issues share one series, <CODE>-NNN, with the type as a field */
  C.nextId = (type, code) => { const p = code || C.P().code, raid = type === 'R' || type === 'I', n = Math.max(0, ...D.S.items.filter(x => x.code === p && (raid ? x.type === 'R' || x.type === 'I' : x.type === type)).map(x => +x.id.split('-').pop() || 0)) + 1; return raid ? `${p}-${String(n).padStart(3, '0')}` : `${p}-${type}-${String(n).padStart(3, '0')}`; };
  C.draftUpdate = x => {
    const [, lk] = C.look(x), m = C.mss().find(mm => mm.id === x.ms);
    return `${lk === 'Overdue' ? `Overdue since ${D.fd(x.due)}.` : x.due ? `Due ${D.fd(x.due)}.` : ''} ${x.owner ? `${x.owner} is ${x.status === 'Open' ? 'yet to start' : 'working on it'}.` : 'Needs an owner.'}${m ? ` Needed for ${m.name.charAt(0).toLowerCase() + m.name.slice(1)} on ${D.fd(m.agreed)}.` : ''}`.trim();
  };

  /* ── the milestone peek (creaite's milestone editor) ── */
  const STATES = ['Forecast', 'On track', 'At risk', 'Slipped', 'Overdue', 'Achieved'];
  const why = (m, st) => ({
    Achieved: `Achieved on ${D.fd(m.achievedOn)}. Pick another state to reopen it.`,
    Forecast: 'A forecast date, not yet agreed. Choose On track once the date is agreed; it then becomes the baseline.',
    'At risk': 'Marked at risk by hand. The dates alone would say ' + (m.forecast > m.agreed ? 'Slipped' : 'On track') + '.',
    Overdue: `The ${m.forecast > m.agreed ? 'forecast' : 'agreed'} date (${D.fd(m.forecast || m.agreed)}) has passed and it isn't achieved.`,
    Slipped: `Following the dates. It is now expected ${C.dy(D.slip(m))} after its agreed date.`,
    'On track': 'Following the dates. The forecast is not later than the agreed date.',
  }[st]);
  function msHtml(m) {
    const st = D.msState(m), p = C.P(), linked = D.S.items.filter(x => x.code === m.code && x.ms === m.id && !x.archived);
    return `${topBar(`<button class="ib" id="pkEye" aria-label="Visible to client: ${m.client ? 'on' : 'off'}" aria-pressed="${m.client}">${C.icon(m.client ? 'eye' : 'eyeoff')}</button><button class="ib" id="pkSneak" aria-label="Sneak peek: change this milestone in words">${C.icon('sparkle')}</button><button class="ib" id="pkMore" aria-label="More">${C.icon('more')}</button>`)}
    <div class="pk-scroll"><div class="pk-inner">
      <div class="pk-meta">${esc(p.code)}-${m.id.replace('M', 'M-00')} · ${esc(p.name)}</div>
      <div class="pk-title" id="pkTitle" contenteditable="plaintext-only" role="textbox" aria-label="Name">${esc(m.name)}</div>
      <div class="mp-chips"><span class="mst ${C.msCls(st)}">${C.msMark(st)}${st}</span><span>Agreed <b>${D.fd(m.agreed)}</b></span>${st === 'Achieved' ? '' : `<span>Forecast <b>${D.fd(m.forecast || m.agreed)}</b></span>`}<span>Progress <b>${m.progress == null ? 'not set' : m.progress + '%'}</b></span></div>
      <div class="mp-sec"><h3>State</h3><div class="states">${STATES.map(s => `<button data-st="${s}" aria-pressed="${s === st}" ${s === 'Overdue' && st !== 'Overdue' ? 'aria-disabled="true" title="Overdue follows the dates"' : ''}>${C.msMark(s)}${s}</button>`).join('')}</div><div class="mp-why">${why(m, st)}</div></div>
      <div class="mp-sec"><h3>Dates</h3><div class="mp-dates">
        ${st === 'Achieved' ? `<div><div class="k">Achieved on</div><input class="field" type="date" id="mpAch" value="${m.achievedOn}"></div><div><div class="k">Agreed</div><div class="bv">${D.fd(m.agreed)}</div></div>`
        : `<div><div class="k">Agreed date</div><div class="bv">${D.fd(m.agreed)} <button class="btn sm" id="mpRebase" ${m.forecast && m.forecast !== m.agreed ? '' : 'disabled'}>Move the agreed date…</button></div><div class="sub">Original ${D.fd(m.original || m.agreed)}${m.original && m.original !== m.agreed ? ` · moved ${D.days(m.agreed) - D.days(m.original) > 0 ? '+' : '-'}${C.dy(Math.abs(D.days(m.agreed) - D.days(m.original)))}` : ''}</div></div>
          <div><div class="k">Forecast</div><input class="field" type="date" id="mpFc" value="${m.forecast || m.agreed}">${D.slip(m) > 0 ? `<div class="sub late" style="color:var(--status-red-text)">${C.dy(D.slip(m))} later than agreed</div>` : ''}</div>`}
      </div></div>
      <div class="mp-sec"><h3>Progress</h3><div class="prog"><input type="range" min="0" max="100" step="5" id="mpPr" value="${m.progress ?? 0}" aria-label="Progress"><input class="field" type="number" min="0" max="100" id="mpPrN" value="${m.progress ?? ''}" placeholder="%" aria-label="Progress in per cent"></div><div class="sub muted" style="font-size:13px;margin-top:6px">Set by hand. Not calculated from actions.</div></div>
      <div class="mp-sec"><h3>Description</h3><div class="k muted" style="font-size:13px;margin-bottom:4px">Scope and needs</div><div class="field-inl" id="mpDesc"></div>
        <div class="k muted" style="font-size:13px;margin:12px 0 4px">Owner</div><input class="field" id="mpOwn" list="mpPeople" value="${esc(m.owner)}" placeholder="Choose the owner"><datalist id="mpPeople">${C.people().map(n => `<option value="${esc(n)}">`).join('')}</datalist>
        <div class="k muted" style="font-size:13px;margin:12px 0 4px">Workstream</div><select class="field" id="mpWs">${p.ws.map(w => `<option${m.ws === w ? ' selected' : ''}>${esc(w)}</option>`).join('')}</select></div>
      <div class="mp-sec"><h3>Client view</h3><label class="sw"><button class="switch" id="mpCl" role="switch" aria-checked="${m.client}" aria-label="Visible to client"></button>Visible to client</label>
        <div class="k muted" style="font-size:13px;margin:12px 0 4px">Client wording</div><div class="field-inl" id="mpClT"></div></div>
      <div class="mp-sec"><h3>Linked work items · ${linked.length}</h3>${linked.length ? `<ul class="feed">${linked.map(x => `<li><span class="type ${x.type}">${x.type}</span><span><button class="link" data-open="${x.id}">${x.id}</button> ${esc(x.title)} ${C.pill(C.look(x))}</span></li>`).join('')}</ul>` : '<p class="muted" style="font-size:13px">None yet. Link an item from its peek (Details, Milestone).</p>'}</div>
      ${tabsHtml()}
    </div></div>${foot('milestone')}`;
  }
  function wireMs(m) {
    const t = C.$('#pkTitle');
    t.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); t.blur(); } });
    t.addEventListener('blur', () => { const v = t.textContent.trim(); if (v && v !== m.name) save('ms', m, { name: v }); else t.textContent = m.name; });
    C.$$('.states button').forEach(b => b.addEventListener('click', () => {
      const s = b.dataset.st; if (b.getAttribute('aria-disabled') === 'true') return;
      if (s === 'Achieved') save('ms', m, { achievedOn: D.TODAY, manual: '', progress: 100 }, `${m.name} achieved`);
      else if (s === 'At risk') save('ms', m, { manual: 'At risk', achievedOn: '' });
      else if (s === 'Forecast') save('ms', m, { manual: 'Forecast', achievedOn: '' }, `${m.name} marked as a forecast`);
      else if (s === 'On track') save('ms', m, { manual: '', achievedOn: '', forecast: m.agreed < D.TODAY ? D.addDays(D.TODAY, 7) : m.agreed, ...(m.agreed < D.TODAY ? { agreed: D.addDays(D.TODAY, 7) } : {}) });
      else if (s === 'Slipped') { save('ms', m, { manual: '', achievedOn: '', forecast: (m.forecast > m.agreed ? m.forecast : D.addDays(m.agreed, 14)) }, `${m.name}: forecast moved; set the new date`); setTimeout(() => C.$('#mpFc')?.focus(), 50); }
    }));
    C.$('#mpFc')?.addEventListener('change', e => e.target.value && save('ms', m, { forecast: e.target.value }));
    C.$('#mpAch')?.addEventListener('change', e => e.target.value && save('ms', m, { achievedOn: e.target.value }));
    C.$('#mpRebase')?.addEventListener('click', () => C.dialog(`<div class="dlg-h"><h2>Move the agreed date of ${esc(m.name)}?</h2><p>The agreed date moves from ${D.fd(m.agreed)} to the forecast, ${D.fd(m.forecast)}. The original date (${D.fd(m.original || m.agreed)}) is kept, and Movement shows the change.</p></div>
      <div class="dlg-f"><button class="btn quiet" data-close>Cancel</button><button class="btn pri" id="rbYes">Move the agreed date</button></div>`, d => C.$('#rbYes', d).addEventListener('click', () => { d.close(); save('ms', m, { agreed: m.forecast, original: m.original || m.agreed }, `${m.name}: the agreed date is now ${D.fd(m.forecast)}`); })));
    const pr = C.$('#mpPr'), prn = C.$('#mpPrN');
    pr.addEventListener('input', () => { prn.value = pr.value; });
    pr.addEventListener('change', () => save('ms', m, { progress: +pr.value }));
    prn.addEventListener('change', () => { const v = prn.value === '' ? null : Math.max(0, Math.min(100, +prn.value)); save('ms', m, { progress: v }); });
    C.inline(C.$('#mpDesc'), { html: C.toHtml(m.desc), label: 'Scope and needs', placeholder: 'What the milestone covers and what it needs', onSave: h => save('ms', m, { desc: h }) });
    C.$('#mpOwn').addEventListener('change', e => save('ms', m, { owner: e.target.value.trim() }));
    C.$('#mpWs').addEventListener('change', e => save('ms', m, { ws: e.target.value }));
    C.inline(C.$('#mpClT'), { html: C.toHtml(m.clientText), label: 'Client wording', place: 'client_message', placeholder: 'Plain wording a client can read', onSave: h => save('ms', m, { clientText: C.plain(h) }) });
    const flip = how => save('ms', m, { client: !m.client }, m.client ? `${m.name} hidden from the client` : `${m.name} shown to the client`, how);
    C.$('#mpCl').addEventListener('click', () => flip()); C.$('#pkEye').addEventListener('click', () => flip('with the eye'));
    /* archived, never deleted (FR-43c, #166): the work items that point at it keep their link and show it as "(archived)" */
    C.$('#pkMore').addEventListener('click', e => C.menu(e.currentTarget, [{ html: `${C.icon('archive', 's')} Archive milestone`, onPick: () => {
      const n = D.S.items.filter(x => x.code === m.code && x.ms === m.id && !x.archived).length, u = D.archive(m, true, D.who('in the peek'), 'ms'); if (!u) return; C.closePeek(); C.refresh();
      C.toast(`Archived ${m.name}. It's out of the lists and counts. ${n ? `${n} work item${n === 1 ? '' : 's'} still point${n === 1 ? 's' : ''} at it and show${n === 1 ? 's' : ''} it as archived.` : 'No work items point at it.'}`, u); } }], { align: 'right' }));
    C.$$('[data-open]', pk()).forEach(b => b.addEventListener('click', () => C.openItem(b.dataset.open, D.S.items.filter(x => x.ms === m.id && x.code === m.code && !x.archived).map(x => x.id))));
    wireTabs('ms', m);
  }

  /* ── an archived work item or milestone (FR-43c, #166): read-only, with one clear Restore; its history is all kept ── */
  function archHtml(kind, r) {
    const p = C.P(), item = kind === 'item', linked = item ? 0 : D.S.items.filter(x => x.code === r.code && x.ms === r.id && !x.archived).length;
    const facts = item ? [['Type', D.TYPES[r.type]], ['Status', r.status], ['Priority', r.priority], ['Owner', r.owner || 'No owner'], ['Due', D.fd(r.due) || 'No date'], ['Workstream', r.ws], ['Milestone', C.msName(r.ms) || 'None']]
      : [['State', D.msState(r)], ['Agreed', D.fd(r.agreed)], ['Forecast', D.fd(r.forecast || r.agreed)], ['Progress', r.progress == null ? 'not set' : r.progress + '%'], ['Owner', r.owner || 'Not set'], ['Workstream', r.ws], ['Linked work items', String(linked)]];
    const text = C.plain((item ? r.update : r.desc) || '');
    return `${topBar('')}
    <div class="pk-scroll"><div class="pk-inner pk-ro">
      <div class="pk-meta">${item ? `<span class="type ${r.type}">${r.type}</span>` : ''}${esc(r.id)} · ${esc(p.name)} <span class="tag arch">${C.icon('archive', 's')}Archived</span></div>
      <div class="pk-archnote"><p>Archived, so it is read-only. It is out of the lists, the counts and the published page; nothing in it was deleted.</p><button class="btn pri" id="pkRestore">Restore</button></div>
      <div class="pk-title" id="pkTitle">${esc(item ? r.title : r.name)}</div>
      <dl class="pk-rofacts">${facts.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
      ${text ? `<div class="pk-lab">${item ? 'Latest update' : 'Scope and needs'}</div><div class="pk-text">${esc(text)}</div>` : ''}
      ${tabsHtml()}
    </div></div><div class="pk-foot"><span class="pk-saved">Restore it to make a change</span></div>`;
  }
  function wireArch(kind, r) {
    C.$('#pkRestore').addEventListener('click', () => { const u = D.archive(r, false, D.who('in the peek'), kind); if (!u) return; C.refresh(); C.$('#pkClose')?.focus({ preventScroll: true });
      C.toast(`Restored ${kind === 'item' ? r.id : r.name}. It's back in the lists and counts.`, u); });
    wireTabs(kind, r);
  }

  /* ── Sneak peek: change the open item in words (plain code, no AI) ── */
  let snHist = [], snT = 0, snPlan = null;
  C.sneakIsOpen = () => !!C.$('#sneak.on');
  C.sneakClose = quiet => { const s = C.$('#sneak'); if (!s || !s.classList.contains('on')) return; s.classList.remove('on'); snPlan = null; if (!quiet) C.$('#pkSneak')?.focus(); };
  C.sneakOpen = () => {
    const s = C.$('#sneak'); if (!s || !cur) return; if ((cur.kind === 'item' ? findItem(cur.id) : findMs(cur.id))?.archived) return;   /* read-only while archived */
    s.innerHTML = `<div class="sn-marks" id="snMarks"></div><div id="snCard"></div><div class="sn-in">${C.icon('sparkle', 'sparkle')}<input id="snIn" placeholder="${cur.kind === 'item' ? 'For example: move to Friday, owner Jo, high priority' : 'For example: forecast 12-12-2026, at risk, progress 40%'}" aria-label="Change it in words" autocomplete="off"><kbd>Esc</kbd><span class="muted" style="font-size:12px">close</span></div>`;
    s.classList.add('on'); const i = C.$('#snIn'); i.focus();
    i.addEventListener('input', () => { clearTimeout(snT); snT = setTimeout(read, 160); });
    i.addEventListener('keydown', e => {
      if (e.key === 'ArrowUp' && !i.value && snHist.length) { e.preventDefault(); i.value = snHist[0]; read(); }
      if (e.key === 'Enter') { e.preventDefault(); clearTimeout(snT); read(); if (snPlan && snPlan.changes.length) apply(); }   // Enter or Shift+Enter: saved at once, Undo in the toast
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); C.sneakClose(); }
    });
  };
  function dateWord(w) {
    w = w.toLowerCase().trim(); let m;
    if (w === 'today') return D.TODAY; if (w === 'tomorrow') return D.addDays(D.TODAY, 1);
    if (w === 'next week') return D.addDays(D.TODAY, 7);
    if ((m = /^in (\d+) (day|week)s?$/.exec(w))) return D.addDays(D.TODAY, +m[1] * (m[2] === 'week' ? 7 : 1));
    const dn = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'].indexOf(w.replace(/^(next |this )/, ''));
    if (dn >= 0) { const d = new Date(D.TODAY + 'T00:00:00'); let add = (dn - d.getDay() + 7) % 7; if (add === 0 || /^next /.test(w)) add += 7; return D.addDays(D.TODAY, add); }
    if ((m = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(w))) return `${m[3]}-${D.pad(m[2])}-${D.pad(m[1])}`;
    if ((m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(w))) return w;
    return '';
  }
  const DATE_RE = '(today|tomorrow|next week|in \\d+ (?:days?|weeks?)|(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|\\d{1,2}[-/.]\\d{1,2}[-/.]\\d{4}|\\d{4}-\\d{2}-\\d{2})';
  function parse(text, kind, rec) {
    const t = text.trim(), ch = {}, marks = [], probs = []; let m;
    const hit = (re, fn) => { const r = re.exec(t); if (r) { marks.push(r[0].trim()); fn(r); } };
    if (kind === 'item') {
      hit(new RegExp(`\\b(?:due|move(?: it)?(?: due)?(?: to)?|by|on)\\s+${DATE_RE}`, 'i'), r => { const d = dateWord(r[1]); d ? ch.due = d : probs.push(`I can't read "${r[1]}" as a date.`); });
      hit(/\b(?:owner|assign(?:ed)?(?: it)? to|give (?:it )?to)\s+([A-Za-z][\w'-]+(?:\s+[A-Za-z][\w'-]+)?)/i, r => {
        /* a second word belongs to the name only when it is written with a capital (so "owner Jo high priority" is Jo) */
        const w = r[1].split(/\s+/); if (w[1] && !/^[A-Z]/.test(w[1])) { r[1] = w[0]; marks[marks.length - 1] = r[0].split(/\s+/).slice(0, -1).join(' '); }
        const q = r[1].toLowerCase(), ps = C.people().filter(n => n.toLowerCase() === q || n.toLowerCase().startsWith(q + ' ') || n.toLowerCase().split(' ')[0] === q);
        if (ps.length === 1) ch.owner = ps[0]; else if (ps.length > 1) probs.push(`"${r[1]}" could be ${ps.join(' or ')}: type the full name.`); else ch.owner = r[1].replace(/\b\w/g, c => c.toUpperCase());
      });
      hit(/\b(done|completed?|closed?|reopen(?:ed)?|delayed|cancell?ed|made|agreed|withdrawn|pending)\b/i, r => {
        const w = r[1].toLowerCase(), map = { A: { done: 'Closed', complete: 'Closed', completed: 'Closed', close: 'Closed', closed: 'Closed', reopen: 'Open', reopened: 'Open', delayed: 'Delayed', cancelled: 'Cancelled', canceled: 'Cancelled' },
          R: { close: 'Closed', closed: 'Closed', done: 'Closed', reopen: 'Open', reopened: 'Open', cancelled: 'Cancelled', canceled: 'Cancelled' }, D: { made: 'Made', agreed: 'Made', withdrawn: 'Withdrawn', pending: 'Pending', done: 'Made' } };
        const s = (map[rec.type === 'I' ? 'R' : rec.type] || {})[w]; s ? ch.status = s : probs.push(`A ${D.TYPES[rec.type].toLowerCase()} can't be "${r[1]}".`);
      });
      hit(/\b(urgent|high|medium|low)(?:\s+priority)?\b/i, r => { ch.priority = r[1][0].toUpperCase() + r[1].slice(1).toLowerCase(); });
      if (rec.type === 'R' || rec.type === 'I') hit(/\b(red|amber|green)\b/i, r => { Object.assign(ch, C.ragSet(rec, r[1][0].toUpperCase())); });
      hit(/\b(show (?:it )?to|hide (?:it )?from) (?:the )?client\b/i, r => { ch.client = /^show/i.test(r[1]); });
      hit(/\buse case\s+([\d.]+[A-Z]?)\b/i, r => { const u = D.S.usecases.find(x => x.code === rec.code && (x.id === r[1] || (x.ref || '').includes(r[1]))); u ? ch.uc = u.id : probs.push(`No use case ${r[1]} in this project.`); });
    } else {
      hit(new RegExp(`\\b(?:forecast|move(?: it)?(?: to)?|expected)\\s+${DATE_RE}`, 'i'), r => { const d = dateWord(r[1]); d ? Object.assign(ch, { forecast: d, achievedOn: '' }) : probs.push(`I can't read "${r[1]}" as a date.`); });
      hit(/\b(achieved|done|met)\b/i, () => Object.assign(ch, { achievedOn: D.TODAY, progress: 100, manual: '' }));
      hit(/\bat risk\b/i, () => { ch.manual = 'At risk'; });
      hit(/\bon track\b/i, () => { ch.manual = ''; });
      hit(/\bprogress\s+(\d{1,3})\s*%?/i, r => { ch.progress = Math.min(100, +r[1]); });
      hit(/\b(?:owner|assign(?:ed)?(?: it)? to)\s+([A-Za-z][\w'-]+(?:\s+[A-Z][\w'-]+)?)/i, r => { const q = r[1].toLowerCase(), ps = C.people().filter(n => n.toLowerCase().split(' ')[0] === q || n.toLowerCase() === q); ch.owner = ps.length === 1 ? ps[0] : r[1]; });
      hit(/\b(show (?:it )?to|hide (?:it )?from) (?:the )?client\b/i, r => { ch.client = /^show/i.test(r[1]); });
    }
    if ((m = /\b(?:rename(?: it)? to|call it)\s+["“]?(.+?)["”]?$/i.exec(t))) { marks.push(m[0]); ch[kind === 'item' ? 'title' : 'name'] = m[1]; }
    if (kind === 'item' && (m = /\b(?:update|note)\s*[:\-]\s*(.+)$/i.exec(t))) { marks.push(m[0]); ch.update = m[1]; }
    const changes = Object.entries(ch).filter(([f, v]) => JSON.stringify(rec[f]) !== JSON.stringify(v)).map(([f, v]) => ({ f, v, from: show(f, rec[f]), to: show(f, v) }));
    return { changes, marks, probs };
  }
  function read() {
    const i = C.$('#snIn'); if (!i || !cur) return;
    const rec = cur.kind === 'item' ? findItem(cur.id) : findMs(cur.id); if (!rec) return;
    snPlan = i.value.trim() ? parse(i.value, cur.kind, rec) : null;
    C.$('#snMarks').innerHTML = snPlan ? snPlan.marks.map(m => `<span>${esc(m)}</span>`).join('') : '';
    const lab = cur.kind === 'item' ? rec.id : rec.name;
    C.$('#snCard').innerHTML = !snPlan ? '' : (snPlan.probs.map(p => `<div class="sn-prob">${esc(p)}</div>`).join('') + (snPlan.changes.length
      ? `<div class="sn-card"><div class="h">${C.icon('sparkle', 's sparkle')}Change ${esc(lab)}<small>Understood in plain code</small></div>${snPlan.changes.map(c => `<div class="sn-ch"><span class="muted">${C.esc(FN[c.f] || c.f).replace(/^./, s => s.toUpperCase())}</span><span><s>${esc(c.from)}</s> → <b>${esc(c.to)}</b></span></div>`).join('')}
        <div class="acts"><span>You can undo it.</span><span class="sp"></span><button class="btn sm" id="snNo">Not now</button><button class="btn sm pri" id="snYes">Make the change ⏎</button></div></div>`
      : snPlan.probs.length ? '' : '<div class="sn-prob">Nothing to change yet. Try a date, an owner, a status or a priority.</div>'));
    C.$('#snYes')?.addEventListener('click', apply);
    C.$('#snNo')?.addEventListener('click', () => C.sneakClose());
  }
  function apply() {
    const rec = cur.kind === 'item' ? findItem(cur.id) : findMs(cur.id); if (!rec || !snPlan) return;
    const text = C.$('#snIn').value.trim(); snHist = [text, ...snHist.filter(h => h !== text)].slice(0, 10);
    const u = D.change(cur.kind, rec, Object.fromEntries(snPlan.changes.map(c => [c.f, c.v])), D.who('in words'));
    const fields = snPlan.changes.map(c => c.f);
    C.sneakClose(true); C.refresh();
    if (u) C.toast(`${cur.kind === 'item' ? rec.id : rec.name} changed`, u);
    /* the changed fields flash for 1.6 seconds, as in creaite */
    const SEL = { status: '[data-prop=status]', rag: '[data-prop=status]', priority: '[data-prop=priority]', owner: '[data-prop=owner]', due: '[data-prop=due]', title: '#pkTitle', name: '#pkTitle', update: '#pkUpd',
      forecast: '.mp-dates', agreed: '.mp-dates', achievedOn: '.states', manual: '.states', progress: '.prog', client: '#pkEye' };
    fields.forEach(f => { const el = SEL[f] && C.$(SEL[f], pk()); if (el) { el.classList.add('flashf'); setTimeout(() => el.classList.remove('flashf'), 1600); } });
  }
})();
