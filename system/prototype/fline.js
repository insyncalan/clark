/* clark prototype: the filter line for Work items (#145, the prototype side of #137). One line for fields and plain words
   together, as GitHub's: field:value, -field:value (not), no:field (missing), a,b (either), dates in plain words, and plain
   words that search titles. This file reads and checks the line; views.js draws it as chips, with the list of suggestions.
   A prototype to try: nothing here is decided. */
(function () {
  'use strict';
  const C = window.C, D = C.D;

  /* ── the four open points of #137, each built as the recommended default and each one setting to change ── */
  const OPT = {
    /* the key that puts the cursor in the line on Work items ('' turns it off; ask clark keeps Ctrl or Cmd + J everywhere) */
    SLASH_KEY: '/',
    /* the syntax hint chips under the line: 'focus' (only while the line has the cursor), 'always' or 'never' */
    HINTS: 'focus',
    /* saved views: 'tabs' (the person's own views as tabs above the line, kept per project) or 'off' */
    VIEWS: 'tabs',
    /* the line is remembered per project: 'session' (until this browser tab closes), 'always' (kept in this browser) or 'never' */
    REMEMBER: 'session',
  };
  /* the views a project starts with; the person can change them and save more */
  const DEFAULT_VIEWS = [
    { id: 'open', name: 'Open items', line: 'is:open' },
    { id: 'overdue', name: 'Overdue', line: 'is:open due:overdue' },
    { id: 'client', name: 'Waiting on the client', line: 'is:open is:needed' },
    { id: 'mine', name: 'My actions', line: 'is:open type:action owner:me' },
  ];
  const BASE = 'is:open';   // the line a Work items page starts on, and the one "Clear all" goes back to

  const me = () => (D.S.profile || {}).name || '';
  const low = s => String(s ?? '').toLowerCase();
  const msOf = x => C.mss().find(m => m.id === x.ms);
  const ucOf = x => D.S.usecases.find(u => u.code === x.code && u.id === x.uc);
  /* each field: its plain name, the values an item has (the words you can type), the values to offer with their labels, and
     whether an item can be without one (for no:) */
  const FIELDS = {
    type: { t: 'Type', of: x => [{ A: 'action', R: 'risk', I: 'issue', D: 'decision' }[x.type]],
      opts: () => [['action', 'Action'], ['risk', 'Risk'], ['issue', 'Issue'], ['decision', 'Decision']] },
    status: { t: 'Status', of: x => [x.status], opts: () => [...new Set(Object.values(D.STATUSES).flat())].map(s => [s, s]) },
    owner: { t: 'Owner', of: x => x.owner ? [x.owner, ...(me() && x.owner === me() ? ['me'] : [])] : [], none: x => !String(x.owner || '').trim(),
      opts: () => [['me', me() ? 'Me (' + me() + ')' : 'Me (your name in Settings)'], ...[...new Set(C.items().map(x => x.owner).filter(Boolean))].sort().map(o => [o, o])] },
    priority: { t: 'Priority', of: x => [x.priority], opts: () => D.PRIORITIES.map(p => [p, p]) },
    due: { t: 'Due', none: x => !x.due, of: x => { if (!x.due) return ['none']; const n = D.days(x.due); return [n < 0 ? 'overdue' : '', n === 0 ? 'today' : '', n >= 0 && n <= 7 ? 'next-7-days' : '', n > 7 ? 'later' : ''].filter(Boolean); },
      opts: () => [['overdue', 'Overdue (the date has passed)'], ['today', 'Today'], ['next-7-days', 'In the next 7 days'], ['later', 'Later than 7 days'], ['none', 'No date']] },
    workstream: { t: 'Workstream', of: x => x.ws ? [x.ws] : [], none: x => !x.ws, opts: () => [...new Set([...(C.P()?.ws || []), ...C.items().map(x => x.ws).filter(Boolean)])].map(w => [w, w]) },
    usecase: { t: 'Use case', of: x => x.uc ? [x.uc] : [], none: x => !x.uc,
      opts: () => D.S.usecases.filter(u => u.code === C.P()?.code && !u.archived).map(u => [u.id, `${u.ref || u.id} ${u.title.split('\n')[0]}`]) },
    milestone: { t: 'Milestone', of: x => { const m = msOf(x); return m ? [m.name, m.id] : []; }, none: x => !x.ms, opts: () => C.mss().map(m => [m.name, m.name]) },
    client: { t: 'Client', of: x => x.client ? ['shown', 'yes'] : ['internal', 'no'], opts: () => [['shown', 'Shown to the client'], ['internal', 'Internal only']] },
    is: { t: 'Is', of: x => [C.isOpen(x) ? 'open' : 'closed', C.isOpen(x) && x.due && D.days(x.due) < 0 ? 'overdue' : '', D.notReviewed(x) ? 'quiet' : '', D.gap(x) ? 'incomplete' : '', x.clientAct ? 'needed' : ''].filter(Boolean),
      opts: () => [['open', 'Open'], ['closed', 'Closed'], ['overdue', 'Open and overdue'], ['quiet', 'Not reviewed in 14 days'], ['incomplete', 'Open, with no owner or no date'], ['needed', 'Needed from the client']] },
  };
  const ALIAS = { ws: 'workstream', uc: 'usecase', 'use-case': 'usecase', ms: 'milestone', prio: 'priority', state: 'status' };
  const NAMES = Object.keys(FIELDS);
  const NONE_OK = NAMES.filter(k => FIELDS[k].none);
  const list = (a, and = 'and') => a.length < 2 ? a.join('') : a.slice(0, -1).join(', ') + ' ' + and + ' ' + a[a.length - 1];
  const fieldOf = name => { const k = low(name); return FIELDS[k] ? k : ALIAS[k] || null; };
  /* the closest field name to a mistyped one (at most two letters out), for "Did you mean" */
  const dist = (a, b) => { const m = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]); for (let j = 1; j <= b.length; j++) m[0][j] = j;
    for (let i = 1; i <= a.length; i++) for (let j = 1; j <= b.length; j++) m[i][j] = Math.min(m[i - 1][j] + 1, m[i][j - 1] + 1, m[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1)); return m[a.length][b.length]; };
  const nearest = name => { const n = low(name), c = [...NAMES, ...Object.keys(ALIAS)].map(k => [k, dist(n, k)]).sort((a, b) => a[1] - b[1])[0]; return c && c[1] <= 2 ? fieldOf(c[0]) : (NAMES.find(k => k.startsWith(n) && n.length >= 2) || null); };
  const quote = v => /[\s,"]/.test(v) ? '"' + String(v).replace(/"/g, '') + '"' : v;

  /* split a line into its words, keeping "quoted words" together (a quote can follow a colon or a comma: owner:"First Last") */
  function words(s) {
    const out = []; let cur = '', q = false;
    for (const ch of String(s || '')) { if (ch === '"') { q = !q; cur += ch; } else if (/\s/.test(ch) && !q) { if (cur) out.push(cur); cur = ''; } else cur += ch; }
    if (cur) out.push(cur); return out;
  }
  const splitVals = s => { const out = []; let cur = '', q = false; for (const ch of s) { if (ch === '"') q = !q; else if (ch === ',' && !q) { out.push(cur); cur = ''; } else cur += ch; } out.push(cur); return out.map(v => v.trim()).filter(Boolean); };
  const isField = w => /^-?[A-Za-z][\w-]*:/.test(w);

  /* one word of the line, read: a condition, a plain word, or a plain-words error that says what the line can offer */
  function token(w) {
    if (!isField(w)) return { word: w.replace(/"/g, '') };
    const not = w.startsWith('-'), body = not ? w.slice(1) : w, i = body.indexOf(':'), name = body.slice(0, i), rest = body.slice(i + 1);
    if (low(name) === 'no') {
      const k = fieldOf(rest.replace(/"/g, ''));
      if (!rest) return { err: `Say which field: no:owner finds items with no owner. It works with ${list(NONE_OK)}.` };
      if (!k) return { err: `There is no “${rest}” field. no: works with ${list(NONE_OK)}.` };
      if (!FIELDS[k].none) return { err: `Every item has a ${FIELDS[k].t.toLowerCase()}, so no:${k} would find nothing. no: works with ${list(NONE_OK)}.` };
      return { field: k, none: true, not, vals: [], text: (not ? '-' : '') + 'no:' + k };
    }
    const k = fieldOf(name);
    if (!k) { const n = nearest(name); return { err: `There is no “${name}” filter.${n ? ` Did you mean ${n}?` : ''} You can filter by ${list(NAMES.map(x => x + ':'))}, or type plain words to search titles.`, near: n }; }
    const vs = splitVals(rest);
    if (!vs.length) return { err: `Say what ${FIELDS[k].t.toLowerCase()} to find, for example ${k}:${quote(FIELDS[k].opts()[0]?.[0] || 'value')}.`, field: k, partial: true };
    const known = new Map(); FIELDS[k].opts().forEach(([v]) => known.set(low(v), v)); C.items().forEach(x => FIELDS[k].of(x).forEach(v => known.has(low(v)) || known.set(low(v), v)));
    const bad = vs.filter(v => !known.has(low(v)));
    if (bad.length) { const offer = FIELDS[k].opts().map(o => o[0]); return { err: `“${bad[0]}” is not a value for ${FIELDS[k].t}. ${offer.length > 8 ? `Try ${offer.slice(0, 8).map(quote).join(', ')} and others. Type ${k}: to see them all.` : `Try ${list(offer.map(quote), 'or')}.`}`, field: k }; }
    const vals = vs.map(v => known.get(low(v)));
    return { field: k, not, vals, text: (not ? '-' : '') + k + ':' + vals.map(quote).join(',') };
  }
  /* the whole line: conditions, the plain words and any errors (a word with an error is left out, never applied) */
  function parse(line) {
    const out = { conds: [], words: [], errors: [] };
    words(line).forEach(w => { const t = token(w); if (t.err) out.errors.push({ raw: w, msg: t.err }); else if (t.word !== undefined) { if (t.word) out.words.push(t.word); } else out.conds.push(t); });
    return out;
  }
  const hit = (c, x) => { const F = FIELDS[c.field]; const yes = c.none ? F.none(x) : F.of(x).some(v => c.vals.some(w => low(w) === low(v))); return yes !== c.not; };
  /* plain words search titles (and the ID, so an ID typed in finds its item); every word has to be there */
  const wordsHit = (ws, x) => ws.every(w => low(x.title + ' ' + x.id).includes(low(w)));
  const match = (p, x) => p.conds.every(c => hit(c, x)) && wordsHit(p.words, x);
  /* a condition in plain words, for a chip's tooltip and the screen reader */
  function say(c) {
    const F = FIELDS[c.field], lab = v => (F.opts().find(o => low(o[0]) === low(v)) || [v, v])[1];
    if (c.none) return c.not ? `${F.t} is set` : `No ${F.t.toLowerCase()}`;
    if (c.field === 'is') return (c.not ? 'Leaves out: ' : '') + list(c.vals.map(lab), 'or');
    return `${F.t} ${c.not ? 'is not' : 'is'} ${list(c.vals.map(lab), 'or')}`;
  }
  /* a whole line in plain words, for a saved view's tooltip: each condition as say() puts it, then the words searched */
  function sayLine(line) {
    const p = parse(line), out = [...p.conds.map(say), ...(p.words.length ? [`Titles with ${list(p.words.map(w => `“${w}”`))}`] : [])];
    return out.length ? out.join('; ') : 'Everything';
  }
  /* owner:me finds nothing until the person's name is set in Settings: say so, rather than show 0 with no reason */
  const NO_ME = 'Add your name in Settings, then owner:me will find your items.';
  const needsMe = line => !me() && parse(line).conds.some(c => c.field === 'owner' && c.vals.some(v => low(v) === 'me'));
  const norm = line => { const p = parse(line); return [...p.conds.map(c => c.text), ...p.words].join(' '); };

  /* suggestions for the word being typed: the fields first, then a field's values with how many items have each */
  function suggest(word, base) {
    const w = word || '', not = w.startsWith('-'), body = not ? w.slice(1) : w;
    const count = (k, v) => base.filter(x => FIELDS[k].of(x).some(z => low(z) === low(v))).length;
    if (!body.includes(':')) {
      const n = low(body); if (w && !/^[a-z-]*$/i.test(w)) return [];
      const fs = NAMES.filter(k => k.startsWith(n)).map(k => ({ kind: 'field', ins: (not ? '-' : '') + k + ':', label: (not ? '-' : '') + k + ':', note: not ? `${FIELDS[k].t} is not…` : FIELDS[k].t }));
      const nos = !not && 'no:'.startsWith(n) && n ? [{ kind: 'field', ins: 'no:', label: 'no:', note: 'Has no owner, date…' }] : [];
      return [...fs, ...nos];
    }
    const i = body.indexOf(':'), name = body.slice(0, i), rest = body.slice(i + 1), lead = rest.lastIndexOf(',') + 1, done = rest.slice(0, lead), part = rest.slice(lead).replace(/"/g, '');
    if (low(name) === 'no') return NONE_OK.filter(k => k.startsWith(low(part))).map(k => ({ kind: 'value', ins: 'no:' + k, label: k, note: `No ${FIELDS[k].t.toLowerCase()}`, n: base.filter(FIELDS[k].none).length }));
    const k = fieldOf(name); if (!k) return [];
    return FIELDS[k].opts().filter(([v, l]) => low(v).includes(low(part)) || low(l).includes(low(part))).map(([v, l]) => ({ kind: 'value', ins: (not ? '-' : '') + k + ':' + done + quote(v), label: v, note: l !== v ? l : '', n: count(k, v) }));
  }

  /* the tiles' filters (Overdue actions, High risks and issues, Decisions needed, a use case, Freshness) as a line */
  function fromFilter(o = {}) {
    const t = [BASE];
    if (o.type && o.type !== 'all') t.push('type:' + ({ A: 'action', R: 'risk,issue', I: 'issue', D: 'decision' }[o.type]));
    const map = { due: { overdue: 'overdue', soon: 'next-7-days', later: 'later' } };
    if (o.due) { if (o.due.includes('none')) t.push('no:due'); const d = o.due.filter(v => v !== 'none').map(v => map.due[v] || v); if (d.length) t.push('due:' + d.join(',')); }
    if (o.status) t.push('status:' + o.status.map(quote).join(','));
    if (o.priority) t.push('priority:' + o.priority.join(','));
    if (o.uc) t.push('usecase:' + o.uc.map(quote).join(','));
    (o.fresh || []).forEach(f => t.push('is:' + ({ stale: 'quiet', gap: 'incomplete' }[f] || f)));
    return norm(t.join(' '));
  }

  /* where the line and the views are kept: the views in this browser, the line per project for the session (OPT.REMEMBER) */
  const mem = () => OPT.REMEMBER === 'session' ? sessionStorage : OPT.REMEMBER === 'always' ? localStorage : null;
  const lineGet = code => { try { const m = mem(); return m ? (JSON.parse(m.getItem('clark.fline') || '{}')[code] || null) : null; } catch (e) { return null; } };
  const linePut = (code, v) => { try { const m = mem(); if (!m) return; const all = JSON.parse(m.getItem('clark.fline') || '{}'); all[code] = v; m.setItem('clark.fline', JSON.stringify(all)); } catch (e) { /* private window */ } };
  const views = code => { const all = C.store.get('fviews', {}); return all[code] || DEFAULT_VIEWS.map(v => ({ ...v })); };
  const viewsPut = (code, vs) => { const all = C.store.get('fviews', {}); all[code] = vs; C.store.set('fviews', all); };

  C.fline = { NO_ME, needsMe, OPT, DEFAULT_VIEWS, BASE, FIELDS, NAMES, NONE_OK, words, token, parse, match, say, sayLine, norm, suggest, fromFilter, quote, isField, lineGet, linePut, views, viewsPut };
})();
