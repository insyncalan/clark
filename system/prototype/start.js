/* clark prototype: the first-start guide (#427). The real one is START-HERE.txt and the starters in the download, before clark is open; here it is drawn so it can be tried.
   Two routes. Docker is the default, the terminal route (clark.command) the alternative. The Docker route checks that Docker is installed, that it is
   running (and starts it, or shows how) and that clark's port is free, then starts clark and opens it. Prototype: nothing is really started; a small
   control pretends what the computer has, so every message can be seen. */
(function () {
  'use strict';
  const C = window.C, esc = C.esc;
  const PORT = 8766;
  const WORLD = [['notrunning', 'Docker is installed but not running'], ['notinstalled', 'Docker is not installed'], ['running', 'Docker is running'], ['portbusy', 'Docker is running, but the port is in use']];
  let route = C.store.get('startRoute', 'docker'), world = 'notrunning', phase = '', how = false, ready = false, opener = null, d = null;
  const SAYS = {
    notinstalled: { ok: [0, 0, 0], head: 'Docker is not installed on this Mac.', body: 'Install Docker Desktop from docker.com, then press Check again. It is a large download, and it asks for your Mac’s password to set itself up, so clark can’t do it for you. Docker Desktop is free for personal use and for companies with fewer than 250 people and under 10 million dollars a year; larger organisations pay for it. Ask your IT team if you are not sure. A free alternative is Colima: it works from Terminal, and is harder to explain. Or use the terminal route, which needs no Docker.' },
    notrunning: { ok: [1, 0, 0], head: 'Docker is installed, but it is not running.', body: 'Start it: press Start Docker, or open Docker from your Applications folder and wait until its whale icon in the menu bar stops moving. Then press Check again.' },
    portbusy: { ok: [1, 1, 0], head: `Port ${PORT} is in use.`, body: 'Close the other clark window or program that is using it, then press Check again.' },
    running: { ok: [1, 1, 1], head: 'Docker is running, and clark’s port is free.', body: 'clark can start now.' },
  };
  const mark = on => on ? `<span class="st-ok" aria-hidden="true">${C.icon('check', 's')}</span><span class="sr">done</span>` : '<span class="st-no" aria-hidden="true">–</span><span class="sr">not yet</span>';
  function html() {
    const s = SAYS[world], busy = !!phase, started = ready;
    const docker = `<div class="st-checks" role="list" aria-label="What clark checked"><div role="listitem">${mark(s.ok[0])}<span>Docker is installed</span></div><div role="listitem">${mark(s.ok[1])}<span>Docker is running</span></div><div role="listitem">${mark(s.ok[2])}<span>The port clark uses (${PORT}) is free</span></div></div>
      <p class="st-say" id="stSay" role="status" aria-live="polite"><b>${esc(busy ? phase : started ? 'clark is ready.' : s.head)}</b> ${busy ? '' : esc(started ? 'It is running in Docker, and your data folder is shared with it. Open it in your browser.' : s.body)}</p>
      ${how && world === 'notrunning' ? '<ol class="st-how" id="stHow"><li>Open Docker from your Applications folder (or from Launchpad).</li><li>Wait until the whale icon in the menu bar stops moving. It can take a minute the first time.</li><li>Come back here and press Check again.</li></ol>' : ''}
      <div class="st-acts">${started ? '<button class="btn pri" id="stOpen">Open clark</button>'
        : world === 'running' ? `<button class="btn pri" id="stGo"${busy ? ' disabled' : ''}>Start clark</button>`
        : world === 'notrunning' ? `<button class="btn pri" id="stDocker"${busy ? ' disabled' : ''}>Start Docker</button><button class="btn" id="stHowBtn" aria-expanded="${how}" aria-controls="stHow">${how ? 'Hide the steps' : 'Show me how'}</button>`
        : world === 'notinstalled' ? '<button class="btn pri" id="stInstall">Go to docker.com</button><button class="btn" id="stTerm">Use the terminal route instead</button>' : ''}
        ${started ? '' : `<button class="btn quiet" id="stAgain"${busy ? ' disabled' : ''}>Check again</button>`}</div>`;
    const term = `<ol class="st-steps"><li>Double-click <b>clark.command</b> in the folder you unzipped.</li>
      <li>The first time, your Mac may say it can’t check who made the file. Control-click clark.command, choose Open, then choose Open again. If there is no Open button: open System Settings, choose Privacy &amp; Security, scroll down and choose Open Anyway beside clark.command.</li>
      <li>A Terminal window starts clark, then its window opens in Chrome (or in your usual browser if Chrome isn’t there).</li>
      <li>After a while with no window open, clark stops by itself. To use it again, double-click the file again.</li></ol>
      <p class="muted">If it says nothing was started because clark is already open in another Terminal window, or another program is using the connection it needs, close that Terminal window or program, then double-click clark.command again. If that does not help, restart your Mac.</p>
      <p class="muted">To check what your Mac needs for clark, open Terminal, type cd and a space, drag the folder into the Terminal window and press Return. Then type <code>python3 -m clark.doctor</code> and press Return. It says what is ready and what to fix.</p>
      <div class="st-acts"><button class="btn pri" id="stTermOpen">Open clark</button></div>`;
    return `<div class="dlg-h"><h2>Start clark</h2><p>Two ways to start clark. Choose one. Both use the same data folder, so don’t run both at the same time.</p></div>
      <div class="dlg-b"><div class="lays st-routes" role="radiogroup" aria-label="How to start clark">
        <button class="lay" role="radio" aria-checked="${route === 'docker'}" data-route="docker"><b>With Docker <span class="tag cl">Recommended</span></b><small>clark runs in a small box on your Mac. Docker has to be installed and running; clark checks it for you.</small></button>
        <button class="lay" role="radio" aria-checked="${route === 'terminal'}" data-route="terminal"><b>Without Docker</b><small>The terminal route: double-click clark.command. It needs only your Mac’s own Python and Chrome.</small></button></div>
      ${route === 'docker' ? `<div class="st-pane" id="stPane">${docker}<div class="st-proto"><label for="stWorld">Prototype: pretend this computer has</label><select class="field" id="stWorld">${WORLD.map(([v, t]) => `<option value="${v}"${world === v ? ' selected' : ''}>${t}</option>`).join('')}</select></div></div>` : `<div class="st-pane" id="stPane">${term}</div>`}</div>
      <div class="dlg-f"><button type="button" class="btn quiet" data-close>Close</button></div>`;
  }
  function draw(focus) { d.innerHTML = html(); wire(); if (focus) C.$(focus, d)?.focus(); }
  const later = (ms, f) => setTimeout(() => { if (d) f(); }, C.reduce ? 0 : ms);
  function wire() {
    C.$$('[data-route]', d).forEach(b => b.addEventListener('click', () => { route = b.dataset.route; C.store.set('startRoute', route); ready = false; phase = ''; draw(`[data-route="${route}"]`); }));
    C.$('#stWorld', d)?.addEventListener('change', e => { world = e.target.value; ready = false; phase = ''; how = false; draw('#stWorld'); });
    C.$('#stAgain', d)?.addEventListener('click', () => { phase = 'Checking Docker…'; draw('#stAgain'); later(600, () => { phase = ''; draw('#stAgain'); }); });
    C.$('#stHowBtn', d)?.addEventListener('click', () => { how = !how; draw('#stHowBtn'); });
    C.$('#stDocker', d)?.addEventListener('click', () => { phase = 'Starting Docker…'; draw(); later(1500, () => { phase = ''; world = 'running'; draw('#stGo'); }); });
    C.$('#stGo', d)?.addEventListener('click', () => { phase = 'Starting clark and waiting for it to answer…'; draw(); later(1500, () => { phase = ''; ready = true; draw('#stOpen'); }); });
    C.$('#stInstall', d)?.addEventListener('click', () => C.toast('Prototype: the real guide opens docker.com in your browser'));
    C.$('#stTerm', d)?.addEventListener('click', () => { route = 'terminal'; C.store.set('startRoute', route); draw('[data-route="terminal"]'); });
    const openIt = () => { C.toast(`Prototype: the real clark opens in your browser at http://127.0.0.1:${PORT}/`); d.close(); };
    C.$('#stOpen', d)?.addEventListener('click', openIt); C.$('#stTermOpen', d)?.addEventListener('click', openIt);
    C.$$('[data-close]', d).forEach(b => b.addEventListener('click', () => d.close()));
  }
  C.startGuide = { open() {
    if (document.querySelector('dialog[open]')) return; opener = document.activeElement; phase = ''; how = false; ready = false;
    d = document.createElement('dialog'); d.id = 'startGuide'; d.className = 'start'; d.setAttribute('aria-label', 'Start clark'); document.body.appendChild(d);
    d.addEventListener('close', () => { d.remove(); d = null; if (opener && opener.isConnected) opener.focus({ preventScroll: true }); });
    draw(); d.showModal(); C.$(`[data-route="${route}"]`, d)?.focus(); } };
  document.addEventListener('DOMContentLoaded', () => C.$('#startBtn')?.addEventListener('click', () => C.startGuide.open()));
})();
