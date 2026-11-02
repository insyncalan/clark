/* clark prototype: ask clark, in creaite's ask panel (full height on the right). Opens with "/" or ⌘J; Esc or a click outside
   closes it; an office quip shows while it works (creaite's list and timing: each quip stays 5 to 10 seconds, never the same twice
   running). Its purpose: help make the most accurate report possible. In this prototype the answers are worked out
   by rules from the project's data; the real ask clark uses Claude over clark's data and the project's source folders. */
(function () {
  'use strict';
  const C = window.C, D = C.D, esc = C.esc;
  /* creaite v2.6.9 system/templates/dashboard/src/ask.js QUIPS (BL-259), copied as they are */
  const QUIPS = ['Percolating coffee', 'Getting my steps in', 'Waiting for the conference call to start', "You're on mute", 'Circling back', 'Touching base', 'Taking this offline', 'Aligning stakeholders', 'Socialising the deck', 'Putting it in the parking lot',
    'Boiling a small ocean', 'Moving the needle', 'Picking the low-hanging fruit', 'Running it up the flagpole', 'Booking a meeting about the meeting', 'Waiting for the projector to connect', 'Hunting for a free meeting room', 'Reply-all-ing, carefully', 'Turning amber back to green',
    'Herding stakeholders', 'Adding an action to the action log', 'Queueing for the kettle', 'Looking for the HDMI dongle', 'Can everyone see my screen?', 'Rescheduling the reschedule', 'Doing a deep dive', 'Taking it to the steering committee', 'Double-clicking on that', 'Going round the room',
    'Adding it to the backlog', 'Chasing sign-off', 'Checking the RACI', 'Re-baselining the plan', 'Syncing on the sync', 'Grabbing five minutes', 'Reading the pre-read', 'Finding a whiteboard pen that works', 'Raising a ticket with IT', 'Wordsmithing the slide', 'Ideating',
    'Leveraging the synergies', 'Updating the RAG status', 'Waiting for the lift', 'Joining from my phone', 'Finding the meeting link', 'Sorry, you go', 'Just finishing another call', 'Pinging the stakeholders', 'Bringing the deck to life', 'Locking in the agenda',
    'Finding the action log', 'Unmuting', 'Sharing the wrong screen', 'Sharing the right screen', 'Waiting for the room to empty', 'Collecting the printouts', 'Refilling the stapler', 'Looking for a working pen', 'Fixing the wobbly chair', 'Warming up the projector',
    'Asking who has the clicker', 'Moving the stand-up to Tuesday', 'Waiting for quorum', 'Taking the minutes', 'Agreeing the next steps', 'Parking that for now', 'Coming back to that', 'Noting the dependency', 'Updating your project record', 'Colour-coding the spreadsheet',
    'Merging two spreadsheets', 'Finding the latest version', 'Renaming it final_final', 'Checking the shared drive', 'Clearing the inbox', 'Flagging it for later', 'Drafting a polite nudge', 'Softening the wording', 'Adding a gentle reminder', 'Writing the out-of-office',
    'Booking the next check-in', 'Finding a slot that suits everyone', 'Declining a clashing invite', 'Accepting tentatively', 'Waiting for the calendar to load', 'Moving my lunch', 'Reheating my coffee', 'Finding the good mugs', 'Wiping the whiteboard',
    'Taking a photo of the whiteboard', 'Drawing a box and an arrow', 'Adding another arrow', 'Labelling the swimlanes', 'Sorting the sticky notes', 'Grouping the sticky notes', 'Voting with dots', 'Timeboxing it', 'Setting a five-minute timer',
    'Running slightly over', 'Going round once more', 'Asking any other business', 'Thanking everyone for their time', 'Sending the follow-up', 'Attaching the slides', 'Forgetting the attachment', 'Tidying the agenda', 'Numbering the actions', 'Assigning an owner',
    'Agreeing a due date', 'Nudging the due date', 'Checking the dependencies', 'Raising a risk', 'Scoring the risk', 'Mitigating the risk', 'Closing the issue', 'Logging a decision', 'Recording who agreed', 'Printing double-sided', 'Unjamming the printer',
    'Finding the meeting room key', 'Adjusting the air conditioning', 'Opening a window', 'Charging my laptop', 'Finding a free socket', 'Restarting for updates', 'Reconnecting to the Wi-Fi', 'Dialling in', 'Spelling my name for the call', 'Waiting in the lobby',
    'Admitting everyone from the lobby', 'Turning my camera on', 'Blurring my background', "Checking I'm not on mute", 'Saying hello to the room', 'Asking for a quick show of hands', 'Reading the room', 'Summarising the discussion', 'Playing it back', 'Checking for questions',
    'Writing it in plain English', 'Cutting it to one page', 'Making the font smaller', 'Aligning the boxes', 'Fixing the bullet points', 'Choosing a better chart', 'Labelling the axes', 'Checking the numbers add up', 'Double-checking the dates', 'Converting the time zones', 'Proofreading'];
  let deck = [], now = { text: '', i: -1, until: 0 };
  const deal = () => { if (!deck.length) { deck = QUIPS.map((_, i) => i); for (let i = deck.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [deck[i], deck[j]] = [deck[j], deck[i]]; } if (deck.length > 1 && deck[deck.length - 1] === now.i) [deck[0], deck[deck.length - 1]] = [deck[deck.length - 1], deck[0]]; } return deck.pop(); };
  C.quipNow = () => { const t = Date.now(); if (!now.text || t >= now.until) { const i = deal(); now = { text: QUIPS[i] + '…', i, until: t + 5000 + Math.random() * 5000 }; } return now.text; };
  setInterval(() => C.$$('#askWork .quip').forEach(q => { const t = C.quipNow(); if (q.textContent !== t) q.textContent = t; }), 500);

  const el = () => C.$('#ask');
  C.askIsOpen = () => el().classList.contains('on');
  let returnTo = null;
  /* width: drag the left edge, like the peek; kept for next time; double-click goes back to the usual width */
  const applyW = () => { const w = C.store.get('askW', 0); el().style.width = w ? Math.min(Math.max(360, w), innerWidth) + 'px' : ''; };
  document.addEventListener('DOMContentLoaded', () => {
    const h = document.createElement('div'); h.className = 'ask-resize'; h.title = 'Drag to change the width; double-click for the usual width'; h.setAttribute('aria-hidden', 'true'); el().prepend(h); applyW();
    h.addEventListener('pointerdown', e => { e.preventDefault(); h.classList.add('drag'); try { h.setPointerCapture(e.pointerId); } catch (x) { /* synthetic event */ }
      const move = ev => { el().style.width = Math.max(360, Math.min(innerWidth, innerWidth - ev.clientX)) + 'px'; };
      const up = ev => { h.classList.remove('drag'); h.removeEventListener('pointermove', move); h.removeEventListener('pointerup', up); C.store.set('askW', Math.round(Math.max(360, Math.min(innerWidth, innerWidth - ev.clientX)))); };
      h.addEventListener('pointermove', move); h.addEventListener('pointerup', up); });
    h.addEventListener('dblclick', () => { C.store.set('askW', 0); applyW(); });
  });
  /* What will be sent (FR-62b, #122): before a question goes, one plain sentence says what it carries, with the details a click away.
     The real ask clark sends the passages it needs to Claude; here nothing is sent, but the preview works out what would be. */
  const wc = t => String(t || '').split(/\s+/).filter(Boolean).length, pl = (t) => C.plain ? C.plain(t) : String(t || '');
  C.sendPreview = () => {
    const p = C.P(); if (!p) return null;
    const its = C.items(), ms = C.mss(), ucs = D.S.usecases.filter(u => u.code === p.code && !u.archived), src = p.sources || [];
    const wi = its.reduce((n, x) => n + wc(x.title) + wc(pl(x.desc)) + wc(pl(x.update)) + wc(pl(x.clientText)), 0), wm = ms.reduce((n, m) => n + wc(m.name) + wc(pl(m.desc)), 0), wu = ucs.reduce((n, u) => n + wc(u.title) + wc(u.headline) + wc(pl(u.standing)), 0);
    const total = wi + wm + wu, conn = C.store.get('aiConn', {}).claude;
    return { project: p.name, items: its.length, milestones: ms.length, usecases: ucs.length, folders: src, wi, wm, wu, total, approx: Math.max(10, Math.round(total / 10) * 10), provider: 'Claude', connected: !!conn };
  };
  let prevOpen = false;
  const round = n => n.toLocaleString('en-GB');
  const drawPrev = () => { const b = C.$('#askPrev'), v = C.sendPreview(); if (!b) return; if (!v) { b.innerHTML = ''; return; }
    b.innerHTML = `<span id="askPrevT">A question sends ${esc(v.project)}’s work items, milestones and use cases (about ${round(v.approx)} words)${v.folders.length ? ` and ${v.folders.length} named source folder${v.folders.length > 1 ? 's' : ''}` : ''} to ${v.provider}.</span> <button type="button" class="link" id="askPrevB" aria-expanded="${prevOpen}" aria-controls="askPrevD">${prevOpen ? 'Hide details' : 'Show details'}</button>
      <ul class="ask-prev-d" id="askPrevD"${prevOpen ? '' : ' hidden'}><li><b>Work items:</b> ${v.items}, about ${round(v.wi)} words</li><li><b>Milestones:</b> ${v.milestones}, about ${round(v.wm)} words</li><li><b>Use cases:</b> ${v.usecases}, about ${round(v.wu)} words</li>
        <li><b>Source folders:</b> ${v.folders.length ? v.folders.map(f => esc(f)).join('; ') : 'none named'}${v.folders.length ? ' (read only)' : ''}</li><li><b>Provider:</b> ${v.provider}${v.connected ? '' : ', not signed in yet (Settings › AI)'}</li><li>Mail, Teams and calendars are never sent. Prototype: nothing is sent; the answers are worked out here.</li></ul>`;
    C.$('#askPrevB').addEventListener('click', () => { prevOpen = !prevOpen; drawPrev(); C.$('#askPrevB').focus(); }); };
  C.askPreviewDraw = drawPrev;
  /* Settings › Asking off (#170): the button and key still open the panel, which says so, with a link to the switch; the send line goes, as nothing is sent */
  C.askOffDraw = nudge => { const n = C.$('#askOff'); if (!n) return; const off = !C.askOn(); n.hidden = !off; C.$('#askPrev').hidden = off; if (!off && C.askIsOpen()) greet();
    if (off && nudge) C.$('#askOffGo').focus(); };
  document.addEventListener('DOMContentLoaded', () => {
    C.$('#askLog').insertAdjacentHTML('beforebegin', '<p class="ask-off" id="askOff" role="status" hidden>Asking is off. <a class="link" href="#sources" id="askOffGo">Turn it on in Settings.</a></p>');
    C.$('#askOffGo').addEventListener('click', e => { e.preventDefault(); C.askClose(); C.go('settings', { keepScroll: true }); setTimeout(() => { if (C.settingsGo('sources')) C.$('#askSw')?.focus({ preventScroll: true }); }, 80); });
  });
  C.askOpen = () => { if (C.askIsOpen()) { C.$('#askIn').focus(); return; } returnTo = document.activeElement; el().classList.add('on'); el().setAttribute('aria-hidden', 'false'); C.$('#askBtn').setAttribute('aria-expanded', 'true'); greet(); drawPrev(); C.askOffDraw(); setTimeout(() => C.$('#askIn').focus(), 60); };
  C.askClose = () => { if (!C.askIsOpen()) return; el().classList.remove('on'); el().setAttribute('aria-hidden', 'true'); C.$('#askBtn').setAttribute('aria-expanded', 'false'); if (returnTo && returnTo.isConnected) returnTo.focus({ preventScroll: true }); };
  C.askToggle = () => C.askIsOpen() ? C.askClose() : C.askOpen();
  C.askReset = () => { C.$('#askLog').innerHTML = ''; };
  const greet = () => { if (C.$('#askLog').children.length || !C.askOn()) return; const p = C.P(), n = (p.sources || []).length;
    bot(`Hi. I can check this week's report on <b>${esc(p.name)}</b>, or answer questions about the project. ${n ? `I use clark's own data and ${n} source folder${n > 1 ? 's' : ''}. ` : ''}Anything I change, you can undo.`); };

  /* a click outside closes it (not on the button that opens it, a menu, a dialog or the peek it opened) */
  document.addEventListener('mousedown', e => { if (!C.askIsOpen()) return; const t = e.target; if (el().contains(t) || C.$('#askBtn').contains(t) || t.closest('.menu,dialog,.peek,.toast')) return; C.askClose(); }, true);

  const scroll = () => { const l = C.$('#askLog'); l.scrollTo({ top: l.scrollHeight, behavior: C.reduce ? 'auto' : 'smooth' }); };
  const me = t => { C.$('#askLog').insertAdjacentHTML('beforeend', `<div class="msg me">${esc(t)}</div>`); scroll(); };
  function bot(h) { C.$('#askLog').insertAdjacentHTML('beforeend', `<div class="msg bot">${h}</div>`); scroll(); wire(); }
  const link = x => `<a class="link" data-open="${x.id}">${x.id}</a> ${esc(x.title)}`;
  /* ── passages from files (#212, ask clark slice 5). The real clark reads the project's saved source folders, read only: text, Markdown and Word. A PDF is not read yet and is
     said so, never guessed at. Every passage has an id (P1, P2…) and every answer cites ids and names the file. The panel says how many files were left out for safety, how many
     PDFs were not read and, when too many passages matched, that only the closest were used. The prototype cannot open a folder: a folder you choose in Settings › Asking
     holds a few made-up files, by its last name (Minutes, Designs, Status reports); any other folder is empty here. The words are the product's (ask_service.py). ── */
  const FILES = {
    'Minutes': [
      { n: 'Steering committee 21-10-2026.md', k: 'md', t: 'The steering committee agreed to hold the go-live date and asked the supplier for a written recovery plan by Friday. Access to the source data is the main blocker.' },
      { n: 'Finance workshop.txt', k: 'txt', t: 'The finance workshop agreed the invoice matching rules. Exceptions go to a named reviewer, and the reviewers are trained before the pilot.' },
      { n: 'Supplier call.docx', k: 'docx', t: 'The supplier confirmed that capacity is limited in November and offered two more people from December, once a signed change request is in.' },
      { n: 'Contract summary.pdf', k: 'pdf' }, { n: 'Notes.zip', k: 'other' }, { n: '.env', k: 'secret' }],
    'Designs': [
      { n: 'Data model.md', k: 'md', t: 'The data model keeps one table for invoices and one for matches. A match records who confirmed it and when.' },
      { n: 'Screens.pdf', k: 'pdf' }],
    'Status reports': [
      { n: 'Week 41 status.md', k: 'md', t: 'Week 41: the pilot data load is on track. The supplier has not yet sent the recovery plan, and the data access request is still open.' },
      { n: 'Week 42 status.docx', k: 'docx', t: 'Week 42: testing started on the invoice matching. Two defects are open and both are due to be fixed before the board review.' }] };
  const ASK_MAX_PASSAGES = 3, STOP_WORDS = new Set(['what', 'which', 'when', 'where', 'about', 'there', 'their', 'have', 'does', 'with', 'from', 'that', 'this', 'were', 'your', 'into', 'files', 'file', 'folder', 'folders', 'notes', 'said', 'says']);
  C.askRead = (q, p = C.P()) => {
    const src = (p && p.sources) || []; if (!src.length) return null;
    const files = src.flatMap(s => FILES[String(s).replace(/\/+$/, '').split('/').pop()] || []);
    const words = String(q || '').toLowerCase().split(/\W+/).filter(w => w.length > 3 && !STOP_WORDS.has(w));
    const hits = files.filter(f => f.t).map(f => ({ f, n: words.filter(w => f.t.toLowerCase().includes(w)).length })).filter(x => x.n).sort((a, b) => b.n - a.n);
    const kept = hits.slice(0, ASK_MAX_PASSAGES).map((x, i) => ({ id: 'P' + (i + 1), file: x.f.n, text: x.f.t }));
    return { passages: kept, tooMany: hits.length > kept.length, pdf: files.filter(f => f.k === 'pdf').length, other: files.filter(f => f.k === 'other').length, safety: files.filter(f => f.k === 'secret').length, read: files.filter(f => f.t).length };
  };
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  C.askFileNotes = f => [f.safety ? `${plural(f.safety, 'file was', 'files were')} left out for safety.` : '', f.pdf ? `${plural(f.pdf, 'PDF file was', 'PDF files were')} not read: PDF is not supported yet.` : '',
    f.other ? `${plural(f.other, 'file was', 'files were')} not read because of its type.` : '', f.tooMany ? 'Some of the report was too long to send in full, so only the parts closest to your question were used.' : ''].filter(Boolean);
  const fileHtml = f => `${f.passages.length ? `From your folders:<ul class="ask-pass">${f.passages.map(x => `<li><b>${x.id}</b> <i>${esc(x.file)}</i>: “${esc(x.text)}”</li>`).join('')}</ul>` : 'I did not find that in the files in your folders.'}${C.askFileNotes(f).map(n => `<p class="ask-note">${esc(n)}</p>`).join('')}`;

  function wire() {
    C.$$('#askLog [data-open]').forEach(a => a.onclick = () => C.openItem(a.dataset.open, C.items().map(i => i.id)));
    C.$$('#askLog [data-ms]').forEach(a => a.onclick = () => C.openMs(a.dataset.ms));
    C.$$('#askLog [data-do]').forEach(b => b.onclick = () => { const f = ACTIONS[b.dataset.do]; if (f) { f(b.dataset); b.disabled = true; } });
  }
  const ACTIONS = {
    summary: d => { const p = C.P(), r = D.clone(p.report), s = r.sections.find(x => x.id === 'summary') || r.sections.find(x => x.type === 'text'); if (!s) return; s.html = decodeURIComponent(d.html); const u = D.change('project', p, { report: r }, D.who('via ask clark')); C.refresh(); C.toast(`${s.title} written by ask clark`, u); },
    update: d => { const x = D.S.items.find(i => i.id === d.id); if (!x) return; const u = D.change('item', x, { update: decodeURIComponent(d.text) }, D.who('via ask clark')); C.refresh(); C.toast(`${x.id} latest update saved`, u); },
    show: d => { const ids = d.ids.split(','); const u = D.batch(ids.map(id => () => D.change('item', D.S.items.find(i => i.id === id), { client: true }, D.who('via ask clark')))); C.refresh(); C.toast(`${ids.length} shown on the page`, u); },
    health: d => { const p = C.P(); const u = D.change('project', p, { health: d.h }, D.who('via ask clark')); C.refresh(); C.toast('Health changed', u); },
  };

  /* checking the report: the things that make a weekly report wrong */
  function check() {
    const p = C.P(), its = C.items(), ms = C.mss(), notes = [];
    const overHidden = its.filter(x => x.type === 'A' && C.isOpen(x) && x.due && D.days(x.due) < 0 && !x.client);
    if (overHidden.length) notes.push(`${overHidden.length} overdue action${overHidden.length > 1 ? 's are' : ' is'} left out of the page: ${overHidden.map(link).join('; ')}. <div class="acts"><button class="btn sm" data-do="show" data-ids="${overHidden.map(x => x.id).join(',')}">Show ${overHidden.length > 1 ? 'them' : 'it'}</button></div>`);
    const slipped = ms.filter(m => !m.achievedOn && D.slip(m) > 0);
    if (p.health === 'G' && (slipped.length || its.some(x => (['R', 'I'].includes(x.type) && C.ragOf(x) === 'R') && C.isOpen(x)))) notes.push(`Health says On track, but ${slipped.length ? `${slipped.length} milestone${slipped.length > 1 ? 's have' : ' has'} slipped` : 'a red risk is open'}. <div class="acts"><button class="btn sm" data-do="health" data-h="A">Set it to At risk</button></div>`);
    if (!p.reason || p.reason.length < 12) notes.push('The health has no real reason. One line on why helps the reader.');
    const stale = its.filter(x => C.isOpen(x) && x.client && !x.update);
    if (stale.length) notes.push(`${stale.length} item${stale.length > 1 ? 's' : ''} on the page ${stale.length > 1 ? 'have' : 'has'} no latest update: ${stale.slice(0, 4).map(link).join('; ')}${stale.length > 4 ? '…' : ''}.`);
    const ucMismatch = D.S.usecases.filter(u => u.code === p.code && !u.archived && u.status === 'On track' && its.some(x => x.uc === u.id && C.isOpen(x) && ((x.type === 'A' && x.due && D.days(x.due) < 0) || (['R', 'I'].includes(x.type) && C.ragOf(x) === 'R'))));
    if (ucMismatch.length) notes.push(`Use case ${ucMismatch.map(u => esc(u.ref || u.id)).join(', ')} ${ucMismatch.length > 1 ? 'say' : 'says'} On track, but has overdue or red work.`);
    const summary = p.report.sections.find(s => s.id === 'summary');
    if (summary && !summary.hidden && !(summary.html || '').replace(/<[^>]+>/g, '').trim()) notes.push('The Summary is empty. I can draft one: ask "Summarise this week".');
    const docs = (p.docs || []).filter(d => !d.hidden && D.days(d.date) >= -7);
    if (!docs.length) notes.push('No supporting documents from this week are linked yet.');
    return notes.length ? `I checked the report and found ${notes.length} thing${notes.length > 1 ? 's' : ''} to look at:<ul>${notes.map(n => `<li>${n}</li>`).join('')}</ul>` : 'I checked the report: the health, the items on the page, milestones and use cases agree. Nothing to fix.';
  }
  function answer(q) {
    const p = C.P(), s = q.toLowerCase(), its = C.items(), open = its.filter(C.isOpen); let m;
    if ((m = /draft an update for ([a-z]+-[a-z]-\d+)/i.exec(q))) { const x = its.find(i => i.id.toLowerCase() === m[1].toLowerCase()); if (!x) return 'I could not find that item.'; const t = C.draftUpdate(x);
      return `A draft for ${link(x)}:<p style="margin:8px 0 0"><i>"${esc(t)}"</i></p><div class="acts"><button class="btn sm" data-do="update" data-id="${x.id}" data-text="${encodeURIComponent(t)}">Save as the latest update</button></div>`; }
    const fl = /\b(minutes|notes|files?|folders?|documents?|steering|workshop|supplier call|contract|designs?|according to)\b/.test(s) ? C.askRead(q, p) : null;
    if (fl) return fileHtml(fl);
    if (/check|accurate|wrong|review the report/.test(s)) return check();
    if (/overdue|late|behind/.test(s)) { const xs = open.filter(x => x.type === 'A' && x.due && D.days(x.due) < 0); return xs.length ? `${xs.length} overdue action${xs.length > 1 ? 's' : ''}:<ul>${xs.map(x => `<li>${link(x)}, ${esc(x.owner)}, due ${D.fd(x.due)}${x.client ? '' : ' <span class="tag">not on the page</span>'}</li>`).join('')}</ul>` : 'Nothing is overdue.'; }
    if (/red|risk|issue/.test(s)) { const xs = open.filter(x => (x.type === 'R' || x.type === 'I') && (s.includes('red') ? (['R', 'I'].includes(x.type) && C.ragOf(x) === 'R') : true)); return xs.length ? `${s.includes('red') ? 'Red' : 'Open'} risks and issues:<ul>${xs.map(x => `<li>${link(x)} (${C.look(x)[1]})</li>`).join('')}</ul>` : `No ${s.includes('red') ? 'red' : 'open'} risks or issues.`; }
    if (/milestone|next|go-live|slip/.test(s)) { const nx = C.mss().filter(mm => !mm.achievedOn).sort((a, b) => (a.forecast || a.agreed).localeCompare(b.forecast || b.agreed)); if (!nx.length) return 'Every milestone is achieved.'; const n = nx[0];
      const sl = nx.filter(mm => D.slip(mm) > 0); return `The next milestone is <a class="link" data-ms="${n.id}">${esc(n.name)}</a> on ${D.fd(n.forecast || n.agreed)} (${D.msState(n)}).${sl.length ? ` ${sl.length} ha${sl.length > 1 ? 've' : 's'} slipped: ${sl.map(mm => `<a class="link" data-ms="${mm.id}">${esc(mm.name)}</a> +${C.dy(D.slip(mm))}`).join(', ')}.` : ''}`; }
    if (/use case|uc\b/.test(s)) { const us = D.S.usecases.filter(u => u.code === p.code && !u.archived); return us.length ? `Use cases:<ul>${us.map(u => `<li><b>${esc(u.ref || u.id)}</b> ${esc(u.title.split('\n')[0])}: ${esc(u.status)}. ${esc(u.headline)}</li>`).join('')}</ul>` : 'This project has no use cases yet.'; }
    if (/summar|week|report|status/.test(s)) { const h = C.draftCurrent(p); return `A summary for this week:<div style="margin-top:6px">${h}</div><div class="acts"><button class="btn sm" data-do="summary" data-html="${encodeURIComponent(h)}">Use it as the Summary</button></div>`; }
    if (/who|most|owner|busiest/.test(s)) { const c = {}; open.filter(x => x.type === 'A').forEach(x => c[x.owner] = (c[x.owner] || 0) + 1); const top = Object.entries(c).sort((a, b) => b[1] - a[1]); return top.length ? `Open actions by owner:<ul>${top.map(([n, k]) => `<li>${esc(n)}: ${k}</li>`).join('')}</ul>` : 'There are no open actions.'; }
    const words = s.split(/\W+/).filter(w => w.length > 3), hits = its.filter(x => words.some(w => (x.title + ' ' + x.desc).toLowerCase().includes(w))).slice(0, 6);
    const fr = C.askRead(q, p), src = fr && (fr.passages.length || C.askFileNotes(fr).length) ? `<div style="margin-top:8px">${fileHtml(fr)}</div>` : '';
    return hits.length ? `These items match:<ul>${hits.map(x => `<li>${link(x)}</li>`).join('')}</ul>${src}` : `I can check the report, or answer about overdue actions, risks, milestones, use cases, owners and this week's summary.${src}`;
  }
  /* while it works, the pills go and the working line sits where they were (above the box), so the box never moves; the pills return with the answer */
  /* the ways a question can end without an answer (#284): Stop, a timeout and a sign-out each say their own thing, never one generic "failed" line. Stop works at once,
     including right after the question went (nothing is "not started yet" here). The Stop and sign-out lines are the product's (askWords.js); the timeout line has no
     approved wording yet, so this one is the prototype's own. The prototype's answers always come back within a few seconds, so a real timeout (a minute) is drawn, not met. */
  const ENDS = { stopped: 'Stopping. Your question and the earlier answers stay here.', timeout: 'The answer took too long, so clark stopped waiting. Your question and the earlier answers stay here. Ask again.',
    signedout: 'Claude is not signed in on this computer, so there is nothing to ask yet. Sign in to Claude on this computer, then open this panel again.' };
  const jobs = new Set();
  const working = on => { C.$('#askWork').hidden = !on; C.$('#askChips').hidden = on; };
  C.askEnd = kind => { if (!jobs.size) return false; jobs.forEach(j => { clearTimeout(j.answer); clearTimeout(j.limit); }); jobs.clear(); working(false); drawPrev();
    C.$('#askLog').insertAdjacentHTML('beforeend', `<div class="msg bot ask-end" role="status" data-end="${kind}">${esc(ENDS[kind])}</div>`); scroll(); return true; };
  C.askSignedOut = () => C.askEnd('signedout');
  function run(q) {
    if (!C.askOn()) { C.askOffDraw(true); return; }   /* Settings › Asking is off: nothing is sent */
    me(q); drawPrev();
    C.$('#askWork').innerHTML = `<span class="mdots"><i></i><i></i><i></i></span><span class="quip" aria-hidden="true">${C.quipNow()}</span><span class="sr">Working</span><button type="button" class="link ask-stop" id="askStop">Stop</button>`; working(true);
    C.$('#askStop').addEventListener('click', () => C.askEnd('stopped'));
    const job = {};
    job.limit = setTimeout(() => C.askEnd('timeout'), C.askTimeoutMs || 60000);
    job.answer = setTimeout(() => { if (!jobs.delete(job)) return; clearTimeout(job.limit); if (!jobs.size) working(false); bot(answer(q)); }, C.reduce ? 0 : 1100 + Math.random() * 1400);
    jobs.add(job);
  }
  document.addEventListener('DOMContentLoaded', () => {
    C.$('#askBtn').addEventListener('click', C.askToggle);
    C.$('#askClose').addEventListener('click', C.askClose);
    C.$('#askNew').addEventListener('click', () => { C.askReset(); greet(); C.$('#askIn').focus(); });
    C.$$('#askChips button').forEach(b => b.addEventListener('click', () => { run(b.textContent); C.$('#askIn').focus(); }));   // the pill is about to be hidden: keep the keyboard's place
    const i = C.$('#askIn');
    const send = () => { const v = i.value.trim(); if (!v) return; if (!C.askOn()) { run(v); return; } i.value = ''; i.style.height = ''; run(v); };
    C.$('#askSend').addEventListener('click', send);
    i.addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); C.askClose(); } });
    i.addEventListener('input', () => { i.style.height = 'auto'; i.style.height = Math.min(140, i.scrollHeight) + 'px'; });
  });
  C.askRun = run;
})();
