/* clark prototype: the command palette (#198). Cmd or Ctrl+K opens it from anywhere, even while typing in a box; Esc or the same keys close it and
   the focus goes back where it was. One search box. Typing finds, in this order: commands, pages, projects, work items (an ID first, then words in
   the title) and milestones. Each result says what it is in words. Up and Down move (wrapping, past any result that cannot run now), Enter runs or
   opens, a click does too; a result that cannot run now is shown disabled with the reason. The published page has no palette. It uses Cmd or Ctrl,
   so it still works when Single-key shortcuts are off. */
(function () {
  'use strict';
  const C = window.C, D = C.D, UI = C.UI, esc = C.esc;
  const MOST_ITEMS = 8;                       /* work items shown at most, so a short word does not fill the box */
  const NEED_PROJECT = 'Open a project first.';
  const lower = s => String(s == null ? '' : s).toLowerCase(), words = q => lower(q).split(/\s+/).filter(Boolean), hits = (t, ws) => { const x = lower(t); return ws.every(w => x.includes(w)); };
  let box = null, opener = null, at = -1, results = [], q = '';
  C.palOpen = () => !!(box && box.open);

  const commands = () => { const why = C.P() ? '' : NEED_PROJECT, dark = document.documentElement.dataset.theme === 'dark', pref = C.themePref();
    return [
      { key: 'publish', label: 'Publish…', more: 'report send client', why, run: () => { if (UI.view !== 'dashboard') C.go('dashboard'); C.publishDialog(); } },
      { key: 'preview', label: 'Preview the page in a new tab', more: 'published page', why, run: () => C.publish('tab') },
      { key: 'export', label: 'Export to Excel', more: 'workbook download xlsx', why, run: () => C.exportExcel() },
      { key: 'settings', label: 'Settings', more: 'options folder profile backup', why: '', run: () => C.go('settings') },
      { key: 'ask', label: 'ask clark', more: 'question chat', why: '', run: () => C.askOpen() },
      { key: 'help', label: 'Help', more: 'keys shortcuts how', why: '', run: () => C.help.open() },
      ...[['light', 'Light'], ['dark', 'Dark'], ['system', 'System']].map(([v, t]) => ({ key: 'look-' + v, label: 'Appearance: ' + t, more: 'dark mode theme look colour', why: '', now: pref === v, run: () => { C.themeSet(v); if (UI.view === 'settings') C.render(); } })),
    ].map(c => ({ id: 'cmd-' + c.key, kind: 'Command', label: c.label, more: c.more, disabled: c.why, now: !!c.now, run: c.run })); };
  const pages = () => [['dashboard', 'Dashboard'], ['work', 'Work items'], ['milestones', 'Milestones'], ['usecases', 'Use cases']].map(([v, t]) => ({ id: 'page-' + v, kind: 'Page', label: t, more: '', disabled: '', current: UI.view === v, run: () => C.go(v) }));
  const find = query => {
    const ws = words(query), all = (t, extra) => !ws.length || hits(t + ' ' + (extra || ''), ws), out = [];
    commands().forEach(c => { if (all(c.label + ' command', c.more)) out.push(c); });
    pages().forEach(p => { if (all(p.label + ' page')) out.push(p); });
    C.live().forEach(p => { if (!all(p.name + ' ' + p.code + ' project')) return; const here = p.code === UI.code; out.push({ id: 'project-' + p.code, kind: 'Project', label: p.name, more: p.code, disabled: '', current: here, run: () => { if (!here) C.setProject(p.code); } }); });
    if (ws.length && C.P()) {
      const t = lower(query).trim(), its = C.items().filter(x => hits(x.id + ' ' + x.title, ws)), rank = x => { const i = lower(x.id); return i === t ? 0 : i.startsWith(t) ? 1 : i.includes(t) ? 2 : 3; };
      its.sort((a, b) => rank(a) - rank(b));   /* stable: an ID match first, the rest keep the page's order */
      its.slice(0, MOST_ITEMS).forEach(x => out.push({ id: 'item-' + x.id, kind: D.TYPES[x.type], label: x.title, more: x.id, disabled: '', run: () => { if (!['dashboard', 'work', 'milestones', 'usecases'].includes(UI.view)) C.go('work'); C.openItem(x.id, its.map(y => y.id)); } }));
      C.mss().forEach(m => { if (hits(m.name + ' ' + m.id + ' milestone', ws)) out.push({ id: 'ms-' + m.id, kind: 'Milestone', label: m.name, more: m.id, disabled: '', run: () => { if (!['dashboard', 'work', 'milestones', 'usecases'].includes(UI.view)) C.go('milestones'); C.openMs(m.id); } }); });
    }
    return out;
  };
  C.palSearch = find;
  const step = (list, from, dir) => { const n = list.length; for (let k = 1; k <= n; k++) { const i = (((from < 0 ? (dir > 0 ? -1 : 0) : from) + dir * k) % n + n) % n; if (!list[i].disabled) return i; } return -1; };

  function draw() {
    results = find(q); if (at < 0 || at >= results.length || results[at].disabled) at = step(results, -1, 1);
    const list = C.$('#palList', box), none = C.$('#palNone', box);
    list.innerHTML = results.map((r, i) => `<li id="pal-${esc(r.id)}" role="option" class="pal-row${i === at ? ' on' : ''}${r.disabled ? ' off' : ''}" data-i="${i}" data-kind="${esc(r.kind)}" aria-selected="${i === at}"${r.disabled ? ' aria-disabled="true"' : ''}><span class="pal-kind">${esc(r.kind)}</span><span class="pal-label">${esc(r.label)}</span>${r.more ? `<span class="pal-more muted num">${esc(r.more)}</span>` : ''}${r.current ? '<span class="pal-more muted">You are here</span>' : ''}${r.now ? '<span class="pal-more muted">In use</span>' : ''}${r.disabled ? `<span class="pal-why muted">${esc(r.disabled)}</span>` : ''}</li>`).join('');
    none.hidden = results.length > 0; none.textContent = `Nothing matches “${q}”. Try a work item’s ID or a word from its title.`;
    const inp = C.$('#palQ', box); if (at >= 0) inp.setAttribute('aria-activedescendant', 'pal-' + results[at].id); else inp.removeAttribute('aria-activedescendant');
    C.$('#palLive', box).textContent = results.length ? `${results.length} ${results.length === 1 ? 'result' : 'results'}` : 'Nothing matches.';
    C.$$('.pal-row', box).forEach(li => { li.addEventListener('mousemove', () => { const i = +li.dataset.i; if (!results[i].disabled && i !== at) { at = i; C.$$('.pal-row', box).forEach(x => { const on = +x.dataset.i === at; x.classList.toggle('on', on); x.setAttribute('aria-selected', on); }); inp.setAttribute('aria-activedescendant', 'pal-' + results[at].id); } });
      li.addEventListener('mousedown', e => e.preventDefault()); li.addEventListener('click', () => choose(+li.dataset.i)); });
    const row = C.$('.pal-row.on', box); if (row && row.scrollIntoView) row.scrollIntoView({ block: 'nearest' });
  }
  const choose = i => { const r = results[i]; if (!r || r.disabled) return; close(false); r.run(); };
  function close(back) {
    if (box && box.open) box.close(); if (box) { box.remove(); box = null; }
    const el = opener; opener = null; C.$('#palBtn')?.setAttribute('aria-expanded', 'false');
    if (back) { if (el && el.isConnected && el.focus) el.focus({ preventScroll: true }); else { const m = C.$('#main'); if (m) { m.setAttribute('tabindex', '-1'); m.focus({ preventScroll: true }); } } }
  }
  function open() {
    if (box) return; const a = document.activeElement; opener = a && a !== document.body ? a : null; q = ''; at = -1;
    box = document.createElement('dialog'); box.id = 'palette'; box.className = 'pal'; box.setAttribute('aria-label', 'Go to or do');
    box.innerHTML = `<div class="pal-q"><input type="text" id="palQ" role="combobox" aria-expanded="true" aria-controls="palList" aria-autocomplete="list" placeholder="Type a command, page, project, work item or milestone" aria-label="Search commands, pages, projects, work items and milestones" autocomplete="off" spellcheck="false"></div>
      <ul id="palList" class="pal-list" role="listbox" aria-label="Results"></ul><p class="pal-none muted" id="palNone" hidden></p><p class="sr" id="palLive" role="status" aria-live="polite"></p>`;
    document.body.appendChild(box); box.showModal(); C.$('#palBtn')?.setAttribute('aria-expanded', 'true');
    const inp = C.$('#palQ', box); inp.focus(); draw();
    inp.addEventListener('input', () => { q = inp.value; at = -1; draw(); });
    inp.addEventListener('keydown', e => {
      if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); at = step(results, at, e.key === 'ArrowDown' ? 1 : -1); draw(); }
      else if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); at = step(results, e.key === 'Home' ? -1 : results.length, e.key === 'Home' ? 1 : -1); draw(); }
      else if (e.key === 'Enter' && !e.isComposing) { e.preventDefault(); choose(at); } });
    box.addEventListener('cancel', e => { e.preventDefault(); close(true); });
  }
  C.palToggle = () => { if (box) close(true); else if (!document.querySelector('dialog[open]')) open(); };
  window.addEventListener('keydown', e => {
    const k = (e.key || '').toLowerCase();
    if ((e.metaKey || e.ctrlKey) && !e.altKey && !e.shiftKey && !e.isComposing && k === 'k') { e.preventDefault(); e.stopImmediatePropagation(); if (!e.repeat) C.palToggle(); return; }
    if (box && (e.key === 'Escape' || ((e.metaKey || e.ctrlKey) && (k === 'j' || k === 'z')))) { e.preventDefault(); e.stopImmediatePropagation(); if (e.key === 'Escape') close(true); }
  }, true);
  document.addEventListener('DOMContentLoaded', () => C.$('#palBtn')?.addEventListener('click', () => C.palToggle()));
})();
