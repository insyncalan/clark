// A picture made ready for a section template (#96 R1), Edit only: drawn again on a canvas, its longest side at most `longest` pixels
// and its size at most `most` bytes. Drawing it again drops whatever the camera left in the file (where and when it was taken), which
// the server refuses. A PNG stays a PNG while it fits (a screenshot stays sharp); anything else, or a PNG that is too big, becomes a
// JPEG on a white ground. Resolves to { ok: true, data, width, height } or { ok: false, message } in plain words; never throws.
export const TYPES = ["image/png", "image/jpeg", "image/webp"];
export const NOT_A_PICTURE = "That file isn't a picture that can go in the report. Choose a PNG, JPEG or WebP picture.";
export const UNREADABLE = "That picture could not be read. Choose another one.";
export const TOO_BIG = "That picture is too large, even made smaller. Choose a smaller picture.";

// The bytes a data address holds once decoded.
export function dataBytes(url) {
  if (typeof url !== "string") return 0;
  const i = url.indexOf(",");
  const b64 = i < 0 ? "" : url.slice(i + 1);
  const pad = b64.endsWith("==") ? 2 : b64.endsWith("=") ? 1 : 0;
  return Math.max(0, Math.floor(b64.length * 3 / 4) - pad);
}

async function bitmapOf(file) {
  try { return await createImageBitmap(file, { imageOrientation: "from-image" }); } catch (e) { return null; }
}

export async function shrink(file, { longest = 1600, most = 1024 * 1024 } = {}) {
  if (!file || !TYPES.includes(file.type)) return { ok: false, message: NOT_A_PICTURE };
  const bmp = await bitmapOf(file);
  if (!bmp || !bmp.width || !bmp.height) return { ok: false, message: UNREADABLE };
  let scale = Math.min(1, longest / Math.max(bmp.width, bmp.height));
  for (let round = 0; round < 6; round++) {
    const width = Math.max(1, Math.round(bmp.width * scale)), height = Math.max(1, Math.round(bmp.height * scale));
    const canvas = document.createElement("canvas");
    canvas.width = width; canvas.height = height;
    const g = canvas.getContext("2d");
    if (file.type === "image/png") {
      g.drawImage(bmp, 0, 0, width, height);
      const png = canvas.toDataURL("image/png");
      if (png.startsWith("data:image/png;base64,") && dataBytes(png) <= most) return { ok: true, data: png, width, height };
      g.clearRect(0, 0, width, height);
    }
    g.fillStyle = "#ffffff";                   // a transparent part becomes white, not black, in a JPEG
    g.fillRect(0, 0, width, height);
    g.drawImage(bmp, 0, 0, width, height);
    for (const q of [0.86, 0.76, 0.64]) {
      const jpg = canvas.toDataURL("image/jpeg", q);
      if (jpg.startsWith("data:image/jpeg;base64,") && dataBytes(jpg) <= most) return { ok: true, data: jpg, width, height };
    }
    scale *= 0.75;
  }
  return { ok: false, message: TOO_BIG };
}
