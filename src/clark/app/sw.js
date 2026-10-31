/* clark's service worker (#71): it does one thing. When clark isn't running, a window the installed app opens shows the
   offline page instead of the browser's error. It handles page loads only; it caches only /offline, never / (that page holds
   this run's token) and never /api/; it has no push, sync or message handler. Copied from creaite v2.6.9 templates/app/sw.js
   (BL-86) with the name changed. */
const CACHE = "clark-offline-v1";
self.addEventListener("install", e => { e.waitUntil(caches.open(CACHE).then(c => c.add("/offline"))); self.skipWaiting(); });
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;
  e.respondWith(fetch(e.request).catch(() => caches.match("/offline")));
});
