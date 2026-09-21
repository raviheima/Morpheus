import { formatBytes, isEncodedName, isImageName } from "../lib/format";

export default function PreviewBody({ preview }) {
  const { item, kind } = preview;
  if (kind === "email") {
    return (
      <div>
        <p>
          <strong>{item.subject}</strong>
        </p>
        <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.5 }}>
          {item.from} → {item.to}
          <br />
          {item.date}
        </p>
        <pre className="preview-pre">{item.body_snippet || "No snippet"}</pre>
      </div>
    );
  }
  if (kind === "url") {
    return (
      <div>
        <p className="mono" style={{ wordBreak: "break-all", fontSize: 13 }}>
          {item.url}
        </p>
        <p style={{ fontSize: 14, lineHeight: 1.5 }}>
          Last accessed: {item.last_accessed || item.visit_time || "—"}
          <br />
          Hits: {item.access_count ?? item.visit_count ?? "—"}
        </p>
      </div>
    );
  }
  const name = item.name || "";
  if (isEncodedName(name)) {
    return (
      <div>
        <span className="tag high">Encrypted / encoded</span>
        <p className="mono">{item.path}</p>
        <p style={{ fontSize: 14, lineHeight: 1.5 }}>
          Ciphertext-style content. Use Extract to save the file.
        </p>
      </div>
    );
  }
  if (isImageName(name)) {
    return (
      <div>
        <p className="mono">{item.path}</p>
        <p style={{ fontSize: 14, lineHeight: 1.5 }}>
          Use <strong>View image</strong> to load a preview from the disk image.
        </p>
      </div>
    );
  }
  return (
    <div>
      <p className="mono">{item.path}</p>
      <p style={{ fontSize: 14, lineHeight: 1.5 }}>
        Size: {formatBytes(item.size)}
        {item.deleted ? " · Recovered/deleted" : ""}
      </p>
      <p style={{ fontSize: 14, color: "var(--text-2)", lineHeight: 1.5 }}>
        Full text body after Extract, or coming soon for inline text.
      </p>
    </div>
  );
}
