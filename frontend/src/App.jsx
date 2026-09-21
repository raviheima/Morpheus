import { useCallback, useEffect, useMemo, useState } from "react";
import { api, downloadBlob } from "./lib/api";
import { DEMO_PATH, pickReport } from "./lib/format";
import Modal from "./components/Modal";
import Toast from "./components/Toast";
import ProgressBar from "./components/ProgressBar";
import TopBar from "./components/TopBar";
import FindingsReport from "./components/FindingsReport";

export default function App() {
  const [token, setToken] = useState(
    () => localStorage.getItem("mz_token") || ""
  );
  const [user, setUser] = useState(
    () => localStorage.getItem("mz_user") || ""
  );
  const [screen, setScreen] = useState(() => (token ? "hub" : "landing"));
  const [view, setView] = useState("overview");

  const [cases, setCases] = useState([]);
  const [active, setActive] = useState(null);
  const [dataSources, setDataSources] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [custody, setCustody] = useState(null);
  const [analysisBySource, setAnalysisBySource] = useState({});
  const [activeAnalysis, setActiveAnalysis] = useState(null);
  const [activeJobUi, setActiveJobUi] = useState(null);

  const [imagePreviewUrl, setImagePreviewUrl] = useState(null);
  const [imagePreviewName, setImagePreviewName] = useState("");

  const [busy, setBusy] = useState(false);
  const [hashing, setHashing] = useState(false);
  const [hashStartedAt, setHashStartedAt] = useState(null);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);

  const [loginOpen, setLoginOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [addSrcOpen, setAddSrcOpen] = useState(false);

  const [loginForm, setLoginForm] = useState({
    username: "admin",
    password: "admin123",
  });
  const [caseForm, setCaseForm] = useState({
    case_name: "",
    examiner_name: "",
    examiner_email: "",
    organisation: "",
    description: "",
  });
  const [srcForm, setSrcForm] = useState({
    file_path: "",
    label: "",
    collected_by: "",
    fileName: "",
  });

  const notify = useCallback((title, detail) => {
    setToast({ title, detail });
    setTimeout(() => setToast(null), 4000);
  }, []);

  const saveSession = (t, u) => {
    localStorage.setItem("mz_token", t);
    localStorage.setItem("mz_user", u);
    setToken(t);
    setUser(u);
  };

  const logout = () => {
    localStorage.removeItem("mz_token");
    localStorage.removeItem("mz_user");
    setToken("");
    setUser("");
    setActive(null);
    setActiveAnalysis(null);
    setScreen("landing");
  };

  const loadCases = useCallback(
    async (t = token) => {
      if (!t) return;
      const data = await api("/cases/", { token: t });
      setCases(Array.isArray(data) ? data : data.cases || []);
    },
    [token]
  );

  useEffect(() => {
    if (token) loadCases().catch(() => {});
  }, [token, loadCases]);

  useEffect(() => {
    return () => {
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
    };
  }, [imagePreviewUrl]);

  const refreshCaseFiles = async (caseNumber, t = token) => {
    try {
      const ds = await api(`/data-sources/${caseNumber}`, { token: t });
      setDataSources(Array.isArray(ds) ? ds : []);
    } catch {
      setDataSources([]);
    }
  };

  const loadCustody = async (caseNumber) => {
    try {
      const data = await api(`/data-sources/${caseNumber}/custody-report`, {
        token,
      });
      setCustody(data);
    } catch {
      setCustody(null);
    }
  };

  const login = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api("/auth/token", {
        method: "POST",
        form: loginForm,
      });
      saveSession(data.access_token, loginForm.username);
      setLoginOpen(false);
      setScreen("hub");
      await loadCases(data.access_token);
      notify("Signed in", loginForm.username);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const createCase = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const created = await api("/cases/", {
        token,
        method: "POST",
        body: caseForm,
      });
      const c = {
        case_number: created.case_number,
        case_name: created.case_name || caseForm.case_name,
        examiner_name: created.examiner_name || caseForm.examiner_name,
        organisation: created.organisation || caseForm.organisation,
        status: created.status || "open",
      };
      setCreateOpen(false);
      await loadCases();
      await openCase(c);
      notify("Case created", c.case_number);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const openCase = async (c) => {
    setActive(c);
    setView("overview");
    setIntegrity(null);
    setActiveAnalysis(null);
    setActiveJobUi(null);
    setAnalysisBySource({});
    setImagePreviewUrl(null);
    setScreen("workspace");
    await refreshCaseFiles(c.case_number);
    await loadCustody(c.case_number);
  };

  const closeCase = async () => {
    if (!active) return;
    setBusy(true);
    try {
      await api(`/cases/${active.case_number}/close`, {
        token,
        method: "POST",
      });
      notify("Case closed", active.case_number);
      await loadCases();
      setScreen("hub");
    } catch (e) {
      notify("Close failed", e.message);
    } finally {
      setBusy(false);
    }
  };

  const deleteCase = async () => {
    if (!active) return;
    if (
      !window.confirm(
        `Delete case ${active.case_number}? This cannot be undone.`
      )
    )
      return;
    setBusy(true);
    try {
      await api(`/cases/${active.case_number}`, { token, method: "DELETE" });
      notify("Case deleted", active.case_number);
      setActive(null);
      await loadCases();
      setScreen("hub");
    } catch (e) {
      notify("Delete failed", e.message);
    } finally {
      setBusy(false);
    }
  };

  const addDataSource = async (e) => {
    e.preventDefault();
    if (!active) return;
    if (!srcForm.file_path.trim()) {
      setError("Enter the full path on the Morpheus analysis machine.");
      return;
    }
    setBusy(true);
    setHashing(true);
    setHashStartedAt(Date.now());
    setError("");
    try {
      await api("/data-sources/", {
        token,
        method: "POST",
        body: {
          case_number: active.case_number,
          file_path: srcForm.file_path.trim(),
          label: srcForm.label || srcForm.fileName || undefined,
          collected_by: srcForm.collected_by || user,
        },
      });
      setAddSrcOpen(false);
      setSrcForm({ file_path: "", label: "", collected_by: user, fileName: "" });
      await refreshCaseFiles(active.case_number);
      await loadCustody(active.case_number);
      notify("Data source registered", "Fingerprint stored");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
      setHashing(false);
      setHashStartedAt(null);
    }
  };

  const runIntegrity = async () => {
    if (!active) return;
    if (dataSources.length === 0) {
      notify("Nothing to verify", "Add a disk image data source first");
      return;
    }
    setBusy(true);
    try {
      const data = await api(
        `/data-sources/${active.case_number}/integrity-check`,
        { token, method: "POST" }
      );
      setIntegrity(data);
      await loadCustody(active.case_number);
      notify(
        data.warnings === 0 ? "Integrity verified" : "Integrity problems",
        `${data.ok ?? 0} ok · ${data.warnings ?? 0} warning(s)`
      );
    } catch (err) {
      notify("Integrity failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const downloadCertificate = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const blob = await api(
        `/data-sources/${active.case_number}/certificate.pdf`,
        { token }
      );
      downloadBlob(blob, `integrity_${active.case_number}.pdf`);
      notify("Certificate downloaded", active.case_number);
    } catch (err) {
      notify("Certificate failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const startAnalysisFor = async (ds) => {
    if (!ds?.stored_path) {
      notify("Missing path", "Data source has no stored path");
      return;
    }
    setBusy(true);
    try {
      const res = await api("/analysis/run", {
        token,
        method: "POST",
        body: {
          evidence_path: ds.stored_path,
          export_artifacts: true,
          build_timeline: false,
        },
      });
      setAnalysisBySource((prev) => ({
        ...prev,
        [ds.id]: { status: res.status || "queued", jobId: res.job_id },
      }));
      setActiveJobUi({
        sourceId: ds.id,
        jobId: res.job_id,
        status: res.status || "queued",
        progress: 0,
        phase: "queued",
      });
      notify("Analysis started", ds.label || ds.original_filename);
      pollJob(ds.id, res.job_id);
    } catch (err) {
      notify("Analyze failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const pollJob = async (sourceId, jobId) => {
    const tick = async () => {
      try {
        const job = await api(`/analysis/jobs/${jobId}`, { token });
        setAnalysisBySource((prev) => ({
          ...prev,
          [sourceId]: {
            status: job.status,
            jobId,
            result: job.result || null,
            error: job.error,
          },
        }));
        setActiveJobUi({
          sourceId,
          jobId,
          status: job.status,
          progress: job.progress,
          phase: job.phase || job.status,
          eta_seconds: job.eta_seconds,
        });
        if (job.status === "completed") {
          setActiveAnalysis(job.result || job);
          setView("findings");
          notify("Analysis complete", "Report ready");
          if (active?.case_number) await loadCustody(active.case_number);
          return;
        }
        if (job.status === "failed") {
          notify("Analysis failed", job.error || "Error");
          return;
        }
        setTimeout(tick, 2000);
      } catch (err) {
        notify("Job poll error", err.message);
      }
    };
    tick();
  };

  const report = useMemo(() => pickReport(activeAnalysis), [activeAnalysis]);

  const extractArtifact = async (art) => {
    const path = art.path || art.file_path;
    const ds = dataSources.find((d) => d.stored_path) || dataSources[0];
    if (!ds?.stored_path || !path) {
      notify("Extract unavailable", "Need data source and path");
      return;
    }
    setBusy(true);
    try {
      const blob = await api("/analysis/export-file", {
        token,
        method: "POST",
        body: { evidence_path: ds.stored_path, file_path: path },
      });
      const name =
        art.name || String(path).split(/[/\\]/).pop() || "artifact.bin";
      downloadBlob(blob, name);
      notify("Extracted", name);
    } catch (err) {
      notify("Extract failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const previewImage = async (art) => {
    const path = art.path || art.file_path;
    const ds = dataSources.find((d) => d.stored_path) || dataSources[0];
    if (!ds?.stored_path || !path) {
      notify("Preview unavailable", "Need data source and image path");
      return;
    }
    setBusy(true);
    try {
      const blob = await api("/analysis/export-file", {
        token,
        method: "POST",
        body: { evidence_path: ds.stored_path, file_path: path },
      });
      if (imagePreviewUrl) URL.revokeObjectURL(imagePreviewUrl);
      const url = URL.createObjectURL(blob);
      setImagePreviewUrl(url);
      setImagePreviewName(art.name || path);
      setView("findings");
      notify("Image loaded", art.name || path);
    } catch (err) {
      notify("Image preview failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const hasFiles = dataSources.length > 0;
  const hashElapsed = hashStartedAt
    ? Math.round((Date.now() - hashStartedAt) / 1000)
    : 0;

  /* ───── LANDING ───── */
  if (screen === "landing") {
    return (
      <div className="landing">
        <header className="land-header">
          <span className="topbar-brand">MORPHEUS</span>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
          >
            Get started
          </button>
        </header>
        <div className="land-hero">
          <h1>Digital forensics with integrity in the workflow</h1>
          <p>
            Register disk images, verify fingerprints, keep chain of custody,
            and run Windows triage — in one examiner workspace. Non-image
            evidence collection and mobile analysis are on the roadmap.
          </p>
          <button
            type="button"
            className="btn btn-primary"
            onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
          >
            Get started
          </button>
        </div>
        {loginOpen && (
          <Modal title="Sign in" onClose={() => setLoginOpen(false)}>
            <form onSubmit={login}>
              <label>Username</label>
              <input
                value={loginForm.username}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, username: e.target.value })
                }
                autoComplete="username"
              />
              <label>Password</label>
              <input
                type="password"
                value={loginForm.password}
                onChange={(e) =>
                  setLoginForm({ ...loginForm, password: e.target.value })
                }
                autoComplete="current-password"
              />
              {error && <p className="err-text">{error}</p>}
              <footer>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setLoginOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={busy}
                >
                  {busy ? "Signing in…" : "Sign in"}
                </button>
              </footer>
            </form>
          </Modal>
        )}
        {toast && <Toast {...toast} />}
      </div>
    );
  }

  /* ───── HUB ───── */
  if (screen === "hub") {
    return (
      <div className="app-root">
        <TopBar user={user} onLogout={logout} />
        <div className="main-scroll">
          <div className="hub">
            <h1 className="page-title">Cases</h1>
            <p className="page-sub">
              Create an investigation or open an existing case.
            </p>
            <div className="hub-tiles">
              <button
                type="button"
                className="hub-tile"
                onClick={() => {
                  setCaseForm((f) => ({ ...f, examiner_name: user }));
                  setError("");
                  setCreateOpen(true);
                }}
              >
                <strong>Create case</strong>
                <span>Start a new investigation with custody from the first action.</span>
              </button>
              <button
                type="button"
                className="hub-tile"
                onClick={() =>
                  loadCases().catch((e) => notify("Refresh failed", e.message))
                }
              >
                <strong>Refresh list</strong>
                <span>Reload cases from the Morpheus API.</span>
              </button>
            </div>
            <div className="panel">
              <div className="panel-title">Registered cases</div>
              <div className="panel-body" style={{ padding: 0 }}>
                {cases.length === 0 ? (
                  <div className="empty">No cases yet. Create one to begin.</div>
                ) : (
                  <table className="data">
                    <thead>
                      <tr>
                        <th>Case number</th>
                        <th>Name</th>
                        <th>Examiner</th>
                        <th>Status</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {cases.map((c) => (
                        <tr key={c.case_number}>
                          <td className="mono">{c.case_number}</td>
                          <td>{c.case_name}</td>
                          <td>{c.examiner_name}</td>
                          <td>{c.status}</td>
                          <td>
                            <button
                              type="button"
                              className="btn btn-sm"
                              onClick={() => openCase(c)}
                            >
                              Open
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>
        {createOpen && (
          <Modal title="Create case" onClose={() => setCreateOpen(false)}>
            <form onSubmit={createCase}>
              <label>Case name</label>
              <input
                required
                value={caseForm.case_name}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, case_name: e.target.value })
                }
              />
              <div className="row-2">
                <div>
                  <label>Examiner</label>
                  <input
                    required
                    value={caseForm.examiner_name}
                    onChange={(e) =>
                      setCaseForm({
                        ...caseForm,
                        examiner_name: e.target.value,
                      })
                    }
                  />
                </div>
                <div>
                  <label>Organisation</label>
                  <input
                    value={caseForm.organisation}
                    onChange={(e) =>
                      setCaseForm({
                        ...caseForm,
                        organisation: e.target.value,
                      })
                    }
                  />
                </div>
              </div>
              <label>Email</label>
              <input
                type="email"
                value={caseForm.examiner_email}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, examiner_email: e.target.value })
                }
              />
              <label>Description</label>
              <textarea
                value={caseForm.description}
                onChange={(e) =>
                  setCaseForm({ ...caseForm, description: e.target.value })
                }
              />
              {error && <p className="err-text">{error}</p>}
              <footer>
                <button
                  type="button"
                  className="btn"
                  onClick={() => setCreateOpen(false)}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={busy}
                >
                  {busy ? "Creating…" : "Create & open"}
                </button>
              </footer>
            </form>
          </Modal>
        )}
        {toast && <Toast {...toast} />}
      </div>
    );
  }

  /* ───── WORKSPACE ───── */
  return (
    <div className="app-root">
      <TopBar
        user={user}
        caseLabel={
          active ? `${active.case_number} — ${active.case_name}` : ""
        }
        onLogout={logout}
        onCases={() => setScreen("hub")}
      />
      <div className="shell">
        <aside className="sidebar">
          <div className="sidebar-section">Investigation</div>
          {[
            ["overview", "Case overview"],
            ["sources", "Data sources"],
            ["findings", "Key findings"],
            ["custody", "Chain of custody"],
            ["reports", "Reports"],
            ["about", "About & roadmap"],
          ].map(([id, label]) => (
            <button
              key={id}
              type="button"
              className={`nav-item ${view === id ? "active" : ""}`}
              onClick={() => setView(id)}
            >
              {label}
            </button>
          ))}
          <div className="sidebar-section">Roadmap</div>
          <button type="button" className="nav-item" disabled>
            Evidence collection <span className="badge">Soon</span>
          </button>
          <button type="button" className="nav-item" disabled>
            Android / iOS <span className="badge">Soon</span>
          </button>
          <div className="sidebar-foot">
            Signed in as <strong>{user}</strong>
          </div>
        </aside>

        <div className="main">
          <div className="main-scroll">
            {hashing && (
              <div className="panel">
                <div className="panel-body">
                  <ProgressBar
                    value={null}
                    label="Computing SHA-256 fingerprint…"
                    sub={`Elapsed ${hashElapsed}s · Large images can take several minutes.`}
                  />
                </div>
              </div>
            )}
            {activeJobUi &&
              !["completed", "failed"].includes(activeJobUi.status) && (
                <div className="panel">
                  <div className="panel-body">
                    <ProgressBar
                      value={activeJobUi.progress}
                      label={`Analysis · ${activeJobUi.phase || activeJobUi.status}`}
                      sub="Status updates every few seconds"
                    />
                  </div>
                </div>
              )}

            {view === "overview" && (
              <>
                <h1 className="page-title">Case overview</h1>
                <p className="page-sub">
                  {active?.case_number} · Integrity, custody, and disk-image
                  analysis
                </p>
                <div
                  className={`banner ${
                    integrity
                      ? integrity.warnings === 0
                        ? "ok"
                        : "warn"
                      : ""
                  }`}
                >
                  <div>
                    <strong>
                      {integrity
                        ? integrity.warnings === 0
                          ? "Integrity check passed"
                          : "Integrity problems detected"
                        : "Integrity has not been run yet"}
                    </strong>
                    <span>
                      {integrity
                        ? `${integrity.ok ?? 0} file(s) ok · ${integrity.warnings ?? 0} warning(s)`
                        : "Register a disk image, then verify fingerprints."}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || !hasFiles}
                    onClick={runIntegrity}
                  >
                    Verify integrity
                  </button>
                </div>
                <div className="panel-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => {
                      setError("");
                      setSrcForm({
                        file_path: "",
                        label: "",
                        collected_by: user,
                        fileName: "",
                      });
                      setAddSrcOpen(true);
                    }}
                  >
                    Add data source
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy || !hasFiles}
                    onClick={runIntegrity}
                  >
                    Verify integrity
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={downloadCertificate}
                  >
                    Integrity certificate
                  </button>
                  <button
                    type="button"
                    className="btn"
                    disabled={busy}
                    onClick={closeCase}
                  >
                    Close case
                  </button>
                  <button
                    type="button"
                    className="btn btn-danger"
                    disabled={busy}
                    onClick={deleteCase}
                  >
                    Delete case
                  </button>
                </div>
                <div className="stats">
                  <div className="stat">
                    <label>Data sources</label>
                    <b>{dataSources.length}</b>
                    <small>Disk images</small>
                  </div>
                  <div className="stat">
                    <label>Files (last report)</label>
                    <b>
                      {report?.case_summary?.total_files_scanned ?? "—"}
                    </b>
                    <small>From analysis</small>
                  </div>
                  <div className="stat">
                    <label>Deleted</label>
                    <b>
                      {report?.case_summary?.total_deleted_recovered ?? "—"}
                    </b>
                    <small>Engine total</small>
                  </div>
                  <div className="stat">
                    <label>Integrity</label>
                    <b>
                      {integrity
                        ? integrity.warnings === 0
                          ? "OK"
                          : "Warn"
                        : "—"}
                    </b>
                    <small>Hash vs collection</small>
                  </div>
                </div>
                <div className="grid-2">
                  <div className="panel">
                    <div className="panel-title">Data sources</div>
                    <div className="panel-body">
                      {dataSources.length === 0 ? (
                        <div className="empty">
                          Add a forensic disk image to begin analysis.
                        </div>
                      ) : (
                        dataSources.map((ds) => (
                          <div key={ds.id} style={{ marginBottom: 14 }}>
                            <strong>
                              {ds.label || ds.original_filename}
                            </strong>
                            <div
                              className="mono"
                              style={{ color: "var(--muted)" }}
                            >
                              {ds.stored_path}
                            </div>
                            <div style={{ marginTop: 10 }}>
                              <button
                                type="button"
                                className="btn btn-sm btn-primary"
                                disabled={busy}
                                onClick={() => startAnalysisFor(ds)}
                              >
                                Analyze
                              </button>{" "}
                              {analysisBySource[ds.id]?.status && (
                                <span className="tag">
                                  {analysisBySource[ds.id].status}
                                </span>
                              )}
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>
                  <div className="panel">
                    <div className="panel-title">Recent custody</div>
                    <div className="panel-body">
                      {!(custody?.custody_timeline || []).length ? (
                        <div className="empty">No custody events yet.</div>
                      ) : (
                        (custody.custody_timeline || [])
                          .slice(0, 8)
                          .map((e, i) => (
                            <div key={i} className="finding">
                              <span className="dot" />
                              <div>
                                <strong>
                                  {e.what} — {e.who}
                                </strong>
                                <small>{e.when}</small>
                              </div>
                            </div>
                          ))
                      )}
                      <button
                        type="button"
                        className="btn btn-sm"
                        style={{ marginTop: 10 }}
                        onClick={() => setView("custody")}
                      >
                        Full custody log
                      </button>
                    </div>
                  </div>
                </div>
              </>
            )}

            {view === "sources" && (
              <>
                <h1 className="page-title">Data sources</h1>
                <p className="page-sub">
                  Forensic disk images for this case. Analyze each source
                  independently.
                </p>
                <div className="panel-actions">
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => setAddSrcOpen(true)}
                  >
                    Add data source
                  </button>
                </div>
                <div className="panel">
                  <div className="panel-body">
                    {dataSources.length === 0 ? (
                      <div className="empty">None registered.</div>
                    ) : (
                      dataSources.map((ds) => (
                        <div key={ds.id} style={{ marginBottom: 14 }}>
                          <strong>{ds.label || ds.original_filename}</strong>
                          <div className="mono">{ds.stored_path}</div>
                          <div className="mono" style={{ marginTop: 4 }}>
                            {ds.sha256_hash
                              ? `${ds.sha256_hash.slice(0, 32)}…`
                              : ""}
                          </div>
                          <button
                            type="button"
                            className="btn btn-sm btn-primary"
                            style={{ marginTop: 10 }}
                            disabled={busy}
                            onClick={() => startAnalysisFor(ds)}
                          >
                            Analyze
                          </button>{" "}
                          {analysisBySource[ds.id]?.status && (
                            <span className="tag">
                              {analysisBySource[ds.id].status}
                            </span>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "findings" && (
              <>
                <h1 className="page-title">Key findings</h1>
                <p className="page-sub">
                  Documents of interest, suspicious files, emails, web history,
                  and more — from the analysis presentation report.
                </p>
                {!report ? (
                  <div className="empty">
                    Run <strong>Analyze</strong> on a data source first.
                  </div>
                ) : (
                  <FindingsReport
                    report={report}
                    busy={busy}
                    onExtract={extractArtifact}
                    onPreviewImage={previewImage}
                    imagePreviewUrl={imagePreviewUrl}
                    imagePreviewName={imagePreviewName}
                  />
                )}
              </>
            )}

            {view === "custody" && (
              <>
                <h1 className="page-title">Chain of custody</h1>
                <p className="page-sub">
                  Actions recorded for this case (same source as the integrity
                  certificate).
                </p>
                <div className="panel">
                  <div className="panel-body">
                    {!(custody?.custody_timeline || []).length ? (
                      <div className="empty">No events.</div>
                    ) : (
                      (custody.custody_timeline || []).map((e, i) => (
                        <div key={i} className="finding">
                          <span className="dot" />
                          <div>
                            <strong>
                              {e.what} — {e.who}
                            </strong>
                            <small>{e.when}</small>
                            {e.detail ? (
                              <small style={{ display: "block" }}>
                                {e.detail}
                              </small>
                            ) : null}
                          </div>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "reports" && (
              <>
                <h1 className="page-title">Reports</h1>
                <p className="page-sub">
                  Integrity certificate for non-technical readers. Analysis
                  detail is on Key findings.
                </p>
                <div className="panel">
                  <div className="panel-title">Evidence integrity certificate</div>
                  <div className="panel-body">
                    <p style={{ color: "var(--text-2)", fontSize: 14 }}>
                      PDF with fingerprints, verification status, and custody
                      timeline.
                    </p>
                    <button
                      type="button"
                      className="btn btn-primary"
                      disabled={busy}
                      onClick={downloadCertificate}
                    >
                      Download certificate PDF
                    </button>
                  </div>
                </div>
              </>
            )}

            {view === "about" && (
              <>
                <h1 className="page-title">About &amp; roadmap</h1>
                <div className="panel">
                  <div className="panel-body">
                    <div className="note-card" style={{ marginTop: 0 }}>
                      <h4>Disk images</h4>
                      <p style={{ margin: 0 }}>
                        Analysis targets forensic images on the Morpheus host.
                        Paste the full path when registering a data source.
                      </p>
                    </div>
                    <div className="note-card">
                      <h4>Evidence collection</h4>
                      <p style={{ margin: 0 }}>
                        Non-image case files — coming soon. Integrity already
                        applies to disk images you register.
                      </p>
                    </div>
                    <div className="note-card">
                      <h4>Mobile</h4>
                      <p style={{ margin: 0 }}>
                        Android and iOS acquisition and analysis — coming soon.
                      </p>
                    </div>
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      </div>

      {addSrcOpen && (
        <Modal title="Add data source" onClose={() => setAddSrcOpen(false)}>
          <form onSubmit={addDataSource}>
            <div className="note-card" style={{ marginTop: 0 }}>
              <h4>How to add a disk image</h4>
              <p style={{ margin: 0 }}>
                Copy the image into a Morpheus Evidence folder on this
                workstation when possible. In the desktop app use{" "}
                <strong>Browse…</strong> to pick the file (full path is filled
                automatically), or paste the path below.
              </p>
            </div>
            <label>Full path on Morpheus host</label>
            <div style={{ display: "flex", gap: 8, alignItems: "stretch" }}>
              <input
                required
                placeholder="/path/to/image.E01"
                value={srcForm.file_path}
                onChange={(e) =>
                  setSrcForm({ ...srcForm, file_path: e.target.value })
                }
                style={{ flex: 1 }}
              />
              {typeof window !== "undefined" && window.electronAPI?.openFile && (
                <button
                  type="button"
                  className="btn btn-sm"
                  onClick={async () => {
                    const selected = await window.electronAPI.openFile({
                      title: "Select evidence disk image",
                    });
                    if (!selected) return;
                    const filePath = Array.isArray(selected)
                      ? selected[0]
                      : selected;
                    const base =
                      String(filePath).split(/[/\\]/).pop() || "";
                    setSrcForm((s) => ({
                      ...s,
                      file_path: filePath,
                      label: s.label || base,
                      fileName: base,
                    }));
                  }}
                >
                  Browse…
                </button>
              )}
            </div>
            <div style={{ display: "flex", gap: 8, marginTop: 10 }}>
              <button
                type="button"
                className="btn btn-sm"
                onClick={() =>
                  setSrcForm((s) => ({
                    ...s,
                    file_path: DEMO_PATH,
                    label: s.label || "2020JimmyWilson.E01",
                  }))
                }
              >
                Fill demo path
              </button>
            </div>
            <label>Label</label>
            <input
              value={srcForm.label}
              onChange={(e) =>
                setSrcForm({ ...srcForm, label: e.target.value })
              }
            />
            <label>Collected by</label>
            <input
              value={srcForm.collected_by || user}
              onChange={(e) =>
                setSrcForm({ ...srcForm, collected_by: e.target.value })
              }
            />
            {hashing && (
              <ProgressBar
                value={null}
                label="Hashing…"
                sub={`Elapsed ${hashElapsed}s`}
              />
            )}
            {error && <p className="err-text">{error}</p>}
            <footer>
              <button
                type="button"
                className="btn"
                onClick={() => setAddSrcOpen(false)}
              >
                Cancel
              </button>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={busy}
              >
                {hashing ? "Hashing…" : "Register"}
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {toast && <Toast {...toast} />}
    </div>
  );
}
