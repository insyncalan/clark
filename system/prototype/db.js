/* clark prototype: the data layer.
   Projects, work items, milestones and the change history live in the browser's own database (IndexedDB), so they persist
   between visits on this browser. Every change goes through Store.change(), which writes the record and one history row per
   field, and returns the way back (undo). The real build keeps the same shape in SQLite (docs/ARCHITECTURE.md). Demo data only. */
(function () {
  'use strict';
  const pad = n => String(n).padStart(2, '0');
  const toIso = d => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  const TODAY = toIso(new Date());
  const addDays = (iso, n) => { const d = new Date(iso + 'T00:00:00'); d.setDate(d.getDate() + n); return toIso(d); };
  const fd = iso => iso ? iso.split('-').reverse().join('-') : '';
  const days = iso => Math.round((new Date(iso + 'T00:00:00') - new Date(TODAY + 'T00:00:00')) / 864e5);
  const tzNow = () => { const m = -new Date().getTimezoneOffset(), a = Math.abs(m); return (m < 0 ? '-' : '+') + pad(Math.floor(a / 60)) + ':' + pad(a % 60); };   /* the offset a history row is stored with, e.g. +01:00 */
  const stamp = () => { const d = new Date(); return `${toIso(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const friday = () => { const d = new Date(TODAY + 'T00:00:00'); d.setDate(d.getDate() + ((5 - d.getDay() + 7) % 7)); return toIso(d); };
  const clone = o => JSON.parse(JSON.stringify(o));
  const keep = v => v === undefined ? undefined : clone(v);   /* a value as it is now, copied; a field that did not exist stays undefined */

  const TYPES = { A: 'Action', R: 'Risk', I: 'Issue', D: 'Decision' };
  /* creaite's value lists (schema.sql, v2.6.9), as the brief asks: "ensure that the work item and milestone schemas reflect those of creaite" */
  const STATUSES = { A: ['Open', 'Delayed', 'Closed', 'Cancelled'], R: ['Open', 'Closed', 'Cancelled'], I: ['Open', 'Closed', 'Cancelled'], D: ['Pending', 'Made', 'Withdrawn'] };
  const PRIORITIES = ['Urgent', 'High', 'Medium', 'Low'];

  function defaultReport() {
    return {
      sections: [
        { id: 'current', type: 'current', title: 'Current state' },
        { id: 'glance', type: 'glance', title: 'At a glance' },
        { id: 'usecases', type: 'usecases', title: 'Use case summary' },
        { id: 'milestones', type: 'milestones', title: 'Milestones' },
        { id: 'summary', type: 'text', title: 'Summary', html: '' },
        { id: 'thisweek', type: 'text', title: 'This week', html: '', beside: true },
        { id: 'nextweek', type: 'text', title: 'Next week', html: '' },
        { id: 'raid', type: 'raid', title: 'Risks and issues' },
        { id: 'actions', type: 'actions', title: 'Open actions' },
        { id: 'decisions', type: 'decisions', title: 'Decisions' },
        { id: 'docs', type: 'docs', title: 'Supporting documents' },
      ],
      glance: [{ k: 'health', hidden: false }, { k: 'overdue', hidden: false }, { k: 'risks', hidden: false }, { k: 'decisions', hidden: true }],
      hide: {},          // work item id → true when left out of the published page
      hideMs: {},        // milestone id → true when left out
    };
  }

  function seed() {
    const d = n => addDays(TODAY, n);
    const made = stamp().slice(0, 10) === TODAY ? addDays(TODAY, -20) + ' 09:00' : stamp();
    /* imported: the day the record came in, for an item that has no "Created" history row (the seed has none); it is "Raised" until history says otherwise (FR-35a) */
    const it = (code, id, type, ws, title, owner, due, status, x = {}) => { const o = { id, code, type, ws, title, owner, due, status, priority: 'Medium', desc: '', update: '', updatedAt: made, client: false, clientText: '', clientAct: false, ms: '', source: 'Weekly delivery meeting, ' + fd(d(-12)), ...x }; o.imported = o.updatedAt.slice(0, 10); return o; };
    const seen = n => d(n) + ' 10:00';   /* some items were looked at lately; the rest were not */
    const ms = (code, id, name, ws, agreed, x = {}) => ({ key: code + '/' + id, id, code, name, ws, agreed, original: agreed, forecast: agreed, achievedOn: '', manual: '', progress: null, desc: '', owner: '', client: true, clientText: '', ...x });
    const P1 = {
      code: 'PDF', name: 'Data Platform Pilot', client: 'Demo client', ws: ['Data platform', 'Testing', 'Change and training'], health: 'A',
      reason: 'The test environment is late, which puts the start of user testing at risk.',
      current: '<p>Build is complete for two of three data domains. The supplier has not yet confirmed the test environment handover, so user testing may start up to two weeks late.</p><p>A decision on using synthetic data for the first test cycle is due this week.</p>',
      report: defaultReport(),
      docs: [
        { id: 'D1', title: 'Weekly delivery meeting minutes', kind: 'Minutes', url: 'https://example.com/minutes/weekly-delivery', date: d(-2) },
        { id: 'D2', title: 'Actions list', kind: 'Actions list', url: 'https://example.com/actions', date: d(-2) },
      ],
    };
    P1.report.sections.find(s => s.id === 'summary').html = '<p>Two of three data domains are built. The test environment is the main risk to the plan.</p>';
    /* the Progress tracker (#189) and the text the Client Requested Report View reads (#192): fictional plan lines, typed, with the sums left to clark */
    { const ln = (no, text, end, st, w, pl, ac) => ({ id: 'l' + no + text.length, no: String(no), text, start: '', end: end ? d(end) : '', status: st, weight: w, planned: pl, achieved: ac, tasks: null, agents: null, workflows: null });
      P1.report.sections.splice(P1.report.sections.findIndex(s => s.id === 'milestones') + 1, 0, { id: 'tracker', type: 'tracker', title: 'Progress tracker', tr: { health: 'A', note: 'The test environment is late, which puts the start of user testing at risk.', cols: {}, overall: { actual: null, planned: null }, groups: [
        { id: 'g1', name: 'Foundation', lines: [ln(1, 'Mobilise the project team', -250, 'completed', 3, 3, 3), ln(2, 'Connect the first two data sources', -120, 'completed', 9, 9, 9), ln(3, 'Set up the test and live environments', -60, 'completed', 8, 8, 8)] },
        { id: 'g2', name: 'Build and test', lines: [ln(1, 'Customer data domain', -30, 'completed', 6, 6, 6), ln(2, 'Product data domain', 0, 'inprogress', 6, 5, 4), ln(3, 'Supplier data domain', 45, 'inprogress', 6, 1, 1), ln(4, 'User testing', 120, 'planned', 12, 0, 0)] },
        { id: 'g3', name: 'Training and handover', lines: [ln(1, 'Training plan agreed', -5, 'completed', 6, 6, 6), ln(2, 'Training wave 1', 60, 'inprogress', 16, 12, 12), ln(3, 'Training wave 2', 150, 'planned', 16, 0, 0), ln(4, 'Handover and support', 200, 'planned', 12, 0, 0)] }] } });
      const t = id => P1.report.sections.find(s => s.id === id);
      t('thisweek').html = '<ul><li>Pre-launch checks complete for the customer data domain</li><li>14 design specifications signed off; 2 in final review</li><li>Demo for the partner team closed with good feedback</li></ul>';
      t('nextweek').html = '<ul><li>Close the 2 outstanding design specifications</li><li>Start acceptance testing of the product data domain</li></ul>'; }
    const P2 = { code: 'CPR', name: 'Customer Portal Refresh', client: 'Demo client', ws: ['Design', 'Build'], health: 'G', reason: 'Design is complete and build is on plan.', current: '<p>Designs are signed off and build is on plan for the beta.</p>', report: defaultReport(), docs: [] };
    const items = [
      it('PDF', 'PDF-A-012', 'A', 'Data platform', 'Confirm test environment handover date', 'Sam Rivers', d(-3), 'Open', { priority: 'High', desc: 'The supplier has not confirmed when the test environment will be handed over.', update: 'Chased the supplier on Monday; waiting for a date.', ms: 'PDF-M-003', client: true, clientText: 'We are confirming the test environment handover date with the supplier.', updatedAt: seen(-9) }),
      it('PDF', 'PDF-A-015', 'A', 'Data platform', 'Share data quality rules for review', 'Jo Ellis', d(4), 'Open', { client: true, updatedAt: seen(-6) }),
      it('PDF', 'PDF-A-016', 'A', 'Data platform', 'Load the second source system', 'Ravi Mehta', d(32), 'Open', { ms: 'PDF-M-004' }),
      it('PDF', 'PDF-A-018', 'A', 'Testing', 'Write the user test scripts', 'Priya Nair', d(12), 'Open', { ms: 'PDF-M-003', updatedAt: seen(-6) }),
      it('PDF', 'PDF-A-019', 'A', 'Testing', 'Book the testers from both business units', 'Priya Nair', d(-1), 'Open', { priority: 'High' }),
      it('PDF', 'PDF-A-021', 'A', 'Change and training', 'Agree the training plan with the business units', 'Tom Hale', d(2), 'Open', { ms: 'PDF-M-002', client: true, updatedAt: seen(-2) }),
      it('PDF', 'PDF-A-022', 'A', 'Change and training', 'Draft the go-live communications', 'Tom Hale', d(28), 'Open', { ms: 'PDF-M-005' }),
      it('PDF', 'PDF-A-009', 'A', 'Data platform', 'Set up access for the analytics team', 'Ravi Mehta', d(-9), 'Closed'),
      it('PDF', 'PDF-003', 'R', 'Testing', 'Late test environment delays user testing', 'Priya Nair', d(14), 'Open', { priority: 'High', desc: 'If the environment is not ready by mid-month, user testing slips by at least two weeks.', update: 'Supplier escalation booked.', client: true, updatedAt: seen(-5) }),
      it('PDF', 'PDF-004', 'R', 'Change and training', 'Business units cannot release staff for training', 'Tom Hale', d(21), 'Open', { priority: 'Urgent' }),
      it('PDF', 'PDF-005', 'R', 'Data platform', 'Source data quality is lower than expected', 'Jo Ellis', d(30), 'Open', { priority: 'Low', client: true, update: 'Quality checks run each week; no action until the next review.', updatedAt: seen(-4) }),
      it('PDF', 'PDF-002', 'I', 'Data platform', 'Nightly load fails on large files', 'Ravi Mehta', d(5), 'Open', { priority: 'High', client: true, update: 'A fix for large files is in test; the first clean run is expected this week.', updatedAt: seen(-3) }),
      it('PDF', 'PDF-D-007', 'D', 'Data platform', 'Pilot scope limited to two business units', 'Steering group', d(-5), 'Made', { client: true }),
      it('PDF', 'PDF-D-008', 'D', 'Testing', 'Use synthetic data for the first test cycle', 'Priya Nair', d(6), 'Pending', { updatedAt: seen(-8) }),
      it('CPR', 'CPR-A-004', 'A', 'Build', 'Set up the test pipeline', 'Lena Fox', d(6), 'Open', { updatedAt: seen(-3) }),
      it('CPR', 'CPR-A-005', 'A', 'Build', 'Agree the beta user list', 'Omar Reid', d(15), 'Open', { ms: 'CPR-M-002', updatedAt: seen(-3) }),
      it('CPR', 'CPR-001', 'R', 'Build', 'Single sign-on changes need security review', 'Lena Fox', d(20), 'Open', { priority: 'High' }),
      it('CPR', 'CPR-D-002', 'D', 'Design', 'Keep the current colour scheme for the beta', 'Omar Reid', d(-12), 'Made'),
    ];
    const milestones = [
      ms('PDF', 'PDF-M-001', 'Discovery complete', 'Data platform', d(-17), { achievedOn: d(-17), progress: 100 }),
      ms('PDF', 'PDF-M-002', 'Training plan agreed', 'Change and training', d(-1), { forecast: d(3), manual: '' }),
      ms('PDF', 'PDF-M-003', 'User testing starts', 'Testing', d(18), { forecast: d(18), manual: 'At risk', progress: 20 }),
      ms('PDF', 'PDF-M-004', 'Second source loaded', 'Data platform', d(39), { progress: 10 }),
      ms('PDF', 'PDF-M-005', 'Pilot go-live', 'Change and training', d(46), { forecast: d(60), original: d(40), owner: 'Tom Hale', desc: 'Both business units live on the pilot.' }),
      ms('PDF', 'PDF-M-006', 'Testing signed off', 'Testing', d(75), { manual: 'Forecast' }),
      ms('CPR', 'CPR-M-001', 'Designs signed off', 'Design', d(-10), { achievedOn: d(-10), progress: 100 }),
      ms('CPR', 'CPR-M-002', 'Beta release', 'Build', d(30), { progress: 30 }),
    ];
    const uc = (code, id, title, status, headline, standing, x = {}) => ({ key: code + '/' + id, id, code, title, status, headline, standing, client: true, ...x });
    const usecases = [
      uc('PDF', '1.1', 'Automated loading of order data', 'Flag', 'Scope and access gaps; testing target end of next month', '<p>The loader built in discovery is being reused. The specification now looks wider than the loader can do today, and the specification owner has lost access to the code store.</p>'),
      uc('PDF', '1.2', 'Assisted invoice matching', 'On track', 'Specification signed; dates set, written confirmation pending', '<p>Specification signed. Test dates are agreed in principle and wait for written confirmation from the business.</p>'),
      uc('PDF', '1.3', 'Assisted ticket sorting\nGuided ticket routing', 'On track', 'Combined specification signed today', '<p>The two use cases share one specification, signed today. Build starts next week.</p>', { ref: '1.3 and 1.4' }),
      uc('PDF', '1.5', 'Automated match of order and payment data', 'Flag', 'One clarification session from sign-off', '<p>One open question on the matching rules remains before sign-off.</p>'),
      uc('PDF', '1.6', 'Address clean-up, after import\nAddress clean-up, before import', 'High risk', 'Likely next year; new requirements from the business', '<p>New requirements arrived this week. Delivery this year is unlikely; a decision is needed on scope.</p>', { ref: '1.6 and 1.7' }),
      uc('PDF', '2.1', 'Customer record checks and clean-up', 'On track', 'Specification signed; one test day each', '<p>Specification signed. One test day is booked for each record type.</p>'),
      /* two the dashboard does not show (the eye is off): the Use Cases page lists them, the published page leaves them out */
      uc('PDF', '2.2', 'Supplier record matching', 'Flag', 'Waiting for a sample of the supplier data', '<p>The matching rules are drafted. A sample of the supplier data is needed before testing can be planned.</p>', { client: false }),
      uc('PDF', '3.2', 'Automated monthly summaries', 'On track', 'Scoping starts next quarter', '<p>Agreed in principle. Scoping starts next quarter, after the pilot go-live.</p>', { client: false }),
    ];
    items.find(x => x.id === 'PDF-A-012').uc = '1.1'; items.find(x => x.id === 'PDF-A-015').uc = '1.1'; items.find(x => x.id === 'PDF-A-018').uc = '1.2';
    items.find(x => x.id === 'PDF-003').uc = '1.1'; items.find(x => x.id === 'PDF-D-008').uc = '1.6'; items.find(x => x.id === 'PDF-A-016').uc = '2.1'; items.find(x => x.id === 'PDF-005').uc = '2.2';
    items.push(it('PDF', 'PDF-A-023', 'A', 'Data platform', 'List the gaps between the specification and the loader', 'Jo Ellis', d(5), 'Open', { uc: '1.1', updatedAt: seen(-4) }));
    items.push(it('PDF', 'PDF-A-024', 'A', 'Testing', 'Arrange the expert and data platform meeting', 'Sam Rivers', d(8), 'Open', { uc: '1.1', updatedAt: seen(-4) }));
    items.push(it('PDF', 'PDF-A-025', 'A', 'Data platform', 'Hold the clarification session on matching rules', 'Priya Nair', d(3), 'Open', { uc: '1.5', updatedAt: seen(-4) }));
    items.forEach(x => { if (x.uc === undefined) x.uc = ''; });
    return { projects: [P1, P2], items, milestones, usecases };
  }

  /* ── IndexedDB ── */
  const DBNAME = 'clark-prototype', VER = 2, STORES = ['projects', 'items', 'milestones', 'usecases', 'history', 'meta'];
  let db = null;
  const open = () => new Promise((res, rej) => {
    let r; try { r = indexedDB.open(DBNAME, VER); } catch (e) { return rej(e); }
    r.onupgradeneeded = () => {
      const d = r.result;
      if (!d.objectStoreNames.contains('projects')) d.createObjectStore('projects', { keyPath: 'code' });
      if (!d.objectStoreNames.contains('items')) d.createObjectStore('items', { keyPath: 'id' });
      if (!d.objectStoreNames.contains('milestones')) d.createObjectStore('milestones', { keyPath: 'key' });
      if (!d.objectStoreNames.contains('usecases')) d.createObjectStore('usecases', { keyPath: 'key' });
      if (!d.objectStoreNames.contains('history')) d.createObjectStore('history', { keyPath: 'seq', autoIncrement: true });
      if (!d.objectStoreNames.contains('meta')) d.createObjectStore('meta', { keyPath: 'k' });
    };
    r.onsuccess = () => { const x = r.result; x.onversionchange = () => x.close(); res(x); }; r.onerror = () => rej(r.error); r.onblocked = () => rej(new Error('database blocked by another tab'));
  });
  const all = (store) => new Promise((res, rej) => { const q = db.transaction(store).objectStore(store).getAll(); q.onsuccess = () => res(q.result); q.onerror = () => rej(q.error); });
  let queue = Promise.resolve();
  function write(ops) {   // ops: [[store, 'put'|'delete', value|key]]
    if (!db) return Promise.resolve();
    /* one transaction per call; a bad record never blocks the writes after it */
    queue = queue.then(() => new Promise(res => {
      let t; try { t = db.transaction([...new Set(ops.map(o => o[0]))], 'readwrite'); } catch (e) { console.warn('clark: write skipped', e); return res(); }
      ops.forEach(([s, op, v]) => { try { if (op === 'clear') t.objectStore(s).clear(); else if (v !== undefined && v !== null) t.objectStore(s)[op](v); } catch (e) { console.warn('clark: one write skipped', s, op, e); } });
      t.oncomplete = () => res(); t.onerror = () => res(); t.onabort = () => res();
    })).catch(e => { console.warn('clark: write failed', e); });
    return queue;
  }
  const flush = () => queue;

  /* ── the in-memory copy everything reads ── */
  const S = { projects: [], items: [], milestones: [], usecases: [], history: [], profile: {}, people: {}, pubCopies: {}, ready: false, persistent: false };
  const PROFILE = ['name', 'alias', 'email', 'phone', 'org'];   // the user's own details (Settings › Profile); kept in meta, not with the demo data
  let seq = 0;

  async function load() {
    try { db = await open(); S.persistent = true; } catch (e) { db = null; }
    let data = null;
    if (db) {
      const [p, i, m, u, h] = await Promise.all(STORES.slice(0, 5).map(all));
      if (p.length) data = { projects: p, items: i, milestones: m, usecases: u, history: h };
      const meta = await all('meta');
      S.profile = (meta.find(r => r.k === 'profile') || {}).v || {};
      S.people = (meta.find(r => r.k === 'people') || {}).v || {};
      S.pubCopies = {}; meta.filter(r => /^pub:/.test(r.k)).forEach(r => { S.pubCopies[r.k] = r.v; });   /* the kept copies of published pages (FR-83a) */
    }
    if (!data) {
      data = seed(); data.history = [];
      if (db) await write(seedOps(data));
    } else if (migrate(data) && db) await write([...STORES.slice(0, 5).map(s => [s, 'clear']), ...seedOps(data), ...data.history.map(h => ['history', 'put', h])]);
    Object.assign(S, data, { ready: true });
    seq = Math.max(0, ...S.history.map(h => h.seq || 0));
    return S;
  }
  /* data saved by an earlier prototype used its own statuses and IDs: move it to creaite's, keeping every edit */
  function migrate(d) {
    const ST = { 'In progress': 'Open', Done: 'Closed', Agreed: 'Made' }, ids = {}, keys = {};
    d.items.filter(x => /^[A-Z0-9]+-[RI]-\d+$/.test(x.id)).forEach(x => {
      const taken = new Set(d.items.filter(y => y.code === x.code && /^[A-Z0-9]+-\d+$/.test(y.id)).map(y => y.id).concat(Object.values(ids)));
      let n = +x.id.split('-')[2], id; while (taken.has(id = `${x.code}-${String(n).padStart(3, '0')}`)) n++;
      ids[x.id] = id;
    });
    d.milestones.filter(m => /^M\d+$/.test(m.id)).forEach(m => { const id = `${m.code}-M-${m.id.slice(1).padStart(3, '0')}`; keys[m.key] = m.code + '/' + id; ids[m.code + ':' + m.id] = id; });
    if (!Object.keys(ids).length && !d.items.some(x => ST[x.status]) && !d.history.some(h => h.field === 'status' && (ST[h.from] || ST[h.to]))) return false;
    d.items.forEach(x => { x.status = ST[x.status] || x.status; x.id = ids[x.id] || x.id; if (x.ms) x.ms = ids[x.code + ':' + x.ms] || x.ms; });
    d.milestones.forEach(m => { if (keys[m.key]) { m.id = ids[m.code + ':' + m.id]; m.key = keys[m.key]; } });
    d.history.forEach(h => {
      if (h.kind === 'item') h.id = ids[h.id] || h.id; if (h.kind === 'ms') h.id = ids[h.code + ':' + h.id] || h.id;
      if (h.field === 'status') { h.from = ST[h.from] || h.from; h.to = ST[h.to] || h.to; }
    });
    return true;
  }
  async function reset() {
    if (db) await write(STORES.map(s => [s, 'clear']));
    const data = seed(); Object.assign(S, data, { history: [], people: {}, pubCopies: {} }); seq = 0;
    if (db) await write([...seedOps(data), ['meta', 'put', { k: 'profile', v: S.profile }]]);   // the profile is the user's, not demo data: a reset keeps it
  }

  const seedOps = d => [...d.projects.map(x => ['projects', 'put', x]), ...d.items.map(x => ['items', 'put', x]), ...d.milestones.map(x => ['milestones', 'put', x]), ...d.usecases.map(x => ['usecases', 'put', x])];
  const KIND = { item: ['items', 'id'], ms: ['milestones', 'key'], uc: ['usecases', 'key'], project: ['projects', 'code'] };
  const list = kind => kind === 'item' ? S.items : kind === 'ms' ? S.milestones : kind === 'uc' ? S.usecases : S.projects;
  function addHistory(rows) { rows.forEach(r => { r.seq = ++seq; r.at = r.at || stamp(); r.tz = r.tz || tzNow(); S.history.push(r); window.C && C.log && C.log('info', 'save', `${r.kind} ${r.id} ${r.field}`); }); return rows.map(r => ['history', 'put', r]); }

  /* change(kind, record, {field: value}, how, label) → undo(); one history row per changed field.
     Undo writes one row per field put back, with the value it came from and the one it returned to (FR-43a). */
  /* who made a change: the user's full name from Settings › Profile ("always use my full name"), or You until it is set */
  const who = how => (S.profile && S.profile.name || 'You') + (how ? ', ' + how : '');
  /* a history row's how is "<full name>, <where>": split it for display and for the Excel History sheet */
  const OLD_HOW = /^(ask clark|by hand|in words|Imported from )/;   /* rows saved before FR-43a carry no name */
  const whoHow = h => { const s = String(h.how || ''), i = s.indexOf(', '); return i >= 0 ? { who: s.slice(0, i), how: s.slice(i + 2) } : OLD_HOW.test(s) ? { who: '', how: s } : { who: s, how: '' }; };
  const idOf = (kind, rec) => kind === 'project' ? rec.code : rec.id;
  function change(kind, rec, changes, how = who('by hand'), label) {
    const [store] = KIND[kind], before = clone(rec), rows = [];
    Object.entries(changes).forEach(([f, v]) => {
      if (JSON.stringify(rec[f]) === JSON.stringify(v)) return;
      rows.push({ kind, id: idOf(kind, rec), code: rec.code, field: f, from: rec[f], to: v, how, text: label || '' });
      rec[f] = v;
    });
    if (!rows.length) return null;
    if (kind === 'item' && !('updatedAt' in changes)) rec.updatedAt = stamp();
    write([[store, 'put', rec], ...addHistory(rows)]);
    return () => {
      const was = label || rows[0].text || 'change to ' + rows.map(r => fieldName(r.field, kind).toLowerCase()).join(', '), back = [];
      rows.forEach(r => { if (JSON.stringify(rec[r.field]) !== JSON.stringify(before[r.field])) back.push({ kind, id: r.id, code: rec.code, field: r.field, from: keep(rec[r.field]), to: keep(before[r.field]), how: who('undo'), text: 'Undone: ' + was }); });
      rows.forEach(r => { if (!(r.field in before)) delete rec[r.field]; });   /* a field that was not there before goes again */
      Object.assign(rec, before);
      write([[store, 'put', rec], ...addHistory(back.length ? back : [{ kind, id: rows[0].id, code: rec.code, field: '*', how: who('undo'), text: 'Undone: ' + was }])]);
    };
  }
  function create(kind, rec, how = who('by hand'), text = 'Created') {
    const [store] = KIND[kind]; list(kind).push(rec);
    write([[store, 'put', rec], ...addHistory([{ kind, id: idOf(kind, rec), code: rec.code, field: '+', how, text }])]);
    return () => remove(kind, rec, who('undo'), 'Creation undone');
  }
  function remove(kind, rec, how = who('by hand'), text = 'Deleted', quiet) {
    const [store, key] = KIND[kind], arr = list(kind), i = arr.indexOf(rec); if (i < 0) return null; arr.splice(i, 1);
    write([[store, 'delete', rec[key]], ...(quiet ? [] : addHistory([{ kind, id: idOf(kind, rec), code: rec.code, field: '-', how, text }]))]);
    return () => { arr.splice(i, 0, rec); write([[store, 'put', rec], ...addHistory([{ kind, id: idOf(kind, rec), code: rec.code, field: '+', how: who('undo'), text: 'Restored' }])]); };
  }
  /* the profile: one save per change, with an undo, like every other setting */
  function setProfile(changes) {
    const before = { ...S.profile }, next = { ...S.profile };
    Object.entries(changes).forEach(([f, v]) => { if (PROFILE.includes(f)) next[f] = String(v || '').trim(); });
    if (PROFILE.every(f => (next[f] || '') === (before[f] || ''))) return null;
    S.profile = next; write([['meta', 'put', { k: 'profile', v: next }]]); window.C && C.log && C.log('info', 'save', 'profile');
    return () => { S.profile = before; write([['meta', 'put', { k: 'profile', v: before }]]); };
  }
  /* a record is archived, never deleted (FR-43c): a project (#132; it and everything in it), a work item or a milestone (#166). It leaves the default
     views and comes back with Restore. One step, one Undo, and a history row each way ("Archived", "Restored"; FR-43a). Nothing of its data is removed. */
  function archive(rec, on, how = who('in the project list'), kind = 'project') {
    const [store] = KIND[kind], id = idOf(kind, rec), was = !!rec.archived, text = on ? 'Archived' : 'Restored'; if (was === !!on) return null;
    if (on) rec.archived = true; else delete rec.archived;
    write([[store, 'put', rec], ...addHistory([{ kind, id, code: rec.code, field: '*', how, text }])]);
    return () => { if (was) rec.archived = true; else delete rec.archived; write([[store, 'put', rec], ...addHistory([{ kind, id, code: rec.code, field: '*', how: who('undo'), text: 'Undone: ' + text.toLowerCase() }])]); };
  }
  /* several changes as one step, with one undo */
  function batch(fns) { const undos = fns.map(f => f()).filter(Boolean); return undos.length ? () => undos.reverse().forEach(u => u()) : null; }
  const historyOf = (kind, id) => S.history.filter(h => h.kind === kind && h.id === id).slice().reverse();

  /* ── reading history back: plain field names, formatted values, local time (FR-43a) ── */
  const FN = { title: 'Title', status: 'Status', rag: 'Rating', owner: 'Owner', due: 'Due date', priority: 'Priority', ws: 'Workstream', ms: 'Milestone', uc: 'Use case', client: 'Client-visible', clientText: 'Client wording', desc: 'Description', update: 'Latest update', type: 'Type',
    name: 'Name', agreed: 'Agreed date', forecast: 'Forecast', achievedOn: 'Achieved date', manual: 'State', progress: 'Progress', original: 'Original date', note: 'Note', chase: 'Chases sent', standing: 'Where it stands', headline: 'Headline', health: 'Health',
    current: 'Current state', report: 'Report layout', docs: 'Supporting documents', published: 'Published', source: 'Source', reason: 'Health reason', ref: 'Shown as', updatedAt: 'Last updated', publish: 'Publishing folders', clientAct: 'Needed from the client' };
  const fieldName = (f, kind) => kind === 'project' && f === 'client' ? 'Client' : FN[f] || f.replace(/([A-Z])/g, ' $1').replace(/^./, c => c.toUpperCase());
  /* rich text fields keep their whole from and to; the Activity tab shows these as a word diff */
  const RICH = ['update', 'desc', 'clientText', 'standing', 'current', 'note'], COMMENT = ['update', 'note', 'standing', 'current'];
  const DATES = ['due', 'agreed', 'forecast', 'achievedOn', 'original'], HEALTH = { R: 'Red', A: 'Amber', G: 'Green' };
  /* a value as a person reads it: dates DD-MM-YYYY, true/false as on/off, "none" when empty; null when it is too big to show (a layout, a list of documents) */
  const showVal = (f, v) => {
    if (v && typeof v === 'object' && !(Array.isArray(v) && v.every(x => typeof x === 'string'))) return null;
    if (Array.isArray(v)) return v.join(', ') || 'none';
    if (v === true) return 'on'; if (v === false) return 'off';
    if (DATES.includes(f)) return fd(v) || 'none';
    if (f === 'health') return HEALTH[v] || 'none';
    if (f === 'progress') return v == null || v === '' ? 'not set' : v + '%';
    if (f === 'manual') return v || 'following the dates';
    if (f === 'chase') return String(v || 0);
    return v == null || v === '' ? 'none' : String(v);
  };
  /* when a row was made, in the viewer's local time as DD-MM-YYYY HH:MM: rows keep their local stamp and the offset they were made at */
  const whenIso = h => { const at = h.at || ''; if (!at) return ''; let l = at;
    if (h.tz) { const d = new Date(at.replace(' ', 'T') + ':00' + h.tz); if (!isNaN(d)) l = `${toIso(d)} ${pad(d.getHours())}:${pad(d.getMinutes())}`; }
    return l; };
  const when = h => { const l = whenIso(h); return l ? fd(l.slice(0, 10)) + ' ' + l.slice(11, 16) : ''; };

  /* ── how fresh an item is (FR-35a, #119): worked out from history, no new columns. Raised = its first row ("Created"); an item that came
     in with the seed has no such row, so the day it was imported stands in. Last reviewed = the latest change a person made by hand
     (not ask clark, not an Excel import, not an Undo); never earlier than raised. "Not reviewed in 14 days" is an open item whose
     last review is 14 or more days ago. ── */
  const STALE_DAYS = 14, NOT_HAND = /^(via ask clark|by Excel import|undo)/;
  const byHand = h => { const w = whoHow(h); return !NOT_HAND.test(w.how) && !/^Imported from /.test(w.how); };
  function fresh(x) {
    const rows = S.history.filter(h => h.kind === 'item' && h.id === x.id && h.code === x.code), first = rows.slice().sort((a, b) => a.seq - b.seq)[0], made = rows.find(h => h.field === '+');
    const raised = made ? whenIso(made).slice(0, 10) : x.imported || (first ? whenIso(first).slice(0, 10) : (x.updatedAt || '').slice(0, 10));
    const mine = rows.filter(byHand).map(h => whenIso(h).slice(0, 10)).sort().pop() || '';
    const reviewed = [raised, mine].sort().pop() || raised;
    return { raised, reviewed, ago: reviewed ? -days(reviewed) : 0 };
  }
  const notReviewed = x => isOpenItem(x) && fresh(x).ago >= STALE_DAYS;
  const isOpenItem = x => !['Closed', 'Cancelled', 'Withdrawn', 'Made'].includes(x.status);
  const gap = x => isOpenItem(x) && (!String(x.owner || '').trim() || !x.due);   /* open, and no owner or no due date */

  /* milestone state, as creaite derives it from the dates (BL-245, tracker.py milestone_state): achieved, overdue, slipped, at risk (by hand), on track */
  function msState(m) {
    if (m.achievedOn) return 'Achieved';
    if (m.manual === 'Forecast') return 'Forecast';   // a date not yet agreed
    if (m.manual === 'At risk') return 'At risk';
    if (m.agreed < TODAY) return 'Overdue';   // creaite counts late from the agreed date, not the forecast
    if (m.forecast && m.forecast > m.agreed) return 'Slipped';
    return 'On track';
  }
  /* creaite's client words for a milestone (tracker.py MS_CLIENT_WORD): a slipped one reads "Expected later", a late one "Late" */
  const MS_CLIENT_WORD = { Slipped: 'Expected later', Overdue: 'Late' };
  const msWord = (st, client) => client ? MS_CLIENT_WORD[st] || st : st;
  /* the next milestone ID, creaite's <CODE>-M-NNN */
  const nextMsId = code => `${code}-M-${String(Math.max(0, ...S.milestones.filter(m => m.code === code).map(m => +m.id.split('-').pop() || 0)) + 1).padStart(3, '0')}`;
  /* slip as creaite v2.6.9 works it out (build_dashboard.py; the ruling on #32): only a planned milestone with an agreed date
     counts (not achieved, not a Forecast); it is expected on the later of its forecast (or its agreed date) and, once the agreed
     date has passed, today; slip is the days from the agreed date to then */
  const expected = m => { if (m.achievedOn || m.manual === 'Forecast' || !m.agreed) return ''; const f = m.forecast || m.agreed; return [f, m.agreed < TODAY ? TODAY : m.agreed].sort()[1]; };
  const slip = m => { const e = expected(m); return e ? Math.round((new Date(e) - new Date(m.agreed)) / 864e5) : 0; };

  /* ── numbered publications (FR-83a, #120): each publish of a project gets the next number; its page is kept (the last 10 per project) in the
     browser's database beside the record in the project's list of publications ── */
  const PUB_KEEP = 10, pubKey = (code, n) => `pub:${code}:${n}`;
  const pubNo = (p, i) => { const r = (p.published || [])[i]; return r ? (r.n || i + 1) : 0; };
  const pubNext = p => Math.max(0, ...(p.published || []).map((r, i) => r.n || i + 1)) + 1;
  const pubCopy = (code, n) => S.pubCopies[pubKey(code, n)] || null;
  function pubKeep(code, n, copy) {
    const ops = [], key = pubKey(code, n); S.pubCopies[key] = copy; ops.push(['meta', 'put', { k: key, v: copy }]);
    const mine = Object.keys(S.pubCopies).filter(k => k.startsWith(`pub:${code}:`)).sort((a, b) => +a.split(':')[2] - +b.split(':')[2]);
    mine.slice(0, Math.max(0, mine.length - PUB_KEEP)).forEach(k => { delete S.pubCopies[k]; ops.push(['meta', 'delete', k]); });
    return write(ops);
  }
  const lastSeq = () => seq;
  /* people (FR-31a, v0.5; a light simulation): details kept by name, in meta: { 'Sam Rivers': { email, org, role } } */
  const PERSON = ['email', 'org', 'role'];
  function setPeople(rows) {
    const before = JSON.parse(JSON.stringify(S.people || {})), next = JSON.parse(JSON.stringify(S.people || {}));
    rows.forEach(r => { const k = String(r.name || '').trim(); if (!k) return; const cur = next[k] || {}; PERSON.forEach(f => { if (r[f] !== undefined) cur[f] = String(r[f] || '').trim(); }); next[k] = cur; });
    if (JSON.stringify(next) === JSON.stringify(before)) return null;
    S.people = next; write([['meta', 'put', { k: 'people', v: next }]]); window.C && C.log && C.log('info', 'save', 'people');
    return () => { S.people = before; write([['meta', 'put', { k: 'people', v: before }]]); };
  }

  window.ClarkDB = { S, load, reset, flush, change, create, remove, archive, batch, setProfile, PROFILE, historyOf, who, whoHow, FN, fieldName, RICH, COMMENT, showVal, when, whenIso, fresh, notReviewed, gap, STALE_DAYS, pubNo, pubNext, pubCopy, pubKeep, PUB_KEEP, lastSeq, setPeople, msState, msWord, nextMsId, migrate, slip, expected, write, clone, defaultReport,
    TYPES, STATUSES, PRIORITIES, TODAY, toIso, addDays, fd, days, stamp, friday, pad };
})();
