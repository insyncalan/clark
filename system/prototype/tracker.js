/* The Progress tracker section (#189) and the Client Requested Report View page (#192, #433, #451), drawn as the owner-approved weekly progress snapshot.
   The tracker is a section template (Add a section › Figures › Progress tracker), Full or Half, edited in place, and shows actual against planned:
   three Overall tiles (health, Actual "of the whole project", Planned "by <date>"), a bar with a Planned label and a 0% to 100% scale, then one or more
   groups of plan lines (number, description, end, status, weight, planned, achieved with a small bar and a "down" chip when behind plan), each with its total.
   The page reads the same tracker, then the dashboard's This week and Next week text, then the open Risks and issues with the word Delay, Risk or Monitor.
   Typed, not derived: the user types weight, planned and achieved for each line; clark only adds up the totals.
   Anything a client sees shows nothing from Edit: no placeholders, no author instructions, no "Weights add up to" note, no empty template.
   The delivery plan template (#190) is on hold and is not drawn here: a third group on the page is an ordinary plan group.
   Demo data is fictional. */
(() => {
  const C = window.C, D = window.ClarkDB, esc = s => C.esc(s);
  /* status words, a fixed list (amber is kept for "at risk", so In progress is blue); health words as everywhere */
  const STATUS = [['planned', 'Planned', 'n'], ['inprogress', 'In progress', 'b'], ['completed', 'Completed', 'g'], ['late', 'Late', 'r']];
  const HEALTH = [['G', 'On track'], ['A', 'At risk'], ['R', 'Off track']];
  const COLS = [['start', 'Start'], ['tasks', 'Tasks'], ['agents', 'Agents'], ['workflows', 'Workflows']];
  const LIM = { groups: 10, lines: 47, name: 80, text: 100, no: 10, note: 100, count: 99999 };
  const MSG = {
    percent: 'A percentage must be a number from 0 to 100.', date: 'A date must be a real day written DD-MM-YYYY, or empty.', order: 'A line can’t end before it starts.',
    count: `A count must be a whole number from 0 to ${LIM.count}, or empty.`, total: 'The weight, planned and achieved figures can each add up to 100% at most.',
    text: `A line description can be ${LIM.text} characters at most.`, no: `A line number can be ${LIM.no} characters at most.`, name: `A group name can be ${LIM.name} characters at most.`, note: `The note can be ${LIM.note} characters at most.`,
    fullLines: `A tracker can have ${LIM.lines} lines in all. Remove one to add another.`, fullGroups: `A tracker can have ${LIM.groups} groups at most. Remove one to add another.`
  };
  C.TR = { STATUS, HEALTH, COLS, LIM, MSG };
  const r1 = n => Math.round(n * 10) / 10, fmt = n => String(r1(n));
  const isNum = v => typeof v === 'number' && isFinite(v) && v >= 0 && v <= 100;
  const num = v => (isNum(v) ? r1(v) : 0);
  const stOf = k => STATUS.find(s => s[0] === k) || STATUS[0];
  const pointsWord = b => `${fmt(b)} point${r1(b) === 1 ? '' : 's'} behind plan`;
  let seq = 0; const uid = p => p + Date.now().toString(36) + (seq++);
  C.trNew = () => ({ health: '', note: '', cols: {}, overall: { actual: null, planned: null }, groups: [{ id: uid('g'), name: '', lines: [] }] });

  /* the sums, worked out every time and never stored. pub: what a client sees (a line with no description, and a group with no lines, are left out) */
  C.trCalc = (tr, o = {}) => {
    tr = tr || {};
    const gs = (tr.groups || []).map(g => {
      const lines = (g.lines || []).filter(l => !o.pub || String(l.text || '').trim()).map(l => ({ ...l, behind: r1(Math.max(0, num(l.planned) - num(l.achieved))) }));
      const sum = k => r1(lines.reduce((a, l) => a + num(l[k]), 0)), t = { weight: sum('weight'), planned: sum('planned'), achieved: sum('achieved') };
      return { ...g, lines, ...t, behind: r1(Math.max(0, t.planned - t.achieved)), none: !lines.length };
    }).filter(g => !o.pub || g.lines.length);
    const n = gs.reduce((a, g) => a + g.lines.length, 0);
    let actual = null, planned = null;
    if (n) { actual = r1(gs.reduce((a, g) => a + g.achieved, 0)); planned = r1(gs.reduce((a, g) => a + g.planned, 0)); }
    else if (tr.overall && isNum(tr.overall.actual)) { actual = tr.overall.actual; planned = isNum(tr.overall.planned) ? tr.overall.planned : null; }
    return { groups: gs, lines: n, weight: r1(gs.reduce((a, g) => a + g.weight, 0)), cols: tr.cols || {}, overall: { actual, planned, behind: actual != null && planned != null ? r1(Math.max(0, planned - actual)) : 0, health: tr.health || '', note: tr.note || '' } };
  };
  /* a tracker with nothing in it is left out of the published page; one with only overall figures (the "just the bar" case) is kept */
  C.trHas = s => { const c = C.trCalc(s && s.tr, { pub: true }); return c.lines > 0 || c.overall.actual != null; };
  C.trSec = p => ((p || C.P()).report.sections || []).find(s => s.type === 'tracker' && !s.hidden);

  /* ── the pieces, drawn the same in View, on the page and in the published file ── */
  const behindChip = b => (b > 0 ? `<span class="behind" title="${pointsWord(b)}"><span aria-hidden="true">▼${fmt(b)}</span><span class="sr">${pointsWord(b)}</span></span>` : '');
  const place = pl => (pl >= 88 ? ' end' : pl <= 12 ? ' start' : '');
  const barHtml = o => o.actual == null ? '' : `<div class="tr-bar-w"><div class="tr-bar" role="img" aria-label="Actual ${fmt(o.actual)} percent${o.planned == null ? '' : ` against ${fmt(o.planned)} percent planned`}"><i class="fill" style="width:${o.actual}%"></i>${o.planned == null ? '' : `<i class="mk" style="left:${o.planned}%"></i><i class="mkl${place(o.planned)}" style="left:${o.planned}%">Planned ${fmt(o.planned)}%</i>`}</div>
      <div class="tr-scale" aria-hidden="true"><span>0%</span><span>100%</span></div></div>${o.behind > 0 ? `<p class="tr-gap">${pointsWord(o.behind)}</p>` : ''}`;
  /* the three Overall tiles (health, Actual "of the whole project", Planned "by <date>") and the bar under them */
  C.trOverallHtml = (c, o = {}) => {
    const v = c.overall, hw = (HEALTH.find(h => h[0] === (o.health != null ? o.health : v.health)) || [])[1], note = o.health != null ? o.note || '' : v.note;
    const hv = o.health != null ? o.health : v.health;
    if (v.actual == null && !hv) return '';
    const health = hv && hw ? `<div class="fig health-fig rag-${hv}" data-fig="health"><div class="k"><i class="ragdot"></i>${esc(o.healthLabel || 'Project health')}</div><div class="hrow"><span class="hpill ${hv}">${hw}</span>${note ? `<div class="hreason">${esc(note)}</div>` : ''}</div></div>` : '';
    const tiles = v.actual == null ? '' : `<div class="fig kpi" data-fig="actual"><div class="k">Actual</div><div class="v">${fmt(v.actual)}%</div><div class="d">of the whole project</div></div>${v.planned == null ? '' : `<div class="fig kpi" data-fig="planned"><div class="k">Planned</div><div class="v">${fmt(v.planned)}%</div><div class="d">${o.on ? `by ${D.fd(o.on)}` : 'so far'}</div></div>`}`;
    return `<div class="glance tr-tiles">${health}${tiles}</div>${barHtml(v)}`;
  };
  /* the Half fit: the same figures, smaller, then the bar */
  const halfFigs = (c, o) => { const v = c.overall, hw = (HEALTH.find(h => h[0] === v.health) || [])[1];
    if (v.actual == null && !hw) return '';
    return `<div class="tr-figs">${v.actual == null ? '' : `<div class="tr-fig"><span class="k">Actual</span><span class="v">${fmt(v.actual)}%</span></div>${v.planned == null ? '' : `<div class="tr-fig"><span class="k">Planned</span><span class="v">${fmt(v.planned)}%</span></div>`}`}${hw ? `<div class="tr-health"><span class="hpill ${v.health}">${hw}</span>${v.note ? `<span class="tr-note">${esc(v.note)}</span>` : ''}</div>` : ''}</div>${barHtml(v)}`; };

  const tplCols = (cols, edit) => { const opt = COLS.filter(([k]) => cols[k]), start = !!cols.start, cnt = opt.filter(([k]) => k !== 'start').length;
    const wide = ['28px', 'minmax(0,1fr)', ...(start ? ['104px'] : []), '104px', '112px', '64px', '64px', '190px', ...Array(cnt).fill('64px'), ...(edit ? ['112px'] : [])].join(' ');
    const narrow = ['28px', 'minmax(0,1fr)', '104px', '60px', '60px', '150px', ...(edit ? ['112px'] : [])].join(' ');
    return `--tc:${wide};--tn:${narrow}`; };
  const pctBar = l => `<span class="pbar"><i style="width:${l.weight > 0 ? Math.min(100, r1(l.achieved / l.weight * 100)) : 0}%"></i></span>`;
  const achieved = l => `<span class="pl-ach msl-prog" title="${fmt(l.achieved)}% achieved of a ${fmt(l.weight)}% weight">${pctBar(l)}<b>${fmt(l.achieved)}%</b>${behindChip(l.behind)}</span>`;
  const status = l => { const s = stOf(l.status); return `<span class="ucw ${s[2]}">${s[1]}</span>`; };
  const dateOf = iso => (iso ? D.fd(iso) : '<span class="muted">—</span>');
  const totalWords = g => `Total ${fmt(g.achieved)}% achieved · ${fmt(g.planned)}% planned · ${fmt(g.weight)}% weight${g.behind > 0 ? ` · ${pointsWord(g.behind)}` : ''}`;
  const groupHead = (g, tag = 'h3') => `<div class="pg-h">${g.name ? `<${tag}>${esc(g.name)}</${tag}>` : '<span></span>'}<span class="pg-t">${totalWords(g)}</span></div>`;
  const colHead = cols => `<span class="tr-no"></span><span>Description</span>${cols.start ? '<span class="tr-opt">Start</span>' : ''}<span class="tr-opt tr-end">End</span><span>Status</span><span class="pl-n">Weight</span><span class="pl-n">Planned</span><span>Achieved</span>${COLS.filter(([k]) => k !== 'start' && cols[k]).map(([, w]) => `<span class="pl-n tr-opt">${w}</span>`).join('')}`;
  const fullGroup = (g, cols) => `<div class="pg tr-g" data-tr-g="${esc(g.id)}">${groupHead(g)}${g.none ? '<p class="quiet tr-none">No lines yet</p>' : `<div class="pl-hd tr-row" style="${tplCols(cols)}" aria-hidden="true">${colHead(cols)}</div>
    <ul class="pl">${g.lines.map((l, i) => `<li class="pl-row tr-row" data-tr-line="${esc(l.id)}" style="${tplCols(cols)}"><span class="uc-tag">${esc(l.no || String(i + 1))}</span><span class="pl-name">${esc(l.text)}</span>${cols.start ? `<span class="pl-end tr-opt">${dateOf(l.start)}</span>` : ''}<span class="pl-end tr-opt tr-end">${dateOf(l.end)}</span>${status(l)}<span class="pl-n tr-w">${fmt(l.weight)}%</span><span class="pl-n tr-p">${fmt(l.planned)}%</span>${achieved(l)}${COLS.filter(([k]) => k !== 'start' && cols[k]).map(([k]) => `<span class="pl-n tr-opt">${l[k] == null ? '—' : l[k]}</span>`).join('')}</li>`).join('')}</ul>`}</div>`;
  const halfGroup = g => `<div class="pg tr-g tr-hg" data-tr-g="${esc(g.id)}">${groupHead(g)}${g.none ? '<p class="quiet tr-none">No lines yet</p>' : `<ul class="pl">${g.lines.map(l => `<li class="pl-row tr-hrow" data-tr-line="${esc(l.id)}"><span class="pl-name">${esc(l.text)}</span>${status(l)}<span class="pl-n"><span class="tr-pl">Planned</span> ${fmt(l.planned)}%</span>${achieved(l)}</li>`).join('')}</ul>`}</div>`;
  C.trGroupsHtml = (c, half) => c.groups.map(g => half ? halfGroup(g) : fullGroup(g, c.cols)).join('');

  /* the section: View and the published file (pub: the same, from the published rules) */
  C.trackerHtml = (s, editing, half, o = {}) => {
    if (editing) return trEditHtml(s, half);
    const c = C.trCalc(s.tr, { pub: true }), on = o.on || (C.P().week || D.friday());
    if (!c.lines && c.overall.actual == null) return '<p class="muted">Nothing is being tracked yet.</p>';
    return `<div class="tr${half ? ' tr-half' : ''}" data-tr-view>${half ? halfFigs(c, o) : C.trOverallHtml(c, { on, health: c.overall.health, note: c.overall.note, healthLabel: 'Health' })}${C.trGroupsHtml(c, half)}</div>`;
  };

  /* ── Edit: every value typed in place, one change at a time (one step with Undo) ── */
  function trEditHtml(s, half) {
    const c = C.trCalc(s.tr), t = s.tr || C.trNew(), sid = esc(s.id), cols = t.cols || {}, on = C.P().week || D.friday();
    const optN = COLS.filter(([k]) => k !== 'start' && cols[k]).length;
    const lab = (txt, inner) => `<label class="tr-l"><span class="k">${txt}</span>${inner}</label>`;
    const inp = (f, v, a = {}) => `<input class="field tr-in" data-tr-f="${esc(f)}" type="text" value="${esc(v == null ? '' : v)}" ${a.ph ? `placeholder="${esc(a.ph)}"` : ''} ${a.inputmode ? `inputmode="${a.inputmode}"` : ''} aria-label="${esc(a.label)}" autocomplete="off" spellcheck="${a.spell ? 'true' : 'false'}">`;
    const overallCtl = `<div class="tr-oc"><label class="tr-l"><span class="k">Health</span><select class="field tr-in" data-tr-f="~|health" aria-label="Health of the tracker"><option value="">Not set</option>${HEALTH.map(([k, w]) => `<option value="${k}"${t.health === k ? ' selected' : ''}>${w}</option>`).join('')}</select></label>
      ${lab('A line about it', inp('~|note', t.note, { label: 'A line about the health, in your own words', ph: 'One line, in your own words' }))}
      ${c.lines ? '' : `${lab('Actual %', inp('~|oa', t.overall && t.overall.actual != null ? t.overall.actual : '', { label: 'Overall actual percent', inputmode: 'decimal', ph: '0 to 100' }))}${lab('Planned %', inp('~|op', t.overall && t.overall.planned != null ? t.overall.planned : '', { label: 'Overall planned percent', inputmode: 'decimal', ph: '0 to 100' }))}`}</div>
      <fieldset class="tr-cols"><legend class="k">Show these columns</legend>${COLS.map(([k, w]) => `<label><input type="checkbox" data-tr-col="${k}" ${cols[k] ? 'checked' : ''}> ${w}</label>`).join('')}</fieldset>`;
    const lineRow = (g, l, li) => { const nm = `line ${li + 1} in ${g.name || 'the group'}`, f = k => `${g.id}|${l.id}|${k}`;
      return `<li class="tr-erow" data-tr-line="${esc(l.id)}" style="${tplCols(cols, true)}">${inp(f('no'), l.no, { label: `Number of ${nm}`, ph: String(li + 1) })}${inp(f('text'), l.text, { label: `Description of ${nm}`, ph: 'Describe the line', spell: true })}
        ${cols.start ? inp(f('start'), l.start ? D.fd(l.start) : '', { label: `Start of ${nm}`, ph: 'DD-MM-YYYY' }) : ''}${inp(f('end'), l.end ? D.fd(l.end) : '', { label: `End of ${nm}`, ph: 'DD-MM-YYYY' })}
        <select class="field tr-in" data-tr-f="${esc(f('status'))}" aria-label="Status of ${esc(nm)}">${STATUS.map(([k, w]) => `<option value="${k}"${l.status === k ? ' selected' : ''}>${w}</option>`).join('')}</select>
        ${inp(f('weight'), l.weight, { label: `Weight of ${nm}`, inputmode: 'decimal' })}${inp(f('planned'), l.planned, { label: `Planned of ${nm}`, inputmode: 'decimal' })}
        <span class="tr-ach">${inp(f('achieved'), l.achieved, { label: `Achieved of ${nm}`, inputmode: 'decimal' })}${behindChip(l.behind)}</span>
        ${COLS.filter(([k]) => k !== 'start' && cols[k]).map(([k, w]) => inp(f(k), l[k] == null ? '' : l[k], { label: `${w} of ${nm}`, inputmode: 'numeric' })).join('')}
        <span class="tr-tools"><button type="button" class="ib" data-tr-act="up:${esc(g.id)}:${esc(l.id)}" aria-label="Move ${esc(nm)} up" ${li ? '' : 'disabled'}>${C.icon('up', 's')}</button><button type="button" class="ib" data-tr-act="down:${esc(g.id)}:${esc(l.id)}" aria-label="Move ${esc(nm)} down" ${li < g.lines.length - 1 ? '' : 'disabled'}>${C.icon('down', 's')}</button><button type="button" class="ib" data-tr-act="rmline:${esc(g.id)}:${esc(l.id)}" aria-label="Remove ${esc(nm)}">${C.icon('trash', 's')}</button></span></li>`; };
    const gi = (g, i) => `<div class="pg tr-g tr-eg" data-tr-g="${esc(g.id)}"><div class="pg-h tr-gh">${inp(`${g.id}|~|name`, g.name, { label: `Name of group ${i + 1}`, ph: 'Group name', spell: true })}<span class="pg-t">${totalWords(g)}</span>
        <span class="tr-tools"><button type="button" class="ib" data-tr-act="gup:${esc(g.id)}" aria-label="Move the group ${esc(g.name || i + 1)} up" ${i ? '' : 'disabled'}>${C.icon('up', 's')}</button><button type="button" class="ib" data-tr-act="gdown:${esc(g.id)}" aria-label="Move the group ${esc(g.name || i + 1)} down" ${i < c.groups.length - 1 ? '' : 'disabled'}>${C.icon('down', 's')}</button><button type="button" class="ib" data-tr-act="rmgroup:${esc(g.id)}" aria-label="Remove the group ${esc(g.name || i + 1)}">${C.icon('trash', 's')}</button></span></div>
        ${g.none ? '<p class="quiet tr-none">No lines yet</p>' : `<div class="pl-hd tr-erow tr-ehd" style="${tplCols(cols, true)}" aria-hidden="true"><span>No.</span><span>Description</span>${cols.start ? '<span>Start</span>' : ''}<span>End</span><span>Status</span><span>Weight</span><span>Planned</span><span>Achieved</span>${COLS.filter(([k]) => k !== 'start' && cols[k]).map(([, w]) => `<span>${w}</span>`).join('')}<span></span></div>
        <ul class="pl">${g.lines.map((l, li) => lineRow(g, l, li)).join('')}</ul>`}
        <button type="button" class="btn sm" data-tr-act="addline:${esc(g.id)}">${C.icon('plus', 's')} Add a line</button></div>`;
    const wnote = c.lines && c.weight !== 100 ? `<p class="note tr-wnote">Weights add up to ${fmt(c.weight)}%. They do not have to reach 100%.</p>` : '';
    return `<div class="tr tr-edit${half ? ' tr-half' : ''}" data-tr-edit="${sid}">${overallCtl}
      <p class="nd-err tr-err" role="alert" data-tr-err="${sid}" hidden></p>
      ${half ? halfFigs(c, {}) : C.trOverallHtml(c, { on, health: t.health || '', note: t.note || '', healthLabel: 'Health' })}
      ${c.groups.map(gi).join('')}
      <button type="button" class="btn sm" data-tr-act="addgroup">${C.icon('plus', 's')} Add a group</button>${wnote}
      <p class="note">${half ? 'Half width shows the bar and a short list, with no dates. ' : ''}You type the weight, planned and achieved figures for each line; clark adds up the totals. A line behind plan shows ▼ and says how many points. The client sees the page as shown here, without these boxes. Everything in a visible tracker is published: there is no way to hide one line, so take a line out of the tracker if the client should not see it. Lines with no description and groups with no lines are left out of the published page.</p></div>`;
  }

  /* parse and check one typed value; returns { v } or { err } */
  const pct = raw => { const t = String(raw == null ? '' : raw).trim().replace(/%$/, '').trim().replace(',', '.'); if (!/^\d{1,3}(\.\d)?$/.test(t)) return null; const n = parseFloat(t); return n >= 0 && n <= 100 ? n : null; };
  const isoOf = raw => { const t = String(raw || '').trim(); if (!t) return ''; const m = /^(\d{2})-(\d{2})-(\d{4})$/.exec(t); if (!m) return null; const d = new Date(+m[3], +m[2] - 1, +m[1]); if (d.getFullYear() !== +m[3] || d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[1] || +m[3] < 2000 || +m[3] > 2100) return null; return `${m[3]}-${m[2]}-${m[1]}`; };
  const totalsOk = tr => ['weight', 'planned', 'achieved'].every(k => r1((tr.groups || []).reduce((a, g) => a + (g.lines || []).reduce((b, l) => b + num(l[k]), 0), 0)) <= 100);

  /* set one field on a copy of the tracker; returns an error message, or '' when it was applied */
  function setField(tr, spec, raw) {
    const [gid, lid, f] = spec.split('|'), val = String(raw == null ? '' : raw);
    if (gid === '~') {
      if (lid === 'health') { tr.health = ['G', 'A', 'R'].includes(val) ? val : ''; return ''; }
      if (lid === 'note') { if (val.trim().length > LIM.note) return MSG.note; tr.note = val.trim(); return ''; }
      if (lid === 'oa' || lid === 'op') { const k = lid === 'oa' ? 'actual' : 'planned', v = val.trim() === '' ? null : pct(val); if (val.trim() !== '' && v == null) return MSG.percent; tr.overall = tr.overall || {}; tr.overall[k] = v; return ''; }
      return '';
    }
    const g = (tr.groups || []).find(x => x.id === gid); if (!g) return '';
    if (lid === '~') { if (val.trim().length > LIM.name) return MSG.name; g.name = val.trim(); return ''; }
    const l = g.lines.find(x => x.id === lid); if (!l) return '';
    if (f === 'text') { if (val.trim().length > LIM.text) return MSG.text; l.text = val.trim(); }
    else if (f === 'no') { if (val.trim().length > LIM.no) return MSG.no; l.no = val.trim(); }
    else if (f === 'start' || f === 'end') { const iso = isoOf(val); if (iso == null) return MSG.date; const o = { ...l, [f]: iso }; if (o.start && o.end && o.end < o.start) return MSG.order; l[f] = iso; }
    else if (f === 'status') l.status = STATUS.some(s => s[0] === val) ? val : 'planned';
    else if (f === 'weight' || f === 'planned' || f === 'achieved') { const v = pct(val); if (v == null) return MSG.percent; const old = l[f]; l[f] = v; if (!totalsOk(tr)) { l[f] = old; return MSG.total; } }
    else if (f === 'tasks' || f === 'agents' || f === 'workflows') { const t = val.trim(); if (t === '') l[f] = null; else if (/^\d{1,5}$/.test(t)) l[f] = +t; else return MSG.count; }
    return '';
  }
  const secOf = (r, sid) => r.sections.find(x => x.id === sid);
  const newLine = () => ({ id: uid('l'), no: '', text: '', start: '', end: '', status: 'planned', weight: 0, planned: 0, achieved: 0, tasks: null, agents: null, workflows: null });
  const lineCount = tr => (tr.groups || []).reduce((a, g) => a + g.lines.length, 0);

  C.trWire = () => {
    C.$$('[data-tr-edit]').forEach(box => {
      const sid = box.dataset.trEdit, err = C.$('[data-tr-err]', box), say = m => { err.textContent = m; err.hidden = !m; };
      /* a refused change must not save: run it on a copy first, and only then hand it to setRep */
      const run = (fn, msg, focus) => { const s = C.rep().sections.find(x => x.id === sid), tr = D.clone(s.tr || C.trNew()), bad = fn(tr) || ''; if (bad) { say(bad); return false; } say('');
        if (JSON.stringify(tr) === JSON.stringify(s.tr || {})) return true; C.trFocus = focus || C.trFocus || ''; C.setRep(r => { secOf(r, sid).tr = tr; }, msg); return true; };
      C.$$('[data-tr-f]', box).forEach(el => el.addEventListener('change', () => {
        const spec = el.dataset.trF; el.removeAttribute('aria-invalid');
        const ok = run(tr => setField(tr, spec, el.value), 'Progress tracker changed', el.tagName === 'SELECT' ? spec : '');
        if (!ok) el.setAttribute('aria-invalid', 'true');
      }));
      C.$$('[data-tr-col]', box).forEach(el => el.addEventListener('change', () => run(tr => { tr.cols = tr.cols || {}; tr.cols[el.dataset.trCol] = el.checked; return ''; }, `${el.parentElement.textContent.trim()} column ${el.checked ? 'shown' : 'hidden'}`)));
      C.$$('[data-tr-act]', box).forEach(b => b.addEventListener('click', () => {
        const [act, gid, lid] = b.dataset.trAct.split(':');
        if (act === 'addgroup') { const g = { id: uid('g'), name: '', lines: [] }; run(tr => (tr.groups.length >= LIM.groups ? MSG.fullGroups : (tr.groups.push(g), '')), 'Group added', `${g.id}|~|name`); }
        else if (act === 'rmgroup') run(tr => { tr.groups = tr.groups.filter(g => g.id !== gid); if (!tr.groups.length) tr.groups.push({ id: uid('g'), name: '', lines: [] }); return ''; }, 'Group removed');
        else if (act === 'gup' || act === 'gdown') run(tr => { const i = tr.groups.findIndex(g => g.id === gid), j = i + (act === 'gup' ? -1 : 1); if (j < 0 || j >= tr.groups.length) return ''; [tr.groups[i], tr.groups[j]] = [tr.groups[j], tr.groups[i]]; return ''; }, 'Group moved', b.dataset.trAct);
        else if (act === 'addline') { const l = newLine(); run(tr => { if (lineCount(tr) >= LIM.lines) return MSG.fullLines; tr.groups.find(g => g.id === gid).lines.push(l); return ''; }, 'Line added', `${gid}|${l.id}|text`); }
        else if (act === 'rmline') run(tr => { const g = tr.groups.find(x => x.id === gid); g.lines = g.lines.filter(l => l.id !== lid); return ''; }, 'Line removed');
        else if (act === 'up' || act === 'down') run(tr => { const g = tr.groups.find(x => x.id === gid), i = g.lines.findIndex(l => l.id === lid), j = i + (act === 'up' ? -1 : 1); if (j < 0 || j >= g.lines.length) return ''; [g.lines[i], g.lines[j]] = [g.lines[j], g.lines[i]]; return ''; }, 'Line moved', b.dataset.trAct);
      }));
    });
    /* after a redraw the field that was being edited gets the keyboard back */
    if (C.trFocus) { const f = C.trFocus; C.trFocus = ''; const el = [...document.querySelectorAll('[data-tr-f],[data-tr-act]')].find(e => e.dataset.trF === f || e.dataset.trAct === f); if (el && !el.disabled) el.focus(); }
  };

  /* ═════════════ the Client Requested Report View ═════════════ */
  const RISK_WORD = { Delay: 'r', Risk: 'a', Monitor: 'n' }, RANK = { Delay: 0, Risk: 1, Monitor: 2 };
  /* the word for a risk or issue (a mapping, not a new field): an issue is a Delay; a High or Urgent risk is a Risk; any other risk is something to Monitor */
  C.crWord = x => (x.type === 'I' ? 'Delay' : x.priority === 'High' || x.priority === 'Urgent' ? 'Risk' : 'Monitor');
  C.crRisks = p => C.itemsAll().filter(x => x.code === p.code && !x.archived && x.client === true && (x.type === 'R' || x.type === 'I') && C.isOpen(x))
    .map(x => ({ x, word: C.crWord(x) })).sort((a, b) => RANK[a.word] - RANK[b.word] || (a.x.due || '9').localeCompare(b.x.due || '9') || a.x.id.localeCompare(b.x.id));
  const textOf = h => String(h || '').replace(/<[^>]*>/g, '').trim();
  const secText = (p, id, re) => { const s = p.report.sections.find(x => x.id === id) || p.report.sections.find(x => x.type === 'text' && re.test(x.title)); return s && !s.hidden && textOf(s.html) ? s : null; };
  const secH = (id, title) => `<section class="sec cr-sec" id="sec-cr-${id}" data-sec="cr-${id}"><h2 class="st"><span>${title}</span><span class="sp"></span></h2>`;
  const riskRow = r => { const x = r.x, owner = x.owner || '', back = x.due ? `${r.word === 'Monitor' ? 'Review by' : 'Back on track by'} ${D.fd(x.due)}` : '', esc2 = x.priority === 'Urgent' ? 'Yes' : 'No', resp = C.plain(x.update || '');
    return `<li class="wl-row" data-cr-risk="${esc(x.id)}" data-word="${r.word}"><span class="wl-state"><span class="pill ${RISK_WORD[r.word]}">${r.word}</span></span><span class="wl-main"><span class="wl-title">${esc(!x.clientText ? x.title : C.plain(x.clientText))}</span>
      <span class="wl-meta">${owner ? `<span class="av">${C.initials(owner)}</span>${esc(owner)}<span class="dot">·</span>` : ''}${back ? `<span>${back}</span><span class="dot">·</span>` : ''}<span>Escalate: ${esc2}</span></span>${resp ? `<span class="wl-resp">${esc(resp)}</span>` : ''}</span><span class="wl-id"><span class="idl">${esc(x.id)}</span></span></li>`; };
  /* the page body: the same in the editor and in the published tab. Anything with nothing to show is left out. */
  C.crBody = (p, o = {}) => {
    const week = p.week || D.friday(), s = C.trSec(p), c = s ? C.trCalc(s.tr, { pub: true }) : null, has = c && (c.lines || c.overall.actual != null);
    const hi = secText(p, 'thisweek', /this week|highlight/i), nx = secText(p, 'nextweek', /next week/i), risks = C.crRisks(p), out = [];
    const H = { G: 'On track', A: 'At risk', R: 'Off track' };
    if (has && c.overall.actual != null) out.push(`${secH('progress', 'Overall progress')}${C.trOverallHtml(c, { on: week, health: p.health, note: p.reason, healthLabel: 'Project health' })}</section>`);
    if (has && c.lines) out.push(`${secH('plans', 'Progress by plan')}<div class="tr" data-tr-view>${C.trGroupsHtml(c, false)}</div></section>`);
    const pair = [hi && `<section class="sec cr-sec" id="sec-cr-highlights" data-sec="cr-highlights"><h2 class="st"><span>Highlights</span><span class="sp"></span></h2><div class="prose">${hi.html}</div></section>`, nx && `<section class="sec cr-sec" id="sec-cr-nextweek" data-sec="cr-nextweek"><h2 class="st"><span>Planned for next week</span><span class="sp"></span></h2><div class="prose">${nx.html}</div></section>`].filter(Boolean);
    if (pair.length) out.push(pair.length > 1 ? `<div class="pair">${pair.join('')}</div>` : pair[0]);
    if (risks.length) out.push(`${secH('raid', 'Risks, delays and items to watch')}<ul class="wl cr-wl">${risks.map(riskRow).join('')}</ul></section>`);
    return out.join('');
  };
  C.crHas = p => !!C.crBody(p);
  C.crWeekLine = p => { const week = p.week || D.friday(), d = new Date(week + 'T00:00:00'); return `<b>WEEKLY PROGRESS SNAPSHOT</b> · Status as at ${C.dayName(week)} ${d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' })}${p.client ? ' · for ' + esc(p.client) : ''}`; };
  /* the published tab: its own dark band with the logo, title and the week line, then the same body */
  C.crPubHtml = p => { const B = window.BRAND || {}, body = C.crBody(p); if (!body) return '';
    return `<header class="cr-band"><h2>${esc(p.name)}</h2><div class="wk">${C.crWeekLine(p)}</div>${B.mark ? `<img class="mark" src="${B.mark}" alt="">` : ''}</header>${body}`; };

  C.views.report = {
    html() {
      const p = C.P(), B = window.BRAND || {}, body = C.crBody(p), s = C.trSec(p);
      return `<div class="rbar"><span class="state">${body ? 'Shown to the client as the Client report tab of the published page' : 'Nothing to show yet, so there is no Client report tab on the published page'}</span><span class="sp"></span>
        <button class="btn sm" id="crEdit">${C.icon('pencil', 's')} ${s ? 'Edit the progress tracker' : 'Add a progress tracker'}</button></div>
        <div class="dash-wrap lay-boxed cr-page" data-report="1"><article class="sheet"><header class="cover"><h1>${esc(p.name)}</h1><div class="wk">${C.crWeekLine(p)}</div>${B.mark ? `<img class="mark" src="${B.mark}" alt="">` : ''}</header>
          <div class="sbody">${body || `<p class="muted cr-empty">The weekly progress snapshot fills in from a Progress tracker, the This week and Next week text and the open risks and issues the client can see. None of them has anything to show yet.</p>`}</div></article></div>`;
    },
    wire() {
      C.$('#crEdit')?.addEventListener('click', () => {
        const have = C.trSec(C.P());
        C.go('dashboard'); C.UI.editing = true; C.render();
        if (have) setTimeout(() => C.$(`#sec-${have.id}`)?.scrollIntoView({ block: 'start', behavior: C.reduce ? 'auto' : 'smooth' }), 60);
        else setTimeout(() => { const b = C.$('.sh-ctl .sh-add'); if (b) b.click(); }, 80);
      });
    }
  };
})();
