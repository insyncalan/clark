// Test-only (tests/test_tpl_gallery_edit.py): the Image gallery's Edit part on a bare page, with a stand-in for clark's routes (POST /api/section-image,
// POST /api/change, GET /api/data) that keeps the sections in memory and logs every call. The stand-in does what gallery.py does with a slot (sets it, or takes
// it out with its words, keeps the framed copy as the image sent); the real checks are test_gallery_v2_server.py's. Never part of clark's bundle. Fictional data only.
import { render } from "preact";
import { data, project } from "@src/stores/report.js";
import { Edit } from "@src/edit/templates/Gallery.jsx";
import { toast } from "@src/stores/changes.js";

const server = { sections: [], calls: [] };
const reply = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
const sectionsOut = () => server.sections.map((s) => ({ ...s }));
let applies = 0;

globalThis.fetch = (url, init = {}) => {
  const path = String(url).split("?")[0];
  const body = init.body ? JSON.parse(init.body) : null;
  if (path === "/api/data") return reply({ ok: true, data: { project: { code: "ABC" }, report_sections: sectionsOut() } });
  if (path === "/api/section-image") {
    server.calls.push({ path, slot: body.slot, image: body.image, v: JSON.parse(server.sections.find((x) => x.id === body.section).body || "{}").v });
    const s = server.sections.find((x) => x.id === body.section);
    const v = JSON.parse(s.body || "{}");
    v.pictures = { ...(v.pictures || {}) };
    v.items = { ...(v.items || {}) };
    if (body.image === null) { delete v.pictures[body.slot]; delete v.items[body.slot]; } else v.pictures[body.slot] = body.image;
    if (!Object.keys(v.items).length) delete v.items;
    if (!Object.keys(v.pictures).length) delete v.pictures;
    s.body = JSON.stringify(v);
    return reply({ ok: true, apply_id: `A${++applies}`, sections: sectionsOut() });
  }
  if (path === "/api/change" || path === "/api/section-body") {
    server.calls.push({ path, op: body.op, changes: body.changes });
    const s = server.sections.find((x) => x.id === body.id);
    const sent = JSON.parse(body.changes.body);
    const was = JSON.parse(s.body || "{}");
    if (sent.pictures) return reply({ ok: false, message: "A picture is sent on its own." }, 400);
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

window.G = {
  server, toast,
  mount(s, width) {
    server.sections = [{ id: s.id, type: "gallery", title: "Image gallery", hidden: 0, body: s.body || "" }];
    server.calls = [];
    project.value = "ABC";
    data.value = { project: { code: "ABC" }, report_sections: sectionsOut() };
    const root = document.getElementById("root");
    root.style.width = `${width}px`;
    render(null, root);
    render(<App id={s.id} />, root);
  },
  body: (id) => JSON.parse(server.sections.find((x) => x.id === id).body || "{}"),
};
