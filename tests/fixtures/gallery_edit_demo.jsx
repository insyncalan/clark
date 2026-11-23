// Test-only (tests/test_tpl_gallery_edit.py, row 1233): the Image gallery's Edit part (Classic) on a bare page, with a stand-in for clark's routes
// (POST /api/section-image, /api/section-body or /api/change, GET /api/data) that keeps the section in memory and logs every call. The stand-in
// stores the sent image as it is in the slot and keeps the body's version; what clark's server does with it is test_gallery_v2_server.py. Never part of
// clark's bundle. Fictional data only.
import { render } from "preact";
import { data, project } from "@src/stores/report.js";
import { Edit } from "@src/edit/templates/Gallery.jsx";
import { toast } from "@src/stores/changes.js";
import * as words from "@src/logic/galleryWords.js";

const server = { sections: [], calls: [] };
const reply = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
const sectionsOut = () => server.sections.map((s) => ({ ...s }));
let applies = 0;

globalThis.fetch = (url, init = {}) => {
  const path = String(url).split("?")[0];
  const body = init.body ? JSON.parse(init.body) : null;
  if (path === "/api/data") return reply({ ok: true, data: { project: { code: "ABC" }, report_sections: sectionsOut() } });
  if (path === "/api/section-image") {
    server.calls.push({ path, slot: body.slot, bytes: body.image ? body.image.length : 0 });
    const s = server.sections.find((x) => x.id === body.section);
    const v = JSON.parse(s.body || "{}");
    v.pictures = { ...(v.pictures || {}) };
    if (body.image === null) delete v.pictures[body.slot]; else v.pictures[body.slot] = body.image;
    s.body = JSON.stringify({ ...v, v: v.v || 1 });
    return reply({ ok: true, apply_id: `A${++applies}`, sections: sectionsOut() });
  }
  if (path === "/api/change" || path === "/api/section-body") {
    server.calls.push({ path, op: body.op, changes: body.changes });
    const s = server.sections.find((x) => x.id === body.id);
    const sent = JSON.parse(body.changes.body);
    const was = JSON.parse(s.body || "{}");
    if (was.pictures) sent.pictures = was.pictures;
    s.body = JSON.stringify(sent);
    return reply({ ok: true, apply_id: `A${++applies}`, sections: sectionsOut() });
  }
  return reply({ ok: false }, 404);
};

function App({ id }) {
  const s = (data.value.report_sections || []).find((x) => x.id === id);
  return s ? <Edit section={s} /> : null;
}

window.F = {
  server, words, toast: () => toast.value,
  // Draw section `s` ({id, body}) in #root at `width` px; `slot` "left" draws it as a half width section.
  mount(s, width, slot) {
    server.sections = [{ id: s.id, type: "gallery", title: "Image gallery", hidden: 0, body: s.body || "" }];
    server.calls = [];
    project.value = "ABC";
    data.value = { project: { code: "ABC" }, report_sections: sectionsOut() };
    const root = document.getElementById("root");
    root.style.width = `${width}px`;
    root.className = slot ? `sec slot-${slot}` : "";
    render(null, root);
    render(<App id={s.id} />, root);
  },
  body: (id) => JSON.parse(server.sections.find((x) => x.id === id).body || "{}"),
};
