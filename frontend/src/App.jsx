import { useCallback, useEffect, useState } from "react";
import "./styles.css";

const API = import.meta.env.VITE_API_BASE || "http://localhost:8000";

async function api(path, { token, method = "GET", body, form } = {}) {
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload = body;
  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    payload = new URLSearchParams(form);
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${API}${path}`, { method, headers, body: payload });
  const ct = res.headers.get("content-type") || "";
  const data = ct.includes("application/json")
    ? await res.json()
    : await res.blob();
  if (!res.ok) {
    const msg =
      data && typeof data === "object" && !(data instanceof Blob)
        ? data.detail || JSON.stringify(data)
        : res.statusText;
    throw new Error(typeof msg === "string" ? msg : "Request failed");
  }
  return data;
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem("mz_token") || "");
  const [user, setUser] = useState(() => localStorage.getItem("mz_user") || "");
  const [screen, setScreen] = useState(token ? "hub" : "landing");
  const [view, setView] = useState("overview");
  const [cases, setCases] = useState([]);
  const [active, setActive] = useState(null);
  const [dataSources, setDataSources] = useState([]);
  const [integrity, setIntegrity] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [jobId, setJobId] = useState(null);
  const [jobStatus, setJobStatus] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [toast, setToast] = useState(null);

  const [loginOpen, setLoginOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [addSrcOpen, setAddSrcOpen] = useState(false);
  const [loginForm, setLoginForm] = useState({ username: "admin", password: "admin123" });
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
  });

  const notify = (title, detail) => {
    setToast({ title, detail });
    setTimeout(() => setToast(null), 3500);
  };

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
    setAnalysis(null);
    setScreen("landing");
  };

  const loadCases = useCallback(async (t = token) => {
    if (!t) return;
    const data = await api("/cases/", { token: t });
    setCases(Array.isArray(data) ? data : data.cases || []);
  }, [token]);

  useEffect(() => {
    if (token) loadCases().catch(() => {});
  }, [token, loadCases]);

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
        organisation: created.organisation,
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
    setAnalysis(null);
    setIntegrity(null);
    setJobId(null);
    setJobStatus(null);
    setScreen("workspace");
    try {
      const ds = await api(`/data-sources/${c.case_number}`, { token });
      setDataSources(Array.isArray(ds) ? ds : []);
    } catch {
      setDataSources([]);
    }
  };

  const addDataSource = async (e) => {
    e.preventDefault();
    if (!active) return;
    setBusy(true);
    setError("");
    try {
      await api("/data-sources/", {
        token,
        method: "POST",
        body: {
          case_number: active.case_number,
          file_path: srcForm.file_path,
          label: srcForm.label || undefined,
          collected_by: srcForm.collected_by || user,
        },
      });
      setAddSrcOpen(false);
      const ds = await api(`/data-sources/${active.case_number}`, { token });
      setDataSources(Array.isArray(ds) ? ds : []);
      notify("Data source registered", "Fingerprint stored");
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const runIntegrity = async () => {
    if (!active) return;
    setBusy(true);
    try {
      const data = await api(
        `/data-sources/${active.case_number}/integrity-check`,
        { token, method: "POST" }
      );
      setIntegrity(data);
      notify(
        data.warnings === 0 ? "Integrity OK" : "Integrity issues",
        `${data.ok} ok, ${data.warnings} warning(s)`
      );
    } catch (err) {
      notify("Integrity check failed", err.message);
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
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `integrity_${active.case_number}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      notify("Certificate downloaded", active.case_number);
    } catch (err) {
      notify("Certificate failed", err.message);
    } finally {
      setBusy(false);
    }
  };

  const startAnalysis = async () => {
    const primary = dataSources[0];
    if (!primary?.stored_path) {
      notify("No data source", "Register a forensic image first");
      return;
    }
    setBusy(true);
    try {
      const res = await api("/analysis/run", {
        token,
        method: "POST",
        body: {
          evidence_path: primary.stored_path,
          export_artifacts: true,
          build_timeline: false,
        },
      });
      setJobId(res.job_id);
      setJobStatus(res.status || "queued");
      notify("Analysis started", res.job_id);
      pollJob(res.job_id);
    } catch (err) {
      notify("Analysis failed to start", err.message);
    } finally {
      setBusy(false);
    }
  };

  const pollJob = async (id) => {
    const tick = async () => {
      try {
        const job = await api(`/analysis/jobs/${id}`, { token });
        setJobStatus(job.status);
        if (job.status === "completed") {
          setAnalysis(job.result || job);
          notify("Analysis complete", "Results loaded");
          return;
        }
        if (job.status === "failed") {
          notify("Analysis failed", job.error || "Unknown error");
          return;
        }
        setTimeout(tick, 2000);
      } catch (err) {
        notify("Job poll error", err.message);
      }
    };
    tick();
  };

  /* —— LANDING —— */
  if (screen === "landing") {
    return (
      <div className="landing">
        <header className="land-header">
          <span className="topbar-brand">MORPHEUS</span>
          <div>
            <button type="button" className="btn btn-ghost" onClick={() => setLoginOpen(true)}>
              Sign in
            </button>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
            >
              Get started
            </button>
          </div>
        </header>
        <div className="land-hero">
          <div>
            <h1>Digital forensics workspace with integrity built into the case</h1>
            <p>
              Morpheus registers data sources, verifies fingerprints, maintains chain of custody,
              and runs Windows disk triage — in one examiner application.
            </p>
            <button
              type="button"
              className="btn btn-primary"
              onClick={() => (token ? setScreen("hub") : setLoginOpen(true))}
            >
              Get started
            </button>
            <ul style={{ marginTop: 16 }}>
              <li>Integrity verification on data sources and evidence</li>
              <li>Chain of custody with the investigation</li>
              <li>Windows E01 / disk image triage</li>
              <li>Android &amp; iOS support — coming soon</li>
            </ul>
          </div>
          <div className="panel land-card">
            <div className="panel-title">Investigation workflow</div>
            <div className="panel-body">
              <ol>
                <li>Create a case</li>
                <li>Register a data source (hash at collection)</li>
                <li>Verify integrity; review custody</li>
                <li>Run analysis; export certificate &amp; reports</li>
              </ol>
            </div>
          </div>
        </div>
        <div className="land-grid">
          {[
            ["Evidence integrity", "Fingerprints at registration; re-verify any time."],
            ["Chain of custody", "Who handled what, visible on the case and certificate."],
            ["Windows triage", "Orchestrated analysis of disk images when you run it."],
            ["Defensible reports", "Integrity certificates and analysis outputs from the same case."],
          ].map(([t, d]) => (
            <div key={t} className="panel">
              <div className="panel-body">
                <h3>{t}</h3>
                <p>{d}</p>
              </div>
            </div>
          ))}
        </div>
        {loginOpen && (
          <Modal title="Sign in" onClose={() => setLoginOpen(false)}>
            <form onSubmit={login}>
              <label>Username</label>
              <input
                value={loginForm.username}
                onChange={(e) => setLoginForm({ ...loginForm, username: e.target.value })}
              />
              <label>Password</label>
              <input
                type="password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({ ...loginForm, password: e.target.value })}
              />
              {error && <p className="err-text">{error}</p>}
              <footer>
                <button type="button" className="btn" onClick={() => setLoginOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  Sign in
                </button>
              </footer>
            </form>
          </Modal>
        )}
        {toast && <Toast {...toast} />}
      </div>
    );
  }

  /* —— HUB —— */
  if (screen === "hub") {
    return (
      <div className="app-root">
        <TopBar user={user} onLogout={logout} />
        <div className="main-scroll">
          <div className="hub">
            <h1 className="page-title">Cases</h1>
            <p className="page-sub">Create an investigation or open an existing case.</p>
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
              <button type="button" className="hub-tile" onClick={() => loadCases().catch((e) => notify("Refresh failed", e.message))}>
                <strong>Refresh list</strong>
                <span>Reload cases from the Morpheus API.</span>
              </button>
            </div>
            <div className="panel">
              <div className="panel-title">Registered cases</div>
              <div className="panel-body" style={{ padding: 0 }}>
                {cases.length === 0 ? (
                  <div className="empty-state">No cases yet. Create one to begin.</div>
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
                            <button type="button" className="btn" onClick={() => openCase(c)}>
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
                onChange={(e) => setCaseForm({ ...caseForm, case_name: e.target.value })}
              />
              <div className="row-2">
                <div>
                  <label>Examiner</label>
                  <input
                    required
                    value={caseForm.examiner_name}
                    onChange={(e) => setCaseForm({ ...caseForm, examiner_name: e.target.value })}
                  />
                </div>
                <div>
                  <label>Organisation</label>
                  <input
                    value={caseForm.organisation}
                    onChange={(e) => setCaseForm({ ...caseForm, organisation: e.target.value })}
                  />
                </div>
              </div>
              <label>Email</label>
              <input
                type="email"
                value={caseForm.examiner_email}
                onChange={(e) => setCaseForm({ ...caseForm, examiner_email: e.target.value })}
              />
              <label>Description</label>
              <textarea
                value={caseForm.description}
                onChange={(e) => setCaseForm({ ...caseForm, description: e.target.value })}
              />
              {error && <p className="err-text">{error}</p>}
              <footer>
                <button type="button" className="btn" onClick={() => setCreateOpen(false)}>
                  Cancel
                </button>
                <button type="submit" className="btn btn-primary" disabled={busy}>
                  Create &amp; open
                </button>
              </footer>
            </form>
          </Modal>
        )}
        {toast && <Toast {...toast} />}
      </div>
    );
  }

  /* —— WORKSPACE —— */
  const summary = analysis?.report_summary || analysis?.summary || null;
  const preview = analysis?.artifacts_preview || [];

  return (
    <div className="app-root">
      <TopBar
        user={user}
        caseLabel={active ? `${active.case_number} — ${active.case_name}` : ""}
        onLogout={logout}
        onCases={() => setScreen("hub")}
      />
      <div className="shell">
        <aside className="sidebar">
          <div className="sidebar-section">Investigation</div>
          {[
            ["overview", "Case overview"],
            ["evidence", "Evidence sources"],
            ["analysis", "Analyze evidence"],
            ["custody", "Chain of custody"],
            ["reports", "Reports"],
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
            Artifact browser <span className="badge">Soon</span>
          </button>
          <button type="button" className="nav-item" disabled>
            Mobile (Android / iOS) <span className="badge">Soon</span>
          </button>
          <div className="sidebar-foot">
            Signed in as <strong>{user}</strong>
          </div>
        </aside>

        <div className="main">
          <div className="main-scroll">
            {view === "overview" && (
              <>
                <h1 className="page-title">Case overview</h1>
                <p className="page-sub">
                  {active?.case_number} · Integrity and analysis results for this investigation
                </p>

                <div
                  className={`banner ${
                    integrity
                      ? integrity.warnings === 0
                        ? "ok"
                        : "warn"
                      : "info"
                  }`}
                >
                  <div>
                    <strong>
                      {integrity
                        ? integrity.warnings === 0
                          ? "Integrity check passed"
                          : "Integrity problems detected"
                        : "Integrity has not been run for this case yet"}
                    </strong>
                    <span>
                      {integrity
                        ? `${integrity.ok} file(s) ok, ${integrity.warnings} warning(s)`
                        : "Register a data source, then verify fingerprints."}
                    </span>
                  </div>
                  <button type="button" className="btn" disabled={busy} onClick={runIntegrity}>
                    Verify integrity
                  </button>
                </div>

                <div className="toolbar">
                  <button type="button" className="btn" onClick={() => setAddSrcOpen(true)}>
                    Add data source
                  </button>
                  <button type="button" className="btn btn-primary" disabled={busy} onClick={startAnalysis}>
                    Analyze evidence
                  </button>
                  <button type="button" className="btn" disabled={busy} onClick={downloadCertificate}>
                    Integrity certificate
                  </button>
                </div>

                <div className="stats">
                  <div className="stat">
                    <label>Data sources</label>
                    <b>{dataSources.length}</b>
                    <small>Registered images</small>
                  </div>
                  <div className="stat">
                    <label>Analysis</label>
                    <b>{jobStatus || (analysis ? "done" : "—")}</b>
                    <small>{jobId ? `Job ${jobId.slice(0, 8)}…` : "Not started"}</small>
                  </div>
                  <div className="stat">
                    <label>Artifacts (preview)</label>
                    <b>{analysis?.artifact_count ?? "—"}</b>
                    <small>From last completed job</small>
                  </div>
                  <div className="stat">
                    <label>Integrity</label>
                    <b>{integrity ? (integrity.warnings === 0 ? "OK" : "Warn") : "—"}</b>
                    <small>Hash vs collection</small>
                  </div>
                </div>

                <div className="grid-2">
                  <div className="panel">
                    <div className="panel-title">Evidence sources</div>
                    <div className="panel-body">
                      {dataSources.length === 0 ? (
                        <div className="empty-state">
                          No data sources. Add a forensic image path to begin.
                        </div>
                      ) : (
                        dataSources.map((ds) => (
                          <div key={ds.id} style={{ marginBottom: 12 }}>
                            <strong>{ds.label || ds.original_filename}</strong>
                            <div className="mono" style={{ color: "var(--muted)" }}>
                              {ds.stored_path}
                            </div>
                            <div style={{ marginTop: 4 }}>
                              <span className={`tag ${ds.is_consistent === false ? "err" : "ok"}`}>
                                {ds.is_consistent === false ? "Inconsistent" : "Tracked"}
                              </span>{" "}
                              <span className="mono">{ds.sha256_hash?.slice(0, 20)}…</span>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  <div className="panel">
                    <div className="panel-title">Analysis summary</div>
                    <div className="panel-body">
                      {!analysis ? (
                        <div className="empty-state">
                          Run <strong>Analyze evidence</strong> to load orchestrator results into
                          this case. Nothing is hard-coded.
                        </div>
                      ) : (
                        <>
                          <div className="meta-grid">
                            <div>
                              <span>Artifact count</span>
                              <strong>{analysis.artifact_count ?? "—"}</strong>
                            </div>
                            <div>
                              <span>Job</span>
                              <strong>{jobStatus || "completed"}</strong>
                            </div>
                            <div>
                              <span>Manifest</span>
                              <strong className="mono" style={{ fontSize: 11 }}>
                                {analysis.manifest_path
                                  ? String(analysis.manifest_path).slice(-40)
                                  : "—"}
                              </strong>
                            </div>
                          </div>
                          {preview.length > 0 && (
                            <div style={{ marginTop: 12 }}>
                              <strong style={{ fontSize: 12 }}>Preview artifacts</strong>
                              {preview.slice(0, 8).map((a, i) => (
                                <div key={i} className="finding">
                                  <span className="dot" />
                                  <div>
                                    <strong>
                                      {a.artifact_type || a.type || "artifact"} —{" "}
                                      {a.name || a.path || "item"}
                                    </strong>
                                    <small className="mono">{a.path || ""}</small>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          {summary && (
                            <pre
                              style={{
                                marginTop: 12,
                                fontSize: 11,
                                overflow: "auto",
                                maxHeight: 180,
                                background: "#f5f7f8",
                                padding: 8,
                                border: "1px solid var(--border)",
                              }}
                            >
                              {typeof summary === "string"
                                ? summary
                                : JSON.stringify(summary, null, 2)}
                            </pre>
                          )}
                        </>
                      )}
                    </div>
                  </div>
                </div>
              </>
            )}

            {view === "evidence" && (
              <>
                <h1 className="page-title">Evidence sources</h1>
                <p className="page-sub">
                  Forensic images for this case. Hash is identity; path is location.
                </p>
                <div className="toolbar">
                  <button type="button" className="btn btn-primary" onClick={() => setAddSrcOpen(true)}>
                    Add data source
                  </button>
                  <button type="button" className="btn" disabled={busy} onClick={runIntegrity}>
                    Verify integrity
                  </button>
                </div>
                <div className="panel">
                  <div className="panel-body" style={{ padding: 0 }}>
                    {dataSources.length === 0 ? (
                      <div className="empty-state">No sources registered.</div>
                    ) : (
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Label</th>
                            <th>Path</th>
                            <th>SHA-256</th>
                            <th>Status</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataSources.map((ds) => (
                            <tr key={ds.id}>
                              <td>{ds.label || ds.original_filename}</td>
                              <td className="mono">{ds.stored_path}</td>
                              <td className="mono">{ds.sha256_hash?.slice(0, 24)}…</td>
                              <td>
                                <span className={`tag ${ds.is_consistent === false ? "err" : "ok"}`}>
                                  {ds.is_consistent === false ? "Problem" : "OK"}
                                </span>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "analysis" && (
              <>
                <h1 className="page-title">Analyze evidence</h1>
                <p className="page-sub">
                  Runs the Morpheus orchestrator against the primary registered data source.
                </p>
                <div className="toolbar">
                  <button type="button" className="btn btn-primary" disabled={busy} onClick={startAnalysis}>
                    Analyze evidence
                  </button>
                </div>
                <div className="panel">
                  <div className="panel-title">Sources to process</div>
                  <div className="panel-body">
                    {dataSources.length === 0 ? (
                      <div className="empty-state">Add a data source first.</div>
                    ) : (
                      <table className="data">
                        <thead>
                          <tr>
                            <th>Type</th>
                            <th>Path</th>
                            <th>Image</th>
                          </tr>
                        </thead>
                        <tbody>
                          {dataSources.map((ds) => (
                            <tr key={ds.id}>
                              <td>{ds.image_type || "image"}</td>
                              <td className="mono">{ds.stored_path}</td>
                              <td>{ds.original_filename}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                    {jobStatus && (
                      <p style={{ marginTop: 12 }}>
                        Status: <strong>{jobStatus}</strong>
                        {jobId && (
                          <span className="mono"> · {jobId}</span>
                        )}
                      </p>
                    )}
                  </div>
                </div>
              </>
            )}

            {view === "custody" && (
              <>
                <h1 className="page-title">Chain of custody</h1>
                <p className="page-sub">
                  Load the custody report from the API (same source as the integrity certificate).
                </p>
                <CustodyPanel caseNumber={active?.case_number} token={token} />
              </>
            )}

            {view === "reports" && (
              <>
                <h1 className="page-title">Reports</h1>
                <p className="page-sub">Integrity certificate and analysis outputs.</p>
                <div className="grid-2">
                  <div className="panel">
                    <div className="panel-title">Evidence integrity certificate</div>
                    <div className="panel-body">
                      <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>
                        PDF generated from current fingerprints and custody log.
                      </p>
                      <button
                        type="button"
                        className="btn btn-primary"
                        disabled={busy}
                        onClick={downloadCertificate}
                      >
                        Download PDF
                      </button>
                    </div>
                  </div>
                  <div className="panel">
                    <div className="panel-title">Analysis export</div>
                    <div className="panel-body">
                      {analysis?.manifest_path ? (
                        <p className="mono" style={{ fontSize: 11 }}>
                          {analysis.manifest_path}
                        </p>
                      ) : (
                        <div className="empty-state">Complete an analysis job to attach exports.</div>
                      )}
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
            <label>Absolute path to forensic image</label>
            <input
              required
              placeholder="/path/to/evidence.E01"
              value={srcForm.file_path}
              onChange={(e) => setSrcForm({ ...srcForm, file_path: e.target.value })}
            />
            <label>Label (optional)</label>
            <input
              value={srcForm.label}
              onChange={(e) => setSrcForm({ ...srcForm, label: e.target.value })}
            />
            <label>Collected by</label>
            <input
              value={srcForm.collected_by || user}
              onChange={(e) => setSrcForm({ ...srcForm, collected_by: e.target.value })}
            />
            {error && <p className="err-text">{error}</p>}
            <footer>
              <button type="button" className="btn" onClick={() => setAddSrcOpen(false)}>
                Cancel
              </button>
              <button type="submit" className="btn btn-primary" disabled={busy}>
                Register
              </button>
            </footer>
          </form>
        </Modal>
      )}
      {toast && <Toast {...toast} />}
    </div>
  );
}

function TopBar({ user, caseLabel, onLogout, onCases }) {
  return (
    <header className="topbar">
      <span className="topbar-brand">MORPHEUS</span>
      {caseLabel && (
        <span className="topbar-case">
          Case <strong>{caseLabel}</strong>
        </span>
      )}
      <div className="topbar-actions">
        {onCases && (
          <button type="button" className="btn btn-ghost" onClick={onCases}>
            Cases
          </button>
        )}
        <span className="topbar-user">{user}</span>
        <button type="button" className="btn btn-ghost" onClick={onLogout}>
          Sign out
        </button>
      </div>
    </header>
  );
}

function Modal({ title, children, onClose }) {
  return (
    <div className="modal-back" role="presentation" onClick={onClose}>
      <div className="modal" role="dialog" onClick={(e) => e.stopPropagation()}>
        <header>
          {title}
          <button
            type="button"
            className="btn-link"
            style={{ float: "right" }}
            onClick={onClose}
          >
            Close
          </button>
        </header>
        <div className="body">{children}</div>
      </div>
    </div>
  );
}

function Toast({ title, detail }) {
  return (
    <div className="toast">
      <strong>{title}</strong>
      {detail && <span>{detail}</span>}
    </div>
  );
}

function CustodyPanel({ caseNumber, token }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!caseNumber || !token) return;
    api(`/data-sources/${caseNumber}/custody-report`, { token })
      .then(setData)
      .catch((e) => setErr(e.message));
  }, [caseNumber, token]);

  if (err) return <div className="empty-state">{err}</div>;
  if (!data) return <div className="empty-state">Loading custody…</div>;

  const timeline = data.custody_timeline || [];
  return (
    <div className="panel">
      <div className="panel-title">
        Custody — {data.overall_status || "Status"} · {data.case_number}
      </div>
      <div className="panel-body">
        <p style={{ color: "var(--text-secondary)", fontSize: 12 }}>{data.overall_summary}</p>
        <ul className="activity" style={{ margin: 0, padding: 0 }}>
          {timeline.length === 0 && <li>No custody events yet.</li>}
          {timeline.map((e, i) => (
            <li key={i}>
              <strong>
                {e.what} — {e.who}
              </strong>
              <time>{e.when}</time>
              {e.detail && <div style={{ color: "var(--muted)" }}>{e.detail}</div>}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
