import { useState } from "react";
import Modal from "./Modal";
import ItemGroup from "./ItemGroup";
import PreviewBody from "./PreviewBody";

export default function FindingsReport({
  report,
  onExtract,
  onPreviewImage,
  busy,
  imagePreviewUrl,
  imagePreviewName,
}) {
  const [tab, setTab] = useState("summary");
  const [preview, setPreview] = useState(null);
  const s = report?.case_summary;

  if (!s) {
    return (
      <div className="empty">
        No presentation report. Run <strong>Analyze</strong> on a data source.
      </div>
    );
  }

  const doi = report.documents_of_interest || [];
  const suspicious = report.suspicious_files || [];
  const deleted = report.deleted_files || [];
  const emails = report.sample_emails || [];
  const history = report.sample_web_history || [];
  const images = report.images || [];
  const vhds = report.nested_virtual_disks || [];

  const tabs = [
    ["summary", "Summary"],
    ["doi", `Documents of interest (${doi.length})`],
    ["suspicious", `Suspicious (${suspicious.length})`],
    ["deleted", `Deleted / recovered (${deleted.length})`],
    ["email", `Emails (${emails.length})`],
    ["web", `Web history (${history.length})`],
    ["images", `Images (${images.length})`],
    ["vhd", `Nested VHD (${vhds.length})`],
  ];

  return (
    <div>
      <div className="stats">
        <div className="stat">
          <label>Files scanned</label>
          <b>{Number(s.total_files_scanned).toLocaleString()}</b>
          <small>{s.image_type}</small>
        </div>
        <div className="stat">
          <label>Deleted (engine total)</label>
          <b>{s.total_deleted_recovered}</b>
          <small>Listed below: {deleted.length}</small>
        </div>
        <div className="stat">
          <label>Emails (engine total)</label>
          <b>{s.total_emails_parsed}</b>
          <small>Listed below: {emails.length}</small>
        </div>
        <div className="stat">
          <label>Web history (engine total)</label>
          <b>{s.total_browser_history_entries}</b>
          <small>Listed below: {history.length}</small>
        </div>
      </div>

      <p className="page-sub mono">{s.target}</p>
      <p className="page-sub">
        Image: {s.image_type}
        {s.is_operating_system ? " · OS" : ""} · {s.total_files_scanned} files ·{" "}
        {s.total_deleted_recovered} deleted · {s.total_emails_parsed} emails ·{" "}
        {s.total_browser_history_entries} history · {doi.length} documents of
        interest · {suspicious.length} suspicious · {vhds.length} nested VHD
      </p>
      <p className="page-sub">
        Header numbers are full scan totals. Each tab lists every item included
        in the presentation payload from the analysis engine.
      </p>

      <div className="panel-actions">
        {tabs.map(([id, label]) => (
          <button
            key={id}
            type="button"
            className={`btn btn-sm ${tab === id ? "btn-primary" : ""}`}
            onClick={() => setTab(id)}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "summary" && (
        <div className="panel">
          <div className="panel-title">Executive summary</div>
          <div className="panel-body">
            <ul style={{ margin: 0, paddingLeft: 20, color: "var(--text-2)", lineHeight: 1.6 }}>
              <li>Documents of interest listed: {doi.length}</li>
              <li>Suspicious listed: {suspicious.length}</li>
              <li>
                Deleted listed: {deleted.length} (engine total{" "}
                {s.total_deleted_recovered})
              </li>
              <li>
                Emails listed: {emails.length} (engine total{" "}
                {s.total_emails_parsed})
              </li>
              <li>
                Web listed: {history.length} (engine total{" "}
                {s.total_browser_history_entries})
              </li>
              <li>
                Images listed: {images.length}
                {s.total_images != null ? ` (engine total ${s.total_images})` : ""}
              </li>
            </ul>
          </div>
        </div>
      )}

      {tab === "doi" && (
        <ItemGroup
          title="Documents of interest"
          items={doi}
          high
          busy={busy}
          onPreview={(d) => setPreview({ item: d, kind: "doc" })}
          onExtract={onExtract}
          onPreviewImage={onPreviewImage}
          emptyText="No documents of interest in presentation."
        />
      )}

      {tab === "suspicious" && (
        <ItemGroup
          title="Suspicious files"
          items={suspicious}
          high
          busy={busy}
          showReasons
          onPreview={(d) => setPreview({ item: d, kind: "doc" })}
          onExtract={onExtract}
          onPreviewImage={onPreviewImage}
          emptyText="No suspicious files in presentation."
        />
      )}

      {tab === "deleted" && (
        <ItemGroup
          title="Deleted / recovered"
          items={deleted}
          busy={busy}
          onPreview={(d) => setPreview({ item: d, kind: "doc" })}
          onExtract={onExtract}
          onPreviewImage={onPreviewImage}
          emptyText="No deleted file rows exported (engine total may still be non-zero)."
        />
      )}

      {tab === "email" && (
        <div className="panel">
          <div className="panel-title">Emails · {emails.length}</div>
          <div className="panel-body">
            {!emails.length ? (
              <div className="empty">No emails.</div>
            ) : (
              emails.map((em, i) => (
                <div key={i} className="finding">
                  <span className="dot high" />
                  <div>
                    <strong>{em.subject || "(no subject)"}</strong>
                    <small>
                      {em.from} → {em.to} · {em.date}
                    </small>
                    <small style={{ display: "block" }}>{em.body_snippet}</small>
                  </div>
                  <button
                    type="button"
                    className="btn btn-sm"
                    onClick={() => setPreview({ item: em, kind: "email" })}
                  >
                    Preview
                  </button>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {tab === "web" && (
        <div className="panel">
          <div className="panel-title">Web history · {history.length}</div>
          <div className="panel-body" style={{ padding: 0 }}>
            {!history.length ? (
              <div className="empty">No history rows.</div>
            ) : (
              <table className="data">
                <thead>
                  <tr>
                    <th>Time</th>
                    <th>Hits</th>
                    <th>URL</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((h, i) => (
                    <tr key={i}>
                      <td className="mono">
                        {h.last_accessed || h.visit_time || "—"}
                      </td>
                      <td>{h.access_count ?? h.visit_count ?? "—"}</td>
                      <td>
                        <button
                          type="button"
                          className="btn btn-sm"
                          onClick={() => setPreview({ item: h, kind: "url" })}
                        >
                          Preview
                        </button>
                        <div
                          className="mono"
                          style={{
                            wordBreak: "break-all",
                            marginTop: 4,
                          }}
                        >
                          {h.url}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      )}

      {tab === "images" && (
        <div className="panel">
          <div className="panel-title">Images · {images.length}</div>
          <div className="panel-body">
            {imagePreviewUrl && (
              <div className="image-preview-box">
                <p className="mono">{imagePreviewName}</p>
                <img
                  src={imagePreviewUrl}
                  alt=""
                  style={{
                    maxWidth: "100%",
                    maxHeight: 400,
                    border: "1px solid var(--border)",
                  }}
                />
              </div>
            )}
            {!images.length ? (
              <div className="empty">
                No image paths in presentation (engine may still report thousands
                of images).
              </div>
            ) : (
              images.map((d, i) => (
                <div key={i} className="finding">
                  <span className="dot" />
                  <div>
                    <strong>{d.name || d.path}</strong>
                    <small className="mono">{d.path}</small>
                  </div>
                  <div style={{ display: "flex", gap: 6 }}>
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={busy}
                      onClick={() => onPreviewImage(d)}
                    >
                      Preview
                    </button>
                    <button
                      type="button"
                      className="btn btn-sm"
                      disabled={busy}
                      onClick={() => onExtract(d)}
                    >
                      Extract
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      )}

      {tab === "vhd" &&
        (vhds.length === 0 ? (
          <div className="empty">No nested VHDs.</div>
        ) : (
          vhds.map((v, i) => (
            <div className="panel" key={i}>
              <div className="panel-title">{v.vhd_path}</div>
              <div className="panel-body">
                <p className="mono">
                  {v.identification?.image_type} ·{" "}
                  {v.identification?.partition_scheme}
                </p>
                {(v.scans || []).map((scan, j) => (
                  <div key={j} style={{ marginBottom: 14 }}>
                    <strong>{scan.volume_name}</strong>
                    <small style={{ display: "block", color: "var(--muted)" }}>
                      Files {scan.total_files_scanned} · Deleted{" "}
                      {scan.total_deleted_found}
                    </small>
                    {(scan.suspicious_files || []).map((sf, k) => (
                      <div key={k} className="finding">
                        <span className="dot high" />
                        <div>
                          <strong>{sf.name}</strong>
                          <small className="mono">{sf.path}</small>
                          <small>{(sf.reasons || []).join(", ")}</small>
                        </div>
                      </div>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          ))
        ))}

      {preview && (
        <Modal title="Preview" onClose={() => setPreview(null)}>
          <PreviewBody preview={preview} />
        </Modal>
      )}
    </div>
  );
}
