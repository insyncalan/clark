// Test-only (tests/test_tpl_textimage_side_edit.py, row 1232): Text and Image Side by Side's (a textimage section's, body version 2) Edit part on a bare page, with a stand-in for clark's
// routes (POST /api/section-image, POST /api/section-body or /api/change, GET /api/data) that keeps the sections in memory and logs every call, so a
// test can see what the page sent. The stand-in does what clark does with the original (stores it, starts the framing again, takes both slots out
// with it) but makes no framed copy of its own: it uses the original, the real one is tested in test_textimage_side_server.py. Never part of clark's bundle. Fictional data only.
import { render } from "preact";
import { data, project } from "@src/stores/report.js";
import { Edit } from "@src/edit/templates/TextImage.jsx";
import * as words from "@src/logic/textImageSideWords.js";

const server = { sections: [], calls: [], fail: "" };
const reply = (body, status = 200) => Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
const sectionsOut = () => server.sections.map((s) => ({ ...s }));
let applies = 0;

globalThis.fetch = (url, init = {}) => {
  const path = String(url).split("?")[0];
  const body = init.body ? JSON.parse(init.body) : null;
  if (path === "/api/data") return reply({ ok: true, data: { project: { code: "ABC" }, report_sections: sectionsOut() } });
  if (path === "/api/section-image") {
    server.calls.push({ path, slot: body.slot, bytes: body.image ? body.image.length : 0, image: body.image });
    const s = server.sections.find((x) => x.id === body.section);
    const v = JSON.parse(s.body || "{}");
    if (body.slot !== "original") return reply({ ok: false, message: "The framed image is made by clark from the original." }, 400);
    for (const k of ["shape", "ratio", "fx", "fy", "crop", "fit", "fill", "from_w"]) delete v[k];      // a new original (or none) starts from no framing
    if (body.image === null) delete v.pictures; else v.pictures = { original: body.image, image: body.image };
    s.body = JSON.stringify({ ...v, v: 2 });
    return reply({ ok: true, apply_id: `A${++applies}`, sections: sectionsOut() });
  }
  if (path === "/api/change" || path === "/api/section-body") {   // a section's body goes to /api/section-body (api.js isBodyEdit)
    server.calls.push({ path, op: body.op, changes: body.changes });
    const s = server.sections.find((x) => x.id === body.id);
    const sent = JSON.parse(body.changes.body);
    const was = JSON.parse(s.body || "{}");
    if (sent.pictures) return reply({ ok: false, message: "A picture is sent on its own." }, 400);
    if (was.pictures) sent.pictures = was.pictures;      // clark keeps the stored images (and the framed copy it made)
    s.body = JSON.stringify(sent);
    return reply({ ok: true, apply_id: `A${++applies}`, sections: sectionsOut() });
  }
  return reply({ ok: false }, 404);
};

function App({ id, mode }) {
  const s = (data.value.report_sections || []).find((x) => x.id === id);
  if (!s) return null;
  return <Edit section={s} />;
}

window.F = {
  server, words,
  // Draw section `s` ({id, body}) in #root at `width` px; `slot` "left" draws it as a half width section.
  mount(s, mode, width, slot) {
    server.sections = [{ id: s.id, type: "textimage", title: "Text and Image Side by Side", hidden: 0, body: s.body || '{"v":2}' }];
    server.calls = [];
    project.value = "ABC";
    data.value = { project: { code: "ABC" }, report_sections: sectionsOut() };
    const root = document.getElementById("root");
    root.style.width = `${width}px`;
    root.className = slot ? `sec slot-${slot}` : "";
    render(null, root);
    render(<App id={s.id} mode={mode} />, root);
  },
  body: (id) => JSON.parse(server.sections.find((x) => x.id === id).body || "{}"),
};
