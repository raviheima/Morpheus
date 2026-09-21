import { formatBytes, isImageName } from "../lib/format";

export default function ItemGroup({
  title,
  items,
  high,
  onPreview,
  onExtract,
  onPreviewImage,
  busy,
  emptyText,
  showReasons,
}) {
  if (!items?.length) {
    return emptyText ? <div className="empty">{emptyText}</div> : null;
  }
  return (
    <div className="panel">
      <div className="panel-title">
        {title} · {items.length}
      </div>
      <div className="panel-body">
        {items.map((d, i) => {
          const name = d.name || d.path || "";
          const img = isImageName(name);
          return (
            <div key={i} className="finding">
              <span className={`dot ${high ? "high" : ""}`} />
              <div>
                <strong>{d.name || d.path}</strong>
                <small className="mono">{d.path}</small>
                {showReasons && (d.reasons || []).length > 0 && (
                  <small>{(d.reasons || []).join(", ")}</small>
                )}
                <small>
                  {formatBytes(d.size)}
                  {d.deleted ? " · deleted" : ""}
                </small>
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                {onPreview && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => onPreview(d)}
                  >
                    Preview
                  </button>
                )}
                {img && onPreviewImage && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => onPreviewImage(d)}
                  >
                    View image
                  </button>
                )}
                {onExtract && (
                  <button
                    type="button"
                    className="btn btn-sm"
                    disabled={busy}
                    onClick={() => onExtract(d)}
                  >
                    Extract
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
