/* Click-through test for the clark prototype: every moving part, driven through the page as a person would.
   Run: python3 run_selftest.py (in this folder) — it loads index.html with this file in headless Chrome and prints the result. */
(async () => {
  const out = [], $ = s => document.querySelector(s), $$ = s => [...document.querySelectorAll(s)];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const S = () => window.ClarkDB.S, P = () => S().projects.find(p => p.code === C.UI.code), item = id => S().items.find(x => x.id === id);
  let pass = 0, fail = 0;
  const live = document.createElement('pre'); live.id = 'selftest-live'; live.hidden = true; document.body.appendChild(live);
  const ok = (n, c, x = '') => { c ? pass++ : fail++; out.push(`${c ? 'PASS' : 'FAIL'} ${n}${x !== '' ? ' — ' + x : ''}`); live.textContent = out.slice(-3).join('\n'); };
  const click = el => { if (!el) throw new Error('missing element'); el.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true })); };
  const key = (el, k, o = {}) => el.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...o }));
  const menuPick = async text => { const o = $$('.menu [data-i]').find(e => e.textContent.trim().startsWith(text)); if (!o) throw new Error('no menu item ' + text + ' in [' + $$('.menu').map(m => m.textContent.slice(0, 80)).join(' | ') + '], last closed by ' + lastClose); click(o); await sleep(60); };
  const undo = async () => { click($('#toastUndo')); await sleep(80); };
  let gone = false;
  const step = async (n, f) => { live.dataset.step = n; try { await f(); } catch (e) { fail++; out.push(`FAIL ${n} — threw ${e.message}`); live.textContent = out.slice(-3).join('\n'); }
    ckGone(); if (!gone && !S().projects.length) { gone = true; fail++; out.push(`FAIL the data vanished during the step '${n}'`); live.textContent = out.slice(-3).join('\n'); } };
  const typeIn = async (el, text) => { el.focus(); document.execCommand('insertText', false, text); await sleep(80); };
  let blobs = 0; const cou = URL.createObjectURL; URL.createObjectURL = b => { blobs++; return cou(b); };
  let writes = []; const spyX = () => { const wf = XLSX.writeFile; XLSX.writeFile = (wb, name) => { writes.push({ name, sheets: wb.SheetNames, wb }); }; return () => { XLSX.writeFile = wf; }; };
  if (document.readyState === 'loading') await new Promise(r => document.addEventListener('DOMContentLoaded', r, { once: true }));
  await C.started;
  const ckGone = () => { if (!S().projects.length && !live.dataset.gone) live.dataset.gone = live.dataset.step; };
  let lastClose = ''; const cp0 = C.closePop; C.closePop = () => { if (C.popOpen()) lastClose = new Error().stack.split('\n').slice(2, 4).map(x => x.trim().replace(/file:.*\//, '')).join(' < '); cp0(); };

  await step('shell', async () => {
    ok('starts on the dashboard', C.UI.view === 'dashboard' && !!$('.sheet'));
    click($('.tab[data-view=work]')); await sleep(60); ok('tab: work items', C.UI.view === 'work' && !!$('table.items'));
    ok('a new view fades in', $('#main .view').classList.contains('enter')); C.refresh(); ok('a redraw in place does not (no bounce)', !$('#main .view').classList.contains('enter') && !$('#main .view').getAnimations().length);
    click($('#logoBtn')); await sleep(60); ok('logo goes home', C.UI.view === 'dashboard');
    click($('#meBtn')); await sleep(60); ok('the profile circle opens a menu with Settings and Dark mode', /Settings/.test($('.menu').textContent) && /Dark mode/.test($('.menu').textContent));
    await menuPick('Settings'); await sleep(60); ok('settings page', C.UI.view === 'settings' && !!$('table.set'));
    ok('dashboard sections: slim gaps by default, each section its own card', document.documentElement.dataset.dash === 'slim');
    click($('[data-secs=roomy]')); await sleep(40); ok('Settings › Personal: roomy gaps chosen and kept', document.documentElement.dataset.dash === 'roomy' && C.store.get('secs') === 'roomy');
    click($('[data-secs=slim]')); await sleep(40);
    click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60);
    ok('dark mode on: the page and cards turn dark', document.documentElement.dataset.theme === 'dark' && getComputedStyle(document.body).backgroundColor !== 'rgb(243, 245, 248)' && getComputedStyle($('.card')).backgroundColor === 'rgb(23, 33, 44)');
    click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60); ok('dark mode off again', document.documentElement.dataset.theme === 'light' && getComputedStyle($('.card')).backgroundColor === 'rgb(255, 255, 255)');
    click($('#logoBtn')); await sleep(60);
    click($('#projBtn')); await sleep(40); await menuPick('Customer Portal Refresh'); ok('switch project', C.UI.code === 'CPR' && $('.cover h1').textContent === 'Customer Portal Refresh');
    click($('#projBtn')); await sleep(40); await menuPick('Data Platform Pilot'); ok('switch back', C.UI.code === 'PDF');
    key(document.body, '/'); await sleep(80); ok('"/" opens ask clark', $('#ask').classList.contains('on') && document.activeElement.id === 'askIn');
    key(document.body, 'Escape'); await sleep(40); ok('Esc closes ask clark', !$('#ask').classList.contains('on'));
    key(document.body, 'j', { metaKey: true }); await sleep(40); ok('Cmd+J opens ask clark', $('#ask').classList.contains('on'));
    $('.sheet').dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(40); ok('a click outside closes ask clark', !$('#ask').classList.contains('on'));
  });

  await step('dashboard: View is read-only, like the client sees it', async () => {
    C.noNativeSave = true;   // the test can't answer the browser's save window
    const secs = $$('.sec').length; ok('report sections drawn', secs >= 10, secs);
    ok('no editing in View: no fields, no sparkle or pencil', !$('.sheet [contenteditable]') && !$('.sheet textarea') && !$('[data-cs]') && !$('.sheet .add-in') && !$('[data-cs-edit],[data-cs-draft]'));
    ok('health tile shows the pill and the reason, not in the header', !!$('[data-fig=health] .hpill') && !$('.cover .hpill') && $('[data-fig=health] .hreason').textContent.length > 10);
    ok('the dashboard\'s Excel export is in the profile menu, not on the page', !$('#exBtn') && $('[data-uc-export]').classList.contains('ib')); click($('#meBtn')); await sleep(40); ok('profile menu: Publish, Preview, Export to Excel', ['Publish', 'Preview the page in a new tab', 'Export to Excel'].every(t => $('.menu').textContent.includes(t))); click($('#meBtn')); await sleep(30);
    ok('contents: a discreet line per section, list on hover', $$('.toc .toc-lines i').length >= 10 && $$('.toc [data-toc]').length >= 10 && getComputedStyle($('.toc-card')).visibility === 'hidden');
    const siv = Element.prototype.scrollIntoView; let jumped = null; Element.prototype.scrollIntoView = function () { jumped = this.id; }; click($('.toc [data-toc=docs]')); await sleep(40); Element.prototype.scrollIntoView = siv; ok('contents rail jumps to a section', jumped === 'sec-docs', jumped);
    window.dispatchEvent(new Event('scroll')); await sleep(60); ok('the current section is marked', $$('.toc a.on').length === 1 && $$('.toc-lines i.on').length === 1);
    const toc = $('.toc'); toc.dispatchEvent(new MouseEvent('mouseenter')); ok('the list opens on hover', toc.classList.contains('open'));
    toc.dispatchEvent(new MouseEvent('mouseleave')); ok('and closes when the pointer leaves', !toc.classList.contains('open'));
    toc.focus(); await sleep(20); ok('opens for the keyboard', toc.classList.contains('open')); toc.dispatchEvent(new MouseEvent('mouseenter')); await sleep(20); $('.toc [data-toc]').click(); await sleep(20); ok('closes after a jump, even with focus there before', !toc.classList.contains('open'));
    scrollTo(0, 3000); window.dispatchEvent(new Event('scroll')); await sleep(60); ok('the navy bar stays at the top and the report bar scrolls away', $('.top').getBoundingClientRect().top === 0 && $('.rbar').getBoundingClientRect().bottom <= $('.top').getBoundingClientRect().bottom, `${$('.top').getBoundingClientRect().top}, ${$('.rbar').getBoundingClientRect().top}`); scrollTo(0, 0); await sleep(40); ok('the report bar is back at the top', $('.rbar').getBoundingClientRect().top >= $('.top').getBoundingClientRect().bottom - 1);
    scrollTo(0, 0); await sleep(40);
    click($('.fig.go[data-fig=overdue]')); await sleep(80); ok('a tile opens its list', C.UI.view === 'work' && $$('tr[data-id]').every(r => item(r.dataset.id).type === 'A')); click($('#logoBtn')); await sleep(60);
    ok('this week and next week side by side', !!$('.pair #sec-thisweek') && !!$('.pair #sec-nextweek'));
    click($('[data-mode=edit]')); await sleep(60); ok('Edit mode', C.UI.editing && !!$('.sheet.editing') && $$('[data-drag]').length >= 10 && !$('[data-uc-export]'));
    click($('#hPill')); await sleep(40); await menuPick('Off track'); ok('health: click the pill to change it', P().health === 'R' && $('#hPill').classList.contains('R')); await undo(); ok('health undo', P().health === 'A');
    const r = $('#hReason'); r.value = 'Line one.\nLine two.'; r.dispatchEvent(new Event('change')); await sleep(60); ok('reason saved, two lines', P().reason === 'Line one.\nLine two.'); await undo();
    const w = $('#wk'); w.value = '2026-11-06'; w.dispatchEvent(new Event('change')); await sleep(60); ok('week ending changed', P().week === '2026-11-06');
    const t = $('[data-title=summary]'); t.focus(); t.textContent = 'In short'; t.dispatchEvent(new Event('blur')); await sleep(60); ok('a heading edits in place', P().report.sections.find(s => s.id === 'summary').title === 'In short'); await undo();
    const t2 = $('[data-title=raid]'); t2.focus(); t2.textContent = 'Risks'; t2.dispatchEvent(new Event('blur')); await sleep(60); ok('any heading, not only text sections', P().report.sections.find(s => s.id === 'raid').title === 'Risks'); await undo();
  });

  await step('one editor everywhere', async () => {
    click($('[data-cs]')); await sleep(120); let pm = $('[data-cs] .ProseMirror');
    ok('current state opens in place in the full editor, with AI ("all editors should have the AI")', !!pm && $$('[data-cs] .ed-bar button').length >= 18 && !!$('[data-cs] [data-c=ai]'));
    await typeIn(pm, ' Extra sentence.'); ok('typing goes into it', pm.textContent.includes('Extra sentence.'));
    const range = document.createRange(); range.selectNodeContents(pm.querySelector('p')); const sel = getSelection(); sel.removeAllRanges(); sel.addRange(range); document.dispatchEvent(new Event('selectionchange')); await sleep(400);
    ok('highlighting shows the formatting bubble', !!$('.fmt-bubble') && $$('.fmt-bubble button').length >= 8);
    ok('the bubble has creaite\'s AI zone: Improve, Structure, Make into, Ask', !!$('.fmt-bubble .ai-zone') && ['Improve', 'Structure'].every(g => !!$(`.fmt-bubble [data-g=${g}]`)) && !!$('.fmt-bubble [data-b=ai-make]') && !!$('.fmt-bubble [data-b=ai-ask]'));
    { const before = pm.textContent; $('.fmt-bubble [data-g=Improve]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(40);
      ok('Improve lists creaite\'s options', ['Rewrite clearly', 'Shorter', 'Longer', 'Make it executive', 'Polish'].every(t => $('.menu').textContent.includes(t)));
      await menuPick('Make it executive'); await sleep(60); ok('a suggestion card, and nothing changes yet', !!$('.ai-sug') && /Where it stands/.test($('.ai-sug-b').textContent) && pm.textContent === before);
      const sc = $('.ai-sug [data-diff]'); sc.checked = true; sc.dispatchEvent(new Event('change')); await sleep(30); ok('Show changes marks what goes and what comes', !!$('.ai-sug-b del, .ai-sug-b ins'));
      $('.ai-sug [data-a=discard]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(40); ok('Discard leaves the text as it was', !$('.ai-sug') && pm.textContent === before);
      const reset = async () => { const z = document.createRange(); z.selectNodeContents(pm); z.collapse(false); getSelection().removeAllRanges(); getSelection().addRange(z); document.dispatchEvent(new Event('selectionchange')); await sleep(120); };
      await reset();
      const r2 = document.createRange(); r2.selectNodeContents(pm.querySelector('p')); getSelection().removeAllRanges(); getSelection().addRange(r2); document.dispatchEvent(new Event('selectionchange')); await sleep(400);
      $('.fmt-bubble [data-g=Structure]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(40); await menuPick('Summarise at the top'); await sleep(60);
      $('.ai-sug [data-a=accept]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(60); ok('Accept puts the suggestion in', !$('.ai-sug') && /In short:/.test(pm.textContent));
      $('[data-cs] [data-c=undo]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(40); ok('and the editor\'s Undo takes it back out', !/In short:/.test(pm.textContent));
      await reset();
      const r3 = document.createRange(); r3.selectNodeContents(pm.querySelector('p')); getSelection().removeAllRanges(); getSelection().addRange(r3); document.dispatchEvent(new Event('selectionchange')); await sleep(400);
      const n0 = S().items.length; $('.fmt-bubble [data-b=ai-make]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(40); await menuPick('Make this an action'); await sleep(60);
      const na2 = S().items.at(-1); ok('Make into: the selection becomes a new action, with Undo', S().items.length === n0 + 1 && na2.type === 'A' && na2.source === 'From selected text'); await undo(); pm.focus(); await sleep(40); }
    $('.fmt-bubble [data-b=bold]').dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(60); ok('bubble makes it bold', !!pm.querySelector('strong, b'));
    const end = document.createRange(); end.selectNodeContents(pm); end.collapse(false); sel.removeAllRanges(); sel.addRange(end); await sleep(40);
    document.execCommand('insertParagraph'); await typeIn(pm, '/'); await sleep(80); ok('"/" opens the command menu', !!$('.slash') && $$('.slash .opt').length >= 8);
    ok('the "/" menu has the AI commands too', ['Rewrite clearly', 'Make it executive', 'Ask AI'].every(t => $$('.slash .opt').some(o => o.textContent.includes(t))));
    await typeIn(pm, 'head'); key(pm, 'ArrowDown'); key(pm, 'Enter'); await sleep(80); ok('Enter inserts a heading', !$('.slash') && !!pm.querySelector('h2'));
    document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(120); ok('a click elsewhere saves', !$('[data-cs] .ProseMirror') && P().current.includes('Extra sentence.') && /<strong>|<b>/.test(P().current));
    await undo(); ok('current state undo', !P().current.includes('Extra sentence.'));
    click($('[data-cs]')); await sleep(120); await typeIn($('[data-cs] .ProseMirror'), ' throwaway'); key($('[data-cs] .ProseMirror'), 'Escape'); await sleep(80); ok('Esc cancels', !P().current.includes('throwaway') && !$('[data-cs] .ProseMirror'));
    click($('[data-txt=summary]')); await sleep(120); pm = $('[data-txt=summary] .ProseMirror'); ok('a text section opens in place', !!pm);
    const until = async f => { for (let i = 0; i < 30 && !f(); i++) await sleep(50); };
    await typeIn(pm, ' /'); await until(() => $('.slash')); ok('text sections keep the AI commands', $$('.slash .opt').some(o => o.textContent.includes('Draft with AI'))); key(pm, 'Escape'); await sleep(40); document.execCommand('delete'); document.execCommand('delete'); await sleep(40);
    await typeIn(pm, ' Plus one line.'); key(pm, 'Enter', { metaKey: true }); await until(() => !$('[data-txt=summary] .ProseMirror')); ok('Cmd+Enter saves it', P().report.sections.find(s => s.id === 'summary').html.includes('Plus one line.'));
  });

  await step('sections', async () => {
    const r0 = P().report.sections.map(s => s.id);
    click($('[data-opts=summary]')); await sleep(40); await menuPick('Leave out'); ok('section left out', P().report.sections.find(s => s.id === 'summary').hidden === true);
    click($('[data-mode=view]')); await sleep(60); ok('left out in View', !$('[data-sec=summary]')); click($('[data-mode=edit]')); await sleep(60);
    click($('[data-opts=summary]')); await sleep(40); await menuPick('Include'); ok('included again', !P().report.sections.find(s => s.id === 'summary').hidden);
    click($('[data-opts=summary]')); await sleep(40); await menuPick('Move down'); ok('move down goes by rows: over the pair below', P().report.sections.map(s => s.id).indexOf('summary') === r0.indexOf('summary') + 2);
    key($('[data-drag=summary]'), 'ArrowUp', { altKey: true }); await sleep(80); ok('Alt+Up moves it back', P().report.sections.map(s => s.id).indexOf('summary') === r0.indexOf('summary'));
    click($('[data-opts=thisweek]')); await sleep(40); await menuPick('Full width'); ok('full width: this week and next week stacked', !P().report.sections.find(s => s.id === 'thisweek').beside && !$('.pair'));
    click($('[data-opts=thisweek]')); await sleep(40); await menuPick('Place beside the next section'); ok('back side by side', !!$('.pair #sec-nextweek'));
    click($('[data-opts=summary]')); await sleep(40); await menuPick('Add a template below'); await sleep(90); key($('#atdQ'), 'Enter'); await sleep(140); const ns = P().report.sections[r0.indexOf('summary') + 1];
    ok('a text section is added from the Add a section box, and its heading is ready', ns.type === 'text' && document.activeElement === $(`[data-title="${ns.id}"]`)); click($(`[data-txt="${ns.id}"]`)); await sleep(140);
    ok('and it opens in the full editor', ns.type === 'text' && !!$(`[data-txt="${ns.id}"] .ProseMirror`) && $$(`[data-txt="${ns.id}"] .ed-bar button`).length >= 18);
    const npm = $(`[data-txt="${ns.id}"] .ProseMirror`); await typeIn(npm, '/'); await sleep(80); ok('"/" in a brand-new, empty section opens the menu', !!$('.slash') && $$('.slash .opt').length >= 10);
    key(npm, 'Enter'); await sleep(80); await typeIn(npm, 'Hello'); click($(`[data-txt="${ns.id}"] [data-c=h2]`)); await sleep(40); ok('the toolbar works there too', !!npm.querySelector('h2') && npm.textContent.includes('Hello'));
    key(npm, 'Escape'); await sleep(40);
    click($(`[data-opts="${ns.id}"]`)); await sleep(40); await menuPick('Delete section'); ok('delete text section', !P().report.sections.some(s => s.id === ns.id));
    ok('decisions tile hidden by default', P().report.glance.find(f => f.k === 'decisions').hidden === true);
    click($('[data-fig-eye=decisions]')); await sleep(60); ok('eye shows a tile', P().report.glance.find(f => f.k === 'decisions').hidden === false); click($('[data-fig-eye=decisions]')); await sleep(60);
    key($('[data-fig=risks]'), 'ArrowLeft', { altKey: true }); await sleep(80); ok('tile moved with Alt+Left', P().report.glance.map(f => f.k).indexOf('risks') === 1);
    ok('tiles: neutral, with the K2 outline fading from the bottom-left in the status colour', $('[data-fig=overdue]').classList.contains('rag-R') && getComputedStyle($('[data-fig=overdue]')).backgroundColor === getComputedStyle($('.glance')).getPropertyValue('--grey-50') || getComputedStyle($('[data-fig=overdue]'), '::after').backgroundImage.includes('linear-gradient(45deg'));
    $('[data-fig=overdue]').dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true })); await sleep(60); ok('right-click offers the tile colour', $$('.menu .swatch').length === 5);
    await menuPick('Amber'); ok('tile colour set by hand', P().report.glance.find(f => f.k === 'overdue').rag === 'A' && $('[data-fig=overdue]').classList.contains('rag-A'));
    $('[data-fig=overdue]').dispatchEvent(new MouseEvent('contextmenu', { bubbles: true, cancelable: true })); await sleep(60); await menuPick('Automatic'); ok('back to automatic', !P().report.glance.find(f => f.k === 'overdue').rag && $('[data-fig=overdue]').classList.contains('rag-R'));
  });

  /* #95: drag the dashboard's sections into full rows or half rows. Drags are simulated as the board's are: dragstart, dragover and drop with one DataTransfer */
  await step('sections: drag into full or half rows', async () => {
    const secs = () => P().report.sections, ids = () => secs().map(s => s.id), snap = () => JSON.stringify(secs()), s0 = snap(), rep0 = JSON.parse(s0), reset = async () => { window.ClarkDB.change('project', P(), { report: JSON.parse(JSON.stringify({ ...P().report, sections: rep0 })) }); C.refresh(); await sleep(60); }, rowsNow = () => $$('.sbody > .sec, .sbody > .pair').map(e => e.classList.contains('pair') ? [...e.children].map(c => c.dataset.sec) : [e.dataset.sec]);
    const sec = id => $(`[data-sec="${id}"]`), w = id => Math.round(sec(id).getBoundingClientRect().width);
    const drag = async (from, to, zone, drop = true) => { const dt = new DataTransfer(); $(`[data-drag="${from}"]`).dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); sec(from).dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt }));
      const b = sec(to).getBoundingClientRect(), x = zone === 'left' ? b.left + b.width * .2 : zone === 'right' ? b.left + b.width * .8 : b.left + b.width / 2, y = zone === 'top' ? b.top + 3 : zone === 'bottom' ? b.bottom - 3 : b.top + b.height / 2;
      const ev = t => new DragEvent(t, { bubbles: true, cancelable: true, dataTransfer: dt, clientX: x, clientY: y }); sec(to).dispatchEvent(ev('dragover')); const marks = $$('.drop-before,.drop-after,.drop-l,.drop-r').map(e => e.className.match(/drop-\w+/)[0] + ':' + e.dataset.sec);
      if (drop) sec(to).dispatchEvent(ev('drop')); else sec(from).dispatchEvent(new DragEvent('dragend', { bubbles: true })); await sleep(90); return marks; };
    click($('[data-mode=edit]')); await sleep(60);
    ok('each section has a grip in the margin, named Move or change <title>', $$('.sec').every(e => { const g = e.querySelector(':scope > .sh-ctl > [data-drag]'); return g && g.getAttribute('aria-label') === 'Move or change ' + e.querySelector('.st-t').textContent; }) && !$('.gut'));
    ok('the seed has one pair (this week, next week) at 50% each', JSON.stringify(rowsNow().filter(r => r.length > 1)) === '[["thisweek","nextweek"]]' && Math.abs(w('thisweek') - w('nextweek')) <= 1);
    /* the target shows first: a line between rows, an outline over half a lone section */
    let m = await drag('decisions', 'usecases', 'top', false); ok('over the top edge: a line above the row', m.join() === 'drop-before:usecases', m.join());
    m = await drag('decisions', 'raid', 'right', false); ok('over the right half of a lone section: the right outline', m.join() === 'drop-r:raid', m.join());
    m = await drag('decisions', 'thisweek', 'bottom', false); ok('over the bottom edge of a pair: a line under both halves', m.sort().join() === 'drop-after:nextweek,drop-after:thisweek', m.join());
    m = await drag('decisions', 'thisweek', 'left', false); ok('the middle of a pair offers no half outline (a row line instead)', m.every(x => /^drop-(before|after):/.test(x)), m.join());
    m = await drag('decisions', 'decisions', 'left', false); ok('over itself: no target', m.length === 0 && snap() === s0);
    ok('a drag that is not dropped changes nothing', snap() === s0);
    /* a new full row */
    await drag('decisions', 'usecases', 'top'); ok('drag to a new full row: Decisions sits above Use case summary', ids().indexOf('decisions') === ids().indexOf('usecases') - 1 && rowsNow().some(r => r.length === 1 && r[0] === 'decisions') && !secs().find(x => x.id === 'decisions').beside, ids().join());
    ok('the step is named in the toast', $('#toastMsg').textContent === 'Decisions moved to a full row above Use case summary', $('#toastMsg').textContent);
    await undo(); ok('Undo puts it back', snap() === s0);
    /* beside a lone section: 50/50 */
    await drag('raid', 'actions', 'right'); let sx = secs(); ok('drop beside: Open actions then Risks and issues share a row', JSON.stringify(rowsNow().filter(r => r.length > 1)) === '[["thisweek","nextweek"],["actions","raid"]]' && sx.find(x => x.id === 'actions').beside === true && !sx.find(x => x.id === 'raid').beside, JSON.stringify(rowsNow()));
    ok('the new pair is 50/50 and level', Math.abs(w('actions') - w('raid')) <= 1 && w('actions') * 2 < $('.sbody').getBoundingClientRect().width && Math.round(sec('actions').getBoundingClientRect().top) === Math.round(sec('raid').getBoundingClientRect().top), `${w('actions')} ${w('raid')}`);
    ok('the toast says what happened', $('#toastMsg').textContent === 'Risks and issues moved beside Open actions', $('#toastMsg').textContent);
    ok('any section type can pair (list sections here, not only text)', secs().find(x => x.id === 'actions').type === 'actions' && secs().find(x => x.id === 'raid').type === 'raid');
    await undo(); ok('Undo restores the layout', snap() === s0 && rowsNow().filter(r => r.length > 1).length === 1);
    await drag('decisions', 'usecases', 'left'); ok('drop on the left half puts it first', JSON.stringify(rowsNow().find(r => r.length > 1 && r.includes('usecases'))) === '["decisions","usecases"]', JSON.stringify(rowsNow())); await undo();
    /* out of a pair: the partner goes full width */
    await drag('nextweek', 'docs', 'top'); ok('drag out of a pair: Next week lands as a full row', rowsNow().some(r => r.length === 1 && r[0] === 'nextweek'), JSON.stringify(rowsNow()));
    ok('the partner is alone at full width', rowsNow().some(r => r.length === 1 && r[0] === 'thisweek') && !secs().find(x => x.id === 'thisweek').beside && w('thisweek') === w('summary'), `${w('thisweek')} ${w('summary')}`); await undo(); ok('Undo puts the pair back', snap() === s0);
    await drag('thisweek', 'actions', 'top'); ok('dragging the first half out leaves the second alone', rowsNow().some(r => r.length === 1 && r[0] === 'nextweek') && !secs().find(x => x.id === 'nextweek').beside, JSON.stringify(rowsNow())); await undo();
    /* a pair never holds a third, and pairs never chain */
    await drag('docs', 'thisweek', 'top'); ok('a pair is not offered a third (it lands as a row above)', rowsNow().every(r => r.length <= 2) && JSON.stringify(rowsNow().find(r => r.includes('thisweek'))) === '["thisweek","nextweek"]' && ids().indexOf('docs') < ids().indexOf('thisweek'), JSON.stringify(rowsNow())); await undo();
    await drag('actions', 'raid', 'left'); await drag('decisions', 'actions', 'right', false); const mm = $$('.drop-l,.drop-r'); ok('nothing is offered beside a section already paired', mm.length === 0); await drag('decisions', 'raid', 'right', false);
    ok('(and no chaining in the data: only the first of a pair carries beside)', secs().filter(x => x.beside).every(x => { const k = ids().indexOf(x.id); return !secs()[k + 1].beside; })); await undo(); await undo();
    ok('undo all the way back', snap() === s0, ids().join());
    /* the cover stays put; At a glance is not draggable when it is in the cover */
    ok('the cover has no grip and is not draggable', !$('.cover [data-drag]') && !$('.cover').draggable);
    /* the keyboard */
    click($('[data-opts=raid]')); await sleep(40); ok('the menu offers Place beside the next section and no Stack entries', $$('.menu [data-i]').some(o => o.textContent.includes('Place beside the next section')) && !$$('.menu [data-i]').some(o => /Stack|Full width/.test(o.textContent))); await menuPick('Place beside the next section');
    await undo(); ok('Undo of Place beside restores', snap() === s0); click($('[data-opts=raid]')); await sleep(40); await menuPick('Place beside the next section');
    ok('keyboard: Risks and issues is beside Open actions', JSON.stringify(rowsNow().find(r => r.includes('raid'))) === '["raid","actions"]' && Math.abs(w('raid') - w('actions')) <= 1, JSON.stringify(rowsNow())); ok('the toast names both', $('#toastMsg').textContent === 'Risks and issues placed beside Open actions');
    click($('[data-opts=actions]')); await sleep(40); ok('a paired section offers Full width, not Place beside', $$('.menu [data-i]').some(o => o.textContent.includes('Full width')) && !$$('.menu [data-i]').some(o => o.textContent.includes('Place beside'))); await menuPick('Full width');
    ok('keyboard: Full width stacks them, in the same order', JSON.stringify(rowsNow().filter(r => r.includes('raid') || r.includes('actions'))) === '[["raid"],["actions"]]' && !secs().some(x => x.id === 'raid' && x.beside)); await undo(); ok('Undo of Full width brings the pair back', !!$('.pair #sec-raid')); await reset();
    click($('[data-opts=summary]')); await sleep(40); ok('Place beside is not offered when the next section is already in a pair', !$$('.menu [data-i]').some(o => o.textContent.includes('Place beside'))); C.closePop();
    click($('[data-opts=decisions]')); await sleep(40); ok('the next section is the last one: still offered (Supporting documents is alone)', $$('.menu [data-i]').some(o => o.textContent.includes('Place beside the next section'))); C.closePop();
    click($('[data-opts=docs]')); await sleep(40); ok('the last section has no next to sit beside', !$$('.menu [data-i]').some(o => o.textContent.includes('Place beside'))); C.closePop();
    /* Move down / up go by rows */
    click($('[data-opts=nextweek]')); await sleep(40); await menuPick('Move down'); ok('Move down on half a pair takes it to a full row below', JSON.stringify(rowsNow().slice(rowsNow().findIndex(r => r.includes('thisweek')))).startsWith('[["thisweek"],["raid"]') || ids().indexOf('nextweek') > ids().indexOf('thisweek'), JSON.stringify(rowsNow())); await undo();
    key($('[data-drag=raid]'), 'ArrowUp', { altKey: true }); await sleep(80); ok('Alt+Up on a lone section steps over the pair above', ids().indexOf('raid') < ids().indexOf('thisweek'), ids().join()); await undo();
    /* survives a re-render and the View mode */
    await drag('raid', 'actions', 'right'); const keep = JSON.stringify(rowsNow()); C.render(); await sleep(80); ok('the layout survives a re-render', JSON.stringify(rowsNow()) === keep);
    click($('[data-mode=view]')); await sleep(80); ok('and View shows the same rows with no grips', JSON.stringify(rowsNow()) === keep && !$('[data-drag]') && Math.abs(w('actions') - w('raid')) <= 1);
    /* a hidden half: the other is full width in View, and shown (greyed) in Edit */
    click($('[data-mode=edit]')); await sleep(60); click($('[data-opts=raid]')); await sleep(40); await menuPick('Leave out'); click($('[data-mode=view]')); await sleep(80);
    ok('View: with one half left out, the other fills the row', !sec('raid') && !$('.pair #sec-actions') && w('actions') === w('summary'), `${w('actions')} ${w('summary')}`);
    click($('[data-mode=edit]')); await sleep(60); ok('Edit: both halves still shown, the hidden one greyed', !!$('.pair #sec-raid') && sec('raid').classList.contains('out'));
    await reset(); ok('back to the start', snap() === s0);
    /* section styles: slim, roomy, head, and dark mode keep two columns at 50% with the normal gap */
    const gap = () => Math.round(sec('nextweek').getBoundingClientRect().left - sec('thisweek').getBoundingClientRect().right);
    for (const d of ['slim', 'roomy', 'head']) { document.documentElement.dataset.dash = d; await sleep(40); const a = sec('thisweek').getBoundingClientRect(), b = sec('nextweek').getBoundingClientRect();
      ok(`section style ${d}: the pair is two equal columns, level`, Math.abs(a.width - b.width) <= 1 && Math.round(a.top) === Math.round(b.top) && b.left > a.right, `${Math.round(a.width)} ${Math.round(b.width)}`);
      if (d !== 'head') ok(`section style ${d}: the gap between them is the gap between rows (${d === 'roomy' ? 22 : 10} px)`, gap() === (d === 'roomy' ? 22 : 10), gap()); }
    document.documentElement.dataset.dash = 'one'; await sleep(40); ok('section style one card: still two columns', Math.abs(w('thisweek') - w('nextweek')) <= 1 && sec('nextweek').getBoundingClientRect().left > sec('thisweek').getBoundingClientRect().right);
    document.documentElement.dataset.dash = C.store.get('secs', 'slim') || 'slim'; document.documentElement.dataset.theme = 'dark'; await sleep(40); ok('dark mode: the pair keeps its columns and the cards turn dark', Math.abs(w('thisweek') - w('nextweek')) <= 1 && getComputedStyle(sec('thisweek')).backgroundColor !== 'rgb(255, 255, 255)');
    document.documentElement.dataset.theme = 'light'; await sleep(40);
    /* the published page */
    await drag('raid', 'actions', 'right'); click($('[data-mode=view]')); await sleep(60);
    const html = await C.webPage(); ok('published page: the pair is in the file', /<div class="pair"><section id="sec-thisweek">.*?<\/section><section id="sec-nextweek">/s.test(html) && /<div class="pair"><section id="sec-actions">.*?<\/section><section id="sec-raid">/s.test(html), (html.match(/class="pair"/g) || []).length);
    ok('published page: its scripts still parse (no stray backtick or ${ in the template)', [...html.matchAll(/<script>([^]*?)<\/script>/g)].length >= 1 && [...html.matchAll(/<script>([^]*?)<\/script>/g)].every(m => { try { new Function(m[1]); return true; } catch (e) { return false; } }));
    { const fr = document.createElement('iframe'); fr.style.cssText = 'position:fixed;left:0;top:0;width:1300px;height:900px;visibility:hidden'; fr.srcdoc = html; document.body.appendChild(fr);
      for (let i = 0; i < 100 && !(fr.contentDocument && fr.contentDocument.readyState === 'complete' && fr.contentDocument.querySelector('#panel')); i++) await sleep(50); await sleep(100);
      const fd = fr.contentDocument, fr$ = x => fd.querySelector(x), bx = x => fr$(x).getBoundingClientRect(), pn = fd.querySelectorAll('.pair');
      ok('published page: both pairs are drawn as two equal columns, level', pn.length === 2 && [...pn].every(pp => { const [a, b] = [...pp.children].map(c => c.getBoundingClientRect()); return Math.abs(a.width - b.width) <= 1 && Math.round(a.top) === Math.round(b.top) && b.left > a.right && a.width * 2 < pp.getBoundingClientRect().width; }), `${pn.length}`);
      ok('published page: the cards in a pair keep the card look', fr.contentWindow.getComputedStyle(fr$('#sec-thisweek')).borderTopWidth === '1px' && Math.round(bx('#sec-thisweek').top) === Math.round(bx('#sec-nextweek').top));
      fr.style.width = '600px'; await sleep(120); { const a = bx('#sec-thisweek'), b = bx('#sec-nextweek'); ok('published page: at 600 px a pair stacks', b.top >= a.bottom - 1 && Math.abs(a.width - b.width) <= 1, `${Math.round(a.width)}`); }
      fr.remove(); }
    await reset(); ok('and back to the start', snap() === s0); click($('[data-mode=edit]')); await sleep(60);
  });

  /* #101 and #96: the section control in the margin, its menu, and the Add a section box */
  await step('sections: the handle, its menu and the Add a template box', async () => {
    const secs = () => P().report.sections, ids = () => secs().map(s => s.id), snap = () => JSON.stringify(secs()), s0 = snap(), rep0 = JSON.parse(s0), reset = async () => { window.ClarkDB.change('project', P(), { report: JSON.parse(JSON.stringify({ ...P().report, sections: rep0 })) }); C.refresh(); await sleep(60); };
    const sec = id => $(`[data-sec="${id}"]`), menuText = () => $$('.menu > *').map(e => e.classList.contains('sep') ? '|' : e.textContent.trim()), selT = () => $('.atd-c[aria-selected=true]')?.dataset.t, names = () => $$('.atd-c b').map(b => b.textContent);
    const rowsNow = () => $$('.sbody > .sec, .sbody > .pair').map(e => e.classList.contains('pair') ? [...e.children].map(c => c.dataset.sec) : [e.dataset.sec]);
    const input = (el, v) => { el.value = v; el.dispatchEvent(new Event('input', { bubbles: true })); };
    const open = async id => { click($(`[data-addbelow="${id}"]`)); await sleep(90); };
    C.store.set('tplRecent', []); click($('[data-mode=edit]')); await sleep(60); document.activeElement?.blur?.();
    /* the handle */
    ok('Edit: each section has a grip in the margin named Move or change <title>, tooltip as drawn, and a + named Add a template below <title>', $$('.sec').every(e => { const c = e.querySelector(':scope > .sh-ctl'), gr = c && c.querySelector('button[data-drag]'), ad = c && c.querySelector('button[data-addbelow]'), t = e.querySelector('.st-t').textContent;
      return gr && gr.getAttribute('aria-label') === 'Move or change ' + t && gr.title === 'Drag to move · click for options' && ad && ad.getAttribute('aria-label') === 'Add a template below ' + t && !e.querySelector('h2 [data-drag]') && !e.querySelector('h2 [data-opts]'); }) && !$('[data-opts]:not([data-drag])'));
    ok('the old heading chevron is gone, and the blue square is back in the heading', !$('h2.st .ib[aria-label$="section options"]') && getComputedStyle($('#sec-summary h2.st'), '::before').display !== 'none');
    const g = $('[data-drag=current]'), ctl = g.closest('.sh-ctl'); g.scrollIntoView({ block: 'center' }); await sleep(250);
    ok('at rest the control is faint (about 0.3)', Math.abs(parseFloat(getComputedStyle(ctl).opacity) - 0.3) < 0.05, getComputedStyle(ctl).opacity);
    g.focus(); await sleep(250); ok('with focus on it the control is at full strength', getComputedStyle(ctl).opacity === '1'); g.blur(); await sleep(250); ok('and faint again when the focus leaves', parseFloat(getComputedStyle(ctl).opacity) < 0.4);
    ok('the style sheet makes it full over the section (:hover)', /\.sec:hover > \.sh-ctl/.test(window.CLARK_APPCSS));
    { const rg = $('[data-drag=nextweek]'); rg.scrollIntoView({ block: 'center' }); await sleep(60); const rb = rg.getBoundingClientRect(), lh = sec('thisweek').querySelector('h2').getBoundingClientRect(), rr = sec('nextweek').getBoundingClientRect(), lr = sec('thisweek').getBoundingClientRect();
      const hit = document.elementFromPoint(rb.left + rb.width / 2, rb.top + rb.height / 2);
      ok('the right half of a pair has its handle in the gap between the cards, clear of the left card\'s content, and clickable', rb.left >= lh.right - 0.5 && rb.left < rr.left && rb.right > lr.right && rb.left > lr.left + lr.width / 2 && !!hit && hit.closest('[data-drag]') === rg, `${Math.round(rb.left)}-${Math.round(rb.right)} ${Math.round(lh.right)} ${Math.round(lr.right)} ${Math.round(rr.left)}`); }
    /* the handle lives in the page's own gutter: no margin or padding is added, so the sections are the same size and place in View and in Edit (the window is 1440 px) */
    { const geo = () => Object.fromEntries($$('.sbody .sec').map(e => { const b = e.getBoundingClientRect(); return [e.dataset.sec, [Math.round(b.left * 10), Math.round(b.width * 10)].join('/')]; }));
      const ge = geo(), gutter = $$('.sbody .sec').every(e => { const c = e.querySelector(':scope > .sh-ctl').getBoundingClientRect(), b = e.getBoundingClientRect(), right = e.matches('.pair > .sec + .sec'); return c.left >= 0 && c.right <= innerWidth && (right ? c.left < b.left && c.right > b.left : c.right <= b.left); });
      click($('[data-mode=view]')); await sleep(80); const gv = geo(); click($('[data-mode=edit]')); await sleep(80);
      ok('every section keeps its left edge and its width between View and Edit (' + innerWidth + ' px window)', Object.keys(gv).length >= 8 && Object.keys(gv).every(k => ge[k] === gv[k]), JSON.stringify(Object.keys(gv).filter(k => ge[k] !== gv[k]).map(k => [k, ge[k], gv[k]])));
      ok('each handle lies left of its card (the right half of a pair, across the gap) and inside the window', gutter);
      ok('nothing is added to the report column or the sections for the handle', parseFloat(getComputedStyle($('.dash-wrap')).marginLeft) === 0 && $$('.sbody .sec').every(e => parseFloat(getComputedStyle(e).marginLeft) === 0)); }
    /* the menu */
    click($('[data-drag=decisions]')); await sleep(40);
    ok('the menu: Add a template below, Move up, Move down, Place beside the next section, Leave out (a section that is not text has no Delete)', JSON.stringify(menuText()) === JSON.stringify(['Add a template below…', '|', 'Move upAlt ↑', 'Move downAlt ↓', 'Place beside the next section', '|', 'Leave out of the published page']), menuText().join(' / ')); C.closePop();
    click($('[data-drag=summary]')); await sleep(40);
    ok('a text section: Delete section closes the list, in danger style; no Add a text section below', JSON.stringify(menuText()) === JSON.stringify(['Add a template below…', '|', 'Move upAlt ↑', 'Move downAlt ↓', '|', 'Leave out of the published page', 'Delete section']) && $$('.menu .danger').length === 1 && /Delete section/.test($('.menu .danger').textContent), menuText().join(' / ')); C.closePop();
    click($('[data-drag=thisweek]')); await sleep(40); ok('half of a pair: Full width instead of Place beside', menuText().includes('Full width') && !menuText().some(t => /Place beside/.test(t))); C.closePop();
    { const i0 = ids().indexOf('raid'); ok('the grip is a button (Enter and Space open the menu)', $('[data-drag=raid]').tagName === 'BUTTON'); key($('[data-drag=raid]'), 'ArrowDown', { altKey: true }); await sleep(90); ok('Alt+Down on the grip still moves the section', ids().indexOf('raid') !== i0 || ids().join() !== rep0.map(x => x.id).join()); await reset(); }
    ok('no "Add a text section below" entry and no "+ Add a section" line between sections', !$('.add-line,.sec-add') && !/Add a text section below/.test($('.sbody').textContent));
    /* a left-out section: an eye-off mark on its handle */
    click($('[data-drag=docs]')); await sleep(40); await menuPick('Leave out'); ok('a section left out shows an eye-off mark on its handle', !!sec('docs').querySelector('.sh-ctl .sh-off')); await undo(); ok('and it goes with Undo', !sec('docs').querySelector('.sh-off'));
    /* the + opens the box */
    await open('summary'); const d = $('#dlg');
    ok('the + opens the Add a section box, with a search box, a close button and the footer links', d.open && d.querySelector('h2').textContent === 'Add a section' && $('#atdQ').placeholder === 'Search templates' && !!d.querySelector('.atd-h [data-close]') && /About section templates/.test(d.querySelector('.atd-f').textContent) && !!d.querySelector('#atdGo') && document.activeElement === $('#atdQ'));
    ok('kinds with counts, as drawn', JSON.stringify($$('#atdK [data-k]').map(b => b.textContent)) === JSON.stringify(['All20', 'Text and pictures6', 'Figures2', 'Work items4', 'Files and links3', 'People and dates3', 'Notes2']) && /Recently used/.test($('#atdK').textContent));
    ok('Work items list is a template, full or half, under Work items (#96)', (t => !!t && t.kind === 'raid' && t.fit.join() === 'Full,Half')(C.templates.find(t => t.id === 'wi-list')) && names().includes('Work items list'));
    ok('20 template cards, each with a sketch, a name and Full or Half chips', names().length === 20 && $$('.atd-c').every(c => c.querySelector('.sk') && c.querySelectorAll('.fit em').length >= 1) && JSON.stringify(names()) === JSON.stringify(C.templates.map(t => t.name)) && names().includes('Key figures, four') && names().includes('One document'));
    click($('[data-k=figures]')); await sleep(30); ok('a kind filters the cards', names().length === 2 && names().every(n => /Key figures/.test(n))); click($('[data-k=raid]')); await sleep(30); ok('Work items: the two RAID cards and the list', names().join() === 'RAID cards, three,RAID cards, four,Work items list,Needs from you'); click($('[data-k=all]')); await sleep(30);
    input($('#atdQ'), 'quote'); await sleep(30); ok('the search filters as you type', names().join() === 'Quote' && selT() === 'quote'); input($('#atdQ'), 'zzzz'); await sleep(30); ok('and says so when nothing matches, with Add section off', !names().length && /No template matches/.test($('#atdG').textContent) && $('#atdGo').disabled); input($('#atdQ'), ''); await sleep(30);
    ok('the preview shows the chosen template: name, sketch, description, Holds, Place it, Help link', selT() === 'text' && $('#atdP h3').textContent === 'Text' && !!$('#atdP .sk') && $$('#atdP .atd-els span').map(s => s.textContent).join() === 'Heading,Text' && /On its own row/.test($('#atdP').textContent) && /See every template explained in Help/.test($('#atdP').textContent));
    key($('#atdQ'), 'ArrowDown'); ok('Down moves a row through the cards (three across)', selT() === 'figures-4', selT()); key($('#atdQ'), 'ArrowUp'); ok('Up moves back', selT() === 'text');
    $('.atd-c[data-t=text]').focus(); key(document.activeElement, 'ArrowRight'); ok('Right moves to the next card and focus goes with it', selT() === 'text-image' && document.activeElement.dataset.t === 'text-image'); key(document.activeElement, 'End'); ok('End goes to the last', selT() === 'one-doc');
    ok('the preview follows (Holds for One document)', $('#atdP h3').textContent === 'One document' && $$('#atdP .atd-els span').map(s => s.textContent).join() === 'Heading,File,Text');
    ok('no Beside choice when the next section is already in a pair', !$('#atdP input[value=beside]'));
    click($('#dlg [data-close]')); await sleep(40); ok('Cancel adds nothing and closes', !d.open && snap() === s0);
    /* Place it: beside the next section when it is alone, and the template is half width */
    await open('decisions'); input($('#atdQ'), 'banner'); await sleep(30); ok('a full-width-only template cannot go beside (the choice is offered, switched off)', !!$('#atdP input[value=beside]') && $('#atdP input[value=beside]').disabled);
    input($('#atdQ'), 'callout'); await sleep(30); const bs = $('#atdP input[value=beside]'); ok('Place it offers Beside <next section> (half width) when allowed', !!bs && !bs.disabled && /Beside “Supporting documents” \(half width\)/.test(bs.closest('label').textContent));
    click(bs); key($('#atdQ'), 'Enter'); await sleep(140);
    const cn = secs().find(x => x.kind === 'callout'); ok('Add (Enter) with Beside: the callout sits beside Supporting documents, as one setRep step', !d.open && !!cn && cn.type === 'tpl' && cn.title === 'Callout' && cn.beside === true && ids().indexOf(cn.id) === ids().indexOf('docs') - 1 && !!$(`.pair #sec-${cn.id}`) && !!$('.pair #sec-docs') && /Callout added beside Supporting documents/.test($('#toast').textContent), $('#toast').textContent);
    ok('focus goes to the new section\'s heading', document.activeElement === $(`[data-title="${cn.id}"]`));
    click($('[data-mode=view]')); await sleep(80); ok('View: with the empty callout left out, Supporting documents fills the row', !sec(cn.id) && !$('.pair') === false && Math.abs(sec('docs').getBoundingClientRect().width - sec('summary').getBoundingClientRect().width) <= 1); click($('[data-mode=edit]')); await sleep(60);
    await undo(); ok('Undo takes it away in one step', snap() === s0);
    /* adding Text: a real text section, as the old menu entry did */
    await open('summary'); key($('#atdQ'), 'Enter'); await sleep(140); const tx = secs()[ids().indexOf('summary') + 1];
    ok('Text adds a real text section below, with Undo; the toast says so; focus on its heading', tx.type === 'text' && tx.title === 'New section' && !tx.beside && /Text added below Summary/.test($('#toast').textContent) && document.activeElement === $(`[data-title="${tx.id}"]`) && !!$(`[data-txt="${tx.id}"]`), $('#toast').textContent);
    await undo(); ok('Undo of Text', snap() === s0);
    /* a template that is not text: an empty section */
    await open('summary'); input($('#atdQ'), 'figures'); await sleep(30); ok('Key figures, four is chosen from the search', selT() === 'figures-4'); click($('#atdGo')); await sleep(140);
    const kf = secs()[ids().indexOf('summary') + 1];
    ok('a template adds { type: tpl, kind, title } below the chosen section', kf.type === 'tpl' && kf.kind === 'figures-4' && kf.title === 'Key figures, four' && /Key figures, four added below Summary/.test($('#toast').textContent), JSON.stringify(kf));
    ok('it draws its empty state: dashed areas with each element named', sec(kf.id).classList.contains('sec-tpl') && $$(`#sec-${kf.id} .tp-el`).length === 5 && $$(`#sec-${kf.id} .tp-el .tp-tag`).map(t => t.textContent).join() === 'Figure,Figure,Figure,Figure,Caption' && getComputedStyle($(`#sec-${kf.id} .tp-el`)).borderTopStyle === 'dashed' && !!$(`#sec-${kf.id} .sh-ctl`));
    ok('its heading is editable and focused', document.activeElement === $(`[data-title="${kf.id}"]`) && $(`[data-title="${kf.id}"]`).isContentEditable);
    { const h = $(`[data-title="${kf.id}"]`); h.textContent = 'Numbers this week'; h.dispatchEvent(new Event('blur')); await sleep(80); ok('renaming it saves', secs().find(x => x.id === kf.id).title === 'Numbers this week'); }
    C.render(); await sleep(80); ok('the template section survives a re-render', !!$(`#sec-${kf.id} .tp-el`) && secs().find(x => x.id === kf.id).kind === 'figures-4');
    ok('Recently used keeps it', C.store.get('tplRecent')[0] === 'figures-4');
    click($('[data-mode=view]')); await sleep(80); ok('View leaves an empty template out, like the published page', !sec(kf.id) && !$(`.toc a[href="#sec-${kf.id}"]`));
    const html = await C.webPage(); ok('published page: the empty template is left out; the page still builds and its scripts parse', !html.includes('sec-' + kf.id) && html.includes('id="sec-summary"') && [...html.matchAll(/<script>([^]*?)<\/script>/g)].length >= 1 && [...html.matchAll(/<script>([^]*?)<\/script>/g)].every(m => { try { new Function(m[1]); return true; } catch (e) { return false; } }));
    click($('[data-mode=edit]')); await sleep(60);
    click($(`[data-drag="${kf.id}"]`)); await sleep(40); await menuPick('Delete section'); ok('a template section can be deleted', !secs().some(x => x.id === kf.id));
    await reset(); ok('back to the start', snap() === s0);
    /* recently used, and the Help links */
    await open('raid'); ok('Recently used lists what was added, and picking it selects that template', /Key figures, four/.test($('#atdK').textContent) && (click($('#atdK [data-r=figures-4]')), selT() === 'figures-4'));
    click($('#atdP [data-help]')); await sleep(140); ok('the preview\'s Help link closes the box and opens Help › Section templates', !$('#dlg').open && C.UI.view === 'help' && !!$('#hp-ref-section-templates') && $('#hpPane').dataset.tab === 'reference');
    ok('Help lists every template with its description and fit', $$('#hp-ref-section-templates tbody tr').length === 20 && C.templates.every(t => { const row = $$('#hp-ref-section-templates tbody tr').find(r => r.cells[0].textContent === t.name); return row && row.cells[1].textContent === t.d && (row.cells[2].textContent.toLowerCase().includes('half')) === t.fit.includes('Half'); }));
    C.help.open('howto-add-a-section-from-a-template'); await sleep(140); ok('Help has the task "Add a section from a template"', !!$('#hp-howto-add-a-section-from-a-template'));
    C.help.open('ref-keys'); await sleep(140); ok('Help\'s keys table lists V and E', $$('#hp-ref-keys tbody tr').some(r => /V.*E/.test(r.cells[0].textContent) && /View mode and Edit mode/.test(r.cells[1].textContent)));
    C.go('dashboard'); await sleep(80); click($('[data-mode=edit]')); await sleep(60); await open('raid'); click($('#dlg .atd-f [data-help]')); await sleep(140); ok('the footer\'s About section templates link opens Help too', C.UI.view === 'help'); C.go('dashboard'); await sleep(80);
    /* V and E */
    ok('the View and Edit buttons say their keys', $('[data-mode=view]').title === 'View (V)' && $('[data-mode=edit]').title === 'Edit (E)');
    const kd = (k, o = {}) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...o }));
    click($('[data-mode=view]')); await sleep(60); document.activeElement?.blur?.(); kd('e'); await sleep(80); ok('E switches the Dashboard to Edit', C.UI.editing && !!$('.sheet.editing')); kd('v'); await sleep(80); ok('V switches it to View', !C.UI.editing && !$('.sheet.editing'));
    kd('e', { ctrlKey: true }); kd('e', { metaKey: true }); kd('e', { altKey: true }); await sleep(60); ok('with a modifier they do nothing', !C.UI.editing);
    { const w = $('#wk'); w.focus(); w.dispatchEvent(new KeyboardEvent('keydown', { key: 'e', bubbles: true, cancelable: true })); await sleep(60); ok('typing in a field: E is ignored', !C.UI.editing); w.blur(); }
    kd('e'); await sleep(80); { const t = $('[data-title]'); t.focus(); t.dispatchEvent(new KeyboardEvent('keydown', { key: 'v', bubbles: true, cancelable: true })); await sleep(60); ok('typing in a heading: V is ignored', C.UI.editing); t.blur(); }
    click($('[data-drag=raid]')); await sleep(40); kd('v'); await sleep(60); ok('with a menu open they are ignored', C.UI.editing); C.closePop();
    await open('raid'); kd('v'); await sleep(60); ok('with a box open they are ignored', C.UI.editing && $('#dlg').open); click($('#dlg [data-close]')); await sleep(40);
    C.go('work'); await sleep(60); kd('e'); await sleep(40); ok('only on the Dashboard', C.UI.view === 'work'); C.go('dashboard'); await sleep(60);
    if (!C.UI.editing) { click($('[data-mode=edit]')); await sleep(60); } await reset(); C.store.set('tplRecent', []);
  });

  await step('use case summary', async () => {
    ok('use cases: summary strip, then slim rows with aligned status words (D2)', !!$('.uc-strip .uc-meter') && $$('.ucr .uc-st .ucw').length === 6 && new Set($$('.ucr .uc-st').map(e => Math.round(e.getBoundingClientRect().left))).size === 1);
    const row = $('.ucr[data-uc="PDF/1.1"]'); row.dispatchEvent(new MouseEvent('mouseenter', { clientX: 300, clientY: 300 })); await sleep(1100); ok('hover for a second shows a tooltip', !!$('.slowtip') && $('.slowtip').textContent.includes('open')); row.dispatchEvent(new MouseEvent('mouseleave')); await sleep(20);
    click($('.ucr[data-uc="PDF/1.1"] .uc-name')); await sleep(60); ok('row opens its detail', $('.ucd[data-ucd="PDF/1.1"]').classList.contains('open'));
    ok('no edit icon: where it stands edits in place', !$('[data-uc-edit]') && !!$('[data-uc-std="PDF/1.1"].inl'));
    click($('[data-uc-status="PDF/1.1"]')); await sleep(40); await menuPick('On track'); const u = S().usecases.find(x => x.key === 'PDF/1.1'); ok('status changed inline', u.status === 'On track'); ok('a use case change records where, with from and to', S().history.some(h => h.kind === 'uc' && h.id === '1.1' && h.field === 'status' && h.how === window.ClarkDB.who('in the report') && h.from === 'Flag' && h.to === 'On track')); await undo();
    const h = $('[data-uc-head="PDF/1.1"]'); h.focus(); h.textContent = 'New headline'; h.dispatchEvent(new Event('blur')); await sleep(60); ok('headline edited inline', u.headline === 'New headline');
    click($('[data-uc-std="PDF/1.1"]')); await sleep(120); await typeIn($('[data-uc-std="PDF/1.1"] .ProseMirror'), ' Added.'); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(120); ok('where it stands saved', u.standing.includes('Added.'));
    const si = $('[data-uc-step="PDF/1.1"]'); si.value = 'Jo Ellis: confirm the loader scope'; key(si, 'Enter'); await sleep(120); const ni = S().items.at(-1);
    ok('next step added inline as "Owner: what"', ni.uc === '1.1' && ni.owner === 'Jo Ellis' && ni.title === 'confirm the loader scope' && document.activeElement?.dataset.ucStep === 'PDF/1.1');
    click($('[data-uc-link="PDF/1.1"]')); await sleep(80); ok('link an existing work item: picker of unlinked items', $('#dlg').open && $$('#pkList li').length >= 5 && !$('#pkList').textContent.includes('PDF-A-012'));
    const lq = $('#pkQ'); lq.value = 'testers'; lq.dispatchEvent(new Event('input')); await sleep(40); click($('#pkList input')); $('#pkF').requestSubmit(); await sleep(100);
    ok('the item is linked and shows as a next step', item('PDF-A-019').uc === '1.1' && $('.ucd[data-ucd="PDF/1.1"]').textContent.includes('Book the testers')); await undo(); ok('link undo', item('PDF-A-019').uc === '');
    const own = $(`[data-ce="${ni.id}"][data-f="owner"]`); own.focus(); own.textContent = 'Sam Rivers'; own.dispatchEvent(new Event('blur')); await sleep(60); ok('next step owner edited inline', item(ni.id).owner === 'Sam Rivers');
    click($('[data-uc-eye="PDF/1.2"]')); await sleep(40); ok('eye: the use case stays, greyed, with Undo', S().usecases.find(x => x.key === 'PDF/1.2').client === false && $('.ucr[data-uc="PDF/1.2"]').classList.contains('leaving') && !$('#toastUndo').hidden);
    await undo(); ok('eye undo', S().usecases.find(x => x.key === 'PDF/1.2').client === true && !$('.ucr[data-uc="PDF/1.2"]').classList.contains('leaving'));
    click($('[data-uc-eye="PDF/1.2"]')); await sleep(7000); ok('without Undo it leaves the editor', !$('.ucr[data-uc="PDF/1.2"]'));
    click($('[data-ucback]')); await sleep(80); ok('it comes back through the picker', $('#dlg').open && $$('#pkList li').length === 1); click($('#pkList input')); $('#pkF').requestSubmit(); await sleep(80); ok('picker adds it back', S().usecases.find(x => x.key === 'PDF/1.2').client === true);
    click($('[data-uc-add]')); await sleep(60); $('#ucI').value = '3.1'; $('#ucT').value = 'Report checks'; $('#ucF').requestSubmit(); await sleep(80); ok('add use case', S().usecases.some(x => x.key === 'PDF/3.1'));
    click($('[data-uc-del="PDF/3.1"]')); await sleep(60); click($('#cfYes')); await sleep(80); ok('delete use case', !S().usecases.some(x => x.key === 'PDF/3.1')); await undo();
  });

  await step('report work items', async () => {
    ok('work items are list rows, not boxed tables', !!$('#sec-actions .wl .wl-row') && !$('#sec-actions table'));
    { const r = $('#sec-actions .wl-row[data-row="PDF-A-021"]'); click(r.querySelector('.wl-state')); await sleep(40); ok('a single click on a row, outside a field, opens its peek', $('#peek').classList.contains('on') && $('#peek').textContent.includes('PDF-A-021')); key(document.body, 'Escape'); await sleep(60);
      click($('[data-ce="PDF-A-021"][data-f="title"]')); await sleep(40); ok('a click in a field edits, no peek', !$('#peek').classList.contains('on')); }
    const x = item('PDF-A-012'), tt = $('[data-ce="PDF-A-012"][data-f="title"]'); tt.focus(); tt.textContent = 'Confirm the handover'; tt.dispatchEvent(new Event('blur')); await sleep(60); ok('title edits in place', x.title === 'Confirm the handover'); await undo();
    click($('[data-cst="PDF-A-012"]')); await sleep(40); await menuPick('Closed'); ok('status from the row', x.status === 'Closed'); await undo();
    click($('[data-cdue="PDF-A-015"]')); await sleep(40); ok('the date picker is one panel, clark\'s own', !!$('.menu .cp') && !$('.menu input[type=date]')); key(document.body, 'Escape'); await sleep(40); ok('a single Esc closes it', !$('.menu')); click($('[data-cdue="PDF-A-015"]')); await sleep(40); while (!$('.menu [data-cp="2026-12-01"]')) { click($('.menu [data-cpm="1"]')); await sleep(20); } click($('.menu [data-cp="2026-12-01"]')); await sleep(60); ok('date from the row', item('PDF-A-015').due === '2026-12-01'); await undo();
    const ai = $('[data-add=actions]'); ai.value = 'Sam Rivers: Book the room'; key(ai, 'Enter'); await sleep(120); const na = S().items.at(-1);
    ok('add an action inline', na.type === 'A' && na.owner === 'Sam Rivers' && na.title === 'Book the room' && na.client && !!$(`[data-row="${na.id}"]`));
    click($('[data-cst="PDF-003"]')); await sleep(40); ok('a risk or issue pill offers its rating', $$('.menu [data-i]').map(o => o.textContent.trim()).slice(0, 3).join() === 'Red,Amber,Green' && /Close it/.test($('.menu').textContent));
    await menuPick('Green'); ok('rating changed from the pill sets the priority', item('PDF-003').priority === 'Low' && $('[data-cst="PDF-003"]').textContent === 'Green'); await undo(); ok('the colour comes from the priority', item('PDF-003').priority === 'High' && $('[data-cst="PDF-003"]').textContent === 'Red');
    const ri = $('[data-add=raid]'); ri.value = 'Supplier capacity is short'; key(ri, 'Enter'); await sleep(120); ok('add a risk inline', S().items.at(-1).type === 'R');
    click($('[data-eye="PDF-A-021"]')); await sleep(40); ok('eye: the row stays, greyed, with Undo', item('PDF-A-021').client === false && $('[data-row="PDF-A-021"]').classList.contains('leaving'));
    await sleep(7000); ok('then it leaves the editor', !$('[data-row="PDF-A-021"]'));
    click($('[data-addfrom=actions]')); await sleep(80); ok('picker: searchable list', $('#dlg').open && !!$('#pkQ') && $$('#pkList li').length >= 3);
    const q = $('#pkQ'); q.value = 'training plan'; q.dispatchEvent(new Event('input')); await sleep(40); ok('picker search filters', $$('#pkList li').length === 1 && $('#pkList').textContent.includes('PDF-A-021'));
    click($('#pkList input')); ok('picker counts the selection', $('#pkCount').textContent === '1 selected' && !$('#pkGo').disabled);
    $('#pkF').requestSubmit(); await sleep(80); ok('picker adds it back', item('PDF-A-021').client === true);
    click($('[data-addfrom=raid]')); await sleep(80); click($('#dlg [data-t=I]')); await sleep(40); ok('picker type filter', $$('#pkList li').length > 0 && $$('#pkList li').every(li => S().items.some(y => y.type === 'I' && li.textContent.includes(y.id))));
    click($('#pkAll')); ok('select all shown', $$('#pkList input:checked').length === $$('#pkList li').length); click($('#dlg [data-close]')); await sleep(40);
    click($('[data-open="PDF-003"]')); await sleep(80); ok('the ID opens the peek', $('#peek').classList.contains('on') && $('#peek .pk-meta').textContent.includes('PDF-003')); key(document.body, 'Escape'); await sleep(40);
    click($('[data-doc-add]')); await sleep(60); $('#dT').value = 'Steering slides'; $('#dU').value = 'https://example.com/s'; $('#dF').requestSubmit(); await sleep(80); ok('document link added', P().docs.some(d => d.title === 'Steering slides'));
    const id = P().docs.find(d => d.title === 'Steering slides').id; click($(`[data-doc-eye="${id}"]`)); await sleep(7000); ok('document taken off, then gone from the editor', P().docs.find(d => d.id === id).hidden && !$(`[data-doc-eye="${id}"]`));
    click($('[data-docback]')); await sleep(60); click($('#pkList input')); $('#pkF').requestSubmit(); await sleep(80); ok('document added back', !P().docs.find(d => d.id === id).hidden);
  });

  await step('milestones on the dashboard', async () => {
    const shown = S().milestones.filter(m => m.code === 'PDF' && m.client);
    ok('line has a mark per milestone shown', $$('.sheet .mv-mk').length === shown.length);
    ok('list in the design system format, 5 at first', $$('.sheet .msl-row').length === Math.min(5, shown.length) && !!$('.sheet .msl .node'));
    ok('a Forecast milestone', $$('.sheet .msl-row').length >= 1 && S().milestones.some(m => window.ClarkDB.msState(m) === 'Forecast'));
    click($('.sheet [data-msall]')); await sleep(60); ok('show all', $$('.sheet .msl-row').length === shown.length);
    click($('.sheet .msl-row')); await sleep(80); ok('a row opens the milestone peek', !!$('#peek .states')); key(document.body, 'Escape'); await sleep(40);
    const wrap = $('.sheet .mv-wrap'), h0 = parseInt(wrap.style.height); wrap.style.height = (h0 * 2) + 'px'; wrap.dispatchEvent(new PointerEvent('pointerup', { bubbles: true })); for (let i = 0; i < 40 && !(C.store.get('tlZoom.dash', 1) > 1.5); i++) await sleep(100); ok('a taller line zooms in', C.store.get('tlZoom.dash', 1) > 1.5 && +$('.sheet .mv-strip').style.getPropertyValue('--z') > 1.5, `zoom ${C.store.get('tlZoom.dash', 1)}, height ${h0} to ${wrap.offsetHeight}`);
    C.store.set('tlZoom.dash', 1); C.refresh(); await sleep(60);
    const m = shown[1]; click($(`.sheet [data-ms-eye="${m.id}"]`)); await sleep(40); ok('eye: the milestone stays, greyed, with Undo', !m.client && $(`.sheet .msl-row[data-ms="${m.id}"]`).classList.contains('leaving')); await undo(); ok('milestone eye undo', m.client);
  });

  await step('publish', async () => {
    click($('[data-mode=view]')); await sleep(60);
    const b0 = blobs; ok('Publish is under the profile circle, not on the page', !$('#pubBtn') && !$('#pubMore')); click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60);
    ok('publish asks where: Local always, To client off', $('#pubLocal').checked && $('#pubLocal').disabled && !$('#pubClient').checked && $('#pubClient').disabled);
    $('#pubF').requestSubmit(); await sleep(1200); const html = C.lastPublished || '';
    ok('publish makes a web page', blobs === b0 + 1 && /<!doctype html>/.test(html));
    ok('client page: Dashboard, Work items, Milestones only', (html.match(/<button data-v="/g) || []).length === 3 && /data-v="dashboard"/.test(html) && /data-v="work"/.test(html) && /data-v="milestones"/.test(html));
    ok('clark\'s icon: the editor\'s favicon, and inside the published file', /clark-icon\.svg$/.test($('link[rel=icon]').href) && /<link rel="icon" href="data:image\/svg\+xml,/.test(html));
    ok('client page: the milestone timeline and list', html.includes('class="mv-strip') && html.includes('class="msl"'));
    ok('client page: creaite\'s client words for milestones', html.includes('Expected later') && />\s*Late\s*</.test(html.replace(/<svg[\s\S]*?<\/svg>/g, '')) && !/>\s*Slipped\s*</.test(html.replace(/<svg[\s\S]*?<\/svg>/g, '')));
    ok('client page: work items as list rows', html.includes('class="wl-row"') && !html.includes('contenteditable'));
    ok('client page: the contents rail', html.includes('class="toc"'));
    ok('page holds only chosen items', html.includes('PDF-A-012') && !html.includes('PDF-A-016'));
    ok('Movement never published', !html.includes('Decide what to do'));
    /* the published page itself: the editor's look and its view-only interactions */
    const fr = document.createElement('iframe'); fr.style.cssText = 'position:fixed;left:0;top:0;width:1300px;height:900px;visibility:hidden'; fr.srcdoc = html; document.body.appendChild(fr);
    for (let i = 0; i < 100 && !(fr.contentDocument && fr.contentDocument.readyState === 'complete' && fr.contentDocument.querySelector('#panel')); i++) await sleep(50); await sleep(100);
    const fd = fr.contentDocument, fw = fr.contentWindow, f$ = s => fd.querySelector(s), fcs = (s, p) => f$(s) ? fw.getComputedStyle(f$(s))[p] : '';
    ok('client page: the CSS of the editor is there (rows, tiles, milestones, use cases)', fcs('.wl-row', 'display') === 'grid' && fcs('.glance', 'display') === 'flex' && fcs('.msl', 'position') === 'relative' && fcs('.ucr', 'display') === 'grid' && fcs('.wl', 'list-style-type') !== 'disc');
    ok('client page: the sections are split into cards over the page picture, as in the editor', fd.documentElement.dataset.dash === 'slim' && fcs('#v-dashboard main', 'backgroundColor') === 'rgba(0, 0, 0, 0)' && fcs('#v-dashboard main > section', 'backgroundColor') === 'rgb(255, 255, 255)' && fw.getComputedStyle(fd.body, '::before').position === 'fixed');
    ok('client page: no editing left on it', !fd.querySelector('[contenteditable], [data-uc-eye], [data-uc-status], [data-uc-work], .uc-eye'));
    ok('client page: the use case status words line up', new Set([...fd.querySelectorAll('.ucr .uc-st')].map(e => Math.round(e.getBoundingClientRect().left))).size === 1);
    f$('.ucr').click(); ok('client page: a use case opens in place', f$('.ucr').classList.contains('open') && f$('.ucd').classList.contains('open'));
    f$('.ucr').click(); ok('client page: and closes again', !f$('.ucr.open') && !f$('.ucd.open'));
    f$('#v-dashboard [data-item]').click(); ok('client page: a work item opens its detail, the dashboard stays', f$('#panel').classList.contains('on') && f$('#v-dashboard').classList.contains('on') && /PDF-/.test(f$('#panel').textContent));
    fd.dispatchEvent(new fw.KeyboardEvent('keydown', { key: 'Escape' })); ok('client page: Esc closes the detail', !f$('#panel').classList.contains('on'));
    { const its = [...fd.querySelectorAll('#v-dashboard [data-item]')], md = el => el.dispatchEvent(new fw.MouseEvent('mousedown', { bubbles: true }));
      its[0].click(); md(its[1]); its[1].click(); ok('client page: with the detail open, a click on another work item moves it there', f$('#panel').classList.contains('on') && f$('#panel').textContent.includes(its[1].dataset.item));
      md(f$('#v-dashboard h2')); ok('client page: a click outside the detail closes it', !f$('#panel').classList.contains('on')); }
    f$('#v-dashboard [data-ms]').click(); ok('client page: a milestone opens its detail', f$('#panel').classList.contains('on') && /Milestone/.test(f$('#panel').textContent)); f$('#panel button').click();
    f$('#v-dashboard .wl-row .wl-main').click(); ok('client page: a single click on a work item row opens it', f$('#panel').classList.contains('on')); f$('#panel button').click();
    f$('[data-v=work]').click(); ok('client page: Work items tab', f$('#v-work').classList.contains('on') && !f$('#v-dashboard').classList.contains('on'));
    const wq = f$('#wq'); wq.value = 'zzqq-none'; wq.dispatchEvent(new fw.Event('input')); ok('client page: work item search', [...fd.querySelectorAll('#v-work .wl-row')].every(r => r.hidden)); wq.value = ''; wq.dispatchEvent(new fw.Event('input'));
    f$('[data-v=work]').click(); { const rows = () => [...fd.querySelectorAll('#v-work .wl-row')].filter(r => !r.hidden);
      const n0 = rows().length; f$('[data-ft=A]').click(); ok('client page: the type switch filters', rows().length > 0 && rows().length < n0 && rows().every(r => /-A-/.test(r.dataset.row)));
      const sel = f$('[data-cf=priority]'); sel.value = 'High'; sel.dispatchEvent(new fw.Event('change')); ok('client page: Filter by narrows it, with a chip', rows().every(r => item(r.dataset.row).priority === 'High') && !!f$('#cfChips .fchip'));
      f$('#cfClear').click(); ok('client page: Clear all brings every item back', rows().length === n0 && !f$('#cfChips .fchip')); }
    f$('[data-v=milestones]').click(); ok('client page: Milestones tab', f$('#v-milestones').classList.contains('on') && !!f$('#v-milestones .mv-strip'));
    { const r = f$('#v-milestones .msv'); r.querySelector('[data-msvb=cal]').click(); ok('client page: the Calendar view, by the discreet switcher', r.dataset.msv === 'cal' && fw.getComputedStyle(r.querySelector('.msv-cal')).display !== 'none' && fw.getComputedStyle(r.querySelector('.msv-line')).display === 'none' && !!r.querySelector('.cal-m:not([hidden]) .cal-d.today'));
      const t0 = r.querySelector('.cal-t').textContent; r.querySelector('[data-cal="1"]').click(); ok('client page: the next month', r.querySelector('.cal-t').textContent !== t0); r.querySelector('[data-cal="0"]').click(); ok('client page: back to today\'s month', r.querySelector('.cal-t').textContent === t0);
      r.querySelector('[data-msvb=line]').click(); ok('client page: and back to the timeline', r.dataset.msv === 'line'); }
    ok('client page: the milestone legend uses the client words', /Expected later/.test(f$('#v-milestones .mlg-p').textContent) && /Late/.test(f$('#v-milestones .mlg-p').textContent));
    f$('[data-v=dashboard]').click(); f$('[data-fig]:not([data-fig=health])')?.click(); ok('client page: a tile goes to the work items', f$('#v-work').classList.contains('on'));
    fr.remove();
    const pr = P(); window.ClarkDB.change('project', pr, { publish: { client: 'https://example.sharepoint.com/sites/demo/Client reports' } });
    click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60); $('#pubClient').checked = true; $('#pubClient').dispatchEvent(new Event('change')); $('#pubWord').checked = true; ok('the button says it sends', $('#pubGo').textContent.includes('send to the client'));
    $('#pubF').requestSubmit(); await sleep(2600); ok('published to the client folder too, and Word', P().published.slice(-1)[0].client.includes('sharepoint') && blobs === b0 + 3);
    ok('the bar says where it went', $('.rbar .state').textContent.includes('to the client'));
    const wo = window.open; let opened = false; window.open = () => { opened = true; return { document: { write() {}, close() {} } }; };
    click($('#meBtn')); await sleep(40); await menuPick('Preview the page in a new tab'); await sleep(300); window.open = wo; ok('preview in a new tab', opened);
  });

  await step('Back and Forward', async () => {
    const back = async () => { history.back(); await sleep(120); }, fwd = async () => { history.forward(); await sleep(120); };
    click($('.tab[data-view=dashboard]')); await sleep(80); click($('.tab[data-view=work]')); await sleep(80); ok('each page has its own address', /^#work&p=PDF$/.test(location.hash));
    await back(); ok('Back returns to the previous page', C.UI.view === 'dashboard'); await fwd(); ok('Forward goes again', C.UI.view === 'work');
    click($('tr[data-id] td')); await sleep(100); const id = C.UI.peek; ok('an open peek has its own address', !!id && location.hash.includes('item=' + id));
    await back(); ok('Back with a peek open closes the peek first', !C.UI.peek && C.UI.view === 'work'); await fwd(); ok('Forward opens it again', C.UI.peek === id);
    key(document.body, 'Escape'); await sleep(150); ok('closing the peek by hand takes the address back too', !C.UI.peek && !location.hash.includes('item='));
  });

  await step('tiles filter the work items', async () => {
    click($('.tab[data-view=dashboard]')); await sleep(80); { const g = $('.glance'), h = $('.glance .health-fig'), last = [...g.querySelectorAll('.fig')].at(-1); ok('At a glance: Project health fills the row and the other tiles sit at the right', Math.abs(last.getBoundingClientRect().right - g.getBoundingClientRect().right) < 2 && h.getBoundingClientRect().width > 400); }
    const back = async () => { click($('.tab[data-view=dashboard]')); await sleep(80); };
    await back(); click($('[data-fig=overdue]')); await sleep(80);
    ok('Overdue actions opens Work items filtered to what it counts', C.UI.view === 'work' && $$('tr[data-id]').length === +C.glanceData(P()).overdue.v && $$('tr[data-id]').every(r => item(r.dataset.id).type === 'A' && window.ClarkDB.days(item(r.dataset.id).due) < 0) && !!$('.fchip'));
    await back(); click($('[data-fig=risks]')); await sleep(80);
    ok('High risks and issues: the urgent and high ones', $$('tr[data-id]').length === +C.glanceData(P()).risks.v && $$('tr[data-id]').every(r => ['R', 'I'].includes(item(r.dataset.id).type) && ['Urgent', 'High'].includes(item(r.dataset.id).priority)));
    click($('#clearAll')); await sleep(60);
  });

  await step('work items', async () => {
    click($('.tab[data-view=work]')); await sleep(80); if ($('#clearAll')) { click($('#clearAll')); await sleep(60); }
    const all = $$('tr[data-id]').length; ok('open items listed', all === S().items.filter(x => x.code === 'PDF' && C.isOpen(x)).length, all);
    click($('.wbar .seg [data-type=R]')); await sleep(40); ok('type: risks and issues', $$('tr[data-id]').length > 0 && $$('tr[data-id]').every(r => /^[A-Z0-9]+-\d{3}$/.test(r.dataset.id)));
    click($('.wbar .seg [data-type=all]')); await sleep(40);
    ok('Group by replaces the workstream dropdown: groups by workstream at first', !$('#wsBtn') && /Workstream/.test($('#groupBtn').textContent) && $$('.group').some(g => g.dataset.ws === 'ws:Testing'));
    click($('#groupBtn')); await sleep(40); await menuPick('Owner'); ok('group by owner', $$('.group').length > 2 && $$('.group').every(g => g.dataset.ws.startsWith('owner:')));
    click($('#groupBtn')); await sleep(40); await menuPick('Workstream');
    click($('[data-fb=ws]')); await sleep(40); { const c = $('.menu input[value=Testing]'); c.checked = true; c.dispatchEvent(new Event('change')); } document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(80);
    ok('workstream is a filter now', $$('.group').length === 1 && $('.group').dataset.ws === 'ws:Testing'); click($('#clearAll')); await sleep(60);
    /* the board, as creaite's: columns, swimlanes, drag and Move to…, each one step with Undo */
    click($('[data-layout=board]')); await sleep(60); ok('the board icon shows the same items as cards', !!$('.board') && $$('[data-card]').length === $$('[data-card]').length && $$('[data-card]').length === S().items.filter(x => x.code === 'PDF' && C.isOpen(x)).length && !$('table.items'));
    click($('#groupBtn')); await sleep(40); await menuPick('Status'); ok('board: coloured state labels', $('.bcol[data-col=Delayed] .bcol-h').classList.contains('tone-a') && $('.bcol[data-col=Open] .bcol-h').classList.contains('tone-b')); ok('board grouped by status: a column per status', $$('.bcol').some(c => c.dataset.col === 'Delayed') && $$('.bcol').some(c => c.dataset.col === 'Pending'));
    { const x = item('PDF-A-019'), card = $('[data-card="PDF-A-019"]'), col = $('.bcol[data-col="Delayed"]'), dt = new DataTransfer();
      card.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt })); col.dispatchEvent(new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt })); col.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt })); await sleep(60);
      ok('drag a card to a column changes the item', x.status === 'Delayed' && !!$('.bcol[data-col="Delayed"] [data-card="PDF-A-019"]'));
      { const h = S().history.filter(r => r.id === 'PDF-A-019' && r.field === 'status').at(-1); ok('a board drag records "on the board", with from and to', !!h && h.how === window.ClarkDB.who('on the board') && h.from === 'Open' && h.to === 'Delayed', JSON.stringify(h)); } await undo(); ok('board move undo', x.status === 'Open'); }
    { const dt = new DataTransfer(), card = $('[data-card="PDF-D-008"]'), col = $('.bcol[data-col="Delayed"]'); card.dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt })); col.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt })); await sleep(60);
      ok('a move a type cannot take is refused', item('PDF-D-008').status === 'Pending' && /can't be Delayed/.test($('#toastMsg').textContent)); }
    click($('#groupBtn')); await sleep(40); await menuPick('Priority');
    click($('[data-mvto="PDF-A-019"]')); await sleep(40); await menuPick('Urgent'); await sleep(60); ok('Move to… from the keyboard menu', item('PDF-A-019').priority === 'Urgent'); await undo();
    click($('#bLane')); await sleep(40); await menuPick('Workstream'); ok('swimlanes by workstream', $$('.blane-h').length >= 2);
    { const x = item('PDF-A-019'), w0 = x.ws, lane = $$('.bcol').find(c => c.dataset.lane !== w0 && c.dataset.col === 'Low'), dt = new DataTransfer(); $('[data-card="PDF-A-019"]').dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt })); lane.dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt })); await sleep(60);
      ok('across a lane and a column: both change, in one step', x.priority === 'Low' && x.ws === lane.dataset.lane); await undo(); ok('and one Undo puts both back', x.priority === 'High' && x.ws === w0); }
    click($('#bLane')); await sleep(40); await menuPick('None');
    click($('#groupBtn')); await sleep(40); await menuPick('Due');
    { const dt = new DataTransfer(); $('[data-card="PDF-A-019"]').dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt })); const od = $('.bcol[data-col=overdue]'); const ev = new DragEvent('dragover', { bubbles: true, cancelable: true, dataTransfer: dt }); od.dispatchEvent(ev); ok('Overdue is not a drop target', !ev.defaultPrevented);
      $('.bcol[data-col=next]').dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt })); await sleep(60); const past = $('.menu [data-cp="' + window.ClarkDB.addDays(window.ClarkDB.TODAY, -1) + '"]'); ok('a move on Due asks for a date, never a past one', !!$('.menu .cp') && (!past || past.disabled)); const pickD = $('.menu .cp-g button.at').dataset.cp; key(document.body, 'Enter'); await sleep(60); ok('the date is set', item('PDF-A-019').due === pickD); await undo(); }
    { const hd = $('.bcol[data-col=week] .bcrz'); hd.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); hd.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowRight', bubbles: true })); await sleep(30);
      ok('a column widens from its edge, remembered', C.store.get('bw').due.week === 304 && $('.bcol[data-col=week]').getBoundingClientRect().width === 304);
      hd.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })); await sleep(30); ok('a double-click puts the width back', !(C.store.get('bw').due || {}).week); }
    { const h = $('.bcol[data-col=later] .bcol-h'); h.dispatchEvent(new KeyboardEvent('keydown', { key: 'ArrowLeft', altKey: true, bubbles: true })); await sleep(60);
      ok('Alt+← moves a column, and the order is remembered', $$('.bcol').map(c => c.dataset.col).join() === 'overdue,week,later,next,none' && C.store.get('bord').due.join() === 'overdue,week,later,next,none');
      const dt = new DataTransfer(); $('.bcol[data-col=none] .bcol-h').dispatchEvent(new DragEvent('dragstart', { bubbles: true, dataTransfer: dt })); $('.bcol[data-col=overdue]').dispatchEvent(new DragEvent('drop', { bubbles: true, cancelable: true, dataTransfer: dt })); await sleep(60);
      ok('drag a heading onto another column to move it', $$('.bcol').map(c => c.dataset.col)[0] === 'none'); C.store.set('bord', {}); }
    ok('the columns are white, not grey', getComputedStyle($('.bcol')).backgroundColor === 'rgb(255, 255, 255)');
    click($('.bcol[data-col=later] .bcol-h')); await sleep(40); ok('a column collapses and is remembered', $('.bcol[data-col=later]').classList.contains('shut') && C.store.get('bshut').includes('due:later')); click($('.bcol[data-col=later] .bcol-h')); await sleep(40);
    click($('[data-card="PDF-A-019"]')); await sleep(80); ok('a card opens its peek', $('#peek').classList.contains('on') && $('#peek .pk-meta').textContent.includes('PDF-A-019')); key(document.body, 'Escape'); await sleep(40);
    { const b = $('.board'); b.scrollTop = b.scrollHeight; await sleep(40); ok('board: the column headings stay in view as it scrolls', Math.abs($('.bcol-h').getBoundingClientRect().top - b.getBoundingClientRect().top) < 2 || b.scrollHeight <= b.clientHeight); b.scrollTop = 0; }
    click($('#bFull')); await sleep(40); ok('the board fills the window, with its filters, picture and colours', document.body.classList.contains('bfull') && getComputedStyle($('.top')).display === 'none' && !!$('.fbar') && getComputedStyle(document.body, '::before').position === 'fixed'); click($('[data-card]')); await sleep(80); ok('full screen: a card opens the peek, with Sneak peek', $('#peek').classList.contains('on') && !!$('#pkSneak')); key(document.body, 'Escape'); await sleep(60); key(document.body, 'Escape'); await sleep(60); ok('Esc brings it back', !document.body.classList.contains('bfull'));
    click($('#groupBtn')); await sleep(40); await menuPick('Workstream'); click($('[data-layout=table]')); await sleep(60); ok('back to the table, remembered', !!$('table.items') && C.store.get('wf').layout === 'table');
    click($('[data-fb=due]')); await sleep(40); const c = $('.menu input[value=overdue]'); c.checked = true; c.dispatchEvent(new Event('change')); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(80);
    ok('filter: due is overdue', $$('tr[data-id]').length >= 2 && $$('tr[data-id]').every(r => C.dueWords(item(r.dataset.id).due).includes('late') || C.dueWords(item(r.dataset.id).due) === 'Yesterday'));
    ok('active filter chip shown', !!$('.fchip'));
    click($('[data-fb=due]')); await sleep(40); click($('.menu [data-not="1"]')); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(80); ok('filter: is not', $$('tr[data-id]').every(r => !(item(r.dataset.id).due && window.ClarkDB.days(item(r.dataset.id).due) < 0)));
    click($('[data-fx=due]')); await sleep(60); ok('remove the chip', !$('.fchip'));
    click($('[data-fb=owner]')); await sleep(40); const o = $('.menu input[value="Priya Nair"]'); o.checked = true; o.dispatchEvent(new Event('change')); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(80); ok('filter: owner', $$('tr[data-id]').every(r => item(r.dataset.id).owner === 'Priya Nair'));
    click($('#clearAll')); await sleep(60); ok('clear all', !$('.fchip') && $$('tr[data-id]').length === all);
    click($('[data-show=closed]')); await sleep(60); ok('closed: the switch shows closed items only', $$('tr[data-id]').length > 0 && $$('tr[data-id]').every(r => !C.isOpen(item(r.dataset.id))));
    ok('the switch counts open, closed and all', ['open', 'closed', 'all'].every(k => /^\d+$/.test($(`[data-show=${k}] em`).textContent)) && +$('[data-show=all] em').textContent === S().items.filter(x => x.code === 'PDF').length);
    click($('[data-show=open]')); await sleep(60);
    ok('option A: no saved-view pills, no Open dropdown, no "hidden by" line', !$('[data-wv]') && !$('#showBtn') && !/hidden by/.test($('#main').textContent));
    /* a second filter opens with one click while the first is open: the buttons survive the redraw */
    const fb = $('[data-fb=priority]'); click($('[data-fb=status]')); await sleep(40);
    fb.dispatchEvent(new MouseEvent('mousedown', { bubbles: true, cancelable: true })); await sleep(20); fb.dispatchEvent(new MouseEvent('mouseup', { bubbles: true })); await sleep(10);
    ok('the filter button under the pointer survives the first filter closing', fb.isConnected && $('[data-fb=priority]') === fb);
    click(fb); await sleep(40); ok('so its click opens it first time', !!$('.menu input[value=High]')); click(fb); await sleep(40); ok('a second click on the same filter closes it', !$('.menu input[value=High]')); click(fb); await sleep(40); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(60);
    click($('[data-fb=client]')); await sleep(40); const cv = $('.menu input[value=yes]'); cv.checked = true; cv.dispatchEvent(new Event('change')); document.body.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(80);
    ok('an active filter gets its dot', $('[data-fb=client]').classList.contains('on') && $$('tr[data-id]').every(r => item(r.dataset.id).client)); click($('#clearAll')); await sleep(60);
    const q = $('#q'); q.focus(); q.value = 'testers'; q.dispatchEvent(new Event('input')); await sleep(60); ok('search, and the box keeps the focus', $$('tr[data-id]').length === 1 && document.activeElement === q); q.value = ''; $('#q').value = ''; $('#q').dispatchEvent(new Event('input')); await sleep(60);
    click($('.ghead')); await sleep(40); ok('group closes', !$('.group').classList.contains('open')); click($('.ghead')); await sleep(40);
    { click($('[data-pick="PDF-A-016"][data-prop=priority]')); await sleep(40); await menuPick('Urgent'); await sleep(60); ok('the table: priority changes in place from a picker', item('PDF-A-016').priority === 'Urgent' && !$('#peek').classList.contains('on'));
      { const h = S().history.filter(r => r.id === 'PDF-A-016' && r.field === 'priority').at(-1); ok('a table-cell change records "in the table", with from and to', !!h && h.how === window.ClarkDB.who('in the table') && h.from === 'Medium' && h.to === 'Urgent' && /^[+-]\d\d:\d\d$/.test(h.tz) && /^\d{4}-\d\d-\d\d \d\d:\d\d$/.test(h.at), JSON.stringify(h)); }
      await undo();
      { const h = S().history.filter(r => r.id === 'PDF-A-016' && r.field === 'priority').at(-1); ok('undo writes a row for the field, with the values and where', !!h && h.how === window.ClarkDB.who('undo') && h.from === 'Urgent' && h.to === 'Medium' && /^Undone/.test(h.text) && h.field !== '*', JSON.stringify(h)); }
      click($('[data-pick="PDF-A-016"][data-prop=status]')); await sleep(40); await menuPick('Delayed'); await sleep(60); ok('the table: status in place', item('PDF-A-016').status === 'Delayed'); await undo();
      click($('[data-pick="PDF-A-016"][data-prop=owner]')); await sleep(40); ok('the table: owner opens the people picker', !!$('#ownIn')); key($('#ownIn'), 'Escape'); await sleep(30); }
    const x = item('PDF-A-016'), was = x.client; click($('[data-weye="PDF-A-016"]')); await sleep(60); ok('eye inline, without the peek', x.client === !was && !$('#peek').classList.contains('on')); await undo(); ok('eye undo', x.client === was);
    const rx = spyX(); click($('#expBtn')); await sleep(40); rx(); ok('export: a sheet for each, and a History sheet', writes.at(-1)?.sheets.join() === 'Actions,Risks and issues,Decisions,Milestones,Use cases,History', writes.at(-1)?.sheets.join());
    { const hs = XLSX.utils.sheet_to_json(writes.at(-1).wb.Sheets.History, { header: 1 }); ok('the History sheet: When, Who, How, Item, Field, From, To, in plain values', hs[0].join() === 'When,Who,How,Item,Field,From,To' && hs.slice(1).some(r => /^PDF-A-016/.test(r[3]) && r[4] === 'Priority' && r[5] === 'Medium' && r[6] === 'Urgent' && r[2] === 'in the table' && r[1] === window.ClarkDB.who().split(',')[0] && /^\d\d-\d\d-\d{4} \d\d:\d\d$/.test(r[0])), JSON.stringify(hs.slice(1, 3))); }
    ok('Add follows the type switch, as an icon that shows its words on hover', $('#newBtn').classList.contains('addb') && $('#newBtn').getAttribute('aria-label') === 'Add item'); ok('import and export are icons with tooltips', !$('#impBtn').textContent.trim() && $('#impBtn').dataset.tip === 'Import from Excel' && $('#expBtn').dataset.tip === 'Export to Excel');
    click($('#newBtn')); await sleep(40); await menuPick('Add risk'); await sleep(100); const nr = S().items.at(-1); ok('a new item is client-visible by default', nr.client === true); ok('new item opens in the peek', nr.type === 'R' && $('#peek').classList.contains('on') && document.activeElement.id === 'pkTitle');
    ok('a new item in the table records where', S().history.some(h => h.id === nr.id && h.field === '+' && h.how === window.ClarkDB.who('in the table')));
    await undo(); ok('undoing a create writes "Creation undone"', !S().items.includes(nr) && S().history.some(h => h.id === nr.id && h.field === '-' && h.text === 'Creation undone' && h.how === window.ClarkDB.who('undo'))); key(document.body, 'Escape'); await sleep(40);
  });

  await step('import from Excel', async () => {
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['ID', 'Type', 'Workstream', 'Title', 'Owner', 'Due', 'Status', 'Rating', 'Use case'], ['PDF-A-016', 'Action', 'Data platform', 'Load the second source system', 'Jo Ellis', '15-12-2026', 'In progress', '', '2.1'], ['', 'Risk', 'Vendor', 'Supplier capacity is limited', 'Sam Rivers', '01-12-2026', 'Open', 'Red', ''], ['', 'Action', '', '', '', '', '', '', '']]), 'Actions');
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['ID', 'Milestone', 'Workstream', 'Agreed', 'Forecast'], ['', 'Board review', 'Testing', '20-12-2026', '05-01-2027'], ['PDF-M-006', 'Testing signed off', 'Testing', '10-01-2027', '']]), 'Milestones');
    XLSX.utils.book_append_sheet(wb, XLSX.utils.aoa_to_sheet([['ID', 'Use case', 'Status', 'Headline'], ['4.2', 'Automated summaries', 'Flag', 'Waiting on data access'], ['1.2', 'Assisted invoice matching', 'Done', 'Live']]), 'Use cases');
    const buf = XLSX.write(wb, { type: 'array', bookType: 'xlsx' });
    click($('#impBtn')); await sleep(60); ok('import dialog', $('#dlg').open);
    const dt = new DataTransfer(); dt.items.add(new File([buf], 'week import.xlsx')); const fi = $('#fileIn'); fi.files = dt.files; fi.dispatchEvent(new Event('change'));
    for (let i = 0; i < 40 && !$('#impF'); i++) await sleep(100);
    ok('check shows what changes', /3\s*new/.test($('#dlg').textContent) && /3\s*updated/.test($('#dlg').textContent) && /1\s*skipped/.test($('#dlg').textContent), $('.stat')?.textContent);
    const n0 = S().items.length, m0 = S().milestones.length, u0 = S().usecases.length; $('#impF').requestSubmit(); await sleep(120);
    ok('import adds and updates items', S().items.length === n0 + 1 && item('PDF-A-016').owner === 'Jo Ellis' && item('PDF-A-016').uc === '2.1' && P().ws.includes('Vendor'));
    const sup = S().items.find(y => y.title === 'Supplier capacity is limited'); ok('an old status word imports as creaite\'s, and a new risk takes the shared series', item('PDF-A-016').status === 'Open' && sup && /^PDF-\d{3}$/.test(sup.id) && sup.type === 'R' && S().items.filter(y => y !== sup && y.code === 'PDF' && (y.type === 'R' || y.type === 'I')).every(y => +y.id.split('-').pop() < +sup.id.split('-').pop()), `${item('PDF-A-016').status} ${sup && sup.id} ${sup && sup.type}`);
    ok('import milestones', S().milestones.length === m0 + 1 && S().milestones.some(m => m.name === 'Board review' && m.forecast === '2027-01-05'));
    ok('import use cases', S().usecases.length === u0 + 1 && S().usecases.find(u => u.key === 'PDF/1.2').status === 'Done');
    ok('an Excel import row says the file name, with the person first', S().history.some(h => h.id === 'PDF-A-016' && h.field === 'owner' && h.how === window.ClarkDB.who('by Excel import (week import.xlsx)')) && S().history.some(h => h.field === '+' && h.how === 'You, by Excel import (week import.xlsx)'));
    await undo(); ok('import undo', S().items.length === n0 && item('PDF-A-016').owner === 'Ravi Mehta' && S().milestones.length === m0 && S().usecases.find(u => u.key === 'PDF/1.2').status === 'On track');
  });

  await step('item peek', async () => {
    click($('tr[data-id="PDF-A-012"] td')); await sleep(100); ok('row opens the peek', $('#peek').classList.contains('on') && $('#pkTitle').textContent.includes('handover'));
    ok('peek shows the warning and fixes', !!$('.pk-warn') && $$('[data-move]').length === 2);
    click($('[data-prop=status]')); await sleep(40); await menuPick('Delayed'); ok('status picker', item('PDF-A-012').status === 'Delayed' && $('#pkFeed').textContent.includes('Open → Delayed'));
    click($('[data-prop=priority]')); await sleep(40); await menuPick('Urgent'); ok('priority picker', item('PDF-A-012').priority === 'Urgent');
    click($('[data-prop=owner]')); await sleep(40); const oi = $('#ownIn'); oi.value = 'Jo Ellis'; key(oi, 'Enter'); await sleep(60); ok('owner picker', item('PDF-A-012').owner === 'Jo Ellis');
    click($('[data-prop=due]')); await sleep(40); click($$('.menu [data-cpq]')[1]); await sleep(60); ok('due picker', item('PDF-A-012').due === window.ClarkDB.addDays(window.ClarkDB.TODAY, 1));
    const t = $('#pkTitle'); t.focus(); t.textContent = 'Confirm the handover date'; t.dispatchEvent(new Event('blur')); await sleep(60); ok('title edit', item('PDF-A-012').title === 'Confirm the handover date');
    { click($('.pk-tabs [data-tab=activity]')); await sleep(40); const tx = $('#pkFeed').textContent.replace(/\s+/g, ' ');
      ok('Activity: the field by its plain name, with from → to formatted as dates', /Due date \d\d-\d\d-\d{4} → \d\d-\d\d-\d{4}/.test(tx) && !/\bdue\b \d{4}-/.test(tx), tx.slice(0, 200));
      ok('Activity: status as words, owner as names, and the person, how and local time first', /Status Open → Delayed/.test(tx) && /Owner Sam Rivers → Jo Ellis/.test(tx) && /You, in the peek · \d\d-\d\d-\d{4} \d\d:\d\d/.test(tx), tx.slice(0, 200));
      ok('Activity: newest first', $$('#pkFeed .feed > li')[0].textContent.includes('Title') && !!$('#pkFeed .pk-filt')); }
    click($('#pkUpd')); await sleep(120); const upm = $('#pkUpd .ProseMirror'); ok('latest update edits in place', !!upm); await typeIn(upm, ' Supplier answered.'); $('#peek .pk-meta').dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(120); ok('latest update saved', item('PDF-A-012').update.includes('Supplier answered.'));
    click($('#pkDraft')); await sleep(80); ok('draft button writes a draft, with Undo', C.plain(item('PDF-A-012').update).length > 10 && !$('#toastUndo').hidden);
    { const h = S().history.filter(r => r.id === 'PDF-A-012' && r.field === 'update').at(-1); ok('a draft records "with a draft", and keeps the whole text', h.how === window.ClarkDB.who('with a draft') && h.from.includes('Supplier answered') && h.to.length > 10);
      const rows = () => $$('#pkFeed .feed > li').map(l => l.textContent.replace(/\s+/g, ' ')), allN = rows().length;
      ok('Activity: a latest update shows a compact word diff', !!$('#pkFeed .hd ins') && !!$('#pkFeed .hd del'));
      click($('[data-hf=comments]')); await sleep(30); const cm = rows(); ok('the filter: Comments and updates shows only updates', cm.length > 0 && cm.length < allN && cm.every(r => /Latest update/.test(r)));
      click($('[data-hf=changes]')); await sleep(30); const chg = rows(); ok('the filter: Changes leaves the updates out', chg.length > 0 && chg.every(r => !/Latest update/.test(r)) && chg.some(r => /Status/.test(r)) && chg.length + cm.length === allN);
      click($('[data-hf=all]')); await sleep(30); ok('the filter: All shows both again', rows().length === allN && $('[data-hf=all]').getAttribute('aria-pressed') === 'true'); }
    const ms = $('#pkMs'); ms.value = 'PDF-M-004'; ms.dispatchEvent(new Event('change')); await sleep(60); ok('milestone link', item('PDF-A-012').ms === 'PDF-M-004');
    const uc = $('#pkUc'); uc.value = '1.5'; uc.dispatchEvent(new Event('change')); await sleep(60); ok('use case link', item('PDF-A-012').uc === '1.5');
    click($('#pkEye')); await sleep(60); ok('eye in the peek', item('PDF-A-012').client === false); click($('#pkEye')); await sleep(60);
    click($$('.pk-tabs button')[2]); await sleep(40); ok('Updates tab', /Latest update/.test($('#pkFeed').textContent));
    { click($('#pkMail')); await sleep(80); const d = $('dialog[open]');
      ok('Draft email from the peek: a chase, written in plain code', !!d && /Draft email/.test(d.textContent) && /Good (morning|afternoon|evening) /.test($('#mlPrev').textContent) && /PDF-A-012/.test($('#mlPrev').textContent) && /Update request|Reminder|Reply needed/.test($('#mlSub').value) && !/hope you|holding up|Action needed/i.test($('#mlPrev').textContent + $('#mlSub').value));
      ok('the email is drawn for Outlook: inline styles, no classes', !$('#mlPrev').querySelector('[class]') && !!$('#mlPrev td[style]'));
      click($('#mlSent')); await sleep(80); ok('I sent it records the chase in history, with Undo', S().history.some(h => h.id === 'PDF-A-012' && h.field === 'chase') && !$('#toastUndo').hidden); await undo(); }
    const id0 = $('.pk-meta').textContent; click($('#pkNext')); await sleep(80); ok('next item', $('.pk-meta').textContent !== id0); click($('#pkPrev')); await sleep(80); ok('previous item', $('.pk-meta').textContent === id0);
    click($('#pkWide')); await sleep(40); ok('across the whole screen', $('#peek').classList.contains('wide') && C.store.get('peekWide') === true);
    click($('#pkWide')); await sleep(40); ok('back to the user\'s width', !$('#peek').classList.contains('wide'));
    C.store.set('peekW', 700); click($('#pkNext')); await sleep(80); ok('width preference kept', getComputedStyle($('#peek')).getPropertyValue('--peek-w').trim() === '700px'); $('.resize').dispatchEvent(new MouseEvent('dblclick', { bubbles: true })); await sleep(40); ok('double-click resets the width', C.store.get('peekW') === 0);
    click($('#pkMore')); await sleep(40); await menuPick('Duplicate'); await sleep(80); const dup = S().items.at(-1); ok('duplicate', dup.title.endsWith('(copy)') && $('.pk-meta').textContent.includes(dup.id));
    click($('#pkMore')); await sleep(40); await menuPick('Delete'); ok('delete', !S().items.includes(dup) && !$('#peek').classList.contains('on'));
    click($('tr[data-id="PDF-A-019"] td')); await sleep(80); $('.head h1').dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(40); ok('click outside closes the peek', !$('#peek').classList.contains('on'));
    click($('tr[data-id="PDF-A-019"] td')); await sleep(80); { const t = $('tr[data-id="PDF-A-018"] td'); t.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); click(t); await sleep(80); ok('with the peek open, a click on another item moves the peek to it', $('#peek').classList.contains('on') && $('#peek .pk-meta').textContent.includes('PDF-A-018')); } key(document.body, 'Escape'); await sleep(40);
  });

  await step('sneak peek', async () => {
    click($('tr[data-id="PDF-A-019"] td')); await sleep(80); document.activeElement.blur();
    key(document.body, '/'); key(document.body, '/'); await sleep(80); ok('"//" opens Sneak peek', $('#sneak').classList.contains('on') && document.activeElement.id === 'snIn' && !$('#ask').classList.contains('on'));
    const i = $('#snIn'); i.value = 'move to friday owner Jo low priority'; i.dispatchEvent(new Event('input')); await sleep(260);
    ok('reads the words into changes', $$('.sn-ch').length === 3, $$('.sn-ch').length);
    key(i, 'Enter', { shiftKey: true }); await sleep(120); const x = item('PDF-A-019');
    ok('Shift+Enter saves at once', x.owner === 'Jo Ellis' && x.priority === 'Low' && !$('#sneak').classList.contains('on'));
    ok('history says "in words"', S().history.some(h => h.id === 'PDF-A-019' && h.how === window.ClarkDB.who('in words')));
    ok('changed fields flash', $$('#peek .flashf').length >= 2);
    await undo(); ok('sneak undo', item('PDF-A-019').owner === 'Priya Nair');
    { const us = S().history.filter(h => h.id === 'PDF-A-019' && /^Undone/.test(h.text)).slice(-3); ok('undoing a step of three changes writes a row for each field, with the values', us.length === 3 && ['owner', 'priority', 'due'].every(f => us.some(h => h.field === f && h.from !== h.to && h.how === window.ClarkDB.who('undo'))) && us.find(h => h.field === 'owner').from === 'Jo Ellis' && us.find(h => h.field === 'owner').to === 'Priya Nair', JSON.stringify(us.map(h => h.field + ':' + h.from + '>' + h.to))); }
    click($('#pkSneak')); await sleep(60); const j = $('#snIn'); j.value = 'owner Zed'; j.dispatchEvent(new Event('input')); await sleep(260); ok('a new name is offered', $('.sn-ch')?.textContent.includes('Zed'));
    key(j, 'Escape'); await sleep(40); ok('Esc closes Sneak peek, peek stays', !$('#sneak').classList.contains('on') && $('#peek').classList.contains('on'));
    key(document.body, 'Escape'); await sleep(40);
  });

  await step('milestones page and peek', async () => {
    click($('.tab[data-view=milestones]')); await sleep(80); ok('milestones plan', !!$('.mv-wrap') && $$('.msl-row').length === 5); click($('[data-msall]')); await sleep(60);
    { click($('[data-msvb=cal]')); await sleep(60); const r = $('.msv'); ok('milestones: Calendar view, remembered', r.dataset.msv === 'cal' && C.store.get('msv.page') === 'cal' && !!$('.cal-m:not([hidden]) .cal-d.today'));
      ok('calendar: a slipped milestone also shows where it is expected', $$('.cal-ms.ghost').length >= 1 || $$('.cal-m .cal-ms.ghost').length >= 1);
      const chip = $('.cal-m:not([hidden]) .cal-ms:not(.ghost)'); click(chip); await sleep(80); ok('calendar: a milestone opens its peek', $('#peek').classList.contains('on')); key(document.body, 'Escape'); await sleep(40);
      { const b = $('.msv .mlg-b'); b.focus(); await sleep(250); ok('milestones: a discreet Legend under the view shows every mark on focus', getComputedStyle($('.msv .mlg-p')).visibility === 'visible' && $$('.msv .mlg-p li').length === 8 && /Forecast/.test($('.msv .mlg-p').textContent)); b.blur(); }
      ok('calendar: Month by default, with Week and Quarter switches', $('.cal').dataset.calv === 'month' && $$('[data-calv-b]').length === 3);
      click($('[data-calv-b=week]')); await sleep(40); { const w = $('.cal-m:not([hidden])'); ok('Week: the seven days of this week, today marked', w && w.dataset.mode === 'week' && w.querySelectorAll('.cal-d').length === 7 && !!w.querySelector('.cal-d.today') && /^Week of /.test($('.cal-t').textContent)); }
      click($('[data-cal="1"]')); await sleep(30); ok('Week: the next week', !$('.cal-m:not([hidden]) .cal-d.today')); click($('[data-cal="0"]')); await sleep(30);
      click($('[data-calv-b=quarter]')); await sleep(40); ok('Quarter: three months side by side, remembered', $('.cal-m:not([hidden])').dataset.mode === 'quarter' && $$('.cal-m:not([hidden]) .cal-g').length === 3 && /^Q\d \d{4}$/.test($('.cal-t').textContent) && C.store.get('msv.calv.page') === 'quarter');
      { const g = $('.cal-m:not([hidden]) [data-cal-goto]'), mo = g.dataset.calGoto; click(g); await sleep(40); ok('Quarter: a month\'s name opens that month', $('.cal-m:not([hidden])').dataset.mode === 'month' && $('.cal-m:not([hidden])').dataset.calM === mo); }
      click($('[data-calv-b=month]')); await sleep(40);
      click($('[data-msvb=line]')); await sleep(60); ok('milestones: back to the timeline', $('.msv').dataset.msv === 'line' && !!$('.mv-strip')); }
    click($('.msl-row[data-ms=PDF-M-004]')); await sleep(80);
    click($('.states [data-st="Forecast"]')); await sleep(60); ok('state: forecast', window.ClarkDB.msState(S().milestones.find(x => x.key === 'PDF/PDF-M-004')) === 'Forecast'); const m = S().milestones.find(x => x.key === 'PDF/PDF-M-004');
    click($('.states [data-st="At risk"]')); await sleep(60); ok('state: at risk', window.ClarkDB.msState(m) === 'At risk');
    click($('.states [data-st="On track"]')); await sleep(60); ok('state: on track', window.ClarkDB.msState(m) === 'On track');
    const fc = $('#mpFc'); fc.value = window.ClarkDB.addDays(m.agreed, 10); fc.dispatchEvent(new Event('change')); await sleep(60); ok('forecast later: slipped', window.ClarkDB.msState(m) === 'Slipped' && window.ClarkDB.slip(m) === 10);
    ok('a milestone change records where, with from and to', S().history.some(h => h.kind === 'ms' && h.id === m.id && h.field === 'forecast' && h.how === window.ClarkDB.who('in the peek') && h.to === m.forecast && h.from !== h.to));
    click($('#mpRebase')); await sleep(60); click($('#rbYes')); await sleep(60); ok('rebaseline keeps the original', m.agreed === m.forecast && m.original !== m.agreed);
    const pr = $('#mpPr'); pr.value = 40; pr.dispatchEvent(new Event('change')); await sleep(60); ok('progress', m.progress === 40);
    click($('#mpCl')); await sleep(60); ok('client switch', m.client === false); click($('#mpCl')); await sleep(60);
    click($('.states [data-st="Achieved"]')); await sleep(60); ok('achieved', window.ClarkDB.msState(m) === 'Achieved'); await undo();
    $('#snIn') || click($('#pkSneak')); await sleep(60); const i = $('#snIn'); i.value = 'progress 70% at risk'; i.dispatchEvent(new Event('input')); await sleep(260); key(i, 'Enter'); await sleep(100); ok('sneak peek on a milestone', m.progress === 70 && m.manual === 'At risk');
    click($('#pkMore')); await sleep(40); await menuPick('Delete milestone'); ok('delete milestone', !S().milestones.includes(m)); await undo(); ok('delete undo', S().milestones.includes(m));
    key(document.body, 'Escape'); await sleep(40);
    click($('[data-mv=move]')); await sleep(80); ok('Movement view', !!$('.mv-move') && $$('.mvrow').length >= 3);
    click($('.mvrow[data-msel=PDF-M-005]')); await sleep(60); ok('select a milestone', $('.mvrow.sel').dataset.msel === 'PDF-M-005');
    const n0 = S().items.length; click($('[data-dec=recover]')); await sleep(100); ok('add a recovery action, linked', S().items.length === n0 + 1 && S().items.at(-1).ms === 'PDF-M-005' && S().items.at(-1).type === 'A'); key(document.body, 'Escape'); await sleep(40);
    click($('[data-dec=escalate]')); await sleep(100); ok('escalate makes a pending decision', S().items.at(-1).type === 'D' && S().items.at(-1).status === 'Pending'); key(document.body, 'Escape'); await sleep(40);
    click($('[data-dec=hold]')); await sleep(60); ok('hold notes it', (S().milestones.find(x => x.key === 'PDF/PDF-M-005').note || '').includes('holding'));
    const nt = $('#mvNote'); nt.value = 'Waiting on the business.'; nt.dispatchEvent(new Event('change')); await sleep(60); ok('internal note', S().milestones.find(x => x.key === 'PDF/PDF-M-005').note === 'Waiting on the business.');
    click($('[data-mv=plan]')); await sleep(40);
    click($('#addMs')); await sleep(100); ok('add milestone opens it', $('#peek').classList.contains('on') && $('#pkTitle').textContent === 'New milestone'); key(document.body, 'Escape'); await sleep(40);
  });

  await step('ask clark', async () => {
    click($('#askBtn')); await sleep(60); ok('opens full height', $('#ask').classList.contains('on') && $('#ask').getBoundingClientRect().height >= innerHeight - 2);
    const rz = $('.ask-resize'); rz.dispatchEvent(new PointerEvent('pointerdown', { bubbles: true, clientX: innerWidth - 420, pointerId: 1 })); rz.dispatchEvent(new PointerEvent('pointermove', { bubbles: true, clientX: innerWidth - 700, pointerId: 1 })); rz.dispatchEvent(new PointerEvent('pointerup', { bubbles: true, clientX: innerWidth - 700, pointerId: 1 })); await sleep(40);
    ok('drag the edge to widen ask clark, kept', Math.round($('#ask').getBoundingClientRect().width) === 700 && C.store.get('askW') === 700);
    rz.dispatchEvent(new MouseEvent('dblclick', { bubbles: true })); await sleep(40); ok('double-click goes back to the usual width', C.store.get('askW') === 0 && Math.round($('#ask').getBoundingClientRect().width) <= 420);
    click($('#askNew')); await sleep(40);
    ok('the suggestion pills sit in one row', new Set($$('#askChips button').map(b => Math.round(b.getBoundingClientRect().top))).size === 1);
    const n = $$('#askLog .msg.bot').length; click($$('#askChips button')[0]); await sleep(150); ok('shows an office quip while working', !$('#askWork').hidden && $('#askWork .quip').textContent.endsWith('…'));
    ok('while it works the pills give way to the working line, above the box', $('#askChips').hidden && !$('#askWork').hidden && $('#askWork').getBoundingClientRect().bottom <= $('#askIn').getBoundingClientRect().top);
    await sleep(2800); ok('Check this report answers', $$('#askLog .msg.bot').length === n + 1 && /checked the report/.test($$('#askLog .msg.bot').at(-1).textContent));
    ok('with the answer the pills come back and the working line goes', !$('#askChips').hidden && $('#askWork').hidden);
    const answered = async k => { for (let i = 0; i < 80 && !($$('#askLog .msg.bot').length > k && $('#askWork').hidden); i++) await sleep(100); };
    for (const c of $$('#askChips button').slice(1)) { const k = $$('#askLog .msg.bot').length; click(c); await answered(k); ok('chip: ' + c.textContent, $$('#askLog .msg.bot').length === k + 1, `${k} to ${$$('#askLog .msg.bot').length}, working ${!$('#askWork').hidden}`); }
    const use = $$('#askLog [data-do=summary]').at(-1); if (!use) ok('the summary answer offers "Use it"', false, `project ${C.UI.code}; projects ${S().projects.map(p => p.code).join(',')}; items ${S().items.length}, PDF items ${S().items.filter(x => x.code === 'PDF').length}, milestones ${S().milestones.length}, use cases ${S().usecases.length}; view ${C.UI.view}`); click(use); await sleep(80); ok('ask clark writes the Summary, with Undo', P().report.sections.find(s => s.id === 'summary').html.includes('Data Platform Pilot is') && !$('#toastUndo').hidden);
    const ai = $('#askIn'), k0 = $$('#askLog .msg.bot').length; ai.value = 'draft an update for PDF-A-018'; key(ai, 'Enter'); await answered(k0); click($$('#askLog [data-do=update]').at(-1)); await sleep(80); ok('ask clark saves a latest update', item('PDF-A-018').update.length > 10 && S().history.some(h => h.id === 'PDF-A-018' && h.how === window.ClarkDB.who('via ask clark') && /^.+, via ask clark$/.test(h.how)));
    key($('#askIn'), 'Escape'); await sleep(40); ok('Esc closes it', !$('#ask').classList.contains('on'));
  });

  await step('settings', async () => {
    C.go('settings'); await sleep(60);
    ok('the page background is on every view', ['dashboard', 'work', 'milestones', 'settings'].every(v => { C.go(v); return getComputedStyle(document.body, '::before').content !== 'none'; }));
    C.go('dashboard'); await sleep(40); C.go('settings'); await sleep(40);
    ok('changing view never restarts the background (no jump), and it does not drift or loop (X11)', !document.getAnimations().some(a => a.animationName === 'drift') && !/drift/.test(getComputedStyle(document.body, '::before').animationName) && !document.getAnimations().some(a => a.effect && a.effect.target === document.body && a.effect.getTiming().iterations > 1));
    ok('profile: five fields', ['name', 'alias', 'email', 'phone', 'org'].every(k => $(`[data-pf=${k}]`)) && $('#pfEmail').type === 'email' && $('#pfPhone').type === 'tel');
    const pf = (id, v) => { $(id).value = v; $(id).dispatchEvent(new Event('change')); };
    pf('#pfName', 'Sam Taylor'); pf('#pfAlias', 'ST'); pf('#pfEmail', 'sam@example.com'); pf('#pfPhone', '+44 20 7946 0000'); pf('#pfOrg', 'Example Consulting'); await sleep(60);
    ok('profile saved', JSON.stringify(window.ClarkDB.S.profile) === JSON.stringify({ name: 'Sam Taylor', alias: 'ST', email: 'sam@example.com', phone: '+44 20 7946 0000', org: 'Example Consulting' }));
    pf('#pfEmail', 'not an email'); await sleep(40); ok('a bad email is not saved', window.ClarkDB.S.profile.email === 'sam@example.com');
    C.refresh(); await sleep(40); pf('#pfOrg', 'Other Org'); await sleep(40); await undo(); ok('profile change undo', window.ClarkDB.S.profile.org === 'Example Consulting' && $('#pfOrg').value === 'Example Consulting');
    await window.ClarkDB.flush(); const kept = await new Promise(res => { const r = indexedDB.open('clark-prototype'); r.onsuccess = () => { const q = r.result.transaction('meta').objectStore('meta').get('profile'); q.onsuccess = () => res(q.result); }; });
    ok('profile kept in the browser database', kept && kept.v.name === 'Sam Taylor');
    ok('the profile circle shows the initials', $('#meBtn').textContent.trim() === 'ST');
    const nx = { id: C.nextId('A'), code: C.P().code, type: 'A', ws: C.P().ws[0], title: 'Name test', owner: '', due: '', status: 'Open', priority: 'Medium', desc: '', update: '', client: false, clientText: '', ms: '', uc: '' };
    const un = window.ClarkDB.create('item', nx); ok('history uses the full name from the profile', S().history.at(-1).how === 'Sam Taylor, by hand'); un();
    click($('#npBtn')); await sleep(60); $('#pN').value = 'Finance System Upgrade'; $('#pN').dispatchEvent(new Event('input')); ok('code suggested', $('#pC').value === 'FSU'); $('#pW').value = 'Design, Build'; $('#pF').requestSubmit(); await sleep(100);
    ok('project created and opened', C.UI.code === 'FSU' && C.UI.view === 'work' && P().ws.join() === 'Design,Build');
    C.go('settings'); await sleep(60); click($('[data-pe=FSU]')); await sleep(60); $('#pN').value = 'Finance Upgrade'; $('#pF').requestSubmit(); await sleep(80); ok('project edited', P().name === 'Finance Upgrade');
    $('#pubC').value = 'https://example.sharepoint.com/sites/fin/Reports'; $('#pubC').dispatchEvent(new Event('change')); await sleep(60); ok('client publish folder saved', P().publish.client.includes('sites/fin'));
    $('#srcIn').value = '~/Projects/Finance/Minutes'; $('#srcF').requestSubmit(); await sleep(80); ok('source folder added', (P().sources || []).length === 1);
    click($('[data-sd="0"]')); await sleep(60); ok('source folder removed', (P().sources || []).length === 0);
    click($('[data-pa=FSU]')); await sleep(80); ok('project archived in one step (no confirm box), kept in the data, and no longer the open project', !$('dialog[open]') && S().projects.some(p => p.code === 'FSU' && p.archived) && C.UI.code !== 'FSU' && !$('[data-pa=FSU]'));
    await undo(); ok('project archive undo', S().projects.some(p => p.code === 'FSU' && !p.archived) && C.UI.code === 'FSU'); C.setProject('PDF'); await sleep(60);
  });

  await step('empty lines are kept', async () => {
    C.go('dashboard'); await sleep(80); const was = P().current, u = window.ClarkDB.change('project', P(), { current: '<p>One.</p><p></p><p></p><p>Two.</p>' }); C.refresh(); await sleep(60);
    const ps = $$('#sec-current .prose p'), gap = ps[3].getBoundingClientRect().top - ps[0].getBoundingClientRect().bottom;
    ok('blank lines from the editor show in View mode', ps.length === 4 && gap > 30, Math.round(gap)); u(); C.refresh(); await sleep(40);
  });

  await step('AI sign-in', async () => {
    C.store.set('aiConn', {}); C.store.set('aiModel', ''); C.go('settings'); await sleep(80);
    ok('one report layout: no Report layout card in Settings, and every project is Boxed (#46 in the backlog)', $$('.card h2').length > 3 && !$$('.card h2').some(h => /Report layout/.test(h.textContent)) && !$('[data-lay]') && window.ClarkDB.S.projects.every(p => C.layOf(p) === 'boxed'));
    ok('Settings › AI: Claude to connect, OpenAI in a later version (FR-63a)', $$('.ai-prov').length === 2 && !$('.ai-prov.on') && !$('[data-aicon=openai]') && /later version/.test($('.ai-prov.later').textContent) && /passages they send go to Claude/.test($('#aiset').textContent));
    click($('[data-aicon=claude]')); await sleep(60); ok('the connect box says the passages go to Claude', /passages ask clark and the AI menu send go to Claude/.test($('dialog[open]').textContent)); click($('[data-how="API key"]')); await sleep(20); $('#aiKey').value = 'short'; $('#aiF').requestSubmit(); await sleep(40); ok('a refused key keeps the box open and says why', $('dialog[open]') && /did not accept this key \(401\)/.test($('#aiMsg').textContent));
    $('#aiKey').value = 'sk-test-TESTONLY-0000'; $('#aiF').requestSubmit(); await sleep(80); ok('connected: its models are offered for ask clark', !!$('.ai-prov.on') && $$('#aiModel option').length === 3 && !JSON.stringify(C.store.get('aiConn')).includes('TESTONLY'));
    click($('[data-aidisc=claude]')); await sleep(60); ok('Disconnect takes its models out', !$('.ai-prov.on') && /Connect Claude first/.test($('#aiModel').textContent));
    click($('[data-aicon=claude]')); await sleep(60); click($('[data-how="Claude subscription"]')); await sleep(20); $('#aiF').requestSubmit(); await sleep(80); ok('Claude by subscription, with Opus recommended', $$('.ai-prov.on').length === 1 && /Opus 5.5 \(recommended\)/.test($('#aiModel').textContent));
    C.store.set('aiConn', {}); C.store.set('aiModel', '');
  });

  await step('clark version and updates', async () => {
    C.store.set('upd', {}); C.go('settings'); await sleep(80);
    const put = name => { const dt = new DataTransfer(); dt.items.add(new File(['x'], name)); $('#updPick').files = dt.files; $('#updPick').dispatchEvent(new Event('change')); };
    ok('Settings › clark version and updates: the card, Installed clark 0.1.0, Up to date', !!$('#update') && $('#update h2').textContent === 'clark version and updates' && $('#updVer').textContent === 'clark 0.1.0' && /Up to date/.test($('#update').textContent) && !$('#updReview') && !$('#updLast'));
    ok('the card says how it works for real (checksums, file by file) and the file picker takes .zip', /checked file by file against its list of checksums before anything changes/.test($('#update').textContent) && $('#updPick').accept === '.zip' && !/Prototype/.test($('#update').textContent));
    put('clark-main.zip'); await sleep(30);
    ok('a zip that is not a clark release is refused with a plain message', $('#updMsg').textContent === "That isn't a clark release. Download clark-X.Y.Z.zip from the release page, not the source code zip." && $('#updMsg').classList.contains('bad') && !$('dialog[open]'));
    put('clark-0.1.0.zip'); await sleep(30); ok('a release that is not newer is refused', /not newer than the installed clark 0\.1\.0/.test($('#updMsg').textContent) && !$('dialog[open]'));
    put('clark-0.3.0.zip'); await sleep(60); ok('a right-named zip opens the review for its version', /0\.1\.0 → 0\.3\.0/.test($('dialog[open]').textContent) && !$('#updMsg').textContent); click($('#updCancel')); await sleep(60);
    ok('Cancel in the review changes nothing', C.version() === '0.1.0' && !$('dialog[open]'));
    click($('#updSim')); await sleep(60);
    ok('Simulate a new release: Update shows Review 0.2.0', $('#updReview').textContent === 'Review 0.2.0' && !$('#updNone') && C.version() === '0.1.0');
    click($('#updReview')); await sleep(60);
    const dg = $('dialog[open]').textContent, notes = $$('dialog[open] .upd-notes li');
    ok('the review: version change, release date, notes, files, what is kept, backup and roll back', /0\.1\.0 → 0\.2\.0/.test(dg) && /Released \d\d-\d\d-\d{4}/.test(dg) && notes.length === 3 && /Copy the notes/.test(dg) && /\d+ files replaced, \d+ added/.test(dg) && /Your projects, settings and published reports are kept/.test(dg) && /Everything is backed up first, and if a step fails clark puts the old version back/.test(dg));
    ok('the review ends in Cancel and Install clark 0.2.0', $('#updCancel').textContent === 'Cancel' && $('#updGo').textContent === 'Install clark 0.2.0');
    let copied = ''; Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { copied = t; } }, configurable: true });
    click($('#updNotes')); await sleep(40); ok('Copy the notes puts the notes on the clipboard', copied.includes(notes[0].textContent) && /Notes copied/.test($('#toastMsg').textContent));
    click($('#updGo')); await sleep(30); ok('Install shows a working state', $('#updGo').textContent === 'Installing…' && $('#updGo').disabled);
    for (let i = 0; i < 30 && $('dialog[open]'); i++) await sleep(100);
    ok('installed: the Installed row shows 0.2.0 and the toast says restart', !$('dialog[open]') && $('#updVer').textContent === 'clark 0.2.0' && C.version() === '0.2.0' && C.store.get('upd').ver === '0.2.0' && $('#toastMsg').textContent === 'Prototype: clark 0.2.0 is installed. Restart clark to finish.' && !!$('#updNone'));
    ok('Last update: 0.1.0 → 0.2.0 with the local date and time', /^0\.1\.0 → 0\.2\.0, \d\d-\d\d-\d{4} \d\d:\d\d$/.test($('#updLast').textContent) && $('#updUndo').textContent === 'Undo update');
    ok('diagnostics report the new version', /Version: clark 0\.2\.0/.test(C.diagText()));
    click($('#updUndo')); await sleep(40);
    ok('Undo update: the first click only arms it (Confirm undo)', $('#updUndo').textContent === 'Confirm undo' && C.version() === '0.2.0');
    click($('#updUndo')); await sleep(60);
    ok('the second click undoes it: back to 0.1.0, no Last update row', C.version() === '0.1.0' && $('#updVer').textContent === 'clark 0.1.0' && !$('#updLast') && /update undone/.test($('#toastMsg').textContent));
    C.store.set('upd', {});
  });

  await step('diagnostics and logs', async () => {
    C.store.set('logLevel', 'info'); C.store.set('logLevelSince', 0); C.go('settings'); await sleep(80);
    ok('Settings › Diagnostics: Normal by default, the folder, Copy diagnostics, no errors', !!$('#diagnostics') && $('[data-ll=info]').getAttribute('aria-pressed') === 'true' && $('[data-ll=debug]').getAttribute('aria-pressed') === 'false' && $('[data-ll=info]').textContent === 'Normal' && /clark’s own log folder/.test($('#diagnostics').textContent) && !/~\//.test($('#diagnostics').textContent) && !!$('#dgCopy') && /Debug adds detail for fixing problems\. Logs hold only counts, IDs and times, never your report text, names or keys\./.test($('#diagnostics').textContent));
    click($('#dgOpen')); await sleep(30); ok('Open the folder says what it would do', $('#toastMsg').textContent === 'Prototype: would open the log folder in Finder');
    click($('[data-ll=debug]')); await sleep(60);
    ok('Debug chosen and kept', C.logLevel() === 'debug' && C.store.get('logLevel') === 'debug' && $('[data-ll=debug]').getAttribute('aria-pressed') === 'true' && C.store.get('logLevelSince') > 0 && !$('#dgOld'));
    await undo(); ok('Undo puts the level back', C.logLevel() === 'info' && $('[data-ll=info]').getAttribute('aria-pressed') === 'true');
    click($('[data-ll=debug]')); await sleep(40); click($('[data-ll=info]')); await sleep(40); ok('Normal chosen again and kept', C.store.get('logLevel') === 'info' && C.store.get('logLevelSince') === 0);
    C.store.set('logLevel', 'debug'); C.store.set('logLevelSince', Date.now() - 10 * 864e5); C.refresh(); await sleep(40);
    ok('Debug on for more than 7 days: a gentle note says how long', /^Debug has been on for 10 days\. Switch back to Normal when you're done\.$/.test($('#dgOld')?.textContent || ''));
    C.store.set('logLevelSince', Date.now() - 2 * 864e5); C.refresh(); await sleep(40); ok('Debug on for two days: no note', !$('#dgOld'));
    C.store.set('logLevel', 'info'); C.store.set('logLevelSince', 0);
    /* C.log */
    const has = t => C.logLines().some(l => l.includes(t));
    C.log('debug', 'test', 'zzdebugone'); ok('C.log writes no debug line at Normal', !has('zzdebugone'));
    C.log('info', 'test', 'zzinfoone'); ok('C.log writes an info line at Normal, as "date time LEVEL area message"', C.logLines().some(l => /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d INFO test zzinfoone$/.test(l)));
    C.store.set('logLevel', 'debug'); C.log('debug', 'test', 'zzdebugtwo'); ok('C.log writes a debug line in Debug', C.logLines().some(l => /^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d DEBUG test zzdebugtwo$/.test(l)));
    C.go('work'); await sleep(40); C.go('settings'); await sleep(40);
    ok('page changes are logged (info nav), and renders in Debug', has('INFO nav view work') && has('DEBUG render view work'));
    C.store.set('logLevel', 'info');
    const un = window.ClarkDB.change('item', item('PDF-A-018'), { priority: item('PDF-A-018').priority === 'Low' ? 'High' : 'Low' }); ok('a save is logged with the item ID only', has('INFO save item PDF-A-018 priority') && !C.logLines(3).join().includes(item('PDF-A-018').title)); un && un();
    C.onError({ error: new TypeError('Zed Quill is missing'), filename: 'file:///x/views.js', lineno: 42 }); C.onReject({ reason: new RangeError('zed@example.org') });
    ok('a caught error is logged as error "page" by kind and place, never its message', has('ERROR page TypeError at views.js:42') && has('ERROR page RangeError not handled') && !has('Zed Quill') && !has('zed@example.org'));
    C.refresh(); await sleep(40); ok('Errors in the last 7 days lists them', $$('#dgErrs li').length === 2 && /TypeError/.test($('#dgErrs').textContent));
    for (let i = 0; i < 250; i++) C.log('info', 'test', 'fill ' + i); ok('the log keeps the last 200 lines', C.logLines().length === 200 && C.logLines().at(-1).endsWith('fill 249'));
    /* Copy diagnostics: no names, emails or project names */
    const uPf = window.ClarkDB.setProfile({ name: 'Zed Quill', email: 'zed@example.org', org: 'Quill Holdings' }); C.log('info', 'test', 'before copy'); C.go('settings'); await sleep(60);
    let got = ''; Object.defineProperty(navigator, 'clipboard', { value: { writeText: async t => { got = t; } }, configurable: true });
    click($('#dgCopy')); await sleep(60);
    ok('Copy diagnostics: the text holds the version, the log level, counts and the last log lines', /Version: clark 0\.1\.0/.test(got) && /Log level: Normal/.test(got) && new RegExp(`Counts: ${S().projects.length} projects, ${S().items.length} work items, ${S().milestones.length} milestones`).test(got) && /appearance \w+, section style \w+, layout .*PDF \w+/.test(got) && /Browser: \S+/.test(got) && /System: \S+/.test(got) && /before copy/.test(got) && got.split('Last 20 log lines:\n')[1].split('\n').length <= 21 && /Diagnostics copied/.test($('#toastMsg').textContent));
    const secret = ['Zed Quill', 'zed@example.org', 'Quill Holdings', ...S().projects.map(x => x.name), ...S().projects.map(x => x.client).filter(Boolean), ...S().items.slice(0, 40).map(x => x.title)];
    const leaks = secret.filter(x => got.includes(x));
    ok('Copy diagnostics holds no profile name, email, organisation, project name, client or item text' + (leaks.length ? ' (leaked: ' + leaks.join(' | ') + ')' : ''), !leaks.length && S().projects.length > 0 && got.includes('PDF'));
    Object.defineProperty(navigator, 'clipboard', { value: { writeText: () => Promise.reject(new Error('no')) }, configurable: true });
    click($('#dgCopy')); await sleep(80);
    ok('if the browser will not copy, the text is shown to select and copy', !!$('dialog[open] #dgRep') && $('#dgRep').value.startsWith('clark diagnostics') && $('#dgRep').readOnly); click($('dialog[open] [data-close]')); await sleep(40);
    delete navigator.clipboard; uPf && uPf(); C.store.set('logLevel', 'info');
  });

  await step('appearance: System', async () => {
    const root = document.documentElement, sd0 = C.sysDark; let dark = false; C.sysDark = () => dark;
    const flip = v => { dark = v; C.mq.dispatchEvent(new Event('change')); };
    try { localStorage.removeItem('clark.theme'); } catch (e) { /* none */ }
    ok('System is the default for a new user', C.themePref() === 'system'); C.themeApply(); ok('System with the Mac light: the page is light', root.dataset.theme === 'light');
    C.go('settings'); await sleep(60);
    ok('Settings › Appearance has Light, Dark and System, System pressed', $$('[data-theme-pick]').map(b => b.textContent).join() === 'Light,Dark,System' && $('[data-theme-pick=system]').getAttribute('aria-pressed') === 'true');
    flip(true); await sleep(30); ok('System follows the Mac when it switches to dark, live', root.dataset.theme === 'dark' && C.store.get('theme') === undefined);
    flip(false); await sleep(30); ok('...and back to light', root.dataset.theme === 'light');
    click($('[data-theme-pick=dark]')); await sleep(30); flip(false); ok('Dark chosen: kept, and the Mac does not change it', root.dataset.theme === 'dark' && C.store.get('theme') === 'dark' && $('[data-theme-pick=dark]').getAttribute('aria-pressed') === 'true');
    click($('[data-theme-pick=light]')); await sleep(30); flip(true); ok('Light chosen: kept, and the Mac does not change it', root.dataset.theme === 'light' && C.store.get('theme') === 'light');
    click($('[data-theme-pick=system]')); await sleep(30); ok('System chosen with the Mac dark: the page is dark and the choice is kept', root.dataset.theme === 'dark' && C.store.get('theme') === 'system' && C.themePref() === 'system');
    click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60);
    ok('the profile menu Dark mode, while the page is dark by System, sets an explicit Light', C.store.get('theme') === 'light' && root.dataset.theme === 'light');
    flip(false); click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60);
    ok('...and then an explicit Dark', C.store.get('theme') === 'dark' && root.dataset.theme === 'dark');
    C.sysDark = sd0; C.theme('light'); await sleep(30); ok('light again for the rest of the test', root.dataset.theme === 'light');
  });

  await step('help', async () => {
    C.go('help'); await sleep(80);
    ok('help: the page opens with three tabs', C.UI.view === 'help' && $$('#hpTabs [role=tab]').length === 3 && !!$('#hpPane'));
    for (const [t, sel] of [['start', '.hp-jobs .hp-job'], ['howto', '.hp-task'], ['reference', '.hp-ref']]) {
      click($(`#hpTabs [data-htab=${t}]`)); await sleep(40);
      ok(`help: the ${t} tab shows its part`, $('#hpPane').dataset.tab === t && $(`#hpTab-${t}`).getAttribute('aria-selected') === 'true' && $$(`#hpPane ${sel}`).length > 0);
    }
    ok('help: the tab used last is kept', C.store.get('helpTab') === 'reference');
    ok('help: the keys table and the milestone marks are there', $$('#hp-ref-keys tbody tr').length > 10 && $$('#hp-ref-milestone-states .hp-mk svg').length === 6);
    const q = $('#hpQ'); q.value = 'swimlanes'; q.dispatchEvent(new Event('input', { bubbles: true })); await sleep(40);
    ok('help: search filters as you type', $('#hpPane').hidden && !$('#hpRes').hidden && $$('#hpRes .hp-r').length > 0 && $$('#hpRes .hp-r').every(r => /swimlane/i.test(r.textContent)) && !!$('#hpRes mark'));
    q.value = 'zzqxj'; q.dispatchEvent(new Event('input', { bubbles: true })); await sleep(40);
    ok('help: a search with no match says so', /Nothing in Help/.test($('#hpRes').textContent) && !$$('#hpRes .hp-r').length);
    q.value = 'move the agreed date'; q.dispatchEvent(new Event('input', { bubbles: true })); await sleep(40); click($('#hpRes .hp-r')); await sleep(60);
    ok('help: a result opens its place and clears the search', !$('#hpPane').hidden && $('#hpRes').hidden && q.value === '');
    click($('#hpTabs [data-htab=start]')); await sleep(40);
    click($('.hp-job [data-hlink="howto-publish-the-report"]')); await sleep(60);
    ok('help: a job title opens its how-to', $('#hpPane').dataset.tab === 'howto' && !!$('#hp-howto-publish-the-report'));
    click($('#hpTabs [data-htab=start]')); await sleep(40);
    click($('.hp-job [data-hgo="work"]')); await sleep(80);
    ok('help: a job card link goes to its screen', C.UI.view === 'work' && !!$('.wbar'));
    click($('#meBtn')); await sleep(40); await menuPick('Help'); await sleep(80); ok('help: from the profile circle', C.UI.view === 'help');
    C.help.open('ref-keys'); await sleep(120);
    ok('help: C.help.open opens a place in Help', C.UI.view === 'help' && $('#hpPane').dataset.tab === 'reference');
    /* Help stays in step with the build (BRD FR-124): every link inside Help finds its place, and every screen it sends you to exists */
    const links = new Set(), gos = new Set(), ids = new Set();
    for (const t of ['start', 'howto', 'reference']) { click($(`#hpTab-${t}`)); await sleep(60); $$('#hpPane [data-hlink]').forEach(a => links.add(a.dataset.hlink)); $$('#hpPane [data-hgo]').forEach(a => gos.add(a.dataset.hgo)); $$('#hpPane [id]').forEach(e => ids.add(e.id)); }
    const lost = [...links].filter(l => !ids.has('hp-' + l) && !ids.has(l));
    ok('help: every link inside Help finds its place' + (lost.length ? ' (lost: ' + lost.join(', ') + ')' : ''), links.size > 20 && !lost.length);
    const ACTIONS = ['ask', 'preview', 'publish', 'dashboard+edit'], noScreen = [];
    for (const g of gos) { const [v, anchor] = g.split('#'); if (ACTIONS.includes(v)) continue; C.go(v); await sleep(60); if (C.UI.view !== v || (anchor && !document.getElementById(anchor))) noScreen.push(g); }
    ok('help: every screen Help sends you to exists' + (noScreen.length ? ' (missing: ' + noScreen.join(', ') + ')' : ''), gos.size > 3 && !noScreen.length);
    C.go('dashboard'); await sleep(60);
  });

  /* the design review (#87): menus, the peek, the board's cards and the calendar by keyboard; the top bar on a phone */
  await step('keyboard (design review #87)', async () => {
    const act = () => document.activeElement, items = () => $$('.menu [role^=menuitem]');
    click($('#logoBtn')); await sleep(60); C.closePop();
    /* menus */
    $('#meBtn').focus(); click($('#meBtn')); await sleep(80);
    ok('menu: it is a role=menu, and focus moves to the first item on open', $('.menu').getAttribute('role') === 'menu' && items().length >= 4 && act() === items()[0], act().textContent.slice(0, 20));
    ok('menu: a switch is a menuitemcheckbox with its state', $$('.menu [role=menuitemcheckbox]').length === 1 && /Dark mode/.test($('.menu [role=menuitemcheckbox]').textContent) && $('.menu [role=menuitemcheckbox]').getAttribute('aria-checked') === 'false');
    key(act(), 'ArrowDown'); ok('menu: Down moves focus to the next item', act() === items()[1]);
    key(act(), 'ArrowUp'); key(act(), 'ArrowUp'); ok('menu: Up from the first wraps to the last', act() === items().at(-1));
    key(act(), 'ArrowDown'); ok('menu: Down from the last wraps to the first', act() === items()[0]);
    key(act(), 'End'); ok('menu: End jumps to the last item', act() === items().at(-1)); key(act(), 'Home'); ok('menu: Home jumps to the first item', act() === items()[0]);
    key(act(), 'Escape'); await sleep(40); ok('menu: Esc closes it and focus returns to the profile circle', !$('.menu') && act() === $('#meBtn'));
    $('#projBtn').focus(); click($('#projBtn')); await sleep(80);
    ok('select menu: items are menuitemradio, the chosen one is checked and holds the focus', $$('.menu [role=menuitemradio]').length >= 2 && act().getAttribute('aria-checked') === 'true' && act().getAttribute('role') === 'menuitemradio' && /Data Platform Pilot/.test(act().textContent));
    key(act(), 'Enter'); await sleep(60); ok('select menu: Enter picks, the menu closes and focus is back on the picker', !$('.menu') && act() === $('#projBtn'));
    /* the peek */
    click($('.tab[data-view=work]')); await sleep(80);
    { const row = () => $('tr[data-id="PDF-A-019"]'); row().focus(); click(row().querySelector('td')); await sleep(100);
      ok('peek: focus moves into it on open', $('#peek').classList.contains('on') && $('#peek').contains(act()), act().id || act().tagName);
      key(act(), 'Escape'); await sleep(60); ok('peek: Esc closes it and focus returns to the row that opened it', !$('#peek').classList.contains('on') && act() === row());
      click(row().querySelector('td')); await sleep(100); click($('#pkClose')); await sleep(60); ok('peek: the close button returns focus to the row', !$('#peek').classList.contains('on') && act().dataset.id === 'PDF-A-019');
      click(row().querySelector('td')); await sleep(100); $('.head h1').dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); await sleep(60); ok('peek: a click away returns focus to the row', !$('#peek').classList.contains('on') && act().dataset.id === 'PDF-A-019');
      click(row().querySelector('td')); await sleep(100); const t = $('tr[data-id="PDF-A-018"]'); t.focus(); t.dispatchEvent(new MouseEvent('mousedown', { bubbles: true })); click(t.querySelector('td')); await sleep(100);
      ok('peek: another row moves the peek, and focus is not lost', C.UI.peek === 'PDF-A-018' && act() !== document.body && ($('#peek').contains(act()) || act() === t), act().tagName);
      key(act(), 'Escape'); await sleep(60); ok('peek: after moving, Esc goes back to the row last clicked', !$('#peek').classList.contains('on') && act().dataset.id === 'PDF-A-018');
      click(row().querySelector('td')); await sleep(100); $('#pkNext').focus(); click($('#pkNext')); await sleep(100); ok('peek: Next keeps focus inside the peek', $('#peek').contains(act()) && act() !== document.body, act().id);
      key(act(), 'Escape'); await sleep(60); }
    /* the board's cards */
    click($('[data-layout=board]')); await sleep(80);
    { const c = $('[data-card="PDF-A-019"]'); ok('card: role=button with the ID and title as its name, and focusable', c.getAttribute('role') === 'button' && c.tabIndex === 0 && /^PDF-A-019 /.test(c.getAttribute('aria-label')) && c.getAttribute('aria-label').length > 12);
      ok('card: a focus ring (:focus-visible) in the stylesheet', /\.bcard:focus-visible\s*\{[^}]*outline:\s*2px solid/.test(window.CLARK_APPCSS));
      c.focus(); key(c, 'Enter'); await sleep(100); ok('card: Enter opens the peek', $('#peek').classList.contains('on') && C.UI.peek === 'PDF-A-019'); key(act(), 'Escape'); await sleep(60);
      ok('card: Esc gives the focus back to the card', !$('#peek').classList.contains('on') && act() === $('[data-card="PDF-A-019"]'));
      key(act(), ' '); await sleep(100); ok('card: Space opens the peek', C.UI.peek === 'PDF-A-019'); key(act(), 'Escape'); await sleep(60);
      key($('[data-mvto="PDF-A-019"]'), 'Enter'); await sleep(60); ok('card: Enter on its Move button does not open the peek', !$('#peek').classList.contains('on')); }
    click($('[data-layout=table]')); await sleep(60);
    /* the milestone calendar */
    click($('.tab[data-view=milestones]')); await sleep(80); if ($('.msv').dataset.msv !== 'cal') { click($('[data-msvb=cal]')); await sleep(60); }
    { const vis = () => $('.cal-m:not([hidden])'), cells = () => [...vis().querySelectorAll('.cal-d[data-d]')], tab0 = () => cells().filter(x => x.tabIndex === 0), add = (d, n) => window.ClarkDB.addDays(d, n);
      for (const [mode, label] of [['month', 'Month'], ['week', 'Week'], ['quarter', 'Quarter']]) {
        click($(`[data-calv-b=${mode}]`)); await sleep(50); click($('[data-cal="0"]')); await sleep(40);
        ok(`calendar ${label}: one day has tabindex 0, and it is today`, tab0().length === 1 && tab0()[0].dataset.d === window.ClarkDB.TODAY, tab0().map(x => x.dataset.d).join());
        const d0 = tab0()[0]; d0.focus(); const d = d0.dataset.d;
        key(act(), 'ArrowRight'); ok(`calendar ${label}: Right moves a day on`, act().dataset.d === add(d, 1) && act().tabIndex === 0 && tab0().length === 1, act().dataset.d);
        key(act(), 'ArrowDown'); ok(`calendar ${label}: Down moves a week on`, act().dataset.d === add(d, 8), act().dataset.d);
        key(act(), 'ArrowLeft'); key(act(), 'ArrowUp'); ok(`calendar ${label}: Left and Up move back a day and a week`, act().dataset.d === d, act().dataset.d); }
      click($('[data-calv-b=month]')); await sleep(50); click($('[data-cal="0"]')); await sleep(40);
      { const last = cells().at(-1); last.focus(); const nx = add(last.dataset.d, 1); key(act(), 'ArrowRight'); ok('calendar: an arrow past the month end goes on into the next month', act().dataset.d === nx && vis().contains(act()) && act().tabIndex === 0, act().dataset.d + ' vs ' + nx); }
      click($('[data-cal="0"]')); await sleep(40);
      { const withMs = cells().find(x => x.querySelector('.cal-ms')); ok('calendar: day cells are named with their date', /\d{4}/.test(cells()[0].getAttribute('aria-label')) && !!withMs && /milestone/.test(withMs.getAttribute('aria-label')));
        withMs.focus(); key(act(), 'Enter'); ok('calendar: Enter on a day with milestones focuses its first chip', act() === withMs.querySelector('.cal-ms') && act().tagName === 'BUTTON');
        const empty = cells().find(x => !x.querySelector('.cal-ms')); empty.focus(); key(act(), 'Enter'); ok('calendar: Enter on an empty day does nothing', act() === empty); }
      click($('[data-calv-b=month]')); await sleep(30); }
    click($('.tab[data-view=dashboard]')); await sleep(80);
    /* a phone: 390 px wide, asked of the runner (the page cannot resize its own window) */
    document.title = 'SELFTEST-PHONE'; { const t0 = Date.now(); while (!window.__phone && Date.now() - t0 < 6000) await sleep(100); }
    if (!window.__phone) out.push('SKIP phone-width checks: the runner gave no 390 px window');
    else {
      await sleep(250); const r = e => $(e).getBoundingClientRect(), noScroll = () => document.documentElement.scrollWidth <= innerWidth;
      ok('phone: the window is 390 px wide', innerWidth === 390, innerWidth);
      for (const v of ['dashboard', 'work', 'milestones']) { click($(`.tab[data-view=${v}]`)); await sleep(150); ok(`phone: no horizontal page scroll on ${v}`, noScroll(), noScroll() ? '' : `scrollWidth ${document.documentElement.scrollWidth}: ` + $$('body *').filter(e => e.scrollWidth > e.clientWidth + 1 && e.clientWidth > 0).slice(0, 6).map(e => e.tagName + '.' + String(e.className).slice(0, 30)).join(' | ')); }
      const row1 = ['#logoBtn', '#projBtn', '#askBtn', '#meBtn'].map(r), tabs = r('.tabs');
      ok('phone: logo, project picker, ask clark and profile share the first row', Math.max(...row1.map(b => b.top)) - Math.min(...row1.map(b => b.top)) < 12 && row1.every(b => b.bottom <= r('.tabs').top + 1), row1.map(b => Math.round(b.top)).join());
      ok('phone: the picker, ask clark and the profile circle fit the width, in order', r('#projBtn').left >= r('#logoBtn').right && r('#projBtn').right <= r('#askBtn').left && r('#askBtn').right <= r('#meBtn').left && r('#meBtn').right <= innerWidth);
      ok('phone: ask clark is an icon (named for screen readers)', r('#askBtn').width < 48 && $('#askBtn').getAttribute('aria-label') === 'ask clark');
      ok('phone: the view tabs sit on a second row that scrolls sideways if needed', tabs.top >= r('#logoBtn').bottom - 1 && tabs.width >= document.documentElement.clientWidth - 10 && getComputedStyle($('.tabs')).overflowX === 'auto' && [...$$('.tab')].every(b => b.getBoundingClientRect().top >= tabs.top - 1 && b.getBoundingClientRect().bottom <= tabs.bottom + 1), `${Math.round(tabs.width)} of ${document.documentElement.clientWidth} px`);   /* the full row, less a classic scroll bar where the system draws one (Linux: 15 px; Mac and phones overlay theirs) */
      ok('phone: the sticky bar is as tall as its two rows', Math.round(r('.top').height) === 96 && getComputedStyle(document.documentElement).getPropertyValue('--topbar').trim() === '96px', Math.round(r('.top').height));
      click($('#projBtn')); await sleep(80); ok('phone: the project menu fits the window', !!$('.menu') && r('.menu').left >= 0 && r('.menu').right <= innerWidth); C.closePop();
      document.title = 'SELFTEST-PHONE-END'; { const t0 = Date.now(); while (window.__phone && Date.now() - t0 < 6000) await sleep(100); } await sleep(200);
      ok('phone: back to the full window', innerWidth > 700, innerWidth); }
    click($('#logoBtn')); await sleep(60);
  });

  await step('database', async () => {
    await window.ClarkDB.flush(); await sleep(100);
    const n = await new Promise(res => { const r = indexedDB.open('clark-prototype'); r.onsuccess = () => { const q = r.result.transaction('history').objectStore('history').count(); q.onsuccess = () => res(q.result); }; r.onerror = () => res(-1); });
    ok('changes and history are in the browser database', n > 50 && n === S().history.length, `${n} history rows`);
    const its = await new Promise(res => { const r = indexedDB.open('clark-prototype'); r.onsuccess = () => { const q = r.result.transaction('items').objectStore('items').get('PDF-A-018'); q.onsuccess = () => res(q.result); }; });
    ok('an item read back from the database', its && its.update.length > 10);
    const DB = window.ClarkDB, old = { items: [{ id: 'PDF-R-003', code: 'PDF', type: 'R', status: 'Open', ms: 'M4' }, { id: 'PDF-I-003', code: 'PDF', type: 'I', status: 'Open', ms: '' }, { id: 'PDF-A-001', code: 'PDF', type: 'A', status: 'In progress', ms: '' }, { id: 'PDF-D-001', code: 'PDF', type: 'D', status: 'Agreed', ms: '' }],
      milestones: [{ key: 'PDF/M4', id: 'M4', code: 'PDF' }], history: [{ kind: 'item', id: 'PDF-R-003', code: 'PDF', field: 'status', from: 'In progress', to: 'Done' }, { kind: 'ms', id: 'M4', code: 'PDF', field: 'agreed' }] };
    ok('older saved data moves to creaite\'s statuses and IDs', DB.migrate(old) && old.items.map(x => x.id + ':' + x.status + ':' + x.ms).join() === 'PDF-003:Open:PDF-M-004,PDF-004:Open:,PDF-A-001:Open:,PDF-D-001:Made:' && old.milestones[0].key === 'PDF/PDF-M-004' && old.history[0].id === 'PDF-003' && old.history[0].to === 'Closed' && old.history[1].id === 'PDF-M-004' && !DB.migrate(old));
    { const T = DB.TODAY, A = n => DB.addDays(T, n);
      ok('slip as creaite: from the agreed date to the later of the forecast and today', DB.slip({ agreed: A(-5), forecast: A(-5), achievedOn: '', manual: '' }) === 5 && DB.slip({ agreed: A(-1), forecast: A(3), achievedOn: '', manual: '' }) === 4 && DB.slip({ agreed: A(10), forecast: A(24), achievedOn: '', manual: '' }) === 14 && DB.slip({ agreed: A(10), forecast: A(10), achievedOn: '', manual: '' }) === 0);
      ok('no slip for an achieved milestone or a Forecast', DB.slip({ agreed: A(-5), forecast: A(-5), achievedOn: A(-1), manual: '' }) === 0 && DB.slip({ agreed: A(-5), forecast: A(9), achievedOn: '', manual: 'Forecast' }) === 0 && DB.msWord('Forecast', true) === 'Forecast'); }
    ok('creaite: a milestone past its agreed date is Overdue even with a later forecast', DB.msState({ agreed: DB.addDays(DB.TODAY, -1), forecast: DB.addDays(DB.TODAY, 3), achievedOn: '', manual: '' }) === 'Overdue');
    ok('creaite\'s value lists', DB.STATUSES.A.join() === 'Open,Delayed,Closed,Cancelled' && DB.STATUSES.D.join() === 'Pending,Made,Withdrawn' && DB.STATUSES.R.join() === 'Open,Closed,Cancelled');
  });

  await step('reset', async () => { click($('#resetDemo')); for (let i = 0; i < 40 && (S().history.length || S().projects.some(p => p.code === 'FSU')); i++) { await window.ClarkDB.flush(); await sleep(50); }   /* the database works in real time; the test's clock runs faster */ ok('reset demo data, keeping the profile', !S().projects.some(p => p.code === 'FSU') && S().history.length === 0 && window.ClarkDB.S.profile.name === 'Sam Taylor', `FSU ${S().projects.some(p => p.code === 'FSU')}, history ${S().history.length}`); });

  await step('accepted candidates: freshness, publications, needs from you, since the last report, send preview, PDF, people', async () => {
    const DB = window.ClarkDB, T = DB.TODAY, A = n => DB.addDays(T, n), pending = []; C.noNativeSave = true; C.setProject('PDF'); C.go('dashboard'); await sleep(80);
    /* #119 freshness */
    { const x = item('PDF-A-016'), y = item('PDF-A-021'), f = DB.fresh(x);
      ok('freshness: an item with no history is raised the day it came in, and was last reviewed then too', f.raised === x.imported && f.reviewed === f.raised && f.ago >= 14, JSON.stringify(f));
      ok('freshness: "not reviewed in 14 days" is on for an old open item and off for a recent one', DB.notReviewed(x) && !DB.notReviewed(y)); }
    C.workFilter({ fresh: ['stale'] }); await sleep(100);
    ok('freshness: Work items has a Freshness filter; Not reviewed in 14 days lists exactly those open items', !!$('[data-fb=fresh]') && $$('tr[data-id]').map(r => r.dataset.id).sort().join() === C.items().filter(x => DB.notReviewed(x)).map(x => x.id).sort().join() && $$('tr[data-id]').length > 0 && $$('.fchip').some(c => /Freshness: Not reviewed in 14 days/.test(c.textContent)));
    C.workFilter({}); await sleep(40);
    C.openItem('PDF-A-016', ['PDF-A-016']); await sleep(140);
    ok('freshness: the peek shows Raised, Last reviewed and the muted chip', /Raised \d\d-\d\d-\d{4} · Last reviewed \d\d-\d\d-\d{4}/.test($('#pkFresh').textContent) && /Not reviewed in 14 days/.test($('#pkFresh').textContent) && $('#pkFresh .tag').textContent === 'Not reviewed in 14 days');
    C.openItem('PDF-A-021', ['PDF-A-021']); await sleep(140); ok('freshness: a recently reviewed item has no chip', !$('#pkFresh .tag') && /Last reviewed/.test($('#pkFresh').textContent));
    { const x = item('PDF-A-022'), u1 = DB.change('item', x, { priority: 'High' }, DB.who('via ask clark'));
      ok('freshness: a change by ask clark is not a review', DB.fresh(x).reviewed !== T && DB.notReviewed(x));
      const u2 = DB.change('item', x, { priority: 'Low' }, DB.who('in the peek'));
      ok('freshness: a change by hand is a review, worked out from history', DB.fresh(x).reviewed === T && !DB.notReviewed(x) && DB.fresh(x).raised === x.imported); u2(); u1(); }
    /* #121 needs (flag in the peek) */
    C.openItem('PDF-A-018', ['PDF-A-018']); await sleep(140);
    ok('needs: the peek has a Needed from the client switch, off to start', $('#pkAct').getAttribute('aria-checked') === 'false' && /Needed from the client/.test($('#peek').textContent));
    click($('#pkAct')); await sleep(100); ok('needs: switching it on flags the item, with history', item('PDF-A-018').clientAct === true && $('#pkAct').getAttribute('aria-checked') === 'true' && S().history.some(h => h.id === 'PDF-A-018' && h.field === 'clientAct' && h.to === true) && DB.fieldName('clientAct', 'item') === 'Needed from the client');
    C.closePeek({ quiet: true });
    /* gaps before publish */
    const u0 = DB.change('item', item('PDF-A-025'), { owner: '' }, DB.who('in the peek'));
    click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60);
    ok('freshness: the Publish box counts open items with no owner or date, and still lets you publish', /1 item has no owner or date\./.test($('#pubGaps').textContent) && !$('#pubGo').disabled && /warning only/.test($('#pubChecks').textContent));
    click($('#pubGaps [data-show]')); await sleep(140);
    ok('freshness: Show them opens Work items filtered to them', !$('#dlg').open && C.UI.view === 'work' && $$('tr[data-id]').map(r => r.dataset.id).join() === 'PDF-A-025', $$('tr[data-id]').map(r => r.dataset.id).join());
    u0(); C.workFilter({}); await sleep(40); C.go('dashboard'); await sleep(80);
    click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60); ok('freshness: nothing missing, no gap line', !$('#pubGaps') && !!$('#pubStale')); click($('#dlg [data-close]')); await sleep(40);
    /* #124 PDF and #120 numbered publications */
    const n0 = DB.pubNext(P()), wo = window.open, wrote = []; window.open = () => ({ document: { write(h) { wrote.push(h); }, close() {} }, close() {} });
    click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60);
    ok('PDF: the Publish box has an Also a PDF tick beside Word, and says which publication this is', !!$('#pubPdf') && /Also a PDF/.test($('#dlg').textContent) && !!$('#pubWord') && new RegExp('Publication ' + n0).test($('#dlg .dlg-h').textContent));
    ok('PDF: the prototype note shows when it is ticked', $('#pubPdfNote').hidden); $('#pubPdf').checked = true; $('#pubPdf').dispatchEvent(new Event('change')); ok('PDF: ... and reads as asked', !$('#pubPdfNote').hidden && $('#pubPdfNote').textContent === 'Prototype: your browser’s print box opens; choose Save as PDF.');
    $('#pubF').requestSubmit(); await sleep(1800); window.open = wo;
    { const rec = P().published.slice(-1)[0], cp = DB.pubCopy('PDF', n0), pg = cp ? cp.html : '';
      ok('publications: a publish gets the next number, with who and where', rec.n === n0 && rec.who === 'Sam Taylor' && rec.where === 'Local' && rec.pdf === true && /^\d{4}-\d\d-\d\d \d\d:\d\d$/.test(rec.at), JSON.stringify(rec));
      ok('publications: a copy of the page is kept, and its foot says Publication N · date', !!cp && cp.html.includes('<footer>Published ' + DB.fd(T) + '. Publication ' + n0 + ' · ' + DB.fd(T) + '. View only.</footer>') && /Two of three data domains/.test(cp.texts.summary));
      ok('PDF: choosing it opens the page in a new tab that prints', wrote.length === 1 && /window\.print\(\)/.test(wrote[0]) && wrote[0].includes('Publication ' + n0));
      ok('PDF: print rules stack the three tabs, hide the controls, keep sections whole, light only, with the publication number', /@media print/.test(pg) && /\.view\{display:block!important\}/.test(pg) && /\.tabsbar/.test(pg.split('@media print')[1]) && /break-inside:avoid/.test(pg) && /color-scheme:light/.test(pg) && new RegExp('@bottom-left\\{content:"Publication ' + n0 + ' ·').test(pg) && /counter\(page\)/.test(pg));
      const js = (pg.split('<script>')[1] || '').split('<\/script>')[0]; ok('the published page script holds no backtick and no ${', js.length > 500 && !js.includes('`') && !js.includes('${')); }
    { const r = DB.clone(P().report); r.sections.find(x => x.id === 'summary').html = '<p>Second version of the summary.</p>'; DB.change('project', P(), { report: r }, DB.who('in the report')); }
    click($('#meBtn')); await sleep(40); await menuPick('Publish'); await sleep(60); $('#pubF').requestSubmit(); await sleep(1300);
    ok('publications: the next publish is the next number, and the earlier copy stays', P().published.slice(-1)[0].n === n0 + 1 && !!DB.pubCopy('PDF', n0) && /Second version/.test(DB.pubCopy('PDF', n0 + 1).texts.summary) && /Two of three/.test(DB.pubCopy('PDF', n0).texts.summary));
    C.go('settings'); await sleep(100);
    ok('publications: Settings lists them newest first with number, date, where, who and Open', $$('#pubs tbody tr').length === P().published.length && $$('#pubs tbody tr')[0].cells[0].textContent === String(n0 + 1) && /Local/.test($$('#pubs tbody tr')[0].cells[2].textContent) && $$('#pubs tbody tr')[0].cells[3].textContent === 'Sam Taylor' && $$('#pubs [data-pubopen]').length === $$('#pubs tbody tr').length);
    { let url = ''; window.open = u => { url = u; return {}; }; click($('#pubs [data-pubopen="' + n0 + '"]')); await sleep(60); window.open = wo; ok('publications: Open shows the kept copy in a new tab from a Blob URL', /^blob:/.test(url)); }
    for (let i = 1; i <= 12; i++) await DB.pubKeep('CAP', i, { n: i, code: 'CAP', html: '<p>' + i + '</p>' });
    { const keys = Object.keys(S().pubCopies).filter(k => k.startsWith('pub:CAP:')); ok('publications: only the last 10 copies are kept', keys.length === 10 && !DB.pubCopy('CAP', 2) && !!DB.pubCopy('CAP', 3) && !!DB.pubCopy('CAP', 12)); }
    click($('#meBtn')); await sleep(40); ok('publications: the profile menu has Published reports', $$('.menu [data-i]').some(e => /^Published reports/.test(e.textContent.trim()))); await menuPick('Published reports'); await sleep(120); ok('publications: ... which goes to the list in Settings', C.UI.view === 'settings' && !!$('#pubs'));
    /* #121 the section */
    ['PDF-D-008', 'PDF-A-018'].forEach(id => window.ClarkDB.change('item', item(id), { client: true }));   /* the list follows the eye (FR-82), so show both to the client first */
    C.go('dashboard'); await sleep(80); click($('[data-mode=edit]')); await sleep(60);
    ok('needs: the template is live, Full or Half, under Work items, and there are 20', C.templates.length === 20 && (t => !!t && t.live === true && t.kind === 'raid' && t.fit.join() === 'Full,Half')(C.templates.find(t => t.id === 'needs')));
    click($('[data-addbelow=summary]')); await sleep(120); click($('.atd-c[data-t=needs]')); await sleep(30); click($('#atdGo')); await sleep(160);
    const nx = P().report.sections.find(x => x.type === 'needs');
    ok('needs: added from the box as a section of its own type, titled Needs from you', !!nx && nx.title === 'Needs from you' && !!$('[data-sec="' + nx.id + '"]'));
    { const t = $('[data-sec="' + nx.id + '"]').textContent;
      ok('needs: it lists the pending decision and the flagged item, each with what, by when and the ID', /PDF-D-008/.test(t) && /PDF-A-018/.test(t) && /Needed by \d\d-\d\d-\d{4}/.test(t) && /Use synthetic data/.test(t) && !/PDF-A-012/.test(t));
      ok('needs: it is on the page (C.onPage) and in the contents with its count', C.onPage(nx) && C.tocCounts(P(), nx) === C.needsList(P()).length + ' needed'); }
    { const html = await C.webPage({ n: 99 }); ok('needs: it is published, with the decision', C.onPage(nx) && /Needs from you/.test(html) && /PDF-D-008/.test(html) && /Needed by/.test(html)); }
    { const d = C.needsList(P())[0]; if (d) { const was = d.client; d.client = false; ok('needs: an item hidden with the eye is never listed', !C.needsList(P()).includes(d)); d.client = was; } }
    C.setProject('CPR'); ok('needs: with nothing to ask the editor says so quietly', C.needsHtml(true).includes('Nothing needed from you this week.') && C.needsList(C.P()).length === 0); C.setProject('PDF');
    /* #122 health suggestion */
    C.go('dashboard'); await sleep(80); click($('[data-mode=edit]')); await sleep(60);
    { const p = P(), hs = C.healthSuggest(p);
      ok('suggestion: At risk from slipped milestones and red risks, in plain words', hs.h === 'A' && /slipped milestones?/.test(hs.because) && /red risks or issues/.test(hs.because) && !/overdue by more than 7/.test(hs.because), hs.text);
      ok('suggestion: shown beside the user\'s own health in Edit, which it matches', /^Suggested: At risk, because/.test($('#hSug').textContent) && !$('#hUse') && /matches/.test($('#hSug').textContent) && !$('#hReq'));
      const ud = DB.change('item', item('PDF-A-012'), { due: A(-9) }, DB.who('in the peek')), h2 = C.healthSuggest(p);
      ok('suggestion: an action overdue by more than 7 days adds a rule; all three make it Off track', h2.h === 'R' && /PDF-A-012/.test(h2.because) && /overdue by more than 7 days/.test(h2.because), h2.text); ud();
      const uh = DB.change('project', p, { health: 'G' }, DB.who('in the report')); C.refresh(); await sleep(60);
      ok('suggestion: a better health than the suggestion makes the reason required, with a plain prompt', C.healthSuggest(p).better && $('#hReason').required && !!$('#hReq') && /reason is needed/.test($('#hReq').textContent) && !!$('#hUse'));
      const rs = $('#hReason'), keep = p.reason; rs.value = ''; rs.dispatchEvent(new Event('change', { bubbles: true })); await sleep(60);
      ok('suggestion: the reason cannot be emptied then, and the user is told', p.reason === keep && /reason is needed/.test($('#toastMsg').textContent));
      const ur = DB.change('project', p, { reason: '' }, DB.who('in the report')); C.refresh(); await sleep(60);
      ok('suggestion: an empty reason shows the prompt as an alert', $('#hReq').getAttribute('role') === 'alert' && /Say why/.test($('#hReq').textContent)); ur(); uh(); C.refresh(); await sleep(40);
      click($('[data-mode=view]')); await sleep(60); ok('suggestion: View never shows it', !$('#hSug') && !$('#hReq') && !/Suggested/.test($('.sheet').textContent)); }
    /* #118 since the last report */
    C.go('dashboard'); await sleep(60);
    DB.change('item', item('PDF-A-012'), { due: A(5) }, DB.who('in the peek')); DB.change('item', item('PDF-A-015'), { status: 'Closed' }, DB.who('in the peek')); DB.change('item', item('PDF-A-018'), { owner: 'Jo Ellis' }, DB.who('in the peek'));
    DB.change('item', item('PDF-D-008'), { status: 'Made' }, DB.who('in the peek')); DB.change('ms', S().milestones.find(m => m.id === 'PDF-M-004'), { forecast: A(50) }, DB.who('in the peek'));
    { const nw = { id: 'PDF-A-026', code: 'PDF', type: 'A', ws: 'Testing', title: 'Check the since panel', owner: 'Sam Rivers', due: A(3), status: 'Open', priority: 'Medium', desc: '', update: '', updatedAt: DB.stamp(), client: true, clientText: '', ms: '', uc: '', source: 'test' }; DB.create('item', nw, DB.who('in the report')); }
    { const sl = C.sinceLast(P()), has = (id, re) => sl.lines.some(l => l.id === id && re.test(l.pre + l.post));
      ok('since: lists changes after the last publication as plain lines with IDs', !!sl && sl.n === n0 + 1 && has('PDF-A-026', /^Opened action/) && has('PDF-A-015', /^Closed/) && has('PDF-A-012', /due \d\d-\d\d-\d{4} → \d\d-\d\d-\d{4}/) && has('PDF-A-018', /owner Priya Nair → Jo Ellis/) && has('PDF-D-008', /Decision made/) && has('PDF-M-004', /forecast/), sl && sl.lines.map(l => l.id).join());
      ok('since: a change made before the publication is not listed', !sl.lines.some(l => l.id === 'PDF-A-025' || l.id === 'PDF-A-022')); }
    click($('[data-mode=edit]')); await sleep(60);
    ok('since: Edit shows the panel headed with the publication number and date, and the IDs open items', $('#since h2').textContent === 'Since the last report (Publication ' + (n0 + 1) + ', ' + DB.fd(T) + ')' && !!$('#since [data-open="PDF-A-012"]') && !!$('#since [data-since-ms="PDF-M-004"]'));
    ok('since: it is for the author only: not in the published page', !/Since the last report/.test(await C.webPage({ n: 98 })) && !/Since the last report/.test(DB.pubCopy('PDF', n0 + 1).html));
    C.setProject('CPR'); click($('[data-mode=edit]')); await sleep(60);
    ok('since: before any publication it says there is nothing to compare with', C.sinceLast(C.P()) === null && /Not published yet, so there is nothing to compare with\./.test($('#since').textContent) && $('#startLast').getAttribute('aria-disabled') === 'true');
    C.setProject('PDF'); click($('[data-mode=edit]')); await sleep(60);
    { const r = DB.clone(P().report); r.sections.find(x => x.id === 'summary').html = '<p>Unpublished third version.</p>'; DB.change('project', P(), { report: r }, DB.who('in the report')); C.refresh(); await sleep(60);
      ok('since: Start from last week\'s report is available once published', $('#startLast').getAttribute('aria-disabled') !== 'true' && /Start from last week’s report/.test($('#startLast').textContent));
      click($('#startLast')); await sleep(80); ok('since: it asks first, and names the sections', $('#dlg').open && /Start from Publication/.test($('#dlg').textContent) && /Summary/.test($('#dlg').textContent));
      click($('#cfYes')); await sleep(120); ok('since: it copies the text sections from the last publication, in one step', P().report.sections.find(x => x.id === 'summary').html === '<p>Second version of the summary.</p>' && /Text carried forward from Publication/.test($('#toastMsg').textContent));
      await undo(); ok('since: ... and Undo puts this week\'s text back', /Unpublished third version/.test(P().report.sections.find(x => x.id === 'summary').html)); }
    /* #122 what will be sent */
    click($('[data-mode=view]')); await sleep(60); C.askOpen(); await sleep(120);
    { const v = C.sendPreview(), t = $('#askPrevT').textContent;
      ok('send preview: one plain sentence says the sources, the size in words and the provider', /^A question sends .*’s work items, milestones and use cases \(about [\d,]+ words\) to Claude\.$/.test(t) && v.items === C.items().length && v.approx >= 50 && v.provider === 'Claude', t);
      ok('send preview: Show details opens the parts, and Hide details closes them', $('#askPrevD').hidden && (click($('#askPrevB')), true) && !$('#askPrevD').hidden && /Work items: \d+, about/.test($('#askPrevD').textContent) && /Mail, Teams and calendars are never sent/.test($('#askPrevD').textContent) && $('#askPrevB').textContent === 'Hide details' && (click($('#askPrevB')), $('#askPrevD').hidden));
      const us = DB.change('project', P(), { sources: ['~/Projects/A', '~/Projects/B'] }, DB.who('in the report')); C.askPreviewDraw();
      ok('send preview: the named source folders are counted and listed', /and 2 named source folders to Claude/.test($('#askPrevT').textContent)); us(); C.askPreviewDraw(); }
    C.askClose(); await sleep(40);
    /* #115 people */
    C.go('settings'); await sleep(100);
    { const rows = $$('#ppTable tbody tr');
      ok('people: a table of the distinct owners; no chip on the rows (the one line above says how many need details)', rows.length === C.people().length && rows.length >= 6 && rows.every(r => !/Needs details/.test(r.textContent)) && /^\d+ of \d+ people need details/.test($('#ppCount').textContent) && $$('#ppTable th').map(h => h.textContent).join() === 'Name,Email,Organisation,Role');
      const cnt0 = $('#ppCount').textContent; click($('#ppPasteBtn')); await sleep(30); $('#ppText').value = 'Name\tEmail\tOrganisation\tRole\nSam Rivers\tsam.rivers@example.com\tSupplier\tDelivery lead\nZed Newman\tzed@example.com\tClient\tSponsor'; click($('#ppAdd')); await sleep(120);
      const sam = $('[data-person="Sam Rivers"]'), zed = $('[data-person="Zed Newman"]');
      ok('people: Paste from Excel fills the details by name, lowers the count of those who need details, and adds a new person', !!sam && /sam\.rivers@example\.com/.test(sam.textContent) && /Delivery lead/.test(sam.textContent) && $('#ppCount').textContent !== cnt0 && !!zed && /Sponsor/.test(zed.textContent));
      ok('people: the owner pickers still work on names', C.people().includes('Sam Rivers') && !C.people().includes('Zed Newman') && $$('#ppTable tbody tr').length === rows.length + 1);
      await undo(); ok('people: Undo takes the paste back', $('#ppCount').textContent === cnt0 && !$('[data-person="Zed Newman"]')); }
    /* Help */
    { const missing = []; for (const id of ['howto-check-before-you-publish', 'howto-find-a-past-publication', 'howto-start-from-last-report', 'howto-ask-the-client-for-something', 'howto-save-as-a-pdf', 'howto-add-people-details', 'ref-freshness', 'ref-needs-from-you', 'ref-since-last-report', 'ref-published-reports', 'ref-people']) { C.help.open(id); await sleep(90); if (!$('#hp-' + id)) missing.push(id); }
      ok('help: each of the new features has its entry' + (missing.length ? ' (missing: ' + missing.join(', ') + ')' : ''), !missing.length);
      C.help.open('ref-sections'); await sleep(90); ok('help: the sections table lists Needs from you', /Needs from you/.test($('#hp-ref-sections').textContent));
      /* opened at Section templates, a place the product's Help also has; the prototype's Needs from you entry is drawn beside it */
      C.help.open('ref-section-templates'); await sleep(90); ok('help: the Needs from you entry explains Overdue, Archive and the place after At a glance', (t => /Overdue/.test(t) && /Archive/.test(t) && /Restore/.test(t) && /straight after At a glance/.test(t) && /Nothing needed from you this week\./.test(t))($('#hp-ref-needs-from-you').textContent)); }
    C.go('dashboard'); await sleep(80); click($('[data-mode=view]')); await sleep(60);
  });

  /* ════ the UX sweep (the accepted fixes and all ten enrichments) ════ */
  await step('Needs from you (#144)', async () => {
    const DB = window.ClarkDB, A = n => DB.addDays(DB.TODAY, n), pub = async () => new DOMParser().parseFromString(await C.webPage({ n: 98 }), 'text/html');
    const waitFor = async (f, ms = 6000) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await sleep(60); return !!f(); };
    const atW = async (w, f) => { document.title = 'SELFTEST-W:' + w; if (!await waitFor(() => window.__w === w)) { out.push('SKIP ' + w + ' px checks: the runner gave no such window'); return false; } await sleep(250);
      try { await f(); } finally { document.title = 'SELFTEST-W-END'; await waitFor(() => !window.__w); await sleep(200); } return true; };
    C.setProject('PDF'); C.go('dashboard'); await sleep(80); if ($('[data-mode=edit]')) { click($('[data-mode=edit]')); await sleep(80); }
    let nx = P().report.sections.find(x => x.type === 'needs');
    if (!nx) { click($('[data-addbelow=summary]')); await sleep(120); click($('.atd-c[data-t=needs]')); await sleep(30); click($('#atdGo')); await sleep(160); nx = P().report.sections.find(x => x.type === 'needs'); }
    const box = () => $('[data-sec="' + nx.id + '"]'), sec = () => P().report.sections.find(x => x.id === nx.id) || {};
    /* the template, in the Add a section box at its place among the others */
    click($('[data-addbelow=summary]')); await sleep(120);
    { const ts = $$('.atd-c').map(e => e.dataset.t), c = $('.atd-c[data-t=needs]');
      ok('needs 144: the Add a section box offers Needs from you at its place, straight after Work items list', !!c && /Needs from you/.test(c.textContent) && ts.indexOf('needs') === ts.indexOf('wi-list') + 1 && C.templates.findIndex(t => t.id === 'needs') === C.templates.findIndex(t => t.id === 'wi-list') + 1, ts.join()); }
    key($('#dlg'), 'Escape'); await sleep(60); if ($('#dlg') && $('#dlg').open) $('#dlg').close();
    /* each line: owner and a due date as DD-MM-YYYY; a late one says Overdue in words */
    const d8 = item('PDF-D-008'), was = { due: d8.due, client: d8.client, status: d8.status }; DB.change('item', d8, { due: A(-3), client: true, status: 'Pending' }); C.refresh(); await sleep(80);
    { const li = box().querySelector('[data-row="PDF-D-008"]');
      ok('needs 144: an open client-visible pending decision is listed with its owner and a due date as DD-MM-YYYY', !!li && li.textContent.includes(d8.owner) && /Needed by \d\d-\d\d-\d{4}/.test(li.textContent));
      ok('needs 144: a late line says Overdue in words, not by colour alone', !!li && !!li.querySelector('.tag.od') && li.querySelector('.tag.od').textContent === 'Overdue' && /Overdue/.test(li.textContent));
      const fut = [...box().querySelectorAll('.wl-row')].find(r => !/Overdue/.test(r.textContent) && /Needed by/.test(r.textContent));
      ok('needs 144: a line not yet due has no Overdue word', !fut || !fut.querySelector('.tag.od')); }
    { const h = await pub(); ok('needs 144: the published line keeps the word Overdue', /Overdue/.test((h.querySelector('#sec-' + nx.id) || {}).textContent || '')); }
    DB.change('item', d8, { client: false }); C.refresh(); await sleep(80);
    ok('needs 144: a decision the client cannot see is not listed', !box().querySelector('[data-row="PDF-D-008"]'));
    DB.change('item', d8, was); C.refresh(); await sleep(80);
    /* a line added by hand: what, owner, due; archived, never deleted */
    { const f = box().querySelector('[data-nd-add]'); ok('needs 144: in Edit the section has a form to add a line: what is needed, owner, due', !!f && !!f.what && !!f.owner && !!f.due);
      /* Due is clark's own date picker, not the browser's date box, so it reads DD-MM-YYYY */
      ok('needs 144: the Due box is clark\'s own picker, not the browser\'s date box', !f.querySelector('input[type=date]') && !!f.querySelector('[data-nd-due]') && f.querySelector('[data-nd-due]').textContent.trim() === 'No date set');
      click(f.querySelector('[data-nd-due]')); await sleep(60); ok('needs 144: Due opens clark\'s one-panel calendar', !!$('.menu .cp') && !$('.menu input[type=date]'));
      for (let k = 0; k < 24 && !$('.menu [data-cp="' + A(-2) + '"]'); k++) { click($('.menu [data-cpm="' + (A(-2) < DB.TODAY.slice(0, 7) ? -1 : 1) + '"]')); await sleep(20); }
      click($('.menu [data-cp="' + A(-2) + '"]')); await sleep(60);
      ok('needs 144: the picked date shows as DD-MM-YYYY in the Due box', !$('.menu') && f.due.value === A(-2) && f.querySelector('[data-nd-due]').textContent.trim() === DB.fd(A(-2)) && /^\d\d-\d\d-\d{4}$/.test(DB.fd(A(-2))));
      /* an empty "What is needed" gets clark's own line, not the browser's warning */
      ok('needs 144: the form leaves the browser\'s own warning off', f.noValidate && !f.what.required);
      f.querySelector('[type=submit]').click(); await sleep(100);
      { const f2 = box().querySelector('[data-nd-add]'), er = f2.querySelector('.nd-err');
        ok('needs 144: with nothing in What is needed, clark says so in its own words and adds nothing', !!er && !er.hidden && er.textContent === 'Say what is needed, then press Add.' && f2.what.getAttribute('aria-invalid') === 'true' && !(sec().asks || []).length); }
      f.what.value = 'Confirm the room for the go-live briefing'; f.what.dispatchEvent(new Event('input')); ok('needs 144: typing in What is needed clears the line', f.querySelector('.nd-err').hidden);
      f.owner.value = 'Client sponsor'; f.querySelector('[type=submit]').click(); await sleep(140); }
    const ask = () => (sec().asks || [])[0];
    { const li = box().querySelector('[data-ask]');
      ok('needs 144: the added line is listed with its owner, its date as DD-MM-YYYY and the word Overdue', !!ask() && !!li && /Confirm the room/.test(li.textContent) && /Client sponsor/.test(li.textContent) && li.textContent.includes('Needed by ' + DB.fd(A(-2))) && li.querySelector('.tag.od').textContent === 'Overdue');
      ok('needs 144: a line has Archive and no Delete', !!li.querySelector('[data-nd-arch]') && li.querySelector('[data-nd-arch]').textContent.trim() === 'Archive' && !/Delete/.test(li.textContent)); }
    { const t = C.tocCounts(P(), sec()), em = $('[data-toc="' + nx.id + '"] em');
      ok('needs 144: the contents count says needed, not pending, and is still marked', /^\d+ needed$/.test(t) && (!em || (em.textContent === t && !!em.className)), t + ' / ' + (em ? em.className : 'no contents rail')); }
    /* a line with no owner says "Not assigned yet", not "No owner" */
    { const f = box().querySelector('[data-nd-add]'); f.what.value = 'Send the floor plan'; f.querySelector('[type=submit]').click(); await sleep(140);
      const li = [...box().querySelectorAll('[data-ask]')].find(r => /Send the floor plan/.test(r.textContent));
      ok('needs 144: a line with no owner says Not assigned yet', !!li && /Not assigned yet/.test(li.textContent) && !/No owner/.test(box().textContent));
      const id = (sec().asks || []).find(a => a.what === 'Send the floor plan').id; await undo(); await sleep(100); ok('needs 144: Undo takes the ownerless test line away again', !(sec().asks || []).some(a => a.id === id)); }
    click(box().querySelector('[data-nd-arch]')); await sleep(140);
    ok('needs 144: Archive takes the line off the list but keeps it, under Archived', sec().asks.length === 1 && ask().archived === true && !box().querySelector('[data-ask]') && /Archived \(1\)/.test(box().querySelector('.nd-arch summary').textContent));
    { const h = await pub(); ok('needs 144: an archived line is not published', !/Confirm the room/.test(h.body.textContent)); }
    box().querySelector('.nd-arch').open = true; click(box().querySelector('[data-nd-back]')); await sleep(140);
    ok('needs 144: Restore brings the line back', ask().archived === false && !!box().querySelector('[data-ask]') && !box().querySelector('.nd-arch'));
    /* on the published page: straight after At a glance, whatever its place in the editor */
    { const h = await pub(), ids = [...h.querySelectorAll('main section[id^="sec-"], section[id^="sec-"]')].map(e => e.id).filter((v, i, a) => a.indexOf(v) === i), g = ids.indexOf('sec-glance');
      const ed = P().report.sections.map(x => x.id);
      ok('needs 144: in the editor it is not after At a glance, yet on the published page it is', ed.indexOf(nx.id) !== ed.indexOf('glance') + 1 && g >= 0 && ids[g + 1] === 'sec-' + nx.id, ids.join()); }
    /* empty: a quiet line in the editor, absent from the published page */
    const listed = C.needsList(P()), keep = listed.map(x => [x, x.client]); listed.forEach(x => { x.client = false; }); ask().archived = true; C.refresh(); await sleep(80);
    ok('needs 144: with nothing to ask the editor shows the quiet line', /Nothing needed from you this week\./.test(box().textContent) && !!box().querySelector('.nd-none.muted'));
    { const h = await pub(); ok('needs 144: with nothing to ask the section is absent from the published page and its contents', !h.querySelector('#sec-' + nx.id) && !/Needs from you/.test(h.body.textContent)); }
    keep.forEach(([x, c]) => { x.client = c; }); ask().archived = false; C.refresh(); await sleep(80);
    /* the section itself: Delete section, with Undo */
    click(box().querySelector('[data-opts]')); await sleep(60); await menuPick('Delete section'); await sleep(120);
    ok('needs 144: Delete section removes the section, with an Undo in the toast', !P().report.sections.some(x => x.id === nx.id) && !!$('#toastUndo'));
    await undo(); await sleep(80); ok('needs 144: Undo brings the section back with its lines', !!box() && (sec().asks || []).length === 1);
    /* light, dark and 900 px: readable, nothing sideways */
    const look = () => { const b = box(), od = b.querySelector('.tag.od'), f = b.querySelector('.nd-add'), inp = f.querySelector('input'), r = f.getBoundingClientRect();
      return { side: document.documentElement.scrollWidth <= innerWidth + 1 && b.scrollWidth <= b.clientWidth + 1 && r.right <= b.getBoundingClientRect().right + 1, od: !!od && getComputedStyle(od).color !== getComputedStyle(od).backgroundColor, inp: getComputedStyle(inp).color !== getComputedStyle(inp).backgroundColor }; };
    const was2 = C.themePref();
    for (const th of ['light', 'dark']) { C.theme(th); C.refresh(); await sleep(300); const l = look(); ok(`needs 144: in ${th} the Overdue word and the form are readable, and nothing scrolls sideways`, l.side && l.od && l.inp, JSON.stringify(l)); }
    await atW(900, async () => { for (const th of ['light', 'dark']) { C.theme(th); C.refresh(); await sleep(300); const l = look(); ok(`needs 144: at 900 px in ${th}, nothing scrolls sideways`, l.side && l.od && l.inp, JSON.stringify(l)); } });
    C.theme(was2); C.refresh(); await sleep(200);
    /* leave the demo as it was */
    { const k = P().report.sections.findIndex(x => x.id === nx.id); if (k >= 0) { const r2 = DB.clone(P().report); (r2.sections[k].asks || []).forEach(x => { x.archived = true; }); DB.change('project', P(), { report: r2 }); } C.refresh(); await sleep(60); }
    if ($('[data-mode=view]')) { click($('[data-mode=view]')); await sleep(60); }
  });

  await step('UX sweep fixes', async () => {
    const DB = window.ClarkDB, rect = e => (typeof e === 'string' ? $(e) : e).getBoundingClientRect(), vis = e => !!e && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 0;
    const waitFor = async (f, ms = 6000) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await sleep(60); return !!f(); };
    /* a window of another width, or with reduced motion on, asked of the runner (see run_selftest.py) */
    const atW = async (w, f) => { document.title = 'SELFTEST-W:' + w; if (!await waitFor(() => window.__w === w)) { out.push('SKIP ' + w + ' px checks: the runner gave no such window'); return false; } await sleep(250);
      try { await f(); } finally { document.title = 'SELFTEST-W-END'; await waitFor(() => !window.__w); await sleep(200); } return true; };
    const reduced = async f => { document.title = 'SELFTEST-REDUCE'; if (!await waitFor(() => window.__reduce)) { out.push('SKIP reduced-motion checks: the runner could not set it'); return false; } const was = C.reduce; C.reduce = true; await sleep(100);
      try { await f(); } finally { C.reduce = was; document.title = 'SELFTEST-REDUCE-END'; await waitFor(() => !window.__reduce); await sleep(150); } return true; };
    const cs = (e, p, pseudo) => getComputedStyle(typeof e === 'string' ? $(e) : e, pseudo)[p], css = window.CLARK_APPCSS;
    const toView = async () => { click($('.tab[data-view=dashboard]')); await sleep(120); if ($('[data-mode=view]')) { click($('[data-mode=view]')); await sleep(80); } };

    /* ── #1 Option A: the circle says what is behind it ── */
    ok('#1 the profile circle has a tooltip and an accessible name: Your menu: Publish, Preview, Export, Settings', $('#meBtn').title === 'Your menu: Publish, Preview, Export, Settings' && $('#meBtn').getAttribute('aria-label') === 'Your menu: Publish, Preview, Export, Settings');
    ok('#1 and Publish is still only in that menu, not on the page', !$('#pubBtn') && !$('#pubOpen'));

    /* ── #2 the section handle: the handle is left as is (finding D1), so nothing is changed and nothing is tested here ── */
    /* ── #3 Settings at 390 px: no sideways scroll, a card per row ── */
    await atW(390, async () => { C.go('settings'); await sleep(250);
      ok('#3 Settings at 390 px: no sideways page scroll', document.documentElement.scrollWidth <= innerWidth, document.documentElement.scrollWidth);
      const trs = $$('table.set.stack tbody tr'); ok('#3 the Projects and People tables are stacked rows (a card each, label beside each value)', $$('table.set.stack').length >= 2 && trs.length >= 6 && trs.every(t => cs(t, 'display') === 'block') && $$('table.set.stack td[data-l]').length > 10 && /Code|Email/.test(cs($('table.set.stack td[data-l]'), 'content', '::before')));
      ok('#3 every table and its Edit button sit inside the window', $$('table.set').every(t => rect(t).right <= innerWidth + .5) && $$('[data-pe]').every(b => rect(b).right <= innerWidth && rect(b).left >= 0));
      ok('#3 the column headings stay for a screen reader (hidden by clipping, not removed)', cs($('table.set.stack thead'), 'position') === 'absolute' && $('table.set.stack thead th').textContent === 'Name');
      ok('#3 the table cells are not wider than the window', $$('table.set td').every(t => rect(t).right <= innerWidth + .5)); });
    C.go('dashboard'); await sleep(100);

    /* ── #4 and enrichment 1: Publish from the dialog: spinner, then a tick and "Published (Publication N)" ── */
    const publishRun = async label => {
      await toView(); const n = DB.pubNext(P()); C.publishDialog(); await sleep(80);
      ok(label + ' the Publish button is ready: Publish locally', $('#pubGo').textContent.trim() === 'Publish locally' && !$('#pubGo').disabled);
      $('#pubF').requestSubmit();
      ok(label + ' at once the button shows a spinner and "Publishing…", is busy, and the dialog stays open', !!$('#pubGo .spin') && /Publishing…/.test($('#pubGo').textContent) && $('#pubGo').disabled && $('#pubGo').getAttribute('aria-busy') === 'true' && $('#dlg').open && $('#dlg [data-close]').disabled);
      if (!C.reduce) { await sleep(200); ok(label + ' it is still working a little later (the demo wait)', !!$('#pubGo .spin') && $('#dlg').open); }
      const got = await waitFor(() => $('#pubGo .tick'), 8000);
      ok(label + ' then a tick and "Published (Publication ' + n + ')"', got && $('#pubGo').textContent.trim() === 'Published (Publication ' + n + ')' && $('#pubGo').classList.contains('ok') && !$('#pubGo').hasAttribute('aria-busy') && !$('#pubGo .spin'), $('#pubGo').textContent);
      await sleep(350); ok(label + ' the tick is drawn (its line fully shown) and the button is green', cs($('#pubGo .tick path'), 'strokeDashoffset') === '0px' && cs($('#pubGo'), 'backgroundColor') === (() => { const pr = document.createElement('i'); pr.style.background = 'var(--status-green)'; document.body.appendChild(pr); const c = getComputedStyle(pr).backgroundColor; pr.remove(); return c; })());
      ok(label + ' the publication is recorded under that number', P().published.slice(-1)[0].n === n);
      await waitFor(() => !$('#dlg').open, 3000); ok(label + ' the dialog closes by itself after the tick', !$('#dlg').open);
      ok(label + ' the toast keeps the record', /Publication \d+/.test($('#toastMsg').textContent), $('#toastMsg').textContent); };
    await publishRun('#4');
    C.publishDialog(); await sleep(60); { const t = $('#dlg').textContent; ok('#7 the Publish dialog has no file path in its copy', !/~\/|Documents\/clark|\/Reports/.test(t)); }
    $('#dlg').close(); await sleep(60);
    await reduced(() => publishRun('enrichment 1 (reduced motion)'));
    ok('enrichment 1 the tick and button colour use the tokens (--dur-state, --ease-out, --status-green)', /\.btn \.tick path \{[^}]*animation: tick var\(--dur-state\) var\(--ease-out\) forwards/.test(css) && /\.btn\.pri\.ok \{ background: var\(--status-green\)/.test(css));

    /* ── #5 Work items on a phone ── */
    await atW(390, async () => { C.go('work'); await sleep(250); if ($('#clearAll')) { click($('#clearAll')); await sleep(80); }
      ok('#5 Work items at 390 px: no sideways page scroll', document.documentElement.scrollWidth <= innerWidth);
      ok('#5 the type switch, Group by and Filter by are folded behind one Filters button', vis($('#fToggle')) && !vis($('[aria-label=Type]')) && !vis($('#groupBtn')) && !vis($('.fbar')) && $('#fToggle').getAttribute('aria-expanded') === 'false');
      click($('#fToggle')); await sleep(80); ok('#5 the Filters button opens them all', vis($('[aria-label=Type]')) && vis($('#groupBtn')) && vis($('.fbar')) && $('#fToggle').getAttribute('aria-expanded') === 'true');
      click($('[data-type=A]')); await sleep(60); ok('#5 the Filters button counts what is set', !$('#fToggle .n').hidden && $('#fToggle .n').textContent === '1'); click($('[data-type=all]')); await sleep(60); click($('#fToggle')); await sleep(60);
      const tr = $('tr[data-id]'), td = i => tr.children[i], inW = e => vis(e) && rect(e).left >= 0 && rect(e).right <= innerWidth + .5;
      ok('#5 each item is a card row with Status, Due and Priority showing inside the window', cs(tr, 'display') === 'grid' && inW(td(4).firstElementChild) && inW(td(2).firstElementChild) && inW(td(3).firstElementChild) && /Due/.test(cs(td(2).firstElementChild, 'content', '::before')) && /Priority/.test(cs(td(3).firstElementChild, 'content', '::before')));
      ok('#5 the card row shows the status pill, the owner, and the item title', !!td(4).querySelector('.pill') && /\w/.test(td(1).textContent) && /\w/.test(td(0).textContent));
      ok('#5 no table scrolls sideways inside its group', $$('.gbody > div').every(e => e.scrollWidth <= e.clientWidth + 1));
      ok('#5 the first item is on the first screen', rect(tr).top < 700, Math.round(rect(tr).top)); });
    C.go('work'); await sleep(100);

    /* ── #6 the timeline: no two labels meet, the Today line goes behind the words, the Today label clears them ── */
    const meets = (host, sel = '.mv-lab') => { const L = [...host.querySelectorAll(sel)].map(e => [e.textContent.slice(0, 18), e.getBoundingClientRect()]), hit = [];
      for (let i = 0; i < L.length; i++) for (let j = i + 1; j < L.length; j++) { const a = L[i][1], b = L[j][1]; if (a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5) hit.push(L[i][0] + ' x ' + L[j][0]); } return hit; };
    C.go('milestones'); await sleep(300); { const w = $('.mv-wrap'), labs = $$('.mv-lab', w), tb = rect($('.mv-today b', w));
      ok('#6 Milestones: the labels are there, and none overlaps another (bounding boxes)', labs.length >= 6 && !meets(w).length, meets(w).join(' | '));
      ok('#6 the Today label clears every milestone label', labs.every(l => { const b = l.getBoundingClientRect(); return !(tb.left < b.right && b.left < tb.right && tb.top < b.bottom && b.top < tb.bottom); }));
      ok('#6 the labels sit above the Today line, on a chip, so the line passes behind the words', parseInt(cs(labs[0], 'zIndex')) > parseInt(cs($('.mv-today', w), 'zIndex')) && cs(labs[0], 'backgroundColor') !== 'rgba(0, 0, 0, 0)'); }
    { const host = document.createElement('div'); host.style.cssText = 'position:absolute;left:0;top:0;width:900px;visibility:hidden'; document.body.appendChild(host);
      const base = C.mss()[0], names = ['Training plan agreed by everyone', 'Second source loaded and checked', 'User testing starts early', 'Pilot go-live', 'Sign-off from the steering group', 'Handover to operations'];
      const fake = names.map((n, i) => ({ ...base, id: 'T' + i, name: n, agreed: DB.addDays(DB.TODAY, i - 1), forecast: DB.addDays(DB.TODAY, i - 1 + (i % 2 ? 4 : 0)), achievedOn: '', manual: '' }));
      C.timeline(host, fake, { key: 'selftest' }); await sleep(60);
      ok('#6 a crowded line (six long names within days, with Expected labels), as the published page draws it: no two labels overlap', $$('.mv-lab', host).length >= 9 && !meets(host).length, meets(host).join(' | ') + ' of ' + $$('.mv-lab', host).length);
      const tb = $('.mv-today b', host).getBoundingClientRect(); ok('#6 and the Today label clears them too', $$('.mv-lab', host).every(l => { const b = l.getBoundingClientRect(); return !(tb.left < b.right && b.left < tb.right && tb.top < b.bottom && b.top < tb.bottom); }));
      host.remove(); }
    ok('#6 the published page takes the chips and layers from the same style sheet', /\.mv-lab \{[^}]*z-index: 3[^}]*background: var\(--grey-50\)/.test(css));
    ok('#6 msvWire and the page script carry no backtick or template placeholder (they are copied as text)', !/[`]|\$\{/.test(C.MSV_JS));
    C.go('dashboard'); await sleep(100);

    /* ── #7 copy ── */
    ok('#7 "1 day", "2 days": one helper for the plural', C.dy(1) === '1 day' && C.dy(2) === '2 days' && C.dy(0) === '0 days');
    { const it = item('PDF-A-012'), u1 = DB.change('item', it, { due: DB.addDays(DB.TODAY, -1) }, DB.who('in the test')); C.openItem(it.id, [it.id]); await sleep(120); const w1 = ($('#peek .pk-warn') || {}).textContent || '';
      const u2 = DB.change('item', it, { due: DB.addDays(DB.TODAY, -2) }, DB.who('in the test')); C.refresh(); await sleep(80); const w2 = ($('#peek .pk-warn') || {}).textContent || ''; C.closePeek(); u2(); u1(); await sleep(60);
      ok('#7 the peek says "1 day overdue" (not "1 days") and "2 days overdue"', /\b1 day overdue/.test(w1) && !/1 days/.test(w1) && /2 days overdue/.test(w2), w1 + ' | ' + w2); }
    { C.go('dashboard'); await sleep(100); click($('[data-mode=edit]')); await sleep(100); const q = id => { const r = P().report.sections.find(s => s.id === id); return r; };
      const ph = id => { const el = $(`[data-txt=${id}]`); return el ? el.textContent.trim() : null; };
      const nx = q('nextweek'), tw = q('thisweek'), a1 = nx && nx.html, a2 = tw && tw.html; P().report.sections.find(s => s.id === 'nextweek').html = ''; P().report.sections.find(s => s.id === 'thisweek').html = ''; C.refresh(); await sleep(120);
      ok('#7 Next week has its own placeholder, not "this week"', ph('nextweek') === 'Say what is planned for next week' && ph('thisweek') === 'Say what matters this week', ph('nextweek') + ' | ' + ph('thisweek'));
      P().report.sections.find(s => s.id === 'nextweek').html = a1; P().report.sections.find(s => s.id === 'thisweek').html = a2; await toView(); }
    C.go('work'); await sleep(150); { const qi = $('#q'); qi.value = 'zzzz'; qi.dispatchEvent(new Event('input', { bubbles: true })); await sleep(120);
      const e = $('#wlist .empty'), ctl = $$('#wlist button, #wlist .link, .factive .link').filter(vis).filter(b => /Clear|Show/.test(b.textContent));
      ok('#7 a search that finds nothing says why ("No open items match “zzzz”.")', !!e && /No open items match “zzzz”\./.test(e.textContent), e && e.textContent);
      ok('#7 and has one clear control (Clear search), not two', ctl.length === 1 && ctl[0].textContent.trim() === 'Clear search' && !$('.factive #clearAll'), ctl.map(b => b.textContent).join('|'));
      click(ctl[0]); await sleep(100); ok('#7 the control clears it and the items return', $$('tr[data-id]').length > 5 && $('#q').value === '');
      click($('[data-show=closed]')); click($('[data-type=D]')); await sleep(100); { const e2 = $('#wlist .empty'); ok('#7 a filter with no match says it is the filters, with the one control', !e2 || (/these filters|this type/.test(e2.textContent) && $$('#wlist button#clearAll, #clearAll').length === 1), e2 && e2.textContent); }
      if ($('#clearAll')) { click($('#clearAll')); await sleep(100); } }
    C.go('settings'); await sleep(150); { const t = $$('#main p, #main small, #main label, #main .fc, #main h2, #main h3').filter(e => !e.closest('.docs')).map(e => e.innerText).join('\n');
      ok('#7 Settings has no file path in its copy (no ~/ and no log folder path)', !/~\/|Library\/Logs|Documents\/clark/.test(t), (t.match(/.{20}~\/.{20}/) || [''])[0]); }
    C.go('dashboard'); await sleep(100);

    /* ── #9 minimum text size 12 px and target size 24 px, on the listed elements and everywhere on these screens ── */
    const scan = label => { const small = new Set(), tiny = new Set();
      $$('body *').forEach(e => { if (e.closest('[inert],[hidden],.sr,#toast,svg')) return; const c = getComputedStyle(e); if (c.display === 'none' || c.visibility === 'hidden') return; const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
        if ([...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(c.fontSize) < 11.99) small.add(e.tagName + '.' + String(e.className).slice(0, 30) + ' ' + c.fontSize);
        if ((e.matches('button,a[href],select,textarea,[role=button],[role=switch],.mv-mk,.switch') || (e.matches('input:not([type=hidden]):not([type=checkbox]):not([type=radio]):not([type=range])'))) && c.position !== 'absolute' && (r.width < 23.5 || r.height < 23.5)) tiny.add(e.tagName + '.' + String(e.className).slice(0, 30) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (e.getAttribute('aria-label') || e.textContent.trim()).slice(0, 20)); });
      return { small: [...small], tiny: [...tiny], label }; };
    const bad = []; const chk = (label) => { const s = scan(label); if (s.small.length || s.tiny.length) bad.push(label + ': ' + [...s.small.map(x => 'text ' + x), ...s.tiny.map(x => 'target ' + x)].join('; ')); };
    await toView(); chk('dashboard'); click($('[data-mode=edit]')); await sleep(150); chk('dashboard in Edit'); await toView();
    C.go('work'); await sleep(200); chk('work table'); click($('[data-layout=board]')); await sleep(200); chk('work board'); click($('[data-layout=table]')); await sleep(150);
    C.openItem('PDF-A-012', ['PDF-A-012']); await sleep(300); chk('item peek'); { const sw = $('#peek .switch'); ok('#9 the "Needed from the client" switch is at least 44 by 24', !!sw && rect(sw).width >= 43.5 && rect(sw).height >= 23.5, sw && Math.round(rect(sw).width) + 'x' + Math.round(rect(sw).height)); } C.closePeek(); await sleep(250);
    C.go('milestones'); await sleep(250); if ($('[data-msvb=line]')) { click($('[data-msvb=line]')); await sleep(150); } chk('milestones'); { const mk = $$('.mv-mk'); ok('#9 the milestone markers are at least 24 by 24 (the drawing keeps its size)', mk.length >= 6 && mk.every(m => rect(m).width >= 23.5 && rect(m).height >= 23.5) && rect($('.mv-mk svg')).width <= 21); }
    click($('[data-msvb=cal]')); await sleep(200); click($('[data-calv-b=quarter]')); await sleep(150); chk('milestone calendar, quarter'); click($('[data-calv-b=month]')); click($('[data-msvb=line]')); await sleep(100);
    C.go('settings'); await sleep(250); chk('settings');
    await toView(); click($('[data-mode=edit]')); await sleep(100); click($('.sh-ctl .sh-add')); await sleep(300); chk('Add a section'); $('#dlg').close(); await sleep(60);
    C.publishDialog(); await sleep(150); chk('Publish dialog'); $('#dlg').close(); await sleep(60);
    ok('#9 every text is at least 12 px and every button, link and switch at least 24 px, on every screen scanned' + (bad.length ? ' (' + bad.join(' || ').slice(0, 600) + ')' : ''), !bad.length);
    ok('#9 the type sizes under 12 px are gone from the style sheet, the Help style sheet and the published page', !/font-size: *(9|10|10\.5|11)px/.test(css) && !/font:[^;]*\b(10|11)px/.test(css) && /--fs-xs: 12px; --fs-s: 13px/.test(css) && !/font-size:(9|10|10\.5|11)px/.test(await C.webPage()));
    await toView();

    /* ── #10 Add a section on a phone ── */
    await atW(390, async () => { click($('.tab[data-view=dashboard]')); await sleep(150); click($('[data-mode=edit]')); await sleep(150); click($('.sh-ctl .sh-add')); await sleep(350);
      const d = $('#dlg'), k = $('#atdK'), chips = $$('#atdK [data-k]'), g = $$('.atd-c');
      ok('#10 the kinds are one row of chips along the top (all at the same height, scrolling sideways)', cs(k, 'display') === 'flex' && cs(k, 'overflowX') === 'auto' && chips.length >= 7 && Math.max(...chips.map(c => rect(c).top)) - Math.min(...chips.map(c => rect(c).top)) < 2);
      ok('#10 the first templates show without scrolling (the first card ends inside the window)', g.length >= 4 && rect(g[0]).bottom <= innerHeight && rect(g[1]).bottom <= innerHeight && rect(g[2]).bottom <= innerHeight, Math.round(rect(g[0]).bottom) + ' of ' + innerHeight);
      ok('#10 "Recently used" waits (not shown in the chip row), and the search is a single line', !vis($('#atdRL')) && rect('.atd-h h2').height < 30);
      ok('#10 the footer link is one short word and the dialog fits the window', vis($('.atd-short')) && !vis($('.atd-long')) && rect($('.atd-f .link')).height < 34 && rect(d).left >= 0 && rect(d).right <= innerWidth && document.documentElement.scrollWidth <= innerWidth);
      click(chips[3]); await sleep(80); ok('#10 a chip still filters the templates', chips[3].getAttribute('aria-pressed') === 'true' && $$('.atd-c').length < 20);
      d.close(); await sleep(60); });
    await toView();

    /* ── enrichment 2: first-load skeletons ── */
    ok('enrichment 2 on first load the page was already holding skeletons while the data loaded', C.skelAtStart === true);
    for (const v of ['dashboard', 'work', 'milestones', 'settings']) { C.showSkeleton(v); await sleep(30);
      ok(`enrichment 2 skeleton for ${v}: grey blocks in the page's shape, and busy, hidden for the first 150 ms`, $$('#main .skel').length >= 5 && $('#main').classList.contains('loading') && $('#main').getAttribute('aria-busy') === 'true' && cs($('#main .skel-wrap'), 'opacity') === '0' && $$('#main .skel').every(b => rect(b).height > 0 && cs(b, 'borderRadius') !== '0px'), $$('#main .skel').length); }
    C.showSkeleton('work'); await sleep(260);
    ok('enrichment 2 after 150 ms the skeleton shows, in the work item row shape (rows with a small square, a line and pills)', cs($('#main .skel-wrap'), 'opacity') === '1' && $$('#main .sk-row').length >= 6 && $$('#main .sk-row .sk-sq').length >= 6 && $('#main').classList.contains('skel-on'));
    ok('enrichment 2 with motion allowed the shimmer is a gentle 2.6 s sweep on the grey blocks', cs($('#main .skel'), 'animationName') === 'skel-sh' && cs($('#main .skel'), 'animationDuration') === '2.6s' && !/rgba|#[0-9a-f]{3,6}/i.test(css.slice(css.indexOf('.skel {'), css.indexOf('.skel {') + 130).replace(/var\([^)]*\)/g, '')));
    await reduced(async () => { ok('enrichment 2 with reduced motion the skeleton is still (no shimmer)', cs($('#main .skel'), 'animationName') === 'none'); });
    C.showSkeleton('dashboard'); await sleep(260); ok('enrichment 2 the dashboard skeleton is a cover, tiles and section cards', !!$('#main .sk-cover') && $$('#main .sk-tile').length === 3 && $$('#main .sk-card').length === 2);
    C.render(); await sleep(60);
    ok('enrichment 2 once the data is there, the skeleton is gone and the page is not busy', !$('#main .skel') && !$('#main').classList.contains('loading') && !$('#main').hasAttribute('aria-busy') && !!$('.sheet'));

    /* ── enrichment 3: a changed row survives reduced motion ── */
    C.go('work'); await sleep(200); if ($('#clearAll')) { click($('#clearAll')); await sleep(80); } click($('[data-show=open]')); await sleep(80); $$('.ghead[aria-expanded=false]').forEach(h => click(h)); await sleep(60); const R = $$('tr[data-id]').map(r => r.dataset.id);
    { const tr = $(`tr[data-id="${R[0]}"]`), td = tr.querySelector('td'); C.reduce = false; C.changed(tr);
      ok('enrichment 3 with motion allowed a changed row flashes (1 s), with no marker', tr.classList.contains('flash') && !tr.querySelector('.chg-tag') && cs(td, 'animationName') === 'flash' && cs(td, 'animationDuration') === '1s');
      await sleep(1700); ok('enrichment 3 and the flash class is let go after about 1.5 s', !tr.classList.contains('flash')); }
    await reduced(async () => { const tr = $(`tr[data-id="${R[1]}"]`), td = tr.querySelector('td'), probe = document.createElement('i'); probe.style.background = 'var(--flash)'; document.body.appendChild(probe); const tint = getComputedStyle(probe).backgroundColor; probe.remove();
      C.changed(tr); await sleep(60);
      ok('enrichment 3 with reduced motion the row gets a still tint (the --flash colour) and no animation', tr.classList.contains('chg-static') && !tr.classList.contains('flash') && cs(td, 'backgroundColor') === tint && td.getAnimations().length === 0, cs(td, 'backgroundColor') + ' vs ' + tint);
      ok('enrichment 3 and a small "Changed" marker', !!tr.querySelector('.chg-tag') && tr.querySelector('.chg-tag').textContent === 'Changed' && parseFloat(cs(tr.querySelector('.chg-tag'), 'fontSize')) >= 12);
      await sleep(2000); ok('enrichment 3 it is still there after 2 s', tr.classList.contains('chg-static') && !!tr.querySelector('.chg-tag'));
      await sleep(1300); ok('enrichment 3 and gone after about 3 s', !tr.classList.contains('chg-static') && !tr.querySelector('.chg-tag') && cs(td, 'backgroundColor') !== tint);
      const t3 = $(`tr[data-id="${R[2]}"]`); t3.classList.add('flash'); await sleep(40); ok('enrichment 3 and even a plain flash class shows the still tint under the media query', t3.querySelector('td').getAnimations().length === 0 && cs(t3.querySelector('td'), 'backgroundColor') === tint); t3.classList.remove('flash'); });
    { const it = item(R[0]), was = it.priority, to = was === 'Low' ? 'Medium' : 'Low'; C.reduce = false; click($(`[data-pick="${R[0]}"][data-prop=priority]`)); await sleep(60); await menuPick(to); await sleep(80);
      ok('enrichment 3 an edit made in the table (the priority picker) flashes its row too', $(`tr[data-id="${R[0]}"]`).classList.contains('flash') && item(R[0]).priority === to); await undo(); }

    /* ── enrichment 4: stepping in the peek fades the body only ── */
    { const ids = [R[0], R[1]]; C.openItem(ids[0], ids); await sleep(350);
      ok('enrichment 4 the first open does not fade the body (the panel slides)', !$('#peek .pk-inner').classList.contains('swap'));
      ok('enrichment 4 the panel slide runs on tokens (--dur-state in, --dur-instant out)', /\.peek\.on \{ transform: none; transition: transform var\(--dur-state\) var\(--ease-enter\)/.test(css) && /translateX\(104%\); transition: transform var\(--dur-instant\) var\(--ease-exit\)/.test(css) && cs('#peek', 'transitionDuration').startsWith('0.22s'));
      click($('#pkNext')); await sleep(40); const bd = $('#peek .pk-inner');
      ok('enrichment 4 Next fades the body from .4 to 1 over 120 ms, once', bd.classList.contains('swap') && cs(bd, 'animationName') === 'pk-swap' && cs(bd, 'animationDuration') === '0.12s' && cs(bd, 'animationIterationCount') === '1');
      ok('enrichment 4 the panel itself stays still (no class, no animation)', !$('#peek').classList.contains('swap') && $('#peek').getAnimations().length === 0 && $('#peek').getAnimations({ subtree: false }).length === 0);
      C.reduce = true; click($('#pkPrev')); await sleep(40); ok('enrichment 4 with reduced motion there is no fade', !$('#peek .pk-inner').classList.contains('swap'));
      await reduced(async () => { C.reduce = true; click($('#pkNext')); await sleep(40); ok('enrichment 4 (reduced motion on) no fade on Next either, and no animation runs', !$('#peek .pk-inner').classList.contains('swap') && $('#peek .pk-inner').getAnimations().length === 0); });
      C.reduce = false; C.closePeek(); await sleep(250); }

    /* ── enrichment 5: the drop line and the half outline ease in ── */
    C.go('dashboard'); await sleep(150); click($('[data-mode=edit]')); await sleep(150);
    { const sec = $('.sbody .sec'), pair = $('.pair > .sec');
      sec.classList.add('drop-before'); const a = getComputedStyle(sec, '::before');
      ok('enrichment 5 the drop line fades and slides in over 120 ms (opacity and a 4 px rise)', a.animationName === 'drop-in' && a.animationDuration === '0.12s' && /drop-in \{ from \{ opacity: 0; transform: translateY\(-4px\)/.test(css));
      sec.classList.remove('drop-before'); pair.classList.add('drop-l'); const l = getComputedStyle(pair, '::before').left; pair.classList.remove('drop-l'); pair.classList.add('drop-r'); const rr = getComputedStyle(pair, '::before'), tp = rr.transitionProperty, td = rr.transitionDuration; await sleep(300);
      ok('enrichment 5 the half outline moves between left and right with a 120 ms transition on left (left: 0 and 50%)', l === '0px' && parseFloat(getComputedStyle(pair, '::before').left) > 50 && tp === 'left' && td === '0.12s', l + ' ' + getComputedStyle(pair, '::before').left + ' ' + tp + ' ' + td); pair.classList.remove('drop-r');
      ok('enrichment 5 the dragged section dims over 120 ms (.4)', /\.sec \{ transition: opacity var\(--dur-instant\) var\(--ease-out\); \} \.sec\.dragging \{ opacity: \.4; \}/.test(css) && cs(sec, 'transitionDuration') === '0.12s');
      await reduced(async () => { sec.classList.add('drop-before'); const b = getComputedStyle(sec, '::before'); ok('enrichment 5 with reduced motion the line appears at once (no animation, no transition)', b.animationName === 'none' && /^0(\.001)?s$/.test(b.transitionDuration), b.animationName + ' ' + b.transitionDuration); sec.classList.remove('drop-before'); }); }

    /* ── enrichment 6: the health badge settles ── */
    { const pick = async () => { const to = P().health === 'G' ? 'At risk' : 'On track'; click($('#hPill')); await sleep(50); await menuPick(to); await sleep(30); };
      C.reduce = false; await pick(); { const b = $('.health-fig .hpill');
        ok('enrichment 6 after a health change the new badge and its reason settle from .5 over 220 ms', b.classList.contains('settle') && cs(b, 'animationName') === 'settle' && cs(b, 'animationDuration') === '0.22s' && !!$('.health-fig #hReason.settle'), b.className); }
      await sleep(500); ok('enrichment 6 the class is let go (one shot)', !$('.settle')); await undo(); await sleep(100);
      C.reduce = true; await pick(); ok('enrichment 6 with reduced motion the new colour and reason simply appear (no class)', !$('.settle')); C.reduce = false; await undo(); await sleep(100); }

    /* ── enrichment 7: the timeline and calendar swap fades ── */
    C.go('milestones'); await sleep(250); { const msv = $('.msv'); $$('.vin').forEach(e => e.classList.remove('vin'));
      click($('[data-msvb=cal]')); await sleep(30); const cal = $('.msv-cal');
      ok('enrichment 7 switching to Calendar fades the view in over 220 ms with a 4 px rise', cal.classList.contains('vin') && cs(cal, 'animationName') === 'msv-in' && cs(cal, 'animationDuration') === '0.22s' && /msv-in \{ from \{ opacity: 0; transform: translateY\(4px\)/.test(css) && cs(cal, 'animationTimingFunction').startsWith('cubic-bezier(0.16'));
      click($('[data-calv-b=week]')); await sleep(30); const pane = $('.cal-m:not([hidden])'); ok('enrichment 7 Week, Month and Quarter fade the same way', pane.classList.contains('vin') && cs(pane, 'animationName') === 'msv-in'); click($('[data-calv-b=quarter]')); await sleep(30); ok('enrichment 7 (Quarter)', $('.cal-m:not([hidden])').classList.contains('vin')); click($('[data-calv-b=month]'));
      click($('[data-msvb=line]')); await sleep(30); ok('enrichment 7 and back to Timeline', $('.msv-line').classList.contains('vin'));
      C.refresh(); await sleep(80); ok('enrichment 7 a redraw in place does not replay it', !$('.vin'));
      await reduced(async () => { $$('.vin').forEach(e => e.classList.remove('vin')); click($('[data-msvb=cal]')); click($('[data-calv-b=week]')); await sleep(30); ok('enrichment 7 with reduced motion the view swaps at once (no class, no animation)', !$('.vin') && $('.msv-cal').getAnimations().length === 0); click($('[data-msvb=line]')); await sleep(30); }); }
    C.go('dashboard'); await sleep(100);

    /* ── enrichment 8: the first time in Edit, the handle shows itself once ── */
    { await toView(); C.store.set('editHintSeen', false); C.edHint = false; C.reduce = false; click($('[data-mode=edit]')); await sleep(60); const first = $('.sheet .sec > .sh-ctl');
      ok('enrichment 8 the first time in Edit the first grip and plus pulse once over 700 ms (rest, then 1 with a 3 px ring, then rest)', first.classList.contains('first') && cs(first, 'animationName') === 'nudge' && cs(first, 'animationDuration') === '0.7s' && cs(first, 'animationIterationCount') === '1' && /nudge \{ 0% \{ opacity: \.3; \} 40% \{ opacity: 1; box-shadow: 0 0 0 3px var\(--brand-blue-tint\)/.test(css) && $$('.sh-ctl.first').length === 1);
      ok('enrichment 8 the one-line hint "Drag to move, + to add a template" sits in the bar, and the profile remembers it was shown', /Drag to move, \+ to add a template/.test(($('#shHint') || {}).textContent || '') && C.store.get('editHintSeen', false) === true);
      click($('[data-mode=view]')); await sleep(60); click($('[data-mode=edit]')); await sleep(60);
      ok('enrichment 8 the next time in Edit there is no pulse, and the hint stays for the session', !$('.sh-ctl.first') && !!$('#shHint'));
      C.edHint = false; C.store.set('editHintSeen', false); click($('[data-mode=view]')); await sleep(40); C.reduce = true; click($('[data-mode=edit]')); await sleep(60);
      ok('enrichment 8 with reduced motion there is no pulse; the hint carries the message', !$('.sh-ctl.first') && !!$('#shHint')); C.reduce = false; C.edHint = false; }
    await toView();

    /* ── enrichment 9: the count line fades when a filter changes it ── */
    C.go('work'); await sleep(200); if ($('#clearAll')) { click($('#clearAll')); await sleep(80); } C.reduce = false;
    { const before = $('.factive > span').textContent; click($('[data-type=A]')); await sleep(30); const c = $('.factive > span');
      ok('enrichment 9 a filter that changes the count fades the count line from .4 to 1 over 120 ms', c.textContent !== before && c.classList.contains('n-chg') && cs(c, 'animationName') === 'pk-swap' && cs(c, 'animationDuration') === '0.12s', before + ' -> ' + c.textContent);
      await sleep(400); ok('enrichment 9 and lets go of the class', !$('.n-chg'));
      click($('[data-type=all]')); await sleep(30); C.reduce = true; click($('[data-type=D]')); await sleep(30); ok('enrichment 9 with reduced motion the numbers change at once (no class)', !$('.n-chg')); C.reduce = false; click($('[data-type=all]')); await sleep(60);
      ok('enrichment 9 the segment counts get the same one-shot class (the code and the style)', /n-chg \{ animation: pk-swap var\(--dur-instant\) var\(--ease-out\)/.test(css)); }

    /* ── enrichment 10: Add a section preview cross-fades; a card lifts on hover (fine pointers) ── */
    C.go('dashboard'); await sleep(150); click($('[data-mode=edit]')); await sleep(150); click($('.sh-ctl .sh-add')); await sleep(300);
    { C.reduce = false; const P2 = $('#atdP');
      ok('enrichment 10 opening the box does not fade the preview', !P2.classList.contains('swap'));
      key($('#atdQ'), 'ArrowRight'); await sleep(30); ok('enrichment 10 moving the selection cross-fades the preview from .4 to 1 over 120 ms', P2.classList.contains('swap') && cs(P2, 'animationName') === 'pk-swap' && cs(P2, 'animationDuration') === '0.12s');
      P2.classList.remove('swap'); C.reduce = true; key($('#atdQ'), 'ArrowRight'); await sleep(30); ok('enrichment 10 with reduced motion there is no fade', !P2.classList.contains('swap')); C.reduce = false;
      const fine = matchMedia('(hover: hover) and (pointer: fine)').matches, card = $('.atd-c');
      ok('enrichment 10 a card lifts 1 px with the --shadow token on hover, for fine pointers only, on 120 ms tokens' + (fine ? '' : ' (this window has no fine pointer: the style is checked, not the computed transition)'), /@media \(hover: hover\) and \(pointer: fine\) \{\s*\.atd-c \{ transition: transform var\(--dur-instant\) var\(--ease-out\), box-shadow var\(--dur-instant\) var\(--ease-out\)/.test(css) && /\.atd-c:hover \{ transform: translateY\(-1px\); box-shadow: var\(--shadow\); \}/.test(css) && (!fine || (cs(card, 'transitionProperty').includes('transform') && cs(card, 'transitionDuration').startsWith('0.12s'))));
      ok('enrichment 10 and with reduced motion there is no lift and no fade (the style sheet says so)', /prefers-reduced-motion: reduce\) \{[^}]*\.atd-p\.swap[^}]*animation: none; \}\s*\.atd-c:hover \{ transform: none; \}/.test(css));
      $('#dlg').close(); await sleep(60); }
    ok('the enrichments use only tokens for time and easing (no ms or cubic-bezier in the new rules)', !/(pk-inner\.swap|\.hpill\.settle|\.vin|\.sh-ctl\.first|\.n-chg|\.atd-p\.swap) \{ [^}]*(\d+ms|cubic-bezier)/.test(css));
    C.go('dashboard'); await sleep(100); click($('[data-mode=view]')); await sleep(60);
  });

  /* ═══ the screen-by-screen findings (#132, the accepted list), each measured in the page: sizes, ratios from computed colours, bounding boxes, no sideways scroll at 390 ═══ */
  await step('Screen-by-screen findings (#132)', async () => {
    const DB = window.ClarkDB, rect = e => (typeof e === 'string' ? $(e) : e).getBoundingClientRect(), shown = e => !!e && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden' && e.getBoundingClientRect().width > 0;
    const waitFor = async (f, ms = 6000) => { const t0 = Date.now(); while (!f() && Date.now() - t0 < ms) await sleep(60); return !!f(); };
    const atW = async (w, f) => { document.title = 'SELFTEST-W:' + w; if (!await waitFor(() => window.__w === w)) { out.push('SKIP ' + w + ' px checks: the runner gave no such window'); return false; } await sleep(250);
      try { await f(); } finally { document.title = 'SELFTEST-W-END'; await waitFor(() => !window.__w); await sleep(200); } return true; };
    const cs = (e, p, pseudo) => getComputedStyle(typeof e === 'string' ? $(e) : e, pseudo)[p], css = window.CLARK_APPCSS, today = DB.TODAY;
    const toView = async () => { click($('.tab[data-view=dashboard]')); await sleep(120); if ($('[data-mode=view]')) { click($('[data-mode=view]')); await sleep(80); } };
    /* colours as numbers: the contrast ratio of what is computed (alpha laid over what is behind it) */
    const rgb = s => { s = String(s); let m = s.match(/^rgba?\(([^)]+)\)/); if (m) { const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p[3] == null ? 1 : p[3]]; }
      m = s.match(/^color\(srgb ([^)]+)\)/); if (m) { const p = m[1].split(/[ \/]+/).filter(Boolean).map(Number); return [p[0] * 255, p[1] * 255, p[2] * 255, p[3] == null ? 1 : p[3]]; } return [255, 255, 255, 1]; };
    const lay = (f, b) => [0, 1, 2].map(i => f[i] * f[3] + b[i] * (1 - f[3])).concat(1);
    const bgAt = el => { const ls = []; for (let e = el; e; e = e.parentElement) { const c = rgb(getComputedStyle(e).backgroundColor); if (c[3] > 0) { ls.push(c); if (c[3] >= .99) break; } }
      let base = [255, 255, 255, 1]; if (!ls.length || ls[ls.length - 1][3] < .99) base = rgb(getComputedStyle(document.body).backgroundColor); for (let i = ls.length - 1; i >= 0; i--) base = lay(ls[i], base); return base; };
    const Lm = c => { const f = v => { v /= 255; return v <= .03928 ? v / 12.92 : Math.pow((v + .055) / 1.055, 2.4); }; return .2126 * f(c[0]) + .7152 * f(c[1]) + .0722 * f(c[2]); };
    const ratio = (a, b) => { const x = Lm(a), y = Lm(b); return (Math.max(x, y) + .05) / (Math.min(x, y) + .05); };
    const r2 = n => Math.round(n * 100) / 100;
    const textRatio = el => { const bg = bgAt(el), fg = lay(rgb(cs(el, 'color')), bg); return ratio(fg, bg); };
    const borderRatio = el => { const b = rgb(cs(el, 'borderTopColor')), inside = bgAt(el), outside = bgAt(el.parentElement || document.body); return Math.min(ratio(lay(b, inside), inside), ratio(lay(b, outside), outside)); };
    const meet = els => { const bad = []; for (let i = 0; i < els.length; i++) for (let j = i + 1; j < els.length; j++) { const a = els[i].getBoundingClientRect(), b = els[j].getBoundingClientRect();
      if (a.left < b.right - .5 && b.left < a.right - .5 && a.top < b.bottom - .5 && b.top < a.bottom - .5) bad.push((els[i].textContent + ' / ' + els[j].textContent).replace(/\s+/g, ' ').slice(0, 60)); } return bad; };
    const noSide = () => document.documentElement.scrollWidth <= innerWidth + 1;
    /* every text at least 12 px and every target at least 24 px, on whatever is showing (inline links inside a sentence are measured too) */
    const scan = (root = document) => { const small = new Set(), tiny = new Set();
      [...root.querySelectorAll('*')].forEach(e => { if (e.closest('[inert],[hidden],.sr,#toast,svg,.skip')) return; const c = getComputedStyle(e); if (c.display === 'none' || c.visibility === 'hidden') return; const r = e.getBoundingClientRect(); if (!r.width || !r.height) return;
        if ([...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(c.fontSize) < 11.99) small.add(e.tagName + '.' + String(e.className).slice(0, 28) + ' ' + c.fontSize);
        if ((e.matches('button,a[href],select,textarea,[role=button],[role=switch],[role=tab],summary') || e.matches('input:not([type=hidden]):not([type=checkbox]):not([type=radio])')) && (r.width < 23.5 || r.height < 23.5)) tiny.add(e.tagName + '.' + String(e.className).slice(0, 28) + ' ' + Math.round(r.width) + 'x' + Math.round(r.height) + ' ' + (e.getAttribute('aria-label') || e.textContent.trim()).slice(0, 18)); });
      return [...small].map(x => 'text ' + x).concat([...tiny].map(x => 'target ' + x)); };
    const bad = [], chk = label => { const s = scan(); if (s.length) bad.push(label + ': ' + s.join('; ')); };
    const prefTheme = C.themePref(), seeDark = async on => { C.theme(on ? 'dark' : 'light'); await sleep(320); };
    const ruleOf = sel => { const i = css.indexOf(sel + ' {'); return i < 0 ? '' : css.slice(i, css.indexOf('}', i)); };

    /* ── D11: the glance tiles fill the row at every width, and none is left alone on a second row ── */
    const tilesFill = (what) => { const g = $('.glance'); if (!g) { ok('D11 ' + what + ': there is a row of tiles', false); return; } const gr = rect(g), tiles = [...g.children].filter(e => e.classList.contains('fig') && shown(e)), rows = [];
      tiles.forEach(t => { const top = Math.round(rect(t).top); (rows.find(r => Math.abs(r.top - top) < 4) || rows[rows.push({ top, items: [] }) - 1]).items.push(t); });
      const fills = rows.every(r => Math.abs(rect(r.items[0]).left - gr.left) < 1.5 && Math.abs(rect(r.items[r.items.length - 1]).right - gr.right) < 1.5);
      const goRows = rows.map(r => r.items.filter(t => t.classList.contains('go')).length).filter(n => n), lone = goRows.length > 1 && !goRows.every(n => n === 1);
      ok(`D11 at ${innerWidth} px ${what}: the tiles fill the row, and none wraps alone`, tiles.length >= 3 && fills && !lone, `${tiles.length} tiles in rows of ${rows.map(r => r.items.length).join(',')}; row ${Math.round(gr.width)} px`); };
    await toView(); tilesFill('View');
    click($('[data-mode=edit]')); await sleep(150); tilesFill('Edit (hidden tiles shown)'); await toView();
    for (const w of [1100, 900]) await atW(w, async () => { await toView(); tilesFill('View'); click($('[data-mode=edit]')); await sleep(150); tilesFill('Edit'); await toView(); });

    /* ── D12: the contents rail says "On this page" when it is hovered or focused ── */
    { const toc = $('.toc'); ok('D12 the rail is named "On this page" for a screen reader, and its card heading says it', toc.getAttribute('aria-label') === 'On this page' && $('.toc-h').textContent.trim() === 'On this page');
      ok('D12 at rest the heading is hidden', cs('.toc-card', 'visibility') === 'hidden');
      toc.dispatchEvent(new MouseEvent('mouseenter')); await sleep(400); ok('D12 on hover the heading "On this page" shows', shown($('.toc-h')) && cs('.toc-card', 'visibility') === 'visible' && +cs('.toc-card', 'opacity') > 0.5, cs('.toc-card', 'opacity'));
      ok('D12 and its jump link at the foot is a 24 px target', rect('.toc-top').height >= 23.5); toc.dispatchEvent(new MouseEvent('mouseleave')); await sleep(260);
      $('#askBtn').focus(); toc.focus(); await sleep(400); ok('D12 on keyboard focus it shows too', toc.classList.contains('open') && shown($('.toc-h'))); $('#askBtn').focus(); await sleep(60); }

    /* ── D4: the Add a section box's small print (Full and Half tags, the Holds chips) is at least 12 px ── */
    { click($('[data-mode=edit]')); await sleep(150); click($('.sh-ctl .sh-add')); await sleep(350); const small = $$('.atd-d *').filter(e => shown(e) && [...e.childNodes].some(n => n.nodeType === 3 && n.textContent.trim()) && parseFloat(cs(e, 'fontSize')) < 11.99);
      ok('D4 nothing in the Add a section box is under 12 px (the Full and Half tags, the Holds chips, the labels)', $$('.atd-d .fit em').length > 3 && $$('.atd-d .atd-els span').length > 0 && !small.length, small.map(e => e.className + ' ' + cs(e, 'fontSize')).slice(0, 3).join('; '));
      $('#dlg').close(); await sleep(60); await toView(); }

    /* ── W4: the board's card pills are at least 12 px, and the ... menu is a 24 px target at full strength ── */
    { C.go('work'); await sleep(200); click($('[data-layout=board]')); await sleep(250); const pills = $$('.bcard .pill'), mv = $$('.bc-mv');
      ok('W4 board card pills are at least 12 px', pills.length > 3 && pills.every(p => parseFloat(cs(p, 'fontSize')) >= 11.99), pills.map(p => cs(p, 'fontSize'))[0]);
      ok('W4 the ... menu on a card is at least 24 px and at full strength', mv.length > 3 && mv.every(b => rect(b).width >= 23.5 && rect(b).height >= 23.5 && +cs(b, 'opacity') === 1), mv.length && cs(mv[0], 'opacity'));
      chk('work board'); click($('[data-layout=table]')); await sleep(150); }

    /* ── Work items board (#134): scrolling takes the toolbar away, the column headings pin under the top bar; back at the top they all show again ── */
    const boardPin = async (label, full) => { C.go('work'); await sleep(200); if (!$('.bcol-h')) { click($('[data-layout=board]')); await sleep(300); } if (full) { click($('#bFull')); await sleep(300); ok('board full screen: the top bar is away and the page is the board', document.body.classList.contains('bfull') && rect('.top').bottom === 0); } scrollTo(0, 0); await sleep(150);
      const rowsNow = () => $$('.view > .head, .wbar, .fbar, .factive, .bbar').filter(shown), tops = rowsNow().map(e => rect(e).top);
      ok(`board ${label}: at the top the toolbar, filters, count line and swimlanes control all show`, rowsNow().length >= 3 && rowsNow().every(e => rect(e).bottom > rect('.top').bottom - 1 || label.includes('full')) && rect('.bbar').height > 0);
      scrollTo(0, 600); await sleep(350); const tb = rect('.top').bottom, rows = rowsNow(), h = $('.bcol-h');
      ok(`board ${label}: scrolled 600 px, the toolbar, filter rows, count line and swimlanes control are above the viewport`, rows.length >= 3 && rows.every(e => rect(e).bottom <= tb + 1), rows.map(e => e.className.slice(0, 8) + ' ' + Math.round(rect(e).bottom)).join(', ') + ' vs ' + Math.round(tb));
      ok(`board ${label}: the column headings are pinned at the foot of the top bar (within 2 px)`, !!h && Math.abs(rect(h).top - tb) <= 2, h && Math.round(rect(h).top) + ' vs ' + Math.round(tb));
      ok(`board ${label}: nothing in the filter area is sticky`, rows.every(e => cs(e, 'position') !== 'sticky') && $$('.wbar *, .fbar *, .factive *, .bbar *').every(e => cs(e, 'position') !== 'sticky'));
      scrollTo(0, 0); await sleep(350); ok(`board ${label}: back at the top they all show again`, rowsNow().length === rows.length && rowsNow().every((e, i) => Math.abs(rect(e).top - tops[i]) < 2), rowsNow().map(e => Math.round(rect(e).top)).join() + ' vs ' + tops.map(Math.round).join()); };
    await boardPin('table-to-board');
    { const bd = $('.board'); scrollTo(0, 0); await sleep(150); bd.dispatchEvent(new WheelEvent('wheel', { deltaY: 240, bubbles: true, cancelable: true })); await sleep(250);
      ok('board: a mouse wheel over the board moves the page first (the board does not swallow it), until the headings reach the top bar', scrollY >= 200, scrollY); scrollTo(0, 0); await sleep(100); }
    await boardPin('full screen', true); if (document.body.classList.contains('bfull')) { click($('#bFull')); await sleep(300); } ok('board full screen: Leave full screen brings the top bar back', !document.body.classList.contains('bfull') && rect('.top').bottom > 40);
    click($('[data-layout=table]')); await sleep(150); { const t = $$('.view > .head, .wbar').filter(shown); scrollTo(0, 600); await sleep(250); ok('the table view is left as it was: its toolbar scrolls away with the page and nothing sticks', !$('.board') && $('table.items') && t.every(e => cs(e, 'position') !== 'sticky')); scrollTo(0, 0); await sleep(100); }

    /* ── Milestones: M1 (no overlap, here and in dark), M2, M5, M6, M7 ── */
    C.go('milestones'); await sleep(250); if (C.store.get('mview', 'plan') !== 'plan') { click($('[data-mv=plan]')); await sleep(120); } if ($('[data-msvb=line]')) { click($('[data-msvb=line]')); await sleep(150); }
    ok('M1 on the Milestones page no two labels overlap, and the Today label clears them', $$('.mv-lab').length >= 6 && !meet($$('.mv-lab')).length && $$('.mv-lab').every(l => { const t = rect('.mv-today b'), b = rect(l); return !(t.left < b.right && b.left < t.right && t.top < b.bottom && b.top < t.bottom); }), meet($$('.mv-lab')).join(' | '));
    ok('M2 the Timeline and Calendar switch has its words beside the icons', ['Timeline', 'Calendar'].every(t => $$('.msv-sw .msv-b').some(b => b.textContent.trim() === t && shown(b) && b.querySelector('svg'))));
    { const b = $$('.msv-sw .msv-b').find(x => x.getAttribute('aria-pressed') !== 'true'); ok('M2 and its resting text and icon are at least 3:1 (the old grey-500 icon alone was 2.7:1)', textRatio(b) >= 3, r2(textRatio(b)) + ':1'); }
    ok('M5 the card has no "Plan" heading repeating the switch above it', !$$('#main h2').some(h => h.textContent.trim() === 'Plan') && !!$('[data-mv=plan]'));
    { const rows = $$('.msl-row'), dup = rows.filter(r => { const t = r.textContent, d = t.match(/\d\d-\d\d-\d{4}/g) || []; return new Set(d).size !== d.length || /(Achieved|Forecast).*\1/.test(r.querySelector('.msl-date').textContent + r.querySelector('.mst').textContent); });
      ok('M5 no row of the details repeats a date or says its state twice', rows.length >= 5 && !dup.length, dup.map(r => r.textContent.replace(/\s+/g, ' ').slice(0, 70)).join(' | ')); }
    click($('[data-msvb=cal]')); await sleep(250);
    { const chips = $$('.cal-m:not([hidden]) .cal-ms'), nm = chips.map(c => c.querySelector('span').textContent), full = chips.every(c => { const s = c.querySelector('span'); return s.scrollWidth <= s.clientWidth + 1 && parseFloat(cs(s, 'fontSize')) >= 11.99 && cs(s, 'whiteSpace') === 'normal'; });
      ok('M7 calendar chips are at least 12 px and show the whole name (it wraps, it is not cut off)', chips.length >= 2 && full, nm.join(' | ')); }
    { click($('[data-calv-b=quarter]')); await sleep(200); const dn = $$('.cal-m:not([hidden]) .cal-dow span');
      ok('M7 the day names in the quarter view are at least 12 px', dn.length === 21 && dn.every(s => parseFloat(cs(s, 'fontSize')) >= 11.99), dn[0] && cs(dn[0], 'fontSize')); chk('milestone quarter'); click($('[data-calv-b=week]')); await sleep(150); chk('milestone week'); click($('[data-calv-b=month]')); await sleep(150); chk('milestone month'); }
    click($('[data-msvb=line]')); await sleep(120);
    { const fine = matchMedia('(hover: hover) and (pointer: fine)').matches; ok('M4 the range label stays on one line, and the zoom hint shows with a mouse and is hidden on touch' + (fine ? '' : ' (this window has no fine pointer, so it is hidden)'), rect('.mv-range').height < 24 && shown($('.mv-zh')) === fine && /Drag the bottom edge to zoom/.test($('.mv-zh').textContent)); }
    ok('M4 the timeline opens with Today in view (not on empty September)', (() => { const t = rect('.mv-today'), w = rect('.mv-wrap'); return t.left >= w.left && t.right <= w.right; })());
    click($('[data-mv=move]')); await sleep(250);
    { const t = $('#main').textContent;
      ok('M6 Movement is in plain words: "Move the agreed date", "on the agreed date", "Never moved"', !!$$('[data-dec=rebase]').find(b => b.textContent.trim() === 'Move the agreed date') && /on the agreed date/i.test(t) && /Never moved/.test(t) && /after the agreed date/.test(t));
      ok('M6 and none of the old words are left (Rebaseline, vs agreed, Not moved, Moved 0×)', !/Rebaselin|vs agreed|Not moved|Moved 0/.test(t));
      ok('M5 the Movement card says "Internal only" in a neutral tag, not amber (X9)', (() => { const g = $('.tag.info'); return !!g && cs(g, 'backgroundColor') !== cs(probe('--status-amber-tint'), 'backgroundColor'); })()); chk('movement'); }
    function probe(v) { const d = document.createElement('i'); d.style.cssText = `position:fixed;left:-9px;top:0;width:1px;height:1px;background:var(${v});color:var(${v})`; document.body.appendChild(d); setTimeout(() => d.remove(), 400); return d; }
    click($('[data-mv=plan]')); await sleep(150);
    /* M1 in dark: the labels still do not overlap, read at 4.5:1 on their chips, and the Today line passes behind them */
    await seeDark(true); { const labs = $$('.mv-lab'), low = labs.filter(l => textRatio(l.querySelector('b') || l) < 4.5);
      ok('M1 in dark the timeline labels do not overlap, each reads at 4.5:1 on its chip, and the Today line is behind them', labs.length >= 6 && !meet(labs).length && !low.length && parseInt(cs(labs[0], 'zIndex')) > parseInt(cs($('.mv-today'), 'zIndex')), low.map(l => l.textContent + ' ' + r2(textRatio(l.querySelector('b') || l))).slice(0, 2).join(' | '));
      ok('M2 in dark the switch text is at least 3:1', textRatio($$('.msv-sw .msv-b').find(x => x.getAttribute('aria-pressed') !== 'true')) >= 3); }
    await seeDark(false);

    /* ── Settings: S2 nav and Help links, S3, S4, S5, S6, S7 ── */
    C.go('settings'); await sleep(200);
    { const ids = $$('[data-sn]').map(a => a.dataset.sn);
      ok('S2 Settings has a row of links to its cards: Profile, Personal, AI, Projects, People, Folders, Publishing, Published reports, Data, Version, Diagnostics', ['profile', 'personal', 'aiset', 'projects', 'people', 'sources', 'publishing', 'pubs', 'data', 'update', 'diagnostics'].every(i => ids.includes(i) && !!document.getElementById(i)), ids.join());
      const reduce0 = C.reduce; C.reduce = true; click($('[data-sn=publishing]')); await sleep(200); const nb = rect('.set-nav').bottom, tp = rect('#publishing').top;
      ok('S2 a link brings its card to just under the sticky row', tp >= nb - 2 && tp <= nb + 90 && document.activeElement.id === 'publishing', `${Math.round(tp)} vs ${Math.round(nb)}`);
      ok('S2 the row stays under the top bar as you scroll, and marks where you are', Math.abs(rect('.set-nav').top - rect('.top').height) < 2 && $('[data-sn=publishing]').getAttribute('aria-current') === 'location' && $$('[data-sn][aria-current]').length === 1, rect('.set-nav').top + ' ' + rect('.top').height);
      click($('[data-sn=profile]')); await sleep(200); ok('S2 and Profile takes you back to the first card', rect('#profile').top < rect('.set-nav').bottom + 90);
      C.help.open(); await sleep(150); click($('#hpTabs [data-htab=start]')); await sleep(60); click($('[data-hgo="settings#profile"]')); await sleep(250); ok('S2 Help\'s "Settings › Profile" link lands on the Profile card, clear of the bars', C.UI.view === 'settings' && rect('#profile').top >= rect('.set-nav').bottom - 2 && rect('#profile').top < rect('.set-nav').bottom + 90, Math.round(rect('#profile').top));
      C.help.open(); await sleep(150); click($('#hpTabs [data-htab=start]')); await sleep(60); click($('[data-hgo="settings#publishing"]')); await sleep(250); ok('S2 and "Settings › Publishing" lands on the Publishing card', C.UI.view === 'settings' && rect('#publishing').top >= rect('.set-nav').bottom - 2 && rect('#publishing').top < rect('.set-nav').bottom + 90);
      C.reduce = reduce0; scrollTo(0, 0); await sleep(60); }
    ok('S3 the Data card has the labelled buttons "Export workbook" and "Import workbook"', $('#sExp').textContent.trim() === 'Export workbook' && $('#sImp').textContent.trim() === 'Import workbook' && !$('#data .ib'));
    { const x = spyX(); click($('#sExp')); await sleep(300); x(); ok('S3 and Export workbook still saves the workbook', writes.length >= 1 && /work items\.xlsx$/.test(writes.at(-1).name)); }
    { const rows = () => $$('#ppTable tbody tr'), need = C.peopleRows().filter(r => !r.email).length, n = C.peopleRows().length;
      ok('S4 People shows one line, "N of N people need details", and no chip on the rows', new RegExp(`^${need} of ${n} people need details`).test($('#ppCount').textContent.trim()) && !$$('#ppTable .tag.need').length && rows().length === n, $('#ppCount').textContent);
      click($('#ppOnly')); await sleep(80); ok('S4 filtered to those who need details, each row carries the chip (neutral, not amber)', rows().length === need && rows().every(r => r.querySelector('.tag.need')) && cs($('.tag.need'), 'backgroundColor') !== cs(probe('--status-amber-tint'), 'backgroundColor') && $('#ppOnly').getAttribute('aria-pressed') === 'true' && /Show everyone/.test($('#ppOnly').textContent));
      click($('#ppOnly')); await sleep(80); ok('S4 and Show everyone puts the list back with no chips', rows().length === n && !$$('#ppTable .tag.need').length); }
    { const t = $$('#main .card').map(c => { const k = c.cloneNode(true); k.querySelectorAll('.docs').forEach(e => e.remove()); return k.textContent; }).join('\n');   /* the folders you listed are your own entries, not the card's copy */ ok('S5 no file path, folder name or prototype note in any Settings card', !/~\/|\/Library|\/Users\/|Documents\/clark|Downloads|Prototype|Finder/.test(t), (t.match(/.{0,20}(~\/|\/Library|\/Users\/|Documents\/clark|Downloads|Prototype|Finder).{0,20}/) || [''])[0]); }
    ok('S5 and the foot of the page is the only place that says this is a prototype', /Prototype with demo data/.test($('footer.proto').textContent) && !/Prototype/.test($('#main').innerText));
    /* S6 Archive: one step with Undo, Show archived, Restore; nothing is deleted; history rows */
    { const cpr = () => S().projects.find(p => p.code === 'CPR'), items0 = S().items.filter(i => i.code === 'CPR').length, ms0 = S().milestones.filter(m => m.code === 'CPR').length, uc0 = S().usecases.filter(u => u.code === 'CPR').length, h0 = S().history.length;
      ok('S6 Projects has Archive and no Delete', !!$('[data-pa=CPR]') && !$('[data-pd]') && !$$('#projects button').some(b => /^Delete/.test(b.textContent.trim())) && items0 > 0);
      const names = () => { click($('#projBtn')); const t = $$('.menu [data-i]').map(e => e.textContent); C.closePop(); return t.join('|'); };
      ok('S6 the project switcher lists it before', /Customer Portal Refresh/.test(names()));
      click($('[data-pa=CPR]')); await sleep(100);
      ok('S6 Archive is one step with no confirm box, and the project goes from the list', !$('dialog[open]') && !!cpr().archived && !$('[data-pa=CPR]') && !$('[data-pr=CPR]') && /archived/.test($('#toastMsg').textContent) && !$('#toastUndo').hidden);
      ok('S6 nothing is deleted: the work items, milestones and use cases are all still in the data', S().items.filter(i => i.code === 'CPR').length === items0 && S().milestones.filter(m => m.code === 'CPR').length === ms0 && S().usecases.filter(u => u.code === 'CPR').length === uc0);
      ok('S6 and it is out of the project switcher and the open items counts', !/Customer Portal Refresh/.test(names()) && C.live().every(p => p.code !== 'CPR'));
      ok('S6 history has a row "Archived"', S().history.slice(h0).some(h => h.kind === 'project' && h.id === 'CPR' && h.text === 'Archived'));
      ok('S6 Show archived is in Settings › Projects', /Show archived/.test($('#showArch').textContent) && $('#showArch').getAttribute('aria-pressed') === 'false');
      click($('#showArch')); await sleep(80); ok('S6 Show archived lists it, marked Archived, with Restore (and no Open, Edit or Archive)', !!$('[data-pr=CPR]') && /Archived/.test($('[data-pr=CPR]').closest('tr').textContent) && !$('[data-pa=CPR]') && !$('[data-pe=CPR]') && $('#showArch').getAttribute('aria-pressed') === 'true');
      click($('[data-pr=CPR]')); await sleep(100); ok('S6 Restore is one step, with Undo: the project is back in the list and the switcher', !cpr().archived && !!$('[data-pa=CPR]') && !$('[data-pr=CPR]') && /restored/.test($('#toastMsg').textContent) && !$('#toastUndo').hidden && /Customer Portal Refresh/.test(names()));
      ok('S6 history has a row "Restored"', S().history.slice(h0).some(h => h.kind === 'project' && h.id === 'CPR' && h.text === 'Restored'));
      await undo(); ok('S6 Undo of Restore archives it again', !!cpr().archived); click($('[data-pr=CPR]')); await sleep(100);
      /* the open project can be archived too: another one opens, and Undo brings it back as the open one */
      const open = C.UI.code; click($(`[data-pa=${open}]`)); await sleep(100); ok('S6 archiving the open project opens another', C.UI.code !== open && !!C.P() && C.P().code !== open);
      await undo(); await sleep(60); ok('S6 and its Undo makes it the open project again', C.UI.code === open && !S().projects.find(p => p.code === open).archived);
      click($('#showArch')); await sleep(60); ok('S6 Show archived is remembered, and turned off again', $('#showArch').getAttribute('aria-pressed') === 'false' && C.store.get('showArchived', false) === false); }
    /* S7 both dark-mode switches say the same thing */
    { const th = C.themePref(); C.theme('light'); C.go('settings'); await sleep(100);
      click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60); const viaMenu = $('#toastMsg').textContent, dark1 = document.documentElement.dataset.theme;
      C.theme('light'); C.render(); await sleep(60); click($('[data-theme-pick=dark]')); await sleep(60); const viaSettings = $('#toastMsg').textContent, dark2 = document.documentElement.dataset.theme;
      ok('S7 the profile menu and Settings › Personal show the same toast for Dark mode on', dark1 === 'dark' && dark2 === 'dark' && viaMenu === viaSettings && viaMenu === 'Dark mode on', viaMenu + ' / ' + viaSettings);
      click($('#meBtn')); await sleep(60); await menuPick('Dark mode'); await sleep(60); const off1 = $('#toastMsg').textContent; C.theme('dark'); C.render(); await sleep(60); click($('[data-theme-pick=light]')); await sleep(60); const off2 = $('#toastMsg').textContent;
      ok('S7 and the same toast for Dark mode off', off1 === off2 && off1 === 'Dark mode off' && document.documentElement.dataset.theme === 'light', off1 + ' / ' + off2); C.theme(th); }
    chk('settings'); click($('#ppOnly')); await sleep(60); chk('settings, people filtered'); click($('#ppOnly')); await sleep(40);

    /* ── Publish: P1, P2 ── */
    await toView(); { const p = C.P(), was = p.publish; p.publish = { ...(was || {}), client: '' }; C.publishDialog(); await sleep(150);
      ok('P1 the Local option has no file path in it', !/~\/|\/Users|Documents|Library|\.html/.test($('#pubLocal').closest('label').textContent), $('#pubLocal').closest('label').textContent);
      ok('P2 "Set it in Settings, Publishing" is a link', !!$('#pubToSet') && $('#pubToSet').tagName === 'BUTTON' && /Settings, Publishing/.test($('#pubToSet').textContent) && rect('#pubToSet').height >= 23.5);
      chk('publish dialog'); const rd0 = C.reduce; C.reduce = true; click($('#pubToSet')); await sleep(400); C.reduce = rd0;
      ok('P2 it closes the box, opens Settings and puts the cursor in the client folder box', !$('dialog[open]') && C.UI.view === 'settings' && document.activeElement.id === 'pubC' && rect('#pubC').top >= rect('.set-nav').bottom && rect('#pubC').bottom <= innerHeight, document.activeElement.id);
      p.publish = was; C.go('dashboard'); await sleep(100); }

    /* ── Help: H2 (labels and links), and the step labels ── */
    C.help.open(); await sleep(150); click($('#hpTabs [data-htab=start]')); await sleep(80);
    { const labs = $$('.hp-n, .hp-gate, .hp-ig, .hp-lab'), links = $$('.hp a.hp-a, .hp .hp-go, .hp .hp-jgo, .hp .hp-jt, .hp .hp-wt[href]').filter(shown);
      ok('H2 the Help step labels are at least 12 px', labs.length >= 5 && labs.every(e => parseFloat(cs(e, 'fontSize')) >= 11.99), labs.map(e => cs(e, 'fontSize'))[0]);
      ok('H2 the links in Help are at least 24 px high', links.length >= 8 && links.every(a => rect(a).height >= 23.5), links.filter(a => rect(a).height < 23.5).map(a => a.textContent.slice(0, 20) + ' ' + Math.round(rect(a).height)).join(' | ')); }
    for (const t of ['start', 'howto', 'reference']) { click($(`#hpTabs [data-htab=${t}]`)); await sleep(100); chk('help ' + t); }

    /* ── Published page: PP1, X7, M1 and M4 on the page, no drift ── */
    { const html = await C.webPage(), mk = w => { const f = document.createElement('iframe'); f.style.cssText = `position:fixed;left:0;top:0;width:${w}px;height:900px;opacity:0;pointer-events:none`; f.srcdoc = html; document.body.appendChild(f); return f; };
      const ready = async f => { for (let i = 0; i < 100 && !(f.contentDocument && f.contentDocument.readyState === 'complete' && f.contentDocument.querySelector('#panel')); i++) await sleep(50); await sleep(150); };
      for (const w of [1300, 390]) { const f = mk(w); await ready(f); const d = f.contentDocument, W = f.contentWindow, $f = s => d.querySelector(s), $$f = s => [...d.querySelectorAll(s)];
        $f('.tabsbar [data-v=milestones]').click(); await sleep(300);
        const mks = $$f('#v-milestones .mv-mk'), labs = $$f('#v-milestones .mv-lab'), av = [...d.querySelectorAll('.av')];
        ok(`PP1 on the published page at ${w} px the milestone markers are at least 24 by 24`, mks.length >= 6 && mks.every(m => { const r = m.getBoundingClientRect(); return r.width >= 23.5 && r.height >= 23.5; }), mks[0] && mks[0].getBoundingClientRect().width);
        ok(`M1 on the published page at ${w} px no two labels overlap`, labs.length >= 6 && !meet(labs).length, meet(labs).join(' | '));
        { const t = $f('#v-milestones .mv-today').getBoundingClientRect(), wr = $f('#v-milestones .mv-wrap').getBoundingClientRect(); ok(`M4 on the published page at ${w} px the timeline opens on today, not on empty September`, t.left >= wr.left && t.right <= wr.right, `${Math.round(t.left)} in ${Math.round(wr.left)}-${Math.round(wr.right)}`); }
        if (w === 390) ok('M4 and the zoom hint is not on the published page', !/Drag the bottom edge/.test(d.body.innerHTML.replace(/<script[^]*?<\/script>/g, '')));
        $f('.tabsbar [data-v=dashboard]').click(); await sleep(150);
        if (w === 1300) { const small = $$f('.av').filter(e => W.getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width).map(e => W.getComputedStyle(e).fontSize); ok('PP1 the avatar initials are at least 12 px', av.length > 0 && small.length > 0 && small.every(s => parseFloat(s) >= 11.99), small[0]);
          const sk = d.body.firstElementChild; ok('X7 the published page has a skip link as its first stop', sk.classList.contains('skip') && /Skip to content/.test(sk.textContent)); sk.click(); await sleep(60); ok('X7 and it takes the focus to the page', d.activeElement && d.activeElement.tagName === 'MAIN');
          ok('X11 the published page has no drifting picture', !/drift/.test(d.documentElement.innerHTML.replace(/<script[^]*?<\/script>/g, '')) && W.getComputedStyle(d.body, '::before').animationName === 'bg-in');
          ok('X5 on the published page the search box and filters have a 3:1 edge', ['.wsearch', '.cfseg', '.cfbar select'].every(s => { const e = $f(s); return e && ratio(rgb(W.getComputedStyle(e).borderTopColor), [255, 255, 255, 1]) >= 3; })); }
        f.remove(); } }

    /* ── Dark mode: the handle, the control borders (X5) ── */
    await toView(); click($('[data-mode=edit]')); await sleep(200);
    for (let i = 0; i < 20 && $('.sh-ctl.first'); i++) await sleep(100);
    { const g = $('.sh-ctl'), light = +cs(g, 'opacity'); ok('D1 the light handle is left as it was: rest opacity .3, in its place', light === .3 && cs(g, 'top') === '12px' && cs(g, 'left') === '-36px', light + ' ' + cs(g, 'left'));
      await seeDark(true); const o = +cs($('.sh-ctl'), 'opacity'), ic = $('.sh-ctl .sh-b'), fg = lay([...rgb(cs(ic, 'color')).slice(0, 3), o * rgb(cs(ic, 'color'))[3]], bgAt($('.sh-ctl').parentElement));
      ok('dark the section handle at rest is at least .7 and its grip reads at 3:1 or more on the card', o >= .7 && ratio(fg, bgAt($('.sh-ctl').parentElement)) >= 3, `${o}, ${r2(ratio(fg, bgAt($('.sh-ctl').parentElement)))}:1`);
      ok('dark the handle is at full strength again on hover', (() => { $('.sec').dispatchEvent(new MouseEvent('mouseover', { bubbles: true })); return true; })() && /\.sec:hover > \.sh-ctl[^}]*opacity: 1/.test(css) && /\[data-theme=dark\] \{ --sh-rest: \.75/.test(css));
      await seeDark(false); ok('D1 and back in light it is .3 again', +cs('.sh-ctl', 'opacity') === .3); }
    { C.go('settings'); await sleep(200); const lo = borderRatio($('#pfName')); await seeDark(true); const dk = borderRatio($('#pfName'));
      ok('X5 an input has a 3:1 border in light and in dark', lo >= 3 && dk >= 3, `${r2(lo)}:1 and ${r2(dk)}:1`); await seeDark(false);
      C.go('work'); await sleep(200); const q = $('.search input'); ok('X5 the search box border is at least 3:1', borderRatio(q) >= 3, r2(borderRatio(q)));
      const seg = $('.seg'); ok('X5 the segmented switch border is at least 3:1', borderRatio(seg) >= 3, r2(borderRatio(seg)));
      C.go('settings'); await sleep(150); ok('X5 the Settings chips have a 3:1 border', borderRatio($('.set-nav a:not([aria-current])')) >= 3, r2(borderRatio($('.set-nav a:not([aria-current])'))));
      await seeDark(true); ok('X5 and so do they in dark', borderRatio($('.set-nav a:not([aria-current])')) >= 3 && borderRatio($('.seg')) >= 3 && borderRatio($('.field')) >= 3, r2(borderRatio($('.set-nav a:not([aria-current])')))); await seeDark(false);
      const cb = rgb(cs(probe('--control-border'), 'backgroundColor')); ok('X5 the token --control-border is at least 3:1 on white and on the page grey (grey-500 itself is only 2.7:1)', ratio(cb, [255, 255, 255, 1]) >= 3 && ratio(cb, rgb('rgb(243, 245, 248)')) >= 3 && /--control-border: #878C92/.test(css)); }

    /* ── Across the app: X7, X8, X9, X10, X11, X3 and X4 ── */
    { const first = [...document.querySelectorAll('a[href],button,input,select,textarea,[tabindex="0"]')].find(shown) || $('#skip'); ok('X7 the skip link is the first thing in the page to Tab to', document.body.firstElementChild.id === 'skip' && $$('a[href],button,input,select,textarea,[tabindex="0"]')[0].id === 'skip' && /^Skip to/.test($('#skip').textContent));
      $('#skip').focus(); await sleep(40); ok('X7 it shows when it has the focus (on the screen, readable)', rect('#skip').top >= 0 && rect('#skip').left >= 0 && textRatio($('#skip')) >= 4.5, Math.round(rect('#skip').top)); const h0 = location.hash; click($('#skip')); await sleep(60);
      ok('X7 and it takes the focus to the page itself, without changing the address', document.activeElement.id === 'main' && location.hash === h0); }
    C.go('dashboard'); await sleep(200); scrollTo(0, 0); { const pr = $('footer.proto'), m = $('#main'), pos = cs(pr, 'position');
      ok('X8 the "Prototype with demo data" note is in the foot of the page, not fixed over the content', pos === 'static' && rect(pr).top >= rect(m).bottom - 1 && /Reset demo data/.test(pr.textContent) && !!$('#resetDemo'), pos + ' ' + Math.round(rect(pr).top) + ' vs ' + Math.round(rect(m).bottom)); }
    { const amberBg = cs(probe('--status-amber-tint'), 'backgroundColor'), amberFg = cs(probe('--status-amber-text'), 'color');
      ok('X9 the note tokens (blue) are there for what is not urgent', /--note-tint: var\(--brand-blue-tint\)/.test(css) && /--note-text: var\(--status-blue-text\)/.test(css));
      ok('X9 "Left out of the published page", the "off" mark, "Changed", "Needs details" and "Internal only" are not amber in the style sheet', ['.sec.out::after', '.sh-off', '.chg-tag', '.tag.need, .tag.info'].every(s => ruleOf(s) && !/amber/.test(ruleOf(s)) && /note-/.test(ruleOf(s))), ['.sec.out::after', '.sh-off', '.chg-tag', '.tag.need, .tag.info'].filter(s => !ruleOf(s) || /amber/.test(ruleOf(s))).join(' | '));
      C.help.open(); await sleep(150); click($('#hpTabs [data-htab=start]')); await sleep(80); const gate = $('.hp-steps li.gate');
      ok('X9 the Help "Your call" step is in the note colour, not amber', !!gate && cs(gate, 'backgroundColor') !== amberBg && cs($('.hp-gate'), 'color') !== amberFg, gate && cs(gate, 'backgroundColor') + ' vs ' + amberBg);
      ok('X9 amber is still used for "look at this soon": a due-soon pill, the warning in Publish and an at-risk milestone', /\.a \{ background: var\(--status-amber-tint\)/.test(css) && /\.pubwarn \{[^}]*amber/.test(css) && /\.mst\.AtRisk \{ color: var\(--status-amber-text\)/.test(css)); }
    C.go('work'); await sleep(150); C.go('dashboard'); await sleep(40);
    ok('X11 a view enters in under 200 ms, and the token says so', parseFloat(cs('#main .view', 'animationDuration')) < 0.2 && parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--dur-view')) < 200 && cs('#main .view', 'animationName') === 'view-in', cs('#main .view', 'animationDuration'));
    ok('X11 no cover picture drifts: no drift animation in the style sheet, the cover, the page picture or the ask panel', !/@keyframes drift|animation:[^;}]*drift/.test(css) && cs('.cover', 'animationName') === 'none' && !/drift/.test(cs('body', 'animationName', '::before')) && !/drift/.test(cs('.cover', 'animationName', '::before')));
    ok('X11 peek and toast durations are tokens', /\.toast\.on \{[^}]*var\(--dur-state\)/.test(css) && /\.peek\.on \{[^}]*var\(--dur-state\)/.test(css));
    /* X3 and X4 again, on the states the earlier sweep did not draw */
    await toView(); chk('dashboard'); C.go('milestones'); await sleep(200); chk('milestones'); C.go('help'); await sleep(150); chk('help'); C.go('dashboard'); await sleep(100);
    { click($('[data-mode=edit]')); await sleep(150); click($('.sh-ctl .sh-add')); await sleep(350); chk('Add a section'); $('#dlg').close(); await sleep(60); await toView();
      C.go('work'); await sleep(150); C.workFilter({ type: 'A', due: ['overdue'] }); await sleep(200); ok('X4 the filter chips have a remove button of at least 24 px', $$('.fchip button').length >= 1 && $$('.fchip button').every(b => rect(b).width >= 23.5 && rect(b).height >= 23.5)); chk('work with filter chips'); if ($('#clearAll')) click($('#clearAll')); await sleep(60); }
    ok('X3 and X4 no text under 12 px and no target under 24 px on any of the screens and states scanned for #132', !bad.length, bad.join(' || ').slice(0, 900));

    /* ── Phone (390 px): D2, D3, M3, M4, H1, S1, W1, and no sideways scroll ── */
    await atW(390, async () => {
      C.go('dashboard'); await sleep(250); await toView(); tilesFill('View on a phone');
      click($('[data-mode=edit]')); await sleep(200); tilesFill('Edit on a phone');
      { const rows = $$('.ucr'); const ov = rows.filter(r => { const t = r.querySelector('.uc-tag').getBoundingClientRect(), n = r.querySelector('.uc-name').getBoundingClientRect(); return t.right > n.left + .5 && n.right > t.left + .5 && t.top < n.bottom && n.top < t.bottom; });
        ok('D2 in Edit at 390 the use case number and its title do not collide', rows.length >= 4 && !ov.length && !!rows[0].querySelector('.uc-eye'), ov.map(r => r.textContent.replace(/\s+/g, ' ').slice(0, 30)).join(' | ')); }
      ok('S1 no sideways scroll on the dashboard in Edit at 390', noSide(), document.documentElement.scrollWidth);
      click($('.sh-ctl .sh-add')); await sleep(350); ok('D3 the Add a section box shows templates first at 390', rect('.atd-g .atd-c').top < innerHeight - 40 && noSide()); $('#dlg').close(); await sleep(60); await toView();
      ok('H1 there is a visible Help button in the top bar on a phone (at least 24 px)', shown($('#helpBtn')) && rect('#helpBtn').width >= 23.5 && rect('#helpBtn').height >= 23.5 && rect('#helpBtn').right <= innerWidth && rect('#helpBtn').left > rect('#askBtn').right - 1);
      click($('#helpBtn')); await sleep(150); ok('H1 it opens Help, and Help says "Tap ? in the top bar", not "Press ?"', C.UI.view === 'help' && shown($('.hp-taphint')) && !shown($('.hp-keyhint')) && noSide()); chk('help on a phone');
      C.go('settings'); await sleep(250); ok('S1 no sideways scroll on Settings at 390, with the section row', noSide() && shown($('.set-nav')) && $('.set-nav').scrollWidth >= $('.set-nav').clientWidth, document.documentElement.scrollWidth); chk('settings on a phone');
      click($('#showArch')); await sleep(60); ok('S1 and none with archived projects showing', noSide()); click($('#showArch')); await sleep(40);
      C.go('milestones'); await sleep(300); if (C.store.get('mview', 'plan') !== 'plan') { click($('[data-mv=plan]')); await sleep(120); } if ($('[data-msvb=line]')) { click($('[data-msvb=line]')); await sleep(250); }
      ok('M4 on a phone the range does not wrap, and there is no "Drag the bottom edge to zoom" hint', rect('.mv-range').height < 24 && !shown($('.mv-zh')) && noSide(), Math.round(rect('.mv-range').height));
      { const t = rect('.mv-today'), w = rect('.mv-wrap'); ok('M4 on a phone the timeline opens on the current month (Today in view)', t.left >= w.left && t.right <= w.right, `${Math.round(t.left)} in ${Math.round(w.left)}-${Math.round(w.right)}`); }
      ok('M1 on a phone no two timeline labels overlap', !meet($$('.mv-lab')).length, meet($$('.mv-lab')).join(' | '));
      ok('M2 on a phone the switch is a row of its own with its words', shown($('.msv-b')) && rect('.msv-sw').right <= innerWidth && $$('.msv-b').every(b => rect(b).height >= 23.5));
      click($('[data-msvb=cal]')); await sleep(300);
      { const pane = $('.cal-m:not([hidden])'), li = [...pane.querySelectorAll('.cal-ag li')], here = C.mss().filter(m => (m.achievedOn || m.agreed).slice(0, 7) === pane.dataset.calM), nm = li.map(x => x.querySelector('.cal-agb span').textContent);
        ok('M3 on a phone the calendar lists the milestones under the month, each with its full name', shown(pane.querySelector('.cal-ag')) && here.length >= 1 && here.every(m => nm.some(n => n === m.name)) && li.every(x => rect(x).right <= innerWidth), nm.join(' | '));
        ok('M3 and a listed milestone opens its detail', (() => { click(li[0].querySelector('.cal-agb')); return true; })() && (await sleep(250), $('#peek').classList.contains('on'))); C.closePeek(); await sleep(250);
        ok('M3 no sideways scroll on the calendar at 390, in month, week and quarter', noSide() && (click($('[data-calv-b=week]')), await sleep(150), noSide()) && (click($('[data-calv-b=quarter]')), await sleep(150), noSide())); click($('[data-calv-b=month]')); await sleep(100); }
      C.go('work'); await sleep(250); ok('W1 on a phone the first item is near the top and no sideways scroll', noSide() && $$('table.items tr').length > 3); chk('work on a phone');
      click($('[data-layout=board]')); await sleep(300); await boardPin('on a phone'); click($('[data-layout=table]')); await sleep(150); });
    ok('the window is back to normal', innerWidth > 700);

    /* ── Reduced motion: nothing animates for the new parts, and the skeleton and tick of #131 are unchanged ── */
    ok('P3 the publish progress and tick are still in the page (built in 1659f6e)', /\.btn \.tick path/.test(css) && /\.btn\.pri\.ok/.test(css) && /aria-busy/.test(css));
  });

  const wide = $$('body *').filter(e => { const r = e.getBoundingClientRect(); return r.width && r.right > innerWidth + 1 && !e.closest('.mv-wrap,.peek,.ask,.toast,table,.menu,dialog'); });
  ok('no horizontal overflow', wide.length === 0, wide.slice(0, 3).map(e => e.tagName + '.' + e.className).join(' | '));
  const pre = document.createElement('pre'); pre.id = 'selftest'; pre.textContent = `RESULT ${pass} passed, ${fail} failed\n${out.join('\n')}\nERRORS ${JSON.stringify(window.__e || [])}`; document.body.appendChild(pre);
  document.title = 'SELFTEST-DONE';
})();
