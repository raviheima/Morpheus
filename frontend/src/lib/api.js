const API = import.meta.env.VITE_API_BASE || "http://localhost:8000";

export async function api(path, { token, method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, { method, headers, body: payload });
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) {
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const d = data.detail;
      const msg =
        typeof d === "string"
          ? d
          : Array.isArray(d)
            ? d.map((x) => x.msg || JSON.stringify(x)).join(", ")
            : res.statusText;
      throw new Error(msg || "Request failed");
    }
    return data;
  }
  const blob = await res.blob();
  if (!res.ok) throw new Error(res.statusText || "Request failed");
  return blob;
}

export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export { API };
