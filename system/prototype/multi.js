/* clark prototype: working with several work items at once, the arrow keys, and the right-click menu, on Work items (the table and the board).
   Drawn from the product's own words where it is built (the bulk bar in src/clark/page/src/edit/Bulk.jsx and bulkLogic.js, #195 and #196; Hand over, #199;
   the arrow keys, #194; the right-click menu, #97) and from each board item's Done-when where it is not.
   - Select several (#195): click, Cmd or Ctrl+click, Shift+click, Shift+Up and Down, Space, Cmd or Ctrl+A, a tick box on each group heading, "Select all N matching".
     The selection lives in memory only. A plain click still opens the peek until something is selected; then it selects, and a double click opens the peek.
   - The bulk bar (#196): "N selected" with Close, Reopen, Status, Owner, Due date, Priority, Workstream, Milestone (decisions: Made by only), the right-click menu on a
     selection, the keys O S P T C and V, one confirm above 25, a change of one cell of a selected row asks first, one Undo for the lot.
   - Hand over (#199): pick mode with a tick box on each open item, All, "N of M selected", Hand over to, Hand over, Cancel; one Undo.
   - Arrow keys (#194, #246): one Tab stop for the table, Up, Down, Home and End on rows, all four arrows on cards, Right and Left open and close the peek from a row,
     and the peek follows the cursor. Where the arrow keys go while the peek is open: they step to the previous and next item while the keyboard is in the peek's top bar
     (where it lands when the peek opens), and the row cursor follows; anywhere else in the peek an arrow scrolls as usual. Esc closes the peek and the keyboard goes back to
     the row of the item the peek last showed.
   - The right-click menu (#97): on a row or a card, one item: Draft email to the owner, Open the peek, Change status, Move due date, Change owner, Show to or Hide from the
     client, Copy link, Copy ID, Duplicate, Archive. On a selection of two or more: "N items" with the bulk actions and Copy IDs. Shift+F10 and the Menu key open it too.
   Every change here is one step with Undo in the toast, through ClarkDB (one history line for each item and field). Nothing here deletes. */
