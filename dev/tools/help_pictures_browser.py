"""The browser half of dev/tools/help_pictures.py: headless Chrome driven over its DevTools pipe, one function `take` per shot.
Kept apart so the quick tests can read the shots list and the safety checks without anything here being loaded."""
import base64
import json
import os
import tempfile
import time

import run_support
from help_pictures import DEFAULT_MARGIN, HEIGHT, SCALE, WIDTH, Refused, crop_list, optimise_png

# ---- Chrome over its DevTools pipe --------------------------------------------------------------------------------------------

class Pipe:
    """Chrome's --remote-debugging-pipe: JSON messages, each ended by a NUL byte."""

    def __init__(self, w, r):
        self.w, self.r, self.n, self.buf = w, r, 0, b""

    def call(self, method, params=None, session=None):
        self.n += 1
        msg = {"id": self.n, "method": method, "params": params or {}}
        if session:
            msg["sessionId"] = session
        os.write(self.w, json.dumps(msg).encode() + b"\0")
        while True:
            while b"\0" not in self.buf:
                chunk = os.read(self.r, 1 << 16)
                if not chunk:
                    raise RuntimeError("Chrome closed the pipe")
                self.buf += chunk
            raw, self.buf = self.buf.split(b"\0", 1)
            m = json.loads(raw)
            if m.get("id") == self.n:
                if "error" in m:
                    raise RuntimeError(m["error"])
                return m["result"]


class Browser:
    """One headless Chrome, a fresh profile, one window at the fixed size and the light theme."""

    def __enter__(self):
        path = run_support.chrome_path()
        if not path:
            raise Refused("Chrome was not found, so no pictures were taken. Install Google Chrome, or set CLARK_CHROME to its file.")
        to_r, to_w = os.pipe()
        from_r, from_w = os.pipe()
        self.profile = tempfile.mkdtemp(prefix="clark-chrome-profile-")
        self.proc = run_support.start_chrome(run_support.chrome_command(path, self.profile), to_r, from_w)
        os.close(to_r)
        os.close(from_w)
        self.pipe, self.fds = Pipe(to_w, from_r), (to_w, from_r)
        tid = next(t["targetId"] for t in self.pipe.call("Target.getTargets")["targetInfos"] if t["type"] == "page")
        self.sid = self.pipe.call("Target.attachToTarget", {"targetId": tid, "flatten": True})["sessionId"]
        self.send("Page.enable")
        self.send("Emulation.setDeviceMetricsOverride", {"width": WIDTH, "height": HEIGHT, "deviceScaleFactor": SCALE, "mobile": False})
        self.send("Emulation.setEmulatedMedia", {"features": [{"name": "prefers-color-scheme", "value": "light"}]})
        return self

    def __exit__(self, *exc):
        run_support.stop_chrome(self.proc)
        for fd in self.fds:
            os.close(fd)
        run_support.remove_profile(self.profile)

    def send(self, method, params=None):
        return self.pipe.call(method, params, self.sid)

    def js(self, expr):
        return self.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True}).get("result", {}).get("value")

    def until(self, expr, what, seconds=15):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self.js(expr):
                return
            time.sleep(0.1)
        raise Refused(what)

    def mouse(self, kind, x, y):
        self.send("Input.dispatchMouseEvent", {"type": kind, "x": x, "y": y, "button": "left",
                                               "buttons": 1 if kind == "mousePressed" else 0, "clickCount": 0 if kind == "mouseMoved" else 1})


# ---- one shot -----------------------------------------------------------------------------------------------------------------

def q(text):
    return json.dumps(text)


def ready_js(selector):
    """True when `selector` matches something with a size, and (for a button) it is not disabled."""
    return (f"(function(){{var e=document.querySelector({q(selector)});if(!e)return false;var r=e.getBoundingClientRect();"
            "return r.width>0&&r.height>0&&!e.disabled;})()")


def centre(b, selector, shot):
    b.until(ready_js(selector), f"Shot {shot}: nothing on the page matches {selector}")
    b.js(f"document.querySelector({q(selector)}).scrollIntoView({{block:'center',inline:'center'}})")
    x, y = b.js(f"(function(){{var r=document.querySelector({q(selector)}).getBoundingClientRect();return [r.left+r.width/2,r.top+r.height/2];}})()")
    return x, y


QUIET = ("*,*::before,*::after{transition:none!important;animation:none!important;caret-color:transparent!important;"
         "scroll-behavior:auto!important}")


