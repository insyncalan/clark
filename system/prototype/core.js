/* clark prototype: shared helpers, the shell (top bar, routing, keys), menus, popovers, dialogs and the toast. */
(function () {
  'use strict';
  const D = window.ClarkDB;
  const C = window.C = { D };
  C.$ = (s, el = document) => el.querySelector(s);
  C.$$ = (s, el = document) => [...el.querySelectorAll(s)];
  C.esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  C.initials = n => (n || '?').split(/\s+/).filter(Boolean).map(w => w[0]).join('').slice(0, 2).toUpperCase();
  C.reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  /* the brand's picture is set now, before the data loads, so the page background never appears late and swaps in (brand-data.js
     loads before this file) */
  if ((window.BRAND || {}).cover) document.documentElement.style.setProperty('--image-cover', `url("${window.BRAND.cover}")`);
  C.store = { get(k, d) { try { const v = localStorage.getItem('clark.' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } }, set(k, v) { try { localStorage.setItem('clark.' + k, JSON.stringify(v)); } catch (e) { /* private window */ } } };
  /* dark mode is set before anything draws, so a dark page never flashes white */
  /* Appearance ("appearance - add system"): Light, Dark or System, and System is the default. The choice is stored as
     'light', 'dark' or 'system'; the page's data-theme is always the look in use, 'light' or 'dark'. System follows the Mac through
     prefers-color-scheme and changes live when the Mac switches. */
  C.mq = matchMedia('(prefers-color-scheme: dark)');
  C.sysDark = () => C.mq.matches;
  C.themePref = () => { const t = C.store.get('theme', 'system'); return t === 'light' || t === 'dark' ? t : 'system'; };
  C.themeApply = () => { document.documentElement.dataset.theme = C.themePref() === 'system' ? (C.sysDark() ? 'dark' : 'light') : C.themePref(); };
  C.theme = t => { C.store.set('theme', t === 'light' || t === 'dark' ? t : 'system'); C.themeApply(); };
  C.themeApply();
  /* both dark-mode switches (the profile menu and Settings › Personal) set the look and say the same thing (the sweep, S7) */
  C.themeSay = pref => pref === 'system' ? 'Appearance follows your Mac: dark mode is ' + (C.sysDark() ? 'on' : 'off') : pref === 'dark' ? 'Dark mode on' : 'Dark mode off';
  C.themeSet = pref => { C.theme(pref); C.toast(C.themeSay(pref)); };
  C.mq.addEventListener('change', () => { if (C.themePref() === 'system') { C.themeApply(); C.log('info', 'theme', 'system look ' + document.documentElement.dataset.theme); } });
  /* how the dashboard's sections are drawn, the user's own choice in Settings › Personal (slim gaps by default) */
  C.secs = v => { if (v) C.store.set('secs', v); return document.documentElement.dataset.dash = C.store.get('secs', 'slim'); };
  C.secs();
  /* the log (prototype): the last 200 lines, in memory. Level Normal keeps info, warn and error; Debug adds debug lines. A line holds
     only IDs, counts and times, never report text, names, emails or keys. The real clark writes the same lines to a file a day. */
  const LOG_MAX = 200, logRows = [], lpad = n => String(n).padStart(2, '0');
  C.logLevel = () => C.store.get('logLevel', 'info');
  C.log = (level, area, msg) => {
    level = String(level || 'info').toLowerCase();
    if (level === 'debug' && C.logLevel() !== 'debug') return;
    const d = new Date(), at = `${d.getFullYear()}-${lpad(d.getMonth() + 1)}-${lpad(d.getDate())} ${lpad(d.getHours())}:${lpad(d.getMinutes())}:${lpad(d.getSeconds())}`;
    logRows.push({ t: d.getTime(), level, line: `${at} ${level.toUpperCase()} ${area} ${msg}` });
    if (logRows.length > LOG_MAX) logRows.splice(0, logRows.length - LOG_MAX);
  };
  C.logLines = n => logRows.slice(n ? -n : 0).map(r => r.line);
  C.logErrors = days => logRows.filter(r => r.level === 'error' && Date.now() - r.t <= days * 864e5).map(r => r.line);
  /* a caught error is logged by its kind and place only: the message could carry a name */
  C.onError = e => C.log('error', 'page', `${(e.error && e.error.name) || 'Error'} at ${String(e.filename || '').split('/').pop() || 'page'}:${e.lineno || 0}`);
  C.onReject = e => C.log('error', 'page', `${(e.reason && e.reason.name) || 'Rejection'} not handled`);
  window.addEventListener('error', C.onError); window.addEventListener('unhandledrejection', C.onReject);
  C.log('info', 'start', 'clark started');
  /* creaite's add button (its NewTile): a quiet "+", which grows to show its words on hover and focus */
  C.addBtn = (attrs, word, menu) => `<button class="addb${menu ? ' hasmenu' : ''}" ${attrs} aria-label="${C.esc(word)}" title="${C.esc(word)}"${menu ? ' aria-haspopup="menu"' : ''}>${C.icon('plus')}<span class="w">${C.esc(word)}</span>${menu ? C.icon('chev', 's nch') : ''}</button>`;
  /* import and export are icons, with their words as a tooltip */
  C.ioBtn = (id, icon, word) => `<button class="ib tip" id="${id}" aria-label="${C.esc(word)}" data-tip="${C.esc(word)}">${C.icon(icon)}</button>`;
  C.typing = el => !!el && (el.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(el.tagName));
  C.dayName = iso => new Date(iso + 'T00:00:00').toLocaleDateString('en-GB', { weekday: 'long' });

  /* ── icons (stroke icons drawn for this prototype, in creaite's shapes) ── */
  const P = {
    close: '<path d="M4 10h11M11 5l5 5-5 5"/>', x: '<path d="M5 5l10 10M15 5L5 15"/>', expand: '<path d="M12 3h5v5M8 17H3v-5M17 3l-6 6M3 17l6-6"/>', collapse: '<path d="M16 9h-5V4M4 11h5v5M11 9l6-6M9 11l-6 6"/>',
    up: '<path d="M5 12l5-5 5 5"/>', down: '<path d="M5 8l5 5 5-5"/>', chev: '<path d="M5 8l5 5 5-5"/>', left: '<path d="M12 5l-5 5 5 5"/>', right: '<path d="M8 5l5 5-5 5"/>',
    eye: '<path d="M2 10s3-5.5 8-5.5S18 10 18 10s-3 5.5-8 5.5S2 10 2 10z"/><circle cx="10" cy="10" r="2.3"/>', eyeoff: '<path d="M3 3l14 14M8.3 5A8.7 8.7 0 0 1 10 4.5c5 0 8 5.5 8 5.5a14 14 0 0 1-2.4 3M5.6 6.4C3.4 7.9 2 10 2 10s3 5.5 8 5.5a8 8 0 0 0 3.2-.7"/>',
    sparkle: '<path d="M10 2.5l1.6 4.4L16 8.5l-4.4 1.6L10 14.5l-1.6-4.4L4 8.5l4.4-1.6z"/><path d="M16 13l.7 1.8 1.8.7-1.8.7L16 18l-.7-1.8-1.8-.7 1.8-.7z"/>',
    link: '<path d="M8.5 11.5a3 3 0 0 0 4.2 0l3-3a3 3 0 0 0-4.2-4.2l-.8.8M11.5 8.5a3 3 0 0 0-4.2 0l-3 3a3 3 0 0 0 4.2 4.2l.8-.8"/>', more: '<circle cx="4.5" cy="10" r="1.2" fill="currentColor"/><circle cx="10" cy="10" r="1.2" fill="currentColor"/><circle cx="15.5" cy="10" r="1.2" fill="currentColor"/>',
    plus: '<path d="M10 4v12M4 10h12"/>', search: '<circle cx="9" cy="9" r="5.5"/><path d="M13 13l4 4"/>', doc: '<path d="M6 2.5h5.5L15 6v11.5H6z"/><path d="M11 2.5V6.5h4M8.5 10h4M8.5 13h4"/>',
    info: '<circle cx="10" cy="10" r="7.5"/><path d="M10 9v5M10 6.2v.3"/>', rows: '<path d="M3 5.5h14M3 10h14M3 14.5h14"/>', filter: '<path d="M3 5h14M6 10h8M9 15h2"/>', board: '<rect x="2.5" y="3.5" width="4.2" height="13" rx="1"/><rect x="8" y="3.5" width="4.2" height="9" rx="1"/><rect x="13.4" y="3.5" width="4.2" height="11" rx="1"/>', tline: '<path d="M2.5 10h15"/><circle cx="6" cy="10" r="1.9" fill="currentColor"/><circle cx="13.5" cy="10" r="1.9"/>', cal: '<rect x="3" y="4.5" width="14" height="12.5" rx="1.5"/><path d="M3 8.5h14M7 2.5v3.5M13 2.5v3.5"/>', drag: '<circle cx="7.5" cy="5" r="1.1" fill="currentColor"/><circle cx="12.5" cy="5" r="1.1" fill="currentColor"/><circle cx="7.5" cy="10" r="1.1" fill="currentColor"/><circle cx="12.5" cy="10" r="1.1" fill="currentColor"/><circle cx="7.5" cy="15" r="1.1" fill="currentColor"/><circle cx="12.5" cy="15" r="1.1" fill="currentColor"/>',
    pencil: '<path d="M13.5 3.5l3 3L7 16H4v-3z"/><path d="M11.5 5.5l3 3"/>', trash: '<path d="M4 6h12M8 6V4h4v2M6 6l.8 11h6.4L14 6"/>', archive: '<rect x="3" y="4" width="14" height="4" rx="1"/><path d="M4.5 8v8h11V8M8.5 11h3"/>', ext: '<path d="M11 3h6v6M17 3l-8 8M14 12v5H3V6h5"/>',
    dl: '<path d="M10 3v10M6 9l4 4 4-4M4 16h12"/>', ul: '<path d="M10 14V4M6 8l4-4 4 4M4 16h12"/>', gear: '<g transform="scale(.8333)" stroke-width="1.92"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></g>',
    chat: '<path d="M4 5.5A2.5 2.5 0 0 1 6.5 3h7A2.5 2.5 0 0 1 16 5.5v5a2.5 2.5 0 0 1-2.5 2.5H9l-3.5 3v-3A2.5 2.5 0 0 1 4 10.5z"/>', send: '<path d="M10 16V4M5 9l5-5 5 5"/>', clock: '<circle cx="10" cy="10" r="7"/><path d="M10 6v4l2.5 2"/>',
    flash: '<path d="M11 2L4 11h5l-1 7 7-9h-5z"/>', user: '<circle cx="10" cy="7" r="3"/><path d="M4 17c.8-3 3.2-4.5 6-4.5s5.2 1.5 6 4.5"/>', bars: '<path d="M5 15v-3M9 15V9M13 15V6M17 15V3"/>',
    half: '<circle cx="10" cy="10" r="7"/><path d="M10 3a7 7 0 0 1 0 14z" fill="currentColor"/>', check: '<path d="M5 10.5l3.2 3L15 6.5"/>', pen: '<path d="M4 16l2-6 7-7 4 4-7 7z"/>', person: '<circle cx="10" cy="7" r="3.2"/><path d="M3.8 17c.8-3.2 3.3-5 6.2-5s5.4 1.8 6.2 5"/>', moon: '<path d="M15.5 12.5A6.5 6.5 0 0 1 7.5 4.5a6.5 6.5 0 1 0 8 8z"/>', mail: '<rect x="3" y="5" width="14" height="10" rx="1.5"/><path d="M3.5 6l6.5 5 6.5-5"/>',
    image: '<rect x="2.5" y="3.5" width="15" height="13" rx="1.5"/><circle cx="7.5" cy="8" r="1.5"/><path d="M17.5 13.5l-4.5-4.5-8 7.5"/>',
    undo: '<path d="M7 7H3V3M3.5 7A7 7 0 1 1 5 14"/>', redo: '<path d="M13 7h4V3M16.5 7A7 7 0 1 0 15 14"/>', text: '<path d="M5 5h10M10 5v11"/>', folder: '<path d="M3 5.5h5l1.5 1.5H17v9H3z"/>',
  };
  C.icon = (n, cls = '') => `<svg class="i ${cls}" viewBox="0 0 20 20" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${P[n] || ''}</svg>`;
  /* milestone state marks, as creaite draws them on the line */
  C.msMark = st => ({
    Achieved: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="#fff" stroke="var(--status-green)" stroke-width="2"/><path d="M6 10.3l2.7 2.6L14 7.6" fill="none" stroke="var(--status-green)" stroke-width="2"/></svg>',
    'On track': '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" fill="var(--status-green)"/></svg>',
    'At risk': '<svg viewBox="0 0 20 20"><path d="M10 3l8 14H2z" fill="#fff" stroke="var(--status-amber)" stroke-width="2" stroke-linejoin="round"/><path d="M10 8v4.2M10 14.4v.3" stroke="var(--status-amber)" stroke-width="2"/></svg>',
    Slipped: '<svg viewBox="0 0 20 20"><path d="M10 2.5l7.5 7.5-7.5 7.5L2.5 10z" fill="#fff" stroke="var(--status-red)" stroke-width="2"/></svg>',
    Overdue: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="8" fill="var(--status-red)"/><path d="M7 7l6 6M13 7l-6 6" stroke="#fff" stroke-width="2"/></svg>',
    Forecast: '<svg viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" fill="#fff" stroke="var(--status-blue)" stroke-width="2" stroke-dasharray="3 2.4"/></svg>',
  }[st] || '');
  C.msCls = st => st.replace(/\s/g, '');

  /* ── toast with undo ── */
  let tT, undoFn = null, expireFn = null;
  /* toast(msg, undo, {onExpire}): onExpire runs when the toast goes without Undo (or another toast takes its place) */
  /* every change that offers Undo also goes on a short list, so Cmd or Ctrl+Z can take back the last one after its message has gone (#197);
     each step runs once, whichever way it is taken back */
  const steps = [];
  C.toast = (msg, undo, o = {}) => {
    if (expireFn) { const f = expireFn; expireFn = null; f(); }
    if (undo) { const rec = { msg, done: false, fn: undo }; steps.push(rec); if (steps.length > 50) steps.shift(); undo = () => { if (rec.done) return; rec.done = true; rec.fn(); }; }
    const t = C.$('#toast'); C.$('#toastMsg').textContent = msg; undoFn = undo || null; C.$('#toastUndo').hidden = !undo; expireFn = o.onExpire || null;
    t.classList.add('on'); clearTimeout(tT); tT = setTimeout(() => { t.classList.remove('on'); undoFn = null; if (expireFn) { const f = expireFn; expireFn = null; f(); } }, o.ms || (undo ? 6500 : 2800));
  };
  /* Cmd or Ctrl+Z: the last change that can still be undone; with none, it says so */
  C.undoClear = () => { steps.length = 0; };   /* a reset of the demo data leaves nothing to undo: the old steps point at records that are gone */
  C.undoLast = () => { let r; while ((r = steps.pop())) { if (r.done) continue; r.done = true; r.fn(); C.refresh(); C.toast('Undone: ' + r.msg); return true; } C.toast('Nothing to undo.'); return false; };
  /* Single-key shortcuts (#193): on unless turned off in Settings › Personal; kept in this browser like the colour theme, read live */
  C.keysOn = () => C.store.get('singleKeys', true) !== false;
  C.keyHint = k => C.keysOn() ? ` (${k})` : '';
  /* the eye: the row stays (greyed) while Undo is offered; then it leaves the editor */
  C.hideLater = (rows, undo, msg) => { [].concat(rows).filter(Boolean).forEach(r => r.classList.add('leaving')); C.toast(msg, undo, { onExpire: () => C.refresh() }); };
  document.addEventListener('DOMContentLoaded', () => C.$('#toastUndo').addEventListener('click', () => { const u = undoFn; undoFn = null; expireFn = null; clearTimeout(tT); C.$('#toast').classList.remove('on'); if (u) { u(); if (!(C.edIsOpen && C.edIsOpen())) C.refresh(); } }));   // an editor still open keeps its text; the page catches up when it closes
  /* a change that can be undone: run it, refresh, offer Undo */
  C.did = (undo, msg) => { if (!undo) return; C.refresh(); C.toast(msg || 'Saved', undo); };

  /* ── menus and popovers (one open at a time; Esc, a click outside or a pick closes) ── */
  let openPop = null;
  C.closePop = () => { if (!openPop) return; const p = openPop, had = p.el.contains(document.activeElement); openPop = null; p.el.remove(); p.anchor?.setAttribute('aria-expanded', 'false'); if (had && p.anchor?.isConnected) p.anchor.focus({ preventScroll: true }); /* Esc, a pick or a click away: the focus goes back to the button */ p.onClose && p.onClose(); };
  C.popOpen = () => !!openPop;
  function place(el, anchor, align) {
    const r = anchor.getBoundingClientRect(), w = el.offsetWidth, h = el.offsetHeight;
    let left = align === 'right' ? r.right - w : r.left; left = Math.max(8, Math.min(left, innerWidth - w - 8));
    let top = r.bottom + 6; if (top + h > innerHeight - 8 && r.top - h - 6 > 8) { top = r.top - h - 6; el.style.transformOrigin = 'bottom left'; }
    el.style.left = left + 'px'; el.style.top = top + 'px';
  }
  C.popover = (anchor, html, { align, cls = '', onClose, wire } = {}) => {
    if (openPop && openPop.anchor === anchor) { C.closePop(); return null; }   // a second click on the same button closes it
    C.closePop();
    const el = document.createElement('div'); el.className = 'menu ' + cls; el.innerHTML = html; document.body.appendChild(el);
    place(el, anchor, align); requestAnimationFrame(() => el.classList.add('on'));
    openPop = { el, anchor, onClose, align }; anchor.setAttribute('aria-expanded', 'true');
    wire && wire(el); return el;
  };
  /* one date picker of clark's own, in a popover, so a single Esc closes it ("a single esc should close both
     calendar panels"; the browser's own calendar opened over the popover and took the first Esc). A month grid with ‹ ›, quick
     choices, and the keyboard: arrows move a day or a week, Enter picks, Esc closes. */
  C.calPick = (anchor, value, onPick, o = {}) => {
    let view = (value || D.TODAY).slice(0, 7), at = value || D.TODAY;
    const draw = el => { const d1 = new Date(view + '-01T00:00:00'), lead = (d1.getDay() + 6) % 7, n = new Date(d1.getFullYear(), d1.getMonth() + 1, 0).getDate();
      const cells = [...Array(lead).fill(''), ...Array.from({ length: n }, (_, i) => `${view}-${String(i + 1).padStart(2, '0')}`)];
      el.querySelector('.cp-g').innerHTML = ['M', 'T', 'W', 'T', 'F', 'S', 'S'].map(x => `<span class="cp-w">${x}</span>`).join('') + cells.map(iso => !iso ? '<span></span>'
        : `<button type="button" data-cp="${iso}" class="${iso === D.TODAY ? 'today ' : ''}${iso === value ? 'sel ' : ''}${iso === at ? 'at' : ''}"${o.min && iso < o.min ? ' disabled' : ''} aria-label="${D.fd(iso)}">${+iso.slice(8)}</button>`).join('');
      el.querySelector('.cp-t').textContent = d1.toLocaleDateString('en-GB', { month: 'long', year: 'numeric' }); };
    const pick = iso => { if (o.min && iso && iso < o.min) return; C.closePop(); onPick(iso); };
    return C.popover(anchor, `<div class="cp" role="dialog" aria-label="Choose a date"><div class="cp-h"><button type="button" class="ib" data-cpm="-1" aria-label="Previous month">${C.icon('left', 's')}</button><b class="cp-t"></b><button type="button" class="ib" data-cpm="1" aria-label="Next month">${C.icon('right', 's')}</button></div><div class="cp-g" role="grid"></div>
      ${(o.quick || []).length ? `<div class="cp-q">${o.quick.map(([t, v]) => `<button type="button" data-cpq="${v}">${t}${v ? `<small>${D.fd(v)}</small>` : ''}</button>`).join('')}</div>` : ''}</div>`, { wire: el => {
      draw(el);
      el.addEventListener('click', e => { const b = e.target.closest('[data-cp],[data-cpm],[data-cpq]'); if (!b) return; e.stopPropagation();
        if (b.dataset.cpm) { const d = new Date(view + '-01T00:00:00'); d.setMonth(d.getMonth() + +b.dataset.cpm); view = D.toIso(d).slice(0, 7); draw(el); }
        else pick(b.dataset.cp ?? b.dataset.cpq); });
      el._key = e => { const mv = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 }[e.key];
        if (mv) { e.preventDefault(); at = D.addDays(at, mv); view = at.slice(0, 7); draw(el); return true; }
        if (e.key === 'Enter') { e.preventDefault(); pick(at); return true; } return false; };
    } });
  };
  /* a menu is role="menu": a plain item is "menuitem"; one with a tick is "menuitemradio" (a choice: select menus) or
     "menuitemcheckbox" (a switch). Focus moves into it; Down/Up wrap, Home/End jump, Enter or Space picks, Esc and Tab close it
     and focus goes back to the button that opened it (the design review, #87). opts.head is markup above the items (the owner picker's
     name field, #99): the focus starts there, Down or Up go from it into the items, and its other keys stay its own; opts.wire wires it. */
  C.menu = (anchor, items, opts = {}) => {
    const html = items.map((it, i) => it.sep ? '<div class="sep" role="separator"></div>' : it.lab ? `<div class="lab" role="presentation">${C.esc(it.lab)}</div>`
      : `<div role="${it.selected === undefined ? 'menuitem' : opts.select ? 'menuitemradio' : 'menuitemcheckbox'}" tabindex="-1" data-i="${i}" ${it.selected !== undefined ? `aria-checked="${!!it.selected}"` : ''} ${it.disabled ? 'aria-disabled="true"' : ''} class="${it.danger ? 'danger' : ''}">${it.html || C.esc(it.label)}</div>`).join('');
    const el = C.popover(anchor, (opts.head || '') + html, { ...opts, wire: el => {
      el.setAttribute('role', 'menu'); const nm = anchor.getAttribute('aria-label') || anchor.title; if (nm) el.setAttribute('aria-label', nm);
      const opts2 = C.$$('[data-i]:not([aria-disabled=true])', el); let at = Math.max(0, opts2.findIndex(o => o.getAttribute('aria-checked') === 'true'));
      const mark = (focus) => { opts2.forEach((o, i) => o.classList.toggle('active', i === at)); if (focus) opts2[at]?.focus({ preventScroll: true }); }; mark(!opts.head);
      opts2.forEach((o, i) => { o.addEventListener('mousemove', () => { at = i; mark(); }); o.addEventListener('click', e => { e.stopPropagation(); const it = items[+o.dataset.i]; C.closePop(); anchor.focus({ preventScroll: true }); it.onPick && it.onPick(it); }); });
      el._key = e => {
        if (!opts2.length) return false;
        if (opts.head && !e.target.closest('[data-i]') && e.key !== 'Tab') {   // in the head: Down or Up go into the items, the rest are its own
          if (e.key !== 'ArrowDown' && e.key !== 'ArrowUp') return false;
          e.preventDefault(); at = e.key === 'ArrowDown' ? 0 : opts2.length - 1; mark(true); return true; }
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); at = (at + (e.key === 'ArrowDown' ? 1 : opts2.length - 1)) % opts2.length; mark(true); return true; }
        if (e.key === 'Home' || e.key === 'End') { e.preventDefault(); at = e.key === 'Home' ? 0 : opts2.length - 1; mark(true); return true; }
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); opts2[at]?.click(); return true; }
        if (e.key === 'Tab') { C.closePop(); return false; }   /* the focus is on the button again; Tab carries on from there */
        return false;
      };
      if (opts.wire) opts.wire(el);
    } });
    return el;
  };
  document.addEventListener('mousedown', e => { if (openPop && !openPop.el.contains(e.target) && !openPop.anchor.contains(e.target)) C.closePop(); }, true);
  window.addEventListener('resize', () => C.closePop());
  /* a page scroll moves the open menu with its button; an inner scroller closes it */
  document.addEventListener('scroll', e => { if (!openPop || openPop.el.contains(e.target)) return; if (e.target === document || e.target === document.documentElement) { if (openPop.anchor.isConnected) place(openPop.el, openPop.anchor, openPop.align); else C.closePop(); } else if (e.target.contains && e.target.contains(openPop.anchor)) C.closePop(); }, true);   // another area scrolling (the timeline finding today) leaves the menu alone

  /* ── dialog ── */
  C.dialog = (html, wire) => {
    const d = C.$('#dlg'); d.innerHTML = html; if (!d.open) d.showModal();
    C.$$('[data-close]', d).forEach(b => b.addEventListener('click', () => d.close()));
    wire && wire(d); return d;
  };
  C.confirm = (title, body, yes, onYes) => C.dialog(`<div class="dlg-h"><h2>${C.esc(title)}</h2></div><div class="dlg-b">${body}</div><div class="dlg-f"><button class="btn quiet" data-close>Cancel</button><button class="btn danger" id="cfYes">${C.esc(yes)}</button></div>`,
    d => C.$('#cfYes', d).addEventListener('click', () => { d.close(); onYes(); }));

  /* ── state of the page ── */
  const UI = C.UI = { view: 'dashboard', code: C.store.get('project', 'PDF'), editing: false, peek: null, uc: '' };   /* uc: the use case open on the Use cases page (its own address), '' for the list */
  /* an archived project (FR-43c) is out of every default view: the switcher, the pages, the owners list. Settings › Projects can show it again and Restore it. */
  C.live = () => D.S.projects.filter(p => !p.archived);
  C.P = () => C.live().find(p => p.code === UI.code) || C.live()[0];
  /* an archived work item or milestone (FR-43c, #166) is out of the default lists and counts, the dashboard and the published page: C.items() and C.mss()
     leave it out. Show archived on Work items and Milestones lists it from C.itemsAll() and C.mssAll(); it opens read-only with Restore. */
  C.itemsAll = () => D.S.items.filter(x => x.code === C.P()?.code);
  C.items = () => C.itemsAll().filter(x => !x.archived);
  C.mssAll = () => D.S.milestones.filter(m => m.code === C.P()?.code).sort((a, b) => (a.agreed || '').localeCompare(b.agreed || ''));
  C.mss = () => C.mssAll().filter(m => !m.archived);
  /* a work item keeps its link to an archived milestone, and shows it as "(archived)" */
  C.msName = id => { const m = id && C.mssAll().find(x => x.id === id); return m ? m.name + (m.archived ? ' (archived)' : '') : ''; };
  /* a use case that is archived (FR-43c) is out of the dashboard, the published page, the counts and the Excel file; the Use cases page lists it under Show archived */
  C.ucAll = () => D.S.usecases.filter(u => u.code === C.P()?.code);
  C.ucs = () => C.ucAll().filter(u => !u.archived);
  C.isOpen = x => !['Closed', 'Cancelled', 'Withdrawn', 'Made'].includes(x.status);   // creaite: Delayed counts as open
  /* creaite has no RAG on risks and issues: the colour is the priority (D-12: "agreed with recommendations") */
  C.ragOf = x => ({ Urgent: 'R', High: 'R', Medium: 'A', Low: 'G' })[x.priority] || 'A';
  C.ragSet = (x, v) => ({ priority: v === 'R' ? (x.priority === 'Urgent' ? 'Urgent' : 'High') : v === 'A' ? 'Medium' : 'Low' });
  /* what a person reads for an item's state: [class, words] */
  C.look = x => {
    if (x.type === 'A') {
      if (x.status === 'Closed' || x.status === 'Cancelled') return ['n', x.status];
      if (x.due && D.days(x.due) < 0) return ['r', 'Overdue'];
      if (x.status === 'Delayed') return ['a', 'Delayed'];
      if (x.due && D.days(x.due) <= 7) return ['a', 'Due soon'];
      return ['b', 'Open'];
    }
    if (x.type === 'D') return x.status === 'Made' ? ['g', 'Made'] : x.status === 'Withdrawn' ? ['n', 'Withdrawn'] : ['b', 'Pending'];
    if (x.status === 'Closed' || x.status === 'Cancelled') return ['n', x.status];
    return { R: ['r', 'Red'], G: ['g', 'Green'] }[C.ragOf(x)] || ['a', 'Amber'];
  };
  /* "1 day", "2 days": one place for the plural of a count of days (the sweep found "1 days overdue") */
  C.dy = n => n + (n === 1 ? ' day' : ' days');
  /* A row or card that has just changed holds a soft tint, then lets go. With reduced motion the tint stays still (no flash) and a small "Changed"
     marker sits in the row, for about 3 seconds: the same news as the flash, without movement. */
  C.changed = el => { if (!el) return; const red = C.reduce, cls = red ? 'chg-static' : 'flash', host = el.matches('tr') ? el.querySelector('td') : el;
    el.classList.add(cls);
    let tag = null; if (red && host) { tag = document.createElement('span'); tag.className = 'chg-tag'; tag.textContent = 'Changed'; host.appendChild(tag); }
    setTimeout(() => { el.classList.remove(cls); tag && tag.remove(); }, red ? 3000 : 1500); };
  /* a changed health: the badge and its reason settle from .5 (idea 6); the redraw has already happened, so this is a one-shot class. Reduced motion: nothing. */
  C.settle = sel => { if (C.reduce) return; C.$$(sel).forEach(el => { el.classList.add('settle'); setTimeout(() => el.classList.remove('settle'), 400); }); };
  C.pill = l => `<span class="pill ${l[0]}">${C.esc(l[1])}</span>`;
  C.dueWords = iso => { if (!iso) return ''; const n = D.days(iso); return n === 0 ? 'Today' : n === 1 ? 'Tomorrow' : n === -1 ? 'Yesterday' : n < 0 ? `${-n} days late` : `In ${n} days`; };
  /* the owners of live work, for the pickers; someone who owns only archived work is left out (#166). all: archived work too (the People table in Settings) */
  C.people = all => { const on = new Set(C.live().map(p => p.code)), use = r => on.has(r.code) && (all || !r.archived);
    return [...new Set(D.S.items.filter(use).map(i => i.owner).concat(D.S.milestones.filter(use).map(m => m.owner)).filter(Boolean))].sort(); };

  /* ── the shell ── */
  const VIEWS = { dashboard: 'Dashboard', work: 'Work items', milestones: 'Milestones', usecases: 'Use cases', settings: 'Settings', help: 'Help', past: 'Past reports' };
  C.drawTop = () => {
    const p = C.P();
    C.$('#projBtn .v').textContent = p ? p.name : 'No project';
    C.$$('.tab').forEach(t => t.setAttribute('aria-selected', t.dataset.view === UI.view));
    document.body.dataset.view = UI.view;
    const me = D.S.profile || {}, b = C.$('#meBtn');
    b.innerHTML = me.name ? `<span aria-hidden="true">${C.esc(C.initials(me.name))}</span>` : C.icon('person', 's');
    /* Publish lives in this menu only (Option A), so the circle says what is behind it */
    b.title = 'Your menu: Publish, Preview, Export, Settings'; b.setAttribute('aria-label', b.title);
  };
  /* standard browser navigation (#63: "backward swipe on trackpad should navigate back a page"): each page, project
     and open peek has its own address (#work&p=PDF&item=PDF-A-012), so Back and Forward, the trackpad swipe and the mouse's buttons
     step through them. Back with a peek open closes the peek first. Filters, scrolling and Edit mode add no steps. */
  const navOf = () => ({ v: UI.view, p: UI.code || '', u: UI.view === 'usecases' ? UI.uc || '' : '', k: UI.peek ? (C.peekKind ? C.peekKind() : 'item') : '', id: UI.peek || '' });
  const navHash = s => '#' + s.v + (s.p ? '&p=' + encodeURIComponent(s.p) : '') + (s.u ? '&uc=' + encodeURIComponent(s.u) : '') + (s.id ? `&${s.k === 'ms' ? 'ms' : 'item'}=${encodeURIComponent(s.id)}` : '');
  const navParse = h => { const [v, ...kv] = String(h || '').replace(/^#/, '').split('&'), q = Object.fromEntries(kv.map(x => x.split('=').map(decodeURIComponent)));
    return { v, p: q.p || '', u: q.uc || '', k: q.ms ? 'ms' : q.item ? 'item' : '', id: q.ms || q.item || '' }; };
  C.navBusy = false;
  C.nav = mode => { if (C.navBusy) return; const s = navOf(); try { history[mode === 'push' ? 'pushState' : 'replaceState'](s, '', navHash(s)); } catch (e) { /* a page without history */ } };
  window.addEventListener('popstate', e => {
    if (C.navSkip) { C.navSkip = false; return; }
    const s = e.state || navParse(location.hash); C.navBusy = true;
    try {
      if (s.p && s.p !== UI.code && C.live().some(p => p.code === s.p)) { UI.code = s.p; C.store.set('project', s.p); UI.editing = false; }
      if (VIEWS[s.v] && s.v !== UI.view) { UI.view = s.v; UI.editing = false; C.store.set('view', s.v); }
      UI.uc = UI.view === 'usecases' ? s.u || '' : '';
      if (!s.id) C.closePeek && C.closePeek({ quiet: true });
      C.drawTop(); C.render();
      if (s.id) (s.k === 'ms' ? C.openMs : C.openItem)(s.id);
    } finally { C.navBusy = false; }
  });
  C.go = (view, opts = {}) => {
    document.body.classList.remove('bfull');
    if (!VIEWS[view]) view = 'dashboard';
    const uc = view === 'usecases' ? opts.uc || '' : '', moved = UI.view !== view || (UI.uc || '') !== uc;
    if (moved) C.log('info', 'nav', 'view ' + view + (uc ? ' ' + uc : ''));
    UI.uc = uc;
    if (UI.view !== view) { UI.editing = false; }
    UI.view = view; C.store.set('view', view);
    if (!opts.keepPeek) C.closePeek && C.closePeek({ quiet: true });
    C.nav(moved ? 'push' : 'replace');
    C.drawTop(); C.render(); if (!opts.keepScroll) window.scrollTo({ top: 0, behavior: C.reduce ? 'auto' : 'smooth' });
  };
  let rendering = false, shown = '';   // the view and project last drawn: the enter animation plays only when they change
  C.render = () => {
    if (rendering) return;   // a field's blur that saves while the page redraws: the redraw already shows the saved state
    rendering = true;
    try {
      const m = C.$('#main'); hideSkeleton(m);
      if (!C.P() && UI.view !== 'settings') UI.view = 'settings';
      const a = document.activeElement; if (a && m.contains(a)) a.blur();
      C.log('debug', 'render', `view ${UI.view} project ${UI.code} items ${D.S.items.length}`);
      const enter = shown !== UI.view + '|' + UI.code; shown = UI.view + '|' + UI.code;
      m.innerHTML = `<div class="view${enter ? ' enter' : ''}">${C.views[UI.view].html()}</div>`;
      C.views[UI.view].wire();
    } finally { rendering = false; }
  };
  C.refresh = () => { const y = scrollY; C.drawTop(); C.render(); scrollTo(0, y); if (UI.peek) C.redrawPeek && C.redrawPeek(); };
  C.setProject = code => { const moved = UI.code !== code; if (moved) C.log('info', 'nav', 'project ' + code); UI.code = code; C.store.set('project', code); UI.editing = false; UI.uc = ''; C.closePeek && C.closePeek({ quiet: true }); C.nav(moved ? 'push' : 'replace'); C.drawTop(); C.render(); };

  function projectMenu(anchor) {
    C.menu(anchor, [...C.live().map(p => ({ html: `<span>${C.esc(p.name)}<small>${D.S.items.filter(i => i.code === p.code && C.isOpen(i) && !i.archived).length} open items</small></span>`, selected: p.code === UI.code, onPick: () => { C.setProject(p.code); C.toast(`Switched to ${p.name}`); } })),
      { sep: true }, { html: `${C.icon('plus')} New project…`, onPick: () => C.projectForm(null) }, { html: `${C.icon('gear')} Project settings`, onPick: () => C.go('settings') }], { select: true });
  }

  let slashT = 0;
  /* ── keys: "/" opens ask clark (or Sneak peek inside a peek), ⌘J too; Esc closes the topmost thing ── */
  document.addEventListener('keydown', e => {
    if (openPop) { if (e.key === 'Escape') { e.preventDefault(); C.closePop(); return; } if (openPop.el._key && openPop.el._key(e)) return; }
    if (C.$('#dlg').open) return;
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'j') { e.preventDefault(); C.askToggle(); return; }
    /* Cmd or Ctrl+Z on the Dashboard, Work items and Milestones undoes the last change; a box or an editor keeps its own undo (#197) */
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && !e.altKey && !e.repeat && !e.isComposing && e.key.toLowerCase() === 'z' && ['dashboard', 'work', 'milestones'].includes(UI.view) && (UI.view !== 'dashboard' || UI.editing)
      && !document.querySelector('dialog[open]') && !openPop && !C.typing(document.activeElement) && !(C.edIsOpen && C.edIsOpen()) && !C.palOpen?.()) { e.preventDefault(); C.undoLast(); return; }
    if (e.key === '/' && C.keysOn() && !e.metaKey && !e.ctrlKey && !C.typing(document.activeElement)) {
      e.preventDefault();
      /* creaite's keys: "//" in a peek opens Sneak peek; a single "/" opens ask clark */
      if (UI.peek && !C.askIsOpen()) { if (slashT) { clearTimeout(slashT); slashT = 0; C.sneakOpen(); } else slashT = setTimeout(() => { slashT = 0; C.askOpen(); }, 450); }
      else C.askOpen();
      return;
    }
    if (e.key === 'Escape' && document.body.classList.contains('bfull') && !openPop && !UI.peek) { e.preventDefault(); document.body.classList.remove('bfull'); C.refresh(); return; }
    if (e.key === 'Escape') {
      if (C.slashOpen && C.slashOpen()) return;   // the editor's slash menu takes it
      if (C.sneakIsOpen && C.sneakIsOpen()) { e.preventDefault(); C.sneakClose(); return; }
      if (C.askIsOpen()) { e.preventDefault(); C.askClose(); return; }
      if (C.edIsOpen && C.edIsOpen()) return;   // an open editor handles its own Esc
      if (UI.peek) { e.preventDefault(); C.closePeek(); }
    }
  });

  /* ── first-load skeletons: grey blocks shaped like the page, in place of an empty page, until the data has loaded. They show only
     after 150 ms (a quick load never flashes them), are still unless motion is allowed (then a very gentle shimmer), and C.render removes them. ── */
  let skT = 0;
  C.skeleton = view => {
    const b = (c = '') => `<i class="skel ${c}"></i>`, row = () => `<div class="sk-row">${b('sk-sq')}${b('sk-ln')}${b('sk-pl')}${b('sk-pl')}</div>`, card = () => `<div class="sk-card">${b('sk-h')}${b('sk-t')}${b('sk-t s')}${b('sk-t')}</div>`;
    const body = view === 'work' ? `${b('sk-title')}<div class="sk-bar">${b('sk-seg')}${b('sk-seg')}${b('sk-seg s')}</div><div class="sk-card">${b('sk-h s')}${row()}${row()}${row()}${row()}</div><div class="sk-card">${b('sk-h s')}${row()}${row()}${row()}</div>`
      : view === 'milestones' ? `${b('sk-title')}<div class="sk-card">${b('sk-h s')}${b('sk-band')}${row()}${row()}${row()}</div>`
      : view === 'dashboard' ? `${b('sk-cover')}<div class="sk-tiles">${b('sk-tile')}${b('sk-tile')}${b('sk-tile')}</div>${card()}${card()}`
      : `${b('sk-title')}${card()}${card()}${card()}`;
    return `<span class="sr" role="status">Loading</span><div class="skel-wrap sk-${view}" aria-hidden="true">${body}</div>`;
  };
  C.showSkeleton = view => { const m = C.$('#main'); if (!m) return false; m.innerHTML = C.skeleton(view); m.classList.add('loading'); m.classList.remove('skel-on'); m.setAttribute('aria-busy', 'true');
    clearTimeout(skT); skT = setTimeout(() => m.classList.add('skel-on'), 150); return true; };
  const hideSkeleton = m => { clearTimeout(skT); m.classList.remove('loading', 'skel-on'); m.removeAttribute('aria-busy'); };

  /* ── start ── */
  C.start = async () => {
    { const h0 = navParse(location.hash); C.skelAtStart = C.showSkeleton(VIEWS[h0.v] ? h0.v : C.store.get('view', 'dashboard')); }
    await D.load();
    if (!C.live().some(p => p.code === UI.code)) UI.code = C.live()[0]?.code || '';
    const B = window.BRAND || {};
    C.$('#logoBtn').innerHTML = B.logo ? `<img src="${B.logo}" alt="Home">` : '<img class="app-ic" src="assets/clark-icon.svg" alt=""><span class="wm">clark</span><span class="sr">Home</span>';   // clark's icon when no client brand is set
    C.$('#logoBtn').addEventListener('click', () => C.go('dashboard'));
    C.$('#projBtn').addEventListener('click', e => { e.stopPropagation(); projectMenu(e.currentTarget); });
    C.$$('.tab').forEach(t => t.addEventListener('click', () => C.go(t.dataset.view)));
    /* the skip link is the first Tab stop (X7): it takes the focus to the page itself, without changing the address; the Help button shows on a phone (H1) */
    C.$('#skip').addEventListener('click', e => { e.preventDefault(); const m = C.$('#main'); m.setAttribute('tabindex', '-1'); m.focus({ preventScroll: true }); m.scrollIntoView({ behavior: 'auto', block: 'start' }); });
    C.$('#helpBtn').addEventListener('click', () => C.help.open());
    /* the profile circle: your initials, and a menu with Settings and Dark mode */
    C.$('#meBtn').addEventListener('click', e => { e.stopPropagation(); const me = D.S.profile || {}, dark = document.documentElement.dataset.theme === 'dark';
      C.menu(e.currentTarget, [{ lab: me.name ? me.name + (me.email ? ' · ' + me.email : '') : 'No name yet: add it in Settings › Profile' },
        ...(C.P() ? [{ html: `${C.icon('ext')} Publish…`, onPick: () => { if (UI.view !== 'dashboard') C.go('dashboard'); C.publishDialog(); } }, { html: `${C.icon('eye')} Preview the page in a new tab`, onPick: () => C.publish('tab') }, { html: `${C.icon('dl')} Export to Excel`, onPick: () => C.exportExcel() }, { html: `${C.icon('doc')} Published reports`, onPick: () => { C.go('settings'); setTimeout(() => { const el = document.getElementById('pubs'); if (el) el.scrollIntoView({ block: 'start', behavior: C.reduce ? 'auto' : 'smooth' }); }, 60); } }, { html: `${C.icon('eye')} Past reports (mockup)`, onPick: () => C.go('past') }, { sep: true }] : []),   // the dashboard's Excel export moved here too (its tooltip was hidden under the cover)   // Publish lives here
        { html: `${C.icon('gear')} Settings`, onPick: () => C.go('settings') },
        { html: `${C.icon('info')} Help`, onPick: () => C.help.open() },
        { html: `${C.icon('moon')} Dark mode`, selected: dark, onPick: () => { C.themeSet(dark ? 'light' : 'dark'); if (UI.view === 'settings') C.render(); } }], { align: 'right' }); });
    C.$('#resetDemo').addEventListener('click', async () => { await D.reset(); C.undoClear(); UI.code = 'PDF'; C.closePeek(); C.askReset && C.askReset(); C.go('dashboard'); C.toast('Demo data reset'); });
    const h = navParse(location.hash);
    if (h.p && C.live().some(p => p.code === h.p)) UI.code = h.p;
    UI.view = VIEWS[h.v] ? h.v : C.store.get('view', 'dashboard');
    UI.uc = UI.view === 'usecases' ? h.u || '' : '';
    C.drawTop(); C.render();
    C.nav('replace');
    if (h.id) { C.navBusy = true; (h.k === 'ms' ? C.openMs : C.openItem)(h.id); C.navBusy = false; C.nav('replace'); }   // a reload or a bookmark opens the same peek
    document.documentElement.dataset.ready = '1';
  };
  document.addEventListener('DOMContentLoaded', () => { C.started = C.start(); });
})();