(function () {
  'use strict';
  const C = window.C, D = C.D, UI = C.UI, esc = C.esc, $ = C.$, $$ = C.$$;
  const api = C.multi = { confirmAbove: 25 };
  const M = api.M = { ids: [], anchor: '', cursor: '', all: false, note: '', code: '' };   // the selection
  const H = api.H = { on: false, ticks: [], to: '' };                                         // Hand over's pick mode

  const WHY = {
    kinds: 'These items are of different kinds',
    decision: 'A decision takes only who makes it',
    decided: 'It has been made or withdrawn, so who made it stays as recorded. Record a new decision instead.',
    closed: 'It is closed, so it stays with its owner. Reopen it first.',
    blank: "A name can't be blank. Type a name, or TBC if no one is known yet.",
  };
  const NOT_OFFERED = 'This item cannot go in an email: it is hidden from the report, marked sensitive or restricted, or no longer open.';
  const NO_OWNER = 'This item has no owner yet, so there is no one to write to.';

  const item = id => D.S.items.find(x => x.id === id);
  const idOf = h => h.dataset.id || h.dataset.card;
  const q = s => CSS.escape(s);
  const ROWS = '#wlist .group tr[data-id]', HOMES = '#wlist .group tr[data-id], #wlist [data-card]';
  const homeOf = id => $(`#wlist .group tr[data-id="${q(id)}"], #wlist [data-card="${q(id)}"]`);
  const board = () => !!$('#wlist .board');
  const drawn = () => board() ? $$('#wlist .bcol:not(.shut) [data-card]').map(idOf) : $$('#wlist .group.open tr[data-id]').map(idOf);   // in the order drawn; a collapsed group's are not drawn
  const inWork = () => UI.view === 'work' && !!$('#wlist');
  const words = n => `${n} item${n === 1 ? '' : 's'}`;
  const countWords = n => n === 0 ? 'Nothing selected' : `${n} selected`;
  const tableOf = x => x.type === 'A' ? 'actions' : x.type === 'D' ? 'decisions' : 'raid';
  const keysOn = () => typeof C.singleKeys === 'function' ? !!C.singleKeys() : C.store.get('singleKeys', true) !== false;   // the Single-key shortcuts switch (#193), on unless turned off
  const busy = () => C.popOpen() || !!document.querySelector('dialog[open]') || (C.askIsOpen && C.askIsOpen()) || (C.edIsOpen && C.edIsOpen());

  /* a polite message for a screen reader: "N selected"; the trailing space that comes and goes makes the same words twice a change */
  let flip = false;
  function say(t) { let l = $('#mLive'); if (!l) { l = document.createElement('div'); l.id = 'mLive'; l.className = 'sr'; l.setAttribute('role', 'status'); l.setAttribute('aria-live', 'polite'); document.body.appendChild(l); } flip = !flip; l.textContent = flip ? t : t + ' '; }

  /* ───────────── #196: what a bar, a menu and a key offer, as plain functions ───────────── */
  const CONTROLS = [
    { id: 'close', label: 'Close', tables: ['actions', 'raid'] },
    { id: 'reopen', label: 'Reopen', tables: ['actions', 'raid'] },
    { id: 'status', label: 'Status', tables: ['actions', 'raid'], menu: true },
    { id: 'owner', label: 'Owner', tables: ['actions', 'raid'], menu: true },
    { id: 'due', label: 'Due date', tables: ['actions', 'raid'], menu: true },
    { id: 'priority', label: 'Priority', tables: ['actions', 'raid'], menu: true },   // the prototype's risks and issues carry a priority, not an impact and a likelihood
    { id: 'workstream', label: 'Workstream', tables: ['actions', 'raid'], menu: true },
    { id: 'milestone', label: 'Milestone', tables: ['actions', 'raid'], menu: true },
    { id: 'made_by', label: 'Made by', tables: ['decisions'], menu: true },
  ];
  const summary = xs => { const t = new Set(xs.map(tableOf)); return { n: xs.length, table: t.size === 1 ? [...t][0] : null, ids: xs.map(x => x.id) }; };
  /* the controls for a selection: those that fit its kind; mixed kinds: every one is off, with the reason as text */
  function controls(sum) {
    const shown = sum.table ? CONTROLS.filter(c => c.tables.includes(sum.table)) : CONTROLS.filter(c => c.id !== 'made_by');
    return shown.map(c => ({ id: c.id, label: c.label, menu: !!c.menu, on: !!sum.table, why: sum.table ? '' : WHY.kinds }));
  }
  function keyWhy(ctl, sum) {
    if (!sum.table) return WHY.kinds + '.';
    const c = controls(sum).find(z => z.id === ctl);
    if (c) return c.on ? '' : c.why + '.';
    return sum.table === 'decisions' ? WHY.decision + '.' : "That can't be changed here.";
  }
  /* what one item gets from a control: {ch} or {why} */
  function planFor(ctl, value, x) {
    if (ctl === 'made_by' && ['Made', 'Withdrawn'].includes(x.status)) return { why: WHY.decided };
    const ch = ctl === 'close' ? { status: 'Closed' } : ctl === 'reopen' ? { status: D.STATUSES[x.type][0] } : ctl === 'status' ? { status: value }
      : ctl === 'owner' || ctl === 'made_by' ? { owner: value } : ctl === 'due' ? { due: value } : ctl === 'priority' ? { priority: value } : ctl === 'workstream' ? { ws: value } : { ms: value };
    return { ch };
  }
  const backWords = n => `Undone: ${words(n)} ${n === 1 ? 'is' : 'are'} back as ${n === 1 ? 'it was' : 'they were'}.`;
  function bulkWords(changed, same, left) {
    const out = [changed ? `Changed ${words(changed)}.` : 'Nothing changed: they already have that.'];
    if (same && changed) out.push(`${same} already had that.`);
    left.slice(0, 3).forEach(e => out.push(`Left out ${e.id}: ${e.why}`));
    if (left.length > 3) out.push(`${left.length - 3} more were left out.`);
    return out.join(' ');
  }

  /* One change to several items, one step: each item is checked first; one that can't take it is left out and named; nothing is saved when none can.
     plan(x) → {ch} | {why}. o: how (the history's "where"), back (words after Undo), done (runs when something changed), from (the id the keyboard goes back to). */
  function apply(ids, plan, o = {}) {
    const left = [], same = [], go = [];
    ids.map(item).filter(Boolean).forEach(x => { const r = plan(x);
      if (r.why) left.push({ id: x.id, why: r.why });
      else if (Object.keys(r.ch).every(k => (x[k] ?? '') === (r.ch[k] ?? ''))) same.push(x.id);
      else go.push([x, r.ch]); });
    if (!go.length) {
      const w = left.length && !same.length ? (new Set(left.map(l => l.why)).size === 1 ? left[0].why : 'Nothing changed: none of these items can take that change.') : 'Nothing changed: they already have that.';
      C.toast(w); say(w); return false;
    }
    const u = D.batch(go.map(([x, ch]) => () => D.change('item', x, ch, D.who(o.how || 'in the table'))));
    const w = bulkWords(go.length, same.length, left);
    if (o.done) o.done(); else clear(true);
    C.refresh(); C.toast(w, u ? () => { u(); setTimeout(() => { const b = (o.back || backWords)(go.length); C.toast(b); say(b); }, 30); } : null); say(w);
    focusSoon(o.from || M.cursor || go[0][0].id);
    return true;
  }
  /* the question above 25 items, and before a cell of a selected row changes the whole selection; Change or Cancel */
  function ask(question, yes, yesWord = 'Change') {
    C.dialog(`<div class="dlg-h"><h2 id="bkQ">${esc(question)}</h2></div><div class="dlg-f"><button type="button" class="btn quiet" data-close>Cancel</button><button type="button" class="btn pri" id="bkYes">${esc(yesWord)}</button></div>`, d => {
      d.setAttribute('role', 'alertdialog'); d.setAttribute('aria-labelledby', 'bkQ'); d.addEventListener('close', () => { d.removeAttribute('role'); d.removeAttribute('aria-labelledby'); }, { once: true });
      const b = $('#bkYes', d); b.focus(); b.addEventListener('click', () => { d.close(); yes(); }); });
  }
  function focusSoon(id) { setTimeout(() => { const h = id && homeOf(id) || $(HOMES); if (h && !C.popOpen() && !document.querySelector('dialog[open]')) h.focus({ preventScroll: true }); }, 40); }

  /* ───────────── the pickers (the cells' own: the same lists) ───────────── */
  const quickDates = () => [['Today', D.TODAY], ['Tomorrow', D.addDays(D.TODAY, 1)], ['Friday', D.friday() === D.TODAY ? D.addDays(D.TODAY, 7) : D.friday()], ['Next week', D.addDays(D.TODAY, 7)]];
  function picker(ctl, anchor, table, n, onPick, onClose) {
    const c = CONTROLS.find(z => z.id === ctl), label = `${c.label} of ${words(n)}`;
    anchor.setAttribute('aria-label', label);
    const menu = list => C.menu(anchor, list.map(([value, text]) => ({ label: text, onPick: () => onPick(value) })), { onClose });
    if (ctl === 'status') return menu(D.STATUSES[table === 'raid' ? 'R' : 'A'].map(s => [s, s]));
    if (ctl === 'priority') return menu(D.PRIORITIES.map(s => [s, s]));
    if (ctl === 'workstream') return menu(C.P().ws.map(w => [w, w]));
    if (ctl === 'milestone') return menu([...C.mss().map(m => [m.id, m.name]), ['', 'No milestone']]);
    if (ctl === 'due') return C.calPick(anchor, '', v => onPick(v), { quick: [...quickDates(), ['No date', '']], onClose });
    /* owner and made by: a name field over the first eight people, as the owner cell's picker */
    const go = name => { const v = String(name || '').trim().split(/\s+/).filter(Boolean).join(' '); if (!v) { C.toast(WHY.blank); say(WHY.blank); return; } onPick(v); };
    return C.menu(anchor, C.people().slice(0, 8).map(nm => ({ html: `<span class="av">${C.initials(nm)}</span>${esc(nm)}`, onPick: () => go(nm) })), { onClose,
      head: `<div style="padding:6px" role="presentation"><input class="field" id="ownIn" placeholder="Type a name" aria-label="${esc(c.id === 'made_by' ? 'Made by' : 'Owner')}" list="ownList"><datalist id="ownList">${C.people().map(nm => `<option value="${esc(nm)}">`).join('')}</datalist></div>`,
      wire: el => { const i = $('#ownIn', el); i.focus(); i.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); const v = i.value; C.closePop(); go(v); } }); } });
  }
  /* an anchor for a picker or a menu at a point (a right click, or under a row): it is removed when what opened at it closes, and the keyboard goes back to `from` */
  function anchorAt(x, y, label, from) {
    $$('.ctx-at').forEach(a => a.remove());
    const a = document.createElement('span'); a.className = 'ctx-at'; a.tabIndex = -1; a.setAttribute('aria-label', label);
    a.style.cssText = `left:${Math.round(x)}px;top:${Math.round(y)}px`; document.body.appendChild(a);
    return { a, onClose: () => { a.remove(); const f = from && from.isConnected ? from : null; if (f) f.focus({ preventScroll: true }); } };
  }
  const below = h => { const r = h.getBoundingClientRect(); return [r.left + 24, r.bottom]; };

  /* open a control for `ids`: Close and Reopen act at once, the others open their picker at the anchor (an element, or a point {x, y}) */
  function openControl(ctl, ids, at, from, o = {}) {
    const xs = ids.map(item).filter(Boolean), sum = summary(xs), why = keyWhy(ctl, sum);
    if (why) { C.toast(why); say(why); return; }
    const c = CONTROLS.find(z => z.id === ctl);
    if (!c.menu) return runControl(ctl, sum.ids, null, from, o);
    let anchor = at, onClose = () => { const f = from && homeOf(from); if (f && !document.activeElement.closest('#wlist')) f.focus({ preventScroll: true }); };
    if (!at.nodeType) { const z = anchorAt(at.x, at.y, '', homeOf(from)); anchor = z.a; onClose = z.onClose; }
    picker(ctl, anchor, sum.table, sum.n, v => runControl(ctl, sum.ids, v, from, o), onClose);
  }
  function runControl(ctl, ids, value, from, o = {}) {
    const go = () => apply(ids, x => planFor(ctl, value, x), { from, how: o.how, done: o.done });
    if (!o.asked && ids.length > api.confirmAbove) ask(`Change ${ids.length} items?`, go); else go();
  }

  /* ───────────── #195: the selection ───────────── */
  function setSel(ids, o = {}) {
    const was = M.ids.join('|');
    M.ids = ids; if ('anchor' in o) M.anchor = o.anchor; if ('cursor' in o) M.cursor = o.cursor; M.all = !!o.all;
    if (!o.keep) M.note = '';
    if (ids.length >= 2 && UI.peek && C.peekKind() === 'item') C.closePeek();                  // two or more: a peek that shows one record closes
    if (M.ids.join('|') !== was) say(o.words || countWords(ids.length));
    paint();
  }
  function clear(quiet) { if (!M.ids.length && !M.note) return; M.ids = []; M.anchor = ''; M.all = false; M.note = ''; if (!quiet) say(countWords(0)); paint(); }
  function reset() { M.ids = []; M.anchor = ''; M.cursor = ''; M.all = false; M.note = ''; H.on = false; H.ticks = []; H.to = ''; M.code = UI.code; }
  function pick(id, how) {
    const order = drawn(), cur = M.ids.slice(), from = M.anchor && order.includes(M.anchor) ? M.anchor : id;
    if (how.range) { const a = order.indexOf(from), b = order.indexOf(id), part = order.slice(Math.min(a, b), Math.max(a, b) + 1);
      setSel(how.add ? [...new Set([...cur, ...part])] : part, { anchor: from, cursor: id }); }
    else if (how.add) setSel(cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id], { anchor: id, cursor: id });
    else setSel([id], { anchor: id, cursor: id });
  }
  function extend(step, id) {
    const order = drawn(), at = order.indexOf(M.ids.length && order.includes(M.cursor) ? M.cursor : id), from = order.includes(M.anchor) && M.ids.length ? M.anchor : order[at];
    const to = Math.max(0, Math.min(order.length - 1, at + step)), a = order.indexOf(from);
    setSel(order.slice(Math.min(a, to), Math.max(a, to) + 1), { anchor: from, cursor: order[to] });
    return order[to];
  }
  const offered = id => { const x = item(id); return !!x && C.isOpen(x); };
  function toggle(id) {
    if (H.on) return tickToggle(id);
    const cur = M.ids.slice(); setSel(cur.includes(id) ? cur.filter(x => x !== id) : [...cur, id], { anchor: id, cursor: id });
  }
  const groupIds = g => $$('tr[data-id]', g).map(idOf);
  function tickGroup(g) {
    const ids = groupIds(g).filter(id => !H.on || offered(id)), list = H.on ? H.ticks : M.ids, all = ids.length && ids.every(i => list.includes(i));
    const next = all ? list.filter(i => !ids.includes(i)) : [...new Set([...list, ...ids])];
    if (H.on) setTicks(next); else setSel(next, { anchor: ids[0], cursor: ids[0] });
  }
  /* after a redraw, or a group opened or shut: a row no longer drawn leaves the selection (all matching keeps those the filters still show), and the line says how many */
  function sync() {
    if (!inWork()) return;
    if (H.on) { const ok = new Set(C.workMatching().filter(offered)), keep = H.ticks.filter(i => ok.has(i)); if (keep.length !== H.ticks.length) H.ticks = keep; return; }
    if (!M.ids.length) return;
    const ok = new Set(M.all ? C.workMatching() : drawn()), keep = M.ids.filter(i => ok.has(i)), left = M.ids.length - keep.length;
    if (!left) return;
    M.ids = keep; M.note = `${left} left the selection`; if (!keep.length) M.all = false; say(`${M.note}. ${countWords(keep.length)}`);
  }

  /* ───────────── what is drawn: marks on rows and cards, group ticks, the bar ───────────── */
  function mark(host, want, picked, box) {
    if (!host) return; let t = host.querySelector(':scope > .mtick');
    if (!want) { if (t) t.remove(); return; }
    if (!t) { t = document.createElement('span'); t.className = 'mtick'; t.setAttribute('aria-hidden', 'true'); host.prepend(t); }
    t.classList.toggle('box', box); t.classList.toggle('on', picked); t.innerHTML = picked ? C.icon('check', 's') : '';
  }
  function cursorOnly() {
    const order = drawn(), stop = order.includes(M.cursor) ? M.cursor : order[0] || '';
    $$(ROWS).forEach(r => { const on = r.dataset.id === stop; r.classList.toggle('cur', on); r.tabIndex = on ? 0 : -1; });   // the table is one Tab stop: the row last used
    $$('#wlist [data-card]').forEach(c => c.classList.toggle('cur', c.dataset.card === stop));
  }
  function paint() {
    if (!inWork()) return;
    const on = M.ids.length > 0 || H.on, sel = H.on ? H.ticks : M.ids;
    cursorOnly();
    $$('#wlist .group table.items').forEach(t => { if (on) { t.setAttribute('role', 'grid'); t.setAttribute('aria-multiselectable', 'true'); t.setAttribute('aria-label', 'Work items'); } else { t.removeAttribute('role'); t.removeAttribute('aria-multiselectable'); t.removeAttribute('aria-label'); } });
    $$(HOMES).forEach(h => {
      const id = idOf(h), picked = sel.includes(id), can = !H.on || offered(id), card = h.matches('[data-card]');
      h.classList.toggle('picked', picked);
      if (on && can) h.setAttribute(card ? 'aria-pressed' : 'aria-selected', picked); else h.removeAttribute(card ? 'aria-pressed' : 'aria-selected');
      mark(card ? $('.bc-top', h) : $('.tcell', h), H.on ? can : picked, picked, H.on);
    });
    $$('#wlist .group').forEach(g => {
      let b = $(':scope > .gtick-hit', g);
      if (!b) { b = document.createElement('label'); b.className = 'gtick-hit'; b.innerHTML = '<input type="checkbox" class="gtick">'; g.prepend(b);
        b.addEventListener('click', e => e.stopPropagation()); $('input', b).addEventListener('change', () => tickGroup(g)); }
      const i = $('input', b), ids = groupIds(g).filter(id => !H.on || offered(id)), n = ids.filter(x => sel.includes(x)).length, shut = !g.classList.contains('open');
      const name = ($('.ghead .t', g).firstChild || {}).textContent || 'group';
      i.checked = !!ids.length && n === ids.length; i.indeterminate = n > 0 && n < ids.length; i.disabled = shut || !ids.length;
      i.setAttribute('aria-label', shut ? `Select ${name}. Open the group first` : `Select ${name}, ${words(ids.length)}`); i.title = shut ? 'Open the group to select its items' : '';
      i.dataset.gtick = g.dataset.ws;
    });
    paintBar(); paintHandBtn();
  }
  function paintBar() {
    let b = $('#mbar');
    if (!b) { const l = $('#wlist'); if (!l) return; b = document.createElement('div'); b.id = 'mbar'; l.prepend(b); b.addEventListener('click', barClick); }
    if (H.on) return handBar(b);
    const had = document.activeElement && b.contains(document.activeElement) ? document.activeElement : null, keep = had ? (had.dataset.bulk ? `[data-bulk="${had.dataset.bulk}"]` : had.id ? '#' + had.id : '') : null;
    const wasHand = b.dataset.mode === 'hand'; b.dataset.mode = '';
    const n = M.ids.length, xs = M.ids.map(item).filter(Boolean), sum = summary(xs), list = controls(sum), m = C.workMatching().length;
    const why = list.length && list.every(c => !c.on) ? list[0].why : '';
    b.innerHTML = (n >= 2 ? `<div class="selbar" role="region" aria-label="Selection" id="selBar"><span class="sb-n num" id="selCount">${countWords(n)}</span>
      ${n < m ? `<button type="button" class="link" id="selAll">Select all ${m} matching</button>` : ''}
      <span class="sb-acts" role="group" aria-label="Change ${words(n)}">${list.map(c => `<button type="button" class="btn sm sb-a" data-bulk="${c.id}"${c.on ? '' : ` aria-disabled="true" title="${esc(c.why)}" aria-describedby="selWhy"`}${c.menu ? ' aria-haspopup="menu"' : ''}>${esc(c.label)}</button>`).join('')}</span>
      ${why ? `<span class="sb-why muted" id="selWhy">${esc(why)}</span>` : ''}
      <button type="button" class="ib sb-x" id="selClear" aria-label="Clear the selection" title="Clear the selection (Esc)">${C.icon('x')}</button></div>` : '')
      + (M.note ? `<p class="muted sel-note" id="selNote">${esc(M.note)}</p>` : '');
    if (keep !== null && !wasHand) { const f = keep && $(keep, b); if (f) f.focus({ preventScroll: true }); else focusSoon(M.cursor); }
  }
  function barClick(e) {
    const t = e.target.closest('button'); if (!t) return;
    if (t.id === 'selAll') { const all = C.workMatching(); setSel(all, { all: true, anchor: M.anchor, cursor: M.cursor, words: countWords(all.length) }); }
    else if (t.id === 'selClear') { clear(); focusSoon(M.cursor); }
    else if (t.dataset.bulk) {
      const sum = summary(M.ids.map(item).filter(Boolean)), c = controls(sum).find(z => z.id === t.dataset.bulk);
      if (!c || !c.on) { const w = `${c ? c.why : WHY.kinds}.`; C.toast(w); say(w); return; }
      openControl(c.id, M.ids.slice(), t, M.cursor);
    }
    else if (t.id === 'handAll') setTicks(offeredIds());
    else if (t.id === 'handNone') setTicks([]);
    else if (t.id === 'handGo') handGo();
    else if (t.id === 'handCancel') handStop();
  }

  /* ───────────── #199: Hand over ───────────── */
  const clean = s => String(s == null ? '' : s).trim().split(/\s+/).filter(Boolean).join(' ');
  const offeredIds = () => C.workMatching().filter(offered);
  const handWhy = (n, to) => n === 0 ? 'Tick at least one item.' : !clean(to) ? 'Say who to hand over to.' : '';
  function setTicks(list) { H.ticks = list; say(`${list.length} of ${offeredIds().length} selected`); paint(); }
  function tickToggle(id) { if (!offered(id)) { say('A closed item is not offered: it stays with its owner.'); return; } setTicks(H.ticks.includes(id) ? H.ticks.filter(x => x !== id) : [...H.ticks, id]); }
  function handStart() {
    if (H.on || !inWork()) return;
    M.ids = []; M.note = ''; M.all = false; H.on = true; H.ticks = []; H.to = '';
    say('Hand over: tick the items to give to someone else.'); paint(); const i = $('#handTo'); if (i) i.focus();
  }
  function handStop(quiet) { if (!H.on) return; H.on = false; H.ticks = []; paint(); if (!quiet) { const h = $('#handBtn'); if (h) h.focus({ preventScroll: true }); else focusSoon(M.cursor); } }
  function handBar(b) {
    if (b.dataset.mode !== 'hand') {
      b.dataset.mode = 'hand';
      b.innerHTML = `<div class="selbar handbar" role="region" aria-label="Hand over" id="handBar"><span class="sb-n num" id="handCount"></span><button type="button" class="link" id="handAll">All</button><button type="button" class="link" id="handNone">None</button>
        <label class="hb-to">Hand over to <input class="field" id="handTo" list="handPeople" autocomplete="off" maxlength="200" placeholder="Choose or type a name"></label><datalist id="handPeople">${C.people().map(nm => `<option value="${esc(nm)}">`).join('')}</datalist>
        <button type="button" class="btn pri sm" id="handGo">Hand over</button><button type="button" class="btn sm" id="handCancel">Cancel</button></div><p class="muted sb-why" id="handWhy"></p>`;
      const i = $('#handTo', b); i.value = H.to; i.addEventListener('input', () => { H.to = i.value; paintBar(); });
      i.addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); handGo(); } });
    }
    const n = H.ticks.length, why = handWhy(n, H.to), go = $('#handGo', b);
    $('#handCount', b).textContent = `${n} of ${offeredIds().length} selected`; $('#handNone', b).hidden = !n;
    if (why) go.setAttribute('aria-disabled', 'true'); else go.removeAttribute('aria-disabled');
    go.setAttribute('aria-describedby', 'handWhy'); $('#handWhy', b).textContent = why;
  }
  function handGo() {
    const ids = H.ticks.slice(), to = clean(H.to), why = handWhy(ids.length, H.to);
    if (why) { C.toast(why); say(why); return; }
    const run = () => apply(ids, x => C.isOpen(x) ? { ch: { owner: to } } : { why: WHY.closed }, { how: 'in the table', done: () => handStop(true), from: ids[0],
      back: n => `Undone: ${words(n)} ${n === 1 ? 'is' : 'are'} back with ${n === 1 ? 'its' : 'their'} owner.` });
    if (ids.length > api.confirmAbove) ask(`Hand over ${ids.length} items to ${to}?`, run, 'Hand over'); else run();
  }
  function paintHandBtn() {
    const acts = $('#main .hacts'); if (!acts) return;
    const b = $('#handBtn'), want = !H.on && !!C.workOwnerLine && C.workOwnerLine();
    if (want && !b) { const n = document.createElement('button'); n.type = 'button'; n.className = 'btn'; n.id = 'handBtn'; n.textContent = 'Hand over'; n.addEventListener('click', handStart); acts.insertBefore(n, $('#newBtn')); }
    if (!want && b) b.remove();
  }
  api.handOverStart = handStart; api.clear = clear;

  /* ───────────── a change of one cell of a selected row changes every selected row, and says so first ───────────── */
  api.cell = (b, x) => {
    if (H.on || M.ids.length < 2 || !M.ids.includes(x.id)) return false;
    const field = b.dataset.prop, rows = M.ids.map(item).filter(Boolean), sum = summary(rows), ctl = field === 'owner' && sum.table === 'decisions' ? 'made_by' : field;
    const name = { owner: sum.table === 'decisions' ? 'decider' : 'owner', due: 'due date', priority: 'priority', status: 'status' }[field] || field;
    const tail = ' Clear the selection to change only this one.';
    if (!sum.table) { const w = `${WHY.kinds}, so the ${name} can't be changed for all of them.${tail}`; C.toast(w); say(w); return true; }
    if (!controls(sum).find(c => c.id === ctl)) { const w = `${sum.table === 'decisions' ? WHY.decision : "That can't be changed for all of them"}.${tail}`; C.toast(w); say(w); return true; }
    const ids = M.ids.slice();
    picker(ctl, b, sum.table, sum.n, v => ask(`Change the ${name} of all ${sum.n} selected items?`, () => runControl(ctl, ids, v, x.id, { asked: true })), () => { if (!document.activeElement || document.activeElement === document.body) focusSoon(x.id); });
    return true;
  };

  /* ───────────── clicks and keys on a row or a card (views.js hands them here first; true = used) ───────────── */
  api.click = (e, id) => {
    const h = e.currentTarget; if (h.classList.contains('arch')) return false;
    if (H.on) { if (!String(getSelection()).length) tickToggle(id); return true; }          // pick mode: a click only ticks
    const add = e.metaKey || e.ctrlKey, range = e.shiftKey;
    if (!add && !range && !M.ids.length) return false;                                     // nothing selected: a click opens the peek, as before
    if (!add && !range && String(getSelection()).length) return true;                       // the person is selecting text
    pick(id, { add, range });
    if (UI.peek && C.peekKind() === 'item' && M.ids.length === 1 && M.ids[0] === id && UI.peek !== id) C.openItem(id, drawn());   // one picked: the peek follows
    return true;
  };
  const eye = x => { const u = D.change('item', x, { client: !x.client }, D.who('with the eye')); C.refresh(); C.toast(`${x.id} ${x.client ? 'shown to' : 'hidden from'} the client`, u); focusSoon(x.id); };
  /* O owner, S status, P priority, T due date, C close on the item with the keyboard, or on the selection it is one of; V the eye, on the cursor row only */
  function letter(e, id, h) {
    if (!keysOn() || H.on) return false;
    const k = e.key.toLowerCase();
    if (UI.peek && k === 'c') return false;                                                  // with the peek open C is the peek's own: Draft email
    if (k === 'v') { const x = item(id); if (!x) return false; e.preventDefault(); eye(x); return true; }
    const ids = M.ids.includes(id) ? M.ids.slice() : [id], sum = summary(ids.map(item).filter(Boolean));
    e.preventDefault();
    const ctl = { o: sum.table === 'decisions' ? 'made_by' : 'owner', s: 'status', p: 'priority', t: 'due', c: 'close' }[k], why = keyWhy(ctl, sum);
    if (why) { C.toast(why); say(why); return true; }
    const [x, y] = below(h); openControl(ctl, ids, { x, y }, id, { how: h.matches('[data-card]') ? 'on the board' : 'in the table' });
    return true;
  }
  function moveTo(to, cell, order) {
    M.cursor = to; cursorOnly();
    const h = homeOf(to); if (!h) return;
    const t = cell && h.matches('tr') ? (cell.dataset.weye !== undefined ? $('[data-weye]', h) : $(`[data-pick][data-prop="${cell.dataset.prop}"]`, h)) : null;   // from a cell: the same cell of that row
    (t || h).focus(); h.scrollIntoView({ block: 'nearest' });
    if (UI.peek && C.peekKind() === 'item') C.openItem(to, order);                         // the peek follows the cursor
  }
  /* the keys on a row, a card, or a cell's own button inside a row. h: the row or card; cell: the button, or null */
  function keys(e, id, h, cell) {
    if (e.defaultPrevented || e.altKey || e.isComposing) return false;
    const k = e.key, mod = e.metaKey || e.ctrlKey, isCard = h.matches('[data-card]'), order = drawn(), i = order.indexOf(id);
    if (k === 'ContextMenu' || (k === 'F10' && e.shiftKey)) { if (H.on) return false; e.preventDefault(); const [x, y] = below(h); menuFor(id, x, y, h); return true; }
    if (mod) { if (!H.on && !e.shiftKey && (k === 'a' || k === 'A')) { e.preventDefault(); setSel(order, { anchor: order[0], cursor: id }); return true; } return false; }
    if (e.shiftKey) {
      if (H.on || (k !== 'ArrowDown' && k !== 'ArrowUp')) return false;
      e.preventDefault(); const to = extend(k === 'ArrowDown' ? 1 : -1, id); if (to && to !== id) moveTo(to, cell, order); return true;
    }
    if (!cell && k === ' ' && (!isCard || M.ids.length || H.on)) { e.preventDefault(); toggle(id); return true; }   // Space adds or removes the cursor row (a card's Space still opens it until something is picked)
    if (/^[ospctv]$/i.test(k) && !e.repeat) return letter(e, id, h);
    if (i < 0) return false;
    const to = j => { e.preventDefault(); moveTo(order[j], cell, order); return true; };
    if (cell) {                                                                              // a cell: Up and Down to the same cell of the next row, Left and Right across the row
      const here = [...h.querySelectorAll('[data-pick], [data-weye]')], c = here.indexOf(cell);
      if (k === 'ArrowDown' || k === 'ArrowUp') { const j = i + (k === 'ArrowDown' ? 1 : -1); if (j < 0 || j >= order.length) { e.preventDefault(); return true; } return to(j); }
      if (k === 'ArrowRight' && here[c + 1]) { e.preventDefault(); here[c + 1].focus(); return true; }
      if (k === 'ArrowLeft') { e.preventDefault(); (here[c - 1] || h).focus(); return true; }
      return false;
    }
    if (k === 'ArrowDown' || (isCard && k === 'ArrowRight')) return to(Math.min(order.length - 1, i + 1));
    if (k === 'ArrowUp' || (isCard && k === 'ArrowLeft')) return to(Math.max(0, i - 1));
    if (k === 'Home') return to(0);
    if (k === 'End') return to(order.length - 1);
    if (!isCard && k === 'ArrowRight') { e.preventDefault(); if (!UI.peek || UI.peek !== id) C.openItem(id, order); return true; }     // Right opens the peek when it is closed
    if (!isCard && k === 'ArrowLeft') { if (UI.peek) { e.preventDefault(); C.closePeek(); } return true; }                              // Left closes it when it is open
    if (!isCard && k === 'Enter') { e.preventDefault(); C.openItem(id, order); return true; }
    return false;
  }
  api.key = (e, id) => { const r = e.currentTarget; if (r.classList.contains('arch')) return false; const cell = e.target !== r ? e.target.closest('[data-pick], [data-weye]') : null; if (e.target !== r && !cell) return false; return keys(e, id, r, cell); };
  api.keyCard = (e, id) => e.target === e.currentTarget ? keys(e, id, e.currentTarget, null) : false;

  /* ───────────── #97 and #196: the right-click menu ───────────── */
  function openAt(x, y, items, o) {
    const z = anchorAt(x, y, o.label, o.from);
    C.menu(z.a, items, { onClose: z.onClose, wire: m => m.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight') { const f = document.activeElement; if (f && f.querySelector && f.querySelector('[data-sub]')) { e.preventDefault(); e.stopPropagation(); f.click(); } }
      else if (e.key === 'ArrowLeft' && o.back) { e.preventDefault(); e.stopPropagation(); C.closePop(); o.back(); } }) });
  }
  const sub = t => `<span data-sub="1" class="ctx-sub">${esc(t)}<span class="ctx-go" aria-hidden="true">${C.icon('right', 's')}</span></span>`;
  const note = (name, line) => `<span>${esc(name)}${line ? `<small>${esc(line)}</small>` : ''}</span>`;
  function chg(x, ch, text, how) { const u = D.change('item', x, ch, D.who(how)); if (u) { C.refresh(); C.toast(text, u); } focusSoon(x.id); }
  const copy = (text, said) => { const done = () => { C.toast(said); say(said); }, fail = () => { C.toast('The browser did not copy it. Select the text and press ⌘C instead.'); };
    try { navigator.clipboard.writeText(text).then(done, fail); } catch (e) { fail(); } };
  function menuFor(id, x, y, h) {
    if (H.on) return;                                                                         // pick mode: the right-click menu is off
    if (M.ids.length >= 2 && M.ids.includes(id)) return bulkMenu(M.ids.slice(), x, y, h);
    if (M.ids.length && !(M.ids.length === 1 && M.ids[0] === id)) setSel([id], { anchor: id, cursor: id });   // a row outside the selection is picked on its own first
    rowMenu(id, x, y, h, '');
  }
  function bulkMenu(ids, x, y, h) {
    const xs = ids.map(item).filter(Boolean), sum = summary(xs), n = xs.length, from = h && h.isConnected ? h : null, how = h && h.matches('[data-card]') ? 'on the board' : 'in the table';
    const items = [{ lab: words(n) }];
    if (!sum.table) items.push({ html: note(WHY.kinds), disabled: true });
    else controls(sum).forEach(c => items.push({ html: note(c.menu ? c.label + '…' : c.label, c.on ? '' : c.why), disabled: !c.on, onPick: () => openControl(c.id, sum.ids, { x, y }, ids[0], { how }) }));
    items.push({ sep: true }, { label: 'Copy IDs', onPick: () => copy(ids.join(', '), `Copied ${n === 1 ? 'the ID' : n + ' IDs'}.`) });
    openAt(x, y, items, { label: words(n), from });
  }
  function rowMenu(id, x, y, h, level) {
    const it = item(id); if (!it) return;
    const how = h && h.matches('[data-card]') ? 'on the board' : 'in the table', from = h && h.isConnected ? h : null, back = () => rowMenu(id, x, y, h, '');
    const done = (ch, text) => chg(it, ch, text, how);
    const pickList = (title, rows) => openAt(x, y, [{ lab: `${title} of ${id}` }, ...rows, { sep: true }, { label: '‹ Back', onPick: back }], { label: `${title} of ${id}`, from, back });
    if (level === 'status') {
      const l = D.STATUSES[it.type].filter(s => s !== it.status);
      return pickList('Change status', l.length ? l.map(s => ({ label: s, onPick: () => done({ status: s }, `${id} set to ${s}`) })) : [{ html: note('There is no other status to give this item.'), disabled: true }]);
    }
    if (level === 'owner') {
      const l = C.people().filter(nm => nm !== it.owner);
      return pickList('Change owner', l.length ? l.map(nm => ({ html: `<span class="av">${C.initials(nm)}</span>${esc(nm)}`, onPick: () => done({ owner: nm }, `${id} now with ${nm}`) })) : [{ html: note('No one else is named in this project yet.'), disabled: true }]);
    }
    if (level === 'due') {
      const f = D.friday() === D.TODAY ? D.addDays(D.TODAY, 7) : D.friday(), w = D.addDays(D.TODAY, 7);
      return pickList('Move due date', [{ html: note('Friday', D.fd(f)), onPick: () => done({ due: f }, `${id} moved to ${D.fd(f)}`) }, { html: note('A week on', D.fd(w)), onPick: () => done({ due: w }, `${id} moved to ${D.fd(w)}`) },
        { label: 'Pick a date', onPick: () => { const z = anchorAt(x, y, 'Choose a date', from); C.calPick(z.a, it.due, v => done({ due: v }, v ? `${id} moved to ${D.fd(v)}` : `${id} has no date now`), { onClose: z.onClose }); } },
        ...(it.due ? [{ label: 'No date', onPick: () => done({ due: '' }, `${id} has no date now`) }] : [])]);
    }
    const people = D.S.people || {}, email = it.owner && (people[it.owner] || {}).email, open = C.isOpen(it);
    const draft = !it.owner ? { name: 'Draft email to the owner', line: NO_OWNER, off: true } : !open ? { name: `Draft email to ${it.owner}`, line: NOT_OFFERED, off: true }
      : { name: `Draft email to ${it.owner}`, line: email ? '' : `${it.owner} has no email on the People list, so the To line is left empty.`, off: false };
    openAt(x, y, [
      { html: `<span>${C.icon('mail', 's')} ${esc(draft.name)}${draft.line ? `<small>${esc(draft.line)}</small>` : ''}</span>`, disabled: draft.off, onPick: () => C.mailPane(it) },
      { label: 'Open the peek', onPick: () => C.openItem(id, drawn()) },
      { sep: true },
      { html: sub('Change status'), onPick: () => rowMenu(id, x, y, h, 'status') }, { html: sub('Move due date'), onPick: () => rowMenu(id, x, y, h, 'due') }, { html: sub('Change owner'), onPick: () => rowMenu(id, x, y, h, 'owner') },
      { label: it.client ? 'Hide from the client' : 'Show to the client', onPick: () => eye(it) },
      { sep: true },
      { label: 'Copy link to this item', onPick: () => copy(location.href.split('#')[0] + '#work&item=' + id, `Link to ${id} copied.`) }, { label: 'Copy ID', onPick: () => copy(id, `${id} copied.`) },
      { sep: true },
      { html: `${C.icon('plus', 's')} Duplicate`, onPick: () => { const n = { ...D.clone(it), id: C.nextId(it.type), title: it.title + ' (copy)', updatedAt: D.stamp(), source: 'Duplicated from ' + id }; const u = D.create('item', n, D.who(how)); C.refresh(); C.toast(`Copy of ${id} added: ${n.id}`, u); focusSoon(id); } },
      { html: `${C.icon('archive', 's')} Archive`, onPick: () => { const u = D.archive(it, true, D.who(how), 'item'); if (!u) return; if (UI.peek === id) C.closePeek(); C.refresh(); C.toast(`Archived ${id}. It's out of the lists and counts.`, u); focusSoon(M.cursor); } },
    ], { label: `Actions for ${id}`, from });
  }

  /* ───────────── wiring: once per draw of the list (views.js calls this at the end of wireList) ───────────── */
  api.wire = () => {
    const l = $('#wlist'); if (!l) return;
    if (!l.dataset.multi) {
      l.dataset.multi = '1';
      l.addEventListener('mousedown', e => {                                                  // a Shift press would select the text between the clicks: stop that, and keep the keyboard on the row
        if (!e.shiftKey || e.button !== 0) return; const h = e.target.closest(HOMES); if (!h || e.target.closest('button, a, input, label')) return;
        e.preventDefault(); h.focus({ preventScroll: true }); });
      l.addEventListener('dblclick', e => {                                                   // once something is picked a click selects, so a double click opens the peek
        const h = e.target.closest(HOMES); if (!h || H.on || !M.ids.length || e.target.closest('button, a, input, label')) return;
        const id = idOf(h); setSel([id], { anchor: id, cursor: id }); C.openItem(id, drawn()); });
    }
    $$('#wlist .ghead').forEach(g => g.addEventListener('click', () => { sync(); paint(); }));   // a group opened or shut: its rows join or leave
    sync(); paint();
  };

  /* ───────────── the page-wide rules ───────────── */
  { const r0 = C.render; C.render = function () { if (UI.view !== 'work' || UI.code !== M.code) reset(); return r0.apply(this, arguments); }; }   // a change of tab or project ends it
  { const o0 = C.openItem; C.openItem = function (id, list) { o0.call(this, id, list); if (M.cursor !== id) { M.cursor = id; cursorOnly(); } }; }   // the peek moved: the cursor follows
  document.addEventListener('focusin', e => {
    const h = e.target.closest && e.target.closest(HOMES); if (!h || !inWork()) return;
    const id = idOf(h); if (M.cursor !== id) { M.cursor = id; cursorOnly(); } });
  /* #246: with the peek open and the keyboard in its top bar (where it lands on opening), Up and Down step to the previous and next item, as its arrows do; the row cursor follows */
  document.addEventListener('keydown', e => {
    if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || e.shiftKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return;
    if (!UI.peek || C.peekKind() !== 'item' || busy()) return;
    const a = document.activeElement; if (!a || !a.closest || !a.closest('#peek .pk-top')) return;
    const b = $(e.key === 'ArrowDown' ? '#pkNext' : '#pkPrev'); if (!b) return; e.preventDefault();
    if (!b.disabled) { b.click(); if (UI.peek && M.cursor !== UI.peek) { M.cursor = UI.peek; cursorOnly(); } }
  });
  /* Esc ends a selection or pick mode, unless something open takes Esc first (a menu, a box, the peek) */
  window.addEventListener('keydown', e => {
    if (e.key !== 'Escape' || e.defaultPrevented || !inWork() || !(M.ids.length || H.on)) return;
    if (UI.peek || busy() || (!H.on && C.typing(document.activeElement))) return;
    e.preventDefault(); e.stopPropagation(); if (H.on) handStop(); else { clear(); focusSoon(M.cursor); }
  }, true);
  /* a click outside Work items (and outside anything open over it) ends a selection */
  document.addEventListener('click', e => {
    if (!M.ids.length) return; const t = e.target; if (!t || !t.isConnected || !t.closest || t.closest('#main, .menu, .toast, dialog, #peek, #ask, .ctx-at')) return;
    clear(true);
  }, true);
  document.addEventListener('contextmenu', e => {
    if (!inWork() || e.defaultPrevented || H.on) return;
    const h = e.target.closest && e.target.closest(HOMES);
    if (!h || e.target.isContentEditable || e.target.closest('input, textarea, select, a')) return;
    e.preventDefault(); menuFor(idOf(h), e.clientX, e.clientY, h);
  });
  /* the People list in Settings: Hand over their work opens Work items on that person's open items in pick mode */
  document.addEventListener('click', e => {
    const b = e.target.closest && e.target.closest('[data-ho]'); if (!b) return;
    C.workLine(`is:open owner:${C.fline.quote(b.dataset.ho)}`); handStart();
  });
})();
