"""Row 1549 THROWAWAY debug helper (never merged): records page events and the menu's box for 500 ms after a menu opens, prints one DBG1549 line."""
import json
import time

REC = r"""(() => {
  if (window.__dbgOff) window.__dbgOff();
  window.__dbg1549 = [];
  const t0 = performance.now(), SEL = %s, ev = [], smp = [], d = window.__dbg = {ev, smp, t0};
  const tg = (e) => { const x = e && e.tagName ? e : null; return x ? [x.tagName, x.id || '', String(x.className && x.className.baseVal !== undefined ? x.className.baseVal : x.className || '').slice(0, 60)].join('|') : String(e && e.constructor && e.constructor.name); };
  const types = ['scroll', 'resize', 'pointerdown', 'mousedown', 'click', 'blur', 'focusout', 'focusin', 'keydown', 'contextmenu', 'visibilitychange'];
  const h = (e) => ev.push({t: Math.round(performance.now() - t0), type: e.type, target: tg(e.target), key: e.key, code: e.code});
  for (const ty of types) { window.addEventListener(ty, h, true); document.addEventListener(ty, h, true); }
  const snap = () => { const m = document.querySelector(SEL), r = m && m.getBoundingClientRect(), a = document.activeElement;
    smp.push({t: Math.round(performance.now() - t0), present: !!m, rect: r ? [r.x, r.y, r.width, r.height] : null, active: a ? tg(a) : null, iw: innerWidth, ih: innerHeight}); };
  snap();
  const iv = setInterval(snap, 50);
  setTimeout(() => clearInterval(iv), 520);
  window.__dbgOff = () => { clearInterval(iv); for (const ty of types) { window.removeEventListener(ty, h, true); document.removeEventListener(ty, h, true); } };
})()"""


last = None


class Dbg:
    def __init__(self, run, name):
        self.run, self.name, self.t0, self.done = run, name, time.time(), False

    def dump(self):
        if self.done:
            return
        self.done = True
        try:
            time.sleep(max(0.0, 0.6 - (time.time() - self.t0)))
            info = self.run("JSON.stringify({d: window.__dbg, closes: window.__dbg1549, ua: navigator.userAgent, dpr: devicePixelRatio, screen: [screen.width, screen.height], vis: document.visibilityState, focus: document.hasFocus()})")
            print(f"DBG1549 {self.name} {info}", flush=True)
        except Exception as e:  # debug only: never change the test's outcome
            print(f"DBG1549 {self.name} dump failed: {e!r}", flush=True)


def arm(run, name, sel, p=None):
    """Install the recorder now (call BEFORE the open action). run(expr) evaluates in the page. With p, p.until dumps after the first wait on sel."""
    try:
        run(REC % json.dumps(sel))
    except Exception as e:
        print(f"DBG1549 {name} arm failed: {e!r}", flush=True)
    global last
    d = last = Dbg(run, name)
    if p is not None:
        orig = p.until

        def until(expr, *a, **k):
            try:
                return orig(expr, *a, **k)
            finally:
                if sel in str(expr):
                    d.dump()
        p.until = until
    return d
