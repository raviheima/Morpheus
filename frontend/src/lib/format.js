export function formatBytes(n) {
  if (n == null) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export function isEncodedName(name = "") {
  return /encoded|bctextencoder/i.test(String(name));
}

export function isImageName(name = "") {
  return /\.(jpg|jpeg|png|gif|bmp|webp|tif|tiff)$/i.test(String(name));
}

export function isDeletedItem(d) {
  if (!d || typeof d !== "object") return false;
  if (d.deleted === true) return true;
  const p = String(d.path || d.name || "");
  return /RECYCLE/i.test(p) || /deleted/i.test(String(d.status || ""));
}

export function pickReport(jobOrResult) {
  const r = jobOrResult?.result ?? jobOrResult;
  if (!r) return null;
  if (r.case_summary) return r;
  if (r.report?.case_summary) return r.report;
  if (r.presentation?.case_summary) return r.presentation;
  return null;
}

export const DEMO_PATH =
  "/home/m4d_5c13nt15t/Documents/E01-Downloaded-by-me/2020JimmyWilson.E01";
