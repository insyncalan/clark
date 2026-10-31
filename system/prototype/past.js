/* Past reports: a mockup for review (design item #125). Three ways in to a past report (a week picker beside "Week ending", the
   Published reports list and a timeline of publications) and one way of showing that you are looking at the past: a banner
   with "Back to now", a tinted frame, and nothing that can be edited. The publications here are made up for the review and
   are not read from the browser's database; nothing on this page changes the project. Opened from the profile menu
   ("Past reports (mockup)") or the address #past. The design note is docs/handoff/design-125-historic-view.md. */
(() => {
  const C = window.C, D = window.ClarkDB, esc = s => C.esc(s);
  const HN = { G: 'On track', A: 'At risk', R: 'Off track' };
  /* the made-up publications: number, the day it was published, the week it covers, health and reason, and a few figures */
  const PUBS = [
    { n: 4, at: '2026-09-30', week: '2026-10-02', h: 'G', why: 'Build on plan; test environment ready a week early.', open: 14, late: 1, ms: 'Design signed off', where: 'Local and to client' },
    { n: 5, at: '2026-10-07', week: '2026-10-09', h: 'A', why: 'Supplier data load slipped by a week; recovery plan agreed.', open: 17, late: 3, ms: 'First data load', where: 'Local and to client' },
    { n: 6, at: '2026-10-14', week: '2026-10-16', h: 'A', why: 'Data load done; two test cases still failing.', open: 16, late: 2, ms: 'First data load', where: 'Local' },
    { n: 7, at: '2026-10-21', week: '2026-10-23', h: 'R', why: 'Go-live date at risk: sign-off needed from the client by 28-10-2026.', open: 19, late: 4, ms: 'User testing starts', where: 'Local and to client' }
  ];
  const NOW_WEEK = '2026-10-30';
  const WAYS = [['picker', 'Week picker'], ['list', 'Published reports'], ['timeline', 'Timeline']];
  const S = { way: 'picker', open: null, mode: 'pub' };   // open: the publication number shown, or null; mode: 'pub' (as published) or 'asat' (rebuilt from history)
  const pub = n => PUBS.find(x => x.n === n);

  /* the way in, one of three */
  const pickerHtml = () => `<div class="pv-bar" id="pvPicker"><label class="muted">Week ending <select class="field" id="pvWeek" aria-label="Week ending">
      <option value="now">${D.fd(NOW_WEEK)} · this week (draft)</option>${PUBS.slice().reverse().map(x => `<option value="${x.n}"${S.open === x.n ? ' selected' : ''}>${D.fd(x.week)} · Publication ${x.n}</option>`).join('')}</select></label>
      <div class="seg" role="group" aria-label="Show"><button data-pv-mode="pub" aria-pressed="${S.mode === 'pub'}">As published</button><button data-pv-mode="asat" aria-pressed="${S.mode === 'asat'}">As at that date</button></div>
      <span class="muted pv-hint">Pick a past week to open it. Every past week is read only.</span></div>`;
  const listHtml = () => `<div class="pv-list" id="pvList"><table class="set stack"><thead><tr><th>#</th><th>Week ending</th><th>Published</th><th>Where</th><th></th></tr></thead><tbody>
      ${PUBS.slice().reverse().map(x => `<tr><td data-l="Publication"><b style="font-weight:500">${x.n}</b></td><td data-l="Week ending">${D.fd(x.week)}</td><td data-l="Published">${D.fd(x.at)}</td><td data-l="Where">${esc(x.where)}</td><td class="acts"><button class="btn sm" data-pv-open="${x.n}">Open</button></td></tr>`).join('')}</tbody></table></div>`;
  const timelineHtml = () => `<div class="pv-tl" id="pvTimeline" role="list" aria-label="Publications in order">
      ${PUBS.map(x => `<div role="listitem" class="pv-tl-i"><button class="pv-dot ${x.h}${S.open === x.n ? ' on' : ''}" data-pv-tl="${x.n}" aria-label="Publication ${x.n}, published ${D.fd(x.at)}, ${HN[x.h]}" aria-pressed="${S.open === x.n}"></button><span><b>${x.n}</b> · ${D.fd(x.at)}</span></div>`).join('')}
      <div role="listitem" class="pv-tl-i now"><span class="pv-dot now" aria-hidden="true"></span><span>Now · draft</span></div></div>`;

  /* the past itself: the banner, then the report in a tinted frame, inert (nothing in it can be focused, typed in or clicked) */
  const pastHtml = x => {
    const asat = S.mode === 'asat';
    const say = asat ? `You are looking at the dashboard as at ${D.fd(x.week)}, rebuilt from the change history.` : `You are looking at ${D.fd(x.at)}, as it was published.`;
    return `<div class="pv-banner" id="pvBanner" role="status"><span class="pv-b-ic">${C.icon('eye', 's')}</span><p><b>${say}</b> <button class="link" id="pvBack">Back to now</button><br>
        <small>${asat ? `Week ending ${D.fd(x.week)} · read only · this was not published in this form` : `Publication ${x.n} · week ending ${D.fd(x.week)} · read only · corrections go into the next report`}</small></p></div>
      <div class="pv-frame${asat ? ' asat' : ''}" id="pvFrame" inert aria-label="${asat ? 'The dashboard as at ' + D.fd(x.week) : 'Publication ' + x.n + ' as it was published'}">
        <div class="pv-mark" aria-hidden="true">${asat ? 'As at ' + D.fd(x.week) : 'Publication ' + x.n + ' · ' + D.fd(x.at)}</div>
        <article class="pv-sheet"><header class="pv-cover"><h2>${esc((C.P() || {}).name || 'Demo project')}</h2><div class="wk"><b>WEEKLY REPORT</b> · Week ending ${D.fd(x.week)}</div></header>
          <div class="pv-body"><div class="pv-tiles"><div class="pv-tile"><span class="hpill ${x.h}">${HN[x.h]}</span><p>${esc(x.why)}</p></div>
            <div class="pv-tile"><b>${x.open}</b><span>open items</span></div><div class="pv-tile"><b>${x.late}</b><span>late</span></div><div class="pv-tile"><b>${esc(x.ms)}</b><span>next milestone</span></div></div>
            <p class="muted pv-foot">${asat ? 'Rebuilt from the change history: the figures are what the project held at the end of that day.' : `The kept copy of the page the client was sent. Published ${D.fd(x.at)}. Publication ${x.n} · ${D.fd(x.at)}. View only.`}</p></div></article></div>`;
  };

  C.views.past = {
    html() {
      const x = S.open ? pub(S.open) : null;
      return `<div class="pv" data-past="${x ? 'on' : 'off'}"><div class="card-h"><h1 class="pv-h">Past reports</h1><span class="tag">Mockup for review</span></div>
        <p class="muted pv-intro">Three ways to reach a past report. The publications on this page are made up; nothing here changes the project.</p>
        <div class="seg pv-ways" role="group" aria-label="Way in">${WAYS.map(([k, l]) => `<button data-pv-way="${k}" aria-pressed="${S.way === k}">${l}</button>`).join('')}</div>
        <div class="card pv-way">${S.way === 'picker' ? pickerHtml() : S.way === 'list' ? listHtml() : timelineHtml()}</div>
        ${x ? pastHtml(x) : '<p class="muted pv-none" id="pvNone">Nothing past is open: you are looking at now.</p>'}</div>`;
    },
    wire() {
      const draw = () => { const y = scrollY; C.render(); scrollTo(0, y); };
      const open = n => { S.open = n; if (S.way !== 'picker') S.mode = 'pub'; draw(); };
      C.$$('[data-pv-way]').forEach(b => b.addEventListener('click', () => { S.way = b.dataset.pvWay; draw(); }));
      C.$$('[data-pv-open]').forEach(b => b.addEventListener('click', () => open(+b.dataset.pvOpen)));
      C.$$('[data-pv-tl]').forEach(b => b.addEventListener('click', () => open(+b.dataset.pvTl)));
      C.$$('[data-pv-mode]').forEach(b => b.addEventListener('click', () => { S.mode = b.dataset.pvMode; draw(); }));
      C.$('#pvWeek')?.addEventListener('change', e => { S.open = e.target.value === 'now' ? null : +e.target.value; draw(); });
      /* Back to now: the past closes and you are on this week's dashboard */
      C.$('#pvBack')?.addEventListener('click', () => { S.open = null; S.mode = 'pub'; C.go('dashboard'); });
    }
  };
  C.pastReset = () => { S.way = 'picker'; S.open = null; S.mode = 'pub'; };
})();
