// clark as a Chrome app (#71). Run only by the live page (main.jsx), never by the published file (view.jsx): it needs the token
// in the "clark-boot" block, which a published file does not have, and a file cannot register a worker. The manifest link and the
// theme colour are added by script, not written in page.html, because the publish scan rejects any <link> but the three icons.
//
// - the manifest link and the theme-colour meta (the top bar's colour, --brand-navy, which the app window's title bar takes on)
// - the service worker (/sw.js), which shows the "clark isn't running" page when the server is stopped
// - "still here": POST /api/here with the token every 10 seconds, and once when the page becomes visible. A launcher-started
//   clark stops a minute after the last one.
const HEARTBEAT_MS = 10000;                   // idle.HEARTBEAT, in step (a test keeps the two together)

function bootToken() {
  try { return JSON.parse(document.getElementById("clark-boot").textContent).token || ""; } catch (e) { return ""; }
}

function head(tag, attrs) {
  const el = document.createElement(tag);
  for (const k of Object.keys(attrs)) el.setAttribute(k, attrs[k]);
  document.head.appendChild(el);
  return el;
}

export function themeColour() {
  return getComputedStyle(document.documentElement).getPropertyValue("--brand-navy").trim();
}

export function keepThemeColour() {
  const meta = document.querySelector('meta[name="theme-color"]') || head("meta", { name: "theme-color", content: themeColour() });
  const set = () => meta.setAttribute("content", themeColour() || meta.getAttribute("content"));
  new MutationObserver(set).observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme", "class"] });
  if (window.matchMedia) window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", set);
  set();
  return meta;
}

export function sayHere(token) {
  return fetch("/api/here", { method: "POST", headers: { "Content-Type": "application/json", "X-Clark-Token": token }, body: "{}", cache: "no-store" })
    .catch(() => {});                          // clark stopped: the offline page takes over on the next load
}

export function startApp() {
  const token = bootToken();
  if (!token) return false;
  if (!document.querySelector('link[rel="manifest"]')) head("link", { rel: "manifest", href: "/manifest.webmanifest" });
  keepThemeColour();
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  sayHere(token);
  setInterval(() => sayHere(token), HEARTBEAT_MS);
  document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") sayHere(token); });
  return true;
}
