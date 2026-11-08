// The page's only way to list, review, install, remove and undo brands: GET /api/brands and POST /api/brands/review, /install,
// /remove and /undo. The page never sends a path: it says "downloads" or "file" (the server opens the system's own dialog), then names
// only the review or the brand. {status, body}: never a throw; a status of 0 is "no answer".
import { token } from "../stores/report.js";

async function call(method, path, body) {
  try {
    const headers = { "X-Clark-Token": token() };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    const r = await fetch(path, { method, headers, body: body === undefined ? undefined : JSON.stringify(body), cache: "no-store" });
    return { status: r.status, body: await r.json().catch(() => null) };
  } catch (e) {
    return { status: 0, body: null };
  }
}

export const listBrands = () => call("GET", "/api/brands");
export const reviewBrand = (from) => call("POST", "/api/brands/review", { from });
export const installBrand = (reviewId) => call("POST", "/api/brands/install", { review_id: reviewId });
export const removeBrand = (id) => call("POST", "/api/brands/remove", { id });
export const undoBrand = () => call("POST", "/api/brands/undo", {});
