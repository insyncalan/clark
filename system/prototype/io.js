/* clark prototype: Excel in and out (a sheet each for actions, risks and issues, decisions, milestones and use cases) and
   Publish. The published web page holds only what the editor chose: anything left out is dropped before the file is made, never
   just hidden (ARCHITECTURE.md). On the page, items, milestones and use cases open read-only. */
(function () {
  'use strict';
  const C = window.C, D = C.D, esc = C.esc;
  const need = () => { if (window.XLSX) return true; C.toast('The Excel tools have not loaded. Check the internet connection and try again.'); return false; };
  const RAG = { R: 'Red', A: 'Amber', G: 'Green' };
  const ICOLS = ['ID', 'Type', 'Workstream', 'Title', 'Owner', 'Due', 'Status', 'Priority', 'Rating', 'Use case', 'Milestone', 'Client-visible', 'Client wording', 'Description', 'Latest update'];
  const MCOLS = ['ID', 'Milestone', 'Workstream', 'Original', 'Agreed', 'Forecast', 'Achieved', 'State', 'Progress', 'Owner', 'Client-visible', 'Description'];
  const UCOLS = ['ID', 'Shown as', 'Use case', 'Status', 'Headline', 'Where it stands', 'Client-visible', 'Open work items'];
  const txt = h => { const d = document.createElement('div'); d.innerHTML = h || ''; return d.innerText.trim(); };
  const irow = x => [x.id, D.TYPES[x.type], x.ws, x.title, x.owner, D.fd(x.due), x.status, x.priority, x.type === 'R' || x.type === 'I' ? RAG[C.ragOf(x)] : '', x.uc || '', C.msName(x.ms), x.client ? 'Yes' : 'No', C.plain(x.clientText), C.plain(x.desc), C.plain(x.update)];
  const mrow = m => [m.id, m.name, m.ws, D.fd(m.original), D.fd(m.agreed), D.fd(m.forecast), D.fd(m.achievedOn), D.msState(m), m.progress ?? '', m.owner, m.client ? 'Yes' : 'No', C.plain(m.desc)];
  const urow = u => [u.id, u.ref || '', u.title, u.status, u.headline, txt(u.standing), u.client ? 'Yes' : 'No', C.items().filter(x => x.uc === u.id && C.isOpen(x)).map(x => x.id).join(', ')];
  /* the History sheet (FR-43a): every change to the project's work items, milestones and use cases, newest first, in plain values */
  const HCOLS = ['When', 'Who', 'How', 'Item', 'Field', 'From', 'To'];
  const hcell = (f, v) => { const t = D.RICH.includes(f) ? C.plain(v) : D.showVal(f, v); return t === null ? null : String(t).slice(0, 32000); };
  const hrow = h => { const w = D.whoHow(h), life = { '+': 1, '-': 1, '*': 1 }[h.field];
    const name = h.kind === 'ms' ? (C.mssAll().find(m => m.id === h.id)?.name || '') : h.kind === 'uc' ? (D.S.usecases.find(u => u.code === h.code && u.id === h.id)?.title || '').split('\n')[0] : h.kind === 'item' ? (D.S.items.find(x => x.id === h.id)?.title || '') : (D.S.projects.find(x => x.code === h.code)?.name || '');
    const item = (h.kind === 'uc' ? 'Use case ' + h.id : h.kind === 'project' ? h.id + ' (project)' : h.id) + (name && h.kind !== 'project' ? ': ' + name : '');
    if (life) return [D.when(h), w.who, w.how, item, h.text || 'Changed', '', ''];
    const f = hcell(h.field, h.from), t = hcell(h.field, h.to);
    return [D.when(h), w.who, w.how, item, D.fieldName(h.field, h.kind), f === null ? '' : f, t === null ? 'changed' : t]; };
  const hrows = p => D.S.history.filter(h => h.code === p.code).slice().sort((a, b) => b.seq - a.seq).map(hrow);
  const sheet = (rows, widths) => { const ws = XLSX.utils.aoa_to_sheet(rows); ws['!cols'] = widths.map(w => ({ wch: w })); return ws; };

  C.exportExcel = (o = {}) => {
    if (!need()) return; const p = C.P(), wb = XLSX.utils.book_new(), its = C.items(), ucs = D.S.usecases.filter(u => u.code === p.code && !u.archived);
    if (o.only === 'usecases') XLSX.utils.book_append_sheet(wb, sheet([UCOLS, ...ucs.map(urow)], [8, 14, 44, 12, 44, 70, 12, 24]), 'Use cases');
    else {
      [['Actions', x => x.type === 'A'], ['Risks and issues', x => x.type === 'R' || x.type === 'I'], ['Decisions', x => x.type === 'D']].forEach(([n, f]) => XLSX.utils.book_append_sheet(wb, sheet([ICOLS, ...its.filter(f).map(irow)], [12, 10, 18, 46, 18, 12, 12, 10, 8, 10, 22, 12, 30, 40, 40]), n));
      XLSX.utils.book_append_sheet(wb, sheet([MCOLS, ...C.mss().map(mrow)], [6, 32, 20, 12, 12, 12, 12, 12, 10, 18, 12, 40]), 'Milestones');
      XLSX.utils.book_append_sheet(wb, sheet([UCOLS, ...ucs.map(urow)], [8, 14, 44, 12, 44, 70, 12, 24]), 'Use cases');
      XLSX.utils.book_append_sheet(wb, sheet([HCOLS, ...hrows(p)], [17, 22, 30, 44, 18, 40, 40]), 'History');
    }
    const name = `${D.TODAY} ${p.name} ${o.only === 'usecases' ? 'use cases' : 'work items'}.xlsx`;
    XLSX.writeFile(wb, name); C.toast(`Saved "${name}" to your downloads`);
  };
  C.importTemplate = () => { if (!need()) return; const wb = XLSX.utils.book_new(), p = C.P();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([ICOLS, ['', 'Action', p.ws[0], 'Example: agree the test dates', 'Sam Rivers', D.fd(D.addDays(D.TODAY, 7)), 'Open', 'Medium', '', '', '', 'No', '', '', '']]), 'Actions');
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([MCOLS, ['', 'Example: pilot go-live', p.ws[0], '', D.fd(D.addDays(D.TODAY, 60)), '', '', '', '', '', 'Yes', '']]), 'Milestones');
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([UCOLS, ['3.1', '', 'Example: automated report checks', 'On track', 'Specification signed', '', 'Yes', '']]), 'Use cases');
    XLSX.writeFile(wb, 'clark import template.xlsx'); };

  C.importExcel = () => C.dialog(`<div class="dlg-h"><h2>Import from Excel</h2><p>Sheets called Actions, Risks and issues, Decisions, Milestones and Use cases are read (a History sheet from an export is left alone). A row whose ID exists updates it; a row without an ID adds a new one. You see the changes before anything is saved.</p></div>
    <div class="dlg-b"><p class="muted">Columns, in any order (only the name or title is needed):</p><p style="font-size:13px"><b>Work items</b> ${ICOLS.join(', ')}<br><b>Milestones</b> ${MCOLS.join(', ')}<br><b>Use cases</b> ${UCOLS.slice(0, 7).join(', ')}</p></div>
    <div class="dlg-f"><button class="btn quiet" id="tpl" style="margin-right:auto">${C.icon('dl', 's')}Get the template</button><button class="btn quiet" data-close>Cancel</button><button class="btn pri" id="pick">${C.icon('ul', 's')}Choose a file</button></div>`, d => {
    C.$('#tpl', d).addEventListener('click', C.importTemplate);
    C.$('#pick', d).addEventListener('click', () => { if (need()) C.$('#fileIn').click(); });
  });

  const dateOf = s => { s = String(s || '').trim(); if (!s) return ''; let m = /^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$/.exec(s); if (m) return `${m[3]}-${D.pad(m[2])}-${D.pad(m[1])}`; m = /^(\d{4})-(\d{2})-(\d{2})/.exec(s); if (m) return m[0]; const d2 = new Date(s); return isNaN(d2) ? '' : D.toIso(d2); };
  const get = (r, k) => { const key = Object.keys(r).find(c => c.trim().toLowerCase() === k.toLowerCase()); return key ? String(r[key]).trim() : ''; };
  const yes = v => /^(yes|y|true|1)$/i.test(v);
  async function readFile(f) {
    const wb = XLSX.read(await f.arrayBuffer(), { cellDates: true }), p = C.P(), plan = { add: [], upd: [], skip: 0, arch: [], done: [] };
    const rows = n => wb.SheetNames.filter(s => s.trim().toLowerCase() === n).flatMap(s => XLSX.utils.sheet_to_json(wb.Sheets[s], { defval: '', raw: false }));
    const itemSheets = wb.SheetNames.filter(s => !['milestones', 'use cases', 'history'].includes(s.trim().toLowerCase()));   /* History is a record, never read back in */
    itemSheets.flatMap(s => XLSX.utils.sheet_to_json(wb.Sheets[s], { defval: '', raw: false })).forEach(r => {
      const title = get(r, 'Title'); if (!title) { plan.skip++; return; }
      const type = ({ action: 'A', risk: 'R', issue: 'I', decision: 'D' })[get(r, 'Type').toLowerCase()] || 'A', id = get(r, 'ID'), ex = id && D.S.items.find(x => x.id === id && x.code === p.code);
      const ms = C.mss().find(m => m.name.toLowerCase() === get(r, 'Milestone').toLowerCase());
      const v = { type, ws: get(r, 'Workstream') || p.ws[0], title, owner: get(r, 'Owner'), due: dateOf(get(r, 'Due')), status: D.STATUSES[type].find(s => s.toLowerCase() === ({ 'in progress': 'open', done: 'closed', agreed: 'made' }[get(r, 'Status').toLowerCase()] || get(r, 'Status').toLowerCase())) || D.STATUSES[type][0],
        priority: D.PRIORITIES.find(s => s.toLowerCase() === get(r, 'Priority').toLowerCase()) || ({ red: 'High', amber: 'Medium', green: 'Low' })[get(r, 'Rating').toLowerCase()] || 'Medium',
        uc: get(r, 'Use case'), ms: ms ? ms.id : '', client: get(r, 'Client-visible') ? yes(get(r, 'Client-visible')) : true, clientText: get(r, 'Client wording'), desc: get(r, 'Description'), update: get(r, 'Latest update') };
      if (ex && ex.archived) { plan.arch.push(ex.id); return; }   /* an archived record is read-only: the import leaves it alone and says so (#166) */
      (ex ? plan.upd : plan.add).push({ kind: 'item', ex, v });
    });
    rows('milestones').forEach(r => {
      const name = get(r, 'Milestone'); if (!name) { plan.skip++; return; }
      const id = get(r, 'ID'), ex = C.mssAll().find(m => (id && m.id === id) || m.name.toLowerCase() === name.toLowerCase()), agreed = dateOf(get(r, 'Agreed')) || ex?.agreed || D.addDays(D.TODAY, 30);
      const v = { name, ws: get(r, 'Workstream') || ex?.ws || p.ws[0], agreed, original: dateOf(get(r, 'Original')) || ex?.original || agreed, forecast: dateOf(get(r, 'Forecast')) || agreed, achievedOn: dateOf(get(r, 'Achieved')),
        manual: /at risk/i.test(get(r, 'State')) ? 'At risk' : /forecast/i.test(get(r, 'State')) ? 'Forecast' : '', progress: get(r, 'Progress') === '' ? (ex?.progress ?? null) : Math.min(100, +get(r, 'Progress') || 0), owner: get(r, 'Owner'), client: get(r, 'Client-visible') === '' ? (ex ? ex.client : true) : yes(get(r, 'Client-visible')), desc: get(r, 'Description') };
      if (ex && ex.archived) { plan.arch.push(ex.name); return; }
      (ex ? plan.upd : plan.add).push({ kind: 'ms', ex, v });
    });
    rows('use cases').forEach(r => {
      const id = get(r, 'ID'), title = get(r, 'Use case'); if (!id || !title) { plan.skip++; return; }
      const ex = D.S.usecases.find(u => u.code === p.code && u.id === id), std = get(r, 'Where it stands');
      /* a use case's status is one of four, Done among them (#412): a sheet's Done comes in as Done */
      const st = get(r, 'Status');
      const v = { id, ref: get(r, 'Shown as'), title, status: ['On track', 'Flag', 'High risk', 'Done'].find(s => s.toLowerCase() === st.toLowerCase()) || 'On track', headline: get(r, 'Headline'),
        standing: std ? std.split(/\n+/).map(t => `<p>${esc(t)}</p>`).join('') : (ex?.standing || ''), client: get(r, 'Client-visible') === '' ? true : yes(get(r, 'Client-visible')) };
      (ex ? plan.upd : plan.add).push({ kind: 'uc', ex, v });
    });
    return plan;
  }
  document.addEventListener('DOMContentLoaded', () => C.$('#fileIn').addEventListener('change', async e => {
    const f = e.target.files[0]; e.target.value = ''; if (!f) return;
    let plan; try { plan = await readFile(f); } catch (err) { C.toast('That file could not be read as a spreadsheet.'); return; }
    const p = C.P(), n = plan.add.length + plan.upd.length, cnt = k => [plan.add.filter(x => x.kind === k).length, plan.upd.filter(x => x.kind === k).length];
    const [ia, iu] = cnt('item'), [ma, mu] = cnt('ms'), [ua, uu] = cnt('uc');
    C.dialog(`<form id="impF"><div class="dlg-h"><h2>Check the import</h2><p>${esc(f.name)} into ${esc(p.name)}</p></div>
      <div class="dlg-b"><div class="stat"><span><b>${plan.add.length}</b>new</span><span><b>${plan.upd.length}</b>updated</span><span><b>${plan.skip}</b>skipped (no name)</span>${plan.arch.length ? `<span><b>${plan.arch.length}</b>left alone (archived)</span>` : ''}</div>
      <p style="margin:0 0 8px">Work items: ${ia} new, ${iu} updated · Milestones: ${ma} new, ${mu} updated · Use cases: ${ua} new, ${uu} updated</p>
      ${plan.arch.length ? `<p class="imp-arch" style="margin:0 0 8px">${plan.arch.map(esc).join(', ')} ${plan.arch.length === 1 ? 'is' : 'are'} archived, so ${plan.arch.length === 1 ? 'its row is' : 'their rows are'} left alone. Restore ${plan.arch.length === 1 ? 'it' : 'them'} first to update ${plan.arch.length === 1 ? 'it' : 'them'} from a sheet.</p>` : ''}
      ${[...plan.add, ...plan.upd].slice(0, 8).map(({ kind, ex, v }) => `<div style="padding:6px 0;border-top:1px solid var(--grey-100)">${kind === 'item' ? `<span class="type ${v.type}">${v.type}</span>` : `<span class="tag">${kind === 'ms' ? 'Milestone' : 'Use case'}</span>`} ${esc(v.title || v.name)} <span class="muted">· ${ex ? 'updates ' + esc(ex.id || ex.name) : 'new'}</span></div>`).join('')}
      ${n > 8 ? `<p class="muted">and ${n - 8} more</p>` : ''}</div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Cancel</button><button class="btn pri" ${n ? '' : 'disabled'}>Import ${n} rows</button></div></form>`, d => C.$('#impF', d).addEventListener('submit', ev => {
      ev.preventDefault(); d.close();
      const how = D.who('by Excel import (' + f.name + ')'), steps = [];
      plan.upd.forEach(({ kind, ex, v }) => steps.push(() => D.change(kind, ex, v, how)));
      plan.add.forEach(({ kind, v }) => {
        if (kind === 'item') steps.push(() => { if (!p.ws.includes(v.ws)) D.change('project', p, { ws: [...p.ws, v.ws] }, how); return D.create('item', { id: C.nextId(v.type), code: p.code, ...v, updatedAt: D.stamp(), source: f.name }, how); });
        if (kind === 'ms') steps.push(() => { const id = D.nextMsId(p.code); return D.create('ms', { key: p.code + '/' + id, id, code: p.code, clientText: '', ...v }, how); });
        if (kind === 'uc') steps.push(() => D.create('uc', { key: p.code + '/' + v.id, code: p.code, ...v }, how));
      });
      const u = D.batch(steps); C.refresh(); C.toast(`${n} rows imported`, u);
    }));
  }));

  /* ═════════════ publish ═════════════ */
  const word = x => C.plain(x.clientText) || x.title;
  /* the editor's styles for the timeline, the milestone list and the work item rows, copied from app.css when this prototype was built */
  /* the published page takes the editor's own rules (app-css.js, a copy of app.css): only those whose classes the page uses,
     leaving out the editor's frame (the page has its own cover, tabs and contents) */
  const PAGE_OWN = /\.(cover|hero|hero-tiles|tabsbar|grid|view|spinegrid|spine|spine-h|coverlay|solo|toc|toc-[\w-]+|lay-[\w-]+|sheet|sbody|rbar|topbar)(?![\w-])/;
  function pubCss(html) {
    const used = new Set(['open', 'on', 'sel', 'shut', 'hot']);
    html.replace(/class="([^"]*)"/g, (_, c) => c.split(/\s+/).forEach(k => k && used.add(k)));
    const keep = sel => { sel = sel.trim(); if (sel.startsWith(':root')) return true; if (PAGE_OWN.test(sel) || sel.includes('contenteditable')) return false;
      const cls = sel.replace(/:(not|has)\((?:[^()]|\([^()]*\))*\)/g, '').match(/\.[\w-]+/g); return !!cls && cls.every(c => used.has(c.slice(1))); };
    const sheet = new CSSStyleSheet(); sheet.replaceSync(window.CLARK_APPCSS || '');
    const walk = rules => [...rules].map(r => {
      if (r instanceof CSSStyleRule) { const sels = r.selectorText.split(/,(?![^()]*\))/).filter(keep); return sels.length ? sels.join(',') + r.cssText.slice(r.cssText.indexOf('{')) : ''; }
      if (r instanceof CSSMediaRule) { const inner = walk(r.cssRules); return inner ? `@media ${r.conditionText}{${inner}}` : ''; }
      if (r instanceof CSSKeyframesRule) return r.cssText;
      return '';
    }).filter(Boolean).join('\n');
    return walk(sheet.cssRules);
  }
  function pubData() {
    const p = C.P(), r = p.report, its = C.items().filter(x => x.client), ms = C.mss().filter(m => m.client), ucs = D.S.usecases.filter(u => u.code === p.code && u.client && !u.archived);
    return { p, r, its, ms, ucs, secs: C.pubOrder(r.sections).filter(s => C.onPub(s, p)), docs: (p.docs || []).filter(d => !d.hidden && !d.archived), glance: r.glance.filter(f => !f.hidden && f.k !== 'stale') };   /* the Not reviewed tile is for you only: never in the published page or the Word file */
  }
  /* the use case summary as the editor shows it in View mode, every row closed; a row's links open the item's detail */
  function ucView(p) {
    const was = C.store.get('ucOpen', ''); C.store.set('ucOpen', '');
    const h = C.ucTableHtml(p, false); C.store.set('ucOpen', was);
    return h.replace(/data-open=/g, 'data-item=').replace(/<div class="ucd-acts">.*?<\/div>/gs, '');
  }
  function pageHtml(forWord) {
    const { p, its, ms, ucs, secs, docs, glance } = pubData(), B = window.BRAND || {}, week = p.week || D.friday(), H = { G: 'On track', A: 'At risk', R: 'Off track' };
    const g = C.glanceData(p), st = x => { const [c, t] = C.look(x); return `<span class="st-${c}">${esc(t)}</span>`; };
    const open = (x, label) => forWord ? esc(label) : `<a href="#" data-item="${x.id}">${esc(label)}</a>`;
    const tbl = (head, rows) => rows.length ? `<table><tr>${head.map(h => `<th>${h}</th>`).join('')}</tr>${rows.map(r2 => `<tr>${r2.map(c => `<td>${c}</td>`).join('')}</tr>`).join('')}</table>` : '<p class="muted">Nothing to show this week.</p>';
    const sec = s => {
      let b = '';
      if (s.type === 'current') b = `<div class="prose">${p.current || ''}</div>`;
      if (s.type === 'glance') b = forWord ? `<p>${glance.map(f => f.k === 'health' ? `<b>Project health: ${H[p.health]}.</b> ${esc(p.reason)}` : g[f.k] ? `<span class="fig"><b>${g[f.k].v}</b> ${g[f.k].k}</span>` : '').join(' ')}</p>` : C.glanceHtml(p, p.report, false, true);
      if (s.type === 'usecases') b = ucs.length ? (forWord ? tbl(['ID', 'Use case', 'Status', 'Headline'], ucs.map(u => [`<b>${esc(u.ref || u.id)}</b>`, esc(u.title).replace(/\n/g, '<br>'), `<b>${esc(u.status.toUpperCase())}</b>`, esc(u.headline)]))
        : ucView(p)) : '<p class="muted">No use cases to show.</p>';
      if (s.type === 'milestones') {
        if (forWord) b = tbl(['Milestone', 'State', 'Date', 'Progress'], ms.map(m => { const stt = D.msState(m); return [esc(m.clientText || m.name), `<span class="st-${{ Achieved: 'g', 'On track': 'g', 'At risk': 'a', Slipped: 'r', Overdue: 'r', Forecast: 'b' }[stt]}">${D.msWord(stt, true)}</span>`, stt === 'Achieved' ? 'Achieved ' + D.fd(m.achievedOn) : D.fd(m.agreed) + (D.slip(m) > 0 ? ` <span class="st-r">(expected ${D.fd(D.expected(m))})</span>` : ''), m.progress == null ? '' : m.progress + '%']; }));
        else { const host = document.createElement('div'); host.style.cssText = 'position:absolute;left:-9999px;width:900px'; document.body.appendChild(host); C.timeline(host, ms, { key: 'pub' }); const tl = host.innerHTML; host.remove();
          const list = C.msListHtml(ms, false, 'pub');
          b = `${C.msViewsHtml(ms, 'pub', `<div class="tl">${tl.replace(/<span class="mv-zoom">.*?<\/span>(?=<\/div><div class="mv-wrap")/s, '')}</div>`)}${list}`; }
      }
      if (s.type === 'text') b = `<div class="prose">${s.html || '<p class="muted">Nothing recorded.</p>'}</div>`;
      if (s.type === 'raid' || s.type === 'actions' || s.type === 'decisions') b = forWord
        ? ({ raid: () => tbl(['ID', 'Risk or issue', 'Priority', 'Owner', 'Response'], its.filter(x => (x.type === 'R' || x.type === 'I') && C.isOpen(x)).map(x => [x.id, esc(word(x)), esc(x.priority), esc(x.owner), esc(C.plain(x.update))])),
            actions: () => tbl(['ID', 'Action', 'Owner', 'Due', 'Status'], its.filter(x => x.type === 'A' && C.isOpen(x)).sort((a, b2) => (a.due || '9').localeCompare(b2.due || '9')).map(x => [x.id, esc(word(x)), esc(x.owner), D.fd(x.due), st(x)])),
            decisions: () => tbl(['Date', 'Decision', 'By', 'Status'], its.filter(x => x.type === 'D' && (x.status === 'Pending' || (x.due && D.days(x.due) >= -14))).map(x => [D.fd(x.due), esc(word(x)), esc(x.owner), st(x)])) })[s.type]()
        : C.itemListHtml(s.type, false).replace(/data-open=/g, 'data-item=');
      if (s.type === 'needs') b = forWord ? tbl(['ID', 'What is needed', 'Owner', 'Needed by'], C.needsRows(p, s).map(r2 => r2.src === 'item' ? [r2.x.id, esc(word(r2.x)), esc(r2.x.owner || C.ND_NOONE), C.needsDue(r2.x.due)] : ['', esc(r2.a.what), esc(r2.a.owner || C.ND_NOONE), C.needsDue(r2.a.due)])) : C.needsHtml(false, true, s).replace(/data-open=/g, 'data-item=');
      if (s.type === 'docs') b = forWord ? (docs.length ? `<ul>${docs.map(d => `<li><a href="${esc(d.url)}">${esc(d.title)}</a> · ${esc(d.kind)} · ${D.fd(d.date)}</li>`).join('')}</ul>` : '<p class="muted">No documents linked.</p>') : C.docsHtml(p, false);
      return `<section id="sec-${s.id}"><h2>${esc(s.title)}</h2>${b}</section>`;
    };
    const lay = forWord ? 'boxed' : C.layOf(p), gl = secs.find(x => x.type === 'glance'), glanceTop = gl && lay !== 'boxed' ? sec(gl).replace(/^<section[^>]*><h2>.*?<\/h2>/, '').replace(/<\/section>$/, '') : '';
    /* the rows as the editor lays them out (#95): a pair becomes two columns on the page; the Word file keeps one column */
    const body = C.secRows(C.pubOrder(p.report.sections).filter(x => !(lay !== 'boxed' && x.type === 'glance')), x => C.onPub(x, p)).map(row => row.length > 1 && !forWord ? `<div class="pair">${row.map(sec).join('')}</div>` : row.map(sec).join('')).join('');
    /* the client's other two views: every work item and milestone shown to them, read-only */
    const lists = forWord ? '' : ['actions', 'raid', 'decisions'].map(t => `<section><h2>${{ actions: 'Actions', raid: 'Risks and issues', decisions: 'Decisions' }[t]}</h2>${C.itemListHtml(t, false).replace(/data-open=/g, 'data-item=')}</section>`).join('');
    let msView = '';
    if (!forWord) { const host = document.createElement('div'); host.style.cssText = 'position:absolute;left:-9999px;width:900px'; document.body.appendChild(host); C.timeline(host, ms, { key: 'pub' }); const tl = host.innerHTML; host.remove();
      const list = C.msListHtml(ms, false, 'pub');
      msView = `<section><h2>Milestones</h2>${C.msViewsHtml(ms, 'pub', `<div class="tl">${tl.replace(/<span class="mv-zoom">.*?<\/span>(?=<\/div><div class="mv-wrap")/s, '')}</div>`)}${list}</section>`; }
    const vals = k => [...new Set(its.map(x => ({ owner: x.owner, status: C.look(x)[1], priority: x.priority, dueb: !x.due ? 'No date' : D.days(x.due) < 0 ? 'Overdue' : D.days(x.due) <= 7 ? 'Due in 7 days' : 'Later', ws: x.ws })[k]).filter(Boolean))].sort();
    /* the Use Cases tab (#162): only the use cases on the dashboard, view only */
    const ucTab = forWord ? '' : `<section><h2>Use Cases</h2>${C.ucPubHtml(p)}</section>`;
    const cfbar = forWord ? '' : `<div class="cfbar"><div class="cfseg" role="group" aria-label="Type">${[['all', 'All'], ['A', 'Actions'], ['R', 'Risks and issues'], ['D', 'Decisions']].map(([v, t]) => `<button data-ft="${v}">${t}</button>`).join('')}</div><input class="wsearch" id="wq" type="search" placeholder="Search the work items" aria-label="Search the work items"></div><div class="cfbar" role="group" aria-label="Filter by"><span class="cfl">Filter by</span>${[['ws', 'Workstream'], ['status', 'Status'], ['dueb', 'Due'], ['owner', 'Owner'], ['priority', 'Priority']].map(([k, t]) => `<select data-cf="${k}" aria-label="${t}"><option value="">${t}: all</option>${vals(k).map(v => `<option>${esc(v)}</option>`).join('')}</select>`).join('')}</div><div class="cfchips" id="cfChips"></div>`;
    return { p, B, week, H, body, lay, cfbar, glance: glanceTop, toc: forWord ? '' : C.tocHtml(p, secs.filter(x => !(lay !== 'boxed' && x.type === 'glance'))), lists, msView, ucTab, its, ms };
  }
  /* [hidden] wins over every display rule (#138): the editor's own rule for it has no class, so pubCss leaves it out, and the work item rows' display:grid
     then kept a row the client's filters had hidden on screen (Due: Overdue said 2 items, more showed) */
  const CSS = `:root{--navy:#14233A;--blue:#3B5BDB;--ink:#18232B;--muted:#5A6270;--line:#E0E2E5;--ctl:#878C92;--cyan:#4FD1E8}
*{box-sizing:border-box}[hidden]{display:none!important}button{font:inherit;color:inherit}.skip{position:absolute;left:12px;top:-60px;z-index:20;background:var(--navy);color:#fff;padding:10px 14px;border-radius:6px;text-decoration:none}.skip:focus{top:8px;outline:2px solid var(--cyan)}body{margin:0;background:#F3F5F8;color:var(--ink);font:400 15px/1.55 Inter,Arial,sans-serif}a{color:#2A4FE0}
.cover{position:relative;overflow:hidden;isolation:isolate;background:var(--navy);color:#fff;padding:32px max(24px,calc(50vw - 480px)) 26px}.cover::before{content:"";position:absolute;inset:0 0 0 40%;z-index:-1;background:var(--cover) center right/cover no-repeat;-webkit-mask-image:linear-gradient(90deg,transparent,#000 45%);mask-image:linear-gradient(90deg,transparent,#000 45%);opacity:.85}
.cover .lab{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--cyan)}.cover h1{margin:6px 0 2px;font-size:30px;font-weight:500}.cover .wk{color:rgba(255,255,255,.8);font-size:14px}.cover img{position:absolute;right:max(24px,calc(50vw - 480px));top:24px;height:60px}
.health{display:flex;gap:12px;align-items:center;margin-top:16px;flex-wrap:wrap}.hp{font-weight:500;font-size:13px;letter-spacing:.06em;text-transform:uppercase;padding:5px 11px;border-radius:4px;color:#fff}.hp.G{background:#0F7B5F}.hp.A{background:#E8A013;color:#18232B}.hp.R{background:#BE3A2B}
.tabsbar{position:sticky;top:0;z-index:5;background:var(--navy);display:flex;gap:2px;padding:0 max(16px,calc(50vw - 640px))}.tabsbar button{all:unset;cursor:pointer;color:rgba(255,255,255,.75);font-size:14px;padding:13px 14px;border-bottom:3px solid transparent}.tabsbar button:hover{color:#fff}.tabsbar button[aria-selected=true]{color:#fff;border-color:var(--cyan)}.tabsbar button:focus-visible{outline:2px solid var(--cyan);outline-offset:-6px}
.grid{max-width:1280px;margin:20px auto;padding:0 24px}.grid main{margin:0;max-width:none}.view{display:none}.view.on{display:block}.solo{max-width:1232px;margin:20px auto}
.toc{position:fixed;right:18px;top:50%;transform:translateY(-50%);z-index:6;outline:none}.toc-lines{display:grid;gap:7px;justify-items:end;padding:10px 4px 10px 14px;cursor:pointer}.toc-lines i{display:block;width:12px;height:2px;border-radius:2px;background:#D3D5D8;transition:width .2s}.toc-lines i.hot{background:#D9B98A}.toc-lines i.on{width:20px;background:var(--navy)}
.toc-card{position:absolute;right:0;top:50%;width:250px;padding:12px 10px 10px;background:#fff;border:1px solid var(--line);border-radius:8px;box-shadow:0 12px 32px rgba(0,0,0,.14);font-size:13px;opacity:0;visibility:hidden;transform:translate(8px,-50%);transition:opacity .16s,transform .16s,visibility 0s linear .16s}.toc.open .toc-card{opacity:1;visibility:visible;transform:translate(0,-50%);transition:opacity .22s .06s,transform .22s .06s}.toc.open .toc-lines{opacity:0}
.toc-h{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:500;margin:0 8px 6px}.toc ul{list-style:none;margin:0;padding:0}.toc a{display:flex;justify-content:space-between;gap:8px;padding:5px 8px;border-radius:5px;color:var(--muted);text-decoration:none}.toc a:hover{background:#E9EBEE;color:var(--ink)}.toc a.on{color:var(--navy);font-weight:500}.toc em{font-style:normal;font-size:12px;color:var(--muted)}.toc em.hot{color:#8A5200}.toc-top{all:unset;margin:6px 8px 0;font-size:12px;color:#2A4FE0;cursor:pointer}
main.open{background:transparent;border:0;padding:8px 4px 30px}.spinegrid{display:grid;grid-template-columns:300px minmax(0,1fr);gap:32px;max-width:1290px;margin:20px auto;padding:0 16px;align-items:start}.spine{position:sticky;top:64px;display:grid;gap:14px}.spine-h{font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:var(--muted);font-weight:500}.spine .glance{grid-template-columns:1fr 1fr}.spine .fig.health-fig{grid-column:1/-1}
.toc.toc-static{position:static;transform:none;border-top:1px solid var(--line);padding-top:12px}.toc.toc-static .toc-lines{display:none}.toc.toc-static .toc-card{position:static;opacity:1;visibility:visible;transform:none;width:auto;border:0;box-shadow:none;padding:0;background:transparent}
.cover.hero{padding-bottom:0;min-height:340px;display:flex;flex-direction:column}.cover.hero .verdict{max-width:52ch;font-size:19px;line-height:1.45;margin:18px 0 26px}.hero-tiles{margin-top:auto;transform:translateY(46px)}.hero-tiles .fig{background:#fff;border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.12);padding:14px 18px;border:0}.coverlay{margin-top:70px}
.toc-btn{display:none}
@media(max-width:1000px){.toc,.toc.toc-static{position:fixed;right:16px;bottom:16px;top:auto;transform:none;border:0;padding:0;z-index:6}.toc .toc-lines{display:none}.toc-btn{all:unset;box-sizing:border-box;display:inline-flex;align-items:center;gap:8px;min-height:40px;padding:8px 16px 8px 14px;border:1px solid var(--ctl);border-radius:999px;background:#fff;color:var(--ink);font-size:14px;box-shadow:0 6px 18px rgba(0,0,0,.16);cursor:pointer}.toc-btn:hover,.toc.open .toc-btn{background:#E9EBEE}.toc-btn:focus-visible{outline:2px solid var(--blue);outline-offset:2px}.toc .toc-card,.toc.toc-static .toc-card{position:absolute;right:0;top:auto;bottom:calc(100% + 8px);width:min(290px,calc(100vw - 32px));max-height:calc(100vh - 120px);overflow-y:auto;padding:12px 10px 10px;background:#fff;border:1px solid var(--line);border-radius:8px;box-shadow:0 12px 32px rgba(0,0,0,.14);opacity:0;visibility:hidden;transform:translateY(8px);transition:opacity .16s,transform .16s,visibility 0s linear .16s}.toc.open .toc-card,.toc.toc-static.open .toc-card{opacity:1;visibility:visible;transform:none;transition:opacity .22s,transform .22s,visibility 0s}.toc a{min-height:32px;align-items:center}.toc-top{display:inline-flex;align-items:center;min-height:24px}}
@media(max-width:1000px) and (prefers-reduced-motion:reduce){.toc .toc-card,.toc.open .toc-card,.toc.toc-static .toc-card{transition:none;transform:none}}
@media(max-width:1000px){.spinegrid{grid-template-columns:1fr}.spine{position:static}.hero-tiles{transform:none;margin-bottom:16px}.coverlay{margin-top:20px}}.wsearch{width:100%;max-width:360px;padding:8px 12px;border:1px solid var(--ctl);border-radius:6px;font:inherit;margin:4px 0 8px}
main{max-width:1232px;margin:20px auto;background:#fff;border:1px solid var(--line);border-radius:8px;padding:8px 40px 36px}section{padding:20px 0 4px;scroll-margin-top:56px}
h2{display:flex;align-items:center;gap:10px;font-size:19px;font-weight:500;color:var(--navy);margin:0 0 10px;padding-bottom:8px;border-bottom:1px solid var(--line)}h2::before{content:"";width:9px;height:9px;background:var(--blue)}
table{width:100%;border-collapse:separate;border-spacing:2px;font-size:14px}th{background:var(--blue);color:#fff;text-align:left;font-weight:400;padding:7px 10px}td{background:#E0E2E5;padding:7px 10px;vertical-align:top}
.st-g{color:#0B654E;font-weight:500}.st-a{color:#8A5200;font-weight:500}.st-r{color:#A3301F;font-weight:500}.st-b{color:#2A4FE0;font-weight:500}.st-n{color:#5A6270;font-weight:500}.muted{color:var(--muted)}
#panel{position:fixed;top:0;right:0;bottom:0;width:min(460px,100vw);background:#fff;box-shadow:-12px 0 40px rgba(0,0,0,.15);transform:translateX(105%);transition:transform .25s cubic-bezier(.16,1,.3,1);z-index:10;padding:20px 24px;overflow-y:auto}#panel.on{transform:none}
#panel h3{font-size:22px;font-weight:500;margin:6px 0 14px}#panel dl{display:grid;grid-template-columns:120px 1fr;gap:8px;font-size:14px}#panel dt{color:var(--muted)}#panel button{float:right;border:1px solid var(--line);background:#fff;border-radius:6px;padding:4px 10px;cursor:pointer;font:inherit}.ro{font-size:12px;color:var(--muted)}
.cfbar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:0 0 10px}.cfbar .wsearch{margin:0 0 0 auto}.cfseg{display:inline-flex;border:1px solid var(--ctl);border-radius:999px;padding:3px;background:#fff}.cfseg button{all:unset;padding:5px 14px;border-radius:999px;cursor:pointer;font-size:14px;color:var(--muted)}.cfseg button[aria-pressed=true]{background:var(--navy);color:#fff}.cfl{font-size:13px;color:var(--muted)}.cfbar select{font:inherit;font-size:14px;padding:6px 10px;border:1px solid var(--ctl);border-radius:6px;background:#fff}.cfbar select.on{border-color:var(--blue);color:#2A4FE0}.cfchips{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font-size:13px;color:var(--muted);margin:0 0 12px}.cfchips .fchip{background:#E9EBEE;color:var(--ink);border-radius:4px;padding:2px 4px 2px 8px}.cfchips .fchip button{border:0;background:none;cursor:pointer;margin-left:2px}.cfchips .link{border:0;background:none;color:#2A4FE0;cursor:pointer;text-decoration:underline}
footer{max-width:1232px;margin:0 auto 40px;color:var(--muted);font-size:12px;padding:0 4px}
body::before{content:"";position:fixed;inset:0 0 0 40%;z-index:-1;pointer-events:none;background:var(--cover) center right/cover no-repeat;-webkit-mask-image:linear-gradient(90deg,transparent,#000 45%);mask-image:linear-gradient(90deg,transparent,#000 45%);opacity:.85;transform:scale(1.03);animation:bg-in .2s cubic-bezier(.16,1,.3,1) both}
html:not([data-dash=one]) main:not(.open){background:transparent;border:0;padding:0}
html:not([data-dash=one]) main:not(.open) section{background:#fff;border:1px solid var(--line);border-radius:8px;box-shadow:0 1px 2px rgba(19,35,42,.08),0 2px 8px rgba(19,35,42,.06);padding:22px 40px;margin-top:var(--sec-gap,10px)}
html:not([data-dash=one]) main:not(.open) section:first-child,html:not([data-dash=one]) main:not(.open)>.pair:first-child{margin-top:0}html[data-dash=roomy]{--sec-gap:22px}
html:not([data-dash=one]) main:not(.open) .pair{gap:var(--sec-gap,10px);margin-top:var(--sec-gap,10px)}html:not([data-dash=one]) main:not(.open) .pair>section{margin-top:0;padding-left:28px;padding-right:28px}html[data-dash=head] main:not(.open) .pair>section>h2{margin:0 -28px 14px;padding:12px 28px}
html[data-dash=head] main:not(.open) section{padding-top:0}html[data-dash=head] main:not(.open) section>h2{margin:0 -40px 14px;padding:12px 40px;background:#F3F5F8;border-radius:8px 8px 0 0}
@media(prefers-reduced-motion:reduce){body::before{animation:none;opacity:.85}}
@media(max-width:700px){main{padding:4px 18px 24px;margin:0;border-radius:0}.cover img{display:none}html:not([data-dash=one]) main:not(.open) section{padding:16px 18px}html[data-dash=head] main:not(.open) section>h2{margin:0 -18px 12px;padding:10px 18px}html:not([data-dash=one]) main:not(.open) .pair>section{padding-left:18px;padding-right:18px}html[data-dash=head] main:not(.open) .pair>section>h2{margin:0 -18px 12px;padding:10px 18px}}`;
  /* the print rules (FR-83b, #124): the page printed to PDF shows the four tabs one after another, no controls, sections kept whole, light only, with the publication
     number and the page number in the foot of each page (Chrome draws the @page margin boxes) */
  const printCss = n => `@media print{@page{size:A4;margin:14mm 12mm 18mm;${n ? '@bottom-left{content:"Publication ' + n + ' · ' + D.fd(D.TODAY) + '";font:9px Arial,sans-serif;color:#5A6270}' : ''}@bottom-right{content:"Page " counter(page);font:9px Arial,sans-serif;color:#5A6270}}
:root{color-scheme:light}*{-webkit-print-color-adjust:exact;print-color-adjust:exact}html,body{background:#fff!important;color:#18232B!important}
body::before,.tabsbar,.toc,#panel,.cfbar,.cfchips,.msv,.mv-bar,.wsearch,.ib,.mlg,.toc-top{display:none!important}
.view{display:block!important}.msl-row[data-more][hidden]{display:grid!important}.msl-all{display:none!important}#v-work,#v-milestones,#v-usecases{break-before:page}.grid,.solo,main{max-width:none;margin:0;padding:0}.cover{padding:16px 20px}
section,.pair>section,.wl-row,.ucr,tr,.msl-row{break-inside:avoid}.pair{display:block}html:not([data-dash=one]) main:not(.open) section{box-shadow:none;margin-top:8px;padding:14px 18px}
a{color:inherit;text-decoration:none}footer{margin:12px 0 0;padding:0}}`;
  /* clark's icon (assets/clark-icon.svg), carried inside the published file so its tab shows it with no outside address */
  const CLARK_ICON = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512" width="512" height="512" role="img" aria-label="clark"><title>clark</title><rect width="512" height="512" rx="112" fill="#14233A"/><rect x="87" y="87" width="225" height="225" rx="46" fill="none" stroke="#7C8BA1" stroke-width="18" stroke-dasharray="31 26"/><rect x="200" y="200" width="225" height="225" rx="46" fill="#3B5BDB"/><path d="M348 276A51 51 0 1 0 348 348" fill="none" stroke="#FFFFFF" stroke-width="28" stroke-linecap="round"/></svg>';
  async function dataUrl(u) { if (!u) return ''; if (u.startsWith('data:')) return u; try { const b = await (await fetch(u)).blob(); return await new Promise(r => { const f = new FileReader(); f.onload = () => r(f.result); f.readAsDataURL(b); }); } catch (e) { return ''; } }
  async function webPage(opts = {}) {
    const o = pageHtml(false), B = o.B, cover = await dataUrl(B.cover), mark = await dataUrl(B.mark);
    const data = { items: Object.fromEntries(o.its.map(x => [x.id, { id: x.id, kind: D.TYPES[x.type], title: word(x), owner: x.owner, due: D.fd(x.due), status: C.look(x)[1], priority: x.priority, t: x.type === 'I' ? 'R' : x.type, ws: x.ws, dueb: !x.due ? 'No date' : D.days(x.due) < 0 ? 'Overdue' : D.days(x.due) <= 7 ? 'Due in 7 days' : 'Later', update: C.plain(x.update), desc: C.plain(x.desc) }])),
      ms: Object.fromEntries(o.ms.map(m => [m.id, { title: m.clientText || m.name, state: D.msWord(D.msState(m), true), agreed: D.fd(m.agreed), forecast: D.slip(m) > 0 ? D.fd(D.expected(m)) : '', progress: m.progress == null ? 'Not set' : m.progress + '%', desc: C.plain(m.desc) }])) };
    const js = `const D=${JSON.stringify(data).replace(/</g, '\\u003c')};const P=document.getElementById('panel'),SM=matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth',esc=s=>String(s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function peek(h){P.innerHTML='<button onclick="P.classList.remove(\\'on\\')">Close</button><div class="ro">View only</div>'+h;P.classList.add('on');P.querySelector('button').focus()}
document.addEventListener('mousedown',e=>{if(!P.classList.contains('on')||e.button!==0)return;if(e.target.closest('#panel,[data-item],[data-ms],.wl-row'))return;P.classList.remove('on')},true);
document.addEventListener('click',e=>{const a=e.target.closest('[data-item],[data-ms]')||(!e.target.closest('a,button,input')&&e.target.closest('.wl-row')?.querySelector('[data-item]'));if(!a||a.closest('[data-mv]'))return;e.preventDefault();if(a.dataset.item){const x=D.items[a.dataset.item];if(!x)return;peek('<div class="ro">'+esc(x.id)+' · '+esc(x.kind)+'</div><h3>'+esc(x.title)+'</h3><dl><dt>Status</dt><dd>'+esc(x.status)+'</dd><dt>Owner</dt><dd>'+esc(x.owner)+'</dd><dt>Due</dt><dd>'+esc(x.due)+'</dd><dt>Priority</dt><dd>'+esc(x.priority)+'</dd><dt>Latest update</dt><dd>'+esc(x.update||'None')+'</dd>'+(x.desc?'<dt>About</dt><dd>'+esc(x.desc)+'</dd>':'')+'</dl>')}else{const m=D.ms[a.dataset.ms];if(!m)return;peek('<div class="ro">Milestone</div><h3>'+esc(m.title)+'</h3><dl><dt>State</dt><dd>'+esc(m.state)+'</dd><dt>Agreed date</dt><dd>'+esc(m.agreed)+'</dd>'+(m.forecast?'<dt>Expected</dt><dd>'+esc(m.forecast)+'</dd>':'')+'<dt>Progress</dt><dd>'+esc(m.progress)+'</dd>'+(m.desc?'<dt>About</dt><dd>'+esc(m.desc)+'</dd>':'')+'</dl>')}});
document.addEventListener('keydown',e=>{if(e.key==='Escape')P.classList.remove('on')});\n${C.MSV_JS}\ndocument.querySelectorAll('.msv').forEach(r=>msvWire(r,k=>{try{return localStorage.getItem('clark.msv.'+k)}catch(e){return ''}},(k,v)=>{try{localStorage.setItem('clark.msv.'+k,v)}catch(e){}}));\nfunction tlPlace(){document.querySelectorAll('.tl .mv-wrap').forEach(w=>{const td=w.querySelector('.mv-today');if(td&&w.clientWidth&&!w.dataset.placed){w.dataset.placed='1';w.scrollTo({left:Math.max(0,td.offsetLeft-w.clientWidth*.35),behavior:'instant'})}})}
document.querySelectorAll('.tl').forEach(t=>{const w=t.querySelector('.mv-wrap'),td=t.querySelector('.mv-today');t.querySelectorAll('[data-mv]').forEach(b=>b.addEventListener('click',()=>{const d=+b.dataset.mv;d?w.scrollBy({left:d*195,behavior:SM}):w.scrollTo({left:Math.max(0,td.offsetLeft-w.clientWidth*.35),behavior:SM})}))});tlPlace();
const L=[...document.querySelectorAll('[data-toc]')],LN=[...document.querySelectorAll('[data-tl]')];function spy(){let c=L[0];L.forEach(a=>{const s=document.getElementById('sec-'+a.dataset.toc);if(s&&s.getBoundingClientRect().top<innerHeight*.3)c=a});L.forEach(a=>a.classList.toggle('on',a===c));LN.forEach(l=>l.classList.toggle('on',c&&l.dataset.tl===c.dataset.toc))}addEventListener('scroll',spy,{passive:true});spy();
L.forEach(a=>a.addEventListener('click',e=>{e.preventDefault();document.getElementById('sec-'+a.dataset.toc)?.scrollIntoView({behavior:SM})}));document.querySelector('[data-totop]')?.addEventListener('click',()=>scrollTo({top:0,behavior:SM}));const TC=document.querySelector('.toc');if(TC){/* at 1000 px and below the rail is a compact On this page button that opens the same list (#141) */const NW=matchMedia('(max-width: 1000px)'),TS=TC.classList.contains('toc-static'),TB=TC.querySelector('.toc-btn');let ins=false,want=false;const st=()=>{const o=NW.matches?want:!TS&&(ins||TC.contains(document.activeElement));TC.classList.toggle('open',o);TB&&TB.setAttribute('aria-expanded',String(NW.matches&&o))};const md=()=>{TC.tabIndex=NW.matches?-1:0;want=false;ins=false;st()};TC.addEventListener('mouseenter',()=>{ins=true;st()});TC.addEventListener('mouseleave',()=>{ins=false;st()});TC.addEventListener('focusin',st);TC.addEventListener('focusout',()=>setTimeout(()=>{if(NW.matches&&!TC.contains(document.activeElement))want=false;st()},0));TB&&TB.addEventListener('click',()=>{want=!want;st();if(want)setTimeout(()=>TC.querySelector('.toc-card a')?.focus({preventScroll:true}),0)});TC.addEventListener('keydown',e=>{if(e.key==='Escape'&&NW.matches&&want){e.stopPropagation();want=false;st();TB&&TB.focus()}});TC.querySelectorAll('a,[data-totop]').forEach(a=>a.addEventListener('click',()=>{ins=false;want=false;a.blur();st()}));document.addEventListener('pointerdown',e=>{if(want&&!TC.contains(e.target)){want=false;st()}},true);NW.addEventListener('change',md);md()}
document.querySelector('.skip').addEventListener('click',e=>{e.preventDefault();const m=document.querySelector('.view.on main');if(m){m.setAttribute('tabindex','-1');m.focus({preventScroll:true});m.scrollIntoView()}});
const T=[...document.querySelectorAll('.tabsbar button')];function show(v){T.forEach(b=>b.setAttribute('aria-selected',b.dataset.v===v));document.querySelectorAll('.view').forEach(x=>x.classList.toggle('on',x.id==='v-'+v));tlPlace();scrollTo(0,0);try{history.replaceState(null,'','#'+v)}catch(e){}}T.forEach(b=>b.addEventListener('click',()=>show(b.dataset.v)));show(['work','milestones','usecases'].includes(location.hash.slice(1))?location.hash.slice(1):'dashboard');
const ucT=r=>{const d=r.nextElementSibling,on=!r.classList.contains('open');document.querySelectorAll('.ucr.open').forEach(x=>{x.classList.remove('open');x.setAttribute('aria-expanded','false');x.nextElementSibling.classList.remove('open')});if(on){r.classList.add('open');r.setAttribute('aria-expanded','true');d.classList.add('open')}};document.querySelectorAll('.ucr').forEach(r=>{r.addEventListener('click',e=>{if(!e.target.closest('[data-item]'))ucT(r)});r.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();ucT(r)}})});
document.querySelectorAll('[data-fig]:not([data-fig=health])').forEach(f=>{const go=()=>show('work');f.addEventListener('click',go);f.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go()}})});
/* the client filters work items as the editor does (#69): type, Filter by, chips, search; kept in this browser only */
const W=document.getElementById('wq'),CF={t:'all',f:{}};try{Object.assign(CF,JSON.parse(localStorage.getItem('clark.cf')||'{}'))}catch(e){}
const FK={owner:'Owner',status:'Status',priority:'Priority',dueb:'Due',ws:'Workstream'};
function cfRun(){const q=(W&&W.value||'').toLowerCase();let n=0;document.querySelectorAll('#v-work section').forEach(sec=>{let m=0;sec.querySelectorAll('.wl-row').forEach(r=>{const x=D.items[r.dataset.row]||{};const ok=(CF.t==='all'||x.t===CF.t)&&Object.entries(CF.f).every(([k,v])=>!v||x[k]===v)&&(!q||r.textContent.toLowerCase().includes(q));r.hidden=!ok;if(ok)m++});sec.hidden=!m&&(CF.t!=='all'||Object.values(CF.f).some(Boolean)||!!q);n+=m});
document.querySelectorAll('[data-ft]').forEach(b=>b.setAttribute('aria-pressed',b.dataset.ft===CF.t));document.querySelectorAll('[data-cf]').forEach(sl=>{sl.value=CF.f[sl.dataset.cf]||'';sl.classList.toggle('on',!!sl.value)});
const ch=document.getElementById('cfChips');if(ch){ch.innerHTML='<span>'+n+' item'+(n===1?'':'s')+'</span>'+Object.entries(CF.f).filter(([,v])=>v).map(([k,v])=>'<span class="fchip">'+FK[k]+': '+esc(v)+'<button data-cfx="'+k+'" aria-label="Remove the '+FK[k]+' filter">×</button></span>').join('')+((CF.t!=='all'||Object.values(CF.f).some(Boolean)||q)?'<button class="link" id="cfClear">Clear all</button>':'');
ch.querySelectorAll('[data-cfx]').forEach(b=>b.addEventListener('click',()=>{delete CF.f[b.dataset.cfx];cfSave()}));const cl=document.getElementById('cfClear');cl&&cl.addEventListener('click',()=>{CF.t='all';CF.f={};if(W)W.value='';cfSave()})}}
function cfSave(){try{localStorage.setItem('clark.cf',JSON.stringify(CF))}catch(e){}cfRun()}
document.querySelectorAll('[data-ft]').forEach(b=>b.addEventListener('click',()=>{CF.t=b.dataset.ft;cfSave()}));document.querySelectorAll('[data-cf]').forEach(sl=>sl.addEventListener('change',()=>{CF.f[sl.dataset.cf]=sl.value;cfSave()}));W&&W.addEventListener('input',cfRun);cfRun();
/* the milestones list shows five rows; Show all N lists the rest, and the same button takes it back */
document.querySelectorAll('[data-msmore]').forEach(b=>{const rows=()=>[...b.parentNode.querySelectorAll('.msl-row[data-more]')],n=rows().length+5;b.addEventListener('click',()=>{const on=b.getAttribute('aria-expanded')!=='true';rows().forEach(r=>{r.hidden=!on});b.setAttribute('aria-expanded',on?'true':'false');b.textContent=on?'Show the first 5':'Show all '+n})});
${C.UCP_JS}`;
    return `<!doctype html><html lang="en-GB" data-dash="${C.store.get('secs', 'slim')}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>${esc(o.p.name)}: week ending ${D.fd(o.week)}</title>
<link rel="icon" href="data:image/svg+xml,${encodeURIComponent(CLARK_ICON)}"><link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=Montserrat:wght@800&display=swap" rel="stylesheet"><style>${pubCss(o.body + o.lists + o.msView + o.ucTab + o.glance)}\n${(window.BRAND || {}).tokens || ''}\n${CSS}:root{--cover:${cover ? `url(${cover})` : 'none'}}\n${printCss(opts.n)}</style></head><body>
<a class="skip" href="#v-dashboard">Skip to content</a>
<header class="cover${o.lay === 'cover' ? ' hero' : ''}">${mark ? `<img src="${mark}" alt="">` : ''}<h1>${esc(o.p.name)}</h1><div class="wk"><b style="color:var(--cyan);font-weight:400">WEEKLY REPORT</b> · Week ending ${D.fd(o.week)}${o.p.client ? ' · for ' + esc(o.p.client) : ''}</div>${o.lay === 'cover' ? `<p class="verdict"><b>${o.H[o.p.health]}.</b> ${esc(o.p.reason)}</p><div class="hero-tiles">${o.glance}</div>` : ''}</header>
<nav class="tabsbar" aria-label="Views"><button data-v="dashboard">Dashboard</button><button data-v="work">Work items</button><button data-v="milestones">Milestones</button><button data-v="usecases">Use Cases</button></nav>
<div class="view" id="v-dashboard">${o.lay === 'spine' ? `<div class="spinegrid"><aside class="spine"><div class="spine-h">Project health</div>${o.glance}${o.toc.replace('class="toc"', 'class="toc toc-static"')}</aside><main class="open">${o.body}</main></div>` : `<div class="grid${o.lay === 'cover' ? ' coverlay' : ''}"><main${o.lay === 'cover' ? ' class="open"' : ''}>${o.body}</main>${o.toc}</div>`}</div>
<div class="view" id="v-work"><main class="solo">${o.cfbar}${o.lists}</main></div>
<div class="view" id="v-milestones"><main class="solo">${o.msView}</main></div>
<div class="view" id="v-usecases"><main class="solo">${o.ucTab}</main></div><footer>Published ${D.fd(D.TODAY)}. ${opts.n ? 'Publication ' + opts.n + ' · ' + D.fd(D.TODAY) + '. ' : ''}View only.</footer><aside id="panel" aria-label="Detail"></aside><script>${js}<\/script></body></html>`;
  }
  function wordDoc(opts = {}) {
    const o = pageHtml(true);
    return `<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:w="urn:schemas-microsoft-com:office:word" xmlns="http://www.w3.org/TR/REC-html40"><head><meta charset="utf-8"><title>${esc(o.p.name)}</title>
<style>body{font-family:Inter,Arial,sans-serif;font-size:11pt;color:#18232B} .cv{background:#14233A;color:#fff;padding:18pt} .lab{color:#4FD1E8;font-size:9pt;text-transform:uppercase} h1{font-size:20pt;color:#fff;margin:4pt 0} h2{font-size:12pt;color:#14233A;text-transform:uppercase;letter-spacing:1pt;margin:16pt 0 6pt}
table{border-collapse:collapse;width:100%} th{background:#3B5BDB;color:#fff;text-align:left;padding:4pt 6pt;border:1.5pt solid #fff;font-weight:normal} td{background:#E0E2E5;padding:4pt 6pt;border:1.5pt solid #fff;vertical-align:top}
.st-g{color:#0B654E;font-weight:bold}.st-a{color:#8A5200;font-weight:bold}.st-r{color:#A3301F;font-weight:bold}.st-b{color:#2A4FE0;font-weight:bold}.st-n{color:#5A6270;font-weight:bold}.muted{color:#5A6270} .fig{display:inline-block;width:23%;vertical-align:top} .fig .v{font-size:16pt;font-weight:bold}</style></head>
<body><div class="cv"><div class="lab">Weekly report</div><h1>${esc(o.p.name)}</h1><div>Week ending ${D.fd(o.week)} · ${o.H[o.p.health]}: ${esc(o.p.reason)}</div></div>${o.body}<p class="muted">Published ${D.fd(D.TODAY)}.${opts.n ? ' Publication ' + opts.n + ' · ' + D.fd(D.TODAY) + '.' : ''}</p></body></html>`;
  }
  C.publish = async (kind, btn, opts = {}) => {
    const p = C.P();
    if (kind === 'tab') { const w = window.open('', '_blank'); if (!w) return C.toast('Your browser blocked the new tab'); w.document.write(await webPage()); w.document.close(); return; }
    /* progress and the tick are shown by the Publish dialog's own button (C.publishDialog); this only writes the file and says whether it did */
    try {
      const [data, type, ext] = kind === 'word' ? [wordDoc(opts), 'application/msword', 'doc'] : [await webPage(opts), 'text/html', 'html'];
      await new Promise(r => setTimeout(r, C.reduce ? 0 : 600));
      const name = `${p.week || D.friday()} ${p.name} weekly report.${ext}`, blob = new Blob([data], { type });
      /* the browser's own save dialog: browse folders, rename, confirm before overwriting; it opens where this project last saved */
      if (window.showSaveFilePicker && !C.noNativeSave) {
        try {
          const h = await window.showSaveFilePicker({ id: ('clark-' + p.code).slice(0, 32), suggestedName: name, startIn: 'documents', types: [{ description: ext === 'doc' ? 'Word document' : 'Web page', accept: { [type]: ['.' + ext] } }] });
          const w = await h.createWritable(); await w.write(blob); await w.close();
          C.toast(`Saved "${h.name}"`); C.lastPublished = data; C.lastSavedName = h.name; return true;
        } catch (err) { if (err && err.name === 'AbortError') { C.toast('Publishing cancelled'); return false; } }
      }
      const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = name; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 4000);
      C.toast(`Saved "${name}" to your downloads`);
      C.lastPublished = data;
    } catch (e) { C.toast('Publishing did not finish. Try again.'); return false; }
    return true;
  };
  C.webPage = webPage;

  /* Publish: "Local" always; "To client" only when ticked, to the client's SharePoint folder set in Settings. */
  C.publishDialog = () => {
    const p = C.P(), loc = p.publish || {}, week = p.week || D.friday(), last = (p.published || []).slice(-1)[0];
    const localPath = loc.local || `~/Documents/clark/${p.name}/Reports`;
    /* before publishing: open items with no owner or no date, and open items not reviewed in 14 days (FR-35a). It warns; it never blocks. */
    const gaps = C.items().filter(D.gap), stale = C.items().filter(D.notReviewed), nextN = D.pubNext(p);
    const warnHtml = (gaps.length || stale.length) ? `<div class="pubwarn" id="pubChecks" role="status">${gaps.length ? `<p id="pubGaps"><span>${gaps.length} ${gaps.length === 1 ? 'item has' : 'items have'} no owner or date.</span> <button type="button" class="link" data-show="gap">Show them</button></p>` : ''}${stale.length ? `<p id="pubStale"><span>${stale.length} open ${stale.length === 1 ? 'item was' : 'items were'} not reviewed in ${D.staleDays(p.code)} days.</span> <button type="button" class="link" data-show="stale">Show them</button></p>` : ''}<small>This is a warning only: you can still publish.</small></div>` : '';
    C.dialog(`<form id="pubF"><div class="dlg-h"><h2>Publish the report</h2><p>${esc(p.name)} · week ending ${D.fd(week)} · this will be Publication ${nextN}${last ? ` · last published ${D.fd(last.at.slice(0, 10))}${last.client ? ', to the client' : ', locally'}` : ''}</p></div>
      <div class="dlg-b">${warnHtml}<div class="pubopts">
        <label class="pubopt"><input type="checkbox" id="pubLocal" checked disabled><span><b>Local</b><small>Always. ${window.showSaveFilePicker ? 'You choose the folder and name in the save window; it opens where you last saved' : 'Saved to your downloads'}</small></span></label>
        <label class="pubopt${loc.client ? '' : ' off'}"><input type="checkbox" id="pubClient" ${loc.client ? '' : 'disabled'}><span><b>To client</b><small>${loc.client ? 'Sent to the client folder: ' + esc(loc.client) : 'No client folder yet. Set it in <button type="button" class="link" id="pubToSet">Settings, Publishing</button>.'}</small></span></label>
        <label class="pubopt"><input type="checkbox" id="pubWord"><span><b>Also a Word document</b><small>Beside the web page, in the same places</small></span></label>
        <label class="pubopt"><input type="checkbox" id="pubPdf"><span><b>Also a PDF</b><small>The page as it prints: the four tabs one after another, no controls, with the publication number in the foot</small><small class="pdfnote" id="pubPdfNote" hidden>Prototype: your browser’s print box opens; choose Save as PDF.</small></span></label>
      </div><p class="muted" id="pubWarn" style="font-size:13px;margin:10px 0 0" hidden>The client will see this page. Only what is shown in View mode is included.</p></div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Cancel</button><button class="btn pri" id="pubGo">Publish locally</button></div></form>`, d => {
      const cl = C.$('#pubClient', d), go = C.$('#pubGo', d);
      C.$('#pubPdf', d).addEventListener('change', e => { C.$('#pubPdfNote', d).hidden = !e.target.checked; });
      C.$('#pubToSet', d)?.addEventListener('click', e => { e.preventDefault(); d.close(); C.go('settings', { keepScroll: true }); setTimeout(() => C.settingsGo('pubC'), 80); });   /* P2: the words are a link to the client folder box */
      C.$$('#pubChecks [data-show]', d).forEach(b => b.addEventListener('click', () => { d.close(); C.workFilter({ fresh: [b.dataset.show] }); }));
      cl.addEventListener('change', () => { go.textContent = cl.checked ? 'Publish and send to the client' : 'Publish locally'; C.$('#pubWarn', d).hidden = !cl.checked; });
      /* the dialog stays open while it works: a spinner on the Publish button, then a tick and "Published (Publication N)", then it closes (the sweep) */
      const form = C.$('#pubF', d), stop = C.$('[data-close]', d); let busy = false;
      d.addEventListener('cancel', e => { if (busy && form.isConnected) e.preventDefault(); });   /* the shared dialog keeps this listener, so it only counts while this form is the one showing */
      form.addEventListener('submit', async e => {
        e.preventDefault(); if (busy) return; busy = true;
        const toClient = cl.checked, word = C.$('#pubWord', d).checked, pdf = C.$('#pubPdf', d).checked, lbl = go.innerHTML;
        go.style.minWidth = go.offsetWidth + 'px'; go.disabled = true; stop.disabled = true; go.setAttribute('aria-busy', 'true'); go.innerHTML = '<span class="spin"></span>Publishing…';
        const n = D.pubNext(p), pw = pdf ? window.open('', '_blank') : null;   /* opened now, while the click still counts, and filled when the page is ready */
        const okSaved = await C.publish('html', null, { n }); if (okSaved === false) { if (pw && pw.close) pw.close(); busy = false; go.disabled = false; stop.disabled = false; go.removeAttribute('aria-busy'); go.innerHTML = lbl; return; }
        const html = C.lastPublished || ''; if (word) await C.publish('word', null, { n });
        /* numbered, with a kept copy of the page and of its text sections (to start next week's report from); the project holds the row */
        const rec = { at: D.stamp(), week, local: localPath, client: toClient ? loc.client : '', word, pdf, n, who: (D.S.profile || {}).name || 'You', where: toClient ? 'Local and to client' : 'Local', hseq: D.lastSeq() };
        await D.pubKeep(p.code, n, { n, code: p.code, at: rec.at, html, texts: Object.fromEntries((p.report.sections || []).filter(x => x.type === 'text').map(x => [x.id, x.html || ''])) });
        D.change('project', p, { published: [...(p.published || []), rec] }, D.who('by publishing the report')); C.refresh();   /* no Undo after a publication: it keeps its number and its copy (#111) */
        if (pdf) { if (pw && pw.document) { pw.document.write(html.replace('</body>', '<script>setTimeout(function(){window.print()},800)<\/script></body>')); pw.document.close(); } else C.toast('Your browser blocked the new tab for the PDF'); }
        C.toast((toClient ? `Publication ${n}: published locally and to the client folder (prototype: not sent; it would go to ${loc.client})` : `Publication ${n}: published locally`) + (pdf ? '. Prototype: your browser’s print box opens; choose Save as PDF.' : ''));
        go.removeAttribute('aria-busy'); go.classList.add('ok'); go.innerHTML = `${C.icon('check', 's tick')}Published (Publication ${n})`;
        setTimeout(() => { if (d.open && form.isConnected) d.close(); }, 1200);
      });
    });
  };
})();
