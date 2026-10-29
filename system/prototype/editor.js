/* clark prototype: one editor everywhere. Every text field is edited in place: click the text, it becomes
   creaite's pinned Tiptap editor (vendor/tiptap/) right there, with no toolbar and no Save button. Highlighting text shows the
   formatting bubble (creaite's editor bar, floating); "/" opens the command menu; ⌘↵ or a click elsewhere saves, Esc cancels.
   AI entries (rules standing in for AI in this prototype) appear where the field allows them. */
(function () {
  'use strict';
  const C = window.C, T = () => window.ClarkTiptap;
  let open = 0, slashEl = null;
  C.edIsOpen = () => open > 0;
  C.slashOpen = () => !!slashEl;
  C.toHtml = s => !s ? '' : /^\s*</.test(s) ? s : String(s).split(/\n{2,}|\n/).map(t => t.trim()).filter(Boolean).map(t => `<p>${C.esc(t)}</p>`).join('');
  C.plain = h => { if (!h) return ''; if (!/</.test(h)) return h; const d = document.createElement('div'); d.innerHTML = h.replace(/<\/(p|li|h\d)>/g, '$&\n'); return d.textContent.replace(/\n{2,}/g, '\n').trim(); };

  const SLASH = [
    { g: 'Text', k: 'p', ic: 'T', t: 'Text', d: 'Plain paragraph', run: c => c.setParagraph() },
    { g: 'Text', k: 'h1', ic: 'H1', t: 'Heading 1', d: 'Big section heading', run: c => c.setHeading({ level: 1 }) },
    { g: 'Text', k: 'h2', ic: 'H2', t: 'Heading 2', d: 'Medium section heading', run: c => c.setHeading({ level: 2 }) },
    { g: 'Text', k: 'h3', ic: 'H3', t: 'Heading 3', d: 'Small section heading', run: c => c.setHeading({ level: 3 }) },
    { g: 'Lists', k: 'ul', ic: '•', t: 'Bulleted list', d: 'A simple list', run: c => c.toggleBulletList() },
    { g: 'Lists', k: 'ol', ic: '1.', t: 'Numbered list', d: 'A list with numbers', run: c => c.toggleOrderedList() },
    { g: 'Lists', k: 'task', ic: '☐', t: 'Checklist', d: 'Tick items off', run: c => c.toggleTaskList() },
    { g: 'Blocks', k: 'quote', ic: '❝', t: 'Quote', d: 'Set a passage apart', run: c => c.toggleBlockquote() },
    { g: 'Blocks', k: 'hr', ic: '—', t: 'Divider', d: 'A line across', run: c => c.setHorizontalRule() },
    { g: 'AI', k: 'ai-draft', ic: '✦', t: 'Draft with AI', d: 'Write this from the project', ai: 'draft' },
    { g: 'AI', k: 'ai-rewrite', ic: '✦', t: 'Rewrite clearly', d: 'The same points, in plainer words', ai: 'rewrite' },
    { g: 'AI', k: 'ai-shorter', ic: '✦', t: 'Shorter', d: 'About half the length; the facts kept', ai: 'shorter' },
    { g: 'AI', k: 'ai-exec', ic: '✦', t: 'Make it executive', d: 'The position and what matters first', ai: 'executive' },
    { g: 'AI', k: 'ai-polish', ic: '✦', t: 'Polish', d: 'Spelling, grammar and a lighter touch', ai: 'polish' },
    { g: 'AI', k: 'ai-ask', ic: '✦', t: 'Ask AI…', d: 'Say what you want done to the text', ai: 'ask' },
  ];
  const PLAIN = [[/\butili[sz]e\b/gi, 'use'], [/\bin order to\b/gi, 'to'], [/\bprior to\b/gi, 'before'], [/\bcommence\b/gi, 'start'], [/\bfacilitate\b/gi, 'help'], [/\bleverage\b/gi, 'use'],
    [/\bgoing forward\b/gi, 'from now on'], [/\bcircle back\b/gi, 'come back'], [/\bsynergies\b/gi, 'shared gains'], [/\bat this point in time\b/gi, 'now'], [/\bcirca\b/gi, 'about']];
  const AI = {
    plain: t => PLAIN.reduce((s, [a, b]) => s.replace(a, b), t),
    shorten: t => (t.match(/[^.!?]+[.!?]/) || [t])[0].trim(),
    improve: t => { let s = t.replace(/\s+/g, ' ').trim(); if (!s) return s; s = s[0].toUpperCase() + s.slice(1); return /[.!?]$/.test(s) ? s : s + '.'; },
  };
  C.ai = AI;

  /* ── creaite's AI on selected text (its AiSelect, BL-301 D and #117: "the AI menu in creaite is much richer...
     include it in clark. Also, all editors should have the AI included"). The options, their places and their groups are creaite's
     (stores/aiEdit.js AI_OPTIONS, AI_PLACES, AI_GROUPS). Nothing changes until Accept: a suggestion card shows the new text (or, with
     Show changes, what goes and what comes, word by word) with Accept, Discard and Try again. In this prototype, rules stand in for
     Claude, so the wording is mechanical; the menus, the card and the steps are what clark builds. ── */
  const AI_OPTIONS = {
    rewrite: ['Rewrite clearly', 'The same points, in plainer words'], shorter: ['Shorter', 'About half the length; the facts kept'],
    longer: ['Longer', 'Fuller sentences; adds no facts'], executive: ['Make it executive', 'The executive voice: the position and what matters first'],
    format: ['Add headings and bold', 'Sub-headings, lists and bold where they help'], checklist: ['Pull out the tasks', 'Finds the tasks and writes one a line to tick off'],
    summary: ['Summarise at the top', 'A short summary first; the text kept below it'], polish: ['Polish', 'Spelling, grammar and a lighter touch on the wording; the facts and length kept'],
    notes: ['Format notes', 'Rough notes sorted under headings, with bullets; every point kept'], formal: ['More formal', 'A more formal tone for the email'],
    warmer: ['Warmer', 'A warmer, friendlier tone for the email'], custom: ['Or say what you want…', 'Your own instruction'],
  };
  const AI_GROUPS = {
    notes: [['Improve', ['rewrite', 'shorter', 'longer', 'executive']], ['Structure', ['format', 'checklist', 'summary']]],
    current: [['Improve', ['rewrite', 'shorter', 'longer', 'executive', 'polish']], ['Structure', ['format', 'checklist', 'summary']]],
    plain: [['Improve', ['rewrite', 'shorter', 'executive', 'polish']]],
    email: [['Improve', ['rewrite', 'shorter', 'longer']], ['Tone', ['formal', 'warmer']]],
    client_message: [['Improve', ['rewrite', 'shorter', 'executive', 'polish']]],
  };
  const NOTES_PLACES = ['notes', 'current'];
  const sentences = t => (String(t).replace(/\s+/g, ' ').trim().match(/[^.!?]+[.!?]*/g) || []).map(x => x.trim()).filter(Boolean);
  const UK = [[/\borganiz/gi, 'organis'], [/\bprioritiz/gi, 'prioritis'], [/\banalyz/gi, 'analys'], [/\bcolor\b/gi, 'colour'], [/\bbehavior\b/gi, 'behaviour'], [/\bcenter\b/gi, 'centre'], [/\bprogram\b/gi, 'programme']];
  const EXPAND = [[/\bdon't\b/gi, 'do not'], [/\bcan't\b/gi, 'cannot'], [/\bwon't\b/gi, 'will not'], [/\bisn't\b/gi, 'is not'], [/\bit's\b/gi, 'it is'], [/ & /g, ' and '], [/\be\.g\./gi, 'for example'], [/\bi\.e\./gi, 'that is'], [/\betc\.?/gi, 'and so on']];
  const tidy = t => sentences(AI.plain(t)).map(AI.improve).join(' ');
  const P = t => `<p>${C.esc(t)}</p>`;
  const HOT = /\b(risk|late|delay|slip|overdue|block|decision|need|cannot|won't|issue)/i, TASK = /\b(need|needs|will|must|to do|should|chase|confirm|agree|send|book|draft|review|share|set up|follow up)\b/i;
  const AI_RUN = {
    rewrite: t => P(tidy(t)),
    shorter: t => { const s = sentences(t); return P(s.slice(0, Math.max(1, Math.ceil(s.length / 2))).join(' ')); },
    longer: t => P(EXPAND.reduce((x, [a, b]) => x.replace(a, b), tidy(t))),
    executive: t => { const s = sentences(tidy(t)), hot = s.filter(x => HOT.test(x)), rest = s.filter(x => !HOT.test(x)), first = hot[0] || s[0] || '';
      return `<p><b>Where it stands:</b> ${C.esc(first)}</p>${[...hot.slice(1), ...rest.filter(x => x !== first)].length ? `<ul>${[...hot.slice(1), ...rest.filter(x => x !== first)].map(x => `<li><p>${C.esc(x)}</p></li>`).join('')}</ul>` : ''}`; },
    format: t => { const s = sentences(tidy(t)); return `<h3>Summary</h3>${P(s[0] || '')}${s.length > 1 ? `<h3>Details</h3><ul>${s.slice(1).map(x => `<li><p>${C.esc(x)}</p></li>`).join('')}</ul>` : ''}`; },
    checklist: t => { const s = sentences(t).filter(x => TASK.test(x)); return s.length ? `<ul data-type="taskList">${s.map(x => `<li data-type="taskItem" data-checked="false"><p>${C.esc(AI.improve(x))}</p></li>`).join('')}</ul>` : ''; },
    summary: (t, html) => `<p><b>In short:</b> ${C.esc(sentences(tidy(t))[0] || '')}</p>${html}`,
    polish: t => P(UK.reduce((x, [a, b]) => x.replace(a, b), tidy(t)).replace(/ {2,}/g, ' ')),
    notes: t => { const ls = String(t).split(/\n+/).map(x => x.trim().replace(/^[-*•]\s*/, '')).filter(Boolean); let h = '', list = [];
      const flush = () => { if (list.length) h += `<ul>${list.map(x => `<li><p>${C.esc(AI.improve(x))}</p></li>`).join('')}</ul>`; list = []; };
      ls.forEach(l => { if (/:$/.test(l) || (l.length < 40 && !/[.!?]$/.test(l) && /^[A-Z]/.test(l) && ls.length > 2)) { flush(); h += `<h3>${C.esc(l.replace(/:$/, ''))}</h3>`; } else list.push(l); });
      flush(); return h.startsWith('<h3>') ? h : `<h3>Notes</h3>${h}`; },
    formal: t => P(EXPAND.reduce((x, [a, b]) => x.replace(a, b), tidy(t)).replace(/\b(hi|hey)\b/gi, 'Dear')),
    warmer: t => P(`Thanks so much. ${tidy(t)} Do let me know if I can help.`),
  };
  /* "Or say what you want…": in the prototype the instruction is matched to an option (Claude follows it in clark) */
  const askKind = q => { q = q.toLowerCase(); return /short|cut|brief|trim/.test(q) ? 'shorter' : /long|expand|more detail/.test(q) ? 'longer' : /task|to-?do|action/.test(q) ? 'checklist' : /head|bullet|list|struct/.test(q) ? 'format'
    : /summ/.test(q) ? 'summary' : /exec|boss|steer|sponsor/.test(q) ? 'executive' : /formal/.test(q) ? 'formal' : /warm|friend/.test(q) ? 'warmer' : /spell|grammar|polish|typo/.test(q) ? 'polish' : 'rewrite'; };
  /* what goes and what comes, word by word (the card's Show changes) */
  const wdiff = (a, b) => { const A = a.split(/\s+/).filter(Boolean), B = b.split(/\s+/).filter(Boolean), n = A.length, m = B.length, L = Array.from({ length: n + 1 }, () => new Array(m + 1).fill(0));
    for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) L[i][j] = A[i] === B[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
    let i = 0, j = 0, out = []; while (i < n && j < m) { if (A[i] === B[j]) { out.push(C.esc(A[i])); i++; j++; } else if (L[i + 1][j] >= L[i][j + 1]) out.push(`<del>${C.esc(A[i++])}</del>`); else out.push(`<ins>${C.esc(B[j++])}</ins>`); }
    while (i < n) out.push(`<del>${C.esc(A[i++])}</del>`); while (j < m) out.push(`<ins>${C.esc(B[j++])}</ins>`); return out.join(' '); };
  C.wdiff = wdiff;   /* the peek's Activity tab reuses it for the compact diff of a latest update or note */
  /* "Make into": creaite's registered actions (its NotesPage "Make this an action, a risk, a decision"); the selection becomes a new work item */
  const MAKE = [['A', 'Make this an action'], ['R', 'Make this a risk'], ['D', 'Make this a decision']];
  const makeItem = (type, text) => { const p = C.P(); if (!p) return; const D = C.D, title = sentences(text)[0] || String(text).trim();
    const x = { id: C.nextId(type), code: p.code, type, ws: p.ws[0], title: title.replace(/[.]$/, '').slice(0, 140), owner: '', due: type === 'D' ? D.TODAY : D.addDays(D.TODAY, 7), status: D.STATUSES[type][0], priority: 'Medium', desc: C.toHtml(text), update: '', updatedAt: D.stamp(), client: true, clientText: '', ms: '', uc: '', source: 'From selected text' };
    const u = D.create('item', x, D.who('from selected text')); C.toast(`${x.id} added: ${x.title}`, () => { u && u(); if (!C.edIsOpen()) C.refresh(); }); };   // the page catches up when the editor closes
  C.AI_OPTIONS = AI_OPTIONS;

  /* richEditor(host, {html, placeholder, label, ai, place, draft, onSave(html), onCancel()}): the editor, in place, inside host. place picks
     the AI options, as creaite's places: current, notes, plain (the default), email, client_message */
  C.richEditor = (host, o) => {
    open++;
    host.classList.add('editing-now');
    /* the full editor, the same in every field: creaite's toolbar on top, the text, then the keys */
    host.innerHTML = `<div class="ed-bar" role="toolbar" aria-label="Formatting">
        <button data-c="h1" title="Heading 1">H1</button><button data-c="h2" title="Heading 2">H2</button><button data-c="h3" title="Heading 3">H3</button><span class="vs"></span>
        <button data-c="bold" title="Bold"><b>B</b></button><button data-c="italic" title="Italic"><i>I</i></button><button data-c="strike" title="Strikethrough"><s>S</s></button><span class="vs"></span>
        <button data-c="ul" title="Bulleted list">•</button><button data-c="ol" title="Numbered list">1.</button><button data-c="task" title="Checklist">☐</button><button data-c="out" title="Outdent">⇤</button><button data-c="in" title="Indent">⇥</button><button data-c="quote" title="Quote">❝</button><button data-c="hr" title="Divider">—</button><span class="vs"></span>
        <button data-c="link">Link</button><button data-c="unlink">Unlink</button><button data-c="clear">Clear</button><span class="vs"></span>
        <button data-c="undo" title="Undo">${C.icon('undo', 's')}</button><button data-c="redo" title="Redo">${C.icon('redo', 's')}</button>${o.ai === false ? '' : '<span class="vs"></span><button data-c="ai" title="AI">✦ AI</button>'}
      </div><div class="ed-inline prose"></div><div class="ed-hint">⌘↵ or click away saves · Esc cancels · / for commands${o.ai === false ? '' : ' and AI'} · highlight text to format it${o.ai === false ? '' : ', Alt+/ for AI on it'}</div>`;
    const area = C.$('.ed-inline', host), start = o.html || '';
    let ed = null, plainBox = null;
    if (T()) { try { ed = T().createEditor(area, { html: start, features: 'current' }); } catch (e) { ed = null; } }
    if (!ed) { area.innerHTML = `<div contenteditable="true" role="textbox" aria-multiline="true">${start}</div>`; plainBox = area.firstElementChild; }
    const pm = () => ed ? C.$('.ProseMirror', area) : plainBox;
    const getHTML = () => ed ? (ed.isEmpty ? '' : ed.getHTML()) : plainBox.innerHTML.trim();
    const setHTML = h => ed ? ed.commands.setContent(h) : (plainBox.innerHTML = h);
    const getText = () => ed ? ed.getText() : plainBox.innerText;
    const chain = () => ed.chain().focus();
    const dirty = () => getHTML() !== start;
    if (pm()) { pm().setAttribute('aria-label', o.label || 'Text'); if (o.placeholder) pm().dataset.placeholder = o.placeholder; }
    const phCheck = () => { const p = pm(); if (!p) return; p.classList.toggle('ph', ed ? ed.isEmpty : !plainBox.textContent.trim()); };

    const CMDS = {
      h1: c => c.toggleHeading({ level: 1 }), h2: c => c.toggleHeading({ level: 2 }), h3: c => c.toggleHeading({ level: 3 }), bold: c => c.toggleBold(), italic: c => c.toggleItalic(), strike: c => c.toggleStrike(),
      ul: c => c.toggleBulletList(), ol: c => c.toggleOrderedList(), task: c => c.toggleTaskList(), in: c => c.sinkListItem('listItem'), out: c => c.liftListItem('listItem'), quote: c => c.toggleBlockquote(), hr: c => c.setHorizontalRule(),
      unlink: c => c.unsetLink(), clear: c => c.unsetAllMarks().clearNodes(), undo: c => c.undo(), redo: c => c.redo() };
    const FALLBACK = { h1: ['formatBlock', 'h1'], h2: ['formatBlock', 'h2'], h3: ['formatBlock', 'h3'], bold: ['bold'], italic: ['italic'], strike: ['strikeThrough'], ul: ['insertUnorderedList'], ol: ['insertOrderedList'], in: ['indent'], out: ['outdent'], quote: ['formatBlock', 'blockquote'], hr: ['insertHorizontalRule'], unlink: ['unlink'], clear: ['removeFormat'], undo: ['undo'], redo: ['redo'] };
    const ACTIVE = { h1: ['heading', { level: 1 }], h2: ['heading', { level: 2 }], h3: ['heading', { level: 3 }], bold: ['bold'], italic: ['italic'], strike: ['strike'], ul: ['bulletList'], ol: ['orderedList'], task: ['taskList'], quote: ['blockquote'], link: ['link'] };
    const syncBar = () => { if (!ed || ed.isDestroyed) return; C.$$('.ed-bar [data-c]', host).forEach(b => { const a = ACTIVE[b.dataset.c]; b.classList.toggle('on', !!a && ed.isActive(...a)); });
      C.$('[data-c=undo]', host).disabled = !ed.can().undo(); C.$('[data-c=redo]', host).disabled = !ed.can().redo(); C.$('[data-c=unlink]', host).disabled = !ed.isActive('link'); };
    C.$$('.ed-bar [data-c]', host).forEach(b => b.addEventListener('mousedown', e => {
      e.preventDefault(); const k = b.dataset.c;
      if (k === 'ai') return aiMenuAll(b);
      if (k === 'link') { const u = prompt('Link address'); if (u) ed ? chain().extendMarkRange('link').setLink({ href: u }).run() : document.execCommand('createLink', false, u); return syncBar(); }
      if (ed) CMDS[k](chain()).run(); else if (FALLBACK[k]) document.execCommand(...FALLBACK[k].length > 1 ? [FALLBACK[k][0], false, FALLBACK[k][1]] : [FALLBACK[k][0]]);
      syncBar();
    }));
    const place = o.place || 'plain', groups = AI_GROUPS[place] || AI_GROUPS.plain;
    /* the text an option works on: the selection, or the whole field when nothing is selected */
    const target = () => { const sel = ed && ed.state.selection; if (ed && sel && !sel.empty) { const sl2 = ed.state.doc.cut(sel.from, sel.to), d = document.createElement('div');
        d.appendChild(window.ClarkTiptap && ed.view.serializeForClipboard ? ed.view.serializeForClipboard(sl2).dom : document.createTextNode(ed.state.doc.textBetween(sel.from, sel.to, '\n')));
        return { from: sel.from, to: sel.to, text: ed.state.doc.textBetween(sel.from, sel.to, '\n'), html: d.innerHTML }; }
      return { all: true, text: getText(), html: getHTML() }; };
    let card = null;
    const closeCard = () => { card?.remove(); card = null; };
    const suggest = (kind, q) => {
      hideBubble(); closeCard(); const t = target(); if (!t.text.trim()) return C.toast('Write or select some text first');
      const k = kind === 'custom' ? askKind(q || '') : kind, out = AI_RUN[k](t.text, t.html);
      if (!out) return C.toast(kind === 'checklist' ? 'No tasks found in the text' : 'Nothing to change');
      const name = kind === 'custom' ? `Ask: “${q}”` : AI_OPTIONS[kind][0];
      card = document.createElement('div'); card.className = 'ai-sug'; card.setAttribute('role', 'dialog'); card.setAttribute('aria-label', 'AI suggestion: ' + name);
      const draw = diff => { card.innerHTML = `<div class="ai-sug-h">✦ <b>${C.esc(name)}</b><span class="sp"></span><label><input type="checkbox" data-diff ${diff ? 'checked' : ''}> Show changes</label></div>
        <div class="ai-sug-b prose">${diff ? `<p>${wdiff(t.text, C.plain(out))}</p>` : out}</div>
        <div class="ai-sug-n">Prototype: rules stand in for Claude${kind === 'custom' ? ` (read as “${C.esc(AI_OPTIONS[k][0])}”)` : ''}. Nothing changes until you accept.</div>
        <div class="ai-sug-a"><button class="btn sm" data-a="again">Try again</button><span class="sp"></span><button class="btn sm" data-a="discard">Discard</button><button class="btn pri sm" data-a="accept">Accept</button></div>`;
        C.$('[data-diff]', card).addEventListener('change', e => draw(e.target.checked));
        C.$('[data-a=accept]', card).addEventListener('mousedown', e => { e.preventDefault(); accept(); });
        C.$('[data-a=discard]', card).addEventListener('mousedown', e => { e.preventDefault(); closeCard(); ed && ed.commands.focus(); });
        C.$('[data-a=again]', card).addEventListener('mousedown', e => { e.preventDefault(); suggest(kind, q); }); };
      const accept = () => { if (ed) { if (t.all) chain().setContent(out).run(); else chain().insertContentAt({ from: t.from, to: t.to }, out).run(); } else setHTML(out); closeCard(); phCheck(); C.toast(name + ' applied. Undo with ⌘Z'); };
      card._accept = accept; draw(false); document.body.appendChild(card);
      const r = ed && !t.all ? ed.view.coordsAtPos(t.to) : host.getBoundingClientRect();
      card.style.left = Math.max(8, Math.min((ed && !t.all ? r.left - 160 : r.left), innerWidth - card.offsetWidth - 8)) + 'px';
      card.style.top = Math.min(innerHeight - card.offsetHeight - 8, (ed && !t.all ? r.bottom : r.top + 40) + 10) + 'px';
      C.$('[data-a=accept]', card).focus({ preventScroll: true });
    };
    const optItems = keys => keys.map(k2 => ({ html: `<span><b>${AI_OPTIONS[k2][0]}</b><small>${AI_OPTIONS[k2][1]}</small></span>`, onPick: () => suggest(k2) }));
    const makeItems = () => C.P() ? MAKE.map(([ty, t]) => ({ html: `<span><b>${t}</b><small>A new ${C.D.TYPES[ty].toLowerCase()} from the text, with Undo</small></span>`, onPick: () => { const tx = target().text; if (tx.trim()) makeItem(ty, tx); } })) : [];
    const ask = anchor => C.popover(anchor, `<form class="ai-ask"><input class="field" placeholder="Say what you want, e.g. make it shorter for the sponsor" aria-label="Ask AI"><button class="btn pri sm">Ask</button></form>`,
      { wire: el => { const i = C.$('input', el); i.focus(); C.$('form', el).addEventListener('submit', e => { e.preventDefault(); const q = i.value.trim(); if (!q) return; C.closePop(); suggest('custom', q); }); } });
    /* the toolbar's ✦ AI: every option of this place, on the selection or the whole text */
    const aiMenuAll = b => C.menu(b, [...(o.draft ? [{ html: '<span><b>Draft from the project</b><small>Write this from the project’s data</small></span>', onPick: () => runAI('draft') }, { sep: true }] : []),
      ...(NOTES_PLACES.includes(place) ? [...optItems(['notes']), { sep: true }] : []),
      ...groups.flatMap(([g, ks], gi) => [...(gi ? [{ sep: true }] : []), { lab: g }, ...optItems(ks)]),
      ...(makeItems().length ? [{ sep: true }, { lab: 'Make into' }, ...makeItems()] : []), { sep: true }, { html: `<span><b>${AI_OPTIONS.custom[0]}</b><small>${AI_OPTIONS.custom[1]}</small></span>`, onPick: () => setTimeout(() => ask(b), 0) }]);
    const runAI = kind => {
      if (kind === 'draft') { const h = o.draft ? o.draft() : ''; if (h) { setHTML(h); C.toast('Drafted from the project (prototype: written by rules, not AI)'); } return; }
      if (kind === 'ask') return ask(C.$('[data-c=ai]', host) || host);
      return suggest(kind);
    };

    /* the formatting bubble: creaite's editor bar, floating over the highlighted text */
    let bubble = null;
    const hideBubble = () => { bubble?.remove(); bubble = null; };
    const BTN = [['bold', '<b>B</b>', 'Bold', c => c.toggleBold(), ['bold']], ['italic', '<i>I</i>', 'Italic', c => c.toggleItalic(), ['italic']], ['strike', '<s>S</s>', 'Strikethrough', c => c.toggleStrike(), ['strike']], null,
      ['h2', 'H2', 'Heading', c => c.toggleHeading({ level: 2 }), ['heading', { level: 2 }]], ['h3', 'H3', 'Small heading', c => c.toggleHeading({ level: 3 }), ['heading', { level: 3 }]], null,
      ['ul', '•', 'Bulleted list', c => c.toggleBulletList(), ['bulletList']], ['ol', '1.', 'Numbered list', c => c.toggleOrderedList(), ['orderedList']], ['quote', '❝', 'Quote', c => c.toggleBlockquote(), ['blockquote']], null,
      ['link', 'Link', 'Link', null, ['link']], ['clear', 'Clear', 'Clear formatting', c => c.unsetAllMarks().clearNodes(), null]];
    const showBubble = () => {
      hideBubble(); if (!ed) return; const s = ed.state.selection; if (s.empty) return;
      const a = ed.view.coordsAtPos(s.from), b = ed.view.coordsAtPos(s.to);
      bubble = document.createElement('div'); bubble.className = 'fmt-bubble'; bubble.setAttribute('role', 'toolbar'); bubble.setAttribute('aria-label', 'Format');
      const sel = ed.state.selection, many = ed.state.doc.textBetween(sel.from, sel.to, '\n').split('\n').filter(x => x.trim()).length > 1;
      bubble.innerHTML = BTN.map(x => x ? `<button data-b="${x[0]}" title="${x[2]}" class="${x[4] && ed.isActive(...x[4]) ? 'on' : ''}">${x[1]}</button>` : '<span class="vs"></span>').join('')
        + (o.ai === false ? '' : `<span class="ai-zone" role="group" aria-label="AI"><span class="ai-mark" aria-hidden="true">✦</span>${many && NOTES_PLACES.includes(place) ? '<button data-b="ai-notes">Format notes</button>' : ''}${groups.map(([g]) => `<button data-b="ai-g" data-g="${g}">${g} ▾</button>`).join('')}${C.P() ? '<button data-b="ai-make">Make into ▾</button>' : ''}<button data-b="ai-ask">Ask…</button></span>`);
      document.body.appendChild(bubble);
      bubble.style.left = Math.max(8, Math.min((a.left + b.right) / 2 - bubble.offsetWidth / 2, innerWidth - bubble.offsetWidth - 8)) + 'px';
      bubble.style.top = Math.max(8, a.top - bubble.offsetHeight - 8) + 'px';
      C.$$('button', bubble).forEach(x => x.addEventListener('mousedown', e => {
        e.preventDefault(); const k = x.dataset.b;
        if (k === 'ai-g') return C.menu(x, optItems(groups.find(g => g[0] === x.dataset.g)[1]));
        if (k === 'ai-make') return C.menu(x, makeItems());
        if (k === 'ai-notes') return suggest('notes');
        if (k === 'ai-ask') return ask(x);
        if (k === 'link') { const u = prompt('Link address'); if (u) chain().extendMarkRange('link').setLink({ href: u }).run(); }
        else BTN.find(z => z && z[0] === k)[3](chain()).run();
        showBubble();
      }));
    };

    /* "/" command menu */
    let sl = null;
    const items = () => SLASH.filter(s => o.ai !== false || !s.ai).filter(s => !s.ai || s.ai !== 'draft' || o.draft);
    const closeSlash = () => { slashEl?.remove(); slashEl = null; sl = null; };
    const drawSlash = () => {
      const list = items().filter(s => !sl.q || (s.t + ' ' + s.d + ' ' + s.k).toLowerCase().includes(sl.q.toLowerCase()));
      sl.list = list; sl.at = Math.min(sl.at, Math.max(0, list.length - 1));
      if (!slashEl) { slashEl = document.createElement('div'); slashEl.className = 'slash'; slashEl.setAttribute('role', 'listbox'); document.body.appendChild(slashEl); }
      let g = '', h = '';
      list.forEach((s, i) => { if (s.g !== g) { g = s.g; h += `<div class="lab">${g}</div>`; } h += `<div class="opt${i === sl.at ? ' active' : ''}" role="option" data-i="${i}"><span class="ic">${s.ic}</span><span><b>${s.t}</b><small>${s.d}</small></span></div>`; });
      slashEl.innerHTML = `<div class="list">${h || '<div class="lab">No match</div>'}</div><div class="ft">↑↓ to move · Enter to insert · Esc to close</div>`;
      const c = ed.view.coordsAtPos(sl.from); slashEl.style.left = Math.min(c.left, innerWidth - 330) + 'px';
      slashEl.style.top = (c.bottom + 346 > innerHeight ? Math.max(8, c.top - 346) : c.bottom + 6) + 'px';
      C.$('.opt.active', slashEl)?.scrollIntoView({ block: 'nearest' });
      C.$$('.opt', slashEl).forEach(o2 => o2.addEventListener('mousedown', e => { e.preventDefault(); sl.at = +o2.dataset.i; pickSlash(); }));
    };
    const pickSlash = () => {
      const s = sl.list[sl.at]; if (!s) return closeSlash();
      ed.chain().focus().deleteRange({ from: sl.from, to: ed.state.selection.from }).run(); closeSlash();
      if (s.ai) runAI(s.ai); else s.run(ed.chain().focus()).run();
    };
    const slashCheck = () => {
      if (!ed) return; const { from, empty } = ed.state.selection; if (!empty) return closeSlash();
      const $f = ed.state.selection.$from, before = $f.parent.textBetween(0, $f.parentOffset, '\n', ' ');
      const m = /(?:^|\s)\/([\w-]*)$/.exec(before); if (!m) return closeSlash();
      const st = from - m[1].length - 1; if (!sl || sl.from !== st) sl = { from: st, q: m[1], at: 0, list: [] }; else sl.q = m[1]; drawSlash();
    };

    /* finish: a click elsewhere or ⌘↵ saves; Esc cancels */
    let done = false;
    const finish = () => { if (done) return false; done = true; open = Math.max(0, open - 1); closeSlash(); hideBubble(); closeCard(); host.classList.remove('editing-now'); try { ed && ed.destroy(); } catch (e) { /* gone */ } return true; };
    const save = () => { const h = getHTML(), changed = h !== start; if (finish()) o.onSave(h, changed); };
    const cancel = () => { if (finish()) o.onCancel && o.onCancel(); };
    host.addEventListener('keydown', e => {
      if (sl && slashEl) {
        if (e.key === 'ArrowDown' || e.key === 'ArrowUp') { e.preventDefault(); sl.at = (sl.at + (e.key === 'ArrowDown' ? 1 : sl.list.length - 1)) % Math.max(1, sl.list.length); drawSlash(); return; }
        if (e.key === 'Enter') { e.preventDefault(); pickSlash(); return; }
        if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeSlash(); return; }
      }
      if (card && (e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); card._accept(); return; }
      if (card && e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); closeCard(); return; }
      if (e.altKey && (e.key === '/' || e.code === 'Slash') && o.ai !== false) { e.preventDefault(); if (ed && !ed.state.selection.empty) { showBubble(); const g = bubble && C.$('[data-b=ai-g]', bubble); g && g.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); } else aiMenuAll(C.$('[data-c=ai]', host)); return; }
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') { e.preventDefault(); save(); return; }
      if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); cancel(); }
    }, true);
    const outside = e => { if (done) return document.removeEventListener('mousedown', outside, true); const t = e.target; if (host.contains(t) || t.closest('.slash,.fmt-bubble,.menu,dialog,.ai-sug,.toast')) return; document.removeEventListener('mousedown', outside, true); save(); };
    setTimeout(() => document.addEventListener('mousedown', outside, true), 0);
    if (ed) {
      ed.on('update', () => { slashCheck(); phCheck(); syncBar(); });
      ed.on('transaction', () => { if (ed.state.selection.empty) slashCheck(); });
      ed.on('selectionUpdate', () => { syncBar(); if (sl) return; const s = ed.state.selection; s.empty ? hideBubble() : setTimeout(() => { if (!ed.isDestroyed && !ed.state.selection.empty) showBubble(); }, 200); });
      setTimeout(() => ed.commands.focus('end'), 20);
    } else { plainBox.addEventListener('input', phCheck); setTimeout(() => plainBox.focus(), 20); }
    phCheck();
    return { getHTML, setHTML, save, cancel, editor: ed, dirty };
  };

  /* inline(el, {html, label, placeholder, ai, draft, onSave(html)}): shows the text; a click (or Enter on it) edits it in place */
  C.inline = (el, o) => {
    const show = () => { el.innerHTML = o.html ? `<div class="prose">${o.html}</div>` : `<div class="prose empty-text"><p>${C.esc(o.placeholder || 'Write here…')}</p></div>`; };
    show();
    el.classList.add('inl'); el.tabIndex = 0; el.setAttribute('role', 'button'); el.setAttribute('aria-label', 'Edit ' + (o.label || 'text').toLowerCase());
    const go = e => {
      if (el.classList.contains('editing-now')) return;
      if (e && e.target.closest('a[href]')) return;
      el.removeAttribute('role'); el.tabIndex = -1;
      C.richEditor(el, { ...o, onSave: (h, changed) => { el.tabIndex = 0; el.setAttribute('role', 'button'); if (changed) o.onSave(h); else show(); }, onCancel: () => { el.tabIndex = 0; el.setAttribute('role', 'button'); show(); } });
    };
    el.addEventListener('click', go);
    el.addEventListener('keydown', e => { if (e.key === 'Enter' && !el.classList.contains('editing-now')) { e.preventDefault(); go(); } });
    return { open: go };
  };
})();