def open_screen(b, port, screen, shot):
    b.send("Page.navigate", {"url": "about:blank"})
    b.send("Page.navigate", {"url": f"http://127.0.0.1:{port}/{screen}"})
    b.until("document.readyState==='complete'&&!!document.querySelector('.top')", f"Shot {shot}: the screen {screen} did not draw")
    b.js(f"(function(){{var s=document.createElement('style');s.textContent={q(QUIET)};document.head.appendChild(s);}})()")
    light = b.js("(function(){var t=document.documentElement.getAttribute('data-theme');"
                 "return t!=='dark'&&!window.matchMedia('(prefers-color-scheme: dark)').matches;})()")
    if not light:
        raise Refused(f"Shot {shot}: the page is not in the light theme, and pictures are light only.")


def run_steps(b, shot):
    for step in shot.get("steps", []):
        (key, value), = step.items()
        if key == "mode":
            sel = f"[data-mode={value}]"
            b.until(ready_js(sel), f"Shot {shot['id']}: nothing on the page matches {sel}")
            b.js(f"document.querySelector({q(sel)}).click()")
            b.until(f"document.querySelector({q(sel)}).getAttribute('aria-pressed')==='true'", f"Shot {shot['id']}: the page did not switch to {value}")
        elif key == "wait":
            b.until(ready_js(value), f"Shot {shot['id']}: nothing on the page matches {value}")
        elif key == "away":
            b.mouse("mouseMoved", WIDTH - 2, HEIGHT - 2)
        elif key == "hover":
            x, y = centre(b, value, shot["id"])
            b.mouse("mouseMoved", x, y)
        else:
            x, y = centre(b, value, shot["id"])
            b.mouse("mouseMoved", x, y)
            b.mouse("mousePressed", x, y)
            b.mouse("mouseReleased", x, y)
        time.sleep(0.25)


MARK_JS = """(function(marks){
  var blue = getComputedStyle(document.documentElement).getPropertyValue('--brand-blue').trim() || '#5B47D8';
  var on = getComputedStyle(document.documentElement).getPropertyValue('--text-on-brand').trim() || '#fff';
  marks.forEach(function(m){
    var t = document.querySelector(m.ring); if (!t) return;
    var r = t.getBoundingClientRect(), host = t.closest('dialog') || document.body, pad = 4;
    var ring = document.createElement('div');
    ring.setAttribute('data-help-mark', '');
    ring.style.cssText = 'position:fixed;pointer-events:none;box-sizing:border-box;z-index:2147483000;border:3px solid ' + blue +
      ';border-radius:8px;left:' + (r.left - pad) + 'px;top:' + (r.top - pad) + 'px;width:' + (r.width + 2 * pad) + 'px;height:' + (r.height + 2 * pad) + 'px';
    host.appendChild(ring);
    if (m.number) {
      var n = document.createElement('div'); n.setAttribute('data-help-mark', ''); n.textContent = String(m.number);
      n.style.cssText = 'position:fixed;pointer-events:none;z-index:2147483001;width:22px;height:22px;border-radius:50%;background:' + blue +
        ';color:' + on + ';font:600 13px/22px var(--font-body, Inter, sans-serif);text-align:center;left:' + (r.left - pad - 11) + 'px;top:' + (r.top - pad - 11) + 'px';
      host.appendChild(n);
    }
  });
})"""


def clip_for(b, shot):
    """{x, y, width, height} in page pixels around every `crop` selector, with the margin."""
    margin = shot.get("margin", DEFAULT_MARGIN)
    boxes = []
    for sel in crop_list(shot):
        b.until(ready_js(sel), f"Shot {shot['id']}: nothing on the page matches the crop {sel}")
        boxes.append(b.js(f"(function(){{var r=document.querySelector({q(sel)}).getBoundingClientRect();"
                          "return [r.left+scrollX,r.top+scrollY,r.right+scrollX,r.bottom+scrollY];})()"))
    x0, y0 = max(0, min(v[0] for v in boxes) - margin), max(0, min(v[1] for v in boxes) - margin)
    x1, y1 = max(v[2] for v in boxes) + margin, max(v[3] for v in boxes) + margin
    x1 = min(x1, b.js("document.documentElement.scrollWidth"))
    return {"x": round(x0), "y": round(y0), "width": max(1, round(x1 - x0)), "height": max(1, round(y1 - y0)), "scale": 1}


def take(b, port, shot, write):
    """Run one shot. Writes the picture when `write`, and returns its bytes (None for a check)."""
    open_screen(b, port, shot["screen"], shot["id"])
    run_steps(b, shot)
    marks = shot.get("marks", [])
    for m in marks:
        b.until(ready_js(m["ring"]), f"Shot {shot['id']}: nothing on the page matches the mark {m['ring']}")
    clip = clip_for(b, shot)
    if not write:
        return None
    if marks:
        b.js(f"{MARK_JS}({json.dumps(marks)})")
    time.sleep(0.2)
    shot_data = b.send("Page.captureScreenshot", {"format": "png", "clip": clip, "captureBeyondViewport": True})["data"]
    return optimise_png(base64.b64decode(shot_data))


