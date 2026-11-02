/* clark prototype: the file features of Publish and files. Four things, each drawn so a person can try it:
   1. Excel file layout (preview): what the product's workbook holds (#85 cover sheet, #127 drop-downs and colour, #128 locked ID column).
      The prototype's own Export to Excel still saves a plain workbook: its Excel library cannot write drop-downs, locking, colour rules or
      frozen panes, so this window draws them and says so.
   2. Export to Word: the product's box (#48, PR 224) with the name-taken question, and the person's own Word template (#219).
   3. Import from Word: the product's box (#48, PR 224); a real .docx is read here (headings called Actions, Risks, Issues or Decisions, and the
      lines under them), checked first, and nothing is added until the person chooses.
   4. The client's comment box on a published page (#120): a comment names the publication and the work item.
   The Word words come from one table (MSG), the date in both boxes from one helper (D.fd), and the Help text names the button the box shows (#432). */
(() => {
  'use strict';
  const C = window.C, D = window.ClarkDB, esc = s => C.esc(s), UI = C.UI;
  const plain = h => C.plain(h || '').replace(/\s+/g, ' ').trim();
  const HN = { G: 'On track', A: 'At risk', R: 'Off track' };

  /* ═════════ 1. Excel file layout (preview) ═════════ */
  const LOCK = '<svg class="xl-lk" viewBox="0 0 12 14" width="10" height="12" aria-hidden="true"><rect x="1" y="6" width="10" height="7" rx="1.5" fill="currentColor"/><path d="M3.5 6V4.2a2.5 2.5 0 0 1 5 0V6" fill="none" stroke="currentColor" stroke-width="1.5"/></svg>';
  const XL = { tab: 'cover', sort: '', dir: 1, rows: null, extra: 0, open: -1 };
  const xlRows = () => C.items().filter(x => x.type === 'A').slice(0, 12).map(x => ({ id: x.id, type: D.TYPES[x.type], ws: x.ws, title: x.title, owner: x.owner, due: x.due, status: x.status, priority: x.priority, t: x.type, open: C.isOpen(x), fresh: false }));
  const clock = () => { const d = new Date(); return `${D.fd(D.TODAY)} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`; };
  const SCOL = { Open: 'b', Delayed: 'a', Closed: 'n', Cancelled: 'n', Pending: 'b', Made: 'g', Withdrawn: 'n' };
  const pill = (r, f) => f === 'status' ? C.pill([SCOL[r.status] || 'b', r.status]) : `<span class="prio ${esc(r.priority)}">${esc(r.priority)}</span>`;

  function coverHtml(p) {
    const me = D.S.profile || {}, g = C.glanceData(p), secs = C.pubOrder(p.report.sections).filter(s => C.onPub(s, p)), week = p.week || D.friday();
    const texts = secs.filter(s => s.type === 'text' && plain(s.html)).map(s => [s.title, plain(s.html)]);
    const shownFig = (p.report.glance || []).filter(f => !f.hidden && f.k !== 'health' && g[f.k]).map(f => `${g[f.k].k}: <b>${g[f.k].v}</b>`).join(' · ');
    const rows = [
      ['xl-title', '', `<span class="xl-brand">clark</span> ${esc(p.name)}`],
      ['xl-sub', '', `WEEKLY REPORT · Week ending ${D.fd(week)}${p.client ? ' · for ' + esc(p.client) : ''}`],
      ['', '', ''],
      ['xl-sec', 'Current state', esc(plain(p.current)) || '<span class="muted"></span>'],
      ['xl-sec', 'At a glance', `<span class="hpill ${p.health}">${HN[p.health]}</span> ${esc(p.reason || '')}`],
      ['', '', shownFig],
      ...texts.map(([t, x]) => ['xl-sec', t, esc(x)]),
      ['', '', ''],
      ['xl-prov', 'Exported', `${clock()} by ${esc(me.name || 'you')}`],
      ['xl-prov xl-caution', 'Caution', 'This workbook shows the data at the date above. It does not reflect changes made since.'],
      ['xl-prov', 'Return it', `Updates may be made in this workbook and sent back to ${esc(me.name || 'the owner')}${me.email ? ' (' + esc(me.email) + ')' : ''}. The owner imports the file to reflect them in the master.`],
      ['xl-prov', 'About this export', 'IDs can’t be changed here. Leave the ID empty for a new item.'],
    ];
    return `<div class="xl-scroll"><table class="xl" aria-label="The Cover sheet"><thead><tr><th class="xl-rn"></th><th>A</th><th>B</th></tr></thead><tbody>${rows.map(([c, a, b], i) => `<tr class="${c}"><th class="xl-rn">${i + 1}</th><td class="xl-a">${esc(a)}</td><td>${b}</td></tr>`).join('')}</tbody></table></div>
      <p class="xl-note">The first sheet. It reads like the dashboard: the title, Current state, At a glance with the health pill and its reason, then the text sections that are shown in the report. A hidden section or row is not here, as in the published file. The date, who exported it and the caution are in the file, and the return note says where to send it back.</p>`;
  }
  function gridHtml(p) {
    if (!XL.rows) XL.rows = xlRows();
    let rows = XL.rows.slice(); if (XL.sort) rows.sort((a, b) => String(a[XL.sort] || '').localeCompare(String(b[XL.sort] || '')) * XL.dir);
    const cols = [['id', 'ID'], ['type', 'Type'], ['ws', 'Workstream'], ['title', 'Title'], ['owner', 'Owner'], ['due', 'Due'], ['status', 'Status'], ['priority', 'Priority']], fixed = ['type', 'ws', 'status', 'priority'];
    return `<div class="xl-scroll xl-frz" id="xlScroll"><table class="xl xl-wi" aria-label="The Actions sheet"><thead><tr><th class="xl-rn"></th>${cols.map(([k, t]) => `<th class="${k === 'id' ? 'xl-id' : ''}"><button class="xl-hd" data-xs="${k}" aria-label="Sort by ${t}">${t}${fixed.includes(k) ? ' <span class="xl-dda" title="A drop-down on every cell">▾</span>' : ''}${XL.sort === k ? (XL.dir > 0 ? ' ↑' : ' ↓') : ''}</button></th>`).join('')}</tr></thead>
      <tbody>${rows.map((r, i) => `<tr><th class="xl-rn">${i + 2}</th>${cols.map(([k]) => {
        if (k === 'id') return r.fresh ? `<td class="xl-id xl-new"><input class="xl-in" data-xnew aria-label="ID (leave empty)" value="${esc(r.id)}"></td>` : `<td class="xl-id xl-locked"><button class="xl-cell" data-xlock="${esc(r.id)}" aria-label="${esc(r.id)}, locked">${LOCK}${esc(r.id)}</button></td>`;
        if (k === 'status' || k === 'priority') return `<td class="xl-dd"><button class="xl-cell" data-xdd="${k}" data-xi="${XL.rows.indexOf(r)}" aria-haspopup="listbox" aria-expanded="${XL.open === XL.rows.indexOf(r) && XL.openF === k}">${pill(r, k)} <span class="xl-dda">▾</span></button>${XL.open === XL.rows.indexOf(r) && XL.openF === k ? `<ul class="xl-list" role="listbox" aria-label="${k === 'status' ? 'Status' : 'Priority'}">${(k === 'status' ? D.STATUSES[r.t] : D.PRIORITIES).map(v => `<li role="option" tabindex="0" data-xpick="${esc(v)}" aria-selected="${r[k] === v}">${esc(v)}</li>`).join('')}</ul>` : ''}</td>`;
        if (k === 'due') return `<td class="${r.open && r.due && r.due < D.TODAY ? 'xl-od' : ''}">${D.fd(r.due)}</td>`;
        return `<td${k === 'title' ? ' class="xl-t"' : ''}>${esc(r[k] || '')}</td>`; }).join('')}</tr>`).join('')}</tbody></table></div>
      <div class="xl-try"><button class="btn sm" id="xlAdd">Add a row</button><form id="xlForm" class="xl-form"><label class="muted" for="xlType">Type into a Status cell</label><input class="field" id="xlType" placeholder="for example Open" autocomplete="off"><button class="btn sm">Enter</button></form></div>
      <div class="xl-msg" id="xlMsg" role="status" aria-live="polite"></div>
      <p class="xl-note">The Actions sheet (Risks and issues, Decisions, Milestones and Use cases are laid out the same way). The header row and the ID column are frozen: scroll the grid and they stay. Type, Workstream, Status and Priority are drop-downs holding clark’s values; anything else is refused. Status and Priority are coloured by their value, so changing a value in Excel recolours it, and the word is always there (colour is never the only signal). An open action past its due date has a red date. The ID column is locked and the sheet is protected without a password: rows can still be added, sorted and filtered. Impact and Likelihood are not fields in this prototype, so they are not drawn.</p>`;
  }
  function listsHtml(p) {
    const cols = [['Type', Object.values(D.TYPES)], ['Status: actions', D.STATUSES.A], ['Status: risks and issues', D.STATUSES.R], ['Status: decisions', D.STATUSES.D], ['Priority', D.PRIORITIES], ['Rating', ['Red', 'Amber', 'Green']], ['Workstream', p.ws], ['Use case', D.S.usecases.filter(u => u.code === p.code && !u.archived).map(u => u.id)], ['Milestone', C.mss().map(m => m.name)], ['Client-visible', ['Yes', 'No']]], n = Math.max(...cols.map(c => c[1].length));
    return `<div class="xl-scroll"><table class="xl" aria-label="The Lists sheet (hidden)"><thead><tr><th class="xl-rn"></th>${cols.map(([t]) => `<th>${esc(t)}</th>`).join('')}</tr></thead><tbody>${Array.from({ length: n }, (_, i) => `<tr><th class="xl-rn">${i + 2}</th>${cols.map(([, v]) => `<td>${esc(v[i] || '')}</td>`).join('')}</tr>`).join('')}</tbody></table></div>
      <p class="xl-note">A hidden sheet called Lists. The drop-downs read their values from here, so a long list such as the project’s workstreams works. The import ignores this sheet, and an export read back in with no edits changes nothing. Owner stays free text until the people table is used for it.</p>`;
  }
  C.xlsxLayout = () => {
    const p = C.P(); if (!p) return; XL.rows = null; XL.sort = ''; XL.open = -1; XL.tab = 'cover';
    const draw = d => { const body = XL.tab === 'cover' ? coverHtml(p) : XL.tab === 'work' ? gridHtml(p) : listsHtml(p);
      d.querySelector('#xlBody').innerHTML = body; d.querySelectorAll('[data-xt]').forEach(b => b.setAttribute('aria-pressed', b.dataset.xt === XL.tab)); wire(d); };
    const say = (d, t, bad) => { const m = d.querySelector('#xlMsg'); if (m) { m.className = 'xl-msg' + (bad ? ' bad' : ''); m.setAttribute('role', bad ? 'alert' : 'status'); m.innerHTML = t; } };
    const wire = d => {
      d.querySelectorAll('[data-xs]').forEach(b => b.addEventListener('click', () => { const k = b.dataset.xs; XL.dir = XL.sort === k ? -XL.dir : 1; XL.sort = k; XL.open = -1; draw(d); }));
      d.querySelectorAll('[data-xlock]').forEach(b => b.addEventListener('click', () => say(d, `<b>The cell is locked.</b> IDs can’t be changed here. Leave the ID empty for a new item.`, true)));
      d.querySelectorAll('[data-xdd]').forEach(b => b.addEventListener('click', () => { const i = +b.dataset.xi; XL.open = XL.open === i && XL.openF === b.dataset.xdd ? -1 : i; XL.openF = b.dataset.xdd; draw(d); d.querySelector('.xl-list li[aria-selected=true]')?.focus(); }));
      d.querySelectorAll('[data-xpick]').forEach(li => { const pick = () => { const r = XL.rows[XL.open]; r[XL.openF] = li.dataset.xpick; if (XL.openF === 'status') r.open = !['Closed', 'Cancelled', 'Withdrawn', 'Made'].includes(r.status); XL.open = -1; draw(d); say(d, `${esc(r.id)}: ${XL.openF === 'status' ? 'Status' : 'Priority'} is now <b>${esc(li.dataset.xpick)}</b>, and its colour followed.`); };
        li.addEventListener('click', pick); li.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); pick(); } else if (e.key === 'Escape') { XL.open = -1; draw(d); } else if (e.key === 'ArrowDown') { e.preventDefault(); li.nextElementSibling?.focus(); } else if (e.key === 'ArrowUp') { e.preventDefault(); li.previousElementSibling?.focus(); } }); });
      d.querySelector('#xlAdd')?.addEventListener('click', () => { XL.rows.push({ id: '', type: 'Action', ws: p.ws[0], title: '', owner: '', due: '', status: 'Open', priority: 'Medium', t: 'A', open: true, fresh: true }); XL.open = -1; draw(d); const i = d.querySelector('[data-xnew]'); i && (i.focus(), say(d, 'Leave the ID empty. clark gives new items an ID when you import the workbook.')); d.querySelector('#xlScroll')?.scrollTo({ top: 9999 }); });
      d.querySelector('[data-xnew]')?.addEventListener('focus', () => say(d, 'Leave the ID empty. clark gives new items an ID when you import the workbook.'));
      d.querySelector('#xlForm')?.addEventListener('submit', e => { e.preventDefault(); const v = d.querySelector('#xlType').value.trim(); const ok = D.STATUSES.A.includes(v);
        say(d, ok ? `“${esc(v)}” is on the list, so the cell accepts it.` : `<b>Not allowed.</b> Choose a value from the list.`, !ok); });
    };
    C.dialog(`<div class="dlg-h"><h2>Excel file layout</h2><p>What clark’s Excel export holds. <span class="tag info">Prototype: drawn here</span></p></div>
      <div class="dlg-b xl-b"><p class="muted xl-proto" id="xlProto">The prototype’s own Export to Excel saves a plain workbook, because its Excel library cannot write drop-downs, locked cells, colour rules or frozen panes. This window draws what the product’s file holds, so you can try it.</p>
        <div class="seg xl-tabs" role="group" aria-label="Sheets">${[['cover', 'Cover'], ['work', 'Actions'], ['lists', 'Lists (hidden)']].map(([k, t]) => `<button data-xt="${k}" aria-pressed="${k === 'cover'}">${t}</button>`).join('')}</div>
        <div id="xlBody"></div><p class="muted" style="font-size:12px;margin:8px 0 0">Also in the file, in this order: Risks and issues, Decisions, Milestones, Use cases and History.</p></div>
      <div class="dlg-f"><button class="btn quiet" id="xlSave" style="margin-right:auto">${C.icon('dl', 's')}Save the plain workbook</button><button class="btn pri" data-close>Close</button></div>`, d => {
      d.querySelectorAll('[data-xt]').forEach(b => b.addEventListener('click', () => { XL.tab = b.dataset.xt; XL.open = -1; draw(d); }));
      d.querySelector('#xlSave').addEventListener('click', () => C.exportExcel()); draw(d); });
  };

  /* ═════════ the Word words: one table, so a screen and a test name a message by its key ═════════ */
  const MB = 25;
  const MSG = {
    not_word: n => `${n} is not a Word file. Choose a Word file.`,
    too_big: n => `${n} is bigger than the ${MB} MB that clark can open. Save a smaller copy (for example without big pictures), then choose it again. Nothing was added.`,
    empty: () => 'That file is empty. Choose the Word file again.',
    unreadable: () => 'That file could not be read by your browser. Choose the Word file again.',
    damaged: n => `${n} can't be opened as a Word document. It may be damaged or cut short. Open it in Word, save it again as a .docx and try again.`,
    password: n => `${n} is password protected, or is an older kind of Word file. Open it in Word, remove the password, save a copy as a .docx and try again.`,
    macros: n => `${n} has macros in it. clark never opens macros. Save a copy as a plain .docx (not .docm) and try again.`,
    objects: n => `${n} has a file or object inside it (such as a spreadsheet). clark won't open it. Remove it in Word and save a copy.`,
    no_text: n => `${n} is not a Word document: it has no main text.`,
    nothing_seen: n => `Everything in ${n} has been added before, so there is nothing new to add.`,
    nothing_new: n => `Nothing new was found in ${n}. Put actions, risks, issues or decisions under a heading with that name, then choose the file again.`,
    found: (n, k) => `${k} new ${k === 1 ? 'item' : 'items'} found in ${n}. Nothing is added until you choose.`,
    choose: () => 'Choose a Word file first.',
    added: (n, f, k) => `Added ${k} new ${k === 1 ? 'item' : 'items'} from ${f}. ${k === 1 ? 'It is' : 'They are'} not shown to the client until you turn ${k === 1 ? 'it' : 'them'} on. Press Undo to take ${k === 1 ? 'it' : 'them all'} back.`,
    taken: (n, where) => `A file called “${n}” is already in ${where}.`,
    taken_end: replace => ` The Word report has not been saved yet. Choose ${replace ? 'Add a number, Replace it or Cancel' : 'Add a number or Cancel'}.`,
    saved: (n, folder) => `Saved “${n}” in ${folder}.`,
    saved_client: n => ` It was also copied to the client folder as “${n}”. OneDrive uploads it from there; clark can't see when that finishes.`,
    no_client: () => 'No client folder yet. Set it in Settings. Nothing was saved.',
    cancelled: () => 'Cancelled. Nothing was saved.',
    tpl_not_filled: (names, where = '') => `Not filled: ${names}${where}. Nothing was written.`,
    tpl_where: () => ' (in a header, footer, note or comment, which are not filled)',
    tpl_ok: (n, k) => `${n} is ready: ${k} ${k === 1 ? 'place' : 'places'} would be filled. Every other part of the template is kept exactly as it is.`
  };
  C.wordMsg = MSG;
  const folderName = path => path ? String(path).replace(/[\\/]+$/, '').split(/[\\/]/).pop() || String(path) : '';
  const wordName = (p, week) => `${week} ${p.name} weekly report.doc`;

  /* ═════════ a .docx, read here: a zip with one part we need (word/document.xml) ═════════ */
  async function zipParts(buf) {
    const u8 = new Uint8Array(buf), dv = new DataView(buf); if (u8.length < 22) throw { key: 'damaged' };
    if (dv.getUint32(0, true) === 0xE011CFD0 || (u8[0] === 0xD0 && u8[1] === 0xCF && u8[2] === 0x11 && u8[3] === 0xE0)) throw { key: 'password' };
    let e = -1; for (let i = u8.length - 22; i >= Math.max(0, u8.length - 65557); i--) if (dv.getUint32(i, true) === 0x06054b50) { e = i; break; }
    if (e < 0) throw { key: 'damaged' };
    const n = dv.getUint16(e + 10, true); let o = dv.getUint32(e + 16, true); const out = new Map(), dec = new TextDecoder();
    for (let k = 0; k < n; k++) { if (dv.getUint32(o, true) !== 0x02014b50) throw { key: 'damaged' };
      const meth = dv.getUint16(o + 10, true), csize = dv.getUint32(o + 20, true), nl = dv.getUint16(o + 28, true), xl = dv.getUint16(o + 30, true), cl = dv.getUint16(o + 32, true), lo = dv.getUint32(o + 42, true), name = dec.decode(u8.subarray(o + 46, o + 46 + nl));
      out.set(name, { meth, csize, lo }); o += 46 + nl + xl + cl; }
    const read = async name => { const m = out.get(name); if (!m) return null; const lnl = dv.getUint16(m.lo + 26, true), lxl = dv.getUint16(m.lo + 28, true), start = m.lo + 30 + lnl + lxl, raw = u8.subarray(start, start + m.csize);
      if (m.meth === 0) return dec.decode(raw);
      if (m.meth !== 8 || typeof DecompressionStream === 'undefined') throw { key: 'unreadable' };
      const s = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw')); return dec.decode(await new Response(s).arrayBuffer()); };
    return { names: [...out.keys()], read };
  }
  const unesc = t => t.replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, '&');
  const paragraphs = xml => (xml.match(/<w:p[ >][\s\S]*?<\/w:p>/g) || []).map(par => ({ style: ((par.match(/<w:pStyle w:val="([^"]*)"/) || [])[1] || ''), text: unesc(par.replace(/<w:tab\/>|<w:br\/>|<w:t(?:\s[^>]*)?>([^<]*)<\/w:t>|<[^>]*>/g, (m, t) => t !== undefined ? t : /^<w:(tab|br)\//.test(m) ? ' ' : '')).replace(/\s+/g, ' ').trim() }));
  async function openDocx(file) {
    let z; try { z = await zipParts(await file.arrayBuffer()); } catch (e) { throw e && e.key ? e : { key: 'unreadable' }; }
    if (z.names.some(n => /vbaProject\.bin$|\.docm$|macrosheets/i.test(n))) throw { key: 'macros' };
    if (z.names.some(n => /^word\/(embeddings|activeX)\//i.test(n) || /oleObject/i.test(n))) throw { key: 'objects' };
    if (!z.names.includes('word/document.xml') || !z.names.includes('[Content_Types].xml')) throw { key: 'no_text' };
    let xml; try { xml = await z.read('word/document.xml'); } catch (e) { throw e && e.key ? e : { key: 'damaged' }; }
    if (xml == null) throw { key: 'no_text' };
    return { z, xml };
  }
  const SECTION = { action: 'A', actions: 'A', risk: 'R', risks: 'R', issue: 'I', issues: 'I', decision: 'D', decisions: 'D', 'risks and issues': 'R', 'risks and issues log': 'R', 'actions and decisions': 'A' };
  const TNAME = { A: 'Action', R: 'Risk', I: 'Issue', D: 'Decision' };
  function itemsOf(paras) {
    let cur = null; const out = [];
    paras.forEach(pr => { const t = pr.text.replace(/[:.]$/, '').toLowerCase(), isH = /^(heading|title)/i.test(pr.style) || (pr.text.length <= 40 && SECTION[t] && !/^list/i.test(pr.style));
      if (isH) { cur = SECTION[t] || null; return; }
      const line = pr.text.replace(/^[•●\-*–]\s*|^\(?\d{1,2}[.)]\s+/, '').trim(); if (cur && line) out.push({ type: cur, text: line.slice(0, 300) }); });
    return out.map((x, i) => ({ ...x, n: i + 1 }));
  }
  const fp = (file, x) => C.pubSum(file + '|' + x.type + '|' + x.text);

  /* a demo file stands in for a .docx when the person has none to hand: the same checks and the same list */
  const DEMO_PARAS = [['Title', 'Weekly notes'], ['Heading1', 'Actions'], ['', 'Agree the test dates with the supplier'], ['', 'Send the access forms to the data team'], ['Heading1', 'Risks'], ['', 'The supplier may not have capacity in November'],
    ['Heading1', 'Issues'], ['', 'The test environment is down on Mondays'], ['Heading1', 'Decisions'], ['', 'Choose the go-live week'], ['Heading1', 'Notes'], ['', 'This paragraph is not under a work item heading, so it is not read']].map(([style, text]) => ({ style, text }));

  /* ═════════ 3. Import from Word ═════════ */
  const WI = { file: null, plan: null, ticks: [], msg: null, demo: false };
  const wiMsg = (key, ...a) => ({ key, text: MSG[key](...a) });
  C.wordImport = () => {
    const p = C.P(); if (!p) return;
    if (!UI.editing) return C.toast('Import from Word is in Edit, because it adds work items.');
    Object.assign(WI, { file: null, plan: null, ticks: [], msg: null, demo: false }); wiDraw();
  };
  function wiDraw(busy) {
    const p = C.P(), s = WI, plan = s.plan, n = s.ticks.length, say = s.msg ? `<p class="${s.msg.kind || 'error'}" data-msg="${s.msg.key}">${esc(s.msg.text)}</p>` : '';
    const body = plan ? `<p class="muted dlg-sub" id="wiCount">${plan.items.length ? esc(MSG.found(plan.file, plan.items.length)) : esc(plan.already ? MSG.nothing_seen(plan.file) : MSG.nothing_new(plan.file))}</p>
        ${plan.items.length ? `<div class="wi-all"><button type="button" class="link" id="wiAll">Tick all</button> <button type="button" class="link" id="wiNone">Untick all</button></div>
        <fieldset class="wi-items"><legend class="sr-only">Items to add</legend>${plan.items.map(i => `<label class="pubopt wi-item"><input type="checkbox" data-wn="${i.n}"${s.ticks.includes(i.n) ? ' checked' : ''}><span><b>${i.n}.</b> <span class="type ${i.type}" title="${TNAME[i.type]}">${i.type}</span> ${esc(i.text)}</span></label>`).join('')}</fieldset>` : ''}
        ${plan.notes.length ? `<ul class="wi-notes" id="wiNotes">${plan.notes.map(t => `<li>${esc(t)}</li>`).join('')}</ul>` : ''}`
      : `<p class="muted dlg-sub">Choose a Word file of up to ${MB} MB. You will see what it holds first. Nothing is added until you choose.</p>
        <label class="pub-field" for="wiFile" style="display:block">Word file <input type="file" id="wiFile" accept=".docx" style="display:block;margin-top:4px"></label><p style="margin:10px 0 0"><button type="button" class="link" id="wiDemo">No Word file to hand? Try a demo file</button></p>`;
    C.dialog(`<form id="wiF"><div class="dlg-h"><h2>Import from Word</h2></div><div class="dlg-b">${body}<div class="pub-msg" id="wiMsg" role="status" aria-live="polite">${busy ? esc(busy) : say}</div></div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close ${busy ? 'disabled' : ''}>${plan && !plan.items.length ? 'Close' : 'Cancel'}</button>${plan ? (plan.items.length ? `<button class="btn pri" id="wiAdd" ${busy || !n ? 'disabled' : ''}>${n ? `Add ${n} ${n === 1 ? 'item' : 'items'}` : 'Add items'}</button>` : '') : `<button class="btn pri" id="wiRead" ${busy || !s.file ? 'disabled' : ''}>Read the file</button>`}</div></form>`, d => {
      const f = C.$('#wiFile', d), read = C.$('#wiRead', d);
      /* a refused or unreadable file is let go and the picker emptied: choosing that same file again is then a change, and Read the file comes on again (#432) */
      const drop = (msg) => { s.file = null; s.msg = msg; if (f) f.value = ''; if (read) read.disabled = true; const m = C.$('#wiMsg', d); m.innerHTML = `<p class="error" data-msg="${msg.key}">${esc(msg.text)}</p>`; };
      f?.addEventListener('change', () => { const x = f.files && f.files[0]; if (!x) { s.file = null; if (read) read.disabled = true; return; }
        if (!/\.docx$/i.test(x.name)) return drop(wiMsg('not_word', x.name)); if (x.size > MB * 1048576) return drop(wiMsg('too_big', x.name)); if (x.size === 0) return drop(wiMsg('empty'));
        s.file = x; s.demo = false; s.msg = null; C.$('#wiMsg', d).innerHTML = ''; read.disabled = false; });
      C.$('#wiDemo', d)?.addEventListener('click', () => { s.file = { name: 'weekly notes (demo).docx' }; s.demo = true; go(d); });
      C.$('#wiAll', d)?.addEventListener('click', () => { s.ticks = plan.items.map(i => i.n); wiDraw(); });
      C.$('#wiNone', d)?.addEventListener('click', () => { s.ticks = []; wiDraw(); });
      C.$$('[data-wn]', d).forEach(b => b.addEventListener('change', () => { const k = +b.dataset.wn; s.ticks = b.checked ? [...s.ticks.filter(t => t !== k), k].sort((a, b2) => a - b2) : s.ticks.filter(t => t !== k); wiDraw(); C.$(`[data-wn="${k}"]`)?.focus(); }));
      C.$('#wiF', d).addEventListener('submit', e => { e.preventDefault(); if (plan) add(d); else if (s.file) go(d); else { s.msg = wiMsg('choose'); C.$('#wiMsg', d).innerHTML = `<p class="error" data-msg="choose">${esc(s.msg.text)}</p>`; } });
    });
  }
  async function go(d) {
    const s = WI, p = C.P(), file = s.file; wiDraw('Reading the file…'); await new Promise(r => setTimeout(r, C.reduce ? 0 : 350));
    let paras, notes = [];
    try { if (s.demo) paras = DEMO_PARAS; else { const o = await openDocx(file); paras = paragraphs(o.xml); } }
    catch (e) { s.file = null; s.msg = { ...wiMsg(e && e.key ? e.key : 'unreadable', file.name), kind: 'error' }; wiDraw(); const inp = C.$('#wiFile'); if (inp) inp.value = ''; return; }
    const all = itemsOf(paras), seen = new Set(C.store.get('wordSeen.' + p.code, [])), have = new Set(C.items().map(x => x.title.toLowerCase()));
    const items = all.filter(x => !seen.has(fp(file.name, x)) && !have.has(x.text.toLowerCase())).map((x, i) => ({ ...x, n: i + 1 })), already = all.length - items.length;
    if (already && items.length) notes.push(`${already} ${already === 1 ? 'item was' : 'items were'} added before, so ${already === 1 ? 'it is' : 'they are'} not listed again.`);
    if (all.some(x => x.text.length >= 300)) notes.push('A line over 300 characters was cut short.');
    s.plan = { file: file.name, items, already, notes, all: all.length }; s.ticks = items.map(i => i.n); s.msg = null; wiDraw();
    C.$('#wiAdd')?.focus();
  }
  function add(d) {
    const s = WI, p = C.P(), plan = s.plan, take = plan.items.filter(i => s.ticks.includes(i.n)); if (!take.length) return;
    wiDraw(`Adding ${take.length} ${take.length === 1 ? 'item' : 'items'}…`);
    const how = D.who('by Word import (' + plan.file + ')'), made = [];
    const u = D.batch(take.map(x => () => D.create('item', { id: C.nextId(x.type), code: p.code, type: x.type, ws: p.ws[0], title: x.text, owner: '', due: '', status: D.STATUSES[x.type][0], priority: 'Medium', uc: '', ms: '', client: false, clientText: '', desc: '', update: '', updatedAt: D.stamp(), source: plan.file }, how)));
    const was = C.store.get('wordSeen.' + p.code, []), fps = take.map(x => fp(plan.file, x)); C.store.set('wordSeen.' + p.code, [...was, ...fps]);
    $dlgClose(); C.refresh();
    C.toast(MSG.added(plan.file, plan.file, take.length), () => { u && u(); C.store.set('wordSeen.' + p.code, was); });
  }
  const $dlgClose = () => { const d = C.$('#dlg'); if (d && d.open) d.close(); };

  /* ═════════ 2. Export to Word, and the person's own template ═════════ */
  const TPL = () => C.store.get('wordTpl.' + (C.P() || {}).code, null);
  C.wordTplLine = () => { const t = TPL(); return t ? `Your Word template “${esc(t.name)}” is used. Change it in Settings, Publishing.` : ''; };
  const VOCAB = ['PROJECT_NAME', 'PROJECT_CODE', 'CLIENT_NAME', 'SPONSOR', 'PHASE', 'WEEK_ENDING', 'AS_AT', 'HEALTH', 'HEALTH_REASON', 'CURRENT_STATE', 'GLANCE', 'USE_CASES', 'MILESTONES', 'RISKS', 'ACTIONS', 'DECISIONS', 'SECTIONS'];
  const tplValues = p => { const g = C.glanceData(p), week = p.week || D.friday(); return { PROJECT_NAME: p.name, PROJECT_CODE: p.code, CLIENT_NAME: p.client || '', SPONSOR: '', PHASE: '', WEEK_ENDING: D.fd(week), AS_AT: D.fd(D.TODAY), HEALTH: HN[p.health], HEALTH_REASON: p.reason || '', CURRENT_STATE: plain(p.current),
    GLANCE: Object.values(g).filter(x => x.v !== undefined).map(x => `${x.k}: ${x.v}`).join(', '), USE_CASES: `${D.S.usecases.filter(u => u.code === p.code && u.client && !u.archived).length} use cases (a table)`, MILESTONES: `${C.mss().filter(m => m.client).length} milestones (a table)`,
    RISKS: `${C.items().filter(x => x.client && (x.type === 'R' || x.type === 'I')).length} risks and issues (a table)`, ACTIONS: `${C.items().filter(x => x.client && x.type === 'A').length} actions (a table)`, DECISIONS: `${C.items().filter(x => x.client && x.type === 'D').length} decisions (a table)`, SECTIONS: 'the whole body, in published order' }; };
  /* what the product's fill would do with a template: the names it finds in the main text (a name may be split across runs, so each paragraph is joined first),
     and a refusal if one is unknown or sits where nothing is filled */
  async function checkTemplate(name, o) {
    const names = new Set(), stray = new Set();
    if (o.demo) { (o.demo.main || []).forEach(n => names.add(n)); (o.demo.stray || []).forEach(n => stray.add(n)); if (o.demo.macros) throw { key: 'macros' }; }
    else { const d = await openDocx(o.file);
      paragraphs(d.xml).forEach(pr => { (pr.text.match(/\{\{(.*?)\}\}/g) || []).forEach(m => names.add(m.slice(2, -2).trim())); });
      for (const n of d.z.names.filter(x => /^word\/(header|footer|footnotes|endnotes|comments)[^/]*\.xml$/.test(x))) { const x = await d.z.read(n); paragraphs(x || '').forEach(pr => (pr.text.match(/\{\{(.*?)\}\}/g) || []).forEach(m => stray.add(m.slice(2, -2).trim()))); } }
    const bad = [...names].filter(n => !VOCAB.includes(n));
    if (stray.size) return { ok: false, key: 'tpl_not_filled', text: MSG.tpl_not_filled([...stray].sort().join(', '), MSG.tpl_where()) };
    if (bad.length) return { ok: false, key: 'tpl_not_filled', text: MSG.tpl_not_filled(bad.sort().join(', ')) };
    return { ok: true, names: [...names] };
  }
  C.wordTemplateDialog = after => {
    const p = C.P(); if (!p) return; let res = null;
    const vals = tplValues(p);
    const draw = () => C.dialog(`<form id="wtF"><div class="dlg-h"><h2>Your Word template</h2><p>Use your own Word file for the report. Put <b>{{NAME}}</b> where a value goes, for example {{PROJECT_NAME}}. <span class="tag info">Prototype: checked here, not written</span></p></div>
      <div class="dlg-b"><p class="muted" style="font-size:13px;margin:0 0 6px">Names clark fills: ${VOCAB.map(v => `<code>{{${v}}}</code>`).join(' ')}</p>
        <label class="pub-field" for="wtFile" style="display:block">Template (.docx) <input type="file" id="wtFile" accept=".docx,.dotx" style="display:block;margin-top:4px"></label>
        <p class="muted" style="font-size:13px;margin:10px 0 4px">No template to hand? Try one:</p><div class="wt-demos"><button type="button" class="btn sm" data-wt="good">A good one</button><button type="button" class="btn sm" data-wt="unknown">One with an unknown name</button><button type="button" class="btn sm" data-wt="header">One with a name in the header</button><button type="button" class="btn sm" data-wt="macros">One with macros</button></div>
        <div id="wtRes" role="status" aria-live="polite">${res ? (res.ok ? `<p class="success" data-msg="tpl_ok">${esc(MSG.tpl_ok(res.name, res.names.length))}</p><table class="set wt-tbl"><thead><tr><th>Place</th><th>Would be filled with</th></tr></thead><tbody>${res.names.map(n => `<tr><td><code>{{${esc(n)}}}</code></td><td>${esc(vals[n] === '' ? 'nothing (not set in this project)' : vals[n])}</td></tr>`).join('')}</tbody></table><p class="muted" style="font-size:13px">Prototype: the file is not written here. In the product only the main text is filled; every other part of your template is copied as it is.</p>` : `<p class="error" data-msg="${res.key}">${esc(res.text)}</p>`) : ''}</div></div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Cancel</button>${TPL() ? '<button type="button" class="btn quiet" id="wtOwn">Use clark’s own layout</button>' : ''}<button class="btn pri" id="wtUse" ${res && res.ok ? '' : 'disabled'}>Use this template</button></div></form>`, d => {
      const run = async (name, o) => { try { const r = await checkTemplate(name, o); res = r.ok ? { ...r, name } : { ...r, name }; } catch (e) { const k = e && e.key ? e.key : 'unreadable'; res = { ok: false, key: k, text: MSG[k](name) }; } draw(); };
      C.$('#wtFile', d).addEventListener('change', e => { const f = e.target.files[0]; if (!f) return; if (!/\.(docx|dotx)$/i.test(f.name)) { res = { ok: false, key: 'not_word', text: MSG.not_word(f.name) }; draw(); return; } if (f.size > MB * 1048576) { res = { ok: false, key: 'too_big', text: MSG.too_big(f.name) }; draw(); return; } run(f.name, { file: f }); });
      C.$$('[data-wt]', d).forEach(b => b.addEventListener('click', () => { const k = b.dataset.wt, nm = { good: 'weekly report template.docx', unknown: 'branded template.docx', header: 'letterhead template.docx', macros: 'old template.docm' }[k];
        run(nm, { demo: { good: { main: ['PROJECT_NAME', 'WEEK_ENDING', 'HEALTH', 'HEALTH_REASON', 'CURRENT_STATE', 'MILESTONES', 'ACTIONS'] }, unknown: { main: ['PROJECT_NAME', 'CLIENT_LOGO'] }, header: { main: ['PROJECT_NAME'], stray: ['PROJECT_CODE'] }, macros: { macros: true } }[k] }); }));
      C.$('#wtOwn', d)?.addEventListener('click', () => { C.store.set('wordTpl.' + p.code, null); d.close(); C.toast('Word reports use clark’s own layout'); if (UI.view === 'settings') C.render(); after && after(); });
      C.$('#wtUse', d)?.addEventListener('click', e => { e.preventDefault(); C.store.set('wordTpl.' + p.code, { name: res.name }); d.close(); C.toast(`Word reports use your template “${res.name}”`); if (UI.view === 'settings') C.render(); after && after(); });
    });
    draw();
  };

  const WX = { phase: 'choose', ticked: false, choice: 'number', confirmed: false, msg: null, clash: null };
  const savedNames = code => { const v = C.store.get('wordFiles.' + code, null) || {}; return { here: v.here || [], client: v.client || [] }; };
  const numbered = (name, taken) => { const m = /^(.*?)(\.[^.]+)$/.exec(name), base = m ? m[1] : name, ext = m ? m[2] : ''; for (let i = 2; ; i++) { const t = `${base} (${i})${ext}`; if (!taken.some(x => x.toLowerCase() === t.toLowerCase())) return t; } };
  C.wordExport = () => { const p = C.P(); if (!p) return; Object.assign(WX, { phase: 'choose', ticked: false, choice: 'number', confirmed: false, msg: null, clash: null }); wxDraw(); };
  function wxDraw(busy) {
    const p = C.P(), loc = p.publish || {}, week = p.week || D.friday(), tpl = TPL(), s = WX, folder = folderName(loc.local) || 'Reports';
    const clashBody = s.phase === 'clash' ? `<p class="word-ask" id="wxAsk" data-msg="taken">${esc(s.clash.message)}</p><fieldset class="pub-clash"><legend class="sr-only">What should clark do?</legend>
        <label class="pubopt"><input type="radio" name="wx-clash" value="number"${s.choice === 'number' ? ' checked' : ''}><span><b>Add a number</b><small>Keeps the old file and saves the new one beside it.</small></span></label>
        ${s.clash.canReplace ? `<label class="pubopt"><input type="radio" name="wx-clash" value="overwrite"${s.choice === 'overwrite' ? ' checked' : ''}><span><b>Replace it</b><small>The old file is replaced by the new one. A copy already in the client folder is kept, and the new one gets a number.</small></span></label>` : ''}
        ${s.choice === 'overwrite' ? `<div class="pub-note"><label class="pubopt"><input type="checkbox" id="wxConfirm"${s.confirmed ? ' checked' : ''}><span>Yes, replace the file</span></label></div>` : ''}</fieldset>`
      : `<div class="pubopts"><p class="muted word-where">The report is saved as a Word file in the folder last used for this project. If there is none yet, a window asks you to choose one.</p>
        <label class="pubopt${loc.client ? '' : ' off'}"><input type="checkbox" id="wxClient" ${s.ticked ? 'checked' : ''} ${loc.client ? '' : 'disabled'}><span><b>To client</b><small>${loc.client ? 'Also copied to the client folder: ' + esc(folderName(loc.client)) : 'No client folder yet. Set it in <button type="button" class="link" id="wxSet">Settings, Publishing</button>.'}</small></span></label>
        <div class="pubopt wx-tpl"><span><b>Layout</b><small id="wxTpl">${tpl ? `Your Word template “${esc(tpl.name)}”.` : 'clark’s own layout.'} <button type="button" class="link" id="wxTplBtn">${tpl ? 'Change' : 'Use your own Word template'}</button></small></span></div></div>
        <p class="muted" id="wxNum" style="font-size:13px;margin:10px 0 0">This Word file is not a publication, so it has no number. To give the web page and its Word copy one number, use Publish and tick Also a Word document.</p>`;
    C.dialog(`<form id="wxF"><div class="dlg-h"><h2>${s.phase === 'clash' ? 'The Word file name is taken' : 'Export to Word'}</h2>${s.phase === 'clash' ? '' : `<p>${esc(p.name)} · week ending ${D.fd(week)}</p>`}</div>
      <div class="dlg-b">${clashBody}${s.ticked && s.phase !== 'clash' ? '<p class="muted dlg-warn" id="wxWarn">The client will see this report.</p>' : ''}<div class="pub-msg" id="wxMsg" role="status" aria-live="polite">${busy ? esc(busy) : s.msg ? `<p class="${s.msg.kind}" data-msg="${s.msg.key}">${esc(s.msg.text)}</p>` : ''}</div></div>
      <div class="dlg-f">${s.phase === 'done' ? '' : `<button type="button" class="btn quiet" data-close ${busy ? 'disabled' : ''}>Cancel</button>`}<button class="btn pri" id="wxGo" ${busy || (s.phase === 'clash' && s.choice === 'overwrite' && !s.confirmed) ? 'disabled' : ''}>${s.phase === 'done' ? 'Close' : s.phase === 'clash' ? 'Continue' : s.ticked ? 'Save and send to the client' : 'Save the Word report'}</button></div></form>`, d => {
      C.$('#wxClient', d)?.addEventListener('change', e => { s.ticked = e.target.checked; wxDraw(); C.$('#wxClient')?.focus(); });
      C.$('#wxSet', d)?.addEventListener('click', () => { d.close(); C.go('settings', { keepScroll: true }); setTimeout(() => C.settingsGo && C.settingsGo('pubC'), 80); });
      C.$('#wxTplBtn', d)?.addEventListener('click', () => C.wordTemplateDialog(() => wxDraw()));
      C.$$('[name=wx-clash]', d).forEach(r => r.addEventListener('change', () => { s.choice = r.value; s.confirmed = false; wxDraw(); C.$('[name=wx-clash]:checked')?.focus(); }));
      C.$('#wxConfirm', d)?.addEventListener('change', e => { s.confirmed = e.target.checked; wxDraw(); C.$('#wxConfirm')?.focus(); });
      C.$('#wxF', d).addEventListener('submit', async e => { e.preventDefault(); if (s.phase === 'done') return d.close(); await wxSave(d); });
    });
  }
  async function wxSave(d) {
    const s = WX, p = C.P(), loc = p.publish || {}, week = p.week || D.friday(), want = wordName(p, week), seen = savedNames(p.code), tpl = TPL(), folder = folderName(loc.local) || 'Reports';
    if (s.ticked && !loc.client) { s.msg = { kind: 'error', ...wiMsg('no_client') }; s.phase = 'choose'; return wxDraw(); }
    const taken = s.phase !== 'clash' ? seen.here.some(x => x.toLowerCase() === want.toLowerCase()) : false;
    if (taken) { const canReplace = true, where = 'the folder last used for this project'; s.clash = { message: MSG.taken(want, where) + MSG.taken_end(canReplace), canReplace }; s.phase = 'clash'; s.choice = 'number'; s.confirmed = false; return wxDraw(); }
    wxDraw('Saving the Word report… If a window asks where to save it, choose a folder there.');
    const replace = s.phase === 'clash' && s.choice === 'overwrite' && s.confirmed;
    let name = want; if (s.phase === 'clash' && s.choice === 'number') name = numbered(want, seen.here);
    let ok = true;
    if (!tpl) ok = await C.publish('word', null, {}); else await new Promise(r => setTimeout(r, C.reduce ? 0 : 300));
    if (ok === false) { s.msg = { kind: 'info', ...wiMsg('cancelled') }; s.phase = 'choose'; return wxDraw(); }
    if (!seen.here.some(x => x.toLowerCase() === name.toLowerCase())) seen.here.push(name);
    let text = MSG.saved(name, `the ${folder} folder`), clientName = '';
    if (s.ticked) { clientName = seen.client.some(x => x.toLowerCase() === name.toLowerCase()) ? numbered(name, seen.client) : name; seen.client.push(clientName); text += MSG.saved_client(clientName); }
    C.store.set('wordFiles.' + p.code, seen);
    if (tpl) text += ` Prototype: with your template “${tpl.name}” the file is not written here; the product fills the template and saves it.`; else text += ' Prototype: the file is saved to your downloads.';
    s.msg = { kind: 'success', key: 'saved', text }; s.phase = 'done'; s.clash = null; wxDraw();
    if (replace) C.toast(`Replaced “${name}”`);
    C.$('#wxGo')?.focus();
  }
  /* Settings, Publishing: the Word template row (#219) */
  C.wordTplRowHtml = () => { const t = TPL(); return `<label>Word template</label><div class="fc"><div class="pf-tpl" id="pubTplRow"><span id="pubTplName">${t ? esc(t.name) : 'clark’s own layout'}</span> <button type="button" class="btn sm" id="pubTplBtn">${t ? 'Change' : 'Choose a template…'}</button>${t ? ' <button type="button" class="btn sm quiet" id="pubTplOwn">Use clark’s own layout</button>' : ''}</div><small>Your own Word file with {{NAME}} where a value goes. Word reports use it instead of clark’s layout.</small></div>`; };
  document.addEventListener('click', e => { const b = e.target.closest('#pubTplBtn'); if (b) C.wordTemplateDialog(); if (e.target.closest('#pubTplOwn')) { C.store.set('wordTpl.' + (C.P() || {}).code, null); C.toast('Word reports use clark’s own layout'); C.render(); } });

  /* ═════════ 4. the client's comment on the published page: the same few lines run inside the page, so they use no app code (#120) ═════════
     A comment names the project, the publication and the item. It stays in the client's browser, kept under the project and the publication number so two
     projects opened in one browser never share a list (and an item of another project is never copied). Copy my comments gives lines the client sends to the
     author, who pastes them into clark: nothing is sent from the page. */
  function cmPage() {
    var P = document.getElementById('panel'); if (!P || !PN || window.CLARK_READONLY) return;
    var KEY = 'clark.cm.' + PC + '.' + PN, ID = /^[A-Z0-9]+-[A-Z]-\d+$/;
    function read() { try { return JSON.parse(localStorage.getItem(KEY) || '[]').filter(function (c) { return c && String(c.item).indexOf(PC + '-') === 0; }); } catch (e) { return []; } }
    function save(a) { try { localStorage.setItem(KEY, JSON.stringify(a)); } catch (e) { } }
    function clean(t, k) { return String(t || '').replace(/[|\r\n]+/g, ' ').trim().slice(0, k || 1000); }
    function name() { try { return localStorage.getItem('clark.cm.name') || ''; } catch (e) { return ''; } }
    function list(box, id) { var l = read().filter(function (c) { return c.item === id; }), ul = box.querySelector('ul'); ul.innerHTML = ''; l.forEach(function (c) { var li = document.createElement('li'); li.textContent = c.by + ': ' + c.text; ul.appendChild(li); }); box.querySelector('.cmcopy').hidden = !read().length; }
    function build() {
      if (P.querySelector('.cm')) return; var id = '', ros = P.querySelectorAll('.ro');
      for (var i = 0; i < ros.length; i++) { var t = ros[i].textContent.split(' ')[0]; if (ID.test(t)) { id = t; break; } }
      if (!id) return;
      var box = document.createElement('div'); box.className = 'cm';
      box.innerHTML = '<h4>Comment on ' + id + '</h4><label>Your name<input class="cmby" maxlength="80"></label><label>Your comment<textarea class="cmtx" rows="3" maxlength="1000"></textarea></label><button type="button" class="cmadd">Add comment</button><button type="button" class="cmcopy" hidden>Copy my comments</button><small class="cmsay" role="status"></small><small>This comment is tied to Publication ' + PN + ' and ' + id + '. It is kept in this browser only (a name up to 80 characters, a comment up to 1000). Press Copy my comments and send what is copied to the project team; they paste it into clark.</small><ul></ul>';
      P.appendChild(box); box.querySelector('.cmby').value = name(); list(box, id);
      box.querySelector('.cmadd').addEventListener('click', function () { var by = clean(box.querySelector('.cmby').value, 80), tx = clean(box.querySelector('.cmtx').value, 1000), say = box.querySelector('.cmsay');
        if (!tx) { say.textContent = 'Write your comment first.'; return; }
        try { localStorage.setItem('clark.cm.name', by); } catch (e) { }
        var a = read(); a.push({ item: id, by: by || 'The client', text: tx }); save(a); box.querySelector('.cmtx').value = ''; say.textContent = 'Comment added to Publication ' + PN + ', ' + id + '.'; list(box, id); });
      box.querySelector('.cmcopy').addEventListener('click', function () { var say = box.querySelector('.cmsay'), t = read().map(function (c) { return 'clark-comment|' + PN + '|' + c.item + '|' + clean(c.by, 80) + '|' + clean(c.text, 1000); }).join('\n');
        try { navigator.clipboard.writeText(t).then(function () { say.textContent = 'Copied. Send it to the project team: it does not go anywhere by itself.'; }, function () { say.textContent = 'Could not copy. Select and copy the comments by hand.'; }); } catch (e) { say.textContent = 'Could not copy. Select and copy the comments by hand.'; } });
    }
    new MutationObserver(function () { build(); }).observe(P, { childList: true });
  }
  C.PUB_CM_JS = '(' + cmPage.toString() + ')();';
})();
